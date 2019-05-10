# Auri - Nanoleaf Aurora CLI [![Build Status](https://travis-ci.org/MrTrustworthy/auri.svg?branch=master)](https://travis-ci.org/MrTrustworthy/auri)

A simple, light-weight tool for controlling multiple Aurora devices from the CLI. Supports the most important functionality of the Nanoleaf app (registering new devices, switching effects, changing brightness, on/off,...) as well as an Ambilight feature that is based on the colors of your main display.


## Usage 

### First-time setup

As it's a Python3-based application, you can install the CLI via it's package manager if you're using Python already. If you're on MacOS, you can use `brew` to install it instead.

To find and generate credentials for the Nanoleaf Aurora device in your home, make sure your PC/Laptop is in the same network and run `auri device setup`. If you have multiple devices, you can set them up at the same time by specifying the number of devices to look for, ex `auri device setup -a 3` if you have 3 devices.

You can give each device a name and switch between the currently active device by running `auri device activate MyOtherNanoleafName`. All commands from the CLI will only affect the currently active device.

### Basic functionality

Switching effects is done via `auri effects`, like `auri effects play rain`. There is a basic autocorrection to find the effect you meant even if you mistype.

Switching brightness and other simple values can be done via ex. `auri effects set brightness 50`. To get the current values, simply use `get` instead of `set`.

The effect list uses terminal colors to show a preview of the effect colors, so `auri effects list` will show you something like this:

![auri_effect_list](https://raw.githubusercontent.com/MrTrustworthy/auri/master/auri_effect_list_terminal.png)


### Alfred Integration

You can use this CLI to build a very simple alfred workflow to change effects. Simply run `auri device images` to generate some preview images for all your effects, then create a simple workflow that has `auri alfred prompt` as a script filter and pipes the result to `auri alfred command` as a "run script" action.


### Ambilight

There is a built-in ambilight functionality that is based on your primary display. Use `auri effects ambi` to start a blocking shell that will update the effect each seconds. It needs to create a new effect on the device to do so, which will be called `AuriAmbi` so you know what it is.

You can customize the behaviour of the ambilight, just use `auri effects ambi --help` to see which parameters you can play with, though the default settings work quite nice.

## Contributing

In case you want new features, feel free to implement them and shoot me a PR. The codebase is small and pretty easy to understand, and in case you're missing a feature it's probably not because it's hard to implement but because I didn't think of it.

## Acknowledgements

Some of the code has been (in altered form) taken from [Anthony Brians GitHub Project "Nanoleaf"](https://github.com/software-2/nanoleaf). Thanks for figuring out the device discovery Anthony!
