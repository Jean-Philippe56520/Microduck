"""Cat-A2b: offline GUI for creating a *declared* blind TEST annotation review.

The already validated private Cat-A2b manifest provides ONLY opaque image IDs,
SHA-256 and geometry to the editor; original labels/boxes are deliberately NOT
passed to the GUI. This is an annotation tool, not independent truth, an ML
model, a robotics service or proof that a reviewer was actually blinded.

Privacy: no server, model, database, telemetry, files outside the approved
private dataset, or prints of image/annotation content. The local reviewer
must have consent and must honestly confirm independence before export.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import secrets

from .cata2b_private_low import (
    LowDataset, MAX_BOXES, _bounded_data, _jpeg_dimensions,
    _private_root_guard, load_private_low_dataset,
)
from .cata2b_blind_review import REVIEW_LIMIT, REVIEW_SOURCE, REVIEW_VERSION
from .cata_yolox_categories import CATEGORIES, MAX_IMAGE_BYTES
from .visual_photo_mobilenet_demo import PhotoBaselineError

CLOSED_ROLES = frozenset({"first", "second"})
VISIBILITY = frozenset({"full", "partial"})
VIEW_MAX_WIDTH = 960
VIEW_MAX_HEIGHT = 650


@dataclass(frozen=True)
class BlindImage:
    """The only per-image metadata visible to the editor; no primary boxes."""

    sample_id: str
    image_sha256: str
    width: int
    height: int


def empty_box_confirmation_prompt(uncertain: bool) -> tuple[str, str]:
    """Do not misclassify an unresolved image as a verified negative."""
    if type(uncertain) is not bool:
        raise PhotoBaselineError("uncertainty must be explicit boolean")
    if uncertain:
        return (
            "Image incertaine",
            "Aucune boite certaine : confirmer une image INDETERMINEE, "
            "sans affirmer l'absence de toutes les cibles ?",
        )
    return (
        "Relecture sans cible",
        "Aucune boite dessinee : confirmer l'absence de "
        "toutes les categories cibles dans cette photo ?",
    )


class BlindAnnotationSession:
    """In-memory draft from a validated local dataset, one reviewer at a time."""

    def __init__(self, dataset: LowDataset, *, role: str):
        if not isinstance(dataset, LowDataset):
            raise TypeError("validated Cat-A2b dataset required")
        if type(role) is not str or role not in CLOSED_ROLES:
            raise ValueError("review role must be first or second")
        self.root = dataset.root
        self.role = role
        # Do not retain LowDataset: its historical V3 labels are NOT blind.
        self.images = tuple(
            BlindImage(s.sample_id, s.image_sha256, s.width, s.height)
            for s in dataset.test()
        )
        if not self.images:
            raise PhotoBaselineError("no TEST images for blind review")
        self._by_id = {s.sample_id: s for s in self.images}
        if len(self._by_id) != len(self.images):
            raise PhotoBaselineError("duplicate private TEST identifiers")
        self._boxes: dict[str, list[dict]] = {
            s.sample_id: [] for s in self.images
        }
        self._uncertain: set[str] = set()
        self._confirmed: set[str] = set()
        self._exported = False
        self.review_session_id = "g-" + secrets.token_hex(8)

    @property
    def reviewed_count(self) -> int:
        return len(self._confirmed)

    def _sample(self, sample_id: str) -> BlindImage:
        if type(sample_id) is not str or sample_id not in self._by_id:
            raise PhotoBaselineError("unknown private review item")
        return self._by_id[sample_id]

    def image_bytes(self, sample_id: str) -> bytes:
        """Read one reviewed-size, SHA-pinned JPEG; never use primary boxes."""
        sample = self._sample(sample_id)
        images = self.root / "images"
        if images.is_symlink() or not images.is_dir():
            raise PhotoBaselineError("unsafe local images directory")
        blob = _bounded_data(
            images / (sample.sample_id + ".jpg"), MAX_IMAGE_BYTES
        )
        if (sha256(blob).hexdigest() != sample.image_sha256
                or _jpeg_dimensions(blob) != (sample.width, sample.height)):
            raise PhotoBaselineError("private JPEG changed since manifest validation")
        return blob

    def boxes(self, sample_id: str) -> tuple[dict, ...]:
        """Return copies of THIS draft only, never primary ground truth."""
        self._sample(sample_id)
        return tuple({
            "category": row["category"],
            "xyxy": row["xyxy"].copy(),
            "visibility": row["visibility"],
        } for row in self._boxes[sample_id])

    def is_uncertain(self, sample_id: str) -> bool:
        self._sample(sample_id)
        return sample_id in self._uncertain

    def is_confirmed(self, sample_id: str) -> bool:
        self._sample(sample_id)
        return sample_id in self._confirmed

    def add_box(
        self, sample_id: str, *,
        category: str, visibility: str,
        xyxy: tuple[int, int, int, int],
    ) -> None:
        if self._exported:
            raise PhotoBaselineError("review already exported")
        sample = self._sample(sample_id)
        if (type(category) is not str or category not in CATEGORIES
                or type(visibility) is not str or visibility not in VISIBILITY
                or type(xyxy) is not tuple or len(xyxy) != 4
                or any(type(v) is not int for v in xyxy)):
            raise PhotoBaselineError("invalid blind annotation class/visibility/box")
        x0, y0, x1, y1 = xyxy
        if not (0 <= x0 < x1 <= sample.width
                and 0 <= y0 < y1 <= sample.height):
            raise PhotoBaselineError("annotation outside original JPEG geometry")
        if len(self._boxes[sample_id]) >= MAX_BOXES:
            raise PhotoBaselineError("private annotation box limit exceeded")
        self._boxes[sample_id].append({
            "category": category, "visibility": visibility,
            "xyxy": [x0, y0, x1, y1],
        })
        self._confirmed.discard(sample_id)

    def undo_last_box(self, sample_id: str) -> None:
        if self._exported:
            raise PhotoBaselineError("review already exported")
        self._sample(sample_id)
        if self._boxes[sample_id]:
            self._boxes[sample_id].pop()
        self._confirmed.discard(sample_id)

    def set_uncertain(self, sample_id: str, value: bool) -> None:
        if self._exported:
            raise PhotoBaselineError("review already exported")
        self._sample(sample_id)
        if type(value) is not bool:
            raise PhotoBaselineError("uncertainty must be explicit boolean")
        if value:
            self._uncertain.add(sample_id)
        else:
            self._uncertain.discard(sample_id)
        self._confirmed.discard(sample_id)

    def confirm_image(self, sample_id: str, *,
                      all_targets_reviewed: bool) -> None:
        if self._exported:
            raise PhotoBaselineError("review already exported")
        self._sample(sample_id)
        if all_targets_reviewed is not True:
            raise PhotoBaselineError("reviewer must confirm complete image inspection")
        self._confirmed.add(sample_id)

    def export(
        self, *, blind_to_model_predictions_declared: bool,
        manual_independent_review_declared: bool,
    ) -> Path:
        """Write exactly one private, non-overwriting, owner-only final JSON.

        Declarations are NOT independently authenticated. Incomplete images,
        uncertainty and disagreement do not silently become ground truth.
        """
        if self._exported:
            raise PhotoBaselineError("review already exported")
        if (blind_to_model_predictions_declared is not True
                or manual_independent_review_declared is not True):
            raise PermissionError("explicit honest blind/manual declarations required")
        if len(self._confirmed) != len(self.images):
            raise PhotoBaselineError("all TEST images must be individually reviewed")

        _private_root_guard(self.root)
        reviews = self.root / "reviews"
        if reviews.is_symlink():
            raise PhotoBaselineError("linked private review directory rejected")
        if not reviews.exists():
            reviews.mkdir(mode=0o700)
        if not reviews.is_dir():
            raise PhotoBaselineError("private reviews directory required")
        records = [
            {
                "sample_id": sample.sample_id,
                "image_sha256": sample.image_sha256,
                "boxes": self.boxes(sample.sample_id),
                "all_targets_reviewed": True,
                "uncertain": sample.sample_id in self._uncertain,
            }
            for sample in self.images
        ]
        content = json.dumps({
            "schema_version": REVIEW_VERSION,
            "source": REVIEW_SOURCE,
            "role": self.role,
            "review_session_id": self.review_session_id,
            "blind_to_model_predictions_declared": True,
            "manual_independent_review_declared": True,
            "samples": records,
        }, allow_nan=False, sort_keys=True).encode("utf-8")
        if not 1 <= len(content) <= REVIEW_LIMIT:
            raise PhotoBaselineError("private review JSON size limit exceeded")
        name = "r-" + secrets.token_hex(8) + ".json"
        # dir_fd + O_NOFOLLOW avoid rewriting existing reviews or following
        # a final-path symlink. Linux/WSL only; the GUI is not an OEM service.
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory_fd = os.open(reviews, flags)
        try:
            file_fd = os.open(
                name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600, dir_fd=directory_fd,
            )
            try:
                with os.fdopen(file_fd, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                os.unlink(name, dir_fd=directory_fd)
                raise
        finally:
            os.close(directory_fd)
        self._exported = True
        return reviews / name


def run_gui(session: BlindAnnotationSession) -> None:
    """Small local tkinter canvas; images never leave the WSL/Ubuntu process."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
        from PIL import Image, ImageTk
    except ImportError as exc:
        raise RuntimeError(
            "local GUI requires Tk and Pillow on Ubuntu/WSL; no server used"
        ) from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError("a local graphical desktop (for example WSLg) is required") from exc
    root.title("Kwipi - contre-annotation privee (sans predictions)")
    root.geometry("1100x900")
    root.minsize(700, 570)
    header = ttk.Label(
        root, text="Relecture sans YOLOX/V3 - humain independant requis",
    )
    header.pack(pady=5)
    status = ttk.Label(root, text="")
    status.pack()
    canvas = tk.Canvas(
        root, bg="#202020", cursor="crosshair", highlightthickness=0
    )
    canvas.pack(pady=6)
    controls = ttk.Frame(root)
    controls.pack(fill="x", padx=10)
    category = tk.StringVar(value="")  # no category assumed for an unseen scene
    visibility = tk.StringVar(value="")  # reviewer must choose explicitly
    uncertain = tk.BooleanVar(value=False)
    model_blind = tk.BooleanVar(value=False)
    manual_independent = tk.BooleanVar(value=False)
    ttk.Label(controls, text="Categorie").grid(row=0, column=0)
    names = ttk.Combobox(
        controls, textvariable=category, values=tuple(CATEGORIES),
        state="readonly", width=14,
    )
    names.grid(row=0, column=1)
    ttk.Label(controls, text="Visibilite").grid(row=0, column=2)
    ttk.Combobox(
        controls, textvariable=visibility, values=("full", "partial"),
        state="readonly", width=12,
    ).grid(row=0, column=3)
    check_uncertain = ttk.Checkbutton(
        controls, text="Image incertaine", variable=uncertain
    )
    check_uncertain.grid(row=0, column=4, padx=8)
    current = 0
    scale = 1.0
    image_ref = None
    start = None
    preview_id = None

    def display():
        nonlocal scale, image_ref, start, preview_id
        start = None
        preview_id = None
        sample = session.images[current]
        blob = session.image_bytes(sample.sample_id)
        with Image.open(BytesIO(blob)) as original:
            scale = min(
                VIEW_MAX_WIDTH / sample.width,
                VIEW_MAX_HEIGHT / sample.height, 4.0,
            )
            w = max(1, round(sample.width * scale))
            h = max(1, round(sample.height * scale))
            im = original.resize((w, h), Image.Resampling.BILINEAR)
            image_ref = ImageTk.PhotoImage(im)
        canvas.configure(width=w, height=h)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=image_ref)
        for item in session.boxes(sample.sample_id):
            x0, y0, x1, y1 = item["xyxy"]
            canvas.create_rectangle(
                x0 * scale, y0 * scale, x1 * scale, y1 * scale,
                outline="#54d6ac", width=2,
            )
            canvas.create_text(
                x0 * scale + 3, y0 * scale + 3, anchor="nw",
                text=item["category"] + " / " + item["visibility"],
                fill="#ffffff",
            )
        uncertain.set(session.is_uncertain(sample.sample_id))
        status.configure(
            text=(
                f"Photo TEST {current + 1}/{len(session.images)}  |  "
                f"confirmees : {session.reviewed_count}/{len(session.images)}  |  "
                f"boites : {len(session.boxes(sample.sample_id))}  |  "
                f"{'VALIDEE' if session.is_confirmed(sample.sample_id) else 'A REVOIR'}"
            )
        )

    def on_uncertain(*_):
        sample = session.images[current]
        session.set_uncertain(sample.sample_id, uncertain.get())
        display()

    uncertain.trace_add("write", lambda *_: None)
    # Handler only on a user click; display() updates the bound variable
    # without creating a self-triggering callback.
    check_uncertain.configure(command=on_uncertain)

    def press(event):
        nonlocal start, preview_id
        start = (event.x, event.y)
        if preview_id is not None:
            canvas.delete(preview_id)
            preview_id = None

    def move(event):
        nonlocal preview_id
        if start is None:
            return
        if preview_id is not None:
            canvas.delete(preview_id)
        preview_id = canvas.create_rectangle(
            start[0], start[1], event.x, event.y,
            outline="#ffd461", dash=(4, 3),
        )

    def release(event):
        nonlocal start, preview_id
        if start is None:
            return
        sample = session.images[current]
        x_start, y_start = start
        start = None
        if preview_id is not None:
            canvas.delete(preview_id)
            preview_id = None
        ax = max(0, min(sample.width, math.floor(min(x_start, event.x) / scale)))
        ay = max(0, min(sample.height, math.floor(min(y_start, event.y) / scale)))
        bx = max(0, min(sample.width, math.ceil(max(x_start, event.x) / scale)))
        by = max(0, min(sample.height, math.ceil(max(y_start, event.y) / scale)))
        if bx <= ax or by <= ay:
            return
        if category.get() not in CATEGORIES or visibility.get() not in VISIBILITY:
            messagebox.showerror(
                "Choix requis", "Choisir categorie et visibilite avant de tracer."
            )
            display()
            return
        try:
            session.add_box(
                sample.sample_id, category=category.get(),
                visibility=visibility.get(), xyxy=(ax, ay, bx, by),
            )
        except PhotoBaselineError as exc:
            messagebox.showerror("Annotation refusee", str(exc))
        display()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", move)
    canvas.bind("<ButtonRelease-1>", release)

    buttons = ttk.Frame(root)
    buttons.pack(pady=6)

    def next_image(delta):
        nonlocal current
        current = max(0, min(len(session.images) - 1, current + delta))
        display()

    def undo():
        session.undo_last_box(session.images[current].sample_id)
        display()

    def confirm():
        sample = session.images[current]
        if not session.boxes(sample.sample_id):
            title, question = empty_box_confirmation_prompt(
                session.is_uncertain(sample.sample_id)
            )
            if not messagebox.askyesno(title, question):
                return
        session.confirm_image(sample.sample_id, all_targets_reviewed=True)
        if current + 1 < len(session.images):
            next_image(1)
        else:
            display()

    ttk.Button(buttons, text="Precedente", command=lambda: next_image(-1)).pack(side="left")
    ttk.Button(buttons, text="Retirer derniere boite", command=undo).pack(side="left")
    ttk.Button(buttons, text="Confirmer cette image", command=confirm).pack(side="left")
    ttk.Button(buttons, text="Suivante", command=lambda: next_image(1)).pack(side="left")
    ttk.Label(root, text=(
        "Tracez une boite a la souris. Ne regardez ni predictions YOLOX ni V3. "
        "Une personne sur un ecran n'est pas une presence physique prouvee."
    ), wraplength=900).pack(pady=7)
    ttk.Checkbutton(
        root, text="Je n'ai pas consulte les predictions ni annotations V3",
        variable=model_blind,
    ).pack(anchor="w", padx=16)
    ttk.Checkbutton(
        root, text="Cette annotation est une nouvelle revue manuelle independante",
        variable=manual_independent,
    ).pack(anchor="w", padx=16)

    def finish():
        try:
            output = session.export(
                blind_to_model_predictions_declared=model_blind.get(),
                manual_independent_review_declared=manual_independent.get(),
            )
        except (PhotoBaselineError, PermissionError, OSError) as exc:
            messagebox.showerror("Relecture non exportee", str(exc))
            return
        messagebox.showinfo(
            "Export local termine",
            "Une revue a ete enregistree localement. "
            "Elle n'est pas une verite terrain certifiee.\n" + str(output),
        )
        root.destroy()

    ttk.Button(root, text="Exporter cette revue privee", command=finish).pack(pady=8)
    display()
    root.mainloop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--role", choices=("first", "second"), required=True)
    parser.add_argument("--approved-private-local-media", action="store_true")
    args = parser.parse_args(argv)
    if not args.approved_private_local_media:
        parser.error("explicit local media access and consent required")
    data = load_private_low_dataset(args.manifest)
    session = BlindAnnotationSession(data, role=args.role)
    run_gui(session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
