"""Update Coordinator for Heatapp Local."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .hub import HeatappHub

_LOGGER = logging.getLogger(__name__)

class heatAppDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Gather data for the climate device."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        user: str,
        password: str,
        interval: int,
    ) -> None:
        """Initialize Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.api_hub = HeatappHub(hass, host, user, password)

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint asynchronously."""
        try:
            # Wrap in a timeout and run the synchronous hub methods in an executor thread
            async with asyncio.timeout(10):
                data = await self.hass.async_add_executor_job(self.api_hub.fetch_data_sync)
                
            if not data:
                raise UpdateFailed("No data received from Heatapp API")
                
            # Log the raw data payload to help identify key mismatches causing 'None' values in entities
            _LOGGER.debug("Raw Heatapp data received from API: %s", data)
                
            return data

        except TimeoutError as err:
            raise UpdateFailed(f"Timeout communicating with Heatapp API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Heatapp API: {err}") from err
