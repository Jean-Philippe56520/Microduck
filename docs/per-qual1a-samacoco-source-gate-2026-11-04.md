# PER-QUAL-1A — qualification de la réannotation Sama-COCO (sources uniquement)

**Date :** 04/11/2026. Autorité : [plan d'action](plan-action.md) ; [préenregistrement avant scores, issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6637584606). **Aucune inférence, aucun modèle et aucun JPEG dans ce premier lot.**

## Question et témoin

Les évaluations #296 (800 JPEG COCO val) et #298 (48 JPEG Open Images) sont acquises. Des propositions non appariées à COCO ne sont pas nécessairement de faux positifs physiques : une annotation peut omettre un objet. [Sama-COCO, source primaire](https://www.sama.com/sama-coco-dataset), a fait réannoter les mêmes photos COCO2017 par d'autres humains, **en partant des préannotations COCO**. Cette seconde annotation est donc **corrélée** à COCO et ne constitue **pas** un nouveau corpus d'images ni une GT entièrement indépendante. Sama a aussi volontairement exclu les objets inférieurs à 10×10 px.

Comparer, avant tout score YOLOX, la géométrie et le nombre de boîtes du COCO original et de Sama-COCO sur des images jamais évaluées pour savoir si les comptes d'objets peuvent affecter la lecture future des résultats.

**Droits :** l'éditeur donne accès gratuitement à l'archive de validation et la [documentation FiftyOne](https://docs.voxel51.com/dataset_zoo/datasets/sama_coco.html) donne **CC BY 4.0** pour Sama-COCO. Les photographies COCO conservent leurs licences Flickr d'origine, différentes selon le cliché ; usage expérimental interne sans publication, entraînement ni redistribution, aucune permission commerciale individuelle présumée.

## Porte prospective, avant modèles et images

- Sources : JSON COCO val2017 déjà SHA256 épinglé ; archive Sama-COCO validation de ~5,7 Mo seulement. Aucun téléchargement d'image ni de poids ONNX.
- **42 ID de photos COCO val jamais évaluées**, six affectées à chacune des sept classes : sports_ball, book, bottle, chair, dog, cat, person, allocation des classes les plus rares d'abord. Chaque image doit porter une boîte non-crowd valide dans **les deux** annotations pour la classe assignée.
- **1 232 exclusions historiques** COCO : 432 issus des évaluations antérieures, plus les 800 de PER-80. La disjonction des IDs d'images ne certifie pas des lieux/scènes physiques distincts.
- Tri déterministe SHA, semence kwipi-per-qual1a-samacoco-paired-20261104-v1, critères et quotas fixés avant tout score. Aucune réduction opportuniste après lecture des scores.
- Sortie : compte des boîtes par classe et par annotation, appariements géométriques IoU50 *entre annotations*, SHA de l'archive Sama et empreinte de la cohorte. **Aucun ID d'image, pixel, coordonnées, modèle, souvenir ou secret publié.** Hauteur : viewpoint_height=unknown admise pour le diagnostic PC, sans équivalence OEM.

**PASS source :** vraie archive compatible avec format/GT, support 7×6, 1 232 ID exclus, SHA fixé avant accès au modèle, contrôles positifs/négatifs et CI du dernier SHA réussis. **STOP_SOURCE :** licence ou provenance incompatible, archive corrompue/ambiguë, mapping divergent, source instable, images/boîtes incorrectes, contamination historique, nombre insuffisant d'images ou CI non verte. En STOP, zéro inférence et zéro promotion.

**Suite ultérieure seulement après PASS source :** exécuter une seule prédiction YOLOX d'origine sur les mêmes 42 nouveaux JPEG, comparer le rappel IoU50 contre les deux listes de GT avec le décodeur 80 classes déjà codé, qualifier les discordances sans les déclarer des erreurs physiques, sans tuning ni promotion automatique. Ne pas lancer ce second lot tant que la source et son empreinte ne sont pas figées.

## Tests, réemploi et sûreté

Tests source sur PC : sélection stable, 42 IDs uniques, six/classes, contrôle de licence/mapping/géométrie, omission de GT et groupes correctement refusés, ZIP corrompu/path traversal/doublons rejeté, absence de conversion silencieuse en négatifs. Réutilisation de experiments.per80_yolox_coco_public._cohort_from_pinned_source, _valid_license_ids et eighth_disjoint pour les exclusions et contrôles historiques ; seul le lecteur de shards Sama-COCO est créé. Scripts et CI *research-only*.

Aucune modification mediad/uyvy/duck-detect, modèle YOLOX, RKNN/NPU RK3566, moteurs robotd 50 Hz, caméra, Qwen, SQLite, rootfs Yocto B11 ou sous-modules OEM. Aucun robot disponible. Retour arrière = revert du script, des tests, du workflow et de ce rapport candidat. **CI source réussie ≠ perception de Kwipi.**
