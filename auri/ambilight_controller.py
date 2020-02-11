import json
import os
import subprocess
from os.path import expanduser
from pathlib import Path
from typing import List

import click
import psutil

from auri.ambilight import AnyDict, Ambilight
from auri.aurora import Aurora

AMBILIGHT_EFFECT_NAME = "AuriAmbi"

SETTING_TEMPLATE: AnyDict = {
    "config": {
        "delay": 1,  # how long to pause between re-applying the current desktop image
        "top": 10,  # How many of the top colors to use for the nanoleaf
        "quantization": 10,
        # As each pixel might have a slightly different color, quantization is used to reduce colors
        # How grey (according to HSV saturation) can something be before it's filtered out into a set of similar colors
        # Setting this lower means having more different colors show up in the result
        "greyness": 10
    },
    "effect_template": {
        "command": "add",
        "animName": AMBILIGHT_EFFECT_NAME,
        "animType": "random",
        "colorType": "HSB",
        "animData": None,
        "palette": [],  # This is where the magic happens, Ambilight fills in the screen colors here
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
}
ENV_PID_PATH = "AURI_PID_PATH"
DEFAULT_PID_PATH = "~/.config/auri/ambi.pid"
ENV_SETTINGS_PATH = "AURI_SETTINGS_PATH"
DEFAULT_SETTINGS_PATH = "~/.config/auri/ambi.json"

# Whenever the name/call-path of this command changes, this also has to be adjusted :(
AMBI_CALL_ARGS = "auri ambi -b"


class AmbilightController:

    def __init__(self, aurora: Aurora, verbose: bool = False):
        self.pid_path = expanduser(os.getenv(ENV_PID_PATH, DEFAULT_PID_PATH))
        self.settings_path = expanduser(os.getenv(ENV_SETTINGS_PATH, DEFAULT_SETTINGS_PATH))
        self.verbose = verbose
        self.settings = self._load_settings()
        self.ambilight = Ambilight(aurora, self.settings["config"], self.settings["effect_template"], verbose=verbose)

    @property
    def is_running(self) -> bool:
        return len(self.find_auri_processes()) > 0

    def start(self, blocking: bool):
        """Starts a new process that calls itself in blocking mode as a separate process"""
        if blocking:
            self.ambilight.run_ambi_loop()
            click.echo("auri ambi started in blocking mode")
            return

        # in case anyone tries to start it twice, run `stop()` before to be safe (which is idempotent)
        self.stop()

        subprocess.Popen(
            AMBI_CALL_ARGS.split(),
            cwd="/",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )

    def stop(self):
        """Stop a running ambi process. If none is found, will do nothing. This is safe to call at any time"""
        auri_procs = AmbilightController.find_auri_processes()
        if self.verbose:
            click.echo(f"Found {len(auri_procs)} processes, PIDS: {[p.pid for p in auri_procs]}")
        for proc in auri_procs:
            if self.verbose:
                click.echo(f"Killing process with PID {proc.pid}")
            proc.kill()

    @staticmethod
    def find_auri_processes() -> List[psutil.Process]:
        procs = psutil.process_iter(attrs=['pid', 'name', 'cmdline'])
        ambis = list(filter(lambda p: p.name() == "Python" and AMBI_CALL_ARGS in " ".join(p.cmdline()), procs))
        return ambis

    # config management

    def _load_settings(self) -> AnyDict:
        self._initialize_settings()
        with open(self.settings_path) as infile:
            config = json.load(infile)
        return config

    def _save_settings(self, settings: AnyDict):
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)  # On first run, make sure the path exists
        with open(self.settings_path, "w+") as outfile:
            return json.dump(settings, outfile, sort_keys=True, indent=4)

    def _initialize_settings(self):
        """Idempotent way to ensure a settings file exists and has at least the template settings"""
        if not Path(self.settings_path).is_file():
            click.echo(f"Couldn't find existing Ambilight settings, creating template at {self.settings_path}")
            self._save_settings(SETTING_TEMPLATE)
