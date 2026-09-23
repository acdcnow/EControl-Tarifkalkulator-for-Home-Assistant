"""Diagnostics support for the E-Control Tarifkalkulator integration.

The download is attached to an issue report and is publicly visible, so the
credentials of the partner interface are redacted before the payload leaves
the instance. Only the derived summaries of a comparison are exported -- the
full offer list can be several hundred kilobytes and adds no diagnostic value.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import EControlConfigEntry
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

#: Keys that are replaced by ``**REDACTED**`` in the published payload.
TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


def _comparison_summary(rate) -> dict[str, Any]:
    """Return the diagnostic summary of one rate comparison."""
    cheapest = rate.cheapest
    own = rate.own_product
    return {
        "grid_operator": rate.grid_operator_name,
        "grid_operator_id": rate.grid_operator_id,
        "grid_area_id": rate.grid_area_id,
        "consumption_kwh": rate.consumption_kwh,
        "fetched_at": rate.fetched_at.isoformat(),
        "offer_count": len(rate.offers),
        "priced_offer_count": rate.priced_offer_count,
        "max_saving": str(rate.max_saving),
        "annual_range": {
            "from": str(rate.range_from) if rate.range_from is not None else None,
            "to": str(rate.range_to) if rate.range_to is not None else None,
        },
        "cheapest": (
            {
                "name": cheapest.name,
                "supplier": cheapest.supplier_name,
                "annual_cost": str(cheapest.annual_cost),
                "price_per_kwh": str(cheapest.price_per_kwh(rate.consumption_kwh)),
            }
            if cheapest is not None
            else None
        ),
        "own_product": (
            {
                "name": own.name,
                "annual_cost": str(own.annual_cost),
                "extra_cost": str(own.extra_cost),
                "saving": str(own.saving),
            }
            if own is not None
            else None
        ),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EControlConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator

    return {
        "integration": {
            "domain": DOMAIN,
            "entry_id": entry.entry_id,
            "title": entry.title,
            "state": str(entry.state),
            "version": entry.version,
        },
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "client": {
            "source": coordinator.source,
            "base_url": coordinator.client.base_url,
            "zip_code": coordinator.zip_code,
            "customer_group": coordinator.customer_group,
            "update_interval": str(coordinator.update_interval),
            "offer_count": coordinator.offer_count,
        },
        "settings": {
            energy_type: {
                "consumption_kwh": settings.consumption_kwh,
                "include_switching_discounts": settings.include_switching_discounts,
                "reference_period": settings.reference_period,
                "brand_id": settings.brand_id,
                "brand_name": settings.brand_name,
                "product_id": settings.product_id,
                "product_association_id": settings.product_association_id,
                "product_name": settings.product_name,
            }
            for energy_type, settings in coordinator.settings.items()
        },
        "targets": {
            energy_type: {
                "grid_operator_id": target.grid_operator_id,
                "grid_area_id": target.grid_area_id,
                "grid_operator_name": target.grid_operator_name,
            }
            for energy_type, target in coordinator.targets.items()
        },
        "failed_energy_types": dict(coordinator.failed),
        "last_update_success": coordinator.last_update_success,
        "comparisons": {
            energy_type: _comparison_summary(rate)
            for energy_type, rate in (coordinator.data or {}).items()
        },
    }
