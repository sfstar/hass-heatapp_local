from __future__ import annotations
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .hub import HeatappHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# coordinator.py

# coordinator.py
class heatAppDeviceUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, host, user, password, interval) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval),
        )
        self.hass = hass
        # Initialize the Hub, but DO NOT call any network methods here
        self.api = HeatappHub(hass, host, user, password)

    async def _async_update_data(self) -> dict:
        """Fetch data."""
        try:
            # Wrap the API call in an executor job. This is the pattern 
            # that worked in b7edc75.
            return await self.hass.async_add_executor_job(self.api.get_all_data)
        except Exception as err:
            _LOGGER.error("Error communicating with API: %r", err)
            raise UpdateFailed(f"Error communicating with API: {err}")
