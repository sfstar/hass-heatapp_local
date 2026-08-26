"""Hub for Heatapp Local."""
from __future__ import annotations

import logging
import threading
from http.client import RemoteDisconnected

import requests

from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class HeatappHub:
    """Wrapper class to handle Heatapp API communication safely."""

    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str) -> None:
        """Initialize the Hub."""
        self.hass = hass
        self.host = host
        self.user = user
        self.password = password
        self._lock = threading.Lock()

        self.login_manager = Login(self.host)
        self.api = None
        self.scene_manager = None

    def _ensure_session(self) -> bool:
        """Ensure active session exists, re-authenticating if necessary."""
        if self.api is None or self.scene_manager is None:
            try:
                credentials = self.login_manager.authorize(self.user, self.password)
                self.api = ApiMethods(credentials, self.host)
                self.scene_manager = SceneManager(self.api)
            except Exception as e:
                _LOGGER.error("Failed to authenticate or initialize API: %s", e)
                self.api = None
                self.scene_manager = None
                return False
        return True

    def ping_gateway(self) -> bool:
        """Quick health check to confirm gateway connectivity."""
        with self._lock:
            return self._ensure_session()

    def fetch_data_sync(self) -> list:
        """Synchronously initialize the API and fetch data with auto-reauthentication."""
        with self._lock:
            if not self._ensure_session():
                raise ConnectionError("Unable to establish session with Heatapp gateway.")

            # --- API DATA FETCHING ---
            try:
                raw_rooms = self.api.getRoomsList()

                if not raw_rooms:
                    _LOGGER.debug("API returned no data.")
                    return []

                formatted_data = []

                if isinstance(raw_rooms, list):
                    for room in raw_rooms:
                        formatted_data.append({
                            "name": room.get("name", "Unknown Room"),
                            "data": room
                        })
                elif isinstance(raw_rooms, dict):
                    rooms_list = raw_rooms.get("rooms") or raw_rooms.get("roomList") or []
                    for room in rooms_list:
                        formatted_data.append({
                            "name": room.get("name", "Unknown Room"),
                            "data": room
                        })

                return formatted_data

            except (RemoteDisconnected, requests.exceptions.RequestException) as e:
                _LOGGER.warning("Connection lost or dropped by Heatapp device, resetting session: %s", e)
                self.api = None
                self.scene_manager = None
                raise ConnectionError(f"Heatapp communication error: {e}") from e
            except AttributeError:
                _LOGGER.error("Method `getRoomsList` encountered an error or does not exist.")
                return []
            except Exception as e:
                _LOGGER.error("Unexpected error fetching data: %s", e)
                return []

    def get_switching_times(self, room_name: str, room_id: int) -> dict:
        """Safely fetch switching times for a room."""
        with self._lock:
            if not self._ensure_session():
                return {"success": False}
            try:
                return self.api.getSwitchingTimes(room_name, room_id)
            except Exception as e:
                _LOGGER.error("Failed to fetch switching times: %s", e)
                self.api = None
                self.scene_manager = None
                return {"success": False}

    def set_temperature(self, temperature: float, room_id: int) -> None:
        """Safely set room temperature."""
        with self._lock:
            if not self._ensure_session():
                return
            try:
                self.api.setTemp(temperature, room_id)
            except Exception as e:
                _LOGGER.error("Failed to set temperature: %s", e)
                self.api = None
                self.scene_manager = None

    def add_member_to_scene(self, room_id: int, preset_mode: str, force: bool) -> None:
        """Safely add room to a preset/scene."""
        with self._lock:
            if not self._ensure_session():
                return
            try:
                self.scene_manager.addMemberToScene(room_id, preset_mode, force)
            except Exception as e:
                _LOGGER.error("Failed to add member to scene: %s", e)
                self.api = None
                self.scene_manager = None

    def remove_member_from_scene(self, room_id: int, preset_mode: str, force: bool) -> None:
        """Safely remove room from a preset/scene."""
        with self._lock:
            if not self._ensure_session():
                return
            try:
                self.scene_manager.removeMemberFromScene(room_id, preset_mode, force)
            except Exception as e:
                _LOGGER.error("Failed to remove member from scene: %s", e)
                self.api = None
                self.scene_manager = None
