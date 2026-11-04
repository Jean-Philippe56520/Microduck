# PER-OI-V7-HUMAN-1 — annotations humaines avant les nouveaux JPEG

**04/11/2026.** Préenregistrement AVANT code sur [l'issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6643913709). Base : `main@e4909805644adfe9dbedd9870033a9b016aa7fb5`, PR #309/#311 fusionnées, #310 encore ouverte au début du lot. Autorité : [plan-action.md](plan-action.md).

## Manque et résultat utile

La PR #311 a inventorié trois CSV officiels Open Images V7, **sans JPEG ni modèle**. Les boîtes seules ne permettent pas d'affirmer l'absence d'une classe non annotée. Le [protocole officiel Open Images](https://storage.googleapis.com/openimages/web/evaluation.html) impose trois états par classe/image : **positive vérifiée, négative vérifiée ou inconnue** ; les prédictions des classes inconnues sont ignorées dans l'évaluation, jamais déclarées fausses.

**Gain testable de ce lot uniquement :** croiser les annotations de boîtes #311 avec le quatrième CSV officiel [des labels vérifiés humainement](https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv), et mesurer le nombre de candidats par catégorie ayant à la fois boîte et label positif. Récupération en CI de **quatre CSV seulement**, empreintes fixées pour les trois premiers d'après #311, empreinte du quatrième relevée lors de l'essai. Aucune photo, miniature, poids ou URL individuelle publiée.

## Réutilisation et limites

Le script `experiments/per_oi_v7_human_label_gate.py` réutilise les parseurs CSV, validations de source, MD5 et licences déclarées de #311, sans modifier l'architecture. Sept classes candidates : **Person, Cat, Dog, Chair, Bottle, Book, Tennis ball**. Ce dernier terme est un **sous-type étroit à contrôler** avant assimilation éventuelle à `sports_ball` COCO ; `Ball` ou `Football` ne sont pas arbitrairement promus. Les 1 316 images COCO antérieures et les campagnes Open Images précédentes restent **exclues du futur benchmark**, mais leur disjonction n'est **pas encore prouvée par ce seul audit de métadonnées**.

Les licences `CC BY 2.0` dans la source Open Images ne prouvent **pas les droits de chaque Flickr** : aucune image n'est qualifiée commercialement sans examen de la page originale, des auteurs/conditions, des collisions URL/Flickr, des empreintes binaires et des doublons perceptuels. Hauteur inconnue = `viewpoint_height=unknown`.

## Cas positifs/négatifs et arrêt

- Positif : sept classes avec label humain positif **et** boîte admissible ; labels négatifs distingués des absences ; six images par classe dans des fixtures donnent uniquement `METADATA_42_POSSIBLE_NOT_LICENSED`, avec `cohort_selected=false`.
- Négatifs : label absent et boîte sans label positif, contradiction positif/négatif, source non humaine, licence NC, MD5 en double, bbox `IsDepiction`, `IsGroupOf` ou `IsInside`, coordonnées invalides, MID manquant, empreinte erronée et chemin symlink. **11 tests synthétiques** prévus, avant le téléchargement externe.
- Si moins de **6** positifs vérifiés et boxés pour l'une des sept cibles : `STOP_GT_POOL_LT6_NOT_LICENSED`, **sans remplacer opportunément la classe ou recycler les images**. Sinon : `METADATA_42_POSSIBLE_NOT_LICENSED`. Dans les deux cas : droits individuels et indépendance des anciens corpus **inconnus**.
- Passage du lot : tests PC, CSV officiels et toutes les CI vertes **au dernier SHA**, sans fuite d'ID/photo/URL de média. Échec d'une porte ou CI en attente = **pas de fusion**.

**Aucun score de YOLOX-Nano/S/M n'est produit.** Les FPS RK3566, 2 Hz sur robot, chaleur/RSS NPU, détection depuis une vue basse, focus réel, identité, effets causaux et autonomie restent inconnus. `mediad` demeure propriétaire caméra ; `robotd` seul pilote et protège à 50 Hz ; SQLite, Yocto, archives B10/B11 et sous-modules ne changent pas.

**Suite conditionnelle :** vérifier droits individuels + absence de doublons, geler le roster inédit avant les pixels puis seulement comparer les modèles épinglés Nano/S/M **sur exactement les mêmes JPEG** avec IoU50/TP/FP/FN, tailles apparentes, latence et RSS hôte. Si droits/GT/disjonction manquent : STOP. Retour arrière : fermer la PR sans fusion.
