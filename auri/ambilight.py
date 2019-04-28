from colorsys import rgb_to_hsv
from typing import List, Tuple, Any, Dict

from PIL import ImageGrab

from auri.aurora import Aurora

Color = Tuple[int, int, int]
Template = Dict[str, Any]

EFFECT_TEMPLATE: Template = {
    "command": "add",
    "animName": "AuriAmbi",
    "animType": "random",
    "colorType": "HSB",
    "animData": None,
    "palette": [],  # This is overwritten by the calling function
    "brightnessRange": {
        "minValue": 5,
        "maxValue": 15
    },
    "transTime": {
        "minValue": 20,
        "maxValue": 30
    },
    "delayTime": {
        "minValue": 25,
        "maxValue": 100
    },
    "loop": True
}


def set_effect_to_current_screen_colors(aurora: Aurora, quantization: int, top: int):
    """ Returns a list of the top-N colors the main monitor currently shows in HSV-format

    :param aurora: Instance of the Nanoleaf device to use
    :param quantization: As each pixel might have a slightly different color, quantization is used to reduce the colors
        into a set of similar colors. Setting this lower means having more different colors show up in the result
    :param top: How many of the top colors to use for the nanoleaf
    """
    assert quantization >= top, f"Quantization ({quantization}) must be at least as big as Top ({top})!"
    colors = _get_current_display_image_colors(quantization, top)
    effect_data = _render_effect_template(colors)
    aurora.effect_set_raw(effect_data)


def _get_current_display_image_colors(quantization: int, top: int) -> List[Color]:
    """ Returns a list of the top-N colors the main monitor currently shows in HSV-format

    :param quantization: As each pixel might have a slightly different color, quantization is used to reduce the colors
        into a set of similar colors. Setting this lower means having more different colors show up in the result
    :param top: How many of the colors to return
    :return: List of :top: colors after quantization, sorted by the frequency of their appearance
    """

    img = ImageGrab.grab()
    img = img.quantize(quantization)
    colors = sorted(img.convert("RGB").getcolors(), reverse=True)

    return [_rgb_to_hsv(color) for frequency, color in colors[:top]]


def _render_effect_template(colors: List[Color]) -> Template:
    """ Given a list of colors, renders the effects template that can be HTTP PUT to Nanoleaf

    :param: colors: List of all colors in HSV/HSB format that's used for rendering
    :return: Rendered template that is accepted by the Nanoleaf API
    """
    palette = [
        {
            "hue": c[0],
            "saturation": c[1],
            "brightness": c[2]
        }
        for c in colors
    ]
    rendered = {**EFFECT_TEMPLATE}  # Shallow copy just to be safe
    rendered["palette"] = palette
    return rendered


def _rgb_to_hsv(rgb_color: Color) -> Color:
    """ Converts the RGB colors we get from ImageGrab into HSV for the NanoLeaf

    `colorsys.py` expects and provides values in range [0, 1], but we get and need them in a different range
    """

    r, g, b = map(lambda v: v/255.0, rgb_color)
    h, s, v = rgb_to_hsv(r, g, b)
    h, s, v = int(h*360), int(s*100), int(v*100)
    return h, s, v

