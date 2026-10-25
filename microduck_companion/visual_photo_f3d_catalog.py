"""F3-D: 28 new public Commons photographs declared CC0 / own work.

Metadata only; no JPEGs committed. Listed labels come from public captions,
not independently reviewed frames. CC0 claims are not rights warranties.
New test images MUST NOT be used to choose the F3-B threshold.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from .visual_photo_catalog import PHOTO_CATALOG, PublicPhoto, CC0_LICENSE

EXPECTED_GROUPS = {"cat":8,"dog":8,"chair":4,"flower":4,"bird":2,"ball":2}

@dataclass(frozen=True)
class ChallengePhoto:
    photo: PublicPhoto
    group: str

def entry(filename: str, author: str, group: str) -> ChallengePhoto:
    label = group if group in ("cat","dog") else "unknown"
    return ChallengePhoto(PublicPhoto(filename, author, label, "test"), group)

CHALLENGE_CATALOG = (
    entry("A_photo_of_a_cat_sitting_down.jpg","Asabae2752","cat"),
    entry("Nopple_cat.jpg","Nopple","cat"),
    entry("The_black_and_white_cat.jpg","Khidoyatxon","cat"),
    entry("Poised_Cat.jpg","Ian Rastall","cat"),
    entry("Cat_lying_down.jpg","Teojincheng","cat"),
    entry("Black_cat_staring_at_the_camera_(2023-07-16).jpg","Roc0ast3r","cat"),
    entry("Gato_doméstico_(Felis_silvestris_catus).jpg","Juan Emilio Prades Bel","cat"),
    entry("Cat_image.jpg","Mohanraj55","cat"),
    entry("Animal_photography..dog.jpg","JAYASHREESATHIYAMOORTHY","dog"),
    entry("Domesticated_dog.jpg","Raizkgh","dog"),
    entry("Petting_my_dog.jpg","JaredMcKenzie","dog"),
    entry("Cute_street_dog.jpg","Abhi3120","dog"),
    entry("IMg_dog.jpg","A140706","dog"),
    entry("Dog_smiling_at_the_camera_-_Reta,_Buenos_Aires,_Argentina_(04-01-2024).jpg","Maxd2","dog"),
    entry("Guide_dog_at_RSM_2024.jpg","Whispyhistory","dog"),
    entry("The_cute_dog(poppy).jpg","Ranjithkanth Tamilselvan J","dog"),
    entry("Chair.JPG","Antonio Borrillo","chair"),
    entry("Cultural_Chair.jpg","787IYO","chair"),
    entry("Red_chair.jpg","Fitrah 9131","chair"),
    entry("A_Fabric_Chair.jpg","Ashakemary","chair"),
    entry("Flower_photos.jpg","Abinayasekar357","flower"),
    entry("FLOWER(1).jpg","SIVA ARULMOZHLI","flower"),
    entry("Flower_🌷.jpg","E.Prabha","flower"),
    entry("Pink_Paper_flower.jpg","By atmika","flower"),
    entry("Silhouette_of_Bird.jpg","Biveti46","bird"),
    entry("A_lighting_bird.jpg","ManikDas1122","bird"),
    entry("Golf_ball_in_dirt,_sep_6_2026.jpg","Logan M Diel","ball"),
    entry("Throwing_ball_exercise.jpg","Onwuka Glory","ball"),
)

def validate_challenge_catalog(catalog=CHALLENGE_CATALOG) -> None:
    if type(catalog) is not tuple or len(catalog) != 28:
        raise ValueError("exactly 28 challenge entries required")
    old_names={p.filename.casefold() for p in PHOTO_CATALOG}
    old_authors={p.author.casefold().strip() for p in PHOTO_CATALOG}
    new_names=set()
    new_authors=set()
    counts=Counter()
    for item in catalog:
        if type(item) is not ChallengePhoto or type(item.photo) is not PublicPhoto:
            raise ValueError("invalid challenge record")
        p=item.photo
        name=p.filename.casefold()
        author=p.author.casefold().strip()
        if (not name.endswith(".jpg") or "/" in p.filename
                or "\\" in p.filename or not author
                or p.split!="test" or p.license!=CC0_LICENSE
                or item.group not in EXPECTED_GROUPS
                or p.category!=(item.group if item.group in ("dog","cat")
                                else "unknown")):
            raise ValueError("invalid challenge metadata")
        if (name in old_names or name in new_names
                or author in old_authors or author in new_authors):
            raise ValueError("author or photograph leakage")
        new_names.add(name)
        new_authors.add(author)
        counts[item.group]+=1
    if dict(counts)!=EXPECTED_GROUPS:
        raise ValueError("wrong per-group challenge counts")
