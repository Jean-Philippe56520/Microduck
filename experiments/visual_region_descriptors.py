"""Experimental region colour / simple shape cues; never object identity.

No model, camera, SQLite, Qwen, sensor or motor access.  A YOLOX bounding
rectangle is NOT an object mask: reject clutter, partial cuts and ambiguous
backgrounds rather than manufacture a silhouette or category.
"""
from __future__ import annotations

import colorsys
from collections import Counter, deque
import math
from statistics import median

from PIL import Image, ImageFilter

MAX_SIDE = 96
MAX_SOURCE_PIXELS = 24_000_000
BG_SPREAD_LIMIT = 56.0


def _dist(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _colour(rgb):
    r, g, b = rgb
    h, saturation, value = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if value < 0.17:
        return "noir"
    if saturation < 0.16:
        return "blanc" if value > 0.79 else "gris" if value >= 0.36 else "noir"
    hue = h * 360.0
    if hue < 16 or hue >= 344:
        return "rouge"
    if hue < 43:
        return "orange"
    if hue < 65:
        return "jaune"
    if hue < 92:
        return "jaune-vert"
    if hue < 169:
        return "vert"
    if hue < 202:
        return "cyan"
    if hue < 258:
        return "bleu"
    if hue < 293:
        return "violet"
    return "rose"


def _indeterminate(reason, *, mode="unknown"):
    return {
        "status": "indeterminate",
        "reason": reason,
        "mask_source": mode,
        "dominant_colours": [],
        "shape": "indeterminee",
        "geometry": None,
        "object_category": "unknown",
    }


def describe_region(image: Image.Image, box) -> dict:
    """Describe only plausible foreground pixels in a supplied crop.

    Inputs must already be authorized, orientated images and a geometrically
    valid hypothesis from the same image coordinate system. No detection here.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("PIL image expected")
    w, h = image.size
    if not 16 <= w <= 8192 or not 16 <= h <= 8192 or w * h > MAX_SOURCE_PIXELS:
        raise ValueError("source geometry outside host safety bounds")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise ValueError("four ROI coordinates required")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
        raise ValueError("invalid ROI coordinates")
    x1, y1, x2, y2 = map(float, box)
    if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
        raise ValueError("ROI must be inside its image, in source coordinates")
    left, upper = int(math.floor(x1)), int(math.floor(y1))
    right, lower = int(math.ceil(x2)), int(math.ceil(y2))
    if right - left < 16 or lower - upper < 16:
        return _indeterminate("region_too_small")

    tile = image.crop((left, upper, right, lower)).convert("RGBA")
    tile.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.BILINEAR)
    tw, th = tile.size
    if min(tw, th) < 16:
        return _indeterminate("region_too_small")
    pixels = list(tile.getdata())
    pw, ph = max(2, tw // 9), max(2, th // 9)
    corners = [
        (0, 0), (tw - pw, 0), (0, th - ph), (tw - pw, th - ph)
    ]
    corner_indices = [
        [y * tw + x for y in range(cy, cy + ph)
         for x in range(cx, cx + pw)]
        for cx, cy in corners
    ]
    transparent_corners = sum(pixels[i][3] < 40
                              for idx in corner_indices for i in idx)
    alpha_segmentation = transparent_corners >= sum(map(len, corner_indices)) * 0.75

    if alpha_segmentation:
        preliminary = [int(px[3] >= 180) for px in pixels]
        mask_source = "alpha"
        spread = 0.
    else:
        corner_centres = [
            tuple(median(pixels[i][channel] for i in idx) for channel in range(3))
            for idx in corner_indices
        ]
        spread = max(_dist(corner_centres[i], corner_centres[j])
                     for i in range(4) for j in range(i))
        if spread > BG_SPREAD_LIMIT:
            return _indeterminate("nonuniform_background")
        background = tuple(median(c[channel] for c in corner_centres)
                           for channel in range(3))
        separation = 29 + spread * 0.6
        preliminary = [
            int(_dist(px[:3], background) > separation) for px in pixels
        ]
        mask_source = "corner_colour_contrast"

    mask_img = Image.new("L", (tw, th))
    mask_img.putdata([255 * v for v in preliminary])
    mask = [v > 127 for v in
            mask_img.filter(ImageFilter.MedianFilter(size=3)).getdata()]
    active = sum(mask)
    if not (0.07 <= active / (tw * th) <= 0.91):
        return _indeterminate("foreground_area_unsupported", mode=mask_source)

    # A single dominant connected component; a crop with multiple things is
    # ambiguous. This is a candidate foreground, NOT verified segmentation.
    seen = set()
    components = []
    for seed in range(tw * th):
        if not mask[seed] or seed in seen:
            continue
        todo = deque((seed,))
        seen.add(seed)
        comp = []
        while todo:
            at = todo.popleft()
            comp.append(at)
            x, y = at % tw, at // tw
            for nx, ny in ((x - 1, y), (x + 1, y),
                           (x, y - 1), (x, y + 1)):
                ni = ny * tw + nx
                if (0 <= nx < tw and 0 <= ny < th
                        and mask[ni] and ni not in seen):
                    seen.add(ni)
                    todo.append(ni)
        components.append(comp)
    components.sort(key=len, reverse=True)
    foreground = components[0]
    if len(foreground) / active < 0.72 or len(foreground) < tw * th * 0.09:
        return _indeterminate("fragmented_or_weak_foreground",
                              mode=mask_source)

    sx, sy = [i % tw for i in foreground], [i // tw for i in foreground]
    xmin, xmax, ymin, ymax = min(sx), max(sx), min(sy), max(sy)
    centre_x, centre_y = sum(sx) / len(sx), sum(sy) / len(sy)
    if abs(centre_x / tw - 0.5) > 0.32 or abs(centre_y / th - 0.5) > 0.32:
        return _indeterminate("offcentre_foreground", mode=mask_source)

    bounds_width, bounds_height = xmax - xmin + 1, ymax - ymin + 1
    if min(bounds_width, bounds_height) < 9:
        return _indeterminate("thin_unreliable_foreground", mode=mask_source)
    occupancy = len(foreground) / (bounds_width * bounds_height)
    aspect = bounds_width / bounds_height
    binary = set(foreground)
    patch_w, patch_h = max(2, bounds_width // 6), max(2, bounds_height // 6)
    corners_filled = [
        sum(y * tw + x in binary for y in range(cy, cy + patch_h)
            for x in range(cx, cx + patch_w)) / (patch_w * patch_h)
        for cx, cy in (
            (xmin, ymin), (xmax - patch_w + 1, ymin),
            (xmin, ymax - patch_h + 1),
            (xmax - patch_w + 1, ymax - patch_h + 1),
        )
    ]
    corner_mean = sum(corners_filled) / 4
    edges = (
        sum(y * tw in binary for y in range(th)) / th,
        sum(y * tw + tw - 1 in binary for y in range(th)) / th,
        sum(x in binary for x in range(tw)) / tw,
        sum((th - 1) * tw + x in binary for x in range(tw)) / tw,
    )
    cropped_partial = max(edges) > 0.20
    shape = "indeterminee"
    if not cropped_partial:
        if 0.79 <= aspect <= 1.27 and 0.63 <= occupancy <= 0.87 and corner_mean < 0.24:
            shape = "ronde_probable"
        elif occupancy >= 0.90 and corner_mean >= 0.58:
            shape = "rectangulaire_probable"
        elif aspect > 1.90 or aspect < 0.52:
            shape = "allongee_probable"

    colours = Counter(_colour(pixels[i][:3]) for i in foreground)
    ordered = sorted(colours.items(), key=lambda pair: (-pair[1], pair[0]))
    dominant = [
        {"colour": name, "fraction": round(n / len(foreground), 3)}
        for name, n in ordered if n / len(foreground) >= 0.16
    ][:3]
    if not dominant:
        return _indeterminate("no_stable_colour", mode=mask_source)
    return {
        "status": "foreground_candidate",
        "reason": "partial_or_ambiguous_outline" if shape == "indeterminee"
                  else "approximate_shape_only",
        "mask_source": mask_source,
        "dominant_colours": dominant,
        "shape": shape,
        "geometry": {
            "aspect_ratio": round(aspect, 3),
            "foreground_occupancy": round(occupancy, 3),
            "foreground_fraction_of_roi": round(len(foreground) / (tw * th), 3),
            "corner_occupancy": round(corner_mean, 3),
            "cutoff_by_roi": cropped_partial,
            "resized_roi_pixels": [tw, th],
        },
        "object_category": "unknown",
    }
