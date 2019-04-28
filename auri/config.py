import json
import os
from os.path import expanduser
from typing import Dict, Union, Tuple, List

import jsonschema
from click._unicodefun import click

from auri.aurora import Aurora

# Config always looks like this
# { "192.168.0.255": {
#     "name": "bananaleaf",
#     "token": "bananas",
#     "default": True
#   }
# }
# But an empty dict {} is also valid for first setups
AuroraConf = Dict[str, Union[str, bool]]
LeafConfig = Dict[str, AuroraConf]
config_schema = {
    "type": "object",
    "patternProperties": {
        "^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "token": {"type": "string"},
                "default": {"type": "boolean"},
                "mac": {"type": "string"}
            }
        }
    }
}

CONF_PATH = expanduser("~/.config/auri/config.json")


# TODO handle duplicated names

class ConfigException(Exception):
    pass


def _verbose_echo(verbose, text):
    if verbose:
        click.echo(text)


# Handle configuration loading, saving and validating

def _load_config(verbose: bool = False):
    if not os.path.exists(CONF_PATH):
        return {}

    with open(CONF_PATH) as infile:
        config = json.load(infile)
    _ensure_valid_config(config, verbose=verbose)
    return config


def _save_config(config: LeafConfig, verbose: bool = False):
    _ensure_valid_config(config, verbose=verbose)
    os.makedirs(os.path.dirname(CONF_PATH), exist_ok=True)  # On first run, make sure the path exists
    with open(CONF_PATH, "w+") as outfile:
        return json.dump(config, outfile, sort_keys=True, indent=4)


def _ensure_valid_config(config, verbose: bool = False):
    jsonschema.validate(config, config_schema)
    _ensure_valid_defaults(config, verbose=verbose)


def _ensure_valid_defaults(config, verbose: bool = False):
    default_auroras = len(list(filter(lambda a: a["default"], config.values())))
    if default_auroras == 1:
        _verbose_echo(verbose, f"There is exactly one default Aurora, which is expected. Continuing.")
        return

    if len(config.keys()) == 0:
        _verbose_echo(verbose, f"Config is empty, so there is no default Aurora. Continuing.")
        return

    click.echo(f"There are {default_auroras} default Auroras, "
               "repairing config automatically now to ensure exactly 1 Aurora is default")

    for ip, data in config.items():
        data["default"] = False

    for ip, data in config.items():
        data["default"] = True
        return


# Loading and retrieving configurations for commands that affect multiple Auroras


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
        click.echo(f"Aurora at {str(aurora)} is already configured, overwriting it with new configuration")
    config.update(aurora.serialize())
    _save_config(config)


# Loading and retrieving configurations for commands that affect 1 Aurora

def is_default(aurora: Aurora, verbose: bool = False) -> bool:
    for ip, data in _load_config(verbose=verbose).items():
        if ip == aurora.ip_address:
            return data["default"]
    raise ConfigException(f"{str(aurora)} not found in config!")


def get_leaf_by_name_or_default(name, verbose: bool = False) -> Aurora:
    """ To get the aurora to use for a certain command

    Raises a ConfigException when
    (1) Neither the config with a given name exists nor a default leaf is configured
    (2) The config is empty (a subset of (1))

    :param name: The name to use for searching, might be `None` if the default should just be used
    :param verbose: Lets you know in case the default is used
    :return: The Aurora to use for commands
    """
    try:
        return _get_leaf_by_name(name, verbose=verbose)
    except ConfigException:
        if verbose:
            click.echo(f"Found no Aurora with the name {name}, attempting to use default instead")
        return _get_default_leaf(verbose=verbose)


def _get_default_leaf(verbose: bool = False) -> Aurora:
    for ip, data in _load_config(verbose=verbose).items():
        if not data["default"]:
            continue
        return Aurora.deserialize(ip, data)

    raise ConfigException("No default Aurora found")


def _get_leaf_by_name(name, verbose: bool = False) -> Aurora:
    for ip, data in _load_config(verbose=verbose).items():
        if not data["name"] == name:
            continue
        return Aurora.deserialize(ip, data)

    raise ConfigException(f"No Aurora with name '{name}' found")
