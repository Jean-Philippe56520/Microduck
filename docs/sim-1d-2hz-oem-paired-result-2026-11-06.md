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

## Correctif de revue dans la même PR #324 — provenance de lancement

**Manque démontré après l'essai historique :** [revue 4494236533](https://github.com/Jean-Philippe56520/Microduck/pull/324#discussion_r4494236533). Le collecteur initial déduisait `world_contains_ball_xml` du seul argument `--world-case`. Une étiquette erronée pouvait donc accompagner une cadence correcte. Les vingt cycles ci-dessus restent des mesures historiques de cadence ; leur JSON ne vérifiait pas lui-même le monde actif. **Ne pas leur attribuer rétroactivement la nouvelle vérification ni les rejouer pour ce correctif.**

[Critères fixés avant code](https://github.com/Jean-Philippe56520/Microduck/pull/324#issuecomment-6688898539) : cas positif cohérent ; refus des labels inversés, PID périmés, ports/sockets croisés, options ambiguës et changements de contexte. Le correctif réutilise les pidfiles du lanceur OEM, `/proc`, les ports d'écoute existants et `SO_PEERCRED` des sockets déjà servis. Aucun RPC moteur, second flux caméra, service, modèle, dépendance ou mémoire ajouté. Le petit contrôle expérimental `sim1d_launch_context.py` est distinct de toute authentification physique.

Le collecteur contrôle maintenant, **avant toute acquisition/inférence puis après la série**, les deux pins et l'absence de modification suivie, les exécutables et arguments du body/robotd/mediad, les PID avec leur instant de démarrage, les propriétaires des sockets et des deux ports du body, le chemin et l'empreinte du XML. `world_case_requested` reste une demande ; `world_contains_ball_xml` ne décrit que le XML du contexte de lancement contrôlé. Une preuve manquante donne `STOP_ACTIVE_WORLD_UNVERIFIED` avant le premier cycle ; une différence finale donne `STOP_ACTIVE_WORLD_CHANGED`, même après dix cycles. Le contexte non confirmé laisse le contenu du monde à `null`, pas à une valeur déduite de l'étiquette.

**Tests et portée :** 12 tests locaux du contrôle ont réussi, comprenant fixtures d'arguments et de provenance, et trois tests de primitives Linux avec vrais sockets/processus de test, **sans démons OEM**. Le collecteur possède 11 tests, dont trois nouveaux refus avant acquisition/après changement/perte de contexte ; leur exécution avec tous les imports réels est à vérifier dans la CI du nouveau SHA. Les quatre blobs Python publiés sont identiques aux fichiers locaux contrôlés. Pas de nouvelle mesure MuJoCo, d'inférence, de caméra, NPU ou robot dans ce correctif. Une CI logicielle verte ne vaut pas qualification du contrôle dans une session OEM.

**Audit utile pour SIM-1D/B :** `microduck_rl@b02fdea4` transmet longueur + UYVY, sans identifiant de rendu ni pas MuJoCo. `mediad/src/frame.rs` a le même blob `80f23c59dff7c03c718a0f8bb0dc8d3fefa57026` entre le pin `942e58e3` et l'amont contrôlé `4a763dd893f3982c3a11c136468ccf5d26bcc28a` : aucun identifiant MuJoCo ajouté. Les masques de `sim_ball_segmentation_gt.py` sont réutilisables sur instantané statique, mais ne sont pas automatiquement la GT d'une image mediad. **Ni une proximité d'horodatages ni une simple égalité d'empreinte ambiguë ne certifie le même pas.** `HOME` est une initialisation, suivie de l'activation/stabilisation par le lanceur ; une pose réelle identique reste à mesurer.

**Reprise :** contrôler les neuf CI sur le nouveau HEAD de #324 ; fusion seulement après réussite complète, puis confirmer `main`. Ensuite une seule comparaison HOME/HOME préenregistrée, avec qualification du nouveau contrôle dans cette session et recherche d'une vérité visuelle indépendante ; aucune métrique de reconnaissance avant appariement démontré. Le contrôle de lancement ne prouve ni l'état complet en RAM, ni la pose caméra, ni la visibilité d'une balle. Retour arrière : retrait du correctif candidat en conservant l'absence de preuve explicite, jamais suppression d'une garde pour obtenir PASS. Sous-modules, modèles et sécurité inchangés.
