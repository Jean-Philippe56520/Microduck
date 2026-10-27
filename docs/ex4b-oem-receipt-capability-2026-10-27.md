# EX4-B — Contrat des accusés OEM v44 et frontières de preuve

**27 octobre 2026 — code de revue de trames sur fixtures, jamais un client de commande ni une mémoire causale sur robot.** Le chantier poursuit l'[issue #80](https://github.com/Jean-Philippe56520/Microduck/issues/80) après EX4-A [PR #88](https://github.com/Jean-Philippe56520/Microduck/pull/88). Il est basé sur la branche EX4-A, encore en revue ; les deux PR doivent donc être intégrées dans cet ordre. Cat-A2b [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78) manque toujours de vraies photos basses autorisées.

## Audit des sources, réutilisation et limites

Le socle fait foi **aux gitlinks du projet** : [microduck 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) et microduck_rl b02fdea4. Le protocole [duck-ipc-proto/src/lib.rs](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs) est à l'**API_VERSION = 44**, non l'API v45 de la [PR OEM #414](https://github.com/pollen-robotics/microduck/pull/414). [robotd/src/main.rs](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/main.rs) montre le chemin exact de dispatch IPC et [robotd/src/control.rs](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs) l'arbitrage différé des animations. La [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) (cerveau proposé) et #414 sont toutes deux **ouvertes/non fusionnées** lors de cette revue.

| Élément | Observé dans la révision épinglée | Décision |
| --- | --- | --- |
| robot.move, robot.head | Intentions continues par notifications sans ID/réponse habituels ; requête avec ID également acceptée, mais la réponse n'atteste qu'une prise en compte IPC | Ne jamais inférer une exécution ou un déplacement depuis le transport |
| robot.do | IntentResult accepted/refused à l'entrée ; accepted signifie **mise en file**, l'arbitrage motorisé au tick suivant peut encore rejeter ou retarder une animation (occupé, assis, etc.) | **Refus explicite** lorsqu'une résolution finale est prétendue par le seul ack |
| robot.look | LookResult avec cibles articulaires et indicateur clamped. Le calcul et l'envoi de cibles vers Intents ne sont pas la mesure d'un regard atteint | Conserver seulement target_computed/target_clamped |
| robot.stop | IntentResult accepted après mise à zéro de la consigne de vitesse ; ne signifie ni limp ni arrêt de toutes les animations | Conserver zero_velocity_requested, jamais une fin d'action |
| robot.subscribe / robot.state | Flux d'état décimé, potentiellement lacunaire, horloges t (depuis démarrage) et t_ns (CLOCK_MONOTONIC), champ move.requested/applied/limited_by et mesures articulaires facultatives | Télémétrie informative et **non reliée** à un ID de commande |
| robot.health, robot.policies | Santé du démon et inventaire des skills ; ne fournit aucun résultat lié à une expérience EX | Rester en lecture uniquement, ne pas forger de reçu de geste |
| robotd Intents, duck-control Safety | robotd détient le seul accès bus ; deadman et clamps moteurs. Les requêtes passent avant le contrôle au prochain tick | **Ne pas modifier** les frontières ni créer un arbitre concurrent |
| EX4-A, ExperienceMemory, EX1–EX3, F4-A et sim_ipc X2-A | Un filtre de provenance SQLite, une mémoire unique et un lecteur de télémétrie **lecture seule**, sans identité de matériel garantie | **Réutiliser** les gardes de provenance et n'ajouter ici aucun écrivain, socket ni seconde mémoire |
| Registre communautaire C3 : QuackNav/microduck-brain, Quacksat, Twin, GC/Smartulf, Lab/Studio | Références utiles pour navigation, audio, interface, mais pas une attestation OEM par action de Companion | Aucun import, changement de licence, nouveau modèle/poids ni commande tiers |

**Décision « créer » :** le module [ex4b_oem_wire_audit.py](../microduck_companion/ex4b_oem_wire_audit.py) est un validateur **pur** de quelques enveloppes JSON-RPC v44 synthétiques, distinct de sim_ipc car il ne lit aucun socket. Il inspecte la différence entre réponse IPC et fait physique et démontre l'absence de rattachement causal ; le lecteur sim_ipc conserve son rôle de télémétrie passif.

## Contrat programmé, sans voie d'exécution

- OemWireProposal : session opaque EX1, séquence et émission chronologique de test, paquet JSON-RPC explicitement fictif, **SHA OEM exact et API 44**. Aucune entrée n'est envoyée à un robot.
- OemWireFrame : réponse JSON-RPC ou notification robot.state **synthétique**, avec heure locale test, sans revendication d'authentification.
- review_oem_wire_fixture : vérifie ID, méthode, forme des paramètres, champs et types, ordre des horloges, fenêtres locales bornées (30 secondes de fixture uniquement), refus et contradictions. Accepte au plus huit états par audit.
- review_oem_wire_batch : au plus 64 cycles ; rejette les doublons (session, séquence) et les IDs RPC réutilisés **dans le lot uniquement**. Il ne prétend pas garantir l'idempotence interprocessus ni à travers les redémarrages.
- OemWireVerdict : reply_status et state_status descriptifs, avec **authorized = not_attested**, **executed = not_attested**, **physical_execution_verified = false**, **causality_established = false**, **physical_learning_allowed = false**, **motor_commands_issued = 0** dans tous les cas.

Cas strictement reconnus : robot.do, robot.look, robot.stop, robot.move et robot.head. Les autres méthodes mutatrices (enable, init, relax, setMode, etc.) sont **refusées par l'audit**, non parce que l'OEM les interdit mais parce qu'elles sont hors périmètre EX4-B. L'audit n'ouvre pas les méthodes, n'envoie pas de paquets, ne crée pas de contrôleur. Les messages avec faux champs executed/completed sont refusés. Une notification robot.state fraîche après un ack reste coherent_unlinked_telemetry, jamais une preuve que **cette** commande s'est exécutée : plusieurs clients peuvent être actifs, les états sont décimés, le contrôleur arbitre dans une boucle distincte.

Les horodatages locaux et SHA/API présents dans les fixtures sont **déclarations de test et non authentification cryptographique ou matérielle**. Le fait que la réponse JSON-RPC possède un ID correct ne certifie ni le processus répondant, ni l'absence de mouvement concurrent, ni l'arrivée de la consigne au bus. Une state avec t_ns=0 indique une horloge incomplète, pas une pose initiale prouvée ; un reset ou un échantillon en désordre dans un lot est rejeté.

## Tests et confidentialité

Tests dans [test_ex4b_oem_wire_audit.py](../tests/test_ex4b_oem_wire_audit.py) : acceptation/suspension du skill, refus explicite, stop, gaze clamped et non clamped, notifications continues sans ack, ack avec ID, RPC error, faux champs executed, doublons, source/API/OEM SHA erronés, reset d'horloge, reprise de valeurs, timestamps périmés/futurs, mouvement limité, chute, limp et pickup, capteur/politique inconnus, erreur de forme, comportement fail-closed et zéro récompense. Les tests Python GitHub Actions restent des **fixtures OEM**, sans exécuter robot.do, sans servos, caméra, micros, réseau ni Qwen.

Aucune photo, identité, voix, identifiant matériel personnel, journal moteur brut ou snapshot privé n'est committé. **Aucune nouvelle table SQLite, migration, poids, cache, writer ni export continu** : CPU/RAM/SQLite/WAL incrémentaux du module non mesurés sur RK3566 ; le coût hôte GitHub ne permet aucune extrapolation à 1 Go RAM. Toute mutation future serait un chantier distinct après resource-audit.sh sur le robot.

## Après EX4-B : conditions d'un véritable reçu d'exécution (non livrées)

Le constructeur doit fournir ou permettre de vérifier un mécanisme compatible et sécurisé de corrélation **intention unique → autorisation moteur → prise en charge par la boucle → événement démarré → fin/refus/interruption**, lié à l'identité du processus, à un horodatage monotone et à des observations indépendantes. Un simple ID JSON-RPC ne suffit pas ; un flux robot.state ne contient actuellement pas le journal transactionnel requis. Modifier le protocole OEM, s'il s'avère indispensable, exigera un projet constructeur distinct, comparaisons de compatibilité et validations avec Pollen avant adoption. **Ne pas concevoir ici un nouveau démon moteur ou contournement de Safety.**

En l'absence de ces preuves : conserver les souvenirs descriptifs et l'état indeterminate ; aucune récompense, adaptation de préférence motrice ou conclusion causale. EX4-C reste tributaire du matériel réel et de Cat-A2b pour les conséquences visuelles. EX0 emploie aussi le nom EX4 pour Qwen/affordances : ce volet reste séparé de l'EX4-B issue #80.
