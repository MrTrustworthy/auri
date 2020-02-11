import json
from difflib import get_close_matches
from typing import Union

import click

from auri.ambilight_controller import AmbilightController, AMBILIGHT_EFFECT_NAME
from auri.aurora import Aurora, AuroraException
from auri.device_finder import DeviceFinder
from auri.device_manager import DeviceManager


# TODO create wrapper or validator that checks we have a valid default/named aurora and redirects to setup if needed
# TODO catch config and aurora exceptions and print them nicely

class CtxObj:
    def __init__(self, aurora: Union[str, None], verbose: bool = False):
        self.dm = DeviceManager(verbose=verbose)
        self.aurora_name = aurora
        self.__aurora = None
        self.verbose = verbose

    @property
    def aurora(self):
        """Lazily create the actual aurora object when it's needed"""
        if not self.__aurora:
            self.__aurora = self.dm.get_by_name_or_active(self.aurora_name)
        return self.__aurora


@click.group()
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use, see `device list`")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
@click.pass_context
@click.version_option("1.3.4")
def cli(ctx: CtxObj, aurora: Union[str, None], verbose: bool):
    ctx.obj = CtxObj(aurora, verbose)


# GENERAL SETTING COMMANDS

@cli.command(name="on", help="Turn on the active device")
@click.pass_obj
def on_command(obj: CtxObj):
    obj.aurora.on = True


@cli.command(name="off", help="Turn off the active device")
@click.pass_obj
def off_command(obj: CtxObj):
    obj.aurora.on = False


@cli.command(name="brighter", help="Make the current effect brighter")
@click.pass_obj
def brighter_command(obj: CtxObj):
    current = obj.aurora.brightness
    new = min(current + 20, 100)
    click.echo(f"Brightness {current}->{new}")
    obj.aurora.brightness = new


@cli.command(name="darker", help="Make the current effect darker")
@click.pass_obj
def darker_command(obj: CtxObj):
    current = obj.aurora.brightness
    new = max(current - 20, 0)
    click.echo(f"Brightness {current}->{new}")
    obj.aurora.brightness = new

# EFFECT COMMANDS

@cli.command(name="play", help="Switches the device to a specific effect. Uses spelling correction.")
@click.argument("name", nargs=-1)
@click.pass_obj
def play_command(obj: CtxObj, name: str):
    effect_name = " ".join(name)
    closest = get_close_matches(effect_name, obj.aurora.get_effect_names(), n=1, cutoff=0)
    if len(closest) == 0:
        # As long as there is a single effect, this should not happen
        click.echo(f"Did not find anything similar to {effect_name}, are there no effects on this device?")
        return
    effect_name = closest[0]

    if effect_name.lower() == AMBILIGHT_EFFECT_NAME.lower():
        # TODO: could probably also forward this to ambi automatically
        click.echo("WARNING: Playing AuriAmbi doesn't activate the Ambi function, use `auri ambi` instead!")

    effect = obj.aurora.get_effect_by_name(effect_name)
    obj.aurora.set_active_effect(effect_name)
    click.echo(f"Set current effect to {effect_name} {effect.color_flag_terminal()}")


@cli.command(name="delete", help="Deletes a specified effect. Warning: This isn't reversible!")
@click.argument("name", nargs=-1)
@click.pass_obj
def delete_command(obj: CtxObj, name: str):
    effect_name = " ".join(name)
    click.confirm(f"This will delete the effect '{effect_name}' from {obj.aurora}, are you sure?", abort=True)

    try:
        obj.aurora.delete_effect(effect_name)
        click.echo(f"Deleted effect {effect_name}")
    except AuroraException:
        click.echo(f"Did not find effect with name {effect_name}")


@cli.command(name="list", help="Displays all effects that are currently installed on this device")
@click.option("-n", "--names", is_flag=True, default=False, help="Only prints the effect names and exits")
@click.pass_obj
def list_command(obj: CtxObj, names: bool):
    active_effect_name = obj.aurora.get_active_effect_name()
    for effect in obj.aurora.get_effects():

        # simple name printing
        if names:
            click.echo(effect.name)
            continue

        # pretty printing with effect colors and active marker
        active = "[X]" if active_effect_name == effect.name else "[ ]"
        click.echo(f"{active} {effect.color_flag_terminal()} {effect.name}")


# AMBINANO COMMANDS

@cli.command(name="ambi", help="Toggles the ambilight functionality")
@click.pass_context
def ambi(ctx: click.Context):
    ambi_controller = AmbilightController(ctx.obj.aurora, verbose=ctx.obj.verbose)

    if not ambi_controller.is_running:
        ambi_controller.start()
        click.echo("auri ambi started")
        return

    ambi_controller.stop()
    ctx.forward(off_command)
    click.echo("auri ambi stopped")


@cli.command(name="ambi-blocking", help="Toggles the ambilight functionality", hidden=True)
@click.pass_obj
def ambi_blocking(obj: CtxObj):
    """This is used to start the ambi in blocking mode

    Not exposed to the user, it needs to match ambilight_controller.AMBI_CALL_ARGS to identify the process
    """
    ambi_controller = AmbilightController(obj.aurora, verbose=obj.verbose)
    ambi_controller.start_blocking()


# DEVICE AND CONTEXT MANAGEMENT


@cli.group(name="device", help="Interact with Nanoleaf devices")
def device_group():
    pass


@device_group.command(name="activate", help="Set a specified Nanoleaf to the currently active one")
@click.argument("name", nargs=-1)
@click.pass_obj
def activate(obj: CtxObj, name: str):
    name = " ".join(name)
    obj.dm.set_active(name)
    click.echo(f"Set {name} as active Aurora")


@device_group.command(name="list", help="Lists all currently configured Nanoleaf devices")
@click.pass_obj
def device_list_command(obj: CtxObj):
    for aurora in obj.dm.get_all():
        active = "[X]" if obj.dm.is_active(aurora) else "[ ]"
        click.echo(f"{active} {str(aurora)}")


@device_group.command(name="identify", help="Make the device blink")
@click.pass_obj
def device_identify_command(obj: CtxObj):
    obj.aurora.identify()


@device_group.command(name="setup", help="Run this to configure new Nanoleaf devices")
@click.option("-a", "--amount", default=1, show_default=True,
              help="How many Auroras to search for. Set this to the number of Auroras that are in your WLAN")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_setup_command(amount: int, verbose: bool):
    click.echo(f"Searching for a total of {amount} Nanoleaf Auroras, press <CTRL+C> to cancel")
    manager = DeviceManager(verbose=verbose)

    for aurora_ip, aurora_mac in DeviceFinder(verbose=verbose).find_aurora_addresses(amount):
        aurora_description = f"{aurora_ip} (MAC: {aurora_mac})"
        click.echo(f"Found one Aurora at {aurora_description}")

        # let's find out if a device with that IP is already configured and offer to change the name
        name = manager.get_name_by_ip(aurora_ip)
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
        manager.save_aurora(aurora)
        click.echo(f"Aurora was saved to config. You can find it in {manager.conf_path}")

    click.echo("Added all requested Auroras - Done.")


# ALFRED WORKFLOW HELPERS

@cli.group(name="alfred", help="Alfred integration functions")
def alfred_group():
    pass


@alfred_group.command(name="prompt", help="Alfred prompt in JSON format")
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


@alfred_group.command(name="command", help="Parse command from `auri alfred prompt`")
@click.argument("command", nargs=-1)
@click.pass_context
def alfred_command_command(ctx: click.Context, command: str):
    command_string = " ".join(command)
    ctx.invoke(play_command, name=command_string)


@alfred_group.command(name="images", help="Generates image files for each effect")
@click.pass_obj
def alfred_images_command(obj: CtxObj):
    obj.dm.generate_image_cache()
    click.echo(f"Generated images into {obj.dm.image_path}")


if __name__ == '__main__':
    cli()
