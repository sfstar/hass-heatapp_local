from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant
import threading
from collections import OrderedDict

import logging

_LOGGER = logging.getLogger(__name__)

# hub.py
class HeatappHub:
    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str) -> None:
        self.host = host.strip()
        # Ensure we don't have double slashes
        self.base_url = f"http://{self.host}"
        self.user = user
        self.password = password
        self.api = None
        self._lock = threading.Lock()

    def get_all_data(self):
        with self._lock:
            if self.api is None:
                # Try pointing directly to the admin login endpoint 
                # as indicated by your curl test
                login_url = f"{self.base_url}/admin/login/index"
                _LOGGER.debug("Authenticating against: %s", login_url)
                
                # Check if your Login class allows passing a specific URL
                # If it doesn't, you must patch the 'heatapp' library 
                # to follow redirects or point to the right URL.
                loginManager = Login(self.base_url) 
                credentials = loginManager.authorize(self.user, self.password)
                self.api = ApiMethods(credentials, self.base_url)
            return self.api.get_data()
