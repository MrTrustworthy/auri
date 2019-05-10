import datetime
import time
from colorsys import rgb_to_hsv
from functools import lru_cache
from typing import List, Tuple, Any, Dict, Iterator
from warnings import warn

import click
import requests

try:
    from PIL import ImageGrab
except ImportError as e:
    ImageGrab = None

from auri.aurora import Aurora, AuroraException

Color = Tuple[int, int, int]
Template = Dict[str, Any]

EFFECT_TEMPLATE: Template = {
    "command": "add",
    "animName": "AuriAmbi",
    "animType": "random",
    "colorType": "HSB",
    "animData": None,
    "palette": [],  # This is overwritten by the calling function
    "brightnessRange": {
        "minValue": 50,
        "maxValue": 100,
    },
    "transTime": {
        "minValue": 20,
        "maxValue": 30
    },
    "delayTime": {
        "minValue": 25,
        "maxValue": 100
    },
    "loop": True
}


class AmbilightController:

    def __init__(self, aurora: Aurora, quantization: int, top: int, greyness: int, delay: int, verbose: bool = False):
        """

        :param aurora: Instance of the Nanoleaf device to use
        :param quantization: As each pixel might have a slightly different color, quantization is used to reduce the colors
            into a set of similar colors. Setting this lower means having more different colors show up in the result
        :param top: How many of the top colors to use for the nanoleaf
        :param greyness: How grey (according to HSV saturation) can something be before it's filtered out
        :param delay: how long to pause between re-applying the current desktop image
        :param verbose: logging detail
        """
        self._aurora = aurora
        self._quantization = quantization
        self._top = top
        self._greyness = greyness
        self._delay = delay
        self.verbose = verbose

        if self._quantization < self._top:
            warn("Quantization is less than top, which doesn't make sense. "
                 f"Reducing top to match quantization ({self._quantization})")
            self._top = self._quantization

        if ImageGrab is None:
            raise AuroraException("Sorry, but Ambilight only works on Windows and MacOS currently :(")

    def run_ambi_loop(self):
        """Runs a refresh in a continuous loop and will not return normally"""

        while True:
            start = time.time()
            try:
                self.set_effect_to_current_screen_colors()
            except requests.exceptions.RequestException as e:
                click.echo(f"[{datetime.datetime.now()}] Got an exception when trying to update the image: {str(e)}")
            if self.verbose > 0:
                click.echo(f"Updating effect took {time.time()-start} seconds")
            time.sleep(self._delay)

    def set_effect_to_current_screen_colors(self):
        """Returns a list of the top-N colors the main monitor currently shows in HSV-format"""
        colors = self._get_current_display_image_colors()

        # reduce amount of "grey" colors if possible
        colors_filtered = list(filter(lambda c: c[1] >= self._greyness, colors))
        if len(colors_filtered) == 0:
            click.echo(
                f"Could not find any colors to show that are above saturation {self._greyness}, trying without it")
            colors_filtered = colors

        effect_data = AmbilightController._render_effect_template(colors_filtered[:self._top])
        self._aurora.set_raw_effect_data(effect_data)

    def _get_current_display_image_colors(self) -> List[Color]:
        """ Returns a list of the top-N colors the main monitor currently shows in HSV-format

        :return: List of :top: colors after quantization, sorted by the frequency of their appearance
        """

        img = ImageGrab.grab()
        img = img.quantize(self._quantization)
        colors = sorted(img.convert("RGB").getcolors(), reverse=True)
        return [AmbilightController._rgb_to_hsv(color) for frequency, color in colors]

    @staticmethod
    def _render_effect_template(colors: Iterator[Color]) -> Template:
        """ Given a list of colors, renders the effects template that can be HTTP PUT to Nanoleaf

        :param: colors: List of all colors in HSV/HSB format that's used for rendering
        :return: Rendered template that is accepted by the Nanoleaf API
        """
        palette = [
            {
                "hue": c[0],
                "saturation": c[1],
                "brightness": c[2]
            }
            for c in colors
        ]
        rendered = {**EFFECT_TEMPLATE}  # Shallow copy just to be safe
        rendered["palette"] = palette
        return rendered

    @staticmethod
    @lru_cache(maxsize=256)
    def _rgb_to_hsv(rgb_color: Color) -> Color:
        """ Converts the RGB colors we get from ImageGrab into HSV for the NanoLeaf

        `colorsys.py` expects and provides values in range [0, 1], but we get and need them in a different range
        """

        r, g, b = map(lambda v: v / 255.0, rgb_color)
        h, s, v = rgb_to_hsv(r, g, b)
        h, s, v = int(h * 360), int(s * 100), int(v * 100)
        return h, s, v
