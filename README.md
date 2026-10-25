# Microduck Companion

Projet de robot autonome, curieux, explorateur et social.

**Objectif :** développer un cerveau comportemental qui observe, conserve une mémoire locale, apprend des conséquences de ses actions et interroge facultativement un modèle Qwen sur un PC du réseau local. Le dialogue est secondaire.

## Les deux sources officielles

- [Pollen Robotics / microduck](https://github.com/pollen-robotics/microduck) : contrôle du robot, capteurs, sécurité et interfaces.
- [Pollen Robotics / microduck_rl](https://github.com/pollen-robotics/microduck_rl) : simulation MuJoCo et entraînement des politiques motrices.

Ces deux sources sont intégrées comme **sous-modules Git**, épinglés sur des révisions précises pour préserver la reproductibilité.

```bash
git clone --recurse-submodules https://github.com/Jean-Philippe56520/Microduck.git
cd Microduck
python -m unittest discover -s tests -v
python -m microduck_companion.autonomy_demo
```

Sur Windows, le prototype Python peut être exécuté normalement. La simulation officielle complète nécessitera un environnement Linux adapté, par exemple WSL2, ainsi que des dépendances supplémentaires.

## Architecture cible

1. **Embarqué (Microduck)** : sécurité, mouvements, motivations, choix d'activités simples et mémoire essentielle.
2. **PC local (facultatif)** : Qwen pour interpréter des images, suggérer des hypothèses et analyser les nouveautés.
3. **GitHub** : conserver le code et les versions ; GitHub n'exécute pas l'IA.

Le module `microduck_companion` est actuellement un **prototype autonome testé avec les services officiels simulés**, y compris une impulsion `robot.move` suivie de `robot.stop`. Il n'est pas un contrôleur moteur ni une solution de navigation autonome validée. Aucune action ne doit être envoyée au robot réel sans un adaptateur validé et ses protections.

## Confidentialité et sécurité

Le dépôt ne doit contenir ni souvenirs personnels, ni enregistrements audio/vidéo, ni clés d'API, ni données privées. Les bases SQLite locales sont ignorées par Git. Le dépôt est actuellement privé. Les données personnelles doivent rester hors du dépôt, même privé.

## Plan de développement

La [feuille de route détaillée](docs/roadmap.md) définit les six phases, leurs dépendances, leurs critères de réussite, les métriques et les limites de validation.

**Prochain jalon :** vérifier une translation mesurable dans la zone plane MuJoCo, enregistrer les conséquences réellement observées en SQLite et adapter graduellement le choix d'exploration. Le premier démarrage MuJoCo et la télémétrie en lecture seule sont validés. Voir le [plan opérationnel MuJoCo J1b → J2](docs/mujoco-integration-plan.md).

### Étapes principales

- [x] Récupérer les deux bases officielles sous forme de sous-modules.
- [x] Tester un premier moteur d'autonomie et une mémoire locale.
- [x] Brancher les observations aux démons officiels du simulateur MuJoCo (lecture seule).
- [ ] Valider la zone plane bornée et les commandes de déplacement autorisées en simulation.
- [ ] Tester l'analyse d'objets avec Qwen sur le PC.
- [ ] Vérifier les ressources, la vitesse et la sécurité sur le matériel réel.

**Pas besoin de posséder le Microduck pour commencer à développer.**

## Contrat de perception (prototype V0)

Le module `microduck_companion/perception.py` fournit `PerceptionEvent` et `PerceptionSnapshot` (schéma v1). Chaque événement déclare sa provenance (`mock`, `simulator`, `sensor`, `robotd`, etc.), sa confiance, une heure monotone et une durée de validité limitée. Le moteur utilise `AutonomyBrain.choose_from_snapshot(snapshot)` pour obtenir une `Scene` conservatrice :

- absence ou expiration du signal de sol, de zone, d'obstacle ou de batterie : intention `halt` (ou `rest` si la batterie faible est confirmée) ;
- contradiction ou manque de confiance dans une mesure de sécurité : pas d'autorisation de déplacement ;
- les affirmations de Qwen n'attestent jamais la sécurité et ne sont jamais promues en observation de capteur ;
- étiquettes `mock`, `simulator` et `sensor` conservées distinctement en SQLite ; un souvenir fictif ne prouve pas une reconnaissance réelle.

L'ancienne méthode `choose(Scene(...))` est maintenue pour les essais synthétiques et **ne doit pas devenir un adaptateur de commande motrice**. Les sources ne sont pas encore authentifiées par un pilote, et aucun vrai capteur n'alimente ces événements : ce sont des protections de prototype, pas une homologation matérielle. `robotd` demeure seul responsable des moteurs et de la sécurité.

Exécuter `python -m unittest discover -s tests -v` pour les tests de sécurité. La **connexion en lecture seule à MuJoCo a été vérifiée** sur un exécuteur GitHub Actions ; une première démonstration de déplacement autonome sûr reste à construire.

## Sonde de télémétrie JSON-RPC (J2a, lecture seule)

Le module `microduck_companion/sim_ipc.py` sait lire `robot.health`, souscrire à `robot.subscribe` (`robot.state`) et `tof.stream` (`tof.frame`) sur les sockets Unix des démons officiels. Il limite la taille des trames, la cadence demandée et les délais de réception ; les données malformées ou manquantes sont rejetées. Les 64 mesures ToF sont conservées avec leurs statuts bruts : **elles ne prouvent pas que le sol est sûr**.

Avec `duck-sim` démarré sur Linux/WSL2, exécuter depuis la racine du dépôt :

```sh
python -m microduck_companion.sim_probe --state-dir "$HOME/.cache/duck-sim"
```

La commande affiche l'état et des échantillons de télémétrie, sans envoyer aucune intention motrice. Elle renvoie un code non nul si `robotd` est malade ou si le flux est inaccessible. Le client possède des tests avec **faux services Unix** et a également été **exécuté avec les véritables services `robotd`/`tofd` en simulation MuJoCo**, lors de l'essai GitHub Actions du 25 octobre 2026. Il ne construit pas encore les événements `floor_clear` ou `safe_area` nécessaires pour autoriser une exploration.

### J2b — Observation conservatrice, sans commande motrice

Le module `microduck_companion/sim_bridge.py` transforme les lectures reçues de `robotd` et `tofd` en un `PerceptionSnapshot` versionné. Il vérifie la fraîcheur, la santé des démons, l'état de chute, la cadence de contrôle et, quand disponible, la cohérence des horloges. Il ne certifie **jamais** le sol ou la zone à partir du ToF, et ne fabrique ni `safe_area`, ni `floor_clear`, ni distance d'obstacle fiable. La décision normale est donc `halt` (ou `rest` lorsque la batterie basse est confirmée sur une télémétrie cohérente).

Pour afficher cette décision quand un simulateur fonctionne déjà :

```sh
python -m microduck_companion.sim_observer --state-dir "$HOME/.cache/duck-sim"
```

Depuis un clone Git sur Linux/WSL2, le script suivant vérifie les prérequis puis démarre un environnement isolé sans caméra, avec arrêt en fin d'essai :

```sh
sh scripts/sim-smoke.sh check
DUCK_SIM_DEP_MODE=runtime sh scripts/sim-smoke.sh run
```

Le mode `run` initialise les sous-modules épinglés puis utilise `duck-sim`, `sim_probe` et `sim_observer`. `DUCK_SIM_DEP_MODE=runtime` installe sur Python 3.12 un ensemble minimal **épinglé** et vérifié pour le simulateur sans caméra (MuJoCo 3.10.0, NumPy 2.5.4 et ONNX Runtime 1.28.0), afin d'éviter les lourdes dépendances d'entraînement. Sans cette variable, `uv sync --frozen` utilise l'environnement RL officiel complet. Les politiques motrices officielles sont toujours téléchargées par `duck-sim` ; elles ne sont pas remplacées par le compagnon.

**Premier essai officiel réussi** : [GitHub Actions #40145369078](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078) a exécuté les 81 tests et lancé MuJoCo en mode headless sur Ubuntu 24.04. `robotd` a rapporté ~50 Hz (0 échéance manquée dans la fenêtre observée), `duck-sim realtime` **1,00×**, deux trames ToF simulées de **64 cellules** et une décision du cerveau `halt` sans commandes motrices. Cette mesure concerne uniquement ce test sur une machine CI Linux, **pas** les ressources ni la sûreté sur le Microduck physique.

Le script constructeur peut lever **son robot virtuel** pendant l'initialisation ; notre cerveau ne commande pas de mouvement. L'intégration validée est **lecture seule** : elle n'établit ni un sol sûr, ni une navigation autonome, ni une reconnaissance d'objets.

## Audit matériel et mémoire

- [Audit de faisabilité du matériel, de la vision, de la RAM et du stockage](docs/hardware-feasibility-audit-2026-10-25.md)
- [Script de mesures en lecture seule pour une unité réelle](scripts/resource-audit.sh)
- Troisième source officielle : [microduck_yocto — OS, partitions et carte beta](https://github.com/pollen-robotics/microduck_yocto).

L'image OS décrite en octobre 2026 prévoit une partition persistante de 8 Gio ; la RAM réellement disponible et l'espace libre ne sont pas encore mesurés sur l'unité commerciale.


## J2c — Contrôle d'une zone plane dans MuJoCo (simulation uniquement)

Le module expérimental `microduck_companion/sim_flat_zone.py` **ne transforme pas les distances ToF en preuve de sol sûr**. Il consulte directement le serveur du corps simulé (`op=read`) et vérifie au préalable le dépôt `microduck_rl` épinglé, son absence de modifications suivies, le hash Git exact de la scène `scene.xml`, le processus Linux `body_server` et ses paramètres (un seul robot, scène par défaut, sans caméra). Toute autre scène ou version est refusée.

Sur la scène officielle plane et vide, la pose `trunk`, la hauteur et la gravité projetée permettent de tester une petite zone virtuelle radiale de **0,90 m**, avec marge de **0,16 m** autour du robot et interdiction d'approcher à moins de **0,35 m** de la limite. Ce sont des **paramètres expérimentaux du simulateur**, pas des distances d'obstacles mesurées sur robot réel.

Pour tester sans commandes motrices, après démarrage du simulateur officiel :

```sh
python -m microduck_companion.sim_zone_probe \
    --state-dir "$HOME/.cache/duck-sim-companion" \
    --rl-root "$PWD/upstream/microduck_rl" --port 17801
```

Une pose incertaine, un processus inconnu, une source périmée ou une scène modifiée donnent `halt`. Le script `scripts/sim-smoke.sh` exécute désormais cette sonde après les vérifications initiales. **Ce jalon ne délivre aucune commande `robot.move`.** La [validation officielle MuJoCo #40173323079](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173323079) a **réussi** : scène certifiée, zone sûre, tronc à (0,0257 ; 0,0069 ; 0,1155) m, réserve de 0,7134 m, décision du cerveau `explore` et aucune commande motrice. Les **103 tests Python** sont également réussis. Prochaine étape : une seule impulsion de mouvement, limitée en vitesse et en durée et envoyée uniquement à `robotd`.


## J2d — Impulsion limitée via robotd (expérience MuJoCo)

`microduck_companion/sim_motion.py` contient une **unique** démonstration de mouvement, non réutilisable sur robot physique. Après autorisation par le cerveau et preuve de la zone MuJoCo plane officielle, il adresse des notifications `robot.move` à `robotd` avec une vitesse avant **fixe de 0,05 m/s**, quatre impulsions séparées de 0,1 s ; ni rotation ni déplacement latéral. Le client revérifie la scène, la position, la réserve de zone, la batterie et la cadence `robotd` avant **chaque** notification. Toute perte de preuve arrête les nouvelles notifications, et un appel `robot.stop` est envoyé et vérifié. Le deadman constructeur (~500 ms) demeure actif en dernier recours.

**Aucun mouvement n'est envoyé par défaut**, y compris dans les workflows manuels habituels. Pour un essai unique sur la machine Linux où le simulateur officiel est déjà en fonctionnement :

```sh
MICRODUCK_SIM_MOTION_TEST=YES python -m microduck_companion.sim_motion_demo \
  --enable-once --state-dir "$HOME/.cache/duck-sim-companion" \
  --rl-root "$PWD/upstream/microduck_rl" --port 17801
```

Le script `sim-smoke.sh` ne lance cette démonstration que si `DUCK_SIM_SHORT_MOVE=YES` est explicitement présent. Le workflow GitHub Actions ne définit cette variable que pour la branche expérimentale `feat/one-bounded-sim-intent-20261025` ; sur `main`, il reste en lecture seule.

**Essai MuJoCo effectué et réussi :** [GitHub Actions #40173809463](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173809463), 115 tests Python verts, `robotd` sain à ~50 Hz, 1,00× temps réel, **4 notifications `robot.move`**, `robot.stop` confirmé. Évolution observée du tronc : **0,0001848 m (0,185 mm)** en ~0,36 s de temps simulé. Cette très faible variation ne prouve **pas** une marche ; elle peut provenir de la stabilisation en posture. Aucune navigation autonome, aucun évitement d'objets mobiles et aucune validation physique.


## J2e — Mesurer une translation et conserver l'expérience (MuJoCo seulement)

Le code constructeur choisit la politique de station debout lorsque la norme de la vitesse demandée est au plus égale à **0,05 m/s**. C'est probablement pour cela que le premier essai, à exactement 0,05 m/s, n'a produit qu'une variation de **0,185 mm** (hypothèse à vérifier). Le nouveau module expérimental `sim_walk_trial.py` demande une seule séquence à **0,12 m/s**, donc au-dessus de ce seuil, sans rotation ni déplacement latéral. Il effectue jusqu'à **12 notifications de 0,1 s** sous réserve d'une zone sûre : soit environ 1,2 s de commandes, avec un budget d'exécution maximal de 2,6 s et `robot.stop` obligatoire.

Le contrôleur vérifie systématiquement le simulateur épinglé, sa scène sans obstacles, la santé `robotd`, la cadence, la position et la marge à la zone. Une **dérive du tronc sans mouvement commandé** est mesurée d'abord. Si la dérive dépasse 5 mm, si une source est douteuse ou si le cerveau ne choisit pas `explore`, **aucun mouvement n'est envoyé**. Aucune adaptation constructeur n'est modifiée.

Après l'accusé de réception de `robot.stop`, une nouvelle position et la santé de `robotd` sont contrôlées. Le module `episodic_memory.py` conserve une table SQLite distincte des souvenirs d'objets (`sim_motion_trials`), avec provenance, déplacement horizontal, dérive de référence, état de sécurité et résultat. Les catégories sont `translation_observed`, `no_progress_observed`, `inconclusive_drift` et `unverified`. Une préférence d'exploration évolue **lentement** uniquement sur une conséquence fiable : cette mise à jour de mémoire n'est **pas un entraînement du modèle**.

Exemple, uniquement sur Linux avec la simulation officielle déjà lancée :

```sh
MICRODUCK_SIM_WALK_TEST=YES python3 -m microduck_companion.sim_walk_demo \
  --enable-once --state-dir "$HOME/.cache/duck-sim-companion" \
  --rl-root "$PWD/upstream/microduck_rl" \
  --memory "$HOME/.local/share/microduck-companion/sim-motion.sqlite" \
  --port 17801
```

En CI, `DUCK_SIM_WALK_TRIAL=YES` est volontairement activé **seulement** sur `feat/measured-sim-walk-learning-v1`. Sur la branche principale, aucun nouveau mouvement n'est autorisé par défaut. La réussite d'un échange de commandes, ou même une variation de position du tronc, **ne prouve pas à elle seule une démarche stable**. Il faut vérifier les résultats mesurés dans MuJoCo, puis instrumenter la marche et les contacts au sol.
