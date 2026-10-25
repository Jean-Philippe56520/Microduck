# P0b — Comparaison repos / marche dans le MuJoCo officiel (25 octobre 2026)

**Périmètre : simulateur officiel épinglé uniquement.** Ce document conserve les résultats du [workflow MuJoCo #40187514292](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514292) de la [PR #12](https://github.com/Jean-Philippe56520/Microduck/pull/12). La réussite du workflow est une réussite **technique d'instrumentation**, pas une validation de la locomotion.

## Sources et conditions

- Révision `microduck_rl` : `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, scène `scene.xml` contrôlée par empreinte Git, processus headless `body_server` et daemon `robotd` constructeur non modifiés.
- `robotd` reste seul responsable des moteurs et de la sélection des politiques. La commande de marche réutilise **un** essai J2e existant, **24 notifications à 0,12 m/s**, plus `robot.stop` exigé et reconnu. Deadman constructeur inchangé.
- P0a lit les mesures sans aucune commande : `hello`/`read` au simulateur et `robot.subscribe` au daemon. P0b ajoute un crochet de lecture **dans** la section à arrêt garanti de J2e, sans accès aux actuateurs.
- Baseline **16** observations à **10 Hz**, toutes en `stand`; puis **24** observations à **10 Hz** lors de l'essai unique; **167 tests Python réussis**, puis [workflow MuJoCo réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514292).
- Les données brutes se trouvent dans l'artefact GitHub Actions **`mujoco-headless-diagnostics`**, notamment `walk-comparison.json` et `joint-trace.json` ; aucune mémoire personnelle, caméra ou donnée du robot réel.

## Mesures (ne pas confondre les fenêtres temporelles)

| Mesure | Repos `stand` | Essai `walk` |
| --- | ---: | ---: |
| Échantillons de politique | 16 `stand` / 16 | 23 `walk` / 24 ; 1 `stand` initial |
| Commande nominale | 0 m/s | 0,12 m/s, `robotd` appliqué max ~0,12 m/s |
| Durée entre premiers/derniers échantillons joints | 1,56 s | 2,58 s |
| Déplacement net du tronc dans la *fenêtre d'échantillonnage* | 2,018 mm | 3,602 mm |
| Chemin XY échantillonné cumulé | 2,435 mm | 5,944 mm |
| Excursion genou gauche | 0,03221 rad (~1,85°) | 0,02227 rad (~1,28°) |
| Excursion genou droit | 0,03003 rad (~1,72°) | 0,00808 rad (~0,46°) |
| Excursion hanche gauche en tangage | 0,01268 rad (~0,73°) | 0,07679 rad (~4,40°) |
| Excursion hanche droite en lacet | 0,01798 rad (~1,03°) | 0,07092 rad (~4,06°) |

**Mesure finale spécifique de J2e**, réalisée **après arrêt et vérification** : **1,3376 mm** de déplacement XY net depuis son état initial contrôlé, dont **+0,0178 mm sur X monde** et **+1,3375 mm sur Y monde**, durant **2,80 s simulées** ; dérive de la baseline propre à J2e : **0,2601 mm**. Les distances de 2,018 mm et 3,602 mm du tableau sont calculées **sur d'autres fenêtres temporelles** et **ne doivent ni être soustraites ni assimilées à la mesure finale de J2e**. Les échantillons joints ne donnent pas la trajectoire continue exacte entre points.

**Vérification de fin d'essai :** 24 commandes J2e envoyées, `robot.stop` confirmé, `no_progress_observed` consigné dans la SQLite éphémère du CI ; intention ultérieure évaluée uniquement depuis une nouvelle perception. Le seuil initial d'au moins 10 mm n'est **pas atteint**. Aucune marche stable ni adhérence démontrée.

## Ce qui est démontré et ce qui manque

- **Démontré :** sélection de `walk` sur 23/24 relevés, vitesse appliquée **déclarée** nominale, variation d'angles articulaires réelle dans MuJoCo, absence de progression selon le seuil et arrêt constructeur confirmé.
- **Mesuré mais insuffisant :** faibles excursions des genoux malgré la politique de marche ; comparaison basée sur un seul essai P0b et des fenêtres distinctes du repos. Les valeurs sont des échantillons, pas une analyse de cycle de pas.
- **Non observé :** contacts dynamiques semelle-sol, forces et adhérence, cibles par articulation, cycle de support et propulsion. Le modèle définit des géométries `left_foot_collision` et `right_foot_collision`, mais le protocole `body_server` `op=read` ne transmet **pas** les contacts `MjData.contact`.
- **Cause racine : inconnue.** Hypothèses non départagées : faible sortie des politiques ou limitation des cibles motrices, interactions de l'actionneur simulé, phase des pas, adhérence/contact de la semelle, écarts de normalisation d'observation ou d'adaptation du modèle. Ne modifier aucun réglage moteur constructeur sans preuve d'une cause.

### Vérifications de code OEM déjà effectuées

- [`robotd/src/control.rs` épinglé](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs) : politiques `stand` / `walk` sélectionnées selon la magnitude de vitesse, sortie ONNX transformée en cibles des articulations via action scale et gains.
- [`duck-control/src/obs.rs` épinglé](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-control/src/obs.rs) : observation ONNX à 61 composantes ; 14 actions articulaires (bouche exclue).
- [`robot_groundcontact.xml` épinglé](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/robot/microduck/robot_groundcontact.xml) : géométries des deux semelles identifiables ; la présence dans le MJCF n'est pas une preuve de contact en dynamique.
- [`body_server.py` épinglé](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/sim/body_server.py) : `sensors()` publie positions/vitesses, pose, IMU, courant proxy `abs(force)*100` ; n'expose ni contacts dynamiques ni consignes articulaires par l'opération `read`.

## Suite proposée

1. Obtenir de manière **non intrusive**, compatible licence et constructeur, une lecture des **contacts et forces** dans le même modèle et les mêmes états MuJoCo, ou marquer durablement l'observation « inconnue ». Éviter tout capteur inventé ou interpolation contact=présent.
2. Si ces données deviennent disponibles : mesurer temps d'appui, alternance gauche/droite, glissement et lien action ONNX -> cibles -> angles -> contacts -> déplacement, dans une nouvelle PR spécifique.
3. Ne tenter P1a (3 traductions d'au moins 10 mm, puis démarche de 5 cm) **qu'après** preuve pertinente et changement justifié. Aucun ajustement de gain, de seuil ou de vitesse en tâtonnant.

**Niveau de preuve :** testé sur simulateur officiel ; jamais validé sur Microduck physique. Les températures, ressources NPU, pilotes et sécurité d'une pièce habitée restent inconnus.
