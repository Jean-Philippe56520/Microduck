# SIM-1D/B1 — comparaison OEM balle/vide avec initialisation HOME commune (07/11/2026)

**Verdict limité : `PASS_MATCHED_HOME_INITIALISATION_ONLY`**, pas une reconnaissance sémantique ni une vérité visuelle temporelle. Exécution OEM MuJoCo du **06/11/2026** : [run GitHub Actions #42257829878](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42257829878), `success` sur le commit de workflow `37012f3cab28b8cc5fc160e7460dc4c801b479bd`. Base au lancement : `main@7e966b7464cbacff4f126af1b2d7763f68516627` après fusion de #324. [Préenregistrement figé avant essai](sim-1db-home-control-preregister-2026-11-06.md) : commit `d4c7b1d77a63cb8649496e53344fc3af57824d8e`.

L'artefact **uniquement JSON numériques** `sim-1c-and-1d-oem-metadata-only`, ID GitHub `13524625440`, SHA256 archive `873ae9debac17945a3d8e72c14ba9bd9871e78bb84b343efee09c75afb130c52`, comprend les deux séries, deux négatifs et `sim-1db-home-pair.json`. Rétention annoncée jusqu'au 13/11/2026 ; les chiffres nécessaires sont reproduits ici. Ni pixels, ni poids, ni base SQLite dans cet artefact.

## Mesures observées (même initialisation HOME, **pas nécessairement** même pose réelle)

| Indicateur | `scene_ball.xml/HOME` | `scene.xml/HOME` |
| --- | ---: | ---: |
| Cycles / départs conformes | **10/10** | **10/10** |
| Timestamps de capture uniques | **10/10** | **10/10** |
| Images contenant au moins une région YOLOX **non vérifiée** | **10/10** | **0/10** |
| F2 mock `inspect unknown` / `idle` | **6 / 4** | **0 / 10** |
| Intervalle de capture médian / max | 470,4 / 566,5 ms | 499,7 / 566,9 ms |
| Inférence YOLOX-Nano hôte CPU médiane / max | 25,753 / 49,994 ms | 27,976 / 38,539 ms |
| Durée totale d'un cycle médiane / max | 125,7 / 296,2 ms | 113,4 / 162,5 ms |
| Âge d'image à décision médian / max | 48 / 196 ms | 53 / 106 ms |
| Commandes moteurs Companion / écritures mémoire | **0 / 0** | **0 / 0** |

Dix scores maximaux **de régions, non de balles reconnues**, dans le monde avec balle : `0,707985 ; 0,817032 ; 0,850406 ; 0,809268 ; 0,805344 ; 0,807341 ; 0,844537 ; 0,642748 ; 0,562554 ; 0,669772`. Le seuil F2 de 0,80, le même Nano ONNX épinglé (`c789161...`), le prétraitement et les gardes de cadence n'ont pas été retouchés. Chaque série a des intervalles compris entre 0,35 et 0,70 s, une médiane entre 0,40 et 0,60 s et une télémétrie `coherent` au sens du collecteur. Cela mesure un départ d'analyse à 2 Hz ; le rendu/capture caméra OEM est configuré indépendamment à 30 FPS.

**Deux négatifs OEM réels** ont volontairement inversé `--world-case` une fois le bon processus HOME lancé : monde balle annoncé vide, puis monde vide annoncé balle. Les deux donnent `STOP_ACTIVE_WORLD_UNVERIFIED`, **0 cycle**, **0 acquisition/inférence**, contenu de monde `null`, aucune commande/écriture. Le contrôle de contexte du collecteur examine le lancement, les PID/démarrages, les ports/sockets, les pins et le XML ; il ne certifie pas l'état complet de MuJoCo en RAM.

## Réutilisation, tests et ce qui **n'est pas** prouvé

- Services réellement exécutés : constructeur épinglé `robotd`, `tofd`, `mediad` et `microduck_rl` MuJoCo ; lecture `media.frame`, Nano CPU et projection F2 **mock**. Le pilote moteur reste exclusivement `robotd`. Zero demande de mouvement **de Companion**, mais `duck-sim` active/stabilise lui-même le robot : zéro commande Companion ne signifie pas robot immobile.
- Le run a validé les tests existants `test_sim1d*.py` (23 tests de contexte/cadence) et les deux séries OEM. Le test ultérieur de synthèse B1 `tests/test_sim1db_home_pair_summary.py` valide 14 cas sur **fixtures locales**, sans simulation : sa présence sur la branche finale ne doit pas être confondue avec une exécution dans le run du 06/11.
- Les deux XML ont été comparés structurellement, décor/robot/lumière communs après exclusion du seul ajout balle et des keyframes inutilisées sous HOME. La comparaison limite donc le biais **de posture initiale** de A, mais ne démontre **ni pose réelle de la caméra identique** ni équivalence de toutes conditions visuelles au moment du rendu.
- **Absence de GT pixel/temps** : `mediad` ne fournit pas d'identifiant de rendu ou de pas MuJoCo. `frame_ball_visibility_known=false`, `pixel_gt_synchronised=false`, `semantic_category_verified=false`, `gt_eligible_for_detection_accuracy=false`. Les 10/10 sont des *candidats de région*, jamais TP ni fiabilité de reconnaissance de balle. Pas d'IoU, FP/FN, portée, identité suivie, effet action, apprentissage, autonomie ou score V1. Les écarts 10/10 contre 0/10 ne démontrent pas la cause au niveau de chaque pixel.
- Le plugin GStreamer x86 Pollen Reachy épinglé v0.14.4 reste une compatibilité **PC**, pas le plugin constructeur Microduck v0.15.3 ou une validation de capteur/NPU RK3566. Aucun robot physique disponible.
- Aucun sous-module, pilote, politique OEM, ONNX, seuil, source B10/B11 ou SQLite modifié ; aucune nouvelle dépendance.

## Prochaine porte SIM-1D/B2 (EN ATTENTE DE PREUVE)

**Besoin précis :** attacher à chaque image réellement retournée par `mediad` une vérité géométrique MuJoCo **indépendante de YOLOX**, issue du **même rendu** ou d'un appariement bijectif démontré, avec conservation d'un identifiant/empreinte non ambigu, de la pose caméra et de la visibilité géométrique. Les masques de `sim_ball_segmentation_gt.py` sont déjà utilisables sur un instantané **statique**, pas encore dans le flux dynamique des vingt images B1.

Avant toute instrumentation : auditer le rendu `Camera.render` et `mediad` épinglés, les effets sur la boucle OEM 50 Hz, les ressources et la confidentialité. Définir positifs visibles et négatifs hors champ / distracteurs, refus pour trame sans appariement, déplacement du monde, hash dupliqué et différence de pose ; conserver un témoin non instrumenté. **Aucun patch OEM ni monkeypatch de la chaîne constructeur autorisé implicitement par B1** ; toute modification d'exécution devra être séparément évaluée et qualifiée comme simulation instrumentée, et non source OEM intacte. Si les interfaces ne fournissent pas cette preuve : `GT_UNKNOWN` explicite, pas de score de reconnaissance.

**Retour arrière :** retirer le mode B1 expérimental si nécessaire, conserver les mesures publiées et les barrières de provenance. Pas de relance des vingt cycles déjà passés sans raison nouvelle. Étapes suivantes : exact appariement visuel, scènes nouvelles, attention temporelle, mémoire on/off, action OEM terminée + effet indépendant, puis matrice V1 à 95–100 % des scénarios avec 100 % des gardes critiques satisfaites (non atteinte ici).
