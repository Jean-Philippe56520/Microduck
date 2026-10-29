"""Positive/negative fixtures for descriptive ROI colors, not object detection."""
import unittest
from PIL import Image, ImageDraw
from experiments.region_appearance_probe import describe_region, rgb_colour

class RegionAppearanceTests(unittest.TestCase):
    def test_pure_rgb_and_luminance_bins(self):
        self.assertEqual(rgb_colour((230, 25, 30)), "red")
        self.assertEqual(rgb_colour((20, 40, 245)), "blue")
        self.assertEqual(rgb_colour((128, 128, 128)), "gray")
        self.assertEqual(rgb_colour((250, 250, 250)), "white")

    def test_center_recovers_red_when_full_box_has_green_background(self):
        image = Image.new("RGB", (160, 160), (24, 215, 24))
        ImageDraw.Draw(image).rectangle((40, 40, 119, 119), fill=(228, 22, 22))
        center = describe_region(image, (20, 20, 140, 140))
        entire = describe_region(image, (20, 20, 140, 140), central_fraction=1.0)
        self.assertEqual(center["color"], "red")
        self.assertNotEqual(entire["color"], "red")
        self.assertEqual(center["geometry"]["bbox_geometry_only"], "roughly_square_box")
        self.assertTrue(center["not_object_shape"])
        self.assertTrue(center["not_object_category"])

    def test_ambiguous_color_is_unknown_not_new_class(self):
        im = Image.new("RGB", (160, 160), (220, 20, 20))
        ImageDraw.Draw(im).rectangle((80, 0, 159, 159), fill=(15, 25, 225))
        desc = describe_region(im, (0, 0, 160, 160))
        self.assertEqual(desc["color"], "unknown")
        self.assertEqual(desc["status"], "unknown")
        self.assertTrue(desc["not_physical_size_or_distance"])

    def test_box_aspect_is_geometry_not_actual_shape(self):
        im = Image.new("RGB", (160, 160), (20, 200, 25))
        res = describe_region(im, (10, 60, 150, 95))
        self.assertEqual(res["geometry"]["bbox_geometry_only"], "wide_box")
        self.assertNotIn("round", res["geometry"]["bbox_geometry_only"])
        self.assertEqual(res["color"], "green")

    def test_too_small_crop_is_unknown(self):
        im = Image.new("RGB", (160, 160), (240, 20, 20))
        desc = describe_region(im, (1, 1, 8, 8))
        self.assertEqual(desc["status"], "unknown")
        self.assertEqual(desc["color"], "unknown")

    def test_invalid_inputs_fail_closed(self):
        im = Image.new("RGB", (160, 160), (0, 0, 0))
        for rectangle in (
            (-1, 0, 50, 50), (20, 20, 20, 40),
            (30, 30, 200, 140), (0, 0, float("nan"), 100),
        ):
            with self.subTest(rectangle=rectangle):
                with self.assertRaises(ValueError):
                    describe_region(im, rectangle)
        with self.assertRaises(TypeError):
            describe_region(im.convert("L"), (10, 10, 90, 90))
        with self.assertRaises(ValueError):
            describe_region(im, (10, 10, 90, 90), central_fraction=.25)

if __name__ == "__main__":
    unittest.main()
