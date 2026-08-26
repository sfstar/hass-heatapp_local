"""Platform for climate integration."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)

_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "None"
PRESET_BOOST = "Boost"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up heatapp climate entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities_added_key = f"{config_entry.entry_id}_entities_added"
    if hass.data[DOMAIN].get(entities_added_key, False):
        _LOGGER.debug("Climate entities already registered for this entry; skipping re-creation")
        return

    if coordinator.data:
        entities = []
        if isinstance(coordinator.data, dict):
            for room_key in coordinator.data.keys():
                entities.append(HeatAppClimateEntity(coordinator, room_key))
        elif isinstance(coordinator.data, list):
            for idx, _ in enumerate(coordinator.data):
                entities.append(HeatAppClimateEntity(coordinator, idx))

        if entities:
            async_add_entities(entities)
            hass.data[DOMAIN][entities_added_key] = True
            _LOGGER.info("Successfully added %d HeatApp climate entities", len(entities))
        else:
            _LOGGER.warning("Coordinator data found, but no entities could be generated")


class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_BOOST,
        PRESET_HOLIDAY,
        PRESET_GO,
        PRESET_PARTY,
        PRESET_STANDBY,
    ]

    def __init__(self, coordinator, room_key) -> None:
        """Initialize climate entity."""
        super().__init__(coordinator)
        self.room_key = room_key
        self._activeMode = HVACMode.HEAT
        self._activePreset = PRESET_NONE
        self._schedulePeriodsForRoom = {"success": False}

    def _get_room_base(self) -> dict:
        """Safely retrieve base room dictionary regardless of data structure type."""
        if not self.coordinator.data:
            return {}

        if isinstance(self.coordinator.data, dict):
            room = self.coordinator.data.get(self.room_key, {})
        elif isinstance(self.coordinator.data, list):
            if isinstance(self.room_key, int) and 0 <= self.room_key < len(self.coordinator.data):
                room = self.coordinator.data[self.room_key]
            else:
                return {}
        else:
            return {}

        return room if isinstance(room, dict) else {}

    def _get_room_data(self) -> dict:
        """Safely retrieve inner room data dictionary handling nested layers."""
        room_base = self._get_room_base()
        first_level = room_base.get("data", {})

        if isinstance(first_level, dict) and "data" in first_level and isinstance(first_level["data"], dict):
            return first_level["data"]

        return first_level if isinstance(first_level, dict) else {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        room_base = self._get_room_base()
        if not room_base:
            return False

        if room_base.get("status") == "problem":
            return False

        first_level = room_base.get("data", {})
        if isinstance(first_level, dict):
            if first_level.get("status") == "problem":
                return False
            inner_data = first_level.get("data", {})
            if isinstance(inner_data, dict) and inner_data.get("status") == "problem":
                return False

        return True

    async def async_added_to_hass(self) -> None:
        """Run tasks when entity is added to registry."""
        await super().async_added_to_hass()
        try:
            await self.initOneTimeInformation()
        except Exception as exc:
            room_base = self._get_room_base()
            name = room_base.get("name", f"Key {self.room_key}")
            _LOGGER.warning("Failed to fetch switching times for %s: %s", name, exc)

    async def initOneTimeInformation(self) -> None:
        """Fetch historical scheduling details via hub wrapper."""
        room_base = self._get_room_base()
        room_data = self._get_room_data()
        room_name = room_base.get("name") or room_data.get("name")
        room_id = room_data.get("id") or room_base.get("id")

        if room_name and room_id is not None:
            self._schedulePeriodsForRoom = await self.hass.async_add_executor_job(
                self.coordinator.api_hub.get_switching_times,
                room_name,
                room_id,
            )

    def getTodaysSchedule(self) -> list | None:
        """Extract current day metrics from switching schedule."""
        if getattr(self, "_schedulePeriodsForRoom", None) and self._schedulePeriodsForRoom.get("success"):
            week_day_index = datetime.datetime.now().weekday()
            list_start_index = week_day_index * 3
            switching_times = self._schedulePeriodsForRoom.get("switchingtimes", [])
            if switching_times and len(switching_times) >= list_start_index + 3:
                return switching_times[list_start_index : list_start_index + 3]
        return None

    @property
    def unique_id(self) -> str | None:
        """Return a stable unique ID based on the room ID."""
        room_data = self._get_room_data()
        room_base = self._get_room_base()
        room_id = room_data.get("id") or room_base.get("id") or self.room_id_fallback()
        return str(room_id) if room_id is not None else None

    def room_id_fallback(self) -> str:
        """Fallback unique identifier generation if room dict lacks explicit id."""
        room_base = self._get_room_base()
        return room_base.get("name") or f"heatapp_room_{self.room_key}"

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        room_base = self._get_room_base()
        room_data = self._get_room_data()
        return room_base.get("name") or room_data.get("name") or f"Heatapp Room {self.room_key}"

    @property
    def device_info(self) -> dict:
        """Return device registry information."""
        uid = self.unique_id
        if not uid:
            return {}
        return {
            "identifiers": {(DOMAIN, str(uid))},
            "name": self.name,
            "manufacturer": "HeatApp (Danfoss)",
            "via_device": (DOMAIN, self.coordinator.config_entry.entry_id),
        }

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        val = self._get_room_data().get("desiredTemperature")
        return float(val) if val is not None else None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        val = self._get_room_data().get("actualTemperature")
        return float(val) if val is not None else None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        val = self._get_room_data().get("minTemperature")
        return float(val) if val is not None else 5.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        val = self._get_room_data().get("maxTemperature")
        return float(val) if val is not None else 30.0

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported flags."""
        return SUPPORT_FLAGS

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        self.determine_preset_membership()
        return self._activePreset

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        self.determine_mode_membership()
        return self._activeMode

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Expose individual properties separately for automations and dashboards."""
        room_data = self._get_room_data()
        room_base = self._get_room_base()

        return {
            "current_temperature": self.current_temperature,
            "target_temperature": self.target_temperature,
            "active_preset": self.preset_mode,
            "active_hvac_mode": self.hvac_mode,
            "raw_room_status": room_data.get("roomstatus") or room_base.get("roomstatus"),
        }

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode via hub context."""
        room_data = self._get_room_data()
        room_base = self._get_room_base()
        room_id = room_data.get("id") or room_base.get("id")
        if room_id is None:
            return

        api_hub = self.coordinator.api_hub

        if self._activePreset != "" and preset_mode != self._activePreset:
            if self._activePreset != PRESET_NONE:
                await self.hass.async_add_executor_job(
                    api_hub.remove_member_from_scene, room_id, self._activePreset, True
                )

            if preset_mode != PRESET_NONE:
                await self.hass.async_add_executor_job(
                    api_hub.add_member_to_scene, room_id, preset_mode, True
                )

            self._activePreset = preset_mode
            await self.coordinator.async_request_refresh()

    def determine_preset_membership(self) -> None:
        """Process status variables into matching HA entity presets."""
        roomstatus = self._get_room_data().get("roomstatus")
        if roomstatus is None:
            roomstatus = self._get_room_base().get("roomstatus")
        if roomstatus is None:
            return

        if roomstatus == 43:
            self._activePreset = PRESET_PARTY
        elif roomstatus == 99:
            _LOGGER.warning("Room %s reports active problem status flag", self.name)
        elif roomstatus == 127:
            self._activePreset = PRESET_HOLIDAY
        elif roomstatus == 132:
            self._activePreset = PRESET_STANDBY
        elif roomstatus == 130:
            self._activePreset = PRESET_GO
        elif roomstatus == 46:
            self._activePreset = PRESET_BOOST
        elif roomstatus in [41, 51, 54, 122, 131, 137]:
            self._activePreset = PRESET_NONE
        else:
            _LOGGER.warning("Unknown status code %s encountered on room %s", roomstatus, self.name)
            self._activePreset = PRESET_NONE

    def determine_mode_membership(self) -> None:
        """Evaluate operational heating flags based on active presets."""
        if self._activePreset in [PRESET_NONE, PRESET_PARTY, PRESET_BOOST]:
            self._activeMode = HVACMode.HEAT
        else:
            self._activeMode = HVACMode.OFF

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature via hub wrapper."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        room_data = self._get_room_data()
        room_base = self._get_room_base()
        room_id = room_data.get("id") or room_base.get("id")
        if temperature is None or room_id is None:
            return

        if hasattr(self.coordinator.api_hub, "set_temperature"):
            await self.hass.async_add_executor_job(
                self.coordinator.api_hub.set_temperature, float(temperature), room_id
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn climate execution on."""
        if self._activePreset in [PRESET_BOOST, PRESET_NONE]:
            return

        room_data = self._get_room_data()
        room_base = self._get_room_base()
        room_id = room_data.get("id") or room_base.get("id")
        if room_id is None:
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api_hub.remove_member_from_scene,
            room_id,
            self._activePreset,
            True,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Force device into tracking standby configuration."""
        if self._activePreset in [PRESET_GO, PRESET_HOLIDAY, PRESET_STANDBY]:
            return

        room_data = self._get_room_data()
        room_base = self._get_room_base()
        room_id = room_data.get("id") or room_base.get("id")
        if room_id is None:
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api_hub.add_member_to_scene,
            room_id,
            PRESET_STANDBY,
            True,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set target operational runtime environment mode mapping."""
        if hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()
        elif hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
