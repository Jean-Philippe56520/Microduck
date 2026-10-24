# Jalon MuJoCo J1b → J2 : plan d'intégration du cerveau Microduck Companion

Date : 2026-10-25 · État : **planifié, non exécuté en simulation**.

Ce document est le plan exécutable qui suit [le contrat de perception v1](../microduck_companion/perception.py) et complète la [feuille de route générale](roadmap.md). Il vise **un Microduck virtuel**, puis une boucle perception → décision → intention sûre → retour → mémoire, sans accès au robot physique.

## Ce qui est déjà vérifié

- Le module Python `microduck_companion` choisit des intentions et conserve des expériences dans SQLite.
- `PerceptionEvent` et `PerceptionSnapshot` v1 distinguent environnement, provenance déclarée, confiance, fraîcheur et événements inconnus. `AutonomyBrain.choose_from_snapshot(...)` est disponible.
- Les 40 tests Python (13 historiques et 27 de perception) ont réussi sur la branche de développement du précédent jalon ; leur exécution ne démontre pas un fonctionnement MuJoCo.
- Les sous-modules `upstream/microduck` et `upstream/microduck_rl` sont épinglés ; respecter les révisions du dépôt et ne pas modifier les sources officielles pour contourner les interfaces.

**Non réalisé :** démarrage validé de `duck-sim` pour ce projet, preuve de sol sûr à partir de MuJoCo, perception de vrais objets, mouvements déclenchés par notre cerveau, mesure de latence dans le simulateur. Le client JSON-RPC en lecture seule et le pont conservateur de perception sont désormais codés et testés sur faux sockets Unix (voir point d'avancement ci-dessous).

## Point d'avancement au 25 octobre 2026

- **J2a codé et testé :** `sim_ipc.py`, `sim_probe.py`, télémétrie `robot.health`, `robot.state` et `tof.frame` en lecture seule.
- **J2b codé et testé sur faux sockets :** `sim_bridge.py`, `sim_observer.py`, conversion conservatrice vers `PerceptionSnapshot` et décision `halt` en l'absence de preuve de sol sûr.
- **81 tests Python réussis localement**, compilation Python contrôlée ; test de prérequis `sh scripts/sim-smoke.sh check` exécuté, signalant l'absence de Rust/Cargo et du dépôt complet.
- **MuJoCo non lancé :** aucun chiffre de performance, aucune mesure physique, aucune intention motrice envoyée par le compagnon. Le script `sh scripts/sim-smoke.sh run` est préparé pour un environnement Linux/WSL2 doté des prérequis.

Le pont n'émet jamais `floor_clear=True` ni `safe_area=True` ; cette absence est une condition délibérée de sécurité. Le prochain jalon exige un fournisseur de vérité terrain simulée réellement vérifié ou restera limité à l'observation.

## Architecture minimale visée

```text
microduck_rl (duck-body / MuJoCo) ── TCP ── robotd --sim (50 Hz, sécurité)
                     │                           │  robot.subscribe / robot.state
                     └── tofd --sim ─────────────┤  tof.stream / tof.frame
                                                 ▼
                                   Adaptateurs de lecture SEULS
                                          (sockets Unix)
                                                 │
                                  provenance liée au socket lu,
                                horodatage, fraîcheur, états sûrs
                                                 ▼
                              PerceptionSnapshot v1 / AutonomyBrain
                                                 │  intention proposée
                                                 ▼
                                Filtre d'intentions + expiration
                                                 │  JSON-RPC autorisé
                                                 ▼
                                      robotd UNIQUEMENT
                                                 │
                                      état/effet observé
                                                 ▼
                                  mémoire SQLite du compagnon
```

Les adaptateurs sont des **cibles de développement**, pas du code déjà présent. Aucune requête Qwen, aucune inférence NPU et aucune modification d'algorithme moteur pour J1b/J2.

## Lot A — Environnement et lancement du simulateur (J1b, premier travail)

**Livrable :** journal de démarrage reproductible et checklist de prérequis.

1. Utiliser Linux (natif ou WSL2 suffisamment configuré), Rust/Cargo, `uv`, Python **3.12** pour l'environnement `microduck_rl` (`requires-python >=3.12,<3.13` dans son `pyproject.toml`) et dépendances système nécessaires. Le prototype compagnon supporte Python >=3.10 et ses tests CI utilisent Python 3.11 : garder les environnements distincts si utile.
2. Initialiser les sous-modules avec `git submodule update --init --recursive`. Ne pas substituer `main` ou `develop` à la révision épinglée sans revue de compatibilité.
3. Préparer `upstream/microduck_rl/.venv` avec `uv sync` (premier téléchargement potentiellement volumineux). Le script officiel compile `robotd`, `robotctl`, `tofd`, etc., et télécharge les politiques ONNX officielles si absentes. Prévoir l'accès réseau initial.
4. Démarrer **un seul** robot, **sans caméra**, **sans conteneur**, dans la scène sol plat par défaut. Vérifier l'état, la santé, la vitesse temps réel, les logs, puis arrêter proprement.
5. Si le facteur temps réel est insuffisant, diagnostiquer les ressources, puis réessayer sans interface graphique (`DUCK_SIM_VIEWER=0`) ; ne pas annoncer une cadence de 50 Hz réussie sans mesure.

Depuis la racine de notre dépôt, sur la machine Linux/WSL2 appropriée :

```sh
git submodule update --init --recursive
cd upstream/microduck_rl
uv sync
cd ../..
export DUCK_SIM_RL="$PWD/upstream/microduck_rl"
unset DUCK_SIM_CAMERAS
upstream/microduck/scripts/duck-sim
upstream/microduck/scripts/duck-sim status
upstream/microduck/scripts/duck-sim ctl health
upstream/microduck/scripts/duck-sim realtime
upstream/microduck/scripts/duck-sim log
upstream/microduck/scripts/duck-sim down
```

**Attention :** les commandes ci-dessus sont une procédure à essayer, **non un compte rendu d'exécution**. Le script `scripts/duck-sim` exige ses dépendances, sa version et les politiques ONNX disponibles. Le retour de `robot.health` est plus important qu'une fenêtre MuJoCo simplement ouverte.

**Acceptation A :** `duck-sim` démarre/arrête de manière reproductible ; `robotd` est sain, `tofd` est présent et les paramètres de cadence et de facteur temps réel sont archivés. Documenter tout échec ; ne pas passer à la commande autonome en cas de simulation instable.

## Lot B — Acquisition JSON-RPC, sans aucune commande motrice

**Livrable :** adaptateur de télémétrie testable à partir de messages de sockets.

1. Implémenter un petit client JSON-RPC 2.0 **NDJSON** avec délais, arrêt propre, reconnexion, numéros de requête et validation de schéma ; ne pas ajouter de broker.
2. Souscrire à `robot.subscribe` sur le socket de `robotd` pour recevoir `robot.state` et lire `robot.health` à cadence modérée (seul `robotd` est source autoritative pour ses états).
3. Souscrire à `tof.stream` sur le socket propre de `tofd`, qui publie des `tof.frame` 8×8. Distinguer distance en **millimètres**, statut de zone et absence de mesure ; ne jamais convertir une cellule invalide en distance libre.
4. Relier les événements au schéma v1 en utilisant **l'heure monotone de réception** et, si les deux sources le permettent, comparer `robot.state.t_ns` et `tof.frame.t_ns`. Les valeurs `t_ns` sont censées utiliser le même `CLOCK_MONOTONIC` sur un même hôte ; vérifier l'environnement avant corrélation.
5. L'adaptateur attribue la provenance selon le **socket réellement utilisé**, non depuis un champ reçu du réseau ni depuis Qwen. Toute source non identifiée ou silencieuse reste `unknown`.

Le périmètre des mesures comporte : `battery_pct` dérivé de `robot.health` lorsque présent ; `obstacle_m` seulement si le ToF est interprétable, cohérent et pertinent dans le repère ; `person_visible` et `object_label` sont **inconnus** à cette étape, sauf injection de données fictives **explicitement étiquetées**.

**Acceptation B :** capture de données authentiquement issues des démons simulés, mise à jour de la fraîcheur, tests sur timeout, déconnexion, trame erronée, données absentes et reconnexion. Le programme reste **en lecture seule**.

## Lot C — Contrat de sécurité et validité des zones

**Livrable :** décision conservatrice sur l'autorisation d'agir.

Le ToF 8×8 orienté par la tête n'est **pas** un capteur de sol garantissant l'absence de marche ou d'escalier. Une `safe_area` saisie par opérateur ne prouve pas non plus `floor_clear`. Le schéma v1 demande, en environnement `simulator`, un `safe_area` fourni par opérateur ou simulateur **et** un `floor_clear` provenant du simulateur.

1. Pour l'observation seule : autoriser `halt` par défaut, même si la fenêtre MuJoCo affiche un sol plat.
2. Pour une première démonstration de mouvement : définir une petite scène de test bornée (sol plat documenté, zone sans bord, obstacles connus). Explorer si le simulateur fournit une **vérité terrain vérifiable** sur le sol, ses contacts, limites et collision. Si cette preuve n'existe pas dans les interfaces, développer un petit fournisseur de vérité terrain côté simulateur, avec tests ; **ne pas usurper** `floor_clear=True` en permanence.
3. Construire la validation de zone : limites connues, capteurs disponibles, vitesse/temps limités, commande expirant sans rafraîchissement ; ajouter des tests où le sol devient incertain ou la position sort de zone.
4. Si une certification simulée du sol n'est pas obtenue, **bloquer les déplacements** et terminer d'abord les lots de lecture et de regard sans translation.

**Acceptation C :** les décisions `halt`/`rest` sont démontrées pour observation périmée, donnée incohérente, obstacle, capteur perdu et batterie simulée faible. Toute autorisation de mouvement porte une justification provenant d'une source simulée réellement vérifiée.

## Lot D — Passer des intentions de haut niveau aux commandes officielles

**Livrable :** adaptateur de commandes indépendant du cerveau, initialement désactivé.

1. Définir une liste blanche minimale : `robot.look` (regard orienté), `robot.move` (mouvement continu à paramètres bornés), `robot.stop`. Le mouvement attend l'acceptation du lot C ; démarrer par des actions non translatoires en situation saine.
2. Respecter le protocole officiel : `robot.look` et `robot.stop` sont des requêtes ; `robot.move` est une **notification continue** avec `vx`, `vy`, `vyaw`. Vérifier les valeurs, plafonds et la temporisation de la politique/deadman officielles avant toute émission.
3. Permettre uniquement une durée courte par intention, avec une autorisation explicite pour la simulation ; en cas de capteur périmé, socket débranché, réponse refusée ou arrêt du compagnon, cesser les notifications et demander `robot.stop` si possible.
4. Garder le contrôle physique et la boucle à 50 Hz sous `robotd`, sans commande de servo, sans mutation de ses limites ni appels bloquants venant du cerveau.
5. Tester séparément le client par un **faux socket** ; ne jamais faire d'un faux accusé de réception une preuve de mouvement réussi.

**Acceptation D :** en simulation stable et zone certifiée, le compagnon peut demander au robot de regarder puis, si les conditions sont réunies, effectuer un mouvement limité et s'arrêter. Les refus de `robotd` sont respectés et consignés.

## Lot E — Boucle d'autonomie observable et apprentissage

**Livrable :** démonstration reproductible entièrement locale, sans Qwen.

Scénarios progressifs :

| Cas | Entrée | Réponse attendue |
| --- | --- | --- |
| 1 — repos | Environnement sans événement | `idle`, `rest` ou exploration **seulement si sûre** |
| 2 — nouveauté fictive | `object_label` d'une source `mock` dans un test isolé | `inspect_object`, hypothèse non prise pour du réel |
| 3 — nouveauté simulée | Événement provenant d'un adaptateur/fixture de simulation authentifié | Inspection autorisée en contexte sûr |
| 4 — conséquence | Résultat d'une action **observé**, non inventé | Épisode SQLite et mise à jour graduelle d'une préférence |
| 5 — souvenir | Situation déjà rencontrée | Nouvelle décision tenant compte du souvenir |
| 6 — sécurité | obstacle, batterie basse, capteur absent, sol inconnu, RPC coupé | refus d'avancer / demande d'arrêt, journal détaillé |

Mesurer systématiquement : intentions/minute, répétition, temps entre événement et décision, délai d'arrêt, événements rejetés, refus RPC, collisions et chutes **si accessibles** depuis le simulateur, facteur temps réel et santé `robotd`. Séparer résultats unitaires, tests IPC et essais MuJoCo.

**Acceptation E :** séquence `observation -> choix -> action via robotd -> conséquence réellement observée -> mémoire -> choix adapté` démontrée avec journaux reproductibles, sans connexion Qwen et sans mouvement non autorisé.

## Ordre des livraisons et stratégie Git

| Livraison | Contenu dans notre dépôt | Dépendance |
| --- | --- | --- |
| J1b / A | procédure environnement + journal de santé et temps réel | aucune |
| J2a / B | client JSON-RPC et adaptateur de télémétrie, tests sans mouvement | J1b |
| J2b / C | définition et tests de zone/sol sûrs en simulation | J2a |
| J2c / D | adaptateur des intentions vers `robotd`, initialement coupé, tests d'arrêt | J2b |
| J2d / E | démonstration enregistrée avec SQLite et métriques | J2c |

Créer des branches/PR ciblées. Pour chaque modification : revoir les interfaces officielles épinglées, ajouter tests, exécuter les vérifications réellement accessibles, archiver échecs et mesures, mettre à jour README, feuille de route et audit le cas échéant. **Ne pas avancer la case de statut « simulé » sur la base de tests Python seulement.**

## Hors périmètre pour ce jalon

Reconnaissance de Nessquick, Kitty ou Malo ; voix ; Qwen ; navigation libre dans une maison réelle ; automatisations d'e-mails ; portage Rust sur RK3566 ; optimisation NPU ; validation thermique ou matérielle. Ces éléments restent dans la feuille de route, après l'intégration du premier cycle en simulation.

## Points de contrôle à maintenir

- **Physique absente :** nous ne disposons pas encore d'une unité Microduck.
- **Simulation limitée :** MuJoCo ne valide pas les pilotes caméra, NPU, radio, IMU réels, la chaleur et les ressources embarquées.
- **Sécurité locale :** aucun programme d'IA ne contrôle directement un moteur ; `robotd` accepte/refuse les intentions.
- **Données privées :** n'enregistrer ni images, ni voix, ni identités personnelles dans GitHub ; privilégier une base SQLite locale avec éléments fictifs.
- **Compatibilité :** Python 3.11 du compagnon et Python 3.12 de `microduck_rl` peuvent cohabiter dans des environnements distincts. Ne pas imposer GPU/CUDA pour un simple test de simulation CPU sans mesures ou preuve des dépendances.

## Références officielles

- [Guide du simulateur `duck-sim`](https://github.com/pollen-robotics/microduck/blob/main/docs/robot/simulation.md)
- [Architecture JSON-RPC / sécurité `robotd`](https://github.com/pollen-robotics/microduck/blob/main/docs/design/robotd-design.md)
- [Protocole du constructeur `duck-ipc-proto`](https://github.com/pollen-robotics/microduck/blob/main/duck-ipc-proto/src/lib.rs)
- [Simulation officielle `microduck_rl`](https://github.com/pollen-robotics/microduck_rl)
- [Audit matériel Companion](hardware-feasibility-audit-2026-10-25.md)
