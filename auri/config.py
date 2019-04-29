import json
import os
from os.path import expanduser
from typing import Dict, Union, List

import jsonschema
from click import echo

from auri.aurora import Aurora, Effect
# Config always looks like this
# { "192.168.0.255": {
#     "name": "bananaleaf",
#     "token": "bananas",
#     "active": True,
#     "mac": "ab:cd"
#   }
# }
# But an empty dict {} is also valid for first setups
AuroraConf = Dict[str, Union[str, bool]]
AuroraConfigs = Dict[str, AuroraConf]
config_schema = {
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

CONF_PATH = expanduser("~/.config/auri/config.json")
IMAGE_PATH = expanduser("~/.config/auri")


# TODO handle duplicated names

class ConfigException(Exception):
    pass


# Loading and retrieving configurations for commands that affect multiple Auroras

def set_active(name: str, verbose: bool = False):
    configs = _load_config(verbose=verbose)
    for ip, data in configs.items():
        if data["name"] != name:
            continue
        data["active"] = True
        _save_config(configs, verbose=verbose)
        return
    raise ConfigException(f"No Aurora with name {name} was found, could not set it active. Reverting")


def get_configured_leafs() -> List[Aurora]:
    return [Aurora.deserialize(ip, data) for ip, data in _load_config().items()]


def aurora_name_if_already_configured(aurora: Aurora, verbose: bool = False) -> Union[str, None]:
    config = _load_config(verbose=verbose)
    if aurora.ip_address not in config.keys():
        return None
    return config[aurora.ip_address]["name"]


def add_aurora_to_config(aurora: Aurora, verbose: bool = False):
    config = _load_config()
    if verbose and aurora.ip_address in config.keys():
        echo(f"Aurora at {str(aurora)} is already configured, overwriting it with new configuration")
    config.update(aurora.serialize())
    _save_config(config)


# Loading and retrieving configurations for commands that affect 1 Aurora

def save_images(aurora: Aurora):
    for effect in aurora.get_effects():
        image = effect.to_image()
        image.save(image_path_for(aurora, effect))


def image_path_for(aurora: Aurora, effect: Effect) -> str:
    return os.path.join(IMAGE_PATH, f"img_{aurora.name}_{effect.name}.jpg")


def is_active(aurora: Aurora, verbose: bool = False) -> bool:
    """Whether the aurora passed as first parameter is the current active Aurora device"""
    for ip, data in _load_config(verbose=verbose).items():
        if ip == aurora.ip_address:
            return data["active"]
    raise ConfigException(f"{str(aurora)} not found in config!")


def get_leaf_by_name_or_active(name, verbose: bool = False) -> Aurora:
    """ To get the aurora to use for a certain command

    Raises a ConfigException when
    (1) Neither the config with a given name exists nor a active leaf is configured
    (2) The config is empty (a subset of (1))

    :param name: The name to use for searching, might be `None` if the active should just be used
    :param verbose: Lets you know in case the active is used
    :return: The Aurora to use for commands
    """
    try:
        return _get_leaf_by_name(name, verbose=verbose)
    except ConfigException:
        if verbose:
            echo(f"Found no Aurora with the name {name}, attempting to use active instead")
        return _get_active_leaf(verbose=verbose)


# Handle internal configuration loading, saving and validating


def _get_active_leaf(verbose: bool = False) -> Aurora:
    for ip, data in _load_config(verbose=verbose).items():
        if not data["active"]:
            continue
        return Aurora.deserialize(ip, data)

    raise ConfigException("No active Aurora found")


def _get_leaf_by_name(name, verbose: bool = False) -> Aurora:
    for ip, data in _load_config(verbose=verbose).items():
        if not data["name"] == name:
            continue
        return Aurora.deserialize(ip, data)

    raise ConfigException(f"No Aurora with name '{name}' found")


def _load_config(verbose: bool = False):
    if not os.path.exists(CONF_PATH):
        return {}

    with open(CONF_PATH) as infile:
        config = json.load(infile)
    _ensure_valid_config(config, verbose=verbose)
    return config


def _save_config(config: AuroraConfigs, verbose: bool = False):
    _ensure_valid_config(config, verbose=verbose)
    os.makedirs(os.path.dirname(CONF_PATH), exist_ok=True)  # On first run, make sure the path exists
    with open(CONF_PATH, "w+") as outfile:
        return json.dump(config, outfile, sort_keys=True, indent=4)


def _ensure_valid_config(config, verbose: bool = False):
    jsonschema.validate(config, config_schema)
    _ensure_valid_actives(config, verbose=verbose)


def _ensure_valid_actives(config, verbose: bool = False):
    active_auroras = len(list(filter(lambda a: a["active"], config.values())))
    if active_auroras == 1:
        _verbose_echo(verbose, f"There is exactly one active Aurora, which is expected. Continuing.")
        return

    if len(config.keys()) == 0:
        _verbose_echo(verbose, f"Config is empty, so there is no active Aurora. Continuing.")
        return

    echo(f"There are {active_auroras} active Auroras, "
         "repairing config automatically now to ensure exactly 1 Aurora is active")

    _clear_all_actives(config)

    for ip, data in config.items():
        data["active"] = True
        return


def _clear_all_actives(config: AuroraConfigs):
    for ip, data in config.items():
        data["active"] = False


def _verbose_echo(verbose, text):
    if verbose:
        echo(text)
