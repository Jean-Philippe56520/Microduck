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

Le module `microduck_companion` est actuellement un **prototype à observations simulées**, pas un contrôleur moteur ni une intégration au simulateur officiel. Aucune action ne doit être envoyée au robot réel sans un adaptateur validé et ses protections.

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

Exécuter `python -m unittest discover -s tests -v` pour les tests de sécurité. La connexion du simulateur MuJoCo et le contrôle de ses cadences sont les étapes suivantes.

## Sonde de télémétrie JSON-RPC (J2a, lecture seule)

Le module `microduck_companion/sim_ipc.py` sait lire `robot.health`, souscrire à `robot.subscribe` (`robot.state`) et `tof.stream` (`tof.frame`) sur les sockets Unix des démons officiels. Il limite la taille des trames, la cadence demandée et les délais de réception ; les données malformées ou manquantes sont rejetées. Les 64 mesures ToF sont conservées avec leurs statuts bruts : **elles ne prouvent pas que le sol est sûr**.

Quand `duck-sim` aura été démarré sur Linux/WSL2, exécuter depuis la racine du dépôt :

```sh
python -m microduck_companion.sim_probe --state-dir "$HOME/.cache/duck-sim"
```

La commande affiche l'état et des échantillons de télémétrie, sans envoyer aucune intention motrice. Elle renvoie un code non nul si `robotd` est malade ou si le flux est inaccessible. Les tests actuels du client reposent sur **des faux services Unix** : ce client n'a **pas encore été testé contre un vrai `duck-sim`**. Il ne construit pas encore les événements `floor_clear` ou `safe_area` nécessaires pour autoriser une exploration.

## Audit matériel et mémoire

- [Audit de faisabilité du matériel, de la vision, de la RAM et du stockage](docs/hardware-feasibility-audit-2026-10-25.md)
- [Script de mesures en lecture seule pour une unité réelle](scripts/resource-audit.sh)
- Troisième source officielle : [microduck_yocto — OS, partitions et carte beta](https://github.com/pollen-robotics/microduck_yocto).

L'image OS décrite en octobre 2026 prévoit une partition persistante de 8 Gio ; la RAM réellement disponible et l'espace libre ne sont pas encore mesurés sur l'unité commerciale.
