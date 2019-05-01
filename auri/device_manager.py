import json
import os
from functools import wraps
from os.path import expanduser
from typing import Dict, Union, List

import jsonschema
import click
from auri.aurora import Aurora, Effect

# A serialized configuration looks like this
# { "192.168.0.255": {
#     "name": "bananaleaf",
#     "token": "bananas",
#     "active": True,
#     "mac": "ab:cd"
#   }
# }
# But an empty dict {} is also valid
AuroraConf = Dict[str, Union[str, bool]]
AuroraConfigs = Dict[str, AuroraConf]
configs_schema = {
    "type": "object",
    "patternProperties": {
        "^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "token": {"type": "string"},
                "active": {"type": "boolean"},
                "mac": {"type": "string"}
            }
        }
    }
}

# Environment variable names and defaults
ENV_CONF_PATH = "AURI_CONFIG_PATH"
DEFAULT_CONF_PATH = "~/.config/auri/config.json"
ENV_IMAGE_PATH = "AURI_IMAGE_PATH"
DEFAULT_IMAGE_PATH = "~/.config/auri"
ENV_IMAGE_FILETYPE = "AURI_IMAGE_FILETYPE"
DEFAULT_IMAGE_FILETYPE = ".jpg"


class DeviceNotExistsException(Exception):
    pass


def inject_config(func):
    """Wrapper to inject a newly loaded config into the wrapped function"""

    # TODO wrapper should only pass `verbose` if the wrapped function expects it
    @wraps(func)
    def inject_config_wraps(self, *args, **kwargs):
        verbose = kwargs.get("verbose", False)
        configs = self._load_configs(verbose=verbose)
        return func(self, configs, *args, **kwargs)

    return inject_config_wraps


class DeviceManager:
    """The device manager is a wrapper around multiple aurora devices which performs SerDe in the background"""

    def __init__(self):
        self.conf_path = expanduser(os.getenv(ENV_CONF_PATH, DEFAULT_CONF_PATH))
        self.image_path = expanduser(os.getenv(ENV_IMAGE_PATH, DEFAULT_IMAGE_PATH))
        self.image_file_ending = os.getenv(ENV_IMAGE_FILETYPE, DEFAULT_IMAGE_FILETYPE)

    # Loading and retrieving configurations for commands that affect multiple Auroras

    @inject_config
    def set_active(self, configs: AuroraConfigs, name: str, verbose: bool = False):
        """Switch the currently active device to the one with a given name"""
        self._clear_all_actives(configs)
        for ip, data in configs.items():
            if data["name"] != name:
                continue
            data["active"] = True
            self._save_config(configs, verbose=verbose)
            return
        raise DeviceNotExistsException(f"No Aurora with name {name} was found, could not set it active")

    @inject_config
    def is_active(self, configs: AuroraConfigs, aurora: Aurora, verbose: bool = False) -> bool:
        """Whether the aurora passed as first parameter is the current active Aurora device"""
        for ip, data in configs.items():
            if ip == aurora.ip_address:
                return data["active"]
        raise DeviceNotExistsException(f"{str(aurora)} not found in config")

    def get_by_name_or_active(self, name: str, verbose: bool = False) -> Aurora:
        """ To get the device to use for a certain command. This is the most-used function of the DeviceManager

        Raises a DeviceNotExistsException when
        (1) Neither the config with a given name exists nor a active leaf is configured
        (2) The config is empty (a subset of (1))

        :param name: The name to use for searching, might be `None` if the active should just be used
        :param verbose: Lets you know in case the active is used
        :return: The Aurora to use for commands
        """
        try:
            return self.get_by_name(name, verbose=verbose)
        except DeviceNotExistsException:
            if verbose:
                click.echo(f"Found no Aurora with the name {name}, attempting to use active instead")
            return self.get_active(verbose=verbose)

    @inject_config
    def get_by_name(self, configs: AuroraConfigs, name: str, verbose: bool = False) -> Aurora:
        for ip, data in configs.items():
            if not data["name"] == name:
                continue
            return Aurora.deserialize(ip, data)

        raise DeviceNotExistsException(f"No Aurora with name '{name}' found")

    @inject_config
    def get_active(self, configs: AuroraConfigs, verbose: bool = False) -> Aurora:
        for ip, data in configs.items():
            if not data["active"]:
                continue
            return Aurora.deserialize(ip, data)

        raise DeviceNotExistsException("No active Aurora found")

    @inject_config
    def get_by_ip(self, configs: AuroraConfigs, ip: str, verbose: bool = False) -> Aurora:
        data = configs.get(ip)
        if data is None:
            raise DeviceNotExistsException(f"No Aurora with ip '{ip}' found")
        return Aurora.deserialize(ip, data)

    def get_name_by_ip(self, ip: str, verbose: bool = False) -> Union[str, None]:
        try:
            return self.get_by_ip(ip, verbose=verbose).name
        except DeviceNotExistsException:
            return None

    @inject_config
    def get_all(self, configs: AuroraConfigs, verbose: bool = False) -> List[Aurora]:
        return [Aurora.deserialize(ip, data) for ip, data in configs.items()]

    @inject_config
    def save_aurora(self, configs: AuroraConfigs, aurora: Aurora, verbose: bool = False):
        if verbose and aurora.ip_address in configs.keys():
            click.echo(f"Aurora at {str(aurora)} is already configured, overwriting it with new configuration")
        configs.update(aurora.serialize())
        self._save_config(configs)

    def generate_images(self, verbose: bool = False):
        """For each effect in each aurora, generate a preview image and save it for other apps (like alfred) to use"""

        self._clean_images(verbose=verbose)
        for aurora in self.get_all(verbose=verbose):
            for effect in aurora.get_effects():
                image = effect.to_image()
                image.save(self.image_path_for(aurora, effect))

    def image_path_for(self, aurora: Aurora, effect: Effect) -> str:
        return os.path.join(self.image_path, f"img_{aurora.name}_{effect.name}{self.image_file_ending}")

    # Handle internal configuration serialization/deserialization, validating and other file management

    def _clean_images(self, verbose: bool = False):
        """Remove all images created by `save_images()` to clean up the folder of old images"""
        image_folder = os.listdir(self.image_path)
        if verbose:
            click.echo(f"Removing all files with ending {self.image_file_ending} from {self.image_path}")
        for item in image_folder:
            if item.endswith(self.image_file_ending):
                os.remove(os.path.join(self.image_path, item))

    def _load_configs(self, verbose: bool = False) -> AuroraConfigs:
        if not os.path.exists(self.conf_path):
            return {}

        with open(self.conf_path) as infile:
            config = json.load(infile)
        DeviceManager._ensure_valid_configs(config, verbose=verbose)
        return config

    def _save_config(self, configs: AuroraConfigs, verbose: bool = False):
        DeviceManager._ensure_valid_configs(configs, verbose=verbose)
        os.makedirs(os.path.dirname(self.conf_path), exist_ok=True)  # On first run, make sure the path exists
        with open(self.conf_path, "w+") as outfile:
            return json.dump(configs, outfile, sort_keys=True, indent=4)

    @staticmethod
    def _ensure_valid_configs(configs: AuroraConfigs, verbose: bool = False):
        jsonschema.validate(configs, configs_schema)
        DeviceManager._ensure_valid_actives(configs, verbose=verbose)
        DeviceManager._ensure_unique_names(configs, verbose=verbose)

    @staticmethod
    def _ensure_valid_actives(configs: AuroraConfigs, verbose: bool = False):
        """Make sure there is exactly one active device before serializing"""
        active_auroras = len(list(filter(lambda a: a["active"], configs.values())))
        if active_auroras == 1:
            if verbose:
                click.echo(verbose, f"There is exactly one active Aurora, which is expected. Continuing.")
            return

        if len(configs.keys()) == 0:
            if verbose:
                click.echo(verbose, f"Config is empty, so there is no active Aurora. Continuing.")
            return

        click.echo(f"There are {active_auroras} active Auroras, "
                   "repairing configs automatically now to ensure exactly 1 Aurora is active")

        DeviceManager._clear_all_actives(configs)

        for ip, data in configs.items():
            data["active"] = True
            return

    @staticmethod
    def _ensure_unique_names(configs: AuroraConfigs, verbose: bool = False):
        """Avoid duplicate names otherwise a lot of name-based commands will behave randomly

        Will rename duplicate names with 'myname [duplicate]'
        """
        names = []

        def _unique_name(data):
            name = data["name"]
            # First occurrence of the name, that's fine
            if name not in names:
                names.append(name)
                return

            # if not, add a suffix and recurse in order to catch multiple duplicates until it ends in the first block
            if verbose:
                click.echo(f"Device with name '{name}' already exists, renaming it")
            data["name"] = name + " [duplicate]"
            _unique_name(data)

        for ip, data in configs.items():
            _unique_name(data)

    @staticmethod
    def _clear_all_actives(configs: AuroraConfigs):
        for ip, data in configs.items():
            data["active"] = False
