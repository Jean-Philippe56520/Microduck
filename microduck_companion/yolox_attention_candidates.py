"""Host-only candidate regions from the existing pinned COCO YOLOX head.

Keeps up to 3 spatial proposals for possible attention. This does not
identify unknown objects, confirm object presence, segment pixels, inspect
colour, or create action authorization. It never runs inference, opens a
camera, contacts Qwen, writes memories, or commands robotd.
A proposal is an *untrusted* 80-class COCO detection hypothesis.
"""
from __future__ import annotations

from .cata_yolox_categories import MIN_SCORE, SIZE, _grid

MAX_PRE_NMS = 160
NMS_IOU = 0.50
PROPOSAL_CAPS = (1, 3, 5)

def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    overlap = max(0, min(ax2,bx2)-max(ax1,bx1))*max(
        0, min(ay2,by2)-max(ay1,by1))
    union = (ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-overlap
    return overlap/union if union > 0 else 0.


def decode_candidates(raw, *, width, height, max_results=5):
    """Fixed .25 YOLOX joint score and existing 0.50 class-agnostic NMS.

    These candidates are hypotheses amongst the 80 pretrained COCO classes,
    NOT a learned open-set or category-free object detector.
    """
    import numpy as np
    if (type(width) is not int or type(height) is not int
            or not 32 <= width <= 4096 or not 32 <= height <= 4096
            or type(max_results) is not int or max_results not in PROPOSAL_CAPS):
        raise ValueError("invalid geometry or cap")
    arr = np.asarray(raw)
    if (arr.shape != (1,3549,85)
            or not np.issubdtype(arr.dtype, np.floating)
            or not np.isfinite(arr).all()
            or np.any(arr[...,4:] < 0) or np.any(arr[...,4:] > 1)):
        raise ValueError("invalid YOLOX output")
    a = arr[0]
    confidence_joint = a[:,4,None]*a[:,5:]
    best_classes = np.argmax(confidence_joint,axis=1)
    scores = confidence_joint[np.arange(a.shape[0]),best_classes]
    cand = np.flatnonzero(scores >= MIN_SCORE)
    order = sorted(cand.tolist(), key=lambda k:(-float(scores[k]),k))[:MAX_PRE_NMS]
    grid, stride = _grid()
    ratio = min(SIZE/width,SIZE/height)
    rw, rh = max(1,round(width*ratio)),max(1,round(height*ratio))
    xscale, yscale = width/rw,height/rh
    accepted = []
    for k in order:
        with np.errstate(over="ignore",invalid="ignore"):
            centre = (a[k,:2]+grid[k])*stride[k]
            span = np.exp(a[k,2:4])*stride[k]
        if not np.isfinite(centre).all() or not np.isfinite(span).all():
            continue
        box = (
            float(np.clip((centre[0]-span[0]/2)*xscale,0,width)),
            float(np.clip((centre[1]-span[1]/2)*yscale,0,height)),
            float(np.clip((centre[0]+span[0]/2)*xscale,0,width)),
            float(np.clip((centre[1]+span[1]/2)*yscale,0,height)),
        )
        if min(box[2]-box[0],box[3]-box[1]) < 9:
            continue
        if any(_iou(box,old["xyxy"]) > NMS_IOU for old in accepted):
            continue
        accepted.append({
            "xyxy": box,
            "score": round(float(scores[k]),6),
            "untrusted_coco_class_index": int(best_classes[k]),
        })
        if len(accepted) >= max_results:
            break
    return accepted

