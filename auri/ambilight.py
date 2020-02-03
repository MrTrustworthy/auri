import datetime
import time
from colorsys import rgb_to_hsv
from functools import lru_cache
from typing import List, Tuple, Any, Dict, Iterator
from warnings import warn

import click
import requests

from auri.aurora import Aurora, AuroraException

try:
    from PIL import ImageGrab
except ImportError as e:
    ImageGrab = None

Color = Tuple[int, int, int]
AnyDict = Dict[str, Any]


class Ambilight:

    def __init__(self, aurora: Aurora, config: AnyDict, effects_template: AnyDict, verbose: bool = False):
        """
        :param aurora: Instance of the Nanoleaf device to use
        :param config: The main configuration options for the ambilight
        :param effects_template: The template for the effect to use
        :param verbose: logging detail
        """
        self._aurora = aurora
        self._quantization = config["quantization"]
        self._top = config["top"]
        self._greyness = config["greyness"]
        self._delay = config["delay"]
        self.effects_template = effects_template
        self.verbose = verbose

        if self._quantization < self._top:
            warn("Quantization is less than top, which doesn't make sense. "
                 f"Reducing top to match quantization ({self._quantization})")
            self._top = self._quantization

        if ImageGrab is None:
            raise AuroraException("Sorry, but Ambilight only works on Windows and MacOS currently :(")

    def run_ambi_loop(self) -> None:
        """Runs a refresh in a continuous loop and will not return normally"""
        while True:
            start = time.time()
            try:
                self.set_effect_to_current_screen_colors()
            except (requests.exceptions.RequestException, AuroraException) as e:
                click.echo(f"[{datetime.datetime.now()}] Got an exception when trying to update the image: {str(e)}")
            if self.verbose > 0:
                click.echo(f"Updating effect took {time.time() - start} seconds")
            time.sleep(self._delay)

    def set_effect_to_current_screen_colors(self) -> None:
        """Returns a list of the top-N colors the main monitor currently shows in HSV-format"""
        colors = self._get_current_display_image_colors()

        # reduce amount of "grey" colors if possible
        colors_filtered = list(filter(lambda c: c[1] >= self._greyness, colors))
        if len(colors_filtered) == 0:
            click.echo(f"Could not find any colors that are above saturation {self._greyness}, using unfiltered colors")
            colors_filtered = colors

        effect_data = self._render_effect_template(colors_filtered[:self._top])
        self._aurora.set_raw_effect_data(effect_data)

    def _get_current_display_image_colors(self) -> List[Color]:
        """ Returns a list of the top-N colors the main monitor currently shows in HSV-format

        :return: List of :top: colors after quantization, sorted by the frequency of their appearance
        """

        img = ImageGrab.grab()
        img = img.quantize(self._quantization)
        colors = sorted(img.convert("RGB").getcolors(), reverse=True)
        return [Ambilight._rgb_to_hsv(color) for frequency, color in colors]

    def _render_effect_template(self, colors: Iterator[Color]) -> AnyDict:
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
        rendered = {**self.effects_template}  # Shallow copy just to be safe
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
