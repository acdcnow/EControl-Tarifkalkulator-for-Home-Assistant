"""Sensor platform of the E-Control Tarifkalkulator integration.

Every configured energy type becomes its own device that carries up to five
entities:

===============================  =========================================
Entity                           Content
===============================  =========================================
``cheapest_offer``               Total annual cost of the cheapest offer,
                                 with the offer details as attributes.
``cheapest_price_per_kwh``       All-in price of that offer in ``ct/kWh``.
``own_product``                  Annual cost of the configured own product.
``possible_saving``              Maximum saving against the own product.
``offers``                       Number of offers, with the full, capped
                                 offer list ("Top N") as attributes.
===============================  =========================================

The ``own_product`` and ``possible_saving`` entities only exist when the API
returned the configured comparison product.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EControlConfigEntry
from .api import Offer, RateResult
from .const import (
    ATTR_CONSUMPTION,
    ATTR_CUSTOMER_GROUP,
    ATTR_ENERGY_TYPE,
    ATTR_FAILED_REASON,
    ATTR_GRID_OPERATOR,
    ATTR_GRID_AREA_ID,
    ATTR_GRID_OPERATOR_ID,
    ATTR_LAST_SUCCESSFUL_UPDATE,
    ATTR_OFFERS,
    ATTR_OFFER_COUNT,
    ATTR_REFERENCE_PERIOD,
    ATTR_SOURCE,
    ATTR_SWITCHING_DISCOUNTS,
    ATTR_ZIP_CODE,
    DOMAIN,
    ENERGY_TYPE_LABELS,
)
from .coordinator import EControlCoordinator

#: Unit used for all-in prices per kilowatt hour.
UNIT_CT_PER_KWH = "ct/kWh"


@dataclass(frozen=True, kw_only=True)
class EControlSensorDescription(SensorEntityDescription):
    """Describes one sensor of the integration."""

    value_fn: Callable[[RateResult], Any]
    attributes_fn: Callable[[RateResult, EControlCoordinator], dict[str, Any]] | None = (
        None
    )
    exists_fn: Callable[[RateResult], bool] | None = None


def _cheapest_offer(result: RateResult) -> Offer | None:
    """Return the cheapest offer of a comparison."""
    return result.cheapest


def _offer_attributes(offer: Offer | None, result: RateResult) -> dict[str, Any]:
    """Return the attributes that describe a single offer."""
    if offer is None:
        return {}
    return offer.to_attributes(consumption_kwh=result.consumption_kwh)


def _offers_attributes(
    result: RateResult, coordinator: EControlCoordinator
) -> dict[str, Any]:
    """Return the comparison context and the capped offer list."""
    settings = coordinator.settings.get(result.energy_type)
    offers = result.payable_offers[: max(coordinator.offer_count, 0)]
    return {
        ATTR_ZIP_CODE: coordinator.zip_code,
        ATTR_CUSTOMER_GROUP: coordinator.customer_group,
        ATTR_ENERGY_TYPE: result.energy_type,
        ATTR_SOURCE: coordinator.source,
        ATTR_CONSUMPTION: result.consumption_kwh,
        ATTR_GRID_OPERATOR: result.grid_operator_name,
        ATTR_GRID_OPERATOR_ID: result.grid_operator_id,
        ATTR_GRID_AREA_ID: result.grid_area_id,
        ATTR_SWITCHING_DISCOUNTS: (
            settings.include_switching_discounts if settings else None
        ),
        ATTR_REFERENCE_PERIOD: settings.reference_period if settings else None,
        ATTR_OFFER_COUNT: result.priced_offer_count,
        ATTR_LAST_SUCCESSFUL_UPDATE: result.fetched_at.isoformat(),
        "price_range_from": (
            float(result.range_from) if result.range_from is not None else None
        ),
        "price_range_to": (
            float(result.range_to) if result.range_to is not None else None
        ),
        ATTR_OFFERS: [
            offer.to_attributes(consumption_kwh=result.consumption_kwh)
            for offer in offers
        ],
    }


def _saving_attributes(
    result: RateResult, coordinator: EControlCoordinator
) -> dict[str, Any]:
    """Describe what the best offer is compared against."""
    settings = coordinator.settings.get(result.energy_type)
    cheapest = result.cheapest
    return {
        "cheapest_brand": cheapest.brand_name if cheapest else None,
        "cheapest_product": cheapest.product_name if cheapest else None,
        "cheapest_annual_cost": (
            float(cheapest.annual_cost)
            if cheapest is not None and cheapest.annual_cost is not None
            else None
        ),
        "own_brand": settings.brand_name if settings else None,
        "own_product": settings.product_name if settings else None,
        "offer_count": result.priced_offer_count,
    }


SENSOR_DESCRIPTIONS: tuple[EControlSensorDescription, ...] = (
    EControlSensorDescription(
        key="cheapest_offer",
        translation_key="cheapest_offer",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        suggested_display_precision=2,
        value_fn=lambda result: (
            float(result.cheapest.annual_cost) if result.cheapest else None
        ),
        attributes_fn=lambda result, coordinator: {
            **_offer_attributes(_cheapest_offer(result), result),
            ATTR_OFFER_COUNT: result.priced_offer_count,
            ATTR_GRID_OPERATOR: result.grid_operator_name,
        },
    ),
    EControlSensorDescription(
        key="cheapest_price_per_kwh",
        translation_key="cheapest_price_per_kwh",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UNIT_CT_PER_KWH,
        suggested_display_precision=2,
        value_fn=lambda result: (
            float(per_kwh)
            if (cheapest := result.cheapest) is not None
            and (per_kwh := cheapest.price_per_kwh(result.consumption_kwh)) is not None
            else None
        ),
        attributes_fn=lambda result, coordinator: {
            ATTR_CONSUMPTION: result.consumption_kwh,
            ATTR_ENERGY_TYPE: result.energy_type,
        },
    ),
    EControlSensorDescription(
        key="own_product",
        translation_key="own_product",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        suggested_display_precision=2,
        exists_fn=lambda result: result.own_product is not None,
        value_fn=lambda result: (
            float(result.own_product.annual_cost) if result.own_product else None
        ),
        attributes_fn=lambda result, coordinator: {
            **_offer_attributes(result.own_product, result),
            ATTR_OFFER_COUNT: result.priced_offer_count,
        },
    ),
    EControlSensorDescription(
        key="possible_saving",
        translation_key="possible_saving",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        suggested_display_precision=2,
        exists_fn=lambda result: result.own_product is not None,
        value_fn=lambda result: (
            float(result.max_saving) if result.max_saving is not None else None
        ),
        attributes_fn=_saving_attributes,
    ),
    EControlSensorDescription(
        key="offers",
        translation_key="offers",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda result: result.priced_offer_count,
        attributes_fn=_offers_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of one energy type per device.

    The entities are created for every *configured* energy type, not only for
    the types whose first comparison succeeded. A comparison that could not be
    run therefore shows up as an unavailable entity instead of silently
    disappearing, and the reason is published in the ``failed_energy_type``
    attribute.
    """
    coordinator = entry.runtime_data.coordinator

    entities: list[EControlSensor] = []
    for energy_type in coordinator.energy_types:
        result = (coordinator.data or {}).get(energy_type)
        for description in SENSOR_DESCRIPTIONS:
            if description.exists_fn is not None and (
                result is None or not description.exists_fn(result)
            ):
                continue
            entities.append(
                EControlSensor(coordinator, description, energy_type=energy_type)
            )

    async_add_entities(entities)


class EControlSensor(CoordinatorEntity[EControlCoordinator], SensorEntity):
    """One tariff sensor of one energy type."""

    entity_description: EControlSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EControlCoordinator,
        description: EControlSensorDescription,
        *,
        energy_type: str,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.energy_type = energy_type
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{energy_type}_{description.key}"
        )

    @property
    def _result(self) -> RateResult | None:
        """Return the comparison of this entity's energy type."""
        return (self.coordinator.data or {}).get(self.energy_type)

    @property
    def available(self) -> bool:
        """Return whether a result for this energy type is present."""
        return super().available and self._result is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device this sensor belongs to (one per energy type)."""
        label = ENERGY_TYPE_LABELS.get(self.energy_type, self.energy_type)
        target = self.coordinator.targets.get(self.energy_type)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry.entry_id}_{self.energy_type}")},
            entry_type=DeviceEntryType.SERVICE,
            name=f"E-Control {label}",
            manufacturer="E-Control",
            model=target.grid_operator_name if target else label,
            configuration_url="https://www.e-control.at/tarifkalkulator",
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        result = self._result
        if result is None:
            return None
        return self.entity_description.value_fn(result)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the sensor attributes."""
        result = self._result
        if result is None:
            reason = self.coordinator.failed.get(self.energy_type)
            return {ATTR_FAILED_REASON: reason} if reason else None
        if self.entity_description.attributes_fn is None:
            return None
        attributes = self.entity_description.attributes_fn(result, self.coordinator)
        # Drop placeholders that could not be filled.
        return {key: value for key, value in attributes.items() if value is not None}
