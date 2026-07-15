"""The heatapp_local integration."""
from __future__ import annotations
import re
import logging  # 1. ADDED IMPORT

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_HOST, CONF_USER, CONF_PASSWORD, CONF_INTERVAL

# 2. DEFINED LOGGER AT TOP LEVEL
_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]

def _sanitize_host(host: str) -> str:
    """Extract just the IP or hostname from the config input."""
    # Remove http/https and any trailing paths/slashes
    clean_host = re.sub(r"^https?://", "", host)
    return clean_host.split('/')[0].rstrip('/')

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up heatapp from a config entry."""
    from .coordinator import heatAppDeviceUpdateCoordinator as Coordinator

    hass.data.setdefault(DOMAIN, {})

    # Sanitize the host: Remove protocol and paths before passing to the coordinator
    raw_host = config_entry.data[CONF_HOST]
    sanitized_host = _sanitize_host(raw_host)

    # 3. USE THE DEFINED _LOGGER
    _LOGGER.debug("Connecting to HeatApp host: %s (sanitized from %s)", sanitized_host, raw_host)

    coordinator = Coordinator(
        hass,
        sanitized_host, # Pass only the clean IP/Hostname
        config_entry.data[CONF_USER],
        config_entry.data[CONF_PASSWORD],
        config_entry.options.get(CONF_INTERVAL, 30),
    )

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()
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
