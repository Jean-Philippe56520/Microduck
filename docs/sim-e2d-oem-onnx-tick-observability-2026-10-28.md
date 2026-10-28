# SIM-E2-D — Porte constructeur pour les observations et actions ONNX par tick

**Date : 28 octobre 2026. Statut : audit des sources effectué, diagnostic OEM *proposé*, non codé, non testé.** Suivi : [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101) ; plan directeur : [docs/plan-action.md](plan-action.md). **Aucune commande motrice, capture de médias, installation de poids, nouvelle interface, sous-module modifié ou essai de marche au titre de ce lot.**

## 1. Observation, question falsifiable, risque, échec et retour arrière

Sur WSLg, le simulateur constructeur a accepté une consigne de 0,08 m/s et signalé 31 `walk` sur 32 mesures, mais seulement **3,500 mm nets** de translation du tronc. Les quatre offsets signés au repos se retrouvent à l'ordre de grandeur près dans l'archive **P0e** du 25/10/2026 ; pendant une ancienne fenêtre `walk` les consignes `data.ctrl` des hanches roulaient d'environ 6°, leurs positions de 0,2–1°. P0e/P0j ont déjà examiné le gain, la force et les doubles contacts ; P0f/P0h ont validé le contrat statique des réseaux v8. **Aucune de ces preuves ne fournit le tableau `[61]` réellement soumis à l'ONNX de `robotd` et le tableau `[14]` qu'il a retourné lors du même tick.**

Question discriminante : *un diagnostic constructeur existant sait-il produire, sans intervention motrice, une paire `obs/actions` provenant de la même inférence, identifiée par son tick, son modèle, son état de remise à zéro et ses limites ?* **Réponse pour l'OEM épinglé : non, dans les méthodes publiques et publications inspectées.** Hypothèses de divergence d'observation/historique/filtrage ou de modèle d'actionnement BAM/MJCF restent **hypothèses**.

Risques si instrumenté à l'aveugle : ralentir la boucle 50 Hz/20 ms, faire entrer les valeurs privées dans une journalisation, produire des couples d'échantillons non synchrones, exposer une méthode sensible à l'app ou aux transports sans permission, ou confondre un tableau reconstitué avec l'entrée ONNX effective. **Porte d'échec :** pas de capture fidèle dans le même chemin constructeur ; horodatage, politique, sécurité ou performance non contrôlés ; écart avec la version/scene/ONNX réellement chargés. **Retour arrière :** ne pas activer de nouvelle sonde ; conserver le constructeur et son IPC inchangés.

## 2. Audit exact des sources officielles

**Versions contrôlées :** gitlink `upstream/microduck` **`942e58e3aa6dbb28e7037203fff11866122c7567`** ; gitlink `upstream/microduck_rl` **`b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`**. `main` OEM consulté en lecture seule le 28/10 au SHA `6cdfdaad21bed25e01b450c0dd4e0aee0ae19fde` ; **ne fait pas partie du pin**. Les PR OEM [#381](https://github.com/pollen-robotics/microduck/pull/381) (brain) et [#414](https://github.com/pollen-robotics/microduck/pull/414) (maploc) sont **ouvertes/non fusionnées** au contrôle ; elles ne constituent pas une API de trace ONNX livrée.

| Référence OEM épinglée | Fait vérifié |
| --- | --- |
| [`duck-ipc-proto/src/lib.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs) : `Call`, `SubscribeResult`, `RobotState` | `robot.subscribe` publie `robot.state` : joint/targets/velocities optionnelles, IMU, gravité, `move.applied`, tête, politique, horloge `t_ns`. **Aucun champ `obs[61]`, `raw_actions[14]` ou `last_action[14]` ; aucune méthode typée `robot.policyTrace`/équivalente identifiée.** |
| [`duck-control/src/obs.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-control/src/obs.rs) | `Observation::build` assemble `[61]`, en particulier **14 actions brutes précédentes** dans les indices `34:48` ; corps x/y/yaw codés à zéro. |
| [`robotd/src/control.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs) | La paire exacte n'existe que localement : `let observation = Observation::build(... &self.last_action ...)` puis `let action = self.policy.infer(&observation, net)?`, `self.last_action = action` ; conversion de 14 actions en cibles HOME+échelle+filtre **après** inférence. Des skills, le sit et une pose active peuvent ré-encoder les commandes. |
| [`duck-control/src/policy.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-control/src/policy.rs) | `Network::run` transmet l'observation à ONNX Runtime ; vérifie 14 sorties finies, gère l'état récurrent si applicable, les resets et les changements de réseau. Pas de journal de la paire brute dans la voie consultée. |
| [`robotd/src/main.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/main.rs) | `robot.state` est construit **après** le calcul des cibles et l'appel `safety.apply(targets, hold, gain)` ; les cibles publiées sont celles du contrôleur **avant** le filtre final de sûreté et le résultat d'écriture ne figure pas dans une confirmation par joint. `t_ns` est l'instant de lecture des capteurs. |
| [`robotctl/src/main.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotctl/src/main.rs), [`robotctl/src/monitor.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotctl/src/monitor.rs) | `robotctl monitor --json` réémet la **même** trame `robot.state` sans observation interne supplémentaire. L'abonnement est décimé, sa lecture ne doit jamais bloquer le propriétaire moteur. |
| [`duck-control/examples/policy-rehearsal.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-control/examples/policy-rehearsal.rs), [`docs/recurrent-policies.md`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/recurrent-policies.md) | Outil officiel de **rejeu hors ligne** : accepte une séquence `[61]` fournie avec marqueurs `reset` et retourne 14 actions/latence ; ne collecte pas lui-même les entrées d'un `robotd` actif. |

**Limite d'assertion :** l'audit porte sur les interfaces et code source vérifiés de ces versions, pas sur d'éventuels outils privés/internes non publiés. Des champs télémétriques potentiellement dérivables ne constituent **pas** le vecteur brut effectivement inféré.

## 3. Matrice des 61 observations : accès public ≠ équivalence des valeurs ONNX

| Indices ONNX | Bloc | Largeur | Disponibilité via `robot.state` |
| --- | --- | ---: | --- |
| `0:3` | Gyro tronc | 3 | `imu.gyro` si IMU présente, même lecture de capteurs du tick |
| `3:6` | Gravité projetée | 3 | `safety.gravity`, même bloc de capteurs |
| `6:20` | Joint angles − pose HOME | 14 | `joints` (15 joints, **bouche exclue**) + HOME épinglée ; dérivé de mesures, pas entrée publiée |
| `20:34` | Vitesses articulaires | 14 | **Conditionnel** : `velocities` peut être absent si publication désactivée, simulation/fake ou backend incompatible |
| `34:48` | Actions brutes *précédentes* | **14** | **Absent** : état privé `Controller.last_action`, non déductible de `targets` filtrées à fréquence décimée |
| `48:51` | Twist de l'ONNX | 3 | `move.applied` **conditionnel** ; un skill, sit/rise, pose active ou transition peut modifier la commande effective à l'intérieur de `Controller::step` |
| `51:55` | Commande tête | 4 | `head` **conditionnel** ; les skills peuvent la remettre à zéro ; ne pas présumer équivalence des commandes publiques et des entrées du réseau |
| `55:61` | Pose du corps (x,y,z,roll,pitch,yaw) | 6 | **x/y/yaw forcés à zéro** par l'OEM ; **z/roll/pitch** issus de l'intention de pose, **non publiés** comme entrée ONNX. Ne pas inférer qu'ils sont nuls sans preuve d'absence de pose |

**Bilan :** au mieux **44 valeurs sur 61** possèdent une source de télémétrie, une transformation conditionnelle ou une constante source (3 + 3 + 14 + 14 + 3 + 4 + 3) ; **17 sur 61 manquent structurellement** (14 historique + 3 pose). Les 44 ne sont **pas** « 44 valeurs ONNX observées » : leur disponibilité, la phase de contrôle, l'absence de skills/pose, les filtres et les horloges doivent être vérifiés. Les **14 actions brutes courantes de sortie** sont **0/14 exposées**. Le schéma `robot.state.targets[15]` n'y remédie pas : cibles converties après l'ONNX, avant sûreté, bouche hors réseau.

## 4. Matrice réutiliser / adapter / créer

| Choix | Décision | Justification |
| --- | --- | --- |
| `robotctl monitor --json`, `robot.subscribe`, `sim_joint_trace --joint-tracking` | **Réutiliser** | Télémétrie et erreurs de suivi disponibles, non intrusives, déjà testées sur WSLg |
| `sim_policy_contract` P0f et `policy-rehearsal` OEM | **Réutiliser si un vecteur *authentique* devient disponible** | Contrats, échelle, home, resets, inférence hors ligne ; ne fournissent pas l'observation manquante |
| Espionner `data.ctrl`, inverser les filtres, réexécuter un ONNX avec actions précédentes fictives, `RUST_LOG=trace` au hasard, `gdb` sur robotd | **Refuser comme preuve** | Non équivalent aux tenseurs du tick ; risque de confusion, de blocage à 50 Hz ou de perturbation |
| Nouvelle socket/moteur/contrôleur Companion, changement d'ONNX ou de gain | **Ne pas créer** | Doublon et rupture de l'autorité OEM, sans lacune de logique motrice avérée |
| Faculté de trace **à l'intérieur du code OEM** avec accord constructeur/opérateur et preuve de coût | **Proposition distincte, non autorisée/codée ici** | Seul le chemin `Observation::build → Policy::infer` possède les deux tenseurs exacts au même tick |

La revue [registre communautaire C3](community-reference-registry-2026-10-26.md) ne fournit pas de justificatif pour importer un pilote tiers dans le propriétaire moteur. Les PR OEM ouvertes #381/#414 ne changent pas cette conclusion pour le pin actuel.

## 5. Proposition OEM optionnelle, non implémentée

Si le fabricant recommande une instrumentation, la proposer sous forme d'une **faculté de diagnostic locale** dans `robotd`, et **pas** comme une extension motrice Companion :

1. **Même tick, même code constructeur** : capturer juste après `Observation::build` et `Policy::infer`, avant toute échelle/filtre, avec `t_ns` du capteur, numéro de tick, mode `walk/stand/skill`, nom du modèle réellement sélectionné, état reset/switch, `obs[61]` et `raw_action[14]` ; marquer les échecs/restarts. Le snapshot doit distinguer clairement les commandes finales post-filtre et le résultat de sûreté si disponibles, sans affirmer un effet physique.
2. **Sûreté et ressources** : hors ligne et **désactivé par défaut** ; uniquement sur banc de simulation dans un premier temps, accès Unix local authentifié/autorisé (pas WebRTC, BLE ou réseau), opt-in explicite, un collecteur, durée/échantillons plafonnés, tampon préalloué borné **sans I/O bloquante ni allocations ajoutées dans le tick 50 Hz**. Taille/durée à choisir après mesure, sans imposer arbitrairement une mémoire embarquée.
3. **Confidentialité** : pas d'images, sons, identités, SQLite privée, export cloud ou journal disque continu ; effacement à expiration, fichiers hôte éventuels locaux seulement avec accord. Sans authentification ou sur robot réel non supervisé, refus.
4. **Preuve positive et négative** : tests OEM sur ticks fidèles, transition `stand→walk`, interruptions, changement de modèle, reset, drop/buffer plein, erreur ONNX, captations refusées ; comparaison exacte des tenseurs à l'entrée `Network::run`. Une trace ne vaut pas preuve de contact ou de marche.
5. **Critère de livraison** : mesurer **avant/après** cadence 50 Hz, dépassements 20 ms, durée d'inférence, RSS CPU/RAM, températures (uniquement quand robot disponible), temps et fréquence de capture. Toute régression de sûreté, timeouts ou fuite de données bloque déploiement. Fusion OEM/validation et pin revus **avant** adaptation Companion.

**Ne pas implémenter cette méthode dans le gitlink OEM ou ouvrir une PR constructeur sans un chantier et un accord distincts.** Le constructeur reste le seul propriétaire du contrôle, et les observations internes restent **inconnues** tant qu'une trace de cette nature n'a pas été validée.

## 6. Décision d'étape et statut de preuve

**Fait vérifié :** protocole public `robot.state` **insuffisant** à une reproduction exacte de `[61] → [14]` au tick OEM ; `policy-rehearsal` a un rôle complémentaire **après** acquisition des entrées, pas avant. **Prévu :** une éventuelle discussion constructeur pour un traceur opt-in. **Non codé/testé :** tout instrument OEM, nouvelle API, captation réelle ONNX. **Simulé antérieurement :** P0d/e/i/j et SIM-E2-A/B/C, sans gait prouvée. **Validé robot : rien**. Aucune expérience d'objet ni récompense causale possible sur ces seuls résultats. Maintenir [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101) ouverte et poursuivre les chantiers cognitifs indépendants si aucun accès OEM sûr n'est disponible.
