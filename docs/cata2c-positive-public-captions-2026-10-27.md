# Cat-A2c — 25 photographies publiques positives, sans prétention de hauteur caméra

**27 octobre 2026 — étude de *concordance aux légendes*, pas benchmark fiable en vue basse.** [Issue Cat-A2b #78](https://github.com/Jean-Philippe56520/Microduck/issues/78). Priorité : obtenir de **vraies images contenant des objets** plutôt que continuer à présenter les trois sols réfléchissants UMD comme un essai de reconnaissance.

## 1. Audit réutiliser / adapter / créer

| Source | Constat réel | Décision |
| --- | --- | --- |
| [OEM épinglé microduck 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) (robotd/mediad) | Caméra et sécurité moteur propriétaires constructeur. Le détecteur OEM historique détecte surtout des Microducks. La RAM/NPU robot et l'angle optique final ne sont **pas mesurés** | Ne toucher ni au firmware ni aux pilotes ; aucun moteur ou caméra Kwipi utilisé |
| [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381), [#414](https://github.com/pollen-robotics/microduck/pull/414) | **Ouvertes, non fusionnées** au 27/10/2026 ; proposition de cerveau et cartographie v45 non livrées | Ne pas intégrer d'API fictive |
| [F3-D](../microduck_companion/visual_photo_f3d_catalog.py), [F3-D benchmark](../microduck_companion/visual_photo_f3d_benchmark.py) | **28 JPEG publics déjà catalogués**, auteurs distincts et licences CC0 1.0 **déclarées** sur leurs pages d'origine ; téléchargement Wikimedia contraint à des vignettes JPEG et contrôle MIME/HTTPS/poids | **Réutiliser sans modifier** les catalogues, droits déclarés, téléchargement et contrôles de diversité d'auteurs. Les légendes ne sont **pas** des GT complètes et les licences ne certifient pas indépendamment les titres |
| [Cat-A YOLOX](../microduck_companion/cata_yolox_categories.py), [Cat-A2a](../microduck_companion/cata2_bbox_eval.py) | Poids ONNX d'origine Megvii Apache-2.0, SHA-256 figé, seuil fixe 0,25, prétraitement 416, score spatial/NMS | **Réutiliser tel quel** pour des propositions de catégories. Aucune sélection de seuil ou entraînement nouveau |
| [Cat-A2b privé](../microduck_companion/cata2b_private_low.py) | Exige caméra à centre optique déclaré 100–300 mm, règle photo, SHA locaux, splits et statut `operator_private_capture` | **Ne pas y injecter de données publiques**, ni fabriquer une hauteur, un consentement ou une boîte |
| CID-SIMS / OCID / ISR RGB-D / ARID / C3 tiers | CID-SIMS annonce caméras ~12/~26 cm mais classes et droits média non confirmés pour cinq catégories ; OCID propose objets en encombrement mais pas de hauteur numérique prouvée ; ISR RGB-D donne boîtes personne/chaise mais hauteur et licences de photos non confirmées ; ARID boîtes et intérieur, hauteur inconnue. La communauté ne fournit pas de modèle validé sur 1 Go | **Ne pas importer**, garder en candidats pour véritable Cat-A2b après inspection des droits, annotations, hauteur, regroupements, ressources et code OEM |

## 2. Corpus source, déjà indépendant de F3-B

Le nouveau banc ne télécharge **aucune image inédite dans le dépôt** : il sélectionne **25 des 28 pages F3-D** par auteurs publics distincts, sans aucune personne du foyer ou information privée.

| Groupe dont la présence est **déclarée par la légende publique** | Photos | Catégorie de YOLOX correspondante |
| --- | ---: | --- |
| Chat | 8 | `cat` |
| Chien | 8 | `dog` |
| Chaise | 4 | `chair` |
| Balle (dont golf, ballon) | 2 | `sports_ball` (correspondance sémantique susceptible d'être imparfaite) |
| Oiseaux / fleur, **non ciblés par notre liste** | 3 | Aucune classe attendue ; absence d'autres cibles NON confirmée |
| **Total** | **25** | **22 sujets positifs déclarés**, 3 scènes potentiellement négatives |

**Pas de photo de personne dans le corpus cible** : `person` n'est pas mesurable ici. Les étiquettes ont été reprises de captions déjà publiques, **sans deuxième annotateur, aucune garantie que l'objet déclaré soit entier dans le champ, ni que les autres classes soient absentes**. Certains JPEG peuvent être proches d'un autre corpus de préentraînement COCO/ImageNet ; la séparation des auteurs de F3-B ne prouve pas l'absence de recouvrement avec les préentraînements.

**Important : aucune hauteur de caméra n'est déclarée ni vérifiée** pour les 25 images. Le fait qu'une photo montre un animal couché ou une balle au sol ne prouve pas un appareil à 10–30 cm. **Ce lot n'est pas une performance de perception de Kwipi à 25 cm**.

## 3. Ce qui est mesurable sans inventer de labels

Le module [`cata2c_public_caption_probe.py`](../microduck_companion/cata2c_public_caption_probe.py), lancé par [la CI dédiée](../.github/workflows/cata2c-public-positive-caption-probe.yml) :

1. Refuse toute liste différente des **25 sources fixes**. Vérifie que les **28 F3-D** restent valides et que leurs auteurs, champs et déclarations CC0 sont cohérents.
2. Réutilise `fetch_challenge_photo()` pour télécharger une unique vignette temporaire de chaque page Commons, en vérifiant hôte final, HTTPS, MIME, budget 1,2 Mo, JPEG, puis la géométrie réelle avec Pillow.
3. Refuse une image en double SHA-256 (seulement copies **exactes**, pas les quasi-doublons).
4. Réutilise `prepare_image()` et `decode_boxes()` du même YOLOX-Nano préentraîné, sur CPU Linux hôte. Le seuil demeure **0,25**, fixé avant la collecte.
5. Publie uniquement **par groupe** : images avec une ou plusieurs propositions de classes, images sans propositions, images avec une **proposition concordante à la catégorie mentionnée dans la légende**, nombres de propositions par classe, empreinte agrégée du lot, latence et RSS du **processus PC**. Aucune image, boîte avec coordonnées, nom privé, modèle, donnée d'enfant ou voix dans les logs.
6. Verrouille explicitement `precision_recall_f1_ap50 = null`, `photos_verified_camera_height_100_to_300mm = 0`, `person_class_caption_positive_photos = 0`. Les propositions de classes non mentionnées dans la légende **ne sont pas nécessairement des faux positifs** ; une proposition concordante n'est pas automatiquement un vrai positif.

Les miniatures externes peuvent changer : le résultat expose un *digest des SHA-256 de session*, sans prétendre épingler des JPEG dans le temps. Si un fichier change, une reprise ultérieure ne doit pas être annoncée comme « mêmes octets » sans comparer l'empreinte. Aucune calibration sur ce lot.

## 4. Portes d'acceptation pour le véritable Cat-A2b à 100–300 mm

**Pour convertir l'exploration en vraie mesure de reconnaissance :**
- Retenir de nouveaux clichés **réels, à hauteur du centre optique documentée**, avec orientation et prise de règle dont la validité a été contrôlée humainement ; un titre « au sol » ne prouve pas la hauteur.
- Vérifier l'autorisation des médias **par fichier**, les droits des personnes et l'usage des masques/annotations ; ne pas inventer de licence à partir de celle d'un utilitaire GitHub.
- Un humain distinct de l'auteur des légendes doit annoter **toutes les boîtes d'objets visibles des cinq catégories** (ou signaler explicitement les zones incertaines). Les entrées sans catégorie doivent être revues ; « le photographe n'a pas mentionné de chaise » ne prouve pas l'absence de chaise.
- Grouper par scène, session, auteur/source, lieu ; ne pas partager ces groupes entre TRAIN/VALIDATION/TEST ; garder l'évaluation TEST au seuil figé et les droits/échantillons hors Git.
- Alors seulement réutiliser `evaluate_localization` Cat-A2a pour comparer TP/FP/FN et AP50 par catégorie avec un petit support explicité. **Aucun robot physique**, NPU, thermique, locomotion, autonomie ou mémoire d'expérience n'est validé par cette étape.

## 5. Résultats

**À compléter uniquement après la vraie exécution CI de la PR** : nombre de téléchargements vérifiés, propositions et concordances par groupe, latence CPU hôte, empreinte et refus observés. Ces nombres ne sont pas des métriques de précision/rappel. Les tests de fixtures jouent sans caméra ni média personnel, et ne donnent aucun chiffre de reconnaissance.

L'[issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78) reste **ouverte**.
