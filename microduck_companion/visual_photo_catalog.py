"""F3-B: small reviewed CC0 Wikimedia Commons *photo* source list.

The exact image source pages (not image bytes) are public. Each file page
declared CC0 1.0 and "Own work" when checked 2026-10-25. Verify their
license, authorship and image subject again before reuse/deployment.
Public uploader names here are for attribution and split-isolation only,
NEVER household identities, face IDs or object tracking IDs.

No images are committed to GitHub. All licenses are public declarations,
NOT a cryptographic warranty of ownership; labels are manually curated from
public file-page descriptions and have not been independently audited for all
image content.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

CC0_LICENSE = "CC0-1.0"
COMMONS_BASE = "https://commons.wikimedia.org/wiki/File:"


@dataclass(frozen=True)
class PublicPhoto:
    filename: str
    author: str
    category: str
    split: str
    license: str = CC0_LICENSE

    @property
    def file_page(self) -> str:
        return COMMONS_BASE + quote(self.filename, safe="._-")

    @property
    def thumbnail_url(self) -> str:
        # The Wikimedia FilePath endpoint redirects to a 320 px thumbnail.
        return ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                + quote(self.filename, safe="._-") + "?width=320")


# 8 train, 6 validation (including 2 out-of-domain), 6 test
# (including 2 out-of-domain). One distinct photographer/source per image;
# grouping by credited author is a conservative, though incomplete, guard.
PHOTO_CATALOG: tuple[PublicPhoto, ...] = (
    PublicPhoto("Picture_of_cat.jpg", "Theeyes 07", "cat", "train"),
    PublicPhoto("Kitten_on_the_tree.jpg", "Jelesije I", "cat", "train"),
    PublicPhoto("A_black_and_white_kitten.jpg", "Jeromi Mikhael", "cat", "train"),
    PublicPhoto("Cat_is_standing.jpg", "Zhmila", "cat", "train"),
    PublicPhoto("Photo_of_a_dog.jpg", "ContaDeletada2906", "dog", "train"),
    PublicPhoto("Pet_animal_photography.jpg", "Obusaranya sekar", "dog", "train"),
    PublicPhoto("My_little_dog.jpg", "Sowmiyamuruganmba", "dog", "train"),
    PublicPhoto("Dog_IMG_1057.jpg", "JasonAstros123", "dog", "train"),
    PublicPhoto("Cat_looking.jpg", "Ani Vincent", "cat", "validation"),
    PublicPhoto("Cute_cat_2024.jpg", "Ahmadjonova Azizaxon", "cat", "validation"),
    PublicPhoto("Dog_in_forest.jpg", "Ssroldan", "dog", "validation"),
    PublicPhoto("My_cute_dog.jpg", "Doglover41", "dog", "validation"),
    PublicPhoto("Flower_photo_normal.jpg", "LorelMan", "unknown", "validation"),
    PublicPhoto("Bird_image.jpg", "Darakshanehaluddin", "unknown", "validation"),
    PublicPhoto("Kitten_Looking.jpg", "Saral Shots", "cat", "test"),
    PublicPhoto("Kitts01e01.jpg", "Coolbrizzy", "cat", "test"),
    PublicPhoto("Sleeping_Brown_Dog.jpg", "Nikkaella", "dog", "test"),
    PublicPhoto("Cute_dog_sitting_in_forest.jpg", "Hamoma30", "dog", "test"),
    PublicPhoto("Small_bird.jpg", "Kyreb", "unknown", "test"),
    PublicPhoto("Flower_vv6.jpg", "Dinkum", "unknown", "test"),
)
