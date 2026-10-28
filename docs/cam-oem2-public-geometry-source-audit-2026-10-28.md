# CAM-OEM-2 — preuve géométrique publique de perspectives basses, sans images

**28 octobre 2026 — audit documentaire et calcul local sur des constantes publiées, non sur la caméra de Kwipi.** Plan directeur : [plan-action.md](plan-action.md). Reprise après CAM-OEM-1 [PR #136](https://github.com/Jean-Philippe56520/Microduck/pull/136) et documentation [PR #137](https://github.com/Jean-Philippe56520/Microduck/pull/137), toutes deux fusionnées ; CI post-fusion #137 [40766536267](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40766536267) verte. Base au début de ce chantier : `main 13699838`, gitlinks OEM `942e58e3` et RL `b02fdea4` inchangés.

## 1. Porte OEM-first : question et critères

**Observation :** le protocole Cat-A2b [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78) exige une perspective basse réelle et une évaluation indépendante des cinq catégories `person/cat/dog/chair/sports_ball`. Le banc Cat-A2c a déjà traité 48 JPEG Open Images avec labels binaires humains, mais **aucune vue à la hauteur de Kwipi n'est attestée**. Le précontrôle CAM-OEM-1 empêche de promouvoir une simple déclaration caméra en validation robot, sans mesurer les différences entre les jeux publics candidats.

**Hypothèse précise :** les jeux « caméra basse » externes ont des différences d'optique, de provenance ou d'annotations suffisantes pour empêcher leur assimilation directe à la caméra IMX219 du Microduck. Les valeurs optiques publiées peuvent être comparées mathématiquement **sans** importer les images ou ajuster le modèle.

**Preuve visée :** comparer les angles horizontaux et verticaux à partir des `fx/fy` CID-SIMS publiés, différencier les deux hauteurs d'observation et les deux intensités lumineuses TiROD, vérifier la correspondance de noms de classes et consigner les droits qui restent inconnus. Tests négatifs des dimensions, focales et angles invalides. Aucun débit/latence RSS, fidélité de détection, calibration du robot ou preuve de terrain n'en découle.

**Critères d'arrêt :** prétendre à une calibration individuelle ou à une précision YOLOX; inférer 25 cm de hauteur optique à partir de la taille du robot; transformer `TiROD/Low` en hauteur basse; mapper `ball` vers COCO `sports_ball` sans preuve; traiter la disponibilité publique ou Apache-2.0 du code tiers comme une licence des images; créer des boîtes depuis un masque non contrôlé; télécharger des médias privés ou exécuter un moteur. **Risque principal : fausse transférabilité.** Retour arrière : supprimer le seul script d'audit, ses tests et les notes CAM-OEM-2, sans restauration OEM/SQLite/ONNX.

## 2. Sources exactes et choix réutiliser / adapter / créer

| Source | Référence lue et provenance | Décision |
| --- | --- | --- |
| OEM `mediad/src/sensor.rs`, `mediad/src/camera.rs`, `robotd-params/src/board.rs` | [microduck@942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) ; Zero3 IMX219 ~62° horizontal nominal, Beta GC2093 HFOV inconnu, montages 90°/0° | **Réutiliser** les chiffres familiaux, jamais comme une mesure de l'exemplaire |
| `src/mjlab_microduck/sim/camera.py` | [microduck_rl@b02fdea4](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3) ; rendu 640×360/15 fps ; géométrie `mediad` de twin fovy 45° | **Distinguer** de toute caméra physique |
| CID-SIMS site et calibration | [CID-SIMS@9e7610ab](https://github.com/CID-SIMS/CID-SIMS.github.io/tree/9e7610abf8320062cf810484dd0fc4fdb58682ae) ; [`calibration.yaml`](https://github.com/CID-SIMS/CID-SIMS.github.io/blob/9e7610abf8320062cf810484dd0fc4fdb58682ae/calibration/calibration.yaml), blob Git `52daae23`; [overview](https://github.com/CID-SIMS/CID-SIMS.github.io/blob/9e7610abf8320062cf810484dd0fc4fdb58682ae/overview/index.html) | **Réutiliser** les chiffres publiés (pas les images). Les prises 12/26 cm sont approximatives; le capteur est un Intel RealSense **D455**, pas un IMX219 |
| TiROD classes et protocole | [TiROD_code@ca74712c](https://github.com/pastifra/TiROD_code/tree/ca74712c857e63956e608626c3ab0967a6373522) : [`eclod/cfg/TiROD.yml`](https://github.com/pastifra/TiROD_code/blob/ca74712c857e63956e608626c3ab0967a6373522/eclod/cfg/TiROD.yml), [README](https://github.com/pastifra/TiROD_code/blob/ca74712c857e63956e608626c3ab0967a6373522/README.md) ; ESP32-CAM, 640×480, 13 classes, `High/Low` = éclairage | **Candidat seulement pour `chair`**, pas cinq classes, pas hauteur/optique comparables démontrées. La licence Apache-2.0 du **code** ne donne pas des droits sur chaque image |
| Companion Cat-A2b #78 / Cat-A2c #123 / CAM-OEM-1 | [protocole privé](cata2b-private-low-camera-protocol-2026-10-26.md), [mesure publique](cata2c-real-openimages-holdout-2026-10-28.md), [garde déclaratif](cam-oem1-camera-fidelity-2026-10-28.md) | **Réutiliser sans modifier.** Aucune nouvelle DB, capture, modèle ou moteur |
| Communauté QuackNav/brain, Quacksat, Twin, GC/Smartulf, Lab/Studio | [registre tiers](community-reference-registry-2026-10-26.md) | **Ne pas intégrer** : aucun besoin d'un second pilote, d'un détecteur ou d'un moteur pour comparer une optique publiée |
| `scripts/cam_oem2_public_optics_audit.py` et tests | Calcul Python standard-library **hors service** sur constantes revues et SHAs explicitement figés | **Créer seulement un calcul reproductible**, sans entrer dans le wheel normal ni modifier CAM-OEM-1 |

## 3. Résultat mathématique reproductible

Modèle **pinhole sans correction de distorsion** : `FOV = 2 atan(taille_image_px / (2*focale_px))`. Pour une caméra simulée définie par FOV vertical et rapport largeur/hauteur : `HFOV = 2 atan((W/H) tan(VFOV/2))`. Ceci ne mesure ni l'étalonnage réel ni l'ISP.

| Référence | Résolution / valeurs utilisées | Champ horizontal | Champ vertical |
| --- | --- | ---: | ---: |
| Microduck Zero3/IMX219, **nominal/familial** | sortie de référence 1280×720, HFOV annoncé 62° | **62,000°** | **37,349°** calculé à rapport 16:9 |
| Microduck Beta/GC2093 | capteur 1920×1080, pas de calibration publiée au pin | **inconnu** | **inconnu** |
| CID-SIMS/RealSense D455, **calibration source** | 640×480 ; `fx=386.5219919`, `fy=387.3230043` | **79,242°** calculé | **63,568°** calculé |
| MuJoCo twin, **rendu virtuel** | 640×360, VFOV par défaut 45° | **72,734°** calculé | **45,000°** |

**Écarts descriptifs** : CID-SIMS ≈ **+17,242°** horizontaux par rapport aux 62° nominaux IMX219 ; MuJoCo ≈ **+10,734°**. Le recadrage ou la réduction d'une image ne recréent **ni la perspective d'un centre optique différent ni les distorsions d'une autre lentille**. Les angles issus de CID sont calculés avec `fx/fy` et non corrigés pixel par pixel de `cam_d`. Le 62° IMX219 n'est pas un étalonnage de Kwipi.

## 4. Pourquoi aucun score Cat-A2b n'est publié

| Candidat | Données utiles établies | Limite empêchant la validation Kwipi |
| --- | --- | --- |
| **CID-SIMS** | Deux points de vue annoncés ≈12 et ≈26 cm, scènes intérieures, calibration optique D455, annotations sémantiques annoncées | Objectifs/classes COCO cinq catégories, boîtes et relectures humaines indépendantes non démontrés sur la cohorte; droits d'usage et licence exacte **non confirmés** à la source examinée; FOV/objectif distincts; vues par image à sélectionner; séquences temporelles ≠ scènes indépendantes |
| **TiROD** | Petit rover, images 640×480, boîtes COCO, cinq environnements et éclairages haut/bas, treize catégories; correspondance nominale **chaise uniquement** | `Low` désigne la lumière; hauteur optique, FOV, calibration et droits médias non attestés; `ball` n'est pas démontré équivalent à `sports_ball`; pas de labels `cat/dog/person` dans la configuration TiROD |
| **Open Images V7 déjà évalué (#123)** | 48 vraies photos et étiquettes humaines de présence/absence, scores honnêtement publiés | Hauteur/optique inconnues, vérité image binaire ≠ boîtes ni performance sur Kwipi |

**Licence :** le dépôt du *code* TiROD présente Apache-2.0, mais la licence des *pixels* des images téléchargeables et leur consentement restent à confirmer sur l'enregistrement du jeu lui-même. Pour CID-SIMS, le portail annonce téléchargement et citation sans que les pages inspectées établissent les droits exacts des JPEG et de leurs sujets. **Aucune photo téléchargée, redistribuée ni inférée** dans ce lot.

## 5. Tests, preuve et décision

`python -m unittest discover -s tests -p 'test_cam_oem2_public_optics_audit.py' -v` : **7 tests host-only locaux réussis** sur Python 3.13 : résultats calculés, conformité de noms, absences de licences/hauteurs/calibration, négatifs `nan`, `inf`, angles et pixels incohérents, imports limités à `json` et `math`. `python -m scripts.cam_oem2_public_optics_audit` retourne uniquement un JSON agrégé sans identifiant personnel ni image. **La CI GitHub finale de la PR et la CI post-fusion doivent être contrôlées séparément** ; ces sept tests ne mesurent ni précision de détection ni ressources du robot.

**Décision : NO-GO** pour qualifier CID-SIMS ou TiROD de « test représentatif de la caméra Kwipi ». **GO seulement** pour la comparaison optique publique **descriptive**. Ne pas multiplier les outils qui reconstitueraient une fausse vérité terrain. Porte Cat-A2b #78 inchangée : identifier la carte/capteur et les paramètres `mediad` réellement actifs, mesurer la hauteur du centre optique, créer de vraies captures distinctes avec consentement, obtenir deux relectures indépendantes, mesurer la confusion, puis auditer NPU/latence/RAM/température et maintenir la sûreté `robotd`. En attendant, avancer sur C3-B ou Qwen **uniquement** avec les scènes réellement autorisées et une vérité indépendante, jamais en attribuant une causalité à des fixtures.