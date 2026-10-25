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

Le module `microduck_companion` est actuellement un **prototype autonome avec lecture seule des flux du simulateur officiel validée le 25 octobre 2026**, pas un contrôleur moteur ni une autonomie de déplacement validée. Aucune action ne doit être envoyée au robot réel sans un adaptateur validé et ses protections.

## Confidentialité et sécurité

Le dépôt ne doit contenir ni souvenirs personnels, ni enregistrements audio/vidéo, ni clés d'API, ni données privées. Les bases SQLite locales sont ignorées par Git. Le dépôt est actuellement privé. Les données personnelles doivent rester hors du dépôt, même privé.

## Plan de développement

La [feuille de route détaillée](docs/roadmap.md) définit les six phases, leurs dépendances, leurs critères de réussite, les métriques et les limites de validation.

**Prochain jalon :** démarrer un Microduck virtuel sain avec `scripts/duck-sim`, puis connecter les états `robotd` et `tofd` au cerveau ; autoriser les intentions uniquement après validation de la zone et des sécurités. Voir le [plan opérationnel MuJoCo J1b → J2](docs/mujoco-integration-plan.md).

### Étapes principales

- [x] Récupérer les deux bases officielles sous forme de sous-modules.
- [x] Tester un premier moteur d'autonomie et une mémoire locale.
- [ ] Brancher les observations au vrai simulateur MuJoCo.
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
