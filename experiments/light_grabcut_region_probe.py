"""Host-only GrabCut crop experiment; not a detector or an OEM integration.

The caller supplies a box. COCO polygon GT and YOLOX scores are entirely
outside this module; labels are not consulted to segment a region.
"""
from __future__ import annotations

import math
import time


def _valid_box(box, width, height):
    if (not isinstance(box, (tuple, list)) or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in box)):
        raise ValueError("invalid rectangle")
    x1, y1, x2, y2 = map(float, box)
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("rectangle outside image")
    return x1, y1, x2, y2


def describe_mask(rgb, mask):
    """Visible color and rough geometric shape, never a semantic class."""
    import cv2
    import numpy as np
    if (not isinstance(rgb, np.ndarray) or rgb.ndim != 3
            or rgb.shape[-1] != 3 or rgb.dtype != np.uint8
            or not isinstance(mask, np.ndarray) or mask.dtype != np.uint8
            or mask.shape != rgb.shape[:2]):
        raise ValueError("invalid image/mask")
    binary = (mask > 0).astype(np.uint8)
    if int(binary.sum()) < 40:
        return {"status": "indeterminate", "reason": "too_few_pixels",
                "shape": "unknown", "colors": []}
    cnts, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return {"status": "indeterminate", "reason": "no_contour",
                "shape": "unknown", "colors": []}
    cont = max(cnts, key=cv2.contourArea)
    perimeter = cv2.arcLength(cont, True)
    area = cv2.contourArea(cont)
    x, y, w, h = cv2.boundingRect(cont)
    circularity = 4 * math.pi * area / perimeter ** 2 if perimeter else 0.0
    aspect = w / max(1, h)
    hull_area = cv2.contourArea(cv2.convexHull(cont))
    solidity = area / hull_area if hull_area > 0 else 0
    cut = x <= 1 or y <= 1 or x + w >= rgb.shape[1] - 1 or y + h >= rgb.shape[0] - 1
    shape = "unknown"
    if not cut and 0.78 <= aspect <= 1.28 and circularity >= 0.69 and solidity >= .89:
        shape = "round_like"
    elif not cut and (aspect >= 1.8 or aspect <= 0.55):
        shape = "elongated_like"
    elif not cut and 0.81 <= aspect <= 1.23 and solidity >= 0.91 and circularity >= .56:
        shape = "compact_like"
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    pixels = hsv[binary > 0]
    sat = pixels[:, 1]
    val = pixels[:, 2]
    bins = {
        "black": (val < 50),
        "white": (val > 201) & (sat < 42),
        "gray": (val >= 50) & (val <= 201) & (sat < 42),
        "red": ((pixels[:, 0] < 9) | (pixels[:, 0] >= 171)) & (sat >= 42) & (val >= 50),
        "orange": (pixels[:, 0] >= 9) & (pixels[:, 0] < 23) & (sat >= 42) & (val >= 50),
        "yellow": (pixels[:, 0] >= 23) & (pixels[:, 0] < 37) & (sat >= 42) & (val >= 50),
        "yellow_green": (pixels[:, 0] >= 37) & (pixels[:, 0] < 52) & (sat >= 42) & (val >= 50),
        "green": (pixels[:, 0] >= 52) & (pixels[:, 0] < 85) & (sat >= 42) & (val >= 50),
        "cyan": (pixels[:, 0] >= 85) & (pixels[:, 0] < 102) & (sat >= 42) & (val >= 50),
        "blue": (pixels[:, 0] >= 102) & (pixels[:, 0] < 130) & (sat >= 42) & (val >= 50),
        "violet": (pixels[:, 0] >= 130) & (pixels[:, 0] < 150) & (sat >= 42) & (val >= 50),
        "pink": (pixels[:, 0] >= 150) & (pixels[:, 0] < 171) & (sat >= 42) & (val >= 50),
    }
    counts = sorted(((int(m.sum()), name) for name, m in bins.items()),
                    key=lambda pair: (-pair[0], pair[1]))
    colors = [
        {"name": name, "fraction": round(n / len(pixels), 3)}
        for n, name in counts[:3] if n / len(pixels) >= .14
    ]
    return {
        "status": "candidate_only",
        "shape": shape,
        "colors": colors,
        "geometry": {
            "aspect_ratio": round(aspect, 3),
            "circularity": round(circularity, 3),
            "solidity": round(solidity, 3),
            "cut_by_frame": cut,
            "area_pixels": int(binary.sum()),
        },
        "not_an_object_identity_or_category": True,
    }


def grabcut_rectangle(rgb, box, *, longest_side=640):
    """One ROI, 144 px cropped input, ONE GrabCut iteration, no new model.

    Same full-frame 640 px scale as historic experiment for comparable GT
    masks. Only the cropped segmenter input shrinks. Input box is an
    unverified proposal; output is never permission for motion or identity.
    """
    import cv2
    import numpy as np
    if (not isinstance(rgb, np.ndarray) or rgb.ndim != 3 or
            rgb.shape[-1] != 3 or rgb.dtype != np.uint8 or
            min(rgb.shape[:2]) < 32 or max(rgb.shape[:2]) > 4096):
        raise ValueError("bounded uint8 RGB required")
    if longest_side != 640:
        raise ValueError("pinned host input geometry")
    h0, w0 = rgb.shape[:2]
    orig = _valid_box(box, w0, h0)
    start = time.perf_counter()
    scale = min(1., 640 / max(w0, h0))
    if scale < 1:
        small = cv2.resize(rgb, (max(2, round(w0 * scale)),
                                 max(2, round(h0 * scale))),
                           interpolation=cv2.INTER_AREA)
    else:
        small = rgb
    h, w = small.shape[:2]
    x1, y1, x2, y2 = [
        v * (w / w0 if i % 2 == 0 else h / h0)
        for i, v in enumerate(orig)
    ]
    if min(x2-x1, y2-y1) < 9:
        return {"status": "indeterminate", "reason": "too_small"}, None, small
    pad = max(8, round(max(x2-x1, y2-y1) * .25))
    l, t = max(0, math.floor(x1)-pad), max(0, math.floor(y1)-pad)
    r, b = min(w, math.ceil(x2)+pad), min(h, math.ceil(y2)+pad)
    patch = np.ascontiguousarray(small[t:b, l:r])
    ph, pw = patch.shape[:2]
    factor = min(1., 144 / max(ph, pw))
    sw, sh = max(2, round(pw * factor)), max(2, round(ph * factor))
    cropped = (cv2.resize(patch, (sw, sh), interpolation=cv2.INTER_AREA)
               if factor < 1 else patch)
    fx, fy = sw / pw, sh / ph
    left, top = max(1, round((x1-l)*fx)), max(1, round((y1-t)*fy))
    right = min(sw-1, round((x2-l)*fx))
    bottom = min(sh-1, round((y2-t)*fy))
    if (min(right-left, bottom-top) < 6 or
            min(left, top, sw-right, sh-bottom) < 2):
        return {"status": "indeterminate", "reason": "no_margin"}, None, small
    labels = np.zeros((sh, sw), np.uint8)
    bg = np.zeros((1, 65), np.float64)
    fg = np.zeros((1, 65), np.float64)
    try:
        cv2.setRNGSeed(0)
        cv2.grabCut(cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR),
                    labels, (left, top, right-left, bottom-top),
                    bg, fg, 1, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return {"status": "indeterminate", "reason": "grabcut_failed"}, None, small
    binary = np.where(
        (labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD),
        255, 0,
    ).astype(np.uint8)
    restored = cv2.resize(binary, (pw, ph), interpolation=cv2.INTER_NEAREST)
    full = np.zeros((h, w), np.uint8)
    full[t:b, l:r] = restored
    elapsed_ms = (time.perf_counter()-start)*1000.
    if int(np.count_nonzero(full)) < 40:
        return {"status": "indeterminate", "reason": "no_foreground",
                "grabcut_ms": round(elapsed_ms, 3)}, full, small
    desc = describe_mask(small, full)
    return {
        "status": "candidate", "grabcut_ms": round((time.perf_counter()-start)*1000, 3),
        "descriptor": desc, "segmentation_crop_max_side_px": 144,
        "iterations": 1,
    }, full, small


def mask_iou(a, b):
    import numpy as np
    aa, bb = np.asarray(a) > 0, np.asarray(b) > 0
    if aa.shape != bb.shape or aa.size == 0:
        raise ValueError("incompatible masks")
    union = int(np.count_nonzero(aa | bb))
    return (int(np.count_nonzero(aa & bb))/union) if union else None
