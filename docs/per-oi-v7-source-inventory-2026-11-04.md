# PER-OI-V7-SRC-0 — inventory Open Images V7 pour un futur témoin YOLOX-S/M

**Date :** 04/11/2026. **Statut de ce lot :** candidat **métadonnées/fixtures hôte seulement** ; CI spécialisée sur le HEAD à effectuer, **aucun JPEG ou poids chargé**. [Porte préenregistrée AVANT le code](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6643588824). Autorité de priorité : [plan d'action](plan-action.md).

## Pourquoi ne pas recycler COCO ?

La [PR #310](https://github.com/Jean-Philippe56520/Microduck/pull/310) a exécuté les vrais modèles optimisés Rockchip YOLOX-S/M sur **entrée noire synthétique**, avec 3 sorties correctes et SHA épinglés, mais **zéro JPEG naturel et zéro précision**. Sur COCO val2017, après les **1 316 images consommées**, le préflight des photos en licence CC BY 2.0 a **0 balle sportive** avec GT COCO+Sama (inventaire numérique CI #41922006466). D'autres licences sont présentes, mais n'ont pas été promues par le protocole arrêté avant essai.

## Nouvelle source officielle, pas de qualification anticipée

[Open Images V7](https://storage.googleapis.com/openimages/web/download_v7.html) : jeu de données de reconnaissance annoté, avec split validation, CSV de boîtes et classes sous identifiants `MID`. [Documentation licences](https://storage.googleapis.com/openimages/web/factsfigures_v7.html) : annotations **CC BY 4.0** et images **déclarées CC BY 2.0**, mais **le producteur ne garantit pas les droits individuels**. La source propose par image `License`, `OriginalMD5`, `OriginalURL`, `Rotation` et pour les boîtes `IsGroupOf`, `IsDepiction`, `IsInside`, `IsOccluded`.

Les **trois fichiers CSV officiels** du préflight :
- `https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv` ;
- `https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv` ;
- `https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv`.

Ces chemins sont publiés dans la page officielle V7 ; **empreintes/volumes avant lecture encore inconnus**, à consigner via la première CI source. Aucune photographie, vignette, catégorie ou URL individuelle n'est enregistrée dans les artefacts de sortie. Aucune GT/média n'est importée dans le dépôt.

## Réutiliser / adapter / créer

**Réutiliser** les sept classes prioritaires du protocole PER-YOLOX-SM-0, les garde-fous de provenance et les empreintes Rockchip S/M (sans téléchargement au cours de ce lot). **Créer** un seul lecteur Python source-only et ses tests avec module standard `csv` ; aucune modification de `mediad`, `robotd`, moteur, RKNN, SQLite, Qwen, Yocto ou 19+5+4 archives B10/B11. Le code propriétaire reste OEM.

Les noms exacts `Person,Cat,Dog,Chair,Bottle,Book` sont **candidats**, non encore classe commune prouvée ; `Ball`, `Football`, `Basketball`, `Baseball`, `Tennis ball`, `Soccer ball` sont **variantes à auditer**, sans assimiler arbitrairement `Ball` à `sports_ball` COCO. Le préflight ne définit aucune conversion MID→80 indices utilisable pour des TP.

## Critères et sécurité, fixés avant CI

- **P1 (métadonnées)** : CSV officiel téléchargé avec limites de taille, SHA-256 communiqué, validation présence des six catégories candidates, au moins 1 000 identifiants validation ; compter seulement les rectangles normalisés non vides, annotés humains, sans `IsGroupOf`, `IsDepiction`, `IsInside`, pour images ayant **licence déclarée CC BY 2.0**, orientation originale 0°, MD5 présent et URL HTTPS. Publier **les comptes agrégés** des labels, jamais les IDs/URLs/auteurs/boîtes.
- **P2 (tests fixtures)** : acceptation de boîtes et de licences saines ; refus d'images dupliquées, classes incomplètes, chemin symlink, champs/coordonnées cassés ; exclusion de licences non compatibles et de représentations/dessins/groupes. Tous les workflows CI du dernier SHA verts.
- **N1 droits** : la déclaration CC BY 2.0 dans un CSV **n'est PAS une vérification indépendante du droit de chaque auteur** ; même après P1, le pool reste **non qualifié pour un benchmark commercial** sans vérification supplémentaire.
- **N2 identité** : les IDs Open Images et COCO sont de **domaines différents** ; une coïncidence JPEG ou URL avec les 1 316 anciens clichés COCO reste **inconnue** tant que le hash/URL par image n'a pas été vérifié AVANT nouvelles inférences. Ne pas présenter la séparation numérique des IDs comme une indépendance.
- **N3 classe** : ballon générique ou sous-type ≠ preuve de `sports_ball`, une image GT sans détection ne prouve pas un faux positif physique. Dépiction de vivant ≠ vivant réel.
- **N4 environnement** : si la source est inaccessible, si des colonnes ou MIDs manquent, si les tests/CI sont rouges, ou si les droits sont insuffisants, **STOP du benchmark** et conservation des seuls constats négatifs.

**Succès borné de ce lot** : inventaire source et licence indépendamment du modèle **ou STOP prouvé**. Aucune inférence réelle, comparaison de rappel, vision RK3566, 2/1,5/1 Hz, suivi, autonomie, mobilité ou effet causal revendiqué. Le [plan OEM 2 Hz](perception-oem-rknn-2hz-plan-2026-10-29.md) et les portes VIS-FOCUS-A2 / EX4-C2 restent en vigueur.

**Retour arrière :** fermer la PR sans fusion si preuves impossibles ou CI non verte. Aucun robot/secret/photo privée touché.
