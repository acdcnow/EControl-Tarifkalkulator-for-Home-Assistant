"""Data update coordinator of the E-Control Tarifkalkulator integration.

One coordinator serves one config entry and therefore one postal code and one
set of energy types. Each energy type is a separate comparison against the API,
and each of them becomes its own Home Assistant device.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EControlError,
    RateRequest,
    RateResult,
    TarifkalkulatorClient,
    create_client,
)
from .const import (
    CONF_BRAND_ID,
    CONF_BRAND_NAME,
    CONF_CONSUMPTION,
    CONF_CUSTOMER_GROUP,
    CONF_ENERGY_TYPES,
    CONF_OFFER_COUNT,
    CONF_PRODUCT_ASSOCIATION_ID,
    CONF_PRODUCT_ID,
    CONF_PRODUCT_NAME,
    CONF_REFERENCE_PERIOD,
    CONF_SCAN_INTERVAL_HOURS,
    CONF_SOURCE,
    CONF_SWITCHING_DISCOUNTS,
    CONF_ZIP_CODE,
    DEFAULT_CUSTOMER_GROUP,
    DEFAULT_OFFER_COUNT,
    DEFAULT_REFERENCE_PERIOD,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DEFAULT_SOURCE,
    DEFAULT_SWITCHING_DISCOUNTS,
    DOMAIN,
    EnergyType,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EnergyTypeSettings:
    """The user's configuration for one energy type."""

    energy_type: str
    consumption_kwh: int
    include_switching_discounts: bool = DEFAULT_SWITCHING_DISCOUNTS
    reference_period: str = DEFAULT_REFERENCE_PERIOD
    brand_id: int | None = None
    brand_name: str | None = None
    product_id: int | None = None
    product_association_id: int | None = None
    product_name: str | None = None


@dataclass(slots=True)
class ComparisonTarget:
    """The resolved grid operator and comparison product of one energy type."""

    grid_operator_id: int
    grid_area_id: int
    grid_operator_name: str


@dataclass(slots=True)
class EControlRuntimeData:
    """Objects stored in ``ConfigEntry.runtime_data``."""

    client: TarifkalkulatorClient
    coordinator: EControlCoordinator


def _float_or(value: Any, default: float) -> float:
    """Return ``value`` as float, falling back to ``default``."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_or_none(value: Any) -> int | None:
    """Return ``value`` as int, or ``None``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def entry_settings(entry: ConfigEntry) -> dict[str, Any]:
    """Return the merged data and options of a config entry."""
    return {**entry.data, **entry.options}


def parse_energy_settings(entry: ConfigEntry) -> dict[str, EnergyTypeSettings]:
    """Build the per energy type settings from a config entry."""
    merged = entry_settings(entry)
    raw_types = merged.get(CONF_ENERGY_TYPES) or []
    if isinstance(raw_types, str):
        raw_types = [raw_types]

    settings: dict[str, EnergyTypeSettings] = {}
    for energy_type in raw_types:
        if energy_type not in tuple(EnergyType):
            _LOGGER.warning("Ignoring unknown energy type %s", energy_type)
            continue
        block = merged.get(energy_type)
        block = block if isinstance(block, dict) else {}
        consumption = _int_or_none(block.get(CONF_CONSUMPTION))
        if consumption is None:
            _LOGGER.error(
                "No consumption configured for %s in entry %s", energy_type, entry.title
            )
            continue
        settings[energy_type] = EnergyTypeSettings(
            energy_type=energy_type,
            consumption_kwh=consumption,
            include_switching_discounts=bool(
                block.get(CONF_SWITCHING_DISCOUNTS, DEFAULT_SWITCHING_DISCOUNTS)
            ),
            reference_period=str(
                block.get(CONF_REFERENCE_PERIOD) or DEFAULT_REFERENCE_PERIOD
            ),
            brand_id=_int_or_none(block.get(CONF_BRAND_ID)),
            brand_name=block.get(CONF_BRAND_NAME) or None,
            product_id=_int_or_none(block.get(CONF_PRODUCT_ID)),
            product_association_id=_int_or_none(block.get(CONF_PRODUCT_ASSOCIATION_ID)),
            product_name=block.get(CONF_PRODUCT_NAME) or None,
        )
    return settings


class EControlCoordinator(DataUpdateCoordinator[dict[str, RateResult]]):
    """Fetch and hold the tariff comparisons of one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        merged = entry_settings(entry)
        self.entry = entry
        self.zip_code = str(merged.get(CONF_ZIP_CODE) or "")
        self.customer_group = str(
            merged.get(CONF_CUSTOMER_GROUP) or DEFAULT_CUSTOMER_GROUP
        )
        self.source = str(merged.get(CONF_SOURCE) or DEFAULT_SOURCE)
        self.offer_count = int(
            _float_or(merged.get(CONF_OFFER_COUNT), DEFAULT_OFFER_COUNT)
        )
        self.settings = parse_energy_settings(entry)

        #: Energy types whose last comparison failed, with a human readable reason.
        self.failed: dict[str, str] = {}
        #: Resolved grid operator per energy type, filled by :meth:`_async_setup`.
        self.targets: dict[str, ComparisonTarget] = {}

        self.client: TarifkalkulatorClient = create_client(
            async_get_clientsession(hass), merged
        )

        hours = _float_or(
            merged.get(CONF_SCAN_INTERVAL_HOURS), DEFAULT_SCAN_INTERVAL_HOURS
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.zip_code}",
            update_interval=timedelta(hours=hours),
            setup_method=self._async_setup,
        )

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    @property
    def energy_types(self) -> tuple[str, ...]:
        """Return the configured energy types, in the order of the entry."""
        return tuple(self.settings)

    async def _async_setup(self) -> None:
        """Resolve the grid operator and the comparison product of every type.

        The interface requires a comparison product for each call: the
        ``comparisonOptions.brandId`` and ``mainProductId`` fields are
        mandatory, so a rate request cannot be sent without one. The defaults
        are the grid operator's own brand (``brandHome``) and that brand's
        default product (``defaultId``), which is exactly what the public
        calculator pre-selects.

        A single energy type that cannot be resolved does not fail the whole
        entry: it is recorded in :attr:`failed` and its entities stay
        unavailable while the remaining types keep working. Only when *no*
        type is usable the entry is retried by Home Assistant.
        """
        await self._async_resolve_targets()
        if not self.targets:
            raise UpdateFailed(
                "No usable tariff comparison could be prepared for "
                f"{', '.join(self.settings) or 'any energy type'}"
            )

    async def _async_resolve_targets(self) -> None:
        """Fill :attr:`targets`, tolerating energy types that cannot be resolved."""
        for energy_type, settings in self.settings.items():
            if energy_type in self.targets:
                continue

            try:
                operator = await self.client.async_get_grid_operator(
                    zip_code=self.zip_code, energy_type=energy_type
                )
            except EControlError as err:
                self.failed[energy_type] = str(err)
                _LOGGER.error(
                    "Cannot resolve the grid operator for %s at %s: %s",
                    energy_type,
                    self.zip_code,
                    err,
                )
                continue

            if operator is None:
                self.failed[energy_type] = (
                    f"Postal code {self.zip_code} is not served for {energy_type}"
                )
                _LOGGER.error("%s", self.failed[energy_type])
                continue

            target = ComparisonTarget(
                grid_operator_id=operator.operator_id,
                grid_area_id=operator.grid_area_id,
                grid_operator_name=operator.name,
            )
            self.targets[energy_type] = target

            if settings.brand_id is None:
                settings.brand_id = operator.brand_id
            if settings.brand_id is not None and settings.product_id is None:
                await self._async_apply_default_product(
                    settings, target, brand_id=settings.brand_id
                )

            if settings.product_id is None:
                self.failed[energy_type] = (
                    "No comparison product could be determined; the interface "
                    "requires one for every query"
                )
                _LOGGER.error(
                    "No comparison product for %s in %s", energy_type, self.zip_code
                )
                continue

            self.failed.pop(energy_type, None)

    async def _async_apply_default_product(
        self,
        settings: EnergyTypeSettings,
        target: ComparisonTarget,
        *,
        brand_id: int,
    ) -> None:
        """Set the brand's default product on ``settings``."""
        request = self._build_request(settings, target, brand_id=brand_id)
        try:
            products = await self.client.async_get_products(
                request, brand_id=brand_id
            )
        except EControlError as err:
            _LOGGER.debug(
                "Cannot load the product list for %s: %s", settings.energy_type, err
            )
            return
        if not products:
            return
        product = next((item for item in products if item.is_default), products[0])
        settings.product_id = product.product_id
        settings.product_association_id = product.association_id
        settings.product_name = product.name

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------
    def _build_request(
        self,
        settings: EnergyTypeSettings,
        target: ComparisonTarget,
        *,
        brand_id: int | None = None,
    ) -> RateRequest:
        """Build the API request of one energy type."""
        return RateRequest(
            customer_group=self.customer_group,
            energy_type=settings.energy_type,
            zip_code=int(self.zip_code or 0),
            grid_operator_id=target.grid_operator_id,
            grid_area_id=target.grid_area_id,
            consumption_kwh=settings.consumption_kwh,
            brand_id=brand_id if brand_id is not None else settings.brand_id,
            product_id=settings.product_id,
            product_association_id=settings.product_association_id,
            product_name=settings.product_name,
            include_switching_discounts=settings.include_switching_discounts,
            reference_period=settings.reference_period,
        )

    async def async_get_products(
        self, energy_type: str
    ) -> tuple[tuple[int, str], ...]:
        """Return the selectable products ``(id, name)`` of an energy type.

        Used by the options flow so the user can pick the product they
        currently hold a contract for.
        """
        settings = self.settings.get(energy_type)
        target = self.targets.get(energy_type)
        if settings is None or target is None or settings.brand_id is None:
            return ()
        request = self._build_request(settings, target, brand_id=settings.brand_id)
        products = await self.client.async_get_products(
            request, brand_id=settings.brand_id
        )
        return tuple((product.product_id, product.name) for product in products)

    # ------------------------------------------------------------------
    # Update cycle
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, RateResult]:
        """Fetch every configured comparison.

        A failing energy type keeps the other types working: the failure is
        recorded in :attr:`failed` and only its own entities become
        unavailable. The coordinator reports a failure to Home Assistant only
        when no comparison at all could be fetched.
        """
        results: dict[str, RateResult] = {}
        failures: dict[str, str] = {}

        for energy_type, settings in self.settings.items():
            target = self.targets.get(energy_type)
            if target is None:
                failures.setdefault(energy_type, "No grid operator resolved")
                continue
            request = self._build_request(settings, target)
            try:
                results[energy_type] = await self.client.async_get_rates(request)
            except EControlError as err:
                failures[energy_type] = str(err)
                _LOGGER.warning(
                    "Tariff comparison for %s failed: %s", energy_type, err
                )

        # Reasons recorded during setup (no grid operator, no product) must
        # survive the update cycle.
        self.failed = {**self.failed, **failures}

        if not results:
            raise UpdateFailed(
                "; ".join(dict.fromkeys(self.failed.values()))
                or "No tariff comparison could be fetched"
            )

        return results
