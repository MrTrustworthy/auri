import json
from difflib import get_close_matches

import json
from difflib import get_close_matches

import click

from auri.ambilight import AmbilightController
from auri.aurora import Aurora, AuroraException
from auri.device_finder import DeviceFinder
from auri.device_manager import DeviceManager


# TODO create wrapper or validator that checks we have a valid default/named aurora and redirects to setup if needed
# TODO catch config and aurora exceptions and print them nicely

@click.group()
@click.version_option("1.0.0")
def cli():
    pass


# AURORA AND CONTEXT MANAGEMENT


@cli.group(name="device")
def device_group():
    pass


@device_group.command()
@click.argument("name", nargs=-1)
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def activate(name: str, verbose: bool):
    name = " ".join(name)
    DeviceManager().set_active(name, verbose=verbose)
    click.echo(f"Set {name} as active Aurora")


@device_group.command(name="list")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_list_command(verbose: bool):
    manager = DeviceManager()
    for aurora in manager.get_all():
        active = "[X]" if manager.is_active(aurora, verbose=verbose) else "[ ]"
        click.echo(f"{active} {str(aurora)}")


@device_group.command(name="images")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_images_command(verbose: bool):
    manager = DeviceManager()
    manager.generate_images()
    click.echo(f"Generated images into {manager.image_path}")


@device_group.command(name="query")
@click.argument("option", default="info")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_query_command(option: str, aurora: str, verbose: bool):
    aurora = DeviceManager().get_by_name_or_active(aurora, verbose=verbose)
    try:
        result = getattr(aurora, option)
        if callable(result):
            result = result()
        click.echo(str(result))
    except AttributeError:
        click.echo(f"Operator '{option}' doesn't exist")


@device_group.command(name="setup")
@click.option("-a", "--amount", default=1, show_default=True,
              help="How many Auroras to search for. Set this to the number of Auroras that are in your WLAN")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_setup_command(amount: int, verbose: bool):
    click.echo(f"Searching for a total of {amount} Nanoleaf Auroras, press <CTRL+C> to cancel")
    manager = DeviceManager()

    for aurora_ip, aurora_mac in DeviceFinder().find_aurora_addresses(amount):

        aurora_description = f"{aurora_ip} (MAC: {aurora_mac})"

        click.echo(f"Found one Aurora at {aurora_description}")

        # let's find out if a device with that IP is already configured and offer to change the name
        name = manager.get_name_by_ip(aurora_ip, verbose=verbose)
        info_message = f"already configured as '{name}'" if name is not None else "not yet configured"

        if not click.confirm(f"This Aurora is {info_message}, do you want to start the setup for it?"):
            click.echo(f"Skipping setup for Aurora at {aurora_description}")
            continue

        aurora_name = click.prompt(f"Please give this Aurora a name:", default="My Nanoleaf" if name is None else name)
        aurora = Aurora(aurora_ip, aurora_name, aurora_mac, None)  # Token and name will be set later

        click.echo(f"Continuing setup for Aurora at {aurora_description}")

        while True:
            click.confirm(f"Please hold the power button of the Aurora at {aurora_description} for ~5 seconds "
                          f"until the LED starts to blink, then press ENTER to continue with the setup", default=True)
            try:
                aurora.generate_token()
                break
            except AuroraException as e:
                click.echo(f"Could not generate token, error was: {str(e)}. Please try again")

        click.echo("Token was successfully generated, adding Aurora to the config")

        manager.save_aurora(aurora, verbose=verbose)
        click.echo(f"Aurora was saved to config. You can find it in {manager.conf_path}")

    click.echo("Added all requested Auroras - Done.")


# EFFECT MANAGEMENT


@cli.group(name="effects")
def effects_group():
    pass


@effects_group.command(name="set")
@click.argument("name", nargs=-1)
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_set_command(name: str, aurora: str, verbose: bool):
    aurora = DeviceManager().get_by_name_or_active(aurora, verbose=verbose)
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


@effects_group.command(name="delete")
@click.argument("name", nargs=-1)
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_delete_command(name: str, aurora: str, verbose: bool):
    aurora = DeviceManager().get_by_name_or_active(aurora, verbose=verbose)
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


@effects_group.command(name="get")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_get_command(aurora: str, verbose: bool):
    aurora = DeviceManager().get_by_name_or_active(aurora, verbose=verbose)
    click.echo(aurora.get_active_effect_name())


@effects_group.command(name="list")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-n", "--names", is_flag=True, default=False, help="Only prints the effect names and exits")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_list_command(aurora: str, names: bool, verbose: bool):
    aurora = DeviceManager().get_by_name_or_active(aurora, verbose=verbose)
    active_effect_name = aurora.get_active_effect_name()
    for effect in aurora.get_effects():

        # simple name printing
        if names:
            click.echo(effect.name)
            continue

        # pretty printing with effect colors and active marker
        active = "[X]" if active_effect_name == effect.name else "[ ]"
        click.echo(f"{active} {effect.color_flag_terminal()} {effect.name}")


@effects_group.command(name="ambi")
@click.option("-d", "--delay", default=1, show_default=True,
              help="Effect update delay in seconds")
@click.option("-t", "--top", default=10, show_default=True,
              help="How many of the quantized colors should be used for the effect")
@click.option("-q", "--quantization", default=10, show_default=True,
              help="In how many different colors should the screen be broken down to")
@click.option("-g", "--greyness", default=10, show_default=True,
              help="How 'grey' can something be before it will be filtered out")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_ambi_command(delay: int, top: int, quantization: int, aurora: str, greyness: int, verbose: bool):
    # TODO start in background, stop with command
    aurora = DeviceManager().get_by_name_or_active(aurora, verbose=verbose)
    AmbilightController(aurora, quantization, top, greyness, delay, verbose=verbose).run_ambi_loop()


# ALFRED WORKFLOW HELPERS

@cli.group(name="alfred")
def alfred_group():
    pass


@alfred_group.command(name="prompt")
def alfred_prompt_command():
    manager = DeviceManager()
    aurora = manager.get_active()

    data = []
    for effect in aurora.get_effects():
        effect_data = {
            "uuid": effect.name,
            "title": effect.name,
            "autocomplete": effect.name,
            "arg": effect.name,
            "subtitle": "change theme",
            "icon": {
                "path": manager.image_path(aurora, effect)
            }
        }
        data.append(effect_data)
    click.echo(json.dumps({"items": data}))


@alfred_group.command(name="command")
@click.argument("command", nargs=-1)
@click.pass_context
def alfred_command_command(ctx, command: str):
    command_string = " ".join(command)
    ctx.invoke(effects_set_command, name=command_string)


if __name__ == '__main__':
    cli()
