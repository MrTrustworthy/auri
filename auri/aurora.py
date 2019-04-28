import colorsys
import random
import re
from typing import Union, Any, Dict, List

import requests
from requests import HTTPError

from auri.effect import Effect


class AuroraException(Exception):
    pass


class Aurora(object):
    def __init__(self, ip_address: str, name: str, mac: str, auth_token: Union[str, None]):
        self.ip_address = ip_address
        self.auth_token = auth_token
        self.name = name
        self.device_url = f"http://{self.ip_address}:16021/api/v1"
        self.authenticated_url = f"{self.device_url}/{self.auth_token}"
        self.token_url = f"{self.device_url}/new"
        self.mac = mac

    def __str__(self):
        token = "loaded" if self.auth_token is not None else "not loaded"
        return f"<Aurora '{self.name}' (IP: {self.ip_address}, MAC: {self.mac}, Token: {token})>"

    def __repr__(self):
        return str(self)

    # Heavy lifting (AKA actually interacting with the Aurora) is done by those two functions

    def __command(self, method: str, endpoint: str, *, authenticated: bool = True, data: Dict[str, Any] = None):

        # Check for auth precondition
        if authenticated and not self.auth_token:
            raise AuroraException("Aurora has no active token, can't run any functions that require auth")

        url = f"{self.authenticated_url if authenticated else self.device_url}/{endpoint}"
        kwargs = {} if data is None else {"json": data}
        response = requests.request(method, url, **kwargs)

        self._convert_response_exceptions(response)

        return None if response.text == "" else response.json()

    def _convert_response_exceptions(self, response):
        # Check for auth postconditions and give more precise error messages in case of failure
        if response.status_code in (401, 403):
            raise AuroraException("Token not valid. Please re-do setup or, if you are in setup, "
                                  "hold the power button for ~5 seconds until the LED flashes")

        try:
            response.raise_for_status()
        except HTTPError as e:
            raise AuroraException(f"Error when handling request for {str(self)}, message was {str(e)}")

    # Interfaces for setup and SerDe

    def generate_token(self):
        response_data = self.__command("post", "new", authenticated=False)
        self.auth_token = response_data.get('auth_token')
        assert self.auth_token is not None, "Auth token is still None after generating it, this shouldn't happen"

    def serialize(self):
        return {
            self.ip_address: {
                "name": self.name,
                "token": self.auth_token,
                "mac": self.mac,
                "default": False
            }
        }

    @classmethod
    def deserialize(cls, ip, data):
        return cls(ip, data["name"], data["mac"], data["token"])

    # Properties

    @property
    def info(self):
        """Returns the full Aurora Info request.

        Useful for debugging since it's just a fat dump."""
        return self.__command("get", "")

    @property
    def color_mode(self):
        """Returns the current color mode."""
        return self.__command("get", "state/colorMode")

    @property
    def firmware(self):
        """Returns the firmware version of the device"""
        return self.__command("get", "").get("firmwareVersion")

    @property
    def model(self):
        """Returns the model number of the device. (Always returns 'NL22')"""
        return self.__command("get", "").get("model")

    @property
    def serial_number(self):
        """Returns the serial number of the device"""
        return self.__command("get", "").get("serialNo")

    @property
    def on(self):
        """Returns True if the device is on, False if it's off"""
        return self.__command("get", "state/on/value")

    @on.setter
    def on(self, value: bool):
        """Turns the device on/off. True = on, False = off"""
        data = {"on": value}
        self.__command("put", "state", data=data)

    @property
    def brightness(self):
        """Returns the brightness of the device (0-100)"""
        return self.__command("get", "state/brightness/value")

    @brightness.setter
    def brightness(self, level):
        """Sets the brightness to the given level (0-100)"""
        data = {"brightness": {"value": level}}
        self.__command("put", "state", data=data)

    # Effect and manipulation methods

    def identify(self):
        """Briefly flash the panels on and off"""
        self.__command("put", "identify", data={})

    def get_active_effect_name(self):
        """Returns the active effect"""
        return self.__command("get", "effects/select")

    def set_active_effect(self, effect_name: str):
        """Sets the active effect to the name specified"""
        data = {"select": effect_name}
        self.__command("put", "effects", data=data)

    def get_effects(self) -> List[Effect]:
        data = {"write": {"command": "requestAll"}}
        effect_data = self.__command("put", "effects", data=data)
        animation_data = effect_data.get("animations", [])
        return sorted((Effect(data) for data in animation_data), key=lambda e: e.name)

    def get_effect_names(self) -> List[str]:
        return [e.name for e in self.get_effects()]

    def set_raw_effect_data(self, effect_data: dict):
        """Sends a raw dict containing effect data to the device.

        The dict given must match the json structure specified in the API docs."""
        data = {"write": effect_data}
        self.__command("put", "effects", data=data)

    def delete_effect(self, name: str):
        """Removed the specified effect from the device"""
        data = {"write": {"command": "delete",
                          "animName": name}}
        self.__command("put", "effects", data=data)
