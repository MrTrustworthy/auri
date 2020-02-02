from colorsys import hsv_to_rgb
from typing import Dict, Any

from PIL import Image, ImageDraw

IMAGE_SIZE = 64
FLAG_TILES = 10  # How many "characters" of color to show in terminal, will wrap around if less colors exist


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
        return flag

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
