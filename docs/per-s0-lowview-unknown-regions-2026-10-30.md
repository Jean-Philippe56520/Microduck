# PER-S0 — objets utiles à vue basse sans leur imposer une catégorie (préenregistrement)

**Porte gelée le 30 octobre 2026 AVANT toute inférence PER-S0.** Base `main@dd23cf04fbff49d2b79e1f3abc38a813fc52b63a`, OEM `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, simulation `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Autorités : `AGENTS.md`, `docs/plan-action.md`, `docs/development-reuse-protocol.md`, `docs/kwipi-experiential-learning-plan-2026-10-26.md`, `docs/perception-oem-rknn-2hz-plan-2026-10-29.md`.

## 0. Objectif, manque, témoin et statut

**Question décisionnelle unique :** peut-on localiser **la zone visible d'un objet pertinent absent de nos cinq catégories opérationnelles** (personne/chat/chien/balle/chaise) avec une proposition spatiale YOLOX top3, même lorsque le décodeur usuel à cinq catégories ne fournit **aucune boîte appariée** ? Sans localisation vérifiée, aucune extraction de forme ni liaison à SQLite/Qwen n'est justifiée. Une proposition top3 reste issue d'un modèle COCO **80 classes** ; **ce n'est PAS un détecteur open-vocabulary ni une segmentation d'objet inconnu**. Le canapé peut même être reconnu comme `couch` COCO : « inconnu » signifie uniquement **hors des cinq classes sélectionnées pour Kwipi**, jamais hors de toutes les classes du réseau.

**Preuve passée et gap :** SIM-VIS-C localise des balles sans catégorie, SIM-VIS-D localise une balle mais rate un pilier, VIS-ATT-2 récupère deux cibles chat/chien sur COCO. PER-P3A PP-YOLOE rate un fauteuil à caméra basse et PER-P3B obtient des catégories sur 13 photos non-basses. **Aucun de ces essais ne valide la région d'un canapé/plante/petit cube à vue basse.** Le même YOLOX-Nano préexistant (ONNX SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`, Apache-2.0 déclaré), `cata_yolox_categories.prepare_image`, `cata2_bbox_eval.decode_boxes`, `yolox_attention_candidates.decode_candidates`, NMS/score originaux `0.50 / 0.25`, et géométrie constructeur sont **réutilisés sans modification**. Aucun modèle ajouté, nouveau seuil, capture, second service, mémoire, Qwen ou pilote.

## 1. Cohorte gelée AVANT essai

Caméra `head_camera` OEM MuJoCo, 640×360 natif, redressé en 360×640 par `np.rot90(k=3)` comme SIM-VIS-B. Images RGB et masques MuJoCo `mjOBJ_GEOM` du **même instant figé** avec contrôle `qpos`/temps, GT calculée indépendamment de YOLOX. Un seul passage ONNX par cas. Aucun fichier d'image ou de masque écrit, ni dans l'artefact CI.

**Cinq positifs et un négatif**, toutes poses et cibles différentes des cas de vérité terrain précédemment exécutés, **mais mondes constructeur et optique partagés**, pas de prétention à des mondes physiquement indépendants ni à des photographies réelles :

| Cas figé | Monde OEM | Robot XY / yaw (rad) | Géométrie GT | Manipulation static-qpos avant capture | Rôle |
| --- | --- | --- | --- | --- | --- |
| `office_blue_cube` | `scene_apartment.xml` | (2.15, -0.55), +π/2 | `obj_1_geom` (cube 70 mm) | Déplacer le **joint libre OEM** `obj_1` à 0,50 m **devant l'axe de caméra**, posé à z=0 | Hors 5 classes |
| `living_plant` | `scene_apartment.xml` | (-2.15, -2.70), 0 | `liv_plant` (cylindre) | Aucune | Hors 5 classes |
| `living_sofa` | `scene_apartment.xml` | (-2.65, -0.95), π | Union `liv_sofa_seat` + `liv_sofa_back` | Aucune | Hors 5 classes ; `couch` dans COCO 80 |
| `vslam_cyan_pillar` | `scene_vslam.xml` | (2.20, -0.60), 0 | `vs_pil_c` (cylindre) | Aucune | Hors 5 classes |
| `office_green_ball` | `scene_apartment.xml` | (2.15, -0.55), +π/2 | `ball_1_geom` (sphère) | Déplacer le joint libre `ball_1` à 0,72 m devant caméra, 0,10 m de décalage latéral, z=0 | **Témoin connu** |
| `empty_floor` | `scene.xml` (sol/ciel/robot OEM) | (0, 0), 0 | **aucun objet extérieur nommé** | Aucune | **Témoin négatif**, sans terrain/obstacle ajouté |

Les corps OEM ne sont jamais commandés, aucun `mj_step` ; seule la position initiale des joints libres du simulateur est changée **en RAM**. Les poses de ce lot **n'ont pas été choisies après vision des prédictions de ce lot** ; les cibles elles-mêmes existent déjà dans le monde constructeur. Une cible connue anatomiquement ou géométriquement n'est pas une reconnaissance par YOLOX. Le canapé GT est l'union de ses deux géométries, pas seulement le coussin assise.

**Préflight obligatoire avant chargement ONNX** : gitlinks inchangés, scène et géométries réellement présentes, caméra native 640×360, segmentation int 360×640 après rotation, RGB strictement aligné, pose/horodatage immobiles, **≥80 pixels** par cible visible (5/5), boîtes GT cohérentes, aucun objet extérieur supplémentaire introduit dans le négatif (sol constructeur/robot seulement). Si **un cas** échoue, **aucune inférence** ; rapport `STOP_invalid_geometry`, ne pas déplacer les objets après avoir vu YOLOX.

## 2. Métriques/critères de sélection préfixés

Pour chaque positif : meilleur `IoU ≥ 0,50` entre la **boîte du masque GT** et n'importe quelle région top1/top3/top5 de `decode_candidates` ; comparer aux boîtes du décodeur déjà limité aux cinq classes `decode_boxes` sur **le même tenseur brut**, indiquer confiance et **classe COCO supposée mais non validée**. Les cinq classes opérationnelles ne sont pas des étiquettes de vérité des quatre objets hors cible. Rapporter `recovered_only_by_top3` uniquement si une région top3 atteint IoU 0,50 alors qu'**aucune** des boîtes classées parmi les cinq ne l'atteint. Interdire les TP/FP/AP50 généraux sur une seule géométrie annotée, ainsi que toute déduction de contours, roues, catégories, matière, distance, danger ou réalité physique.

Négatif `empty_floor` : compter les régions top3/5 et les confiances ≥0,80 **sans les décrire comme preuve d'objet extérieur** ; un modèle pourrait voir une partie de son robot ou une structure visuelle. Aucune promotion en `inspect` ou action. Chronométrer inférence et décodage PC, sans extrapoler NPU/RK3566/2 Hz/50 Hz.

**Porte de valeur S0 fixée avant inférence** : les **5/5 GT positives valides** et le négatif valide sont obligatoires ; ensuite **≥2/4 objets hors cinq classes** localisés top3 avec IoU≥0,50, dont **au moins une récupération additionnelle** comparée aux cinq boîtes classées, et **0 région négative de score ≥0,80**. La balle connue est un témoin diagnostique (IoU top3 communiqué) et **non une façon de satisfaire la porte sur objets non connus**. Si la porte échoue, `insuffisant`, **STOP pour l'extracteur de propriétés S1 sur ce détecteur**, aucune optimisation ou relance de ces six vues. Une CI verte prouve que le test a tourné et que ses vérifications sont correctes ; **elle ne prouve pas cette porte fonctionnelle**. Si la porte passe, preuve uniquement « régions intéressantes dans ces quelques scènes MuJoCo », **pas** compréhension réelle, ni adoption modèle.

**Tests négatifs logiciels** : refus GT invalide/missing, positif vide, masque non aligné, contrat des six cas incomplet/désordonné, score ou IoU NaN, sortie de forme invalide, négatif avec géométrie non déclarée ; absence de moteur, Qwen, SQLite, sortie image, source privée et modification OEM. L'absence de vrai écran/photo/animal dans ces mondes est une **lacune de données explicite** : **aucune affirmation de distinction photo/présence physique** ne découlera de cette étude. La comparaison sur les deux photos privées déjà vues n'est **pas** un holdout aveugle.

## 3. Réemploi, ressource, arrêt et retour arrière

Réutiliser `World/Body/Camera` dans `upstream/microduck_rl`, `sim_vis_f_gt_preflight._set_free_joint`, `sim_ball_segmentation_gt.visible_geom_bbox`, `cata_yolox_categories.prepare_image/validate_model_file`, `cata2_bbox_eval.decode_boxes` et `yolox_attention_candidates.decode_candidates/_iou`. **Adapter uniquement** un orchestrateur hôte read-only et des tests de portes (positif/négatif), car l'oracle multi-géométries canapé et la comparaison sur le même tenseur manquent. **Aucun changement de `mediad`, `tofd`, `robotd`, DFL, Qwen, `ExperienceMemory`, gitlink, caméra, poids ou firmware**. Exécution OSMesa CPU isolée, modèle ONNX temporaire vérifié SHA, images et segments uniquement en mémoire, rapports numériques publics sans éléments personnels ; limite CI 20 min.

Retour arrière : supprimer/revert branche expérimentale ; aucune installation robot, aucun schéma SQLite ni paramètre OEM à restaurer. **Après CI**, enregistrer chiffres et décision dans cette note, `README.md`, `docs/plan-action.md`, `docs/roadmap.md` ; fusion seulement avec CI et tests unitaires verts. Les portes S1/M1/Q1 restent séparées et en attente d'un signal réel suffisamment fiable ; les travaux de mémoire/Qwen sur fixtures indépendantes ne sont pas bloqués.

## 4. Résultat exécuté

**Exécuté le 30/10/2026, après le préenregistrement** : [CI OEM/YOLOX #41065887857](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41065887857) **verte**, tête expérimentale `92aa03afe3ef53ec31dd0067a48931d5c77156e3` : tests positifs/négatifs de contrat passés, **6/6 scènes rendues** avec caméra OEM et masques indépendants, **5/5 positifs valides** (≥80 px), négatif sans objet extérieur (ni pixels du robot visibles), et **6/6 inférences YOLOX CPU réellement réalisées** après contrôle SHA. Aucune image ni poids publiée dans l'artefact `per-s0-oem-geometry-and-onnx-numeric-only`.

| Cas gelé | Pixels GT | Boîte parmi les cinq classes IoU≥0,50 | Région top1 / top3 / top5 meilleure IoU | Hypothèse de classe COCO top3 (non confirmée) |
| --- | ---: | --- | ---: | --- |
| `office_blue_cube` | **5 438** | Non | **0 / 0 / 0** (zéro région) | Aucune |
| `living_plant` (cylindre OEM nommé plante) | **31 594** | Non | **0,943425 / 0,943425 / 0,943425** | Index **61 = toilet** (erroné), score **0,470296** |
| `living_sofa` (union assise + dossier) | **52 975** | Non | **0,245016 / 0,245016 / 0,245016** | Index **6 = train** (erroné), score **0,453999** |
| `vslam_cyan_pillar` (cylindre) | **45 746** | Non | **0,940207 / 0,940207 / 0,940207** | Index **37 = surfboard** (erroné), score **0,470187** |
| `office_green_ball` (témoin connu) | **1 918** | Oui, **0,887870** | **0,887870** sur top1/3/5 | Index **32 = sports ball**, score **0,817301** |
| `empty_floor` (négatif) | **0** objet extérieur, **0** pixel robot visible | Non applicable | **0 région** top1/3/5 | Aucune |

**Bilan préfixé : `functional_value_gate_met=true`** — 2/4 hors cinq classes localisés top3 à IoU≥0,50, **2 récupérations complémentaires** vis-à-vis des cinq boîtes classées, zéro région forte ≥0,80 sur négatif ; balle témoin correctement localisée mais exclue du quota. **La porte de test logiciel S0 est franchie dans CES vues OEM simulées.** Les confusions `toilet`, `train`, `surfboard` sont importantes : un objet/région localisé ne justifie absolument **pas de conserver son étiquette** comme « vérité », ni d'inférer forme matérielle complète, usage ou sécurité. Le « plant » OEM est lui-même une **simple primitive cylindrique**, pas une plante botanique détaillée ; aucune démonstration de propriétés d'une vraie plante n'en découle.

**Ressources CPU hôte mesurées** : inférence médiane **12,772 ms/image**, p95 **13,634 ms** ; décodage des boîtes et top1/3/5 médiane **2,855 ms**, p95 **3,146 ms** sur **six images seulement**, hors coût de rendu/MuJoCo et de modèle sur robot. Aucune mesure de consommation RKNN/NPU, RSS RK3566, 2 Hz ou 50 Hz moteur.

**Décision `progres_demontre_PC_MuJoCo_borne`, et NON « objet compris » :** S0 prouve seulement une **possibilité d'attention spatiale `unknown` sur 2/4 objets hors vocabulaire prioritaire** pour ce modèle, et 2 échecs (cube, canapé) très visibles. Cela **autorise l'étude S1** des propriétés visuelles *uniquement* sur des régions réellement appariées et un témoin à masque indépendant. **S1 ne doit pas être déclaré opérationnel** ni créer une fonction de segmentation/forme avant un protocole nouveau et comparatif ; l'étiquette COCO erronée est écartée pour toute future décision. Les négatifs photo/écran, les personnes/animaux, la caméra réelle, la distinction présence physique/représentation et les objets domestiques de type trottinette **ne sont pas testés**. Un seuil passager ne prouve pas une généralisation ; ne pas retoucher/rejouer ces six scènes pour améliorer le score.

**Limite importante d'indépendance :** la cohorte emploie des *poses/cibles nouvelles préenregistrées* mais les **mondes et maillages OEM déjà employés par d'autres études**. Ce n'est pas un corpus public entièrement inédit, ni un test de validité hors simulation. Les deux images privées existantes sont volontairement exclues des jobs GitHub. Aucun sous-module, moteur, caméra OEM ou stockage cognitif modifié. Retour arrière intégral : supprimer ce seul banc expérimental.

