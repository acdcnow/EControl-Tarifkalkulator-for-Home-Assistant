"""The E-Control Tarifkalkulator integration.

The integration publishes the results of the Austrian E-Control tariff
calculator (Tarifkalkulator) into Home Assistant: for every configured energy
type it finds the cheapest offer, prices it against the user's own product and
exposes the full comparison.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import EControlCoordinator, EControlRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

#: Typing alias for the config entry of this domain.
type EControlConfigEntry = ConfigEntry[EControlRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: EControlConfigEntry) -> bool:
    """Set up one E-Control Tarifkalkulator config entry.

    The first refresh resolves the grid operator and the comparison product of
    every configured energy type and already fetches a first comparison, so the
    entities are populated as soon as they are added. A failure is reported as
    :class:`~homeassistant.exceptions.ConfigEntryNotReady` with the original
    reason, which makes Home Assistant retry the setup instead of leaving the
    user with an empty integration.
    """
    coordinator = EControlCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        # The coordinator raises a bare ConfigEntryNotReady and keeps the real
        # reason in ``__cause__``; Home Assistant should log that reason.
        reason = str(err.__cause__ or err) or "The E-Control interface is unreachable"
        raise ConfigEntryNotReady(reason) from err

    entry.runtime_data = EControlRuntimeData(
        client=coordinator.client, coordinator=coordinator
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EControlConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.async_close()
    return unloaded
