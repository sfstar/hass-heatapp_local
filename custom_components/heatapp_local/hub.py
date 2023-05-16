from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant
import threading
from collections import OrderedDict

import logging

_LOGGER = logging.getLogger(__name__)

class HeatappHub:

    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str) -> None:
        """Initialize."""
        self.host = host
        self.user = user
        self.password = password
        loginManager = Login("http://" + self.host)
        credentials = hass.async_add_executor_job(loginManager.authorize, self.user, self.password)
        api = ApiMethods(credentials, "http://" + self.host)
        sceneManager = SceneManager(api)
        self._lock = threading.Lock()