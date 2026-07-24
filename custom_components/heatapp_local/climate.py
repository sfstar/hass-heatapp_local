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

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
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
    """Set up heatapp climate entities from a config entry[cite: 2]."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if coordinator.data:
        async_add_entities(
            HeatAppClimateEntity(coordinator, idx) 
            for idx, _ in enumerate(coordinator.data)
        )


class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device[cite: 2]."""

    def __init__(self, coordinator, heatapp_room_idx: int) -> None:
        """Pass coordinator to CoordinatorEntity[cite: 2]."""
        super().__init__(coordinator)
        self.idx = heatapp_room_idx
        self._activeMode = HVACMode.HEAT
        self._activePreset = PRESET_NONE
        self._schedulePeriodsForRoom = {"success": False}
        _LOGGER.info("Initializing heatapp thermostat entity index: %s", self.idx)

    def _get_room_base(self) -> dict:
        """Safely retrieve base room dictionary."""
        if not self.coordinator.data or self.idx >= len(self.coordinator.data):
            return {}
        room = self.coordinator.data[self.idx]
        return room if isinstance(room, dict) else {}

    def _get_room_data(self) -> dict:
        """Safely retrieve inner room data dictionary."""
        room_base = self._get_room_base()
        data = room_base.get("data", {})
        return data if isinstance(data, dict) else {}

    async def async_added_to_hass(self) -> None:
        """Run tasks when entity is added to registry[cite: 2]."""
        await super().async_added_to_hass() 
        try: 
            await self.initOneTimeInformation()
        except Exception as exc: 
            room_base = self._get_room_base()
            name = room_base.get("name", f"Index {self.idx}")
            _LOGGER.warning(
                "Failed to fetch switching times for %s: %s", 
                name, exc
            ) 
            
    async def initOneTimeInformation(self) -> None:
        """Fetch historical scheduling details via hub wrapper[cite: 2]."""
        room_base = self._get_room_base()
        room_data = self._get_room_data()
        room_name = room_base.get("name") or room_data.get("name")
        room_id = room_data.get("id")

        if room_name and room_id is not None:
            self._schedulePeriodsForRoom = await self.hass.async_add_executor_job(
                self.coordinator.api_hub.get_switching_times, 
                room_name, 
                room_id
            )

    def getTodaysSchedule(self) -> list | None:
        """Extract current day metrics from switching schedule[cite: 2]."""
        if getattr(self, "_schedulePeriodsForRoom", None) and self._schedulePeriodsForRoom.get("success"):            
            weekDayIndex = datetime.datetime.now().weekday()
            listStartIndex = weekDayIndex * 3
            switching_times = self._schedulePeriodsForRoom.get("switchingtimes", [])
            if switching_times and len(switching_times) >= listStartIndex + 3:
                return switching_times[listStartIndex:listStartIndex+3]
        return None

    @property
    def unique_id(self) -> str | None:
        """Return a stable unique ID based on the room ID[cite: 2]."""
        room_id = self._get_room_data().get("id")
        return str(room_id) if room_id is not None else None

    @property
    def name(self) -> str | None:
        """Return the name of the entity[cite: 2]."""
        room_base = self._get_room_base()
        room_data = self._get_room_data()
        return room_base.get("name") or room_data.get("name") or f"Heatapp Room {self.idx}"

    @property
    def device_info(self) -> dict:
        """Return the device info[cite: 2]."""
        uid = self.unique_id
        if not uid:
            return {}
        return {
            "identifiers": {(DOMAIN, uid)},
            "name": self.name,
            "manufacturer": "HeatApp (Danfoss)",
            "via_device": (DOMAIN, self.coordinator.entry_id),
        }

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement[cite: 2]."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature[cite: 2]."""
        return self._get_room_data().get("desiredTemperature")

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature[cite: 2]."""
        return 0.5

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature[cite: 2]."""
        return self._get_room_data().get("actualTemperature")

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature[cite: 2]."""
        return self._get_room_data().get("minTemperature", 5.0)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature[cite: 2]."""
        return self._get_room_data().get("maxTemperature", 30.0)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features[cite: 2]."""
        return SUPPORT_FLAGS

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes[cite: 2]."""
        return [HVACMode.HEAT, HVACMode.OFF]  

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode[cite: 2]."""
        self.determine_preset_membership()
        return self._activePreset

    @property
    def preset_modes(self) -> list[str]:
        """Return available presets[cite: 2]."""
        return [PRESET_NONE, PRESET_BOOST, PRESET_HOLIDAY, PRESET_GO, PRESET_PARTY, PRESET_STANDBY]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode[cite: 2]."""
        self.determine_mode_membership()
        return self._activeMode

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode via the hub context[cite: 2]."""
        room_id = self._get_room_data().get("id")
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

    def is_between_obj(self, time, range_start, range_end) -> bool:
        """Helper to parse and evaluate schedule hours boundaries[cite: 2]."""
        time_format = '%H:%M'
        range_start = datetime.datetime.strptime(range_start, time_format).time()
        range_end = datetime.datetime.strptime(range_end, time_format).time()
        return (range_start <= time <= range_end) or (
            range_end <= range_start and (range_start <= time or time <= range_end)
        )

    def determine_preset_membership(self) -> None:
        """Process status variables into matching HA entity presets[cite: 2]."""
        roomstatus = self._get_room_data().get("roomstatus")
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
        """Evaluate operational heating flags based on temperature differentials[cite: 2]."""
        room_data = self._get_room_data()
        actual_temp = room_data.get("actualTemperature")
        target_temp = room_data.get("desiredTemperature")

        if actual_temp is None or target_temp is None:
            return

        if self._activePreset == PRESET_NONE:
            if actual_temp <= target_temp or actual_temp > target_temp:
                self._activeMode = HVACMode.HEAT
            else:
                self._activeMode = HVACMode.OFF
        elif self._activePreset in [PRESET_PARTY, PRESET_BOOST]:
            self._activeMode = HVACMode.HEAT 
        else:
            self._activeMode = HVACMode.OFF
        
    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature via hub wrapper[cite: 2]."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        room_id = self._get_room_data().get("id")
        if temperature is None or room_id is None:
            return
        await self.hass.async_add_executor_job(
            self.coordinator.api_hub.set_temperature, temperature, room_id
        )
        await self.coordinator.async_request_refresh()

    async def turn_on(self, **kwargs) -> None: 
        """Turn entity execution on[cite: 2]."""
        if self._activePreset in [PRESET_BOOST, PRESET_NONE]:
            return
        
        room_id = self._get_room_data().get("id")
        if room_id is None:
            return
        
        await self.hass.async_add_executor_job(
            self.coordinator.api_hub.remove_member_from_scene, 
            room_id, self._activePreset, True
        )
        await self.coordinator.async_request_refresh()

    async def turn_off(self, **kwargs) -> None:
        """Force device into tracking standby configuration[cite: 2]."""
        if self._activePreset in [PRESET_GO, PRESET_HOLIDAY, PRESET_STANDBY]:
            return
        
        room_id = self._get_room_data().get("id")
        if room_id is None:
            return
            
        await self.hass.async_add_executor_job(
            self.coordinator.api_hub.add_member_to_scene, 
            room_id, "Standby", True
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set target operational runtime environment mode mapping[cite: 2]."""
        if hvac_mode == HVACMode.HEAT:
            await self.turn_on()
        elif hvac_mode == HVACMode.OFF:
            await self.turn_off()
