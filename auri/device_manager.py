import json
import os
from os.path import expanduser
from typing import Dict, Union, List, Tuple

import jsonschema
import click
from auri.aurora import Aurora
from auri.effects import Effect

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


class DeviceManager:
    """The device manager is a wrapper around multiple aurora devices which performs SerDe in the background"""

    def __init__(self, verbose: bool = False):
        self.conf_path = expanduser(os.getenv(ENV_CONF_PATH, DEFAULT_CONF_PATH))
        self.image_path = expanduser(os.getenv(ENV_IMAGE_PATH, DEFAULT_IMAGE_PATH))
        self.image_file_ending = os.getenv(ENV_IMAGE_FILETYPE, DEFAULT_IMAGE_FILETYPE)
        self.verbose = verbose

    # Loading and retrieving configurations for commands that affect multiple Auroras

    def set_active(self, name: str):
        """Switch the currently active device to the one with a given name"""
        configs = self._load_configs()
        self._clear_all_actives(configs)
        for ip, data in configs.items():
            if data["name"] != name:
                continue
            data["active"] = True
            self._save_config(configs)
            return
        raise DeviceNotExistsException(f"No Aurora with name {name} was found, could not set it active")

    def is_active(self, aurora: Aurora) -> bool:
        """Whether the aurora passed as first parameter is the current active Aurora device"""
        configs = self._load_configs()
        for ip, data in configs.items():
            if ip == aurora.ip_address:
                return data["active"]
        raise DeviceNotExistsException(f"{str(aurora)} not found in config")

    def get_by_name_or_active(self, name: str) -> Aurora:
        """ To get the device to use for a certain command. This is the most-used function of the DeviceManager

        Raises a DeviceNotExistsException when
        (1) Neither the config with a given name exists nor a active leaf is configured
        (2) The config is empty (a subset of (1))

        :param name: The name to use for searching, might be `None` if the active should just be used
        :return: The Aurora to use for commands
        """
        if name is None:
            return self.get_active()
        return self.get_by_name(name)

    def get_by_name(self, name: str) -> Aurora:
        configs = self._load_configs()
        for ip, data in configs.items():
            if not data["name"] == name:
                continue
            return Aurora.deserialize(ip, data)

        raise DeviceNotExistsException(f"No Aurora with name '{name}' found")

    def get_active(self) -> Aurora:
        configs = self._load_configs()
        for ip, data in configs.items():
            if not data["active"]:
                continue
            return Aurora.deserialize(ip, data)

        raise DeviceNotExistsException("No active Aurora found")

    def get_by_ip(self, ip: str) -> Aurora:
        configs = self._load_configs()
        data = configs.get(ip)
        if data is None:
            raise DeviceNotExistsException(f"No Aurora with ip '{ip}' found")
        return Aurora.deserialize(ip, data)

    def get_name_by_ip(self, ip: str) -> Union[str, None]:
        try:
            return self.get_by_ip(ip).name
        except DeviceNotExistsException:
            return None

    def get_all(self) -> List[Aurora]:
        configs = self._load_configs()
        return [Aurora.deserialize(ip, data) for ip, data in configs.items()]

    def save_aurora(self, aurora: Aurora):
        configs = self._load_configs()
        if self.verbose and aurora.ip_address in configs.keys():
            click.echo(f"Aurora at {str(aurora)} is already configured, overwriting it with new configuration")
        configs.update(aurora.serialize())
        self._save_config(configs)

    def generate_image_cache(self):
        """For each effect in each aurora, generate a preview image and save it for other apps (like alfred) to use"""

        self._clean_image_cache()
        for aurora in self.get_all():
            for effect in aurora.get_effects():
                image = effect.to_image()
                image.save(self.image_path_for(aurora, effect))

    def image_path_for(self, aurora: Aurora, effect: Effect) -> str:
        return os.path.join(self.image_path, f"img_{aurora.name}_{effect.name}{self.image_file_ending}")

    # Handle internal configuration serialization/deserialization, validating and other file management

    def _clean_image_cache(self):
        """Remove all images created by `save_images()` to clean up the folder of old images"""
        image_folder = os.listdir(self.image_path)
        if self.verbose:
            click.echo(f"Removing all files with ending {self.image_file_ending} from {self.image_path}")
        for item in image_folder:
            if item.endswith(self.image_file_ending):
                os.remove(os.path.join(self.image_path, item))

    def _load_configs(self) -> AuroraConfigs:
        if not os.path.exists(self.conf_path):
            return {}

        with open(self.conf_path) as infile:
            config = json.load(infile)
        self._ensure_valid_configs(config)
        return config

    def _save_config(self, configs: AuroraConfigs):
        self._ensure_valid_configs(configs)
        os.makedirs(os.path.dirname(self.conf_path), exist_ok=True)  # On first run, make sure the path exists
        with open(self.conf_path, "w+") as outfile:
            return json.dump(configs, outfile, sort_keys=True, indent=4)

    def _ensure_valid_configs(self, configs: AuroraConfigs):
        jsonschema.validate(configs, configs_schema)
        self._ensure_valid_actives(configs)
        self._ensure_unique_names(configs)

    def _ensure_valid_actives(self, configs: AuroraConfigs):
        """Make sure there is exactly one active device before serializing"""
        active_auroras = len(list(filter(lambda a: a["active"], configs.values())))
        if active_auroras == 1:
            if self.verbose:
                click.echo(f"There is exactly one active Aurora, which is expected. Continuing.")
            return

        if len(configs.keys()) == 0:
            if self.verbose:
                click.echo(f"Config is empty, so there is no active Aurora. Continuing.")
            return

        click.echo(f"There are {active_auroras} active Auroras, "
                   "reconciling automatically to ensure exactly 1 Aurora is active")

        self._clear_all_actives(configs)

        for ip, data in configs.items():
            data["active"] = True
            return

    def _ensure_unique_names(self, configs: AuroraConfigs):
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
            if self.verbose:
                click.echo(f"Device with name '{name}' already exists, renaming it")
            data["name"] = name + " [duplicate]"
            _unique_name(data)

        for ip, data in configs.items():
            _unique_name(data)

    @staticmethod
    def _clear_all_actives(configs: AuroraConfigs):
        for ip, data in configs.items():
            data["active"] = False
