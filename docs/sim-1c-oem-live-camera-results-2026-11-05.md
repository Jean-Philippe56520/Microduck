# SIM-1C — Première exécution intégrée OEM MuJoCo / mediad / YOLOX / F2 (05/11/2026)

## Verdict exact

**`PASS` limité au trajet logiciel réellement exécuté sur GitHub Actions.** Ce n'est **pas** la réussite perceptive d'une balle et ne compte **aucun** scénario V1 dans une cible 95–100 % avant acquisition du robot.

- Run réussi : [#42038791808](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42038791808), SHA de la branche de test `94a6ae30a1c52d01786bbce4f1dd221bb11f07b1` ; GitHub Actions `live-camera` **SUCCESS**, démarrage OEM, `media.frame`, inférence CPU réelle, F2 mock, nettoyage et export JSON.
- Préenregistrement : [SIM-1C avant exécution](sim-1c-oem-live-camera-preregister-2026-11-05.md). Une seule scène constructeur `scene_ball.xml`, option constructeur `DUCK_SIM_KEYFRAME=HOME` après échec `SIT` documenté ; aucun XML, modèle, score ou sous-module retouché.
- Pins prouvés : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. `robotd`/ `tofd`/ `mediad` issus du checkout OEM ; signal capteur seulement *revendiqué par socket Unix*, pas cryptographiquement authentifié.
- Distinction C3 : plugin x86 Linux signé par empreinte SHA256 `3045989c437be6f7859262f1970c550d6fc92d9ea9b59e49a05d5ec7bc4afbe9` du dépôt Pollen `reachy-mini-desktop-app@c6ea61a5d57dc069e01aab07c723402b3d8263f5`, GStreamer **0.14.4**. Le constructeur Microduck épinglé utilise **0.15.3** en version robot : ce test n'affirme **pas** la parité de plugin. Aucune dépendance vendue ou intégrée à Yocto ; ports de console/WebRTC entrants filtrés dans le runner.

## Mesure positive réelle et témoin

| Chaîne observée | Donnée mesurée | Ce que cela ne prouve pas |
| --- | --- | --- |
| Premier `mediad.media.frame` | 640×360, **460 800 octets UYVY**, rotation 90°, horodatage `1793886631344212` µs, identité socket UID 1001 seulement observée | processus authentifié, catégories, GT, image robot |
| Deuxième trame consommée par YOLOX | capture `1793886631677612` µs ; **0,3334 s** après la première ; âge à la décision **0,102 s** | cadence 2 Hz soutenue, même pas MuJoCo que `robotd/tofd` |
| Qualité lecture OEM | `telemetry_quality=coherent` : gardes existantes de sûreté et de fraîcheur satisfaites pour ce cycle | sol traversable, perception de surface, autonomie |
| YOLOX-Nano hôte CPU | poids SHA `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` ; **10,212 ms d'inférence sur un seul appel** | p95/fps, coût conversion+prétraitement, RKNN/NPU/thermique |
| Propositions spatiales | **1 région** ; score **0,402887**, indice COCO non vérifié **25** ; boîte en image redressée 360×640 `[0.1623,24.2949,359.2639,619.4819]` | objet physiquement présent, balle ou catégorie correcte, vrai positif |
| Décision `AutonomyBrain` F2 via projection **mock** | `idle`, raison `no_high_scoring_passive_attention` ; **0 région ≥0,80** | apprentissage, identité, effet d'action |
| Contrôles d'action/écriture | **0 commande moteur Companion**, **0 écriture d'expérience**, `semantic_category_verified=false`, `same_mujoco_step_verified=false` | validation sûre d'un acte réel, autonomie fonctionnelle |

**Interprétation :** Kwipi a reçu des pixels réels de son simulateur constructeur, le modèle existant a produit un signal spatial faible et le cerveau existant s'est abstenu. **Aucune balle n'a été localisée ou reconnue avec GT indépendante** dans cette campagne. La première et la deuxième capture sont distinctes ; leurs timestamps ne prouvent aucun alignement avec l'état `robotd` ou la vérité MuJoCo.

**Témoins déjà existants :** SIM-VIS-D = rendu + masques MuJoCo **statiques**, 1/2 localisations positives, F2 en mock ; X2-C = télémétrie des démons OEM **sans caméra** et 0/6 gain cognitif de mémoire. Ces observations ne sont **pas** remplacées ni comptées deux fois. Aucun essai sur robot physique.

## Échecs observés et leurs causes — conservés

1. [#42036945613](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42036945613) : mauvais endpoint Git LFS renvoyant **133 octets de pointeur** au lieu de 11 367 544 octets ; contrôle SHA refuse le plugin. Nouvelle URL **exacte de l'action Pollen**, même SHA, pas de dérogation.
2. [#42037384120](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42037384120) : constructeur `duck-sim up` ne démarre pas `body_server`, aucun pixel.
3. [#42038074738](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42038074738) : `body.log` récupéré, erreur explicite `no keyframe 'SIT' in scene_ball.xml. It has:`. Le fichier OEM `scene_ball.xml` ne déclare effectivement pas de keyframe. Correction **du seul argument d'essai** `DUCK_SIM_KEYFRAME=HOME`, prévu dans `pose_table()` OEM, avant relance ; aucune image/détection de la scène ratée.
4. [#42038791808](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42038791808) : démarrage constructeur `HOME`, capteur et cognition F2 **PASS** dans les limites ci-dessus.

## Suite et porte de succès

**SIM-1D avant toute revendication perceptive** : préenregistrer des scènes OEM *nouvelles*, positives et négatives, incluant visibles/hors champ et distracteurs. Obtenir d'abord une **vérité indépendante de la prédiction et correctement associée au temps de capture de `mediad`** ; si ce couplage n'est pas démontrable sans modifier l'OEM, marquer `UNKNOWN` et ne pas chiffrer IoU/TP/FP/FN. Témoin même séquence **sans mémoire**, puis mémoire SQLite unique avec correction prudente ; observer plusieurs cycles à 2 Hz initiaux, pertes de cible, inaction et gardes de sûreté, sans glissement d'identité. Ne pas retoucher le détecteur, le score, la scène d'évaluation ou les politiques pour obtenir un résultat favorable.

**SIM-3 toujours bloqué** : motrice `robotd` exclusive, SIM-E2/#101, EX4 fin d'acte + effet indépendant ; aucune revendication de marche autonome, kick autonome, vrai apprentissage ou réussite à 95 %. Sans support NPU/robot réel, ressources physiques et fidélité restent `en attente robot`.

Les preuves JSON anonymisées sont disponibles dans l'artefact `sim-1c-oem-live-metadata-only` du [run réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/42038791808) (rétention 7 jours), **pas de photos ni de modèles téléchargés**. Le protocole pilote reste une expérience reproductible `workflow_dispatch`, pas un service compagnon supplémentaire.
