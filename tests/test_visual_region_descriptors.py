"""Bounded positive/negative tests for descriptive colour/shape candidates.

These fixtures test a pixel algorithm, not YOLOX detections or physical robot.
"""
import unittest
from PIL import Image, ImageDraw
from experiments.visual_region_descriptors import describe_region


def scene(shape="circle", fg=(230, 25, 30), bg=(135, 140, 145)):
    im = Image.new("RGB", (160, 160), bg)
    draw = ImageDraw.Draw(im)
    if shape == "circle":
        draw.ellipse((36, 36, 124, 124), fill=fg)
    if shape == "square":
        draw.rectangle((39, 39, 121, 121), fill=fg)
    return im


class VisualRegionDescriptorTests(unittest.TestCase):
    def test_red_circle_has_circular_shape_and_red(self):
        row = describe_region(scene(), (18, 18, 143, 143))
        self.assertEqual(row["status"], "foreground_candidate")
        self.assertEqual(row["shape"], "ronde_probable")
        self.assertIn("rouge", [c["colour"] for c in row["dominant_colours"]])
        self.assertEqual(row["object_category"], "unknown")

    def test_blue_square_has_rectangular_shape_and_blue(self):
        row = describe_region(scene("square", (20, 65, 230)), (18, 18, 143, 143))
        self.assertEqual(row["status"], "foreground_candidate")
        self.assertEqual(row["shape"], "rectangulaire_probable")
        self.assertIn("bleu", [c["colour"] for c in row["dominant_colours"]])

    def test_plain_background_cannot_be_a_detected_object(self):
        image = Image.new("RGB", (128, 128), (128, 128, 128))
        row = describe_region(image, (0, 0, 128, 128))
        self.assertEqual(row["status"], "indeterminate")
        self.assertEqual(row["dominant_colours"], [])
        self.assertEqual(row["shape"], "indeterminee")

    def test_cluttered_background_refuses_to_invent_silhouette(self):
        image = scene()
        pixels = image.load()
        for y in range(160):
            for x in range(160):
                if x < 30 and y < 30:
                    pixels[x, y] = (255, 15, 15)
        row = describe_region(image, (0, 0, 160, 160))
        self.assertEqual(row["status"], "indeterminate")

    def test_transparent_background_supported(self):
        image = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(image).ellipse((36, 36, 124, 124), fill=(50, 220, 50, 255))
        row = describe_region(image, (18, 18, 143, 143))
        self.assertEqual(row["status"], "foreground_candidate")
        self.assertEqual(row["shape"], "ronde_probable")
        self.assertIn("vert", [c["colour"] for c in row["dominant_colours"]])

    def test_partial_outside_roi_is_not_called_round(self):
        img = scene()
        row = describe_region(img, (44, 45, 108, 108))
        self.assertNotEqual(row["shape"], "ronde_probable")

    def test_invalid_roi_rejected(self):
        img = scene()
        for box in [(-1, 0, 60, 60), (20, 20, 20, 30), (0, 0, 999, 999),
                    (0, 0, float("nan"), 32)]:
            with self.subTest(box=box):
                with self.assertRaises(ValueError):
                    describe_region(img, box)
        with self.assertRaises(TypeError):
            describe_region("not-an-image", (0, 0, 32, 32))


if __name__ == "__main__":
    unittest.main()
