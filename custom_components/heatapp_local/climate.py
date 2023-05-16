from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_USER, CONF_PASSWORD, CONF_HOST

from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant import config_entries
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_IDLE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE,
    PRESET_BOOST,
)
from homeassistant.const import (
    ATTR_NAME,
    ATTR_TEMPERATURE,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    TEMP_CELSIUS,
)

import datetime

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import asyncio

from .const import (
    DOMAIN
)
import logging

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "None"
PRESET_BOOST = "Boost"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"

api = None
credentials = None
sceneManager = None
coordinator = None
async def async_setup_integration(hass, config_entry: config_entries.ConfigEntry, async_add_entities):
    #TODO add http prepend to conf host saved value 
    loginManager = Login("http://" + config_entry.options[CONF_HOST])
    credentials = await hass.async_add_executor_job(loginManager.authorize, config_entry.options[CONF_USER], config_entry.options[CONF_PASSWORD])
    api = ApiMethods(credentials, "http://" + config_entry.options[CONF_HOST])
    sceneManager = SceneManager(api)
    heatapp_coordinator: heatAppDeviceUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    """Config entry example."""
    # assuming API object stored here by __init__.py
    #api = hass.data[DOMAIN][entry.entry_id]
    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        devs = []
        roomData = await hass.async_add_executor_job(
            api.getRoomsList
            )
        return roomData
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
#            async with async_timeout.timeout(10):
#                return await api.fetch_data()
#        except ApiError as err:
#            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="climate",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=datetime.timedelta(seconds=2),
    )
    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()    
    
    async_add_entities(
        HeatAppClimateEntity(coordinator, heatapproom, api, sceneManager) for heatapproom, ent in enumerate(coordinator.data)
    ) 
  
#    hass.async_block_till_done()
    
async def async_setup_entry(    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,):
#    asyncio.run_coroutine_threadsafe(
#        async_setup_integration(hass,"http://" + config_entry.options[CONF_HOST], config_entry.options[CONF_USER], config_entry.options[CONF_PASSWORD]), hass.loop
#    ).result()
    hass.async_create_task(async_setup_integration(hass, config_entry, async_add_entities))

    #await hass.async_add_executor_job(prereq, hass,"http://" + config_entry.options[CONF_HOST], config_entry.options[CONF_USER], config_entry.options[CONF_PASSWORD])


#class HeatAppClimateEntity(ClimateEntity):
class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

#    def __init__(self, data, apiObject, scene, hass):
#        """Initialize the thermostat."""
    def __init__(self, coordinator, heatappRoomData, apiObject, scene):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = heatappRoomData
        #Ideally this should be done in a larger interval than the standard update interval or triggered by an service call
        self.initOneTimeInformation()
        #self._data = data
        self._apiObject = apiObject
        self._sceneManager = scene
        self._activeMode = ""
        self._activePreset = PRESET_NONE
        _LOGGER.info("initializing thermostat: %s", self.idx)
        _LOGGER.info("data: %s", self.coordinator.data[self.idx])
        #_LOGGER.info("initializing thermostat: %s", self._data["data"]["name"])

    async def initOneTimeInformation(self):
        self._schedulePeriodsForRoom = await self.hass.async_add_executor_job(
            self._apiObject.getSwitchingTimes, self.coordinator.data[self.idx]["data"]["name"], self.coordinator.data[self.idx]["data"]["id"]
        )

    def getTodaysSchedule(self):
        if self._schedulePeriodsForRoom["success"]:
            #Every weekday has an entry in the switching times array. Therefore, an offset needs to be applied to return the correct results
            listStartIndex = weekDayIndex * 3
            return self._schedulePeriodsForRoom["switchingtimes"][listStartIndex:listStartIndex+3]

    @property
    def unique_id(self):
        """Return a unique ID."""
#        return self._data["name"]
        return self.coordinator.data[self.idx]["name"]

    @property
    def name(self):
        """Return the name of the entity."""
#        return self._data["name"]
        return self.coordinator.data[self.idx]["name"]

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.coordinator.data[self.idx]["name"],
            "manufacturer": "HeatApp (danfoss)",
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
#        return self._data["data"]["desiredTemperature"]
        _LOGGER.info("the current temperatue in coordinator data is: %s", self.coordinator.data[self.idx]["data"]["desiredTemperature"])
        return self.coordinator.data[self.idx]["data"]["desiredTemperature"]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def current_temperature(self):
        """Return the current temperature."""
#        return self._data["data"]["actualTemperature"]
        return self.coordinator.data[self.idx]["data"]["actualTemperature"]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
#        return self._data["data"]["minTemperature"]
        _LOGGER.info("data: %s", self.coordinator.data[self.idx])
        return self.coordinator.data[self.idx]["data"]["minTemperature"]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
#        return self._data["data"]["maxTemperature"]
        return self.coordinator.data[self.idx]["data"]["maxTemperature"]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_AUTO]

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.
        Requires SUPPORT_PRESET_MODE.
        """
        self.determine_preset_membership()
        return self._activePreset
        

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        _LOGGER.info("preset_mode to enable is: %s", preset_mode)
        _LOGGER.info("room id for scene change is: %s", self.coordinator.data[self.idx]["data"]["id"])
        if self._activePreset != "":
            if preset_mode != self._activePreset:
                await self.hass.async_add_executor_job(
                    self._sceneManager.removeMemberFromScene, self.coordinator.data[self.idx]["data"]["id"], self._activePreset, True
                )
                _LOGGER.info("Scene removal : %s", self._activePreset)
                if preset_mode == PRESET_NONE:
                    self._activePreset = preset_mode
                if preset_mode != PRESET_NONE:
                    await self.hass.async_add_executor_job(
                        self._sceneManager.addMemberToScene, self.coordinator.data[self.idx]["data"]["id"], preset_mode, True
                    )
                    _LOGGER.info("Member has been added to scene: %s", self.coordinator.data[self.idx]["name"])
                    self._activePreset = preset_mode
        _LOGGER.info("Scene removal has been finished: %s", self.coordinator.data[self.idx]["name"])

    @property
    def preset_modes(self):
        return [PRESET_NONE,PRESET_BOOST,PRESET_HOLIDAY,PRESET_GO,PRESET_PARTY,PRESET_STANDBY]

    @property
    def hvac_mode(self):
        """Return current operation."""
        # TODO implement
        #if self._data.get("power", "").lower() == "on":
        #    return HVAC_MODE_HEAT
        #_LOGGER.info("Room id type is %s", type(self._data["data"]["id"]))
        self.determine_if_device_is_following_schema()
        self.determine_mode_membership()
        return self._activeMode

    def is_between(self, time, time_range):
        if time_range[1] < time_range[0]:
            return time >= time_range[0] or time <= time_range[1]
        return time_range[0] <= time <= time_range[1]
    
    def is_between_obj(self,time, range_start, range_end):
        #return datetime.time(time) < datetime.time(range_start) and datetime.time(time) <= datetime.time(range_end)
        #is_between = datetime.time(range_start)  < datetime.time(time) < datetime.time(range_end)
        #return is_between
        # Time Now
#        now = datetime.datetime.now().time()
        # Format the datetime string
#        time_format = '%Y-%m-%d %H:%M:%S'
        time_format = '%H:%M'
        # Convert the start and end datetime to just time
#        start = datetime.datetime.strptime(start, time_format).time()
#        end = datetime.datetime.strptime(end, time_format).time()
        range_start = datetime.datetime.strptime(range_start, time_format).time()
        range_end = datetime.datetime.strptime(range_end, time_format).time()
        #time = datetime.datetime.strptime(time, time_format).time()
        is_between = False
        is_between |= range_start <= time <= range_end
        is_between |= range_end <= range_start and (range_start <= time or time <= range_end)


    async def determine_if_device_is_following_schema(self):
        currentWeekdayIndex = datetime.datetime.now().weekday()
        currentTime = datetime.datetime.now().time()
        
        schedulePeriodsToday = self.getTodaysSchedule()
        #schedulePeriodsToday = await self.hass.async_add_executor_job(
        #    self._apiObject.getSwitchingTimesForWeekday, self.coordinator.data[self.idx]["data"]["name"], self.coordinator.data[self.idx]["data"]["id"], currentWeekdayIndex
        #)
        #schedulePeriodsToday = self._apiObject.getSwitchingTimesForWeekday(self.coordinator.data[self.idx]["data"]["name"], self.coordinator.data[self.idx]["data"]["id"], currentWeekdayIndex)
        _LOGGER.info("from time: %s", schedulePeriodsToday)
        
        desiredTempDaySchedule = None
        desiredTempDay2Schedule = None
        desiredTempNightSchedule = None

        if schedulePeriodsToday is not None: 
            desiredTempDaySchedule =  next((elem for elem in schedulePeriodsToday if elem is not None and elem["type"] == "H"), None) #(elem["type"] == "H" for elem in schedulePeriodsToday)
            desiredTempDay2Schedule = next((elem for elem in schedulePeriodsToday if elem is not None and elem["type"] == "L"), None) #any(elem["type"] == "L" for elem in schedulePeriodsToday) #L might not be correct
            desiredTempNightSchedule = next((elem for elem in schedulePeriodsToday if elem is not None and elem["type"] == "N"), None) #any(elem["type"] == "N" for elem in schedulePeriodsToday) #N might not be correct
        else:
            _LOGGER.warn("Unable to retrieve the schedule periods for today")

        if desiredTempDaySchedule is not None:
            #check current roomstatus matches the status code expected for this schedule and then skip
            #if self.is_between(currentTime, (desiredTempDaySchedule["from"], desiredTempDaySchedule["to"])) == True:
            _LOGGER.info("from time: %s", desiredTempDaySchedule["from"])
            _LOGGER.info("end time: %s", desiredTempDaySchedule["to"])
            if self.is_between_obj(currentTime, desiredTempDaySchedule["from"], desiredTempDaySchedule["to"]):
                return "Day"

        elif desiredTempDay2Schedule is not None:
            if self.is_between_obj(currentTime, desiredTempDay2Schedule["from"], desiredTempDay2Schedule["to"]):
                return "Evening"

        elif desiredTempNightSchedule is not None: 
            if self.is_between_obj(currentTime, desiredTempNightSchedule["from"], desiredTempNightSchedule["to"]):
                return "Night"

        return "Manual"


    def determine_preset_membership(self):
#        roomstatus = self._data["data"]["roomstatus"]
        roomstatus = self.coordinator.data[self.idx]["data"]["roomstatus"]
#        _LOGGER.info("Room name: %s has status", self._data["data"]["originalName"])
#        _LOGGER.info("code: %s ", self._data["data"]["roomstatus"] )
        if roomstatus == 43:
            
            self._activePreset = PRESET_PARTY
            _LOGGER.info("room has party mode active as scene for room: %s", self.coordinator.data[self.idx]["data"]["id"])
        elif roomstatus == 99:    
            _LOGGER.info("room has an problem active: %s", self.coordinator.data[self.idx]["data"]["originalName"])
        elif roomstatus == 127:
            self._activePreset = PRESET_HOLIDAY
        elif roomstatus == 132:
            self._activePreset = PRESET_STANDBY
        elif roomstatus == 130:
            self._activePreset = PRESET_GO
        elif roomstatus == 46:
            self._activePreset = PRESET_BOOST
        elif roomstatus == 122 or roomstatus == 51 or roomstatus == 41 or roomstatus == 131 or roomstatus == 54 or roomstatus == 137:
            #status code 54 hasn't positively been mapped to an scene however it appears to be linked being on or around the correct set temp
            #122 work according to schema, 51 user manually set an desired temp heating while 41 is used to define that the set temp would entail cooling
            #131 is used to indicate that the minimal normal (non scene) temp was manually set
            #137 seems to indicate that the outside and room temp is above the set value for that room
            self._activePreset = PRESET_NONE
            _LOGGER.info("Room has manual / schema mode active as scene for room %s", self.coordinator.data[self.idx]["data"]["id"])
        else:
            _LOGGER.warn("The room %s has entered an unknown preset please inform the developer (give the dev the following code %s). This will default to the none preset until fixed", self.coordinator.data[self.idx]["data"]["name"], roomstatus)
            self._activePreset = PRESET_NONE
#        _LOGGER.info("active scene %s", self._activeMode)
#        boostMember = self._sceneManager.isMemberOfScene(roomId, PRESET_BOOST)
#        if boostMember == True:
#            return 

    def determine_mode_membership(self):
        _LOGGER.info("active scene %s", self._activeMode)
        if self._activePreset == PRESET_NONE:
            if self.coordinator.data[self.idx]["data"]["actualTemperature"] < self.coordinator.data[self.idx]["data"]["desiredTemperature"]:
                self._activeMode = HVAC_MODE_HEAT
            elif self.coordinator.data[self.idx]["data"]["actualTemperature"] > self.coordinator.data[self.idx]["data"]["desiredTemperature"]:
                self._activeMode = HVAC_MODE_COOL
            elif self.coordinator.data[self.idx]["data"]["actualTemperature"] == self.coordinator.data[self.idx]["data"]["desiredTemperature"]:
                self._activeMode = HVAC_MODE_OFF
            
        elif self._activePreset == PRESET_PARTY:
            self._activeMode = HVAC_MODE_HEAT 

        elif self._activePreset == PRESET_HOLIDAY:
            self._activeMode = HVAC_MODE_OFF
            
        elif self._activePreset == PRESET_GO:
            self._activeMode = HVAC_MODE_OFF
            
        elif self._activePreset == PRESET_STANDBY:
            self._activeMode = HVAC_MODE_OFF
            
        elif self._activePreset == PRESET_BOOST:
            self._activeMode = HVAC_MODE_HEAT
        
        
    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self.hass.async_add_executor_job(
            self._apiObject.setTemp, temperature, self.coordinator.data[self.idx]["data"]["id"]
        )
        #self.coordinator.data[self.idx]["data"]["desiredTemperature"] = temperature
#    async def async_set_preset_mode(self, **kwargs):
        """Set new preset mode."""
        #return BOOST
        
    async def turn_on(self, **kwargs): 
        if self._activePreset == PRESET_BOOST or self._activePreset == PRESET_NONE: #should be based on temp whether something should be done
            return
        
        await self.hass.async_add_executor_job(
            self._sceneManager.removeMemberFromScene, self.coordinator.data[self.idx]["data"]["id"], self._activePreset, True
        )
        self.determine_mode_membership()

    async def turn_off(self, **kwargs):
        if self._activePreset == PRESET_GO or self._activePreset == PRESET_HOLIDAY or self._activePreset == PRESET_STANDBY: #should be based on temp whether something should be done
            return
        await self.hass.async_add_executor_job(
            self._sceneManager.addMemberToScene, self.coordinator.data[self.idx]["data"]["id"], "Standby", True
        )
        self.determine_mode_membership()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            await self.turn_on()
            return
        if hvac_mode == HVAC_MODE_OFF:
            await self.turn_off()
        # TODO implement
        #if hvac_mode == HVAC_MODE_HEAT:
        #    await self._heater.turn_on()
        #    return
        #if hvac_mode == HVAC_MODE_OFF:
        #    await self._heater.turn_off()

#    async def async_update(self):
#        """Retrieve latest state."""
#        result = await self.hass.async_add_executor_job(
#            self._apiObject.getSpecificRoom, self._data["data"]["id"]
#        )
#        #_LOGGER.info("update data obj: %s", result)
#        self._data = result
#        
#        self.hass.async_add_executor_job(self.determine_mode_membership, self._data["data"]["id"])
#        self.hass.async_add_executor_job(self.determine_preset_membership, self._data["data"]["id"])
#        _LOGGER.info("the active scene is: %s", self._activeMode)

#        return
        #try:
        #    token_info = await self._heater.control.refresh_access_token()
        #except ambiclimate.AmbiclimateOauthError:
        #    _LOGGER.error("Failed to refresh access token")
        #    return

        #if token_info:
        #    await self._store.async_save(token_info)

        #self._data = await self._heater.update_device()