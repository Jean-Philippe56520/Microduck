# SIM-E2-C — Parité entraînement/runtime : lacunes d'observation et relecture P0e originale

**28 octobre 2026.** Chantier **sans moteur**, sans simulateur relancé, sans modèle installé et sans robot physique. Prolongement de [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101). Le [plan d'action](plan-action.md) demeure l'autorité. Comparaison avec la session WSLg du 28/10 uniquement sur quatre statistiques agrégées communiquées volontairement ; **aucun JSON local ni média privé importé sur GitHub**.

## 1. Question, hypothèses et critère de refus

**Observation** : l'OEM graphique à 0,08 m/s a déclaré 31 états `walk` sur 32 sans limiteur, pour seulement **3,500 mm** de translation nette ; P0e CI headless à 0,12 m/s avait déjà montré des consignes articulaires qui bougent davantage que les positions et deux pieds chargés. Au repos WSLg, huit mesures `stand` présentent environ 10–12° de décalage signé sur hanches roll et genoux ; `robot.state.safety.gain=160` a été vérifié séparément à un instant.

**Hypothèses à distinguer, sans causalité présumée :** incohérence des entrées ONNX (normalisation, histoire de 14 actions, observations différées), différence d'actionnement BAM entraînement / MJCF simulation, appuis/contacts ou phase insuffisante, conventions articulaires, politique/scene active. La preuve cherchée dans ce lot est plus restreinte : **ce que le solveur MuJoCo original P0e a réellement commandé et mesuré**, et si son offset debout est reproduit à titre descriptif dans les données WSLg.

**Échecs bloquants de l'analyse hors ligne** : fichier original d'une autre provenance, SHA modifié, perte/doublon de frames, révision ou scène incohérente, échec du `robot.stop` historique, fenêtre P0b incomplète, valeurs non finies, état des actionneurs absent. Risque : comparer abusivement des exécutions différentes ou appeler consigne MJCF « action brute ONNX ». Retour arrière : aucun service ni fichier OEM touché ; retirer le seul module de diagnostic et son rapport. Aucune expérience active demandée.

## 2. Audit constructeur épinglé : le contrat existe, le flux interne n'est pas observable

| Source exacte | Ce qui est établi | Ce qui **n'est pas** établi |
| --- | --- | --- |
| [`duck-control/src/obs.rs` OEM `942e58e3`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-control/src/obs.rs) et [P0f](mujoco-p0f-policy-contract-2026-10-25.md) | `obs[1,61]` → `actions[1,14]` ; gyro 3, gravité 3, angles relatifs HOME 14, vitesses 14, **14 actions brutes précédentes**, commandes 13 ; tests OEM sur positions HOME et exclusion bouche | La **vraie observation 61D** à chaque tick et les 14 sorties brutes de `robotd` ; `robot.state.targets` est une consigne **après échelle et filtre** et **avant `safety.apply`**, pas l'action brute |
| [`robotd/src/control.rs` OEM](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs) | `last_action` est le résultat réseau précédent ; les cibles utilisent HOME + échelle (0,9 marche/1,0 debout par défaut) et filtre jambes à 0,7 | Rétro-inversion fiable de l'ONNX brut depuis quelques `targets` à 4–10 Hz ; elle exigerait chaque tick, les états de filtre, transitions et données d'entrée |
| [Tâche RL `microduck_velocity_env_cfg.py` au pin `b02fdea4`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py) | Échelle d'action déclarée `1.0`, entrées avec bruit/délai (p. ex. `joint_vel` un décalage de 1 pas d'observation dans cette configuration), perturbations et randomisation | Que **ce même état exact du code** ait servi à exporter le checkpoint du modèle alpha installé |
| [`microduck_constants.py` RL épinglé](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/robot/microduck_constants.py) et [`infer_policy.py`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/scripts/infer_policy.py) | Configuration d'entraînement/évaluation contenant **BAM M6** (dynamique électrique/frottement/délai) ; l'outil d'inférence OEM l'utilise par défaut | Identité de la dynamique avec les actionneurs `chosen_actuator` simples du simulateur `duck-sim` |
| [`body_server.py` RL épinglé](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/sim/body_server.py) et [P0e](mujoco-p0e-actuator-gains-2026-10-25.md) | `data.ctrl` de position, modèle MJCF ajusté à `kp/200` ; P0e vérifie ses efforts et l'absence d'écrêtage dans les fenêtres enregistrées | Que cette loi de position soit équivalente au BAM d'entraînement, ou qu'elle suffise à une démarche stable |

**Provenance réseau :** P0h rattache les noms `alpha_walking.onnx`, `alpha_stand.onnx` et `velstand.onnx` à des checkpoints déclarés via la [documentation OEM `velstand_policy.md`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/docs/velstand_policy.md). Les trois empreintes ONNX installées sur WSLg correspondent au bundle v8 audité. Cela **n'est pas** une preuve cryptographique du checkpoint ni de sa version exacte de code d'entraînement. La comparaison A/B P0i ne prouve aucun modèle locomoteur supérieur.

## 3. Nouvelle relecture hors ligne de l'archive P0e authentifiée

**Source originale :** [CI MuJoCo P0e #40193139617](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617), archive `mujoco-headless-diagnostics` (disponibilité GitHub Actions annoncée jusqu'au **1er novembre 2026**). Les trois fichiers d'entrée ont été **téléchargés et vérifiés bit à bit** :

| Fichier original P0e | SHA-256 vérifié |
| --- | --- |
| `solver-tap.jsonl` | `7606cf8f06a944d7905b29b2a4b144eed304a05bbbf7bbb30d022f61965f8e39` |
| `solver-analysis.json` | `1be478752366e295f23ce37e970bb3ea994dcfbb5589985681d6399ef7013929` |
| `walk-comparison.json` | `e5dfc4a86039002e9cf75f62b0bbb9fb22cbde597df5dd2c2f1d849b3c56bb5a` |

**Un seul essai historique**, P0e, pas de nouveau mouvement. Le journal de 888 échantillons de solveur à 50 Hz contient **79** trames dans la fenêtre `stand` (12,20–13,76 s de simulation) et **127** dans la fenêtre `walk` (14,26–16,78 s). L'appartenance aux fenêtres est déduite des observations P0b **à 10 Hz**, pas une preuve du label ONNX à chacun des 50 ticks du solveur. `robot.stop` historique confirmé.

### Décalages debout : répétition descriptive entre CI et WSLg

Écart **signé `data.ctrl - qpos_avant_pas`** dans la fenêtre P0e, puis moyennes **`robot.state.targets - robot.state.joints`** déjà calculées par l'opérateur sur huit trames au repos WSLg. Ces deux définitions sont proches, **mais leurs instants, voies de mesure et conditions ne sont pas identiques**.

| Joint | P0e CI, moyenne sur 79 (°) | WSLg, moyenne sur 8 (°) | Écart des moyennes WSLg−P0e (°, approx.) |
| --- | ---: | ---: | ---: |
| Hanche roll gauche | **−11,606** | −11,64 | −0,034 |
| Hanche roll droite | **+10,592** | +11,26 | +0,668 |
| Genou gauche | **−11,831** | −10,83 | +1,001 |
| Genou droit | **+10,624** | +10,10 | −0,524 |

Ce constat réduit l'intérêt d'incriminer une particularité transitoire du viewer WSLg ; il est **également compatible avec un comportement commun d'équilibre du modèle constructeur**, non encore expliqué. Deux traces **ne prouvent ni équivalence statistique ni cause**.

### Durant la fenêtre `walk` P0e : consigne variable mais suivi moindre

| Joint | Excursion consigne `data.ctrl` | Excursion angle avant pas | Comparaison |
| --- | ---: | ---: | --- |
| Hanche roll gauche | **6,07°** | **0,99°** | Position de bien moindre amplitude |
| Hanche roll droite | **6,05°** | **0,20°** | Position de bien moindre amplitude |
| Genou gauche | **3,14°** | **1,31°** | Position de moindre amplitude |
| Genou droit | **3,01°** | **1,51°** | Position de moindre amplitude |

Les cibles de roulis gauche/droite sont anticorrélées (**Pearson ≈ −0,935**) pendant les 127 échantillons de la fenêtre marche ; les positions correspondantes ont une corrélation d'environ **+0,377**. Mesures purement descriptives sur **2,52 s**, sans périodicité prouvée ni preuve d'alternance de pas. P0j avait déjà établi les **deux pieds chargés sur 127/127 relevés** au seuil diagnostique de 0,1 N. P0e avait déjà démontré **zéro saturation de force sur 2 884 valeurs** dans ses deux fenêtres.

**Ce que les nouvelles statistiques apportent :** le biais au repos n'est pas propre à WSLg et les commandes de marche ne sont pas uniformément constantes. **Ce qu'elles ne donnent toujours pas :** vraies observations ONNX de `robotd`, actions brutes avant filtrage, équivalence BAM/PD, impulsion horizontale signée du contact, glissement au patch ou cause de la faible translation.

## 4. Matrice réutiliser / adapter / créer, vérifications et suite

- **Réutiliser :** le collecteur natif P0e `sim_live_solver_tap.py`, `sim_actuator_gain_audit.validate_pre_step_audit`, les gardes de provenance/horloge/stop de P0j et le registre de sources P0f/P0h/P0i. Aucun nouvel essai moteur ou instrument constructeur.
- **Adapter :** un **petit analyseur hors ligne** `microduck_companion.sim_e2c_offline_joint_tracking`, strictement limité aux mêmes trois fichiers originaux et aux quatre joints ; il calcule moyennes signées, variations et corrélations en lisant des données déjà archivées. Il marque explicitement `real_robotd_61_input_observations_available=false`, `gait_validated=false`, `root_cause_proven=false`. C'est un outil **PC**, pas embarqué.
- **Créer :** tests sur fixtures positives/négatives (fenêtres discontinues, trames absentes, valeurs non finies, SHA/provenance refusés, aucun rapport écrit en cas d'échec) et ce rapport ; pas de nouveau pilote, politique, action moteur, modèle IA, base de données, dépendance ni modification OEM. Aucune référence tierce non auditée n'est importée.

Si l'archive originale est encore disponible, le script se lance après extraction **locale** de la ZIP source, sans démarrer le simulateur :

```bash
python3 -m microduck_companion.sim_e2c_offline_joint_tracking \
  --solver-tap ./tmp/duck-sim-companion/solver-tap.jsonl \
  --solver-analysis ./tmp/duck-sim-companion/solver-analysis.json \
  --walk-comparison ./tmp/duck-sim-companion/walk-comparison.json \
  --output ./sim-e2c-offline-evidence.json
```

**Étape suivante justifiée :** rechercher une voie *OEM* permettant de capturer à des instants cohérents le vecteur réel d'observation 61D et les actions ONNX brutes, sans toucher au pilote ou aux sous-modules et avec coût de 50 Hz maîtrisé ; faute de telle API, ces valeurs restent **inconnues**, donc pas d'inférence « reproduite » fictive. Les différences d'actionnement BAM/MJCF et de scène sont **des pistes**, non des correctifs validés. Une collecte active n'est **pas** autorisée par ce lot. Pas de crédit causal ni de validation robot.
