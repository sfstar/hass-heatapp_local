"""The heatapp_local integration."""
from __future__ import annotations

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_HOST, CONF_USER, CONF_PASSWORD, CONF_INTERVAL

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    from .coordinator import heatAppDeviceUpdateCoordinator as Coordinator

    hass.data.setdefault(DOMAIN, {})

    coordinator = Coordinator(
        hass,
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_USER],
        config_entry.data[CONF_PASSWORD],
        config_entry.options.get(CONF_INTERVAL, 30),
    )

    coordinator.entry_id = config_entry.entry_id
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Register the main Hub device in Home Assistant
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        name="Heatapp Gateway",
        manufacturer="HeatApp",
        model="Local Gateway",
        configuration_url=config_entry.data[CONF_HOST],
    )

    # Perform initial refresh and handle failures so HA retries later
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Initial data fetch failed: {err}") from err

    if not coordinator.data:
        # Defensive: if no data after first refresh, retry later
        raise ConfigEntryNotReady("HeatApp returned no data during initial setup")

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)
