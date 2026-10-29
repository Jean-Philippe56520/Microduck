# SIM-VIS-B — balle visible, segmentation MuJoCo indépendante (29/10/2026)

**Statut :** test dans le véritable modèle OEM MuJoCo épinglé et sur les véritables poids YOLOX-Nano Cat-A ; test de géométrie visuelle **réussi**, critère de reconnaissance **NON ATTEINT**. Aucun robot physique.

## Porte 0 : manque prouvé et expérience bornée

- **Manque :** SIM-VIS-A1b [#181](https://github.com/Jean-Philippe56520/Microduck/pull/181) avait bien envoyé une image MuJoCo à YOLOX mais produit 0 boîte, **sans savoir si les 3 balles du monde étaient visibles**. Il était impossible de conclure sur la reconnaissance de balles.
- **Objectif :** obtenir une vérité terrain au pixel **indépendante de YOLOX**, pour une balle réellement visible, et mesurer le résultat du détecteur **sans aucun réentraînement ni tuning**.
- **Réutiliser :** `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` : `scene_apartment.xml`, `Body`, `World`, `Camera` (retournement optique constructeur), `mujoco.Renderer` RGB+segmentation ; modèle OEM `microduck@942e58e3aa6dbb28e7037203fff11866122c7567` pin vérifié. Companion : `cata_yolox_categories.prepare_image`, `validate_model_file`, `cata2_bbox_eval.decode_boxes`/`iou`.
- **Adaptation minimale :** `microduck_companion/sim_ball_segmentation_gt.py` capture une image RGB et une segmentation géométrique **au même état figé** (hash `qpos` et temps vérifiés inchangés), les redresse toutes deux de 90° et évalue les boîtes YOLOX sur des labels de géométries MuJoCo `mjOBJ_GEOM`. Ni nouveau moteur, ni nouveau modèle/driver/daemon, ni sous-module modifié.
- **Licences :** code/modelés RL/actifs sous leurs licences constructeurs (voir `microduck_rl/pyproject.toml` et `LICENSE-MODELS.md`), **utilisation dans CI sans recopier les fichiers** ; poids publics Megvii/YOLOX-Nano Apache-2.0, digest SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`.
- **Test prévu avant résultat :** robot placé par `qpos` à yaw 90° en pose OEM, 3 balles **derrière** la caméra (négatif) ; puis `ball_0_geom` (rayon constructeur 40 mm) placé **0,55 m devant la caméra**, base à hauteur de sol, 2 autres balles derrière (positif). Pas de `mj_step`, pas de commande `robotd`. Segmentation positive ≥80 pixels et négative =0 obligatoires ; proposition `sports_ball` avec IoU ≥0,50 pour succès de reconnaissance ; seuil YOLOX 0,25 inchangé.
- **Arrêt :** si segmentation de l'objet absente/mal alignée, stop. Si YOLOX ne le détecte pas, conserver le faux négatif ; aucun déplacement de la balle, tuning ou nouvelle scène opportuniste après résultat.

## Mesures réelles — [GitHub Actions #40927477247](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40927477247)

| Critère | Témoin négatif (balles derrière) | Témoin positif (balle au sol devant) |
| --- | ---: | ---: |
| Pixels de balle dans segmentation OEM | **0** | **3 352** |
| Boîte visible indépendamment | Aucune | **[148, 455, 212, 523]** (64×68 pixels) |
| Boîtes `sports_ball` proposées par YOLOX | **0** | **0** |
| Paires IoU ≥0,50 | 0 | **0** |
| Faux positifs `sports_ball` | 0 | 0 |
| Faux négatifs `sports_ball` | 0 | **1** |
| Inférence ONNX CPU sur runner | 22,832 ms | 21,031 ms |

La CI dédiée a confirmé les empreintes Git des 2 sous-modules, les poids SHA-256, le chargement MuJoCo avec **vraie caméra constructeur**, le rendu RGB et la segmentation dans un état statique constant, ainsi que les tests unitaires des boîtes et de l'appariement un-à-un. La CI est **verte pour la qualité du protocole**, mais le rapport retourne explicitement `ball_classification_gate_met=false`. Ce résultat est **un échec de détection dans une vue synthétique donnée**, pas une preuve qu'aucun détecteur ne peut fonctionner, ni une mesure sur des vraies photos à faible hauteur.

L'orientation source est un test **contrôlé** : ce n'est pas la posture de la marche ni une scène choisie spontanément. Un objet de 8 cm est prépositionné exprès au sol dans le champ ; aucun apprentissage, comportement exploratoire ou causalité n'est démontré. Les pixels/mémoires/photos privés ne sont pas archivés ; le rapport CI ne comporte que les coordonnées, tailles, temps et SHA de rendus synthétiques.

## Séparation des validations et décision

- **Prouvé (MuJoCo OEM statique)** : une balle réellement visible, la localisation pixel indépendante, le pipeline YOLOX et **un faux négatif** au seuil inchangé.
- **Non prouvé** : images de `mediad.media.frame`, invariance temporelle / 50 Hz simulés, GT des 29 photos réelles, généralisation multi-scènes/multi-angles, NPU RK3566, navigation, toucher/déplacement de balle, cause et effet, robot physique.
- **État OEM** : [#181](https://github.com/Jean-Philippe56520/Microduck/pull/181) garde `mediad` bloqué (plugin `webrtcsink` indisponible pour le runner x86) et la simulation OSMesa précédente seulement 0,42× temps réel ; ce lot statique ne revendique pas leur résolution.
- **Décision STOP** : ne pas modifier modèle/seuil/scene sur ces mêmes images. L'analyse ultérieure de généralisation exige des vues indépendantes pré-déclarées ; en attendant, B/C (Qwen/ExperienceMemory) restent des jalons indépendants et Cat-A2b #78 réclame des contre-annotations humaines réelles. Pas de nouveau sous-module ou pilote.

**Retour arrière :** retirer uniquement `sim_ball_segmentation_gt.py`, son test et le workflow `sim-vis-b-ball-gt.yml`. Aucune donnée robot ou media privé sur GitHub.
