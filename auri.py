import json
import time
from difflib import get_close_matches
from warnings import warn

import click

from auri.ambilight import set_effect_to_current_screen_colors
from auri.aurora import Aurora, AuroraException
from auri.aurora_finder import find_aurora_addresses
from auri.config import get_leaf_by_name_or_default, aurora_name_if_already_configured, get_configured_leafs, \
    add_aurora_to_config, CONF_PATH, is_default, set_active, save_images, IMAGE_PATH, image_path_for


# TODO create wrapper or validator that checks we have a valid default/named aurora and redirects to setup if needed
# TODO catch config and aurora exceptions and print them nicely

@click.group()
@click.version_option("1.0.0")
def cli():
    pass


# AURORA AND CONTEXT MANAGEMENT


@cli.group()
def aurora():
    pass


@aurora.command()
@click.argument("name")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def activate(name: str, verbose: bool):
    set_active(name, verbose=verbose)
    click.echo(f"Set {name} as active Aurora")


@aurora.command(name="list")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def list_command(verbose: bool):
    for aurora in get_configured_leafs():
        default = " [X]" if is_default(aurora, verbose=verbose) else "[ ]"
        click.echo(f"{default} {str(aurora)}")


@aurora.command()
@click.argument("option", default="info")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def query(option: str, aurora: str, verbose: bool):
    aurora = get_leaf_by_name_or_default(aurora, verbose=verbose)
    try:
        result = getattr(aurora, option)
        click.echo(str(result))
    except AttributeError:
        click.echo(f"Operator '{option}' doesn't exist")


@aurora.command()
@click.option("-a", "--amount", default=1, show_default=True,
              help="How many Auroras to search for. Set this to the number of Auroras that are in your WLAN")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def setup(amount: int, verbose: bool):
    click.echo(f"Searching for a total of {amount} Nanoleaf Auroras, press <CTRL+C> to cancel")

    for aurora_ip, aurora_mac in find_aurora_addresses(amount):

        click.echo(f"Found one Aurora at {aurora_ip}")
        aurora = Aurora(aurora_ip, "UNKNOWN", aurora_mac, None)  # Token and name will be set later

        name = aurora_name_if_already_configured(aurora, verbose=verbose)
        info_message = f"already configured as '{name}'" if name is not None else "not yet configured"

        if not click.confirm(f"This Aurora is {info_message}, do you want to start the setup for it?"):
            click.echo(f"Skipping setup for Aurora at {str(aurora)}")
            continue

        aurora.name = click.prompt(f"Please give this Aurora a name:", default="My Nanoleaf")

        click.echo(f"Continuing setup for Aurora at {str(aurora)}")

        while True:
            click.confirm(f"Please hold the power button of the Aurora at {str(aurora)} for ~5 seconds "
                          f"until the LED starts to blink, then press ENTER to continue with the setup", default=True)
            try:
                aurora.generate_token()
                break
            except AuroraException as e:
                click.echo(f"Could not generate token, error was: {str(e)}. Please try again")

        click.echo("Token was successfully generated, adding Aurora to the config")

        add_aurora_to_config(aurora)
        click.echo(f"Aurora was saved to config. You can find it in {CONF_PATH}")

    click.echo("Added all requested Auroras - Done.")


# EFFECT MANAGEMENT


@cli.group()
def effects():
    pass


@effects.command(name="set")
@click.argument("name", nargs=-1)
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def set_effect(name: str, aurora: str, verbose: bool):
    aurora = get_leaf_by_name_or_default(aurora, verbose=verbose)
    effect_name = " ".join(name)
    try:
        aurora.set_active_effect(effect_name)
    except AuroraException:
        if verbose:
            click.echo(f"Did not find effect with name {effect_name} (case sensitive), trying closest match")
        closest = get_close_matches(effect_name, aurora.get_effect_names(), n=1)
        if len(closest) == 0:
            click.echo(f"Did not find effect with name {effect_name} and could not find a similar name")
            return
        effect_name = closest[0]
        aurora.set_active_effect(effect_name)
    click.echo(f"Set current effect to {effect_name}")


@effects.command(name="delete")
@click.argument("name", nargs=-1)
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def delete_effect(name: str, aurora: str, verbose: bool):
    aurora = get_leaf_by_name_or_default(aurora, verbose=verbose)
    effect_name = " ".join(name)
    click.confirm(f"This will delete the effect '{effect_name}' from {aurora}, are you sure?", abort=True)

    try:
        aurora.delete_effect(effect_name)
    except AuroraException:
        if verbose:
            click.echo(f"Did not find effect with name {effect_name} (case sensitive), trying closest match")
        closest = get_close_matches(effect_name, aurora.get_effect_names(), n=1)
        if len(closest) == 0:
            click.echo(f"Did not find effect with name {effect_name} and could not find a similar name")
            return
        effect_name = closest[0]
        aurora.delete_effect(effect_name)
    click.echo(f"Deleted effect {effect_name}")


@effects.command(name="get")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def get_command(aurora: str, verbose: bool):
    aurora = get_leaf_by_name_or_default(aurora, verbose=verbose)
    click.echo(aurora.get_active_effect())


@effects.command(name="list")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-n", "--names", is_flag=True, default=False, help="Only prints the effect names and exits")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def list_effects_command(aurora: str, names: bool, verbose: bool):
    aurora = get_leaf_by_name_or_default(aurora, verbose=verbose)
    active_effect = aurora.get_active_effect()
    for effect in aurora.get_effects():

        # simple name printing
        if names:
            click.echo(effect.name)
            continue

        # pretty printing with effect colors and active marker
        active = "[X]" if active_effect == effect.name else "[ ]"
        click.echo(f"{active} {effect.to_terminal()}")


@effects.command()
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def imagegen(aurora: str, verbose: bool):
    aurora = get_leaf_by_name_or_default(aurora, verbose=verbose)
    save_images(aurora)
    click.echo(f"Generated images into {IMAGE_PATH}")


@effects.command()
@click.option("-d", "--delay", default=3, show_default=True,
              help="Effect update delay in seconds")
@click.option("-t", "--top", default=4, show_default=True,
              help="How many of the quantized colors should be used for the effect")
@click.option("-q", "--quantization", default=4, show_default=True,
              help="In how many different colors should the screen be broken down to")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def ambi(delay: int, top: int, quantization: int, aurora: str, verbose: bool):
    aurora = get_leaf_by_name_or_default(aurora, verbose=verbose)
    if quantization < top:
        warn("Quantization is less than top, which doesn't make sense. "
             f"Reducing top to match quantization ({quantization})")
        top = quantization
    while True:
        start = time.time()
        set_effect_to_current_screen_colors(aurora, quantization, top)
        if verbose > 0:
            print(f"Updating effect took {time.time()-start} seconds")
        time.sleep(delay)


# ALFRED WORKFLOW HELPERS

@cli.group()
def alfred():
    pass


@alfred.command(name="prompt")
def alfred_prompt():
    aurora = get_leaf_by_name_or_default(None)

    data = []
    for effect in aurora.get_effects():
        effect_data = {
            "uuid": effect.name,
            "title": effect.name,
            "autocomplete": effect.name,
            "arg": effect.name,
            "subtitle": "change theme",
            "icon": {
                "path": image_path_for(aurora, effect)
            }
        }
        data.append(effect_data)
    click.echo(json.dumps({"items": data}))


@alfred.command(name="command")
@click.argument("command", nargs=-1)
@click.pass_context
def alfred_command(ctx, command: str):
    command_string = " ".join(command)
    ctx.invoke(set_effect, name=command_string)


if __name__ == '__main__':
    cli()
