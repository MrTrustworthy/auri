import datetime
import os
import signal
import subprocess
import time
from colorsys import rgb_to_hsv
from functools import lru_cache
from typing import List, Tuple, Any, Dict, Iterator
from warnings import warn

import click
import requests

from auri.device_manager import DeviceManager
from auri.aurora import Aurora, AuroraException

try:
    from PIL import ImageGrab
except ImportError as e:
    ImageGrab = None

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

PROPERTY_TEMPLATE: Template = {
    "delay": 1,  # As each pixel might have a slightly different color, quantization is used to reduce the colors
    "top": 10,  # How many of the top colors to use for the nanoleaf
    "quantization": 10,
    # How grey (according to HSV saturation) can something be before it's filtered out into a set of similar colors
    # Setting this lower means having more different colors show up in the result
    "greyness": 10  # how long to pause between re-applying the current desktop image
}


class AmbilightController:

    def __init__(self, aurora: Aurora, device_manager: DeviceManager, verbose: bool = False):
        """
        :param aurora: Instance of the Nanoleaf device to use
        :param verbose: logging detail
        """
        self._aurora = aurora
        self._quantization = PROPERTY_TEMPLATE["quantization"]
        self._top = PROPERTY_TEMPLATE["top"]
        self._greyness = PROPERTY_TEMPLATE["greyness"]
        self._delay = PROPERTY_TEMPLATE["delay"]
        self.verbose = verbose
        self.device_manager = device_manager

        if self._quantization < self._top:
            warn("Quantization is less than top, which doesn't make sense. "
                 f"Reducing top to match quantization ({self._quantization})")
            self._top = self._quantization

        if ImageGrab is None:
            raise AuroraException("Sorry, but Ambilight only works on Windows and MacOS currently :(")

    def start(self, blocking: bool):
        """Starts a new process that calls itself in blocking mode as a separate process"""
        if blocking:
            self._run_ambi_loop()
            click.echo("auri ambi started in blocking mode")

        # in case anyone tries to start it twice, run `stop()` before to be safe (which is idempotent)
        self.stop()

        # TODO: find an approach that also works if ambi isn't available via global `ambi`, such as `python -m ambi`
        # TODO: Whenever the name/call-path of this command changes, this also has to be adjusted :(
        process = subprocess.Popen(
            ['auri', 'ambi', 'start', "-b"],
            cwd="/",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        self.device_manager.save_pid(process.pid)
        click.echo("auri ambi started")

    def stop(self):
        """Stop a running ambi process. If none is found, will do nothing"""
        pid = self.device_manager.load_pid()
        if pid is None:
            click.echo("Could not find a running `ambi`")
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            click.echo(f"Could not find a process with PID {pid}, maybe it was already killed?")
        click.echo("auri ambi stopped")

    def _run_ambi_loop(self) -> None:
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
