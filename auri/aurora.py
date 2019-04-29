from colorsys import hsv_to_rgb
from typing import Union, Any, Dict, List

import requests
from PIL import Image, ImageDraw
from requests import HTTPError

IMAGE_SIZE = 64
FLAG_TILES = 10  # How many "characters" of color to show in terminal, will wrap around if less colors exist


class AuroraException(Exception):
    pass


class EffectColor:
    """Wrapper for a color in a Aurora Effect, has utility functions to print the effect nicely"""

    def __init__(self, data: Dict[str, int]):
        """Initializes Effect color based on the data from the Aurora REST API

        :param data: result of response.animations[x].palette[x] for a response of
            the "requestAll" command to the Aurora API at /effects
        """
        self._hue = data["hue"]
        self._saturation = data["saturation"]
        self._brightness = data["brightness"]
        self._termcode_text = " "

    @property
    def rgb(self):
        """Returns the RGB value of that color"""
        h, s, v = self._hue / 360, self._saturation / 100, self._brightness / 100
        rgb = hsv_to_rgb(h, s, v)
        return rgb

    @property
    def _termcode_number(self):
        """The terminal code number for this color, which represents the color as ANSI terminal color"""
        # rgb must be [0-5], this scaling formula looks the most accurate (most "colorful")
        r, g, b = list(map(lambda x: min(5, int(x * 6)), self.rgb))
        number = 16 + 36 * r + 6 * g + b  # https://stackoverflow.com/a/27165165/2683726
        return number

    @property
    def termcode(self):
        """String of <self._termcode_text> (default: a space character), with the background color of this color"""
        return f'\033[48;5;{self._termcode_number}m{self._termcode_text}\033[0m'


class Effect:
    """Wrapper for a Effect/Animation from the Nanoleaf Aurora"""

    def __init__(self, effect_data: Dict[str, Any], image_size: int = IMAGE_SIZE, flag_size: int = FLAG_TILES):
        """Initializes "Effect" object based on the response from the Aurora REST API

        :param effect_data: Expects the content of "animations" from the JSON response
            of the "requestAll" command to the Aurora API at /effects
        :param image_size: how big the images to create should be, defaults to 64x64
        :param flag_size: how many characters the terminal flag should have, defaults to 10
        """
        self.name = effect_data["animName"]
        self._image_size = image_size
        self._flag_size = flag_size
        self._colors = [EffectColor(data) for data in effect_data["palette"]]

    def color_flag_terminal(self) -> str:
        """Returns a "flag" of all colors in this effect as a string with terminal colors for printing

        The flag is stretched (via cycling colors) to <self._flag_size> in order to have a uniform length for all flags.

        :return: String of the respective flag that, when printed to terminal,
            will produce single-character blocks of color
        """
        color_cycle = [c.termcode for c in self._colors] * FLAG_TILES
        flag = ''.join(color_cycle[:self._flag_size])
        return f"{flag} {self.name} "

    def to_image(self) -> Image:
        """Returns a (self._image_size x self._image_size) large image of the colors in this effect, left to right

        :return: Image
        """
        image = Image.new("RGB", (self._image_size, self._image_size))
        draw = ImageDraw.Draw(image)
        spacing = int(self._image_size / len(self._colors))
        for i, color in enumerate(self._colors):
            rect = [i * spacing, 0, (i + 1) * spacing, self._image_size]
            draw_color = tuple(map(lambda c: int(c * 255), color.rgb))
            draw.rectangle(rect, fill=draw_color)
        return image


class Aurora:
    """Wrapper for a single Nanoleaf Aurora device"""

    def __init__(self, ip_address: str, name: str, mac: str, auth_token: Union[str, None]):
        """Creates an instance of the device so the REST API is wrapped in function calls


        :param ip_address: address of the Aurora in the local network
        :param name: given as an identifier in case multiple Auroras exist
        :param mac: not actually needed for any functionality, but helps to differentiate
        :param auth_token: token to use in the rest API, if not already known can be discovered via <generate_token()>
        """
        self._ip_address = ip_address
        self._auth_token = auth_token
        self._name = name
        self._device_url = f"http://{self._ip_address}:16021/api/v1"
        self._authenticated_url = f"{self._device_url}/{self._auth_token}"
        self.mac = mac

    def __str__(self):
        token = "loaded" if self._auth_token is not None else "not loaded"
        return f"<Aurora '{self.name}' (IP: {self._ip_address}, MAC: {self.mac}, Token: {token})>"

    def __repr__(self):
        return str(self)

    # Heavy lifting (AKA actually interacting with the Aurora) is done by those two functions

    def __command(
            self,
            method: str,
            endpoint: str,
            *,
            authenticated: bool = True,
            data: Dict[str, Any] = None
    ) -> Union[Dict[str, Any], None, str, int, bool]:
        """Wrapper for all REST API calls and is invoked by other functions to fetch data from the Aurora device

        May raise an `AuroraException` in case something goes wrong.

        :param method: HTTP Method to use for this call, the correct one is defined in the REST API documentation
        :param endpoint: URL path to use, the correct one is defined in the REST API documentation
        :param authenticated: whether to use the authenticated URL (with token) or not, depending on the endpoint
        :param data: in case data needs to be passed (typically only via PUT)
        :return: The response or, if no response data would make sense, None
        """

        # Check for auth precondition
        if authenticated and not self._auth_token:
            raise AuroraException("Aurora has no active token, can't run any functions that require auth")

        url = f"{self._authenticated_url if authenticated else self._device_url}/{endpoint}"
        kwargs = {} if data is None else {"json": data}
        response = requests.request(method, url, **kwargs)

        self._convert_response_exceptions(response)

        return None if response.text == "" else response.json()

    def _convert_response_exceptions(self, response: requests.Response):
        """Converts errors during the request into `AuroraException`s if needed"""
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
        """Will generate an access token for this device and save it into `self._auth_token

        Requires the power button of the device to be pressed for ~5s until the power LED blinks
        """
        response_data = self.__command("post", "new", authenticated=False)
        self._auth_token = response_data.get('auth_token')
        assert self._auth_token is not None, "Auth token is still None after generating it, this shouldn't happen"

    def serialize(self) -> Dict[str, Dict[str, Union[str, bool]]]:
        """Serialize this object so it can be restored later

        :return:
        """
        return {
            self._ip_address: {
                "name": self.name,
                "token": self._auth_token,
                "mac": self.mac,
                "active": False  # This is just used as a placeholder
            }
        }

    @classmethod
    def deserialize(cls, ip: str, data: Dict[str, str]):
        """Re-instantiate a device based on the output from `self.serialize()`"""
        return cls(ip, data["name"], data["mac"], data["token"])

    # Properties

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def ip_address(self) -> str:
        return self._ip_address

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
    def brightness(self, level: int):
        """Sets the brightness to the given level (0-100)"""
        data = {"brightness": {"value": level}}
        self.__command("put", "state", data=data)

    # Effect and manipulation methods

    def identify(self):
        """Briefly flash the panels on and off"""
        self.__command("put", "identify", data={})

    def get_active_effect_name(self):
        """Returns the active effect name"""
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
