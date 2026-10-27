# Cat-A2b — premier essai sur photographies publiques d'une caméra annoncée à ~12 cm

**27 octobre 2026 — lot d'évaluation exploratoire CPU hôte ; précision et validation sur robot non établies.** [Issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78). Ce document décrit une **sonde de propositions non annotées**, distincte du vrai benchmark privé et du benchmark COCO Cat-A2a.

## 1. Décision réutiliser / adapter / créer

- **Constructeur épinglé** : OEM `microduck` à `942e58e3aa6dbb28e7037203fff11866122c7567`, `robotd/mediad` propriétaires de la perception et des mouvements sur robot ; ses poids RKNN OEM détectent principalement d'autres Microducks, pas ces cinq catégories du foyer. Les PR [OEM #381](https://github.com/pollen-robotics/microduck/pull/381) (cerveau) et [#414](https://github.com/pollen-robotics/microduck/pull/414) (cartographie, API v45) restent **ouvertes/non fusionnées**, donc non utilisables comme fonctions livrées.
- **Companion** : **réutiliser** sans modification `cata_yolox_categories.py` (même modèle ONNX Megvii Apache-2.0, même SHA-256, prétraitement 416 px et seuil 0,25) et `cata2_bbox_eval.py` (boîtes/NMS). Ne pas inscrire ces photos tierces dans `cata2b_private_low.py` avec la fausse source `operator_private_capture`.
- **Communauté / autres corpus** : CID-SIMS (12/26 cm) et OCID (floor/bottom) sont des candidats de recherche, mais les droits de redistribution et les catégories/boîtes nécessaires ne sont pas suffisamment audités pour un benchmark. Smartulf/GC/quack-control/Quacksat/Twin/QuackNav n'ajoutent aucune vérité de catégorie par prise basse utile ici. **Aucun pilote, modèle, réseau neuronal, image ou code tiers importé.**
- **Créer seulement** une sonde **non motrice** pour trois PNG directement publiés dans le dépôt des chercheurs, avec SHA Git des fichiers épinglé, tests négatifs et inférence temporaire sur le runner GitHub. Ne pas créer de nouveau jeu TRAIN/TEST, SQLite, API OEM, réglage de seuil ou rapport d'exactitude inventé.

## 2. Source, hauteur, licences, provenance

- Étude universitaire originale : [Ground Plane Segmentation Using Semantic Segmentation](https://github.com/adarshmalapaka/ground-plane-segmentation/blob/473d261362901c944a65d630e3892abdeee2353b/README.md), auteurs du projet à l'University of Maryland, 2022 ; dans **Video Specifications**, hauteur de la caméra **« 12 cm approx (from the ground) »**, images originales annoncées 1280×720, séquences de couloirs universitaires. Cette hauteur est **indiquée pour l'ensemble du dispositif**, pas instrumentée pour chaque PNG, ni identique au centre optique final de Kwipi.
- Les **trois** seuls PNG d'aperçu publics dans `Code/training/data/orig_imgs/` sont `A00001.png`, `A00002.png` et `A00019.png`. Ils sont présents dans le dépôt original, à la révision Git **`473d261362901c944a65d630e3892abdeee2353b`** ; contrôle par les **SHA-1 Git blob** respectifs `8f9b11d518b7ad24b34555853d6c521a8582fe47`, `aee05238a8e8f6766bdcd342ba206ff6240c2b57`, `59d9ef204c36a5ae0ae0f9355c0b696f53289518`.
- Le [fichier LICENSE](https://github.com/adarshmalapaka/ground-plane-segmentation/blob/473d261362901c944a65d630e3892abdeee2353b/LICENSE) indique MIT pour le dépôt. **Cette licence ne certifie pas automatiquement les autorisations de chaque sujet photographié ni tous les droits spécifiques aux images** ; aucune revendication de licence média indépendante. Les JPEG/PNG tiers ne sont **ni copiés, ni ajoutés à notre Git, ni mis en artifact CI**. Les sources et les auteurs sont attribués. Si les ayants droit interdisent cet usage, retirer immédiatement cette sonde.
- Les trois fichiers peuvent provenir d'une même séquence, de scènes proches ou recouper l'apprentissage du modèle, sans information suffisante pour les déclarer indépendants. **Aucun split**, aucune conclusion statistique, aucune classification des droits personnels, aucune vérité humaine `person/cat/dog/chair/sports_ball` vérifiée ici.
- Les masques d'origine étiquettent le **sol praticable** et non les cinq catégories visuelles demandées. Ils **ne sont pas un ground truth de détection d'objet**.

## 3. Chemin technique et sûreté

`microduck_companion/cata2b_public_low_probe.py` : ouvrir seulement trois URLs d'un même dépôt **à commit immuable**, lecture HTTPS bornée à 1,25 Mo par fichier, vérification du SHA Git blob, validation du PNG et des dimensions, transcodage JPEG de qualité 95 **en mémoire** (prétraitement Cat-A attend des JPEG). Un léger changement d'image dû au JPEG est divulgué. Inférence CPU ONNX Runtime sur les mêmes poids hashés que Cat-A, relecture du même `decode_boxes()`, résultat composé seulement de **comptages de boîtes proposées par classe**, du digest de digests, des mesures CPU/RSS runner et des **indicateurs explicites d'absence de vérité terrain**. Aucune image, boîte avec coordonnées, identité, nom de fichier individuel, voix ou emplacement personnel n'est imprimé.

La commande exige l'option explicite `--approved-public-research-media`; aucune action automatique hors CI de PR dédiée, aucun capteur/moteur, SQLite, Qwen ou service constructeur.

```bash
# Depuis le dépôt cloné sur PC, après installation de Pillow, numpy, onnxruntime :
# Télécharger et vérifier le modèle YOLOX déjà approuvé, hors Git (.onnx ignoré).
python -m microduck_companion.cata2b_public_low_probe \
  --model-path .local_visual_data/models/yolox_nano.onnx \
  --approved-public-research-media
```

Reproduire également via [workflow CI dédié](../.github/workflows/cata2b-public-12cm-probe.yml). Une erreur de source, checksum, résolution, modèle, réponse ONNX, disponibilité réseau ou couverture attendue **invalide l'essai**. Aucun fallback sur des images de remplacement non vérifiées.

## 4. Résultats et limite de l'étape

**Résultat à remplir à partir des logs CI réels de la PR** : nombres de propositions par classe, provenance validée, temps CPU et RSS runner. **Aucun TP/FP/FN, précision, rappel ou AP50 ne peut être calculé à partir d'images non contre-annotées** ; un résultat « zéro balle » n'est ni la preuve de leur absence ni une mesure de rappel.

Le nombre de vraies images privées à hauteur de Kwipi reste **zéro**. Les trois PNG sources sont des prises réelles avec **hauteur générale déclarée par les auteurs**, non des photos synthétiques ; la hauteur de **chaque prise** n'est pas vérifiée par nous et la pertinence exacte de ces vues pour les cinq classes reste à contrôler.

### Suite admissible

- Confirmer les autorisations d'utilisation des images auprès des auteurs si une vraie évaluation doit être diffusée.
- Obtenir des annotations de boîtes **indépendantes** et des séries suffisamment variées, en contrôlant les regroupements de scènes ; conserver les médias hors Git et respecter le droit des personnes.
- Ajouter d'autres sources documentées à 100–300 mm pour animaux, balles, personnes et meubles, éventuellement CID-SIMS/OCID seulement après audit légal et catégoriel.
- Refaire Cat-A2b avec vérité terrain et rapport TP/FP/FN/AP50 par catégorie, sans ajuster le seuil sur TEST. Le robot RK3566 restant absent, aucune propriété NPU/RAM/thermique ou locomotrice n'est démontrée.
