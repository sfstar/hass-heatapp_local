import logging
import datetime
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from heatapp.sceneManager import SceneManager

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

PRESET_NONE = "None"
PRESET_BOOST = "Boost"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"

async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
):
    """Set up the climate platform from a config entry."""
    # Retrieve the coordinator from hass.data, initialized in __init__.py
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    api = coordinator.api
    scene_manager = SceneManager(api)

    entities = []
    # Loop through the data to create entities for each room
    if coordinator.data:
        for i in range(len(coordinator.data)):
            entities.append(HeatAppClimateEntity(coordinator, i, api, scene_manager))
    
    async_add_entities(entities)

class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

    def __init__(self, coordinator, idx, api_object, scene_manager):
        super().__init__(coordinator)
        self.idx = idx
        self._api_object = api_object
        self._scene_manager = scene_manager
        self._active_preset = PRESET_NONE
        self._schedule_periods_for_room = {"success": False}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        try:
            await self.init_one_time_information()
        except Exception as exc:
            _LOGGER.warning("Failed to fetch switching times for index %s: %s", self.idx, exc)

    async def init_one_time_information(self):
        """Fetch switching times from the API."""
        room_data = self.coordinator.data[self.idx]["data"]
        self._schedule_periods_for_room = await self.hass.async_add_executor_job(
            self._api_object.getSwitchingTimes, room_data["name"], room_data["id"]
        )

    @property
    def name(self):
        try:
            return self.coordinator.data[self.idx]["name"]
        except (IndexError, KeyError, TypeError):
            return f"HeatApp Zone {self.idx}"

    @property
    def unique_id(self):
        return f"heatapp_{self.name}_{self.idx}"

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self):
        try:
            return float(self.coordinator.data[self.idx]["data"]["desiredTemperature"])
        except (IndexError, KeyError, TypeError, ValueError):
            return None

    @property
    def current_temperature(self):
        try:
            return float(self.coordinator.data[self.idx]["data"]["actualTemperature"])
        except (IndexError, KeyError, TypeError, ValueError):
            return None

    @property
    def hvac_mode(self):
        return HVACMode.AUTO

    @property
    def hvac_modes(self):
        return [HVACMode.AUTO, HVACMode.OFF]

    @property
    def supported_features(self):
        return SUPPORT_FLAGS

    @property
    def preset_mode(self):
        return self._active_preset

    @property
    def preset_modes(self):
        return [PRESET_NONE, PRESET_BOOST, PRESET_HOLIDAY, PRESET_GO, PRESET_PARTY, PRESET_STANDBY]
