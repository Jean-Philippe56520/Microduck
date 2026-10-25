# Jalon MuJoCo J1b → J2 : plan d'intégration du cerveau Microduck Companion

Date : 2026-10-25 · **État actualisé : télémétrie, zone plane, commandes bornées, arrêt et mémoire des conséquences vérifiés dans MuJoCo ; marche effective NON validée.**

Ce document conserve les procédures, protocoles et journaux **historiques** des étapes J1b–J2e, après [le contrat de perception v1](../microduck_companion/perception.py). Les **priorités futures**, dépendances et critères d'acceptation se trouvent dans le **[plan d'action consolidé](plan-action.md)** ; la [roadmap générale](roadmap.md) présente les six phases. Les essais J2 ont été réalisés sur **un Microduck virtuel**, jamais sur robot physique.

## Ce qui est déjà vérifié

- Le module Python `microduck_companion` choisit des intentions et conserve des expériences dans SQLite.
- `PerceptionEvent` et `PerceptionSnapshot` v1 distinguent environnement, provenance déclarée, confiance, fraîcheur et événements inconnus. `AutonomyBrain.choose_from_snapshot(...)` est disponible.
- Les 40 tests Python (13 historiques et 27 de perception) ont réussi sur la branche de développement du précédent jalon ; leur exécution ne démontre pas un fonctionnement MuJoCo.
- Les sous-modules `upstream/microduck` et `upstream/microduck_rl` sont épinglés ; respecter les révisions du dépôt et ne pas modifier les sources officielles pour contourner les interfaces.

**Non validés à ce jour :** déplacement locomoteur significatif, démarche stable, boucle autonome sur plusieurs cycles, perception de vrais objets, latences de bout en bout en mission, robot physique. **Validés en simulation :** scène plane bornée attestée par sa révision, commandes brèves déclenchées par une intention, arrêt explicite et mémoire d'un résultat mesuré. Les valeurs ToF seules ne certifient toujours aucun sol.

## Point d'avancement au 25 octobre 2026

- **J2a codé et testé :** `sim_ipc.py`, `sim_probe.py`, télémétrie `robot.health`, `robot.state` et `tof.frame` en lecture seule.
- **J2b codé et testé sur faux sockets :** `sim_bridge.py`, `sim_observer.py`, conversion conservatrice vers `PerceptionSnapshot` et décision `halt` en l'absence de preuve de sol sûr.
- **81 tests Python réussis localement**, compilation Python contrôlée ; test de prérequis `sh scripts/sim-smoke.sh check` exécuté, signalant l'absence de Rust/Cargo et du dépôt complet.
- **MuJoCo officiel lancé :** [GitHub Actions #40145369078](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078) a vérifié l'intégration en lecture seule sur Ubuntu 24.04 : `robotd` sain (~50 Hz, 0 échéance manquée dans la période contrôlée), MuJoCo **1,00× temps réel**, ToF simulé **2 trames × 64 cellules**, cerveau `halt` (sol inconnu), sans intention motrice. Résultat enregistré dans les journaux de l'exécution.
- **Aucune validation matérielle :** la machine CI ne mesure ni RAM utilisable, ni batterie réelle, ni chauffe sur RK3566. Les données du simulateur restent distinctes des observations sur robot.

Le **pont de télémétrie seul** n'émet jamais `floor_clear=True` ni `safe_area=True`. L'étape **J2c** a ensuite ajouté un fournisseur **distinct** de vérité terrain MuJoCo, attesté sur la scène plane constructeur épinglée. Ce fournisseur n'existe **pas** sur le robot physique ; hors de cette scène, aucun mouvement n'est autorisé.

## Compte rendu vérifié : 25 octobre 2026

- **Exécution** : [MuJoCo headless smoke test #40145369078](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078) — Ubuntu 24.04, un seul robot, sans caméra, sous-modules `microduck` (`942e58e3`) et `microduck_rl` (`b02fdea4`) épinglés.
- **Conditions réelles du test** : installation du Python RL 3.12, MuJoCo 3.10.0, NumPy 2.5.4 et ONNX Runtime 1.28.0, compilation des démons Rust officiels, téléchargement de leurs politiques motrices et démarrage par `duck-sim up`.
- **Résultats** : contrôleur `healthy`, lecture `robot.health` à 49,9957 Hz, 0 échéance manquée dans les échantillons, MuJoCo à 1,00×, deux trames ToF de 64 zones, `sim_observer` retour `halt` et `errors=[]` ; `duck-sim down` réussit.
- **81 tests unitaires Python réussis**, compilation Python vérifiée, syntaxe `sh` validée ; **aucune commande de mouvement du cerveau**.
- **Diagnostic initial corrigé** : un premier essai CI réclamait OSMesa sans bibliothèque correspondante ; le backend MuJoCo headless sans caméra n'a pas besoin de cet override.
- **Limites** : `tof.frame` n'atteste pas `floor_clear` ; pas de déplacement initié par notre cerveau ni d'identification d'objets. Pas de test sur Microduck réel, ni de mesure thermique/énergétique embarquée.

La suite est le **lot C** : obtenir, avec une scène MuJoCo bornée et une source de vérité terrain vérifiée, des informations `safe_area` et `floor_clear` suffisamment fiables pour décider d'autoriser ou non un déplacement contrôlé.

## Synthèse factuelle après J2e — décision pour la suite

| Élément | Résultat vérifié | Portée |
| --- | --- | --- |
| Test suite | **142/142 tests Python réussis** ([CI `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176905506)) | Logiciel seulement |
| Démons constructeur et ToF | `robotd` sain ~50 Hz, MuJoCo 1,00× ; ToF 8×8 | Simulation |
| Zone de sol sûr | Vérifiée **uniquement** dans la scène MuJoCo officielle épinglée | Pas une preuve du sol réel |
| Intention `explore`, `robot.move`, `robot.stop` | Ordres bornés exécutés, `stop` explicitement accepté | Simulation |
| Politique de marche | `walk` sur **23/24** échantillons ; vitesse appliquée ~0,12 m/s | Ne démontre pas la propulsion |
| Translation du tronc | **0,820–2,574 mm** sur quatre essais | **Critère 10 mm NON atteint** |
| Mémoire | `no_progress_observed`, récompense négative modérée et adaptation de préférence | SQLite locale à chaque essai CI ; bases éphémères entre jobs |
| Robot physique | Aucun essai | Validation matérielle inconnue |

**Décision :** instrumenter **sans nouvelle commande motrice** les contacts, mouvements articulaires et poses dans le simulateur épinglé (P0a), comparer et isoler la cause (P0b), puis seulement retenter la translation mesurée (P1a). [Plan d'action détaillé](plan-action.md).

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

Les adaptateurs **de lecture seule** ont été codés et validés sur les démons simulés. **Depuis J2d/J2e, une voie de commande strictement bornée et autorisée volontairement** a aussi été vérifiée via `robotd`. Il manque toujours un adaptateur général à intentions sûres et une boucle autonome multi-cycles. Aucune requête Qwen, aucune inférence NPU, aucune modification de la politique motrice OEM.

## Lot A — Environnement et lancement du simulateur (J1b : validé sur Ubuntu CI)

**Livrable :** journal de démarrage et checklist de prérequis. Essai CI disponible avec `DUCK_SIM_DEP_MODE=runtime sh scripts/sim-smoke.sh run` (MuJoCo 3.10.0, NumPy 2.5.4, ONNX Runtime 1.28.0), ou installation RL complète via `uv sync --frozen`.

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

**Acceptation A : satisfaite pour un premier essai Ubuntu CI** ([journaux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078)). `duck-sim` a démarré, le robot s'est levé via son contrôleur constructeur, la santé a été mesurée et le simulateur a été arrêté proprement. Rejouer sur une autre machine pour vérifier la reproductibilité ; ne pas passer à la commande autonome en cas de simulation instable.

## Lot B — Acquisition JSON-RPC, sans aucune commande motrice (lecture validée en simulation)

**Livrable :** adaptateur de télémétrie testable à partir de messages de sockets.

1. Implémenter un petit client JSON-RPC 2.0 **NDJSON** avec délais, arrêt propre, reconnexion, numéros de requête et validation de schéma ; ne pas ajouter de broker.
2. Souscrire à `robot.subscribe` sur le socket de `robotd` pour recevoir `robot.state` et lire `robot.health` à cadence modérée (seul `robotd` est source autoritative pour ses états).
3. Souscrire à `tof.stream` sur le socket propre de `tofd`, qui publie des `tof.frame` 8×8. Distinguer distance en **millimètres**, statut de zone et absence de mesure ; ne jamais convertir une cellule invalide en distance libre.
4. Relier les événements au schéma v1 en utilisant **l'heure monotone de réception** et, si les deux sources le permettent, comparer `robot.state.t_ns` et `tof.frame.t_ns`. Les valeurs `t_ns` sont censées utiliser le même `CLOCK_MONOTONIC` sur un même hôte ; vérifier l'environnement avant corrélation.
5. L'adaptateur attribue la provenance selon le **socket réellement utilisé**, non depuis un champ reçu du réseau ni depuis Qwen. Toute source non identifiée ou silencieuse reste `unknown`.

Le périmètre des mesures comporte : `battery_pct` dérivé de `robot.health` lorsque présent ; `obstacle_m` seulement si le ToF est interprétable, cohérent et pertinent dans le repère ; `person_visible` et `object_label` sont **inconnus** à cette étape, sauf injection de données fictives **explicitement étiquetées**.

**Acceptation B : partiellement satisfaite.** Capture de données authentiquement issues des démons simulés et tests des cas d'erreur (faux sockets) réussis. La reconnexion automatique, l'endurance et la robustesse sous pertes répétées restent à développer/vérifier. Le programme reste **en lecture seule**.

## Lot C — Contrat de sécurité et validité des zones

**Livrable :** décision conservatrice sur l'autorisation d'agir.

Le ToF 8×8 orienté par la tête n'est **pas** un capteur de sol garantissant l'absence de marche ou d'escalier. Une `safe_area` saisie par opérateur ne prouve pas non plus `floor_clear`. Le schéma v1 demande, en environnement `simulator`, un `safe_area` fourni par opérateur ou simulateur **et** un `floor_clear` provenant du simulateur.

1. Pour l'observation seule : autoriser `halt` par défaut, même si la fenêtre MuJoCo affiche un sol plat.
2. Pour une première démonstration de mouvement : définir une petite scène de test bornée (sol plat documenté, zone sans bord, obstacles connus). Explorer si le simulateur fournit une **vérité terrain vérifiable** sur le sol, ses contacts, limites et collision. Si cette preuve n'existe pas dans les interfaces, développer un petit fournisseur de vérité terrain côté simulateur, avec tests ; **ne pas usurper** `floor_clear=True` en permanence.
3. Construire la validation de zone : limites connues, capteurs disponibles, vitesse/temps limités, commande expirant sans rafraîchissement ; ajouter des tests où le sol devient incertain ou la position sort de zone.
4. Si une certification simulée du sol n'est pas obtenue, **bloquer les déplacements** et terminer d'abord les lots de lecture et de regard sans translation.

**Acceptation C :** les décisions `halt`/`rest` sont démontrées pour observation périmée, donnée incohérente, obstacle, capteur perdu et batterie simulée faible. Toute autorisation de mouvement porte une justification provenant d'une source simulée réellement vérifiée.

## Lot C — Première preuve de zone par scène MuJoCo épinglée (validée en simulation J2c)

Une scène plane officielle contenant un seul Microduck et un sol infini permet une **preuve de géométrie limitée au monde simulé**, pas une preuve à partir du ToF. `sim_flat_zone.py` vérifie : commit RL exact, checkout propre, hash Git de `scene.xml`, processus Linux authentifié par PID et ligne de commande du serveur du corps (scène par défaut, `--headless`, `--ducks 1`), puis pose lue par `op=read`.

Le centre de test est l'origine de la scène. Rayon maximal 0,90 m, marge d'encombrement 0,16 m, arrêt si la distance résiduelle à la limite devient inférieure à 0,35 m. L'altitude du tronc et la gravité projetée doivent indiquer un robot debout ; un autre scénario, une pose absente ou une valeur non finie entraînent le refus. La preuve de pose expire après 0,35 s, et les télémétries `robotd`/`tofd` doivent rester fraîches et cohérentes.

**La vérification en situation MuJoCo officielle a réussi** ([CI #40173323079](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173323079)) : pose (0,0257 ; 0,0069 ; 0,1155) m, réserve de zone 0,7134 m et première intention `explore` fondée sur une preuve de simulation, aucune commande moteur. L'API demeure limitée à `sim_zone_probe` en lecture seule jusqu'au lot de commande distinct.

## Lot D — Passer des intentions de haut niveau aux commandes officielles

**Livrable :** adaptateur de commandes indépendant du cerveau, initialement désactivé.

1. Définir une liste blanche minimale : `robot.look` (regard orienté), `robot.move` (mouvement continu à paramètres bornés), `robot.stop`. Le mouvement attend l'acceptation du lot C ; démarrer par des actions non translatoires en situation saine.
2. Respecter le protocole officiel : `robot.look` et `robot.stop` sont des requêtes ; `robot.move` est une **notification continue** avec `vx`, `vy`, `vyaw`. Vérifier les valeurs, plafonds et la temporisation de la politique/deadman officielles avant toute émission.
3. Permettre uniquement une durée courte par intention, avec une autorisation explicite pour la simulation ; en cas de capteur périmé, socket débranché, réponse refusée ou arrêt du compagnon, cesser les notifications et demander `robot.stop` si possible.
4. Garder le contrôle physique et la boucle à 50 Hz sous `robotd`, sans commande de servo, sans mutation de ses limites ni appels bloquants venant du cerveau.
5. Tester séparément le client par un **faux socket** ; ne jamais faire d'un faux accusé de réception une preuve de mouvement réussi.

**Acceptation D :** en simulation stable et zone certifiée, le compagnon peut demander au robot de regarder puis, si les conditions sont réunies, effectuer un mouvement limité et s'arrêter. Les refus de `robotd` sont respectés et consignés.

## Premier essai J2d — ordre moteur strictement borné (commande/arrêt validés ; marche non démontrée)

Le jalon J2d a introduit `sim_motion.py`, séparé de la perception et des contrôleurs OEM. Après validation explicite du cerveau `explore` et de la zone plane MuJoCo épinglée, un client envoie à `robotd` au plus **4 notifications `robot.move`** à 0,05 m/s vers l'avant, avec 0,1 s entre deux et une durée totale ~0,4 s. Les validations de scène/processus/pose et de santé moteur sont renouvelées avant chaque notification ; une réponse `robot.stop` sans erreur est obligatoire. En cas d'échec de liaison, aucun nouveau mouvement n'est émis ; l'expiration constructeur des intentions (~500 ms) reste une protection de dernier ressort.

Le contrôle d'exécution exige deux autorisations explicites (paramètre CLI et variable d'environnement). Le workflow sur la branche principale ne les émet pas ; l'essai CI est limité à la branche expérimentale. **Validation CI [#40173809463](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173809463) :** 115 tests Python, MuJoCo sain à 1,00×, 4 notifications `robot.move`, `robot.stop` confirmé, et variation positionnelle du tronc de **0,0001848 m** sur 0,36 s simulée. **La communication motrice et le stop sont validés en simulation, pas le déplacement effectif**, car cette variation de 0,185 mm peut provenir du maintien d'équilibre. L'essai ne mesure ni collisions en maison, ni comportement autour d'un animal.

## Expérience J2e — choisir, agir, mesurer, mémoriser (validée techniquement ; translation insuffisante)

Le contrôleur officiel a un seuil par défaut de sélection de politique de station debout de 0,05 m/s (`duck-control/src/policy.rs`). L'essai précédent à cette vitesse n'a confirmé que l'ordre/arrêt avec ~0,185 mm de mouvement du tronc. Le nouvel essai `sim_walk_trial.py` utilise une vitesse avant fixe 0,12 m/s pendant au maximum **24 notifications** espacées de 0,1 s. Il ne peut fonctionner que sur la scène MuJoCo épinglée, sans obstacles ni caméra, et exige une sécurité vérifiée et une batterie simulée suffisante.

Avant toute notification, il compare deux positions du tronc à ~0,3 s d'intervalle sans mouvement demandé, afin de mesurer la dérive de référence. Chaque pas vérifie à nouveau l'identité de la scène/processus, l'horloge MuJoCo, la position et la santé `robotd`. Il réclame `robot.stop` en fin de séquence, et n'enregistre que des conséquences mesurées après cet arrêt. Toute observation contradictoire annule l'essai. Une seule séquence est possible, avec opt-in explicitement demandé.

La base SQLite privée conserve `sim_motion_trials` et `intent_preferences` pour l'environnement `simulator`, indépendamment des objets individuels. Un déplacement de plus d'1 cm, suffisamment supérieur à la dérive initiale et accompagné de confirmations d'arrêt et de sécurité, peut produire une faible préférence positive ; l'absence de progression vérifiée produit une faible préférence négative. Dérive élevée et confirmation incertaine sont conservées sans récompense. Il s'agit d'**apprentissage d'une préférence mémorisée**, pas d'entraînement d'un modèle. Le choix suivant de `AutonomyBrain` lit cet état. La translation du tronc n'atteste pas à elle seule la marche.

**Validation MuJoCo réalisée, objectif de marche non atteint** : [CI J2e-A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175133570) a mesuré 1,242 mm sur 12 notifications (dérive 0,105 mm), [J2e-B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175696383) 0,820 mm sur 12 (dérive 0,037 mm, `walk` 11/12), et [J2e-C](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176018018) 1,399 mm sur 24 (dérive 0,273 mm, `walk` 23/24). `robotd` a reporté une vitesse appliquée proche de 0,12 m/s sans limitation persistante ; `robot.stop` a été confirmé. Chaque base SQLite de CI, éphémère et isolée, a enregistré `no_progress_observed`, récompense -0,5 et préférence 0 → −0,075. **Aucune marche effective ne peut être annoncée ; la translation minimale ne franchit pas le seuil expérimental de 1 cm.** Un quatrième essai [CI finale #40176410817](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) a effectué 24 commandes, obtenu **2,574 mm** avec dérive **0,192 mm** et confirmé `robot.stop`. Le workflow technique a terminé **avec succès** (142 tests, verdict distinct `WALK_TRANSLATION_ACCEPTANCE=NOT_MET`). Les prochains diagnostics doivent porter sur la cinématique / les contacts et le modèle locomoteur. Aucun résultat matériel n'a été validé.

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

**Acceptation E : partiellement satisfaite.** Une séquence bornée `observation -> choix -> action via robotd -> conséquence observée -> mémoire -> choix suivant` est exécutée en simulation et a appris `no_progress_observed`. Une **vraie boucle multi-cycles**, avec redémarrage du processus et réutilisation effective d'un souvenir entre sessions CI, reste à développer et démontrer. La locomotion significative n'est pas validée.

## Ordre initial des livraisons (historique) et stratégie Git

| Livraison | Contenu dans notre dépôt | Dépendance |
| --- | --- | --- |
| J1b / A | procédure environnement + journal de santé et temps réel | aucune |
| J2a / B | client JSON-RPC et adaptateur de télémétrie, tests sans mouvement | J1b |
| J2b / C | définition et tests de zone/sol sûrs en simulation | J2a |
| J2c / D | adaptateur des intentions vers `robotd`, initialement coupé, tests d'arrêt | J2b |
| J2d / E | démonstration enregistrée avec SQLite et métriques | J2c |

Ce tableau retrace l'ordre de conception initial ; **le prochain travail commence maintenant à P0a** ([plan opérationnel](plan-action.md#5-trois-prochaines-pr-concrètes)). Créer des PR ciblées. Pour chaque modification : relire les interfaces officielles épinglées, ajouter les tests, vérifier les résultats réellement accessibles, archiver échecs et mesures, puis actualiser README et le plan canonique. **Ne pas considérer des tests Python comme une preuve de locomotion MuJoCo.**

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
