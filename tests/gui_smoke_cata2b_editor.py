"""Real Tk/Canvas smoke with a virtual Linux display and synthetic JPEGs only.

Run explicitly with:
    xvfb-run -a python -m unittest discover -s tests \
        -p 'gui_smoke_cata2b_editor.py' -v

No Tk window during normal unittest discovery, no original private media,
no YOLOX, Qwen, robotd, sqlite, network or motor action. Synthetic fixture
interaction is NOT WSLg/OEM/real-annotator validation.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.cata2b_blind_editor import (
    BlindAnnotationSession, run_gui,
)
from microduck_companion.cata2b_blind_review import _read_review
from microduck_companion.cata2b_private_low import LowDataset, LowSample


class TkVirtualDisplaySmoke(unittest.TestCase):
    def test_real_tk_canvas_drag_confirmation_and_private_export(self):
        if not os.environ.get("DISPLAY"):
            self.fail("virtual DISPLAY required; never silently skip GUI coverage")

        import tkinter as tk
        from tkinter import messagebox, ttk
        from PIL import Image, ImageTk

        # This is generated paint, not a photo of a person, room or robot.
        with tempfile.TemporaryDirectory() as dirname:
            root_dir = Path(dirname)
            (root_dir / "images").mkdir()
            samples = []
            for i in (3, 4):
                sid = f"s-{i:016x}"
                buff = BytesIO()
                Image.new("RGB", (80, 120), (i * 20, 100, 170)).save(
                    buff, format="JPEG",
                )
                photo = buff.getvalue()
                (root_dir / "images" / (sid + ".jpg")).write_bytes(photo)
                # Existing V3 label is intentionally misleading and must
                # never reach the UI; the canvas starts with no boxes.
                samples.append(LowSample(
                    sid, f"g-{i:016x}", f"g-{i+100:016x}",
                    "test", 80, 120,
                    (Box("dog", (1., 2., 50., 60.)),) if i == 3 else (),
                    ("full",) if i == 3 else (),
                    sha256(photo).hexdigest(),
                ))
            dataset = LowDataset(
                root_dir, (), tuple(samples), "0" * 64,
            )
            session = BlindAnnotationSession(dataset, role="first")
            captured_errors = []
            reviews_shown = []
            asks = []
            constructed = tk.Tk

            def descendants(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from descendants(child)

            def drive_ui(window):
                try:
                    widgets = list(descendants(window))
                    canvas, = [w for w in widgets if isinstance(w, tk.Canvas)]
                    comboboxes = [w for w in widgets
                                  if isinstance(w, ttk.Combobox)]
                    buttons = {
                        w.cget("text"): w
                        for w in widgets if isinstance(w, ttk.Button)
                    }
                    checks = {
                        w.cget("text"): w
                        for w in widgets if isinstance(w, ttk.Checkbutton)
                    }
                    self.assertEqual(2, len(comboboxes))
                    self.assertEqual("", comboboxes[0].get())
                    self.assertEqual("", comboboxes[1].get())
                    self.assertEqual(1, len(canvas.find_all()))
                    self.assertEqual(0, session.reviewed_count)
                    self.assertFalse(session.boxes(samples[0].sample_id))

                    # Drive the actual Tk event bindings, not just the
                    # BlindAnnotationSession API already covered by unit tests.
                    comboboxes[0].set("cat")
                    comboboxes[1].set("partial")
                    window.update_idletasks()
                    self.assertTrue(canvas.winfo_ismapped())
                    self.assertTrue(canvas.bind("<ButtonPress-1>"))
                    hits = []
                    for event_name, value in (
                        ("<ButtonPress-1>", "press"),
                        ("<B1-Motion>", "drag"),
                        ("<ButtonRelease-1>", "release"),
                    ):
                        canvas.bind(
                            event_name,
                            lambda event, label=value: hits.append(label),
                            add="+",
                        )
                    for event_name, x, y in (
                        ("<ButtonPress-1>", 40, 60),
                        ("<B1-Motion>", 120, 180),
                        ("<ButtonRelease-1>", 120, 180),
                    ):
                        canvas.event_generate(event_name, x=x, y=y, when="now")
                        window.update_idletasks()
                    self.assertEqual(["press", "drag", "release"], hits)
                    self.assertEqual(
                        [{
                            "category": "cat",
                            "visibility": "partial",
                            "xyxy": [10, 15, 30, 45],
                        }],
                        list(session.boxes(samples[0].sample_id)),
                    )
                    self.assertGreaterEqual(len(canvas.find_all()), 3)
                    buttons["Confirmer cette image"].invoke()
                    self.assertEqual(1, session.reviewed_count)
                    self.assertIn("Photo TEST 2/2", " ".join(
                        w.cget("text") for w in widgets
                        if isinstance(w, ttk.Label)
                    ))

                    # A naked second image must ask before accepting empty
                    # boxes as a valid negative, never guess a category.
                    buttons["Confirmer cette image"].invoke()
                    self.assertEqual(2, session.reviewed_count)
                    self.assertEqual("Relecture sans cible", asks[-1][0])
                    checks[
                        "Je n'ai pas consulte les predictions ni annotations V3"
                    ].invoke()
                    checks[
                        "Cette annotation est une nouvelle revue manuelle independante"
                    ].invoke()
                    buttons["Exporter cette revue privee"].invoke()
                except BaseException as error:
                    captured_errors.append(error)
                    window.destroy()

            def create_instrumented_root(*args, **kwargs):
                window = constructed(*args, **kwargs)
                window.after(200, lambda: drive_ui(window))
                # Fail closed if the GUI hangs or a modal dialog unexpectedly
                # blocks the synthetic session. No background work.
                def timeout_close():
                    captured_errors.append(
                        AssertionError("GUI smoke did not finish within 10s")
                    )
                    window.destroy()
                window.after(10000, timeout_close)
                return window

            def ask_yes_no(title, question):
                asks.append((title, question))
                return True

            with patch("tkinter.Tk", side_effect=create_instrumented_root), \
                 patch.object(messagebox, "askyesno", side_effect=ask_yes_no), \
                 patch.object(messagebox, "showinfo",
                              side_effect=lambda *x: reviews_shown.append(x)), \
                 patch.object(messagebox, "showerror",
                              side_effect=AssertionError("unexpected GUI error")):
                run_gui(session)

            if captured_errors:
                raise captured_errors[0]
            self.assertEqual(1, len(reviews_shown))
            self.assertEqual(2, session.reviewed_count)
            paths = list((root_dir / "reviews").glob("r-*.json"))
            self.assertEqual(1, len(paths))
            metadata = json.loads(paths[0].read_text("utf-8"))
            self.assertEqual("first", metadata["role"])
            self.assertTrue(metadata["blind_to_model_predictions_declared"])
            self.assertTrue(metadata["manual_independent_review_declared"])
            self.assertEqual(2, len(metadata["samples"]))
            self.assertEqual("cat", metadata["samples"][0]["boxes"][0]["category"])
            self.assertEqual([], metadata["samples"][1]["boxes"])
            self.assertNotIn("dog", paths[0].read_text("utf-8"))
            # Read it using the existing #118 parser; not a new writer.
            session_id, parsed = _read_review(dataset, paths[0], "first")
            self.assertEqual(session.review_session_id, session_id)
            self.assertEqual(2, len(parsed))
            self.assertFalse(parsed[samples[1].sample_id][1])


if __name__ == "__main__":
    unittest.main()
