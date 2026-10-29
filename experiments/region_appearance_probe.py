"""Experimental host-only region colour and rectangular geometry.

Input: already approved RGB image and untrusted YOLOX box. This module does
NOT detect objects, distinguish foreground/background, identify objects,
establish physical size, prove roundness, interact with OEM or write memories.
"""
from __future__ import annotations

import colorsys
from collections import Counter
import math

SAMPLE_SIDE = 24
MIN_REGION_PX = 12
DOMINANCE_MIN = 0.55
DOMINANCE_GAP = 0.20
CENTRAL_FRACTION = 0.55


def rgb_colour(rgb):
    """Coarse, intentionally nonsemantic RGB color bins."""
    r, g, b = rgb
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if v < 0.17:
        return "black"
    if s < 0.18:
        return "white" if v >= 0.80 else "gray"
    hue = h * 360
    if hue < 14 or hue >= 345:
        return "red"
    if hue < 43:
        return "orange"
    if hue < 66:
        return "yellow"
    if hue < 92:
        return "yellow_green"
    if hue < 170:
        return "green"
    if hue < 201:
        return "cyan"
    if hue < 260:
        return "blue"
    if hue < 295:
        return "violet"
    return "pink"


def _color_summary(pixels):
    if not pixels:
        return {"color": "unknown", "dominance": 0.,
                "runner_up": 0., "measured": False}
    counts = Counter(rgb_colour(p) for p in pixels)
    vals = sorted(counts.values(), reverse=True)
    n = len(pixels)
    top = vals[0] / n
    runner = (vals[1] / n) if len(vals) > 1 else 0.
    name = next(k for k, v in counts.items() if v == vals[0])
    enough = top >= DOMINANCE_MIN and top - runner >= DOMINANCE_GAP
    return {"color": name if enough else "unknown",
            "dominance": round(top, 4),
            "runner_up": round(runner, 4),
            "measured": enough}


def describe_region(image, xyxy, *, central_fraction=CENTRAL_FRACTION):
    """Describe region pixels only; return unknown for mixed pixels.

    Sampling uses the fixed center fraction of the bounding rectangle. The
    surrounding background may dominate; this is evaluated with independent
    polygon masks, not assumed away.
    """
    from PIL import Image
    if not isinstance(image, Image.Image) or image.mode != "RGB":
        raise TypeError("bounded RGB Pillow image required")
    w, h = image.size
    if not 32 <= w <= 4096 or not 32 <= h <= 4096:
        raise ValueError("out of range image geometry")
    if (not isinstance(xyxy, (tuple, list)) or len(xyxy) != 4
            or any(type(v) not in (float, int) or not math.isfinite(v)
                   for v in xyxy)):
        raise ValueError("invalid rectangle")
    x1, y1, x2, y2 = map(float, xyxy)
    if not 0 <= x1 < x2 <= w or not 0 <= y1 < y2 <= h:
        raise ValueError("rectangle must be inside image")
    if type(central_fraction) not in (float, int) or central_fraction not in (
        CENTRAL_FRACTION, 1.0
    ):
        raise ValueError("only preregistered sampling fractions")
    bw, bh = x2-x1, y2-y1
    cx, cy = (x1+x2)/2., (y1+y2)/2.
    aspect = bw/bh
    shape_hint = ("wide_box" if aspect >= 1.8 else
                  "tall_box" if aspect <= 0.55 else "roughly_square_box"
                  if .80 <= aspect <= 1.25 else "rectangular_box")
    geometry = {"bbox_width_fraction": round(bw/w, 4),
                "bbox_height_fraction": round(bh/h, 4),
                "bbox_aspect_ratio": round(aspect, 4),
                "bbox_geometry_only": shape_hint,
                "center_x_fraction": round(cx/w, 4),
                "center_y_fraction": round(cy/h, 4)}
    if min(bw, bh) < MIN_REGION_PX:
        return {"status": "unknown", "reason": "small_roi", "color": "unknown",
                "geometry": geometry, "not_object_shape": True}
    left = max(0, int(math.floor(cx - bw*central_fraction/2)))
    upper = max(0, int(math.floor(cy - bh*central_fraction/2)))
    right = min(w, int(math.ceil(cx + bw*central_fraction/2)))
    bottom = min(h, int(math.ceil(cy + bh*central_fraction/2)))
    if min(right-left,bottom-upper) < 6:
        return {"status": "unknown", "reason": "sampling_too_small",
                "color": "unknown", "geometry": geometry,
                "not_object_shape": True}
    tile = image.crop((left, upper, right, bottom)).resize(
        (SAMPLE_SIDE, SAMPLE_SIDE), resample=Image.Resampling.BILINEAR
    )
    colors = _color_summary(list(tile.getdata()))
    return {"status": "color_candidate" if colors["measured"] else "unknown",
            "reason": "dominant_region_pixels_not_verified_foreground"
                       if colors["measured"] else "ambiguous_color",
            "color": colors["color"],
            "color_dominance": colors["dominance"],
            "color_runner_up": colors["runner_up"],
            "geometry": geometry,
            "not_object_shape": True,
            "not_object_category": True,
            "not_physical_size_or_distance": True,
            "source_pixels_stored": False}
