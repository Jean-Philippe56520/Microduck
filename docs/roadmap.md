# Feuille de route — Microduck Companion

Mise à jour : 2026-10-25. **La [nouvelle organisation opérationnelle F0–F8](plan-action.md) définit seule les priorités, critères de sortie et prochaines PR.** Ce fichier conserve l'historique technique des **six phases précédentes** et des diagnostics P0a–P0j. L'[ancien plan P0–P8](plan-action-historique-2026-10-25.md) est archivé. Une case cochée indique la preuve explicitement mentionnée (code, tests logiciels, MuJoCo), **jamais** une validation physique par défaut. Les mentions « priorité P0 » ou « prochaine étude » plus bas appartiennent à **l'historique**, pas au backlog actuel.

**Ordre actuel :** F1-A [fusionné/testé](https://github.com/Jean-Philippe56520/Microduck/pull/24) → F1-B [fusionné/testé](https://github.com/Jean-Philippe56520/Microduck/pull/25) → **F1-C fusionné/testé sur `main`** : SQLite partagée, catégorie/`unknown` et provenance fictive, reprise par deux processus indépendants, rétention 14 jours et 512 lignes → **F1-D prochain** : démonstration passive complète → F2 intentions cognitives sans moteur, F3 vision/sons, F4 sociabilité, F5 Qwen facultatif, F6 embarqué, F7 matériel réel, F8 options. **Locomotion L en pause, P1a bloqué** ; aucune preuve sensorielle ni mouvement ajouté par F1-C. [Critères de passage](plan-action.md).

**État courant :** P0j [fusionné dans `main` (PR #22)](https://github.com/Jean-Philippe56520/Microduck/pull/22), [replay sans moteurs de P0e](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655) réussi : **[269 tests Python sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946)**, 79 relevés `stand` et 127 `walk` à 50 Hz, **127/127 appuis bilatéraux**, charge gauche moyenne **52,03 % → 44,54 %**, mais aucun appui unipodal observé ; aucune cause ni démarche validées. P0i [fusionné dans `main` (PR #21)](https://github.com/Jean-Philippe56520/Microduck/pull/21) et testé sur [MuJoCo officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) : alpha **1,444 mm** vs VelStand **1,968 mm**, 24 commandes par configuration, deux arrêts confirmés et deux modèles choisis par `robotd` vérifiés ; [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915). Seuil indicatif 10 mm **non atteint**, aucune causalité ni gait validées, P1a bloqué. P0h fusionné ([PR #20](https://github.com/Jean-Philippe56520/Microduck/pull/20)) : [243 tests Python sur main](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219827102) et [audit MuJoCo OEM / ONNX réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997). Le simulateur force `alpha_walking`/`alpha_stand` tandis que `robotd` utilise normalement `velstand`. Trois modèles v8 conformes et comparés sur observations synthétiques, **cause de non-marche toujours inconnue**. P2b [fusionné dans `main` (PR #19)](https://github.com/Jean-Philippe56520/Microduck/pull/19), avec **[234 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216649169)** et [six cycles cognitifs passifs testés sous MuJoCo officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) (3 puis 6 lignes persistées en SQLite, six `halt`, zéro moteur). P2a avait démontré huit cycles fictifs persistés. P0g : modèles compilés 76/82/141 géométries, 2/10/69 éligibles aux masques du sol ; la cause de non-marche demeure inconnue. Dernier essai moteur P0e 2,295 mm ; P1a bloqué, aucun robot physique testé.

## F1-C — Mémoire des catégories passives dans la SQLite existante ([PR #26 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/26))

- [x] `PassiveObservationJournal` complète **la connexion SQLite d'`ExperienceMemory`** sans deuxième base. Seulement `PassiveRead` venant du contrat fictif F1-B : environnement et source `mock`, canal fixe `mock_fixture_unix`, observations d'objet/son, aucun événement de sécurité ni commande motrice.
- [x] `identified`, `unknown`, `conflict`, `low_confidence`, `stale` et `future` conservés **sans promotion d'une incertitude en catégorie sûre** ; pas de `track_id`, transcription, nom libre, pixel ou voix brute. Les anciennes données sont **historiques**, jamais converties en perception encore fraîche.
- [x] Deux **processus Python distincts** rouvrent la même SQLite et retrouvent un nombre croissant d'observations de *catégorie* (1 puis 2), avec horloges monotones différentes et identifiants de session séparés ; cela n'identifie **aucun animal ou objet individuel**.
- [x] **Rétention logique de 14 jours**, borne physique à **512 lignes**, consultation plafonnée à 100, séquences idempotentes et purge du contenu ancien ou anormalement futur.
- [x] **Tests logiciels F1-C : [339 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234908502), dont 24 nouveaux scénarios** avec données fictives ; [rapport de conception et limites](f1c-passive-sqlite-memory-2026-10-25.md). Aucun robot physique ni `mediad` constructeur testé.
- [ ] **F1-D encore à faire** : scénario entier « observation → mémoire → nouvel événement → source absente → reprise », puis seulement critères de sortie F1.

## F1-B — Adaptateur de source passive à provenance explicitement fictive (PR #25, fusionnée et testée logiciellement)

- [x] `FixtureUnixReader` lit des catégories de fixtures via **socket Unix local** ; trame JSON bornée 8192 octets, délai global 3 s, données âgées d'au plus 2 s, débit ≤2 lectures/s, séquences strictement croissantes, maximum 64 événements et refus conservateur. Toute source acceptée reste `mock`, même si le service déclare `sensor`.
- [x] Sonde `probe_official_mediad()` vérifiant seulement `hello` sur l'API OEM ; sélection du chemin officiel, identité du pair Unix et version/révision épinglées avant toute qualification locale. **Aucune image via `media.frame` et aucun flux `media.detections` réellement consommé.** Un socket temporaire de test ne peut pas se prétendre constructeur.
- [x] [315 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234054024), **20 nouveaux** sur sockets Unix réels entre processus fictifs : interruption, silence/délai, doublons, trames excessives, usurpation de provenance, commande/sécurité refusées et `hello` uniquement.
- [ ] **Réception de vraies catégories OEM, voix/caméra et validation sur robot : non réalisées.** L'API examinée ne fournit pas une classification chien/chat/personne sur son socket local. Aucun moteur ni stockage d'image/son.
- [x] **F1-C fusionné séparément dans `main`** : journal de catégories fictives en SQLite, repris dans deux processus ; [rapport F1-C](f1c-passive-sqlite-memory-2026-10-25.md). La démonstration F1-D reste à faire.

[Rapport F1-B](f1b-passive-source-2026-10-25.md).

## F1-A — Contrat de perceptions passives (PR #24, fusionnée et testée logiciellement)

- [x] Réutilisation de `PerceptionEvent`/`PerceptionSnapshot` v1, ajout additif d'un événement `sound_label` limité à des catégories (pas de transcription, biométrie, modèle de son ou vraie capture).
- [x] Projection passive `summarize_passive` : `ball`, `toy`, `dog`, `cat`, `person`, `microduck` ou `unknown`, ainsi que signaux fictifs ; source **déclarée**, confiance ≥0,80, TTL, `track_id` éphémère, contradictions, limite 64 événements. Un événement non fiable, ancien ou incompatible ne devient pas un fait.
- [x] **[295 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40233207115)**, dont 26 nouveaux sur fixtures fictives ; `keyword_stop` n'est pas un arrêt moteur. Les données `safe_area`/`floor_clear` et les politiques OEM restent inchangées.
- [x] Inspection des sources `mediad` épinglées : `media.frame` propose une image brute locale ; `media.detections` fournit des boîtes de Microducks via une session WebRTC, **sans catégories animaux/personnes**. Aucune interface audio de catégories validée.
- [x] **F1-B fusionné et testé séparément**, puis **F1-C fusionné/testé sur `main`** pour observations persistantes fictives. Aucune classification ni identité constructeur réelle n'est acquise ; aucun média, moteur ou robot physique testé.

[Rapport F1-A](f1a-passive-observation-contract-2026-10-25.md). **F1-A/F1-B/F1-C fusionnées et testées au niveau logiciel ; prochaine étape F1-D.**

## P0j — Réanalyse hors ligne des forces de contact de P0e (PR #22, fusionnée)

- [x] Module `sim_p0j_load_transfer.py`, aucun socket ni pilote : trois SHA-256 immuables, 888 trames archivées, horloge physique continue, fenêtres `stand`/`walk` héritées de l'observation P0b 10 Hz et contrôle de `robot.stop` déjà archivé.
- [x] **[269 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946) et [replay OEM P0e réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655)** ; 12 nouveaux tests factices de classification des pieds, données manquantes/non finies, provenance et arrêt obligatoire.
- [x] **P0e recalculé :** repos 79/79 et marche 127/127 avec deux pieds chargés > 0,1 N ; **0/127 appui unipodal** pendant la fenêtre `walk`, répartition moyenne gauche 52,03 % au repos contre 44,54 % en marche. Les trajectoires de sites pied monde ne sont **pas** des vitesses de glissement réelles ; aucune force de propulsion signée exploitable dans le journal.
- [ ] **Causalité du défaut de propulsion, démarche stable et validation physique non établies.** Aucun nouvel essai moteur ; **P1a bloqué**.

[Rapport P0j](mujoco-p0j-load-transfer-2026-10-25.md).

## P0i — Comparaison bornée des politiques en deux boots MuJoCo (PR #21)

- [x] Banc expérimental : un essai `run_walk_trial` à **0,12 m/s** et **24 notifications** dans chaque nouveau processus OEM ; paire `alpha_walking/alpha_stand` d'abord, `velstand` avec `stand=none` ensuite, sélection effective vérifiée via `robotctl policy list`. Les trois SHA-256 ONNX v8 sont exigés, la scène et les révisions épinglées vérifiées.
- [x] **[257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915)** ; quatorze nouveaux tests couvrent les modèles, le manifeste, les refus, le stop, l'absence de données finies et la séparation des bras.
- [x] **[CI MuJoCo constructeur réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528)** : **alpha 1,443665 mm XY, VelStand 1,967688 mm XY**, variation +0,524023 mm ; 23/24 et 24/24 échantillons `walk`, deux confirmations `robot.stop`, PIDs différents, vitesse appliquée max 0,12 m/s, SQLite distinctes. **0/2 bras atteint 10 mm**.
- [x] Premier essai CI refusé sans commande B : confusion entre fichier modèle `robotd.toml` et paramètre réellement chargé `robotd-duck-a.toml`. Corrigée sans abaisser les exigences de sécurité.
- [ ] **Marche effective, cause racine et validation physique non démontrées.** Les premières mesures restent de petits déplacements relatifs ; contacts précis et inertie de la politique en boucle fermée non résolus.

[Rapport P0i](mujoco-p0i-controlled-policy-pair-2026-10-25.md).

## P0h — Sélection et filiation des politiques ONNX (PR #20)

- [x] **Contrat source :** `robotd` utilise normalement `velstand.onnx` sans slot debout, mais `duck-sim` force la paire `alpha_walking.onnx` / `alpha_stand.onnx` (seuil `0,05`). Provenance W&B déclarée dans les sources RL épinglées, sans preuve cryptographique d'identité des poids.
- [x] Nouveau diagnostic en lecture seule `sim_policy_lineage.py` et **[243 tests Python réussis sur main](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219827102)** : vérifications de sources, TOML, manifeste, `.source`, formes ONNX et refus conservateurs.
- [x] [CI MuJoCo officielle P0h réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) : trois modèles ONNX v8 présents, 10 entrées de manifeste, mêmes dimensions 61→14, SHA-256 différents, sorties CPU synthétiques différentes (L2 **0,2296** et **0,1524**) et **zéro nouvelle commande motrice**.
- [ ] Le rôle de cette divergence dans l'absence de translation n'est **pas prouvé**. P1a bloqué, pas de test matériel.

[Rapport P0h](mujoco-p0h-policy-slot-lineage-2026-10-25.md).

## P2b — Cycles cognitifs passifs reliés aux démons simulés (PR #19)

- [x] Exécuteur `sim_passive_cycles.py` : télémétries datées `robotd`/`tofd` via RPC limités en lecture, choix `AutonomyBrain`, journal SQLite de qualité/intention et reprise entre sessions, **sans API moteur et sans récompense**.
- [x] **234 tests Python réussis** sur branche : [CI P2b](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199119). Dix tests nouveaux, y compris sockets Unix fictives, reprise SQLite, horodatages, répétitions, pertes de capteurs et refus sûrs.
- [x] [CI MuJoCo constructeur](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) réussie : **3/3 + 3/3 cycles cohérents**, même SQLite réouverte, **3 puis 6 enregistrements**, séquences ToF progressives, `halt` six fois (sol non certifié), zéro moteur, récompense ou conséquence. JSON archivés.
- [ ] Aucun résultat moteur, visuel ou physique validé. P0h est terminé et fusionné, avec les politiques ONNX vérifiées ; les perceptions visuelles et sonores ne sont pas encore développées.

[Rapport P2b](p2b-passive-mujoco-cycles-2026-10-25.md).

## P0g — Contacts compilés statiques (PR #18, testé MuJoCo)

- [x] Trois variantes constructeur en scènes temporaires, même STAND, **mj_forward seulement**, 0 commande moteur. [214 tests](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208638362) et [MuJoCo OEM #40208635206 réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208635206).
- [x] Geoms compilées Walk/Groundcontact/AllCollisions **76/82/141**, masques-sol éligibles **2/10/69**. Même pose, masse simulée 0,73724318 kg, mêmes friction/solref/solimp des pieds et du sol ; 0 contact candidat statique sans relaxation dynamique, ce qui ne mesure PAS les contacts en marche.
- [ ] Cause inconnue, pas de correction motrice. **P0h terminé** : audit de provenance et sélection alpha_walking/velstand ; une comparaison motrice contrôlée exigerait un nouveau lot. **P2b** : cycles cognitifs passifs MuJoCo indépendants de la locomotion.

[Rapport P0g](mujoco-p0g-compiled-contacts-2026-10-25.md). P1a toujours bloqué, aucun test sur robot physique.

## P2a — Cycles fictifs multiples et mémoire persistante (PR #17)

- [x] **Boucle logique hors connexion, mock uniquement :** perception sourcée et horodatée → mémoire SQLite → motivation et intention → aucune exécution motrice → résultat fictif explicite avec observation fraîche → préférence graduelle → cycle suivant. Les intentions de marche/jeu sont marquées `blocked_motion`, jamais exécutées ni récompensées.
- [x] **Vérification CI :** [217 tests réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40207932413). Deux sessions avec une même base de données montrent **4 puis 8 lignes de journal**, une préférence fictive `0,06` réutilisée et **zéro commande moteur**. Tests de redémarrage, doublons, source LLM refusée, horodatages, perte de sécurité et retour sans preuve.
- [x] **P2b, déjà livré et validé :** plusieurs cycles passifs reliés à `robotd`/`tofd` réels **du simulateur**, sans activer `robot.move` ; garder les cas limites de fraîcheur, déconnexion et reprise SQLite. Pas de preuve de mobilité ni de validation embarquée.

[Rapport P2a](p2a-mock-cycles-2026-10-25.md).

## P0f — Contrats ONNX et variantes de géométrie (PR #16, testé en MuJoCo)

- [x] **Audit contrôlé :** lecture seule des sous-modules constructeur et RL épinglés, vérification des contrats du code d'observation (61), des actions (14, `mouth` exclue), de la pose HOME et du filtrage/échelle de `robotd`, de la provenance locale des fichiers `alpha_walking`/`alpha_stand` et de leurs SHA-256.
- [x] **Vérification ONNX réelle, mais indépendante :** [207 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419766) et [MuJoCo headless #40200419709 réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419709). Les deux fichiers chargés de **793 705 octets** sont des réseaux non récurrents `obs [1,61] → actions [1,14]`. Pose HOME des 14 articulations : **0 rad de différence** ; variation de sortie brute synthétique du réseau de marche **0,147 L2** entre 0 et 0,12 m/s.
- [x] **Différences de sources identifiées :** tâche vitesse `robot_walk.xml` (85 géométries, **2** géométries explicitement classées `collision`), tâche VelStand `robot_allcollisions.xml` (150, **69**), runtime headless `robot_groundcontact.xml` (91, **10**). **Ce ne sont pas les contacts actifs et la variante exacte utilisée pour les poids ONNX v8 reste à établir.** Échelles de contrôle 1,0 dans la configuration RL de vitesse et 0,9 par défaut dans `robotd` : comparaison directe insuffisante sans version du réseau et filtres.
- [ ] **Cause et boucle motrice non vérifiées :** aucune observation/action brute de `robotd` capturée au même tick, aucune nouvelle mesure J2e ; P1a reste bloqué. P0g comparera les paramètres de contact compilés des trois variantes en MuJoCo **séparé**, passif et épinglé, et cherchera la provenance du checkpoint ONNX. P2 peut avancer sans marche.

Voir [rapport P0f](mujoco-p0f-policy-contract-2026-10-25.md). Les appels ONNX CPU sont **synthétiques** et ne représentent pas l'inférence réelle en boucle fermée.

## P0e — Audit du gain et du modèle de force actif (PR #15, testé MuJoCo)

- [x] **Code et sûreté :** sonde facultative dans l'unique processus OEM headless déjà vérifié ; capture au pas physique avant intégration (`ctrl`, `qpos`, `qvel`, gains, biais, `forcerange`, damping, frottement), `mj_step` constructeur appelé **une seule fois** et forces originales récupérées après. P0d reste utilisable sans le mode P0e ; erreurs diagnostiques n'interrompent pas la physique et aucune commande n'est ajoutée.
- [x] **Tests et simulation :** [199 tests Python + scénario OEM réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617). 79 trames `stand`, 127 trames `walk`, gains **0,44** et **0,55 N·m/rad** conformes au modèle OEM (quatre trames de transition 0,44 dans la fenêtre marche), effort prédit égal au solveur sur **2 884 échantillons**, **0 saturation** à la limite ±0,96 N·m. Double appui chargé **127/127** ; J2e **2,295 mm** de translation finale, stop et mémoire `no_progress_observed`.
- [ ] **Marche toujours bloquée :** P0e n'explique pas la faible excursion des hanches, la persistance du double appui ou l'absence de propulsion. P0f devra analyser sans réglage les entrées/sorties ONNX, mises à l'échelle et le simulateur d'entraînement à révision OEM connue ; pas de tentative P1a sans cause vérifiée.

Voir le [rapport P0e](mujoco-p0e-actuator-gains-2026-10-25.md). La capture Python pré-pas ajoute de la charge CPU non mesurée globalement, et aucune force/cadence n'est validée sur robot réel.

## P0d — Mesures native du solveur et consignes (PR #14, testée sur MuJoCo)

- [x] **Capture :** `mujoco.mj_step` constructeur conservé, copie facultative de contacts, forces normales/tangentielles, cibles articulaires `data.ctrl` et angles dans le même processus. Fichiers OEM intacts, aucun nouvel ordre moteur ; capture un pas sur quatre à 5 ms, journal JSONL via file asynchrone.
- [x] **Essai officiel :** [CI MuJoCo #40190232870](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190232870) réussi ; 888 relevés validés à l'analyse, `stand` 79, `walk` 126 à ~50 Hz. **Les deux pieds chargés sur 126/126** relevés pendant marche, forces normales moyennes gauche ~3,21 N et droite ~4,03 N, roulis hanche gauche consigne 0,157 rad / angle 0,011 rad, droite 0,167 rad / angle 0,006 rad. J2e : **2,222 mm**, arrêt confirmé.
- [x] **Robustesse logicielle :** [190 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697176), vérification provenance, pertes de trames, sauvegarde asynchrone et erreurs de sonde sans arrêt du solveur OEM.
- [x] **Répétition du diagnostic durci :** [MuJoCo #40190697090](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697090) réussi avec **190 tests**, 77 trames `stand`, **132 trames de marche, deux pieds chargés 132/132**, 1,597 mm final, `robot.stop` confirmé. Gains estimés sur les hanches/genoux ~0,52–0,55 N·m/rad, cohérents avec le `kp=0.55` du MJCF épinglé ; aucun écrêtage à ±0,96 N·m observé pour ces articulations. **Ce n'est pas une preuve que le gain est fautif.**
- [ ] **Causalité et marche :** contacts et cibles observés par une sonde de diagnostic, mais **pas** de cause démontrée ni de cycle de pas stable. P0e devra confronter gains, limites et écart de suivi des consignes de façon mesurée ; P1a reste bloquée.

Le [rapport P0d](mujoco-p0d-live-solver-2026-10-25.md) explique l'écart de temps entre contact, consigne et position, le surcoût d'instrumentation et les mesures non physiques. Le protocole OEM `body_server.op=read` **n'a pas été modifié** et ne transmet toujours pas contacts/consignes ; P0d lit `MjData` localement en mode diagnostic.

## P0c — Replay hors ligne des contacts géométriques (PR #13, testé en MuJoCo)

- [x] **Code et tests :** lecture du quaternion OEM, reconstruction de pose avec `mj_forward` dans un modèle indépendant, appariement géométrique semelles/sol, refus des données invalides, aucune commande moteur ni progression de la physique ; [179 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954).
- [x] **Simulation épinglée exécutée :** [CI MuJoCo #40188553954](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954) : les deux semelles montrent un léger chevauchement du sol à **16/16** instants de `stand` et **24/24** instants de l'essai de marche, distance signée entre environ **−0,534 et −0,289 mm** pendant `walk`. L'essai J2e de cette exécution s'arrête avec **1,997 mm** de déplacement net, `stop` confirmé, `no_progress_observed`.
- [ ] **Cause toujours inconnue :** les contacts dynamiques du solveur, forces/impulsions et cibles articulaires originales ne sont pas exposés par le protocole constructeur `op=read`. Le replay statique ne peut pas établir une alternance des appuis, une traction, une absence de décollage entre échantillons ou une démarche. P1a reste bloquée.

Voir le [rapport P0c](mujoco-p0c-contact-replay-2026-10-25.md) ; prochaine étude P0d : une instrumentation de diagnostic des contacts **au même tick** dans un environnement de simulation isolé, sans modifier la sécurité de `robotd` ni prétendre valider le robot réel.

## P0b — Repos comparé à un essai `walk` (PR #12, testé en MuJoCo)

- [x] **Code et tests :** la [PR #12](https://github.com/Jean-Philippe56520/Microduck/pull/12) ajoute `sim_walk_compare.py`, un crochet de mesure passive limité à la section J2e où `robot.stop` est garanti, et des tests d'arrêt sur perte de télémétrie. [167 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514224).
- [x] **Essai OEM émulé :** [workflow MuJoCo #40187514292](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514292) réussi avec `stand` 16/16, `walk` 23/24, vitesse appliquée déclarée ~0,12 m/s, 24 commandes, `robot.stop` confirmé, déplacement final **1,338 mm** et `no_progress_observed`.
- [x] **Excursions articulaires mesurées :** genou gauche 0,0223 rad et genou droit 0,0081 rad en fenêtre `walk`, distinctes des références repos ; ne pas déduire un cycle de pas de ces seules variations.
- [ ] **Blocage non levé :** les contacts des pieds et cibles articulaires ne sont pas fournis par le serveur OEM. Origine du manque de progression **non établie** ; P1a reste bloquée. Priorité : méthode non intrusive pour obtenir contacts/forces dans la même simulation, puis interprétation causale fondée sur les données.

Voir le [rapport de mesures P0b](mujoco-p0b-stand-walk-comparison-2026-10-25.md). Les mouvements et les métriques MuJoCo ne constituent pas une validation physique.

## P0a — Diagnostic articulations et politiques (testé en MuJoCo, 25 octobre 2026)

- [x] **Code proposé par PR #11 :** [PR #11](https://github.com/Jean-Philippe56520/Microduck/pull/11), nouvelle sonde passive `sim_joint_trace.py` et tests de formats, provenance, temps et cohérence des mesures.
- [x] **151 tests Python réussis :** [GitHub Actions #40178580633](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580633).
- [x] **Collecte MuJoCo effective :** [smoke test #40178580637](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580637) réussi ; `joint-trace.json` archivé avec 8 échantillons (5 Hz, durée simulée 1,4 s), politique `stand` 8/8, vitesse demandée/appliquée 0 m/s, variation nette du tronc **0,991 mm** et trajet XY cumulé **1,044 mm**. C'est un relevé passif au repos, pas un essai de locomotion.
- [ ] **Contacts des pieds :** indisponibles dans `op=read` du protocole OEM épinglé ; idem pour les cibles articulaires. Les valeurs restent explicitement inconnues ; examiner la possibilité d'un moyen de diagnostic constructeur compatible pour P0b, sans modifier ses mécanismes de sécurité.

Le capteur de courant est une approximation fournie par le serveur MuJoCo (`abs(actuator_force) * 100`) et ne doit pas être interprété comme un courant électrique réel. L'activation de `policy=walk`, la variation des articulations et l'absence de chute ne suffisent pas à valider une démarche. **Aucune nouvelle commande motrice ne fait partie de P0a** et le robot physique reste indisponible.

## Vision et périmètre

Créer un Microduck discret, curieux, explorateur et social : percevoir, retrouver ses souvenirs, choisir une intention sûre, agir, observer le résultat et adapter progressivement ses préférences. Il peut décider de ne rien faire. Le dialogue est secondaire.

Le robot doit conserver les fonctions essentielles sans PC ni Internet. `robotd` reste seul maître des moteurs et de la sécurité. Le modèle Qwen, facultatif, propose des hypothèses ; il ne commande jamais les moteurs et ne certifie jamais une observation. Priorité au Microduck, sans travail pour d'autres matériels à ce stade.

## État du socle et écarts restants

- [x] Dépôt de développement, tests Python et GitHub Actions présents.
- [x] Sources officielles `upstream/microduck` et `upstream/microduck_rl` liées par sous-modules Git sur des révisions précises.
- [x] Prototype Python : `AutonomyBrain`, motivations, intentions, garde-fous initiaux, mémoire SQLite d'objets/expériences et rétroaction sur les préférences.
- [x] Les hypothèses du LLM restent distinguées des étiquettes issues d'observations déclarées par les capteurs.
- [x] Treize cas de test automatisés dans `tests/test_autonomy.py` ; les exécutions CI consultées avant ce plan étaient réussies.
- [x] Audit documentaire du matériel et script `scripts/resource-audit.sh` préparés.
- [x] Connexion **en lecture seule** du compagnon aux vrais démons `robotd` et `tofd` exécutés en simulation MuJoCo (essai CI 2026-10-25).
- [x] Chaîne **bornée** perception → décision → action via `robotd` → résultat → mémoire démontrée dans MuJoCo (un essai volontaire, locomotion non validée).
- [ ] Boucle autonome **multi-cycles** et perception visuelle depuis `mediad` ; connexion des véritables pilotes et capteurs physiques non réalisée.
- [ ] Inférence visuelle chien/chat/personne, reconnaissance individuelle, intégration Qwen.
- [ ] Mesures et validation sur un Microduck physique.

Les scènes du prototype sont **fictives**. Aucun mouvement réel, capteur réel, taux de reconnaissance ou budget de ressources matériel n'a été validé. Le robot physique n'est pas encore disponible.

## Avancement du jalon J1 — 2026-10-25

- [x] `PerceptionEvent` et `PerceptionSnapshot` v1 ajoutés : horodatage monotone, durée de validité, provenance, confiance, identifiant d'objet suivi et distinction des environnements `mock`, `simulator` et `robot`.
- [x] Le moteur accepte `choose_from_snapshot` ; les données de sécurité manquantes, périmées, contradictoires, de faible confiance ou attribuées à une source non autorisée conduisent à `halt` (avec exception du repos sur batterie basse vérifiée).
- [x] La mémoire SQLite conserve la provenance `mock` / `simulator` / `sensor` d'une étiquette, et les hypothèses LLM restent distinctes.
- [x] 40 tests Python passés localement et sur GitHub Actions sur la branche de développement (13 tests historiques + 27 tests de perception).
- [x] Associer la provenance aux sockets de `robotd`/`tofd` et à la scène épinglée **dans MuJoCo**, avec validation du processus du simulateur.
- [ ] Établir l'authenticité de mesures de **capteurs physiques** via les vrais pilotes ; le seul texte `source="sensor"` n'est pas une preuve matérielle.
- [x] Lancer `duck-sim` sur Linux CI, relever sa santé et sa vitesse, puis connecter les observations MuJoCo en lecture seule ([exécution réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078)).
- [ ] Évaluer les garde-fous avec les capteurs, les pilotes et le matériel physique.

**Frontière de confiance :** la méthode historique `choose(Scene(...))` reste un chemin de démonstration synthétique ; toute intégration devra passer par des mesures réellement produites et vérifiées par un adaptateur. Ce module ne contrôle aucun moteur et `robotd` conserve seul l'autorité de sécurité.

## Phase 1 — Consolider le cerveau sur PC (V0 ; en cours)

**But :** disposer d'un moteur local déterministe, explicable, testable, séparé des capteurs et des commandes.

Travaux :
1. Définir un contrat versionné `PerceptionEvent` / `PerceptionSnapshot` : horodatage, provenance, confiance, identifiant suivi, durée de validité, incertitude et état des capteurs. Adapter le `Scene` existant sans casser les tests.
2. Traiter explicitement les données absentes, périmées ou contradictoires : ne pas transformer « inconnu » en « sol sûr ».
3. Renforcer la boucle motivations → souvenirs → choix → résultat ; éviter les actions répétitives et permettre `idle`/`rest` sans oscillations arbitraires.
4. Étendre progressivement SQLite : épisodes, objets/propriétés, repères incertains et résultats comportementaux. Séparer provenance et confiance ; conserver la possibilité de corriger une hypothèse.
5. Ajouter des tests de reprise, de persistance, de capteur perdu, de temporisation et d'échec. Utiliser des observations fictives uniquement.

**Critère de sortie :** tous les tests sont verts ; pour chaque entrée incertaine ou dangereuse, aucune intention de déplacement non sûre ; apprentissage reproductible sur plusieurs épisodes ; aucun PC ou LLM requis pour choisir une intention locale.

## Avancement J2a — client IPC en lecture seule (25 octobre 2026)

- [x] `microduck_companion/sim_ipc.py` : client Unix JSON-RPC 2.0 NDJSON avec liste blanche stricte (`robot.health`, `robot.subscribe`, `tof.stream`), délais, validation des réponses et trames ToF 8×8 brutes.
- [x] `microduck_companion/sim_probe.py` : outil de diagnostic ciblant les sockets locaux créés par `duck-sim` ; aucune commande moteur autorisée.
- [x] 25 nouveaux tests sur sockets Unix fictifs (22 IPC + 3 sonde), soit **65 tests logiciels** dans le projet. Validation CI à contrôler lors de la fusion.
- [x] Démarrage du vrai `duck-sim` officiel sur **Ubuntu CI** avec Rust/Cargo, Python 3.12 et les politiques ONNX épinglées ; reproductibilité sur poste Linux/WSL2 personnel non encore vérifiée.
- [x] Lire les trames des vrais démons simulés, mesurer l'état du contrôleur (~50 Hz), le ToF 8×8 et le facteur temps réel (1,00×) sur Ubuntu CI.
- [x] Convertir les lectures vérifiées en `PerceptionSnapshot` avec gestion d'incertitude ; la **scène plane épinglée** peut produire une attestation limitée à la simulation, jamais le ToF seul.
- [x] Tester **une intention bornée** `robot.move` puis `robot.stop` via `robotd`, sur MuJoCo seulement ; l'adaptateur pour les intentions générales et le robot physique reste à développer.

**Historique J2a :** les premiers tests utilisaient uniquement de faux sockets. **Mise à jour :** l'exécution CI du 25 octobre a depuis confirmé `robot.health`, `robot.state` et `tof.frame` sur les démons officiels sous MuJoCo. Toujours aucune mesure sur robot physique ni commande motrice issue du compagnon.

## Avancement J2b — pont télémétrie → cerveau (25 octobre 2026)

- [x] `microduck_companion/sim_bridge.py` : acquisition des télémétries officielles en lecture seule, contrôle de fraîcheur, santé, cadence moteur, chute et cohérence temporelle des sources ; `PerceptionSnapshot` conservateur (aucun sol ou espace déclaré sûr par le ToF).
- [x] `microduck_companion/sim_observer.py` : diagnostiquer une décision du cerveau sans envoyer de commande motrice.
- [x] `scripts/sim-smoke.sh` : contrôle des prérequis, lancement prévu de `duck-sim` sans interface graphique ni caméra, probes, puis arrêt propre ; réservé au clone Linux/WSL2.
- [x] **81 tests logiciels** exécutés en local : 65 tests existants + 16 tests de pont IPC, données absentes et réponses sûres, dont de faux sockets Unix.
- [x] Exécuter `scripts/sim-smoke.sh run` dans un environnement Linux GitHub Actions avec Rust/Cargo, Python 3.12, `uv`, sous-modules épinglés et politiques ONNX officielles.
- [x] Vérifier `robot.health`, `tof.frame`, la cadence effective de `robotd`, la vitesse MuJoCo et les décisions observées sur l'exécuteur CI.
- [x] Vérifier une petite zone plane **uniquement en MuJoCo** par provenance du modèle et vérité terrain ; ne jamais inférer la sécurité des escaliers à partir du ToF 8×8.

**Statut du jalon J2b :** lecture seule validée sur MuJoCo ; aucune validation sur robot. Les étapes ultérieures J2c/J2d ont ensuite attesté la **scène plane virtuelle** et la commande bornée. Le ToF 8×8 ne certifie toujours pas la sécurité du sol réel.

## Première validation MuJoCo officielle — 25 octobre 2026

Le jalon de **lecture seule** est désormais **simulé et testé** sur Ubuntu 24.04 via [GitHub Actions #40145369078](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078), utilisant les sous-modules épinglés et les politiques ONNX officielles :

| Contrôle | Observation réelle pendant cette exécution |
| --- | --- |
| Lancement et arrêt `duck-sim` | Réussis ; un Microduck, sans caméra, mode headless |
| `robotd` | `healthy`, ~50 Hz (exemple de santé à 50,1 / 50,0 Hz), 0 échéance manquée dans l'échantillon |
| Temps réel MuJoCo | `duck-sim realtime` : **1,00×** |
| `tof.stream` | Source `sim`, trames 150 et 151, **64 cellules** chacune |
| `sim_probe` | Lecture `robot.health`, `robot.state`, `tof.frame` validée ; aucune commande motrice |
| `sim_observer` | `environment=simulator`, `intention=halt`, `errors=[]`, `floor_certified=false` |
| Tests Python | **81/81 réussis** |

L'observation de batterie (~50 % dans le flux) et les données ToF sont **simulées**. La santé `robotd` et la cadence concernent uniquement l'exécuteur Linux de ce test. Ni l'évitement des escaliers, ni une exploration de maison, ni les consommations, températures et latences du robot physique ne sont validés.

**Prochain verrou à traiter :** vraie preuve de `safe_area` / `floor_clear` provenant d'un scénario de test MuJoCo borné, puis autorisation conditionnelle de courtes intentions via `robotd`, avec arrêt sûr.

## Phase 2 — Démarrer et observer le simulateur officiel (V1a ; vérifiée sur Ubuntu CI)

Plan opérationnel avec critères de sortie et étapes de validation : [J1b → J2 — MuJoCo](mujoco-integration-plan.md).

**But :** obtenir une base MuJoCo reproductible avant de connecter le cerveau.

Travaux :
1. Sur Linux ou WSL2, initialiser les deux sous-modules épinglés, préparer l'environnement Python de `upstream/microduck_rl` et les dépendances Rust/ONNX requises.
2. Utiliser `upstream/microduck/scripts/duck-sim` en mode `up` (sans conteneur) avec `DUCK_SIM_RL` pointant sur notre sous-module RL ; commencer **sans caméra** et avec un seul robot.
3. Confirmer le démarrage de `robotd` et `tofd`, `duck-sim status`, `duck-sim ctl health`, `duck-sim realtime` et l'arrêt propre.
4. Documenter les commandes, versions, téléchargements initiaux des politiques ONNX, erreurs de dépendances et mesures de référence. N'activer la caméra simulée qu'après cette validation.

Exemple de commandes depuis la racine du projet (procédure officielle ; le script `scripts/sim-smoke.sh` a été **effectivement exécuté sur CI** avec ces opérations de démarrage, santé, temps réel et arrêt) :

```sh
git submodule update --init --recursive
cd upstream/microduck_rl
uv sync
cd ../..
export DUCK_SIM_RL="$PWD/upstream/microduck_rl"
upstream/microduck/scripts/duck-sim
upstream/microduck/scripts/duck-sim status
upstream/microduck/scripts/duck-sim ctl health
upstream/microduck/scripts/duck-sim realtime
upstream/microduck/scripts/duck-sim down
```

**Critère de sortie :** démarrage et arrêt reproductibles, santé du robot virtuel contrôlée, facteur de temps réel mesuré et journaux diagnostiques disponibles. Le maintien de la boucle officielle à 50 Hz reste vérifié par les outils et journaux du constructeur, pas présumé.

## Avancement J2c — zone simulée à preuve bornée (25 octobre 2026)

- [x] `sim_flat_zone.py` : contrôle strict de la révision et de l'intégrité du simulateur officiel, de l'identité du processus `body_server`, de sa scène par défaut sans caméra et de sa pose dynamique. **Sans ces attestations, aucune preuve de sol sûr.**
- [x] `sim_zone_probe.py` : déduit `safe_area`, `floor_clear` et une distance à la **limite virtuelle** de la zone ; n'utilise jamais le ToF 8×8 pour inventer un sol sûr, et n'envoie aucun mouvement.
- [x] 22 nouveaux tests logiciels vérifiant limites, pose, trames invalides, sources périmées, scène non épinglée et processus inconnu ; 103 tests Python réussis sur GitHub Actions.
- [x] Sonde vérifiée en **véritable MuJoCo** : [CI #40173323079](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173323079), scène épinglée validée, réserve 0,7134 m, robot debout (tronc z=0,1155 m), décision `explore` sans commande motrice.
- [x] Autoriser **une intention courte et bornée** en simulation (J2d/J2e), avec vérification de zone, arrêt explicite et deadman constructeur préservé.
**Contrainte non négociable :** aucune preuve de sécurité MuJoCo n'est transposable à un Microduck physique ; des capteurs réels et des essais supervisés restent nécessaires.

**Statut J2c (historique) :** contrôles de zone codés et validés dans MuJoCo, initialement en lecture seule. La première commande bornée a **ensuite** été validée en J2d. Aucune transposition sur robot réel.

## J2d — Une seule intention robot.move bornée (25 octobre 2026)

- [x] `sim_motion.py` : vitesse avant fixée à **0,05 m/s**, quatre notifications sur ~0,4 s, sans rotation ; lecture de la vraie pose MuJoCo et de la santé `robotd` avant chaque commande.
- [x] `robot.stop` (appel discret) vérifié en fin d'essai, y compris sur pertes de capteur pendant une séquence de mouvement ; deadman constructeur conservé.
- [x] Double consentement explicite `--enable-once` + `MICRODUCK_SIM_MOTION_TEST=YES` ; le workflow normal sur `main` ne lance pas de mouvement.
- [x] 12 tests de contrôle de mouvement avec faux services Unix, **115 tests logiciels** réussis.
- [x] Impulsion exécutée sur le vrai `robotd` simulé : [CI #40173809463](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173809463), 4 `robot.move`, `robot.stop` confirmé, contrôleur sain ~50 Hz, MuJoCo 1,00×. Déplacement observé du tronc **0,185 mm** (trop faible pour valider la marche).
- [ ] Après cet essai, développer une vraie boucle continue perception → décision → action → conséquence → mémoire, avec limites réévaluées, sans Qwen.

**Statut : code + tests vérifiés ; chemin de commande et arrêt testés en vrai MuJoCo.** Une intention `explore` a déclenché un essai très bref sans preuve de locomotion effective. Aucun moteur réel ni pilote constructeur modifié.

## J2e — Essais de translation et mémoire des conséquences (mesurés ; locomotion non validée, 25 octobre 2026)

- [x] Revue du constructeur : le seuil par défaut de la politique station debout / marche est `0,05 m/s` ; précédente commande `vx=0,05 m/s` au seuil, seulement 0,185 mm de variation de position du tronc.
- [x] `sim_walk_trial.py` : essai unique `vx=0,12 m/s`, **24 notifications** espacées de 0,1 s au maximum, observation de la dérive au repos, contrôles des zones et santé avant chaque commande, `robot.stop` confirmé.
- [x] `episodic_memory.py` : persistance en SQLite des essais simulés ; résultats fiables distingués des hypothèses, préférences qui évoluent doucement et décisions suivantes adaptées. Aucun effet sur les intentions du vrai robot.
- [x] Tests unitaires avec faux sockets et mémoire persistante, y compris reprise, refus pour zone/connexion, apprentissage négatif et absence d'effet des résultats incertains.
- [x] **Quatre essais MuJoCo vérifiés** : [A : 12 commandes, 1,242 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175133570), [B : 12 commandes, 0,820 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175696383), [C : 24 commandes, 1,399 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176018018), [D : 24 commandes, 2,574 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817). `robot.stop` confirmé ; résultat **`no_progress_observed`**, préférence `explore` 0 → −0,075 **pour chaque base CI éphémère**.
- [ ] **Priorité P0a :** expliquer pourquoi `walk` est exécutée à la vitesse prévue, mais le tronc n'a progressé que de **0,820 à 2,574 mm** ; examiner en **lecture seule** contacts des pieds, commandes d'articulations, pose et dynamique sans changer la sécurité OEM.

**Portée et verdict :** 142 tests Python dont le renforcement de l'accusé `robot.stop`, et boucle mesure → mémoire réellement exécutée sous MuJoCo. **Locomotion non validée** malgré `policy=walk` 23 fois sur 24 et `max_applied_vx≈0,12 m/s`. Le résultat d'acceptation de la translation reste `NOT_MET` (confirmé sur la [CI finale #40176410817](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) : 24 commandes, **2,574 mm** de translation, dérive 0,192 mm, `robot.stop` confirmé ; le workflow technique est **réussi** sans déclarer de marche). Un seul essai par lancement sur la branche expérimentale ; la CI principale et le robot réel ne reçoivent aucune commande.

## Phase 3 — Boucler perception, décision et action dans MuJoCo (V1b)

**But :** démontrer la première autonomie observable, sans modifier le contrôle moteur officiel.

Travaux :
1. Ajouter un adaptateur de perception qui lit les états `robotd` et flux `tofd` simulés puis produit le contrat de la phase 1. Commencer par injecter des **événements fictifs étiquetés comme tels** pour les objets non encore détectés par caméra.
2. Construire un adaptateur d'intentions JSON-RPC vers les seules opérations documentées et autorisées de `robotd`, avec liste blanche, vitesse/zone limitées, durée de validité et arrêt sûr en cas de perte de données.
3. Ne jamais bloquer la boucle motrice sur SQLite, la perception, l'IA ou une requête réseau. `robotd` conserve ses protections.
4. Tester une séquence complète : nouveauté → inspection sûre → résultat observé → souvenir SQLite → comportement ultérieur adapté.
5. Ajouter des scénarios de capteur absent, obstacle, risque de chute, batterie simulée faible, interruption de connexion et reprise. Mesurer collisions, arrêts de sécurité, latences, décisions par minute et répétitions.

**Critère de sortie :** démonstration rejouable de la boucle complète, sans commande directe de servomoteur, tests d'échec concluants et mesures enregistrées. Aucun résultat MuJoCo ne vaut validation sur matériel.

## Phase 4 — Vision et interactions sociales (V2)

**But :** remplacer progressivement les événements fictifs par une perception mesurable.

Travaux :
1. Brancher `mediad --sim-camera` / `media.frame` dans une scène adaptée et mesurer le coût CPU et la cadence de simulation.
2. Développer la détection **multi-classe** d'objet, personne, chien et chat ; distinguer catégorie, suivi temporel et identité individuelle.
3. Préparer sur PC des données locales privées pour Nessquick et Kitty ; évaluer précision, rappel, faux positifs et option « inconnu » avant toute prétention à la reconnaissance individuelle.
4. Pour Malo, privilégier une identification volontaire ou une balise locale plutôt qu'une reconnaissance biométrique continue. Aucune donnée personnelle dans GitHub.
5. Ajouter des interactions discrètes et sûres (regarder, s'arrêter, s'approcher uniquement en zone contrôlée). Les mots-clés audio seront abordés après cette première validation visuelle.

**Critère de sortie :** jeu de validation séparé des données d'entraînement, métriques documentées et repli sûr sur « inconnu ». Les performances des modèles RKNN ne sont pas présumées à partir de MuJoCo.

## Phase 5 — Qwen local facultatif sur PC (V3)

**But :** améliorer l'interprétation d'une situation complexe sans rendre le robot dépendant du PC.

Travaux :
1. Créer un client réseau local isolé, temporisé et limité en fréquence ; aucune commande motrice issue d'une réponse Qwen.
2. Comparer d'abord Qwen multimodal 4B, puis 9B, selon qualité des hypothèses, latence, mémoire et consommation réellement mesurées sur le PC.
3. Enregistrer les propositions comme **hypothèses sourcées**, non comme observations ; n'apprendre d'un résultat que lorsqu'il est vérifié.
4. Tester PC indisponible, réponse tardive, incohérente ou fausse, et réseau coupé.

**Critère de sortie :** le robot simulé continue ses comportements locaux hors connexion ; aucune hallucination de Qwen n'autorise une action physique.

## Phase 6 — Portage embarqué et validation physique (V4 ; après disponibilité du robot)

**But :** faire fonctionner une version légère du cerveau sur Microduck avec les services officiels intacts.

Travaux :
1. Utiliser Rust pour le chemin embarqué critique si les mesures le justifient ; conserver des modules testables et une mémoire locale SQLite privée sous `/var/lib/robot/`.
2. Mesurer avec `scripts/resource-audit.sh` : RAM disponible, RSS des démons, partitions libres, CPU, fréquence et température en trois situations (repos, vision, vision + déplacement).
3. Vérifier la cadence et les délais de `robotd` avant et après intégration. Réduire ou suspendre la vision non essentielle en cas de surcharge, chaleur ou capteur incohérent.
4. Procéder à des essais physiques graduels dans une zone fermée sans risque de chute, sous supervision autour des enfants et animaux. Respecter les interfaces et le système de mise à jour constructeur.

**Critère de sortie :** fonctionnement autonome réel, garde-fous testés, mesures reproductibles et écarts avec la simulation documentés. Aucun budget de RAM, espace disponible, autonomie ou précision n'est considéré acquis avant mesure.

## Indicateurs communs et règle de validation

À chaque jalon, consigner :
- **Statut :** prévu / codé / tests unitaires passés / simulé / validé sur robot.
- **Décision :** motif de l'intention, capteurs exploités, informations inconnues, possibilité de rester inactif.
- **Apprentissage :** souvenirs effectivement réutilisés, préférences modifiées seulement après résultat constaté.
- **Sûreté :** collisions, arrêts préventifs, délais de traitement, absence d'action en cas de perte de capteur.
- **Ressources :** CPU, RAM, température, cadence et disponibilité de `robotd`, mesurées seulement dans l'environnement correspondant.
- **Vision :** précision, rappel, faux positifs, identités inconnues et performances en conditions variées.

Les documents et les tests doivent toujours distinguer un **test logiciel**, une **simulation** et un **essai sur robot physique**. Ne jamais publier de secret, image, voix, souvenir ou identité personnelle.

## Ordre de travail actualisé — voir le plan canonique

**Source de vérité de l'exécution :** [plan directeur F0–F8](plan-action.md), avec P0/P1 locomotion en chantier L séparé et suspendu, dépendances, critères de passage et trois prochaines PR. Les tableaux P0–P8 antérieurs ne représentent plus les priorités actuelles.

- **J1 — cerveau/perception contractuelle :** prototype codé et testé ; la reconnaissance visuelle et les capteurs réels restent à faire.
- **J2a–J2c — services officiels, zone plane :** vérifiés dans MuJoCo ; pas sur matériel.
- **J2d–J2e — commande bornée, arrêt, résultat, mémoire SQLite :** exécutés en simulation ; **aucune progression locomotrice démontrée**.
- **P0a terminé et fusionné :** mesure passive des articulations et de la politique (contacts dynamiques non exposés). **P0b en PR #12 :** comparaison `stand` / `walk` testée, insuffisance de marche confirmée, cause encore inconnue.
- **Ensuite :** compléter l'analyse de contacts et de propulsion avant P1a (translation de 10 mm sur trois essais) ; P2 (autonomie multi-cycles avec mémoire durable) et perception non motrice parallèles si P0 persiste.
- **Plus tard :** vision/social, Qwen PC facultatif, optimisation Rust/ressources, robot physique, puis automatisations optionnelles.

Les essais réussis en simulation ne valident **ni** la navigation domestique **ni** le stockage, la chaleur, la RAM et la batterie du Microduck réel.

## Références

- [README du projet](../README.md)
- [Audit matériel et limites](hardware-feasibility-audit-2026-10-25.md)
- [Simulateur officiel](https://github.com/pollen-robotics/microduck/blob/main/docs/robot/simulation.md)
- [Source simulation RL](https://github.com/pollen-robotics/microduck_rl)
- [Système Yocto officiel](https://github.com/pollen-robotics/microduck_yocto)

## Idées à tester plus tard (hors périmètre des jalons actuels)

Après la simulation d'autonomie et la perception : proposer des automatisations sous contrôle explicite, par exemple détecter l'ouverture d'une porte puis suggérer une alerte. Une détection fiable exigera un capteur adapté ou une validation visuelle mesurée ; tout envoi de message nécessitera un service de messagerie autorisé et une connexion. Aucune automatisation ou auto-modification de code n'est actuellement intégrée.
