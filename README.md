# Auri - Nanoleaf Aurora CLI [![Build Status](https://travis-ci.org/MrTrustworthy/auri.svg?branch=master)](https://travis-ci.org/MrTrustworthy/auri)

A simple, light-weight tool for controlling multiple Aurora devices from the CLI. Supports the most important functionality of the Nanoleaf app (registering new devices, switching effects, changing brightness, on/off,...) as well as an Ambilight feature that is based on the colors of your main display.


## Usage 

![Auri Gif Sample](https://raw.githubusercontent.com/MrTrustworthy/auri/master/preview.gif)

### Installation

As it's a Python3-based application, you can install the CLI simply via `pip`. `pip install auri` or `python3 -m pip install auri` (if your default pip is for Python2) are both acceptable ways of installing.

### Device management and setup

To find and generate credentials for the Nanoleaf Aurora device in your home, make sure your PC/Laptop is in the same network and run `auri device setup`. Auri will then guide you through the setup for each device it can find and allow you to set a name for each device in your home. Auri saves the device data and access tokens in a small file in your application config folder, so you only have to do this once. 

You can switch the currently active device by running `auri device activate <device name>`. In general, all commands will only affect the currently active device. If you want a command to apply to a different device, either `auri device activate` it or target a specific device like `auri -a <device name> play Flames`.

### Playing and changing effects

Switching effects is done via `auri play`, like `auri play rain`. There is a best-effort spelling correction to find the effect you meant even if you mistype or only provide a part of the effect name. The most common operations are easily accessible, for example `on`, `off`, `brighter` and `darker` will do exactly what you'd expect. `auri list` will show you all available effects including a small color preview in the terminal.


### Ambilight

There is a built-in ambilight functionality that is based on your primary display. Use `auri ambi` to toggle the _ambi_ mode that will update the effect each seconds. It needs to create a new effect on the device to do so, which will be called `AuriAmbi` so you know what it is.

You can customize the behaviour of the ambilight, just check your config file (see "Device management and setup") to see which parameters you can play with, though the default settings should work quite nicely without any tuning. The Ambilight functionality only works on MacOS and Windows, but not on Linux due to the dependency on `ImageGrab`. If you're using Linux and know of a way to get this working, feel free to shoot me a PR.

### Alfred Integration

If you're on MacOS, you can also use this CLI to easily build a [Alfred](https://www.alfredapp.com/) workflow to change effects and have preview images for each effect in your search bar. Simply run `auri alfred images` to generate some preview images for all your effects, then create a simple workflow that has `auri alfred prompt` as a script filter and pipes the result to `auri alfred command` as a "run script" action.

## Contributing

In case you want new features, feel free to implement them and shoot me a PR. The codebase is small and pretty easy to understand, and in case you're missing a feature it's probably not because it's hard to implement but because I didn't think of it.

## Acknowledgements

Some of the code has been (in altered form) taken from [Anthony Brians GitHub Project "Nanoleaf"](https://github.com/software-2/nanoleaf). Thanks for figuring out the device discovery Anthony!
