"""PER-OI-V7-V2-SRC-0: prospective metadata-only 42-photo pool with 288+COCO identity exclusions.

The stopped V1 roster is never altered or benchmarked. A *new* seeded source
selection excludes 288 previously inferred Open Images photos BEFORE sampling.
All source bytes are transient official CSV / pinned COCO JSON: NO JPEG, ONNX,
motor commands, SQLite, author, URL or photo ID in output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs

from experiments.per_oi_v7_source_inventory import (
    _file, _rows, _md5, _HEX_ID, PHOTO_LICENSES, OpenImagesSourceStop,
)
from experiments.cata2d_openimages_bbox_public import _load_sources
from experiments.per_oi_w1_openimages_stress import choose_cases
from microduck_companion.cata2c_openimages_human_labels import (
    SOURCE_SHA256, select_human_verified_cases,
)

SEED = "kwipi-per-oi-v7-v2-exclude-288-v1-20261104"
TARGETS = ("Tennis ball", "Book", "Bottle", "Chair", "Cat", "Dog", "Person")
PER_TARGET = 6
EXPECTED_TOTAL = 42
W1_SHA = "6954c9a0136d262a01eeba44b1da35319cf5323d270c73bc306cfd7f5f33179a"
EXPECTED_SHA = {
    "classes": "1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9",
    "images": "ed93a0e121fe345effdfc7359b848dbc64a1ff6778c8c73563157cb500b33a17",
    "human": "92ddbdfceb3626e044df5e89100b24f6c22a79c1888a4bddd00a6f231d86d56a",
    "boxes": "d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2",
    "coco": "e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f",
}
LIMITS = {"classes": 1_000_000, "images": 40_000_000,
          "human": 55_000_000, "boxes": 180_000_000, "coco": 35_000_000}
COCO_VAL_IMAGES = 5000
_SUFFIX = re.compile(r"^([0-9]{5,})_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)?\.(?:jpg|jpeg|png)\Z", re.I)
_LANDING = re.compile(r"^/photos/[^/]+/([0-9]{5,})(?:/|$)")


def flickr_id(uri: str) -> str | None:
    """Return stable Flickr photo ID only from well-known source URL forms."""
    if not isinstance(uri, str):
        return None
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return None
    if parsed.scheme not in ("https", "http") or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower()
    if host == "staticflickr.com" or host.endswith(".staticflickr.com"):
        file_name = parsed.path.rsplit("/", 1)[-1]
        m = _SUFFIX.fullmatch(file_name)
        return m.group(1) if m else None
    if host == "flickr.com" or host.endswith(".flickr.com"):
        m = _LANDING.fullmatch(parsed.path)
        if m:
            return m.group(1)
        if parsed.path == "/photo.gne":
            values = parse_qs(parsed.query).get("id", [])
            if len(values)==1 and re.fullmatch(r"[0-9]{5,}",values[0]):
                return values[0]
    return None


def coco_val_flickr_ids(path: Path, *, expected: int = COCO_VAL_IMAGES):
    """Read ONLY COCO validation annotations; do not treat COCO ImageID as Flickr ID."""
    try:
        source=json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError,ValueError,OSError) as exc:
        raise OpenImagesSourceStop("STOP_COCO: unreadable pinned annotations") from exc
    images=source.get("images") if isinstance(source,dict) else None
    if not isinstance(images,list) or len(images)!=expected:
        raise OpenImagesSourceStop("STOP_COCO: unexpected val images cardinality")
    used=set()
    ids=set()
    unparsed=0
    for img in images:
        if not isinstance(img,dict) or type(img.get("id")) is not int:
            raise OpenImagesSourceStop("STOP_COCO: invalid COCO image entry")
        if img["id"] in ids:
            raise OpenImagesSourceStop("STOP_COCO: duplicate COCO ID")
        ids.add(img["id"])
        p=flickr_id(img.get("flickr_url",""))
        if p is None:
            unparsed+=1
        else:
            used.add(p)
    return used,unparsed


def _history_ids(classes: Path, images: Path, human: Path, boxes: Path):
    """Reuse old real source-only historical selectors; never infer again."""
    a2d,_,_=_load_sources(classes,images,human,boxes)
    c,i,h,b=(p.read_bytes() for p in (classes,images,human,boxes))
    a2c=select_human_verified_cases(c,i,h)
    a2c_ids=frozenset(x.image_id for x in a2c)
    a2d_ids=frozenset(x.image_id for x in a2d)
    if len(a2c_ids)!=48 or len(a2d_ids)!=192 or len(a2c_ids|a2d_ids)!=240:
        raise OpenImagesSourceStop("STOP_HISTORY: old 240 source not reconstructed")
    w1=choose_cases(c,i,h,b,excluded_ids=a2c_ids|a2d_ids)
    digest=sha256("|".join(
        f"{x.image_id}/{x.category}/{int(x.present)}" for x in w1
    ).encode("ascii")).hexdigest()
    w1_ids=frozenset(x.image_id for x in w1)
    used=a2c_ids|a2d_ids|w1_ids
    if digest!=W1_SHA or len(w1_ids)!=48 or len(used)!=288:
        raise OpenImagesSourceStop("STOP_HISTORY: W1 digest or 288 cases drifted")
    return used


def _taxonomy(path: Path):
    mids={}
    seen=set()
    for row in _rows(path,("LabelName","DisplayName")):
        mid,name=row["LabelName"],row["DisplayName"]
        if mid in seen or not mid.startswith("/m/") or not name:
            raise OpenImagesSourceStop("STOP_SOURCE: invalid taxonomy")
        seen.add(mid)
        if name in TARGETS:
            if name in mids:
                raise OpenImagesSourceStop("STOP_SOURCE: ambiguous target")
            mids[name]=mid
    if set(mids)!=set(TARGETS):
        raise OpenImagesSourceStop("STOP_SOURCE: missing target")
    return mids


def _eligible_images(images: Path, *, old: frozenset[str], coco_flickr: set[str]):
    """Exclude old 288 IDs, all MD5 doubles, and Flickr collisions BEFORE choosing."""
    metadata={}
    md5s=defaultdict(list)
    seen=set()
    eligible_count=0
    bad_flickr=0
    collided_coco=0
    for row in _rows(images,(
        "ImageID","Subset","License","OriginalMD5","Rotation",
        "OriginalURL","OriginalLandingURL",
    )):
        ident=row["ImageID"]
        if not _HEX_ID.fullmatch(ident) or ident in seen:
            raise OpenImagesSourceStop("STOP_SOURCE: invalid or duplicate OI ID")
        seen.add(ident)
        if row["Subset"]!="validation":
            raise OpenImagesSourceStop("STOP_SOURCE: non-val image metadata")
        digest=_md5(row["OriginalMD5"])
        if (ident in old or row["License"] not in PHOTO_LICENSES
            or row["Rotation"] not in ("0","0.0") or digest is None
            or not row["OriginalURL"].startswith("https://")
            or not row["OriginalLandingURL"].startswith("https://")):
            continue
        a,b=flickr_id(row["OriginalURL"]),flickr_id(row["OriginalLandingURL"])
        if not a and not b or a and b and a!=b:
            bad_flickr+=1
            continue
        fid=a or b
        if fid in coco_flickr:
            collided_coco+=1
            continue
        eligible_count+=1
        md5s[digest].append(ident)
        metadata[ident]=digest
    if len(seen)!=41_620:
        raise OpenImagesSourceStop("STOP_SOURCE: OI validation volume drifted")
    repeated={ident for ids in md5s.values() if len(ids)>1 for ident in ids}
    return ({ident:digest for ident,digest in metadata.items() if ident not in repeated},
            {"eligible_before_md5":eligible_count,
             "removed_md5_duplicates_all_copies":len(repeated),
             "excluded_unusable_or_ambiguous_flickr":bad_flickr,
             "excluded_coco_flickr_collisions":collided_coco})


def _human_positive(human: Path, mids: dict[str,str], eligible: set[str]):
    by_mid={mid:name for name,mid in mids.items()}
    states={}
    for row in _rows(human,("ImageID","Source","LabelName","Confidence")):
        ident=row["ImageID"]
        name=by_mid.get(row["LabelName"])
        if name is None or ident not in eligible:
            continue
        if row["Source"] not in ("verification","crowdsource-verification"):
            raise OpenImagesSourceStop("STOP_SCHEMA: target vote is not human")
        raw=row["Confidence"]
        if not raw or len(raw)>12 or any(ch not in "0123456789." for ch in raw):
            raise OpenImagesSourceStop("STOP_SCHEMA: unknown vote encoding")
        try:
            value=Decimal(raw)
        except InvalidOperation as exc:
            raise OpenImagesSourceStop("STOP_SCHEMA: malformed human vote") from exc
        if not value.is_finite() or value not in (0,1):
            raise OpenImagesSourceStop("STOP_SCHEMA: nonbinary human vote")
        states.setdefault((ident,name),set()).add(int(value))
    return frozenset(key for key,val in states.items() if val=={1})


def _valid_boxes(boxes: Path, mids: dict[str,str], positive: frozenset):
    target={mid:name for name,mid in mids.items()}
    allowed=set(positive)
    found=defaultdict(int)
    for row in _rows(boxes,(
        "ImageID","LabelName","Source","Confidence","XMin","XMax",
        "YMin","YMax","IsGroupOf","IsDepiction","IsInside",
    )):
        pair=(row["ImageID"],target.get(row["LabelName"]))
        if pair not in allowed:
            continue
        if (row["Source"] not in ("xclick","activemil")
                or row["Confidence"] not in ("1","1.0")):
            raise OpenImagesSourceStop("STOP_SCHEMA: non-human target bbox")
        if any(row[k]!="0" for k in ("IsGroupOf","IsDepiction","IsInside")):
            continue
        try:
            x0,x1,y0,y1=(float(row[f]) for f in ("XMin","XMax","YMin","YMax"))
        except (TypeError,ValueError):
            continue
        if (all(math.isfinite(v) and 0<=v<=1 for v in (x0,x1,y0,y1))
                and x0<x1 and y0<y1):
            found[pair]+=1
    return found


def select_v2(boxed: dict[tuple[str,str],int], old: set[str] | frozenset[str],
              *, seed: str = SEED):
    """One deterministic prospective cohort; no adaptive resampling or predictions."""
    if type(seed) is not str or seed!=SEED:
        raise OpenImagesSourceStop("STOP_SOURCE: changed preregistered seed")
    pools={name:frozenset(ident for (ident,label),n in boxed.items()
                          if label==name and n>=1 and ident not in old)
           for name in TARGETS}
    ordered=sorted(TARGETS,key=lambda name:(len(pools[name]),TARGETS.index(name)))
    chosen=[]
    taken=set(old)
    for name in ordered:
        available=sorted(pools[name]-taken,key=lambda ident:(
            sha256(f"{SEED}/{name}/{ident}".encode("ascii")).digest(),ident))
        if len(available)<PER_TARGET:
            return (),{k:len(v) for k,v in pools.items()},name
        for ident in available[:PER_TARGET]:
            chosen.append((ident,name))
            taken.add(ident)
    if len(chosen)!=EXPECTED_TOTAL or len({i for i,_ in chosen})!=EXPECTED_TOTAL:
        raise OpenImagesSourceStop("STOP_SOURCE: incomplete or duplicate cohort")
    return tuple(chosen),{name:len(pools[name]) for name in TARGETS},None


def audit(classes: Path, images: Path, human: Path, boxes: Path, coco: Path):
    paths=dict(classes=classes,images=images,human=human,boxes=boxes,coco=coco)
    hashes={name:_file(path,LIMITS[name]) for name,path in paths.items()}
    if hashes!=EXPECTED_SHA:
        raise OpenImagesSourceStop("STOP_SOURCE: official pinned metadata SHA drift")
    historical=_history_ids(classes,images,human,boxes)
    coco_ids,unparsed=coco_val_flickr_ids(coco)
    # Non-Flickr COCO IDs mean full identity coverage cannot be claimed;
    # retain the result as a documented STOP rather than misstate zero overlap.
    mids=_taxonomy(classes)
    eligible,exclusions=_eligible_images(images,old=historical,coco_flickr=coco_ids)
    positive=_human_positive(human,mids,set(eligible))
    boxes_per_case=_valid_boxes(boxes,mids,positive)
    chosen,pool,insufficient=select_v2(boxes_per_case,historical)
    cross_coco_complete=unparsed==0
    success=bool(chosen) and cross_coco_complete and insufficient is None
    digest=(sha256("|".join(
        f"{label}/{ident}" for ident,label in chosen
    ).encode("ascii")).hexdigest() if success else None)
    return {
        "status": ("V2_GT_42_FROZEN_SOURCE_ONLY_NOT_LICENSED"
                   if success else "STOP_V2_SOURCE_NOT_QUALIFIED"),
        "selection_seed": SEED,
        "source_sha256": hashes,
        "historical_openimages_ids_excluded": len(historical),
        "coco_val_image_metadata": COCO_VAL_IMAGES,
        "coco_flickr_photo_ids_readable": COCO_VAL_IMAGES-unparsed,
        "coco_flickr_photo_ids_unknown": unparsed,
        "source_flickr_identity_checked_for_selected": success,
        "per_category_candidate_boxes": pool,
        "insufficient_category": insufficient,
        "cohort_images": len(chosen),
        "roster_sha256": digest,
        "candidate_image_filters": exclusions,
        "candidate_human_positive_with_box_count": len(boxes_per_case),
        "last_42_v1_roster_reused_as_a_selection": False,
        "historical_288_reinferred": False,
        "rights_by_original_author_verified": False,
        "cross_corpus_perceptual_duplicate_absence_verified": False,
        "real_pixels_loaded": 0,
        "model_inferences": 0,
        "robot_npu_validated": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-metadata",action="store_true")
    for k in ("classes","images","human","boxes","coco"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args(argv)
    if not a.approved_public_metadata:
        p.error("public metadata audit must be explicitly authorized")
    print(json.dumps(audit(a.classes,a.images,a.human,a.boxes,a.coco),
                     allow_nan=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
