# P2b — Cycles cognitifs passifs avec la télémétrie MuJoCo (25 octobre 2026)

**État : code et tests Python réussis ; validation du scénario MuJoCo officiel à confirmer dans la CI de la PR #19.** Aucun essai sur le Microduck physique.

## Objectif limité

Relier plusieurs décisions du cerveau local aux télémétries datées de `robotd` et `tofd` exécutés par `duck-sim` constructeur, journaliser ces décisions sur SQLite et vérifier la réouverture de la même base au cours d'une seconde session. Cette étape n'essaie ni de marcher, ni de certifier un sol sûr, ni de simuler une conséquence d'action.

## Implémentation

- `microduck_companion/sim_passive_cycles.py` lit les mesures via `sim_bridge.read_simulator_telemetry`, lequel n'utilise que les appels autorisés en lecture `robot.health`, `robot.subscribe` et `tof.stream`. L'exécuteur n'importe aucune interface de mouvement.
- À chaque cycle : acquisition fraîche, contrôle de cohérence (santé, fréquence, horodatage, présence des deux flux, monotonie de la séquence ToF), transformation en `PerceptionSnapshot`, choix d'une intention par `AutonomyBrain`, inscription en base `sim_passive_cycles`. Les intentions sont **proposées**, jamais exécutées.
- Données absentes, périmées, contradictoires ou répétées ⇒ `halt`. Batterie basse observée avec télémétrie cohérente ⇒ `rest` possible. Le pont ne génère jamais `safe_area`, `floor_clear` ou `obstacle_m` à partir du ToF brut.
- Le journal conserve session, séquence, qualité, intention, disposition et sources, mais ni images, ni audio, ni matrice brute de profondeur, ni données privées. Le résultat de chaque cycle est `no_action_executed`, `reward` demeure `NULL`, `motor_commands=0`. Aucun apprentissage de préférence sur un résultat fictif n'est possible.
- La reprise de la même session sur la SQLite rechargée conserve le numéro de cycle, l'intention précédente et la dernière séquence ToF cohérente ; les anciens échantillons ne sont pas réutilisés. Après redémarrage du simulateur ou de l'horloge monotone, utiliser une **nouvelle session**.

## Vérifications effectuées

- [x] [234 tests Python réussis sur la branche](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199119), contre 224 sur `main` avant P2b.
- [x] Dix nouveaux tests : trames valides, invalides et répétées ; persistance entre deux ouvertures SQLite ; perte de capteur ; batterie basse ; sources et limites d'entrée ; faux services Unix JSON-RPC avec vérification stricte des trois méthodes autorisées.
- [ ] [Scénario `duck-sim` officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) : six cycles en deux sessions, une seule base SQLite et preuves JSON archivées ; résultat à vérifier.

La vérification MuJoCo utilise le script existant `scripts/sim-smoke.sh`, avec `DUCK_SIM_PASSIVE_CYCLES=YES` uniquement sur la branche P2b. Deux appels distincts à `python -m microduck_companion.sim_passive_cycles` demandent trois cycles chacun ; aucun appel `robot.move` supplémentaire.

## Ce que P2b ne prouve pas

Il n'existe toujours pas de démonstration de locomotion mesurée. `P1a` reste bloqué après P0g ; dernier essai moteur P0e : déplacement net **2,295 mm**, arrêt confirmé. Les valeurs de sûreté MuJoCo ne prouvent ni la sécurité du sol domestique, ni les performances de caméra/NPU, ni l'autonomie énergétique ou la chaleur de la carte physique. Qwen, `mediad` et la reconnaissance d'individus restent hors périmètre.

**Suite indépendante :** diagnostic P0h des politiques de marche. Pas de nouvelle action motrice dans cette PR.
