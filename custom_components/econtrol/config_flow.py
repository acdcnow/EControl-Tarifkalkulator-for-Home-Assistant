"""Config and options flow of the E-Control Tarifkalkulator integration.

The user picks a data source, a postal code and one or more energy types, and
enters a yearly consumption for each of them. The grid operator and a
comparison product are resolved automatically.

The comparison product is not optional: the documented interface *requires*
``comparisonOptions.brandId`` and ``mainProductId`` for every rate query, even
when the user is not interested in a comparison. The integration therefore
always resolves one -- the grid operator's own brand (``brandHome``) and that
brand's default product (``defaultId``) -- which is exactly what the public
calculator pre-selects. The options flow allows picking a different product, so
the saving sensors can refer to the contract the user actually holds.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EControlAuthError, EControlConnectionError, EControlError, create_client
from .api.constants import PARTNER_DEVELOPMENT_URL, PARTNER_PRODUCTION_URL
from .const import (
    CONF_CONSUMPTION,
    CONF_CUSTOMER_GROUP,
    CONF_ENERGY_TYPES,
    CONF_ENERGY_TYPE_OPTION,
    CONF_OFFER_COUNT,
    CONF_PASSWORD,
    CONF_PRODUCT_ASSOCIATION_ID,
    CONF_PRODUCT_ID,
    CONF_PRODUCT_NAME,
    CONF_REFERENCE_PERIOD,
    CONF_SCAN_INTERVAL_HOURS,
    CONF_SOURCE,
    CONF_SWITCHING_DISCOUNTS,
    CONF_URL,
    CONF_USERNAME,
    CONF_ZIP_CODE,
    CUSTOMER_GROUPS,
    DEFAULT_CUSTOMER_GROUP,
    DEFAULT_OFFER_COUNT,
    DEFAULT_REFERENCE_PERIOD,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DEFAULT_SOURCE,
    DEFAULT_SWITCHING_DISCOUNTS,
    DOMAIN,
    ENERGY_TYPE_LABELS,
    ENERGY_TYPES,
    MAX_CONSUMPTION,
    MAX_OFFER_COUNT,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_CONSUMPTION,
    MIN_OFFER_COUNT,
    MIN_SCAN_INTERVAL_HOURS,
    REFERENCE_PERIODS,
    SOURCE_PARTNER,
    SOURCE_PUBLIC,
    EnergyType,
)
from .coordinator import EControlCoordinator, entry_settings

_LOGGER = logging.getLogger(__name__)

#: Default yearly consumption offered for each energy type.
DEFAULT_CONSUMPTION: dict[str, int] = {
    EnergyType.POWER: 3500,
    EnergyType.POWER_FEED_IN: 2000,
    EnergyType.GAS: 15000,
}

#: Key of the product selector in the options flow.
CONF_PRODUCT = "product"

#: Sentinel of the options flow meaning "use the resolved default product".
OPTION_KEEP_DEFAULT = "__keep_default__"


# --------------------------------------------------------------------------
# Selectors
# --------------------------------------------------------------------------
def _source_selector() -> selector.SelectSelector:
    """Return the data source selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[SOURCE_PUBLIC, SOURCE_PARTNER],
            translation_key=CONF_SOURCE,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _energy_type_selector(multiple: bool = True) -> selector.SelectSelector:
    """Return the energy type selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(ENERGY_TYPES),
            translation_key=CONF_ENERGY_TYPE_OPTION,
            multiple=multiple,
            mode=(
                selector.SelectSelectorMode.LIST
                if multiple
                else selector.SelectSelectorMode.DROPDOWN
            ),
        )
    )


def _consumption_selector() -> selector.NumberSelector:
    """Return the yearly consumption selector."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_CONSUMPTION,
            max=MAX_CONSUMPTION,
            step=1,
            unit_of_measurement="kWh",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _period_selector() -> selector.SelectSelector:
    """Return the comparison period selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(REFERENCE_PERIODS),
            translation_key=CONF_REFERENCE_PERIOD,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _energy_type_label(energy_type: str) -> str:
    """Return the human readable label of an energy type."""
    return ENERGY_TYPE_LABELS.get(energy_type, energy_type)


async def _validate_connection(
    hass: HomeAssistant,
    config: dict[str, Any],
    *,
    zip_code: str,
    energy_type: str,
) -> None:
    """Check the endpoint and the credentials against the real service."""
    client = create_client(async_get_clientsession(hass), config)
    try:
        await client.async_validate(zip_code=zip_code, energy_type=energy_type)
    finally:
        await client.async_close()


def _error_key(err: EControlError) -> str:
    """Map an API error onto a config flow error key."""
    if isinstance(err, EControlAuthError):
        return "invalid_auth"
    if isinstance(err, EControlConnectionError):
        return "cannot_connect"
    return "invalid_response"


class EControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow with empty progress state."""
        self._source: str = DEFAULT_SOURCE
        self._zip_code: str = ""
        self._customer_group: str = DEFAULT_CUSTOMER_GROUP
        self._energy_types: list[str] = []
        self._partner: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Step 1: source, postal code, energy types
    # ------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the source, the postal code and the energy types."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._source = str(user_input[CONF_SOURCE])
            self._zip_code = str(user_input[CONF_ZIP_CODE]).strip()
            self._customer_group = str(
                user_input.get(CONF_CUSTOMER_GROUP) or DEFAULT_CUSTOMER_GROUP
            )
            self._energy_types = [
                energy_type
                for energy_type in user_input.get(CONF_ENERGY_TYPES, [])
                if energy_type in tuple(EnergyType)
            ]

            if not self._zip_code.isdigit() or len(self._zip_code) != 4:
                errors[CONF_ZIP_CODE] = "invalid_zip_code"
            elif not self._energy_types:
                errors[CONF_ENERGY_TYPES] = "no_energy_type"
            else:
                await self.async_set_unique_id(
                    f"{self._source}_{self._zip_code}_"
                    f"{'-'.join(sorted(self._energy_types))}"
                )
                self._abort_if_unique_id_configured()

                if self._source == SOURCE_PARTNER:
                    return await self.async_step_partner()
                return await self.async_step_consumption()

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE, default=self._source): _source_selector(),
                vol.Required(
                    CONF_ZIP_CODE, default=self._zip_code
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_CUSTOMER_GROUP, default=self._customer_group
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(CUSTOMER_GROUPS),
                        translation_key=CONF_CUSTOMER_GROUP,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_ENERGY_TYPES,
                    default=self._energy_types or [EnergyType.POWER],
                ): _energy_type_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    # ------------------------------------------------------------------
    # Step 2 (partner source only): credentials
    # ------------------------------------------------------------------
    async def async_step_partner(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the credentials of the partner interface."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._partner = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_URL: user_input.get(CONF_URL) or PARTNER_PRODUCTION_URL,
            }
            try:
                await _validate_connection(
                    self.hass,
                    self._base_config(),
                    zip_code=self._zip_code,
                    energy_type=self._energy_types[0],
                )
            except EControlError as err:
                _LOGGER.debug("Partner interface validation failed: %s", err)
                errors["base"] = _error_key(err)
            else:
                return await self.async_step_consumption()

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): selector.TextSelector(),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
                vol.Optional(
                    CONF_URL, default=PARTNER_PRODUCTION_URL
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[PARTNER_PRODUCTION_URL, PARTNER_DEVELOPMENT_URL],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="partner", data_schema=schema, errors=errors)

    # ------------------------------------------------------------------
    # Step 3: one consumption per energy type
    # ------------------------------------------------------------------
    async def async_step_consumption(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect one yearly consumption per selected energy type."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_connection(
                    self.hass,
                    self._base_config(),
                    zip_code=self._zip_code,
                    energy_type=self._energy_types[0],
                )
            except EControlError as err:
                _LOGGER.debug("Interface validation failed: %s", err)
                errors["base"] = _error_key(err)
            else:
                labels = ", ".join(
                    _energy_type_label(item) for item in self._energy_types
                )
                return self.async_create_entry(
                    title=f"E-Control {self._zip_code} ({labels})",
                    data={
                        **self._base_config(),
                        CONF_ENERGY_TYPES: self._energy_types,
                    },
                    options={
                        CONF_SCAN_INTERVAL_HOURS: DEFAULT_SCAN_INTERVAL_HOURS,
                        CONF_OFFER_COUNT: DEFAULT_OFFER_COUNT,
                        **{
                            energy_type: {
                                CONF_CONSUMPTION: int(
                                    user_input[CONF_CONSUMPTION][energy_type]
                                ),
                                CONF_SWITCHING_DISCOUNTS: bool(
                                    user_input[CONF_SWITCHING_DISCOUNTS]
                                ),
                                CONF_REFERENCE_PERIOD: user_input[CONF_REFERENCE_PERIOD],
                            }
                            for energy_type in self._energy_types
                        },
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_CONSUMPTION): section(
                    vol.Schema(
                        {
                            vol.Required(
                                energy_type,
                                default=DEFAULT_CONSUMPTION.get(energy_type, 3500),
                            ): _consumption_selector()
                            for energy_type in self._energy_types
                        }
                    )
                ),
                vol.Optional(
                    CONF_SWITCHING_DISCOUNTS, default=DEFAULT_SWITCHING_DISCOUNTS
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_REFERENCE_PERIOD, default=DEFAULT_REFERENCE_PERIOD
                ): _period_selector(),
            }
        )
        return self.async_show_form(
            step_id="consumption", data_schema=schema, errors=errors
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _base_config(self) -> dict[str, Any]:
        """Return the config entry data collected so far."""
        return {
            CONF_SOURCE: self._source,
            CONF_ZIP_CODE: self._zip_code,
            CONF_CUSTOMER_GROUP: self._customer_group,
            **self._partner,
        }

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "EControlOptionsFlow":
        """Return the options flow."""
        return EControlOptionsFlow()


class EControlOptionsFlow(OptionsFlowWithReload):
    """Adjust the comparison settings of an existing entry.

    The flow derives from
    :class:`~homeassistant.config_entries.OptionsFlowWithReload`
    (``automatic_reload = True``), so a change of the consumption, of the
    comparison period or of the selected product takes effect immediately
    without the user having to reload the integration. No config entry update
    listeners are registered anywhere in this integration, which is what that
    base class requires.
    """

    def __init__(self) -> None:
        """Initialise the options flow."""
        self._selected: str | None = None

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init", menu_options=["settings", "product"]
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Adjust consumption, discount handling, period and polling."""
        merged = self._merged
        energy_types = self._energy_types

        if user_input is not None:
            options = self._base_options()
            for energy_type in energy_types:
                block = options[energy_type]
                block[CONF_CONSUMPTION] = int(
                    user_input[CONF_CONSUMPTION][energy_type]
                )
                block[CONF_SWITCHING_DISCOUNTS] = bool(
                    user_input[CONF_SWITCHING_DISCOUNTS]
                )
                block[CONF_REFERENCE_PERIOD] = user_input[CONF_REFERENCE_PERIOD]
            options[CONF_SCAN_INTERVAL_HOURS] = int(user_input[CONF_SCAN_INTERVAL_HOURS])
            options[CONF_OFFER_COUNT] = int(user_input[CONF_OFFER_COUNT])
            return self.async_create_entry(data=options)

        first = next(
            (merged[item] for item in energy_types if merged.get(item)), {}
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_CONSUMPTION): section(
                    vol.Schema(
                        {
                            vol.Required(
                                energy_type,
                                default=merged.get(energy_type, {}).get(
                                    CONF_CONSUMPTION,
                                    DEFAULT_CONSUMPTION.get(energy_type, 3500),
                                ),
                            ): _consumption_selector()
                            for energy_type in energy_types
                        }
                    )
                ),
                vol.Optional(
                    CONF_SWITCHING_DISCOUNTS,
                    default=first.get(
                        CONF_SWITCHING_DISCOUNTS, DEFAULT_SWITCHING_DISCOUNTS
                    ),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_REFERENCE_PERIOD,
                    default=first.get(CONF_REFERENCE_PERIOD, DEFAULT_REFERENCE_PERIOD),
                ): _period_selector(),
                vol.Optional(
                    CONF_SCAN_INTERVAL_HOURS,
                    default=int(
                        merged.get(
                            CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS
                        )
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_HOURS,
                        max=MAX_SCAN_INTERVAL_HOURS,
                        step=1,
                        unit_of_measurement="h",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_OFFER_COUNT,
                    default=int(merged.get(CONF_OFFER_COUNT, DEFAULT_OFFER_COUNT)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_OFFER_COUNT,
                        max=MAX_OFFER_COUNT,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    # ------------------------------------------------------------------
    # Product selection (two steps, so no free text selector is needed)
    # ------------------------------------------------------------------
    async def async_step_product(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the energy type whose comparison product should change."""
        available: list[selector.SelectOptionDict] = []
        for energy_type in self._energy_types:
            if await self._products(energy_type):
                available.append(
                    selector.SelectOptionDict(
                        value=energy_type, label=_energy_type_label(energy_type)
                    )
                )

        if not available:
            return self.async_abort(reason="no_products")

        if user_input is not None:
            self._selected = str(user_input["energy_type"])
            return await self.async_step_product_select()

        return self.async_show_form(
            step_id="product",
            data_schema=vol.Schema(
                {
                    vol.Required("energy_type"): _energy_type_selector(multiple=False)
                }
            ),
        )

    async def async_step_product_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the product the comparison is made against."""
        energy_type = self._selected
        if energy_type is None:
            return await self.async_step_product()

        products = await self._products(energy_type)
        if not products:
            return self.async_abort(reason="no_products")

        options = self._base_options()
        if user_input is not None:
            block = options[energy_type]
            selection = str(user_input[CONF_PRODUCT])
            if selection == OPTION_KEEP_DEFAULT:
                block.pop(CONF_PRODUCT_ID, None)
                block.pop(CONF_PRODUCT_ASSOCIATION_ID, None)
                block.pop(CONF_PRODUCT_NAME, None)
            else:
                product = next(
                    (item for item in products if str(item[0]) == selection), None
                )
                if product is not None:
                    block[CONF_PRODUCT_ID] = product[0]
                    block[CONF_PRODUCT_NAME] = product[1]
                    block.pop(CONF_PRODUCT_ASSOCIATION_ID, None)
            return self.async_create_entry(data=options)

        current = (self._merged.get(energy_type) or {}).get(CONF_PRODUCT_NAME)
        keep_label = (
            f"Keep automatic default ({current})"
            if current
            else "Keep automatic default"
        )
        choices = [
            selector.SelectOptionDict(value=OPTION_KEEP_DEFAULT, label=keep_label)
        ]
        choices.extend(
            selector.SelectOptionDict(value=str(product_id), label=name)
            for product_id, name in products
        )

        return self.async_show_form(
            step_id="product_select",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRODUCT, default=OPTION_KEEP_DEFAULT
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"energy_type": _energy_type_label(energy_type)},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @property
    def _merged(self) -> dict[str, Any]:
        """Return the merged data and options of the entry."""
        return entry_settings(self.config_entry)

    @property
    def _energy_types(self) -> list[str]:
        """Return the energy types of the entry."""
        return [
            str(item)
            for item in (self._merged.get(CONF_ENERGY_TYPES) or [])
            if str(item) in tuple(EnergyType)
        ]

    def _base_options(self) -> dict[str, Any]:
        """Return the current options as a mutable copy."""
        merged = self._merged
        options: dict[str, Any] = {
            CONF_SCAN_INTERVAL_HOURS: int(
                merged.get(CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS)
            ),
            CONF_OFFER_COUNT: int(merged.get(CONF_OFFER_COUNT, DEFAULT_OFFER_COUNT)),
        }
        for energy_type in self._energy_types:
            options[energy_type] = dict(merged.get(energy_type) or {})
        return options

    async def _products(self, energy_type: str) -> list[tuple[int, str]]:
        """Load the selectable products of an energy type, tolerating failures."""
        runtime = getattr(self.config_entry, "runtime_data", None)
        coordinator: EControlCoordinator | None = getattr(runtime, "coordinator", None)
        if coordinator is None:
            return []
        try:
            return list(await coordinator.async_get_products(energy_type))
        except EControlError as err:
            _LOGGER.debug("Cannot load products for %s: %s", energy_type, err)
            return []
