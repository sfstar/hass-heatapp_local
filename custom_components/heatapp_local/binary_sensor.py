"""Binary sensor platform for HeatApp integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeatApp binary sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create the gateway status binary sensor
    entities = [HeatAppGatewayStatusEntity(coordinator, config_entry)]
    async_add_entities(entities)


class HeatAppGatewayStatusEntity(CoordinatorEntity, BinarySensorEntity):
    """Representation of HeatApp Gateway Connection Status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Gateway Connection"

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """Initialize the gateway binary sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_gateway_connectivity"

    @property
    def device_info(self) -> dict:
        """Link this sensor to the main HeatApp Gateway device entry."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry_id)},
            "name": "HeatApp Gateway",
            "manufacturer": "HeatApp (Danfoss)",
            "model": "Central Gateway",
        }

    @property
    def is_connected(self) -> bool:
        """Check if the gateway is responding and reports a healthy state."""
        # 1. First check if DataUpdateCoordinator successfully fetched data on the last cycle
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False

        # 2. Check for explicit error flags inside the coordinator payload structure
        data = self.coordinator.data

        # If payload contains a root status key
        if isinstance(data, dict):
            if data.get("status") == "problem" or data.get("error") is True:
                return False

            # Inspect underlying rooms to verify at least one is not in a failed/problem state
            for room in data.values():
                if isinstance(room, dict):
                    # Check base level or inner data level status
                    room_status = room.get("status")
                    inner_status = room.get("data", {}).get("status") if isinstance(room.get("data"), dict) else None
                    if room_status == "problem" or inner_status == "problem":
                        continue

        return True

    @property
    def is_on(self) -> bool:
        """Return True if the gateway is connected, False if disconnected."""
        return self.is_connected

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Expose connection diagnostic metadata."""
        return {
            "last_successful_update": self.coordinator.last_update_success_time,
            "gateway_entry_id": self.config_entry.entry_id,
        }
