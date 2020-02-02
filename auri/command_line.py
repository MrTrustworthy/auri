import json
import os
import signal
import subprocess
import sys
from difflib import get_close_matches

import click

from auri.ambilight import AmbilightController
from auri.aurora import Aurora, AuroraException
from auri.device_finder import DeviceFinder
from auri.device_manager import DeviceManager


# TODO create wrapper or validator that checks we have a valid default/named aurora and redirects to setup if needed
# TODO catch config and aurora exceptions and print them nicely

@click.group()
@click.version_option("1.1.2")
def cli():
    pass


# AURORA AND CONTEXT MANAGEMENT


@cli.group(name="device", help="Interact with Nanoleaf devices")
def device_group():
    pass


@device_group.command(name="activate", help="Set a specified Nanoleaf to the currently active one")
@click.argument("name", nargs=-1)
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def activate(name: str, verbose: bool):
    name = " ".join(name)
    DeviceManager(verbose=verbose).set_active(name)
    click.echo(f"Set {name} as active Aurora")


@device_group.command(name="list", help="Lists all currently configured Nanoleaf devices")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_list_command(verbose: bool):
    manager = DeviceManager(verbose=verbose)
    for aurora in manager.get_all():
        active = "[X]" if manager.is_active(aurora) else "[ ]"
        click.echo(f"{active} {str(aurora)}")


@device_group.command(name="query", help="Query the Nanoleaf device with a custom attribute for debugging")
@click.argument("option", default="info")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_query_command(option: str, aurora: str, verbose: bool):
    aurora = DeviceManager(verbose=verbose).get_by_name_or_active(aurora)
    try:
        result = getattr(aurora, option)
        if callable(result):
            result = result()
        click.echo(str(result))
    except AttributeError:
        click.echo(f"Operator '{option}' doesn't exist")


@device_group.command(name="on", help="Turn on the active device")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_on_command(aurora: str, verbose: bool):
    DeviceManager(verbose=verbose).get_by_name_or_active(aurora).on = True


@device_group.command(name="off", help="Turn off the active device")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def device_off_command(aurora: str, verbose: bool):
    DeviceManager(verbose=verbose).get_by_name_or_active(aurora).on = False


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


# EFFECT MANAGEMENT


@cli.group(name="effects", help="Interact with effects of the current device")
def effects_group():
    pass


@effects_group.command(name="play", help="Switches the device to a specific effect. Uses spelling correction.")
@click.argument("name", nargs=-1)
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_play_command(name: str, aurora: str, verbose: bool):
    aurora = DeviceManager(verbose=verbose).get_by_name_or_active(aurora)
    effect_name = " ".join(name)

    if effect_name.lower() == "auriambi":
        # TODO: could probably also forward this to ambi automatically
        click.echo("WARNING: Playing AuriAmbi doesn't activate the Ambi function, use `auri effects ambi` instead!")

    closest = get_close_matches(effect_name, aurora.get_effect_names(), n=1, cutoff=0)
    if len(closest) == 0:
        # As long as there is a single effect, this should not happen
        click.echo(f"Did not find anything similar to {effect_name}, are there no effects on this device?")
        return
    effect_name = closest[0]
    effect = aurora.get_effect_by_name(effect_name)
    aurora.set_active_effect(effect_name)
    click.echo(f"Set current effect to {effect_name} {effect.color_flag_terminal()}")


@effects_group.command(name="delete", help="Deletes a specified effect. Warning: This isn't reversible!")
@click.argument("name", nargs=-1)
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_delete_command(name: str, aurora: str, verbose: bool):
    aurora = DeviceManager(verbose=verbose).get_by_name_or_active(aurora)
    effect_name = " ".join(name)
    click.confirm(f"This will delete the effect '{effect_name}' from {aurora}, are you sure?", abort=True)

    try:
        aurora.delete_effect(effect_name)
        click.echo(f"Deleted effect {effect_name}")
    except AuroraException:
        click.echo(f"Did not find effect with name {effect_name}")


@effects_group.command(name="get", help="Gets either name or brightness of the current effect")
@click.argument("option")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_get_command(option: str, aurora: str, verbose: bool):
    aurora = DeviceManager(verbose=verbose).get_by_name_or_active(aurora)
    output = f"Couldn't find option {option} for `effects get"
    if option == "name":
        output = aurora.get_active_effect_name()
    elif option == "brightness":
        output = aurora.brightness

    click.echo(output)


@effects_group.command(name="set", help="Sets either name or brightness of the current effect")
@click.argument("option")
@click.argument("value")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_set_command(option: str, value: str, aurora: str, verbose: bool):
    aurora = DeviceManager(verbose=verbose).get_by_name_or_active(aurora)
    if option == "brightness":
        aurora.brightness = int(value)
    elif option == "identify":
        aurora.identify()
    else:
        click.echo(f"Couldn't find the option {option}")
        sys.exit(1)

    click.echo(f"Set {option} to {value}")


@effects_group.command(name="list", help="Displays all effects that are currently installed on this device")
@click.option("-a", "--aurora", default=None, help="Which Nanoleaf to use")
@click.option("-n", "--names", is_flag=True, default=False, help="Only prints the effect names and exits")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def effects_list_command(aurora: str, names: bool, verbose: bool):
    aurora = DeviceManager(verbose=verbose).get_by_name_or_active(aurora)
    active_effect_name = aurora.get_active_effect_name()
    for effect in aurora.get_effects():

        # simple name printing
        if names:
            click.echo(effect.name)
            continue

        # pretty printing with effect colors and active marker
        active = "[X]" if active_effect_name == effect.name else "[ ]"
        click.echo(f"{active} {effect.color_flag_terminal()} {effect.name}")


@cli.group(name="ambi", help="Manage the ambilight functionality")
def ambi_group():
    pass

# TODO the additional arguments only work when being run in blocking mode, move them to the config
@ambi_group.command(name="start", help="Activates the ambilight functionality")
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
@click.option("-b", "--block", is_flag=True, default=False, help="Block the CLI while running ambi")
def effects_ambi_start(delay: int, top: int, quantization: int, aurora: str, greyness: int, verbose: bool,
                         block: bool):
    device_manager = DeviceManager(verbose=verbose)
    aurora = device_manager.get_by_name_or_active(aurora)

    # The non-blocking call of `ambi play` will start the blocking call as a daemon/subprocess
    if block:
        AmbilightController(aurora, quantization, top, greyness, delay, verbose=verbose).run_ambi_loop()
        return

    # TODO: find an approach that also works if ambi isn't available via global `ambi`, such as `python -m ambi`
    # TODO: Whenever the name/call-path of this command changes, this also has to be adjusted :(
    process = subprocess.Popen(
        ['auri', 'ambi', 'start', "-v"],
        cwd="/",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    device_manager.save_pid(process.pid)
    click.echo("auri ambi started")


@ambi_group.command(name="stop", help="Stops the ambilight functionality")
def effects_ambi_stop():
    pid = DeviceManager().load_pid()
    if pid is None:
        click.echo("Could not find a running `ambi`")
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        click.echo(f"Could not find a process with PID {pid}, maybe it was already killed?")
        return
    click.echo("auri ambi stopped")


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
def alfred_command_command(ctx, command: str):
    command_string = " ".join(command)
    ctx.invoke(effects_set_command, name=command_string)


@alfred_group.command(name="images", help="Generates image files for each effect")
@click.option("-v", "--verbose", is_flag=True, default=False, help="More Logging")
def alfred_images_command(verbose: bool):
    manager = DeviceManager(verbose=verbose)
    manager.generate_image_cache()
    click.echo(f"Generated images into {manager.image_path}")


if __name__ == '__main__':
    cli()
