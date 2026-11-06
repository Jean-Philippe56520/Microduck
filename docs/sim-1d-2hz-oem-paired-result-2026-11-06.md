# SIM-1D/A — deux séquences OEM MuJoCo à 2 Hz (06/11/2026)

**Verdict : PASS pour la cadence et l'abstention, pas pour la reconnaissance d'une balle.**

Le [run #42241267570](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42241267570), exécuté sur le commit expérimental `f579d9e05de57a9f7862c94231ef72c706f8b021`, a réussi les deux sessions de dix cycles sur les vrais démons constructeur simulés `mediad`, `robotd`, `tofd` et MuJoCo. L'essai suit le [protocole préenregistré](sim-1d-2hz-oem-paired-preregister-2026-11-06.md). Le premier run #42240917738 avait échoué avant la simulation à cause d'une virgule dans une expression Python ; corrigé sans changer les critères. Huit tests PC-fixtures de cadence et STOP ont ensuite réussi.

| Mesure | `scene_ball.xml` / `HOME` | `scene.xml` / `SIT` |
| --- | ---: | ---: |
| Cycles complets et départs dans la fenêtre prévue | **10/10** | **10/10** |
| Horodatages caméra strictement croissants | **10/10** | **10/10** |
| Intervalle caméra médian / maximum | **497,3 / 568,6 ms** | **495,6 / 566,7 ms** |
| Cycle total, médiane / maximum | 116,1 / 195,9 ms | 100,4 / 137,8 ms |
| Inférence YOLOX CPU, médiane / maximum | 21,434 / 39,488 ms | 23,459 / 29,352 ms |
| Âge d'image à décision, médiane / maximum | 41,5 / 78 ms | 39 / 69 ms |
| Captures avec au moins une région hypothétique | **9/10** | **0/10** |
| Intention F2 `inspect unknown` | **5/10** | **0/10** |
| Intention F2 `idle` | **5/10** | **10/10** |
| Commandes moteurs et écritures d'expérience | 0 / 0 | 0 / 0 |

Les dix scores YOLOX maximaux, **non validés sémantiquement**, dans la scène avec balle : `0,857409 ; 0,762006 ; 0,426195 ; 0,257687 ; aucune région ; 0,884927 ; 0,834900 ; 0,807421 ; 0,768300 ; 0,852873`. Dans le témoin vide : aucune région sur dix images. Le seuil F2 **0,80** est resté inchangé. La **caméra constructeur rend à 30 FPS** ; l'analyse de Kwipi a eu **un départ toutes les 500 ms**, pas une caméra réglée à 2 FPS.

## Ce que la réussite ne prouve PAS

- **Confondant de pose** : le cas « balle » démarrait à `HOME` et le cas « vide » à `SIT`. Les deux vues et postures diffèrent ; l'écart **9/10 contre 0/10 n'est pas attribuable causalement à la balle**. Le comparateur à pose identique `scene.xml/HOME` doit être préenregistré séparément.
- **Vérité image absente** : `scene_ball.xml` contient bien une balle physique dans l'XML, `scene.xml` n'en contient pas, mais la caméra `mediad` ne fournit pas de masque indépendant ni d'identifiant synchronisé au pas MuJoCo. Sa visibilité dans les pixels est **INCONNUE**. Les 9/10 ne sont ni des vrais positifs, ni un score de reconnaissance, ni une métrique IoU/FP/FN.
- Dix timestamps distincts ne garantissent pas dix contenus de pixels distincts. La source du socket n'est pas un capteur physiquement authentifié. La fidélité au robot, la charge thermique, le RKNN/NPU et l'autonomie batterie restent inconnus.
- F2 reçoit ses hypothèses via **projection mock** et une `ExperienceMemory(':memory:')` éphémère sans écritures ; aucune preuve de suivi d'identité, rappel, progrès mémoire, geste OEM achevé ou effet indépendant.
- Plugin GStreamer du PC Pollen Reachy **v0.14.4**, SHA256 `3045989c437be6f7859262f1970c550d6fc92d9ea9b59e49a05d5ec7bc4afbe9`, distinct du constructeur Microduck **v0.15.3**. OEM et sous-modules inchangés. La cible V1 à 95–100 % n'est PAS mesurée.

**Prochaine porte SIM-1D/B** : d'abord comparer `scene_ball/HOME` à `scene/HOME` avec une nouvelle cohorte *préenregistrée*, sans modifier ni modèle ni seuil. En parallèle, examiner si les API OEM permettent un appariement indépendant des images à une vérité MuJoCo temporelle (sinon `UNKNOWN`). Puis seulement évaluer réellement des objets visibles/hors champ et scènes inédites, la continuité 2 Hz et le rappel SQLite sans récompense causale inventée.

Reproduction : `.github/workflows/sim-1c-oem-live-camera.yml` via `workflow_dispatch` option `run_sim1d` ; garde SHA, ports locaux filtrés, aucune image, poids ou souvenir archivé. Preuves numériques dans l'artefact `sim-1c-oem-live-metadata-only` du [run #42241267570](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42241267570). Aucun moteur Companion commandé.
