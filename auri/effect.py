from colorsys import hsv_to_rgb
from typing import Any, Dict


class EffectColor:
    def __init__(self, data: Dict[str, int]):
        self.hue = data["hue"]
        self.saturation = data["saturation"]
        self.brightness = data["brightness"]
        self.termcode_text = " "

    @property
    def rgb(self):
        h, s, v = self.hue / 360, self.saturation / 100, self.brightness / 100
        rgb = hsv_to_rgb(h, s, v)
        return list(map(lambda x: min(5, int(x * 6)), rgb))  # scale is [0-1]

    @property
    def termcode_number(self):
        r, g, b = self.rgb
        number = 16 + 36 * r + 6 * g + b  # https://stackoverflow.com/a/27165165/2683726
        return number

    @property
    def termcode(self):
        return f'\033[48;5;{self.termcode_number}m{self.termcode_text}\033[0m'

    @property
    def details(self):
        return f"RGB: {self.rgb}, Number: {self.termcode_number}, Code: {self.termcode}"


class Effect:
    def __init__(self, effect_data: Dict[str, Any]):
        self.name = effect_data["animName"]
        self.palette = [EffectColor(data) for data in effect_data["palette"]]

    def to_terminal(self):
        return f"{self.name}: {''.join(c.termcode for c in self.palette)}"
