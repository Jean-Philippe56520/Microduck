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

Sur Windows, le prototype Python peut être exécuté normalement. La simulation officielle s'exécute sur Linux ou WSL2 correctement configuré ; son démarrage headless a déjà été validé sur Ubuntu dans GitHub Actions.

## Architecture cible

1. **Embarqué (Microduck)** : sécurité, mouvements, motivations, choix d'activités simples et mémoire essentielle.
2. **PC local (facultatif)** : Qwen pour interpréter des images, suggérer des hypothèses et analyser les nouveautés.
3. **GitHub** : conserver le code et les versions ; GitHub n'exécute pas l'IA.

Le module `microduck_companion` est actuellement un **prototype autonome testé avec les services officiels simulés**, y compris une impulsion `robot.move` suivie de `robot.stop`. Il n'est pas un contrôleur moteur ni une solution de navigation autonome validée. Aucune action ne doit être envoyée au robot réel sans un adaptateur validé et ses protections.

## Confidentialité et sécurité

Le dépôt ne doit contenir ni souvenirs personnels, ni enregistrements audio/vidéo, ni clés d'API, ni données privées. Les bases SQLite locales sont ignorées par Git. Le dépôt est actuellement privé. Les données personnelles doivent rester hors du dépôt, même privé.

## Plan de développement

Le **[plan directeur par phases](docs/plan-action.md)** est la **référence unique pour les priorités, critères de sortie et trois prochaines PR**. Il distingue F0–F8 et le chantier indépendant L (locomotion). La [roadmap](docs/roadmap.md) conserve l'historique des six phases initiales et des jalons P0a–P0j ; le [précédent plan P0–P8](docs/plan-action-historique-2026-10-25.md) est archivé sans supprimer les preuves. Le [plan MuJoCo](docs/mujoco-integration-plan.md) décrit les protocoles J1b–J2e ; l'[audit matériel](docs/hardware-feasibility-audit-2026-10-25.md) conserve les limites vérifiées.

**F1 — perceptions passives et mémoire sur données fictives : terminée en logiciel.** Les [PR #24–27](https://github.com/Jean-Philippe56520/Microduck/pull/27) ont mis en place un lecteur de faux événements Unix, la validation des catégories, une SQLite persistante et un scénario de **10 cycles** sur deux processus : **8 observations journalisées**, **2 déconnexions**, **10 décisions de sécurité `halt`**, **aucune commande motrice**. [Rapport F1-D](docs/f1d-integrated-passive-demo-2026-10-25.md). **Aucun capteur constructeur ni détecteur d'animal/personne réel n'est raccordé.**

**F2 — autonomie cognitive immobile : en cours.** F2-A ([PR #28 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/28), [378 tests Python sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40237211717)) propose `observe`, `inspect`, `listen`, `idle` ou `rest` à partir des catégories fictives et de la SQLite, sans les exécuter. **F2-B est fusionnée dans `main` et testée via [PR #29](https://github.com/Jean-Philippe56520/Microduck/pull/29)** : [409 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40239148712), dont **31 nouveaux**. `AutonomyBrain.propose_balanced_passive()` ajoute un arbitrage utilisant les **cinq motivations**, un **cooldown de 3 s par catégorie**, une cadence minimale de **0,5 s**, le choix `idle` et un repos à hystérésis (`energy` fictive ≤0,22 jusqu'à ≥0,34). L'état de rythme est **en RAM**, le journal SQLite et les voies F2-A/`robotd` demeurent séparés ; les métriques comptent des propositions, non des actions réalisées. **Aucun moteur, caméra/microphone réel, Qwen, récompense ou mesure de batterie physique.** [Rapport F2-B](docs/f2b-motivations-cooldowns-2026-10-25.md), [plan directeur](docs/plan-action.md). **F2-C en [PR #30](https://github.com/Jean-Philippe56520/Microduck/pull/30) ([425 tests Python réussis sur branche](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240139625), pas encore fusionnée) :** nouveau `PassiveLearning` sur la SQLite F1-C, classement de nouveautés/répétitions **fictives**, corrections réversibles et petits biais d'attention (`observe` / `listen`), opt-in uniquement. Ce ne sont ni des conséquences d'actions exécutées, ni un entraînement de modèle ; les expériences MuJoCo restent séparées. [Rapport F2-C](docs/f2c-reversible-mock-learning-2026-10-25.md). **Prochaine étape conditionnelle : F2-D**, après validation et fusion de F2-C. La locomotion P0/P1 reste suspendue.

**État vérifié au 25 octobre 2026 :** P0j [fusionné dans `main` (PR #22)](https://github.com/Jean-Philippe56520/Microduck/pull/22) a [recalculé hors ligne les charges de pieds de l'archive P0e](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655) : **79 échantillons repos, 127 marche, 0 appui unipodal échantillonné**, et part moyenne de charge du pied gauche **52,03 % → 44,54 %**. **[269 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946) et [replay P0e réussi en CI P0j](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655)**, zéro commande motrice nouvelle, aucune cause démontrée ni validation physique. [Rapport P0j](docs/mujoco-p0j-load-transfer-2026-10-25.md). P0i [fusionné dans `main` (PR #21)](https://github.com/Jean-Philippe56520/Microduck/pull/21) a réussi sa [comparaison instrumentée MuJoCo](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) avec **1,444 mm alpha contre 1,968 mm VelStand** (2 arrêts confirmés, 48 notifications au total) et [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915). Les deux configurations sont **sous le seuil expérimental de 10 mm**, sans preuve de gait ni cause démontrée, P1a reste bloqué et aucun robot physique testé. P0h **fusionné dans `main`** ([PR #20](https://github.com/Jean-Philippe56520/Microduck/pull/20)) a validé [243 tests Python sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219827102) et un [audit MuJoCo/ONNX officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) : `duck-sim` force la paire alpha alors que `robotd` utilise normalement `velstand`, trois modèles présents et différents, aucune causalité de non-marche prouvée. P2b a été **fusionné dans `main`** ([PR #19](https://github.com/Jean-Philippe56520/Microduck/pull/19)) : **[234 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216649169)** et [MuJoCo officiel validé pour six cycles cognitifs passifs](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) (3 puis 6 entrées SQLite, six intentions `halt`, zéro commande motrice et aucune récompense). P2a a démontré la mémoire fictive persistante ; P0g a comparé les variantes de contacts. La marche reste non validée (dernier essai moteur P0e : **2,295 mm**, arrêt confirmé), P1a bloqué et aucun robot physique testé.

**Cognition sans mouvement (P2a) :** [217 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40207932413) et **deux sessions fictives successives** sur une même SQLite. Journal de 8 cycles, préférence fictive persistée, tout mouvement non exécuté. Cela ne résout pas le blocage locomoteur P1a.

**Historique des jalons ci-dessous :** les mentions « prochaine étude » de ces rapports décrivent les décisions de leur époque et **ne remplacent pas la priorité courante du plan directeur (F2-C en PR #30 puis F2-D)**.

### P0j — Relecture hors ligne des forces d'appui P0e (PR #22)

Sans nouveau mouvement, le module `sim_p0j_load_transfer.py` vérifie les SHA-256 exacts des anciens diagnostics du solveur MuJoCo P0e et calcule le transfert de charge gauche/droite. La [CI P0j](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655) a réussi : **269 tests Python**, replay du traceur original à 50 Hz, **127/127 relevés de marche avec deux pieds en charge**, 0 relevé sur un seul pied, part de charge gauche passant de **52,03 % au repos** à **44,54 % en marche**. Le changement de charge n'est ni un changement d'appui unipodal, ni une preuve de traction ou de marche. [Rapport détaillé](docs/mujoco-p0j-load-transfer-2026-10-25.md) ; **cause inconnue et P1a bloqué**. Les [269 tests passent aussi sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946).

### P0i — Essai comparatif alpha / VelStand en MuJoCo (PR #21)

La [PR #21](https://github.com/Jean-Philippe56520/Microduck/pull/21), fusionnée, teste les politiques v8 du constructeur, à **0,12 m/s, 24 notifications par essai**, sur deux démarrages indépendants et deux SQLite séparées ; `robotd` seul pilote les moteurs. La [CI MuJoCo officielle](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) a vérifié les configurations réellement chargées, les deux arrêts, **1,444 mm XY pour alpha** et **1,968 mm pour VelStand**, donc **aucune translation de 10 mm**. Le premier lancement a refusé le bras B, car il inspectait le gabarit `robotd.toml` plutôt que le paramètre actif `robotd-duck-a.toml` ; cette différence OEM a été corrigée, sans supprimer les garde-fous. [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915). **Un essai par configuration dans l'exécution finale ne démontre pas une causalité ni une démarche.** Voir [rapport P0i](docs/mujoco-p0i-controlled-policy-pair-2026-10-25.md) ; P1a reste bloqué.

### P0h — Auditer les politiques constructeur sans commande moteur (PR #20)

La [PR #20](https://github.com/Jean-Philippe56520/Microduck/pull/20), fusionnée, identifie une **différence réelle de sélection ONNX** : `robotd` charge normalement `velstand.onnx` sans second modèle debout, tandis que le lancement `duck-sim` force `alpha_walking.onnx` et `alpha_stand.onnx` (seuil vitesse `0,05`). L'audit vérifie les sources épinglées, les déclarations de filiation W&B et les fichiers du bundle v8, puis compare des sorties ONNX CPU **sur données synthétiques**, sans aucune commande de mouvement. [243 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219234669) ; [validation sur les trois ONNX installés et le MuJoCo officiel réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) (bundle v8, 10 entrées de manifeste, trois modèles 61→14, empreintes SHA-256, distances brutes L2 0,2296 et 0,1524, zéro commande motrice). **La cause de l'échec locomoteur n'est pas démontrée.** Voir [rapport P0h](docs/mujoco-p0h-policy-slot-lineage-2026-10-25.md).

### P2b — Cycles passifs sur les services simulés (PR #19, testé MuJoCo)

La [PR #19](https://github.com/Jean-Philippe56520/Microduck/pull/19), désormais fusionnée, ajoute une collecte répétée des télémétries `robotd`/`tofd` du simulateur, des choix cognitifs passifs et un journal SQLite réouvert entre deux sessions. Les données périmées, non progressives ou incohérentes conduisent à `halt`. Les intentions ne deviennent jamais des commandes, récompenses ou résultats de déplacement. **234 tests Python réussis** sur branche ; l'[exécution MuJoCo officielle](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) a réussi **3 + 3 cycles cohérents, avec 3 puis 6 entrées SQLite**, zéro ordre moteur et zéro récompense. Les six décisions ont été `halt` faute de sol certifié. Voir [rapport P2b](docs/p2b-passive-mujoco-cycles-2026-10-25.md). Aucune validation robot physique.

### P0g — Comparaison des géométries compilées (PR #18)

La [PR #18](https://github.com/Jean-Philippe56520/Microduck/pull/18) compare des copies temporaires des trois variantes constructeur à une posture STAND identique, sous MuJoCo épinglé, par **mj_forward seulement**, sans commande moteur ou modification OEM. La [CI officielle a réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208635206) : **76 / 82 / 141 géométries compilées** pour Walk / Groundcontact / AllCollisions et **2 / 10 / 69** éligibles aux masques du sol. Les semelles et le plan ont mêmes friction, solref et solimp dans les trois modèles. Aucun contact candidat à l'état STAND brut sans relaxation dynamique ; ce zéro ne contredit pas les forces sous charge mesurées P0d. **Cause locomotrice inconnue, P1a bloqué.** [Rapport P0g](docs/mujoco-p0g-compiled-contacts-2026-10-25.md). P0h vérifie ensuite les politiques velstand/alpha_walking et leur provenance, sans encore lancer de comparaison motrice. P2b a été fusionné.

### P2a — Cycles autonomes fictifs et mémoire durable (PR #17)

La [PR #17](https://github.com/Jean-Philippe56520/Microduck/pull/17) ajoute **quatre cycles de décision consécutifs par session fictive**, avec journal SQLite de chaque intention, décision ultérieure sensible aux préférences mémorisées, et réouverture effective de la même base lors d'une seconde session. [217 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40207932413) ; démonstration de CI : **4 puis 8 cycles persistés**, préférence fictive pour un jouet **0,06 maintenue après redémarrage**.

Le système **ne commande jamais un moteur** : `explore` et `play_with_object` sont journalisées comme **non exécutées** ; un retour positif ou négatif n'est pris en compte que s'il est **explicitement fictif**, daté, attaché à une inspection `mock` ciblée et corroboré par une seconde observation fictive fraîche. Sans cette confirmation, aucune préférence n'est modifiée. Une perte de preuves de sûreté produit `halt`, même après un précédent résultat positif.

Commande de reproduction purement locale :

```bash
python -m microduck_companion.mock_cycle_demo --database /tmp/p2a-local.sqlite3 --session first
python -m microduck_companion.mock_cycle_demo --database /tmp/p2a-local.sqlite3 --session second
```

Ce jalon **n'est pas** une boucle de navigation autonome validée dans MuJoCo ni sur un robot physique. Prochain P2b : exécuter plusieurs cycles **sans déplacement** avec les observations datées `robotd` et `tofd` de MuJoCo, sans transformer une intention de marche en commande physique. Voir le [rapport P2a](docs/p2a-mock-cycles-2026-10-25.md).

### P0f — Politiques ONNX et variantes de simulation (PR #16)

La [PR #16](https://github.com/Jean-Philippe56520/Microduck/pull/16) ajoute un audit **sans commande motrice** des deux ONNX nommés par `duck-sim` (`alpha_walking` et `alpha_stand`, jeu v8 déclaré) et du contrat de `robotd`. [207 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419766) et [smoke MuJoCo headless](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419709) réussis : chaque ONNX répond à **61 observations / 14 actions float32**, **non récurrent**, et les constantes HOME présentent **0 rad d'écart** entre contrôle et entraînement. Une entrée **synthétique** vx 0 → 0,12 m/s fait varier la sortie brute du modèle de marche de **0,147 L2**.

Les sources comparent des variantes différentes : `robot_walk.xml` (tâche vitesse, 2 balises géométriques de collision explicites), `robot_allcollisions.xml` (tâche VelStand, 69) et `robot_groundcontact.xml` (headless `duck-sim`, 10). **Ce sont des comptes de balises XML, pas des contacts simulés mesurés** et la provenance d'entraînement exacte des poids v8 n'est pas démontrée. Le filtrage des actions et la différence d'échelle 1,0 / 0,9 exigent également un contrôle de version avant conclusion.

Voir le [rapport P0f](docs/mujoco-p0f-policy-contract-2026-10-25.md). **Les entrées 61D et sorties brutes 14D réellement utilisées dans la boucle `robotd` n'ont pas été capturées** ; aucune cause racine de l'absence de marche n'est démontrée, et P1a reste bloqué. Prochaine recherche P0g : confronter les paramètres géométriques et contacts compilés des trois variantes en MuJoCo indépendant et sans modification des sources constructeur ; poursuivre P2 en parallèle.

### P0e — Gains actifs et cohérence de la loi d'actionnement (PR #15)

La [PR #15](https://github.com/Jean-Philippe56520/Microduck/pull/15) ajoute une capture **avant** le pas MuJoCo et un audit **hors ligne** : gain réellement actif, biais, limites de force, consigne, position et vitesse, comparés à l'effort observé après le pas original. La sonde reste facultative, n'écrit dans aucune commande ou paramètre constructeur, et exige l'essai J2e borné avec `robot.stop` confirmé.

Dans le [scénario MuJoCo officiel réussi #40193139617](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617), **199 tests Python réussis** : gains de **0,44 N·m/rad** au repos (79/79 relevés) et **0,55 N·m/rad** sur 123/127 relevés de marche (quatre à 0,44). **2 884 efforts** correspondent exactement à la loi du modèle et aucun écrêtage à ±0,96 N·m n'a été observé. Pourtant, **127/127 trames montrent les deux pieds chargés**, et le déplacement final est seulement **2,295 mm**. Voir le [rapport P0e](docs/mujoco-p0e-actuator-gains-2026-10-25.md) pour la provenance, la cadence, les exceptions et les limites.

**Ce résultat exclut un défaut évident de conversion gain/effort pour les échantillons mesurés, mais ne démontre ni une marche valide ni une cause de l'absence de propulsion.** Prochaine étude P0f : comparer les commandes/références de la politique ONNX et les conditions de simulation/entraînement sans changer arbitrairement les gains ou les garde-fous.

### P0d — Contacts et consignes originaux du solveur (PR #14)

La [PR #14](https://github.com/Jean-Philippe56520/Microduck/pull/14) ajoute un tap optionnel **dans le processus headless officiel MuJoCo épinglé**, sans changer les fichiers constructeur ni émettre de commandes motrices. Il prélève les **contacts/forces réels de MuJoCo** (`MjData.contact`, `mj_contactForce`) et les **consignes de position articulaires** (`data.ctrl`) à environ 50 Hz, avec file non bloquante et contrôle de provenance.

Le [premier essai P0d officiel réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190232870) a montré les **deux pieds sous force normale > 0,1 N sur 126/126 relevés de marche**, des écarts entre les variations de commande et d'angle (roulis hanches gauche/droite particulièrement), ainsi que **2,222 mm** de déplacement net final malgré 23/24 politiques `walk` et `robot.stop` confirmé. Ce sont des **mesures de physique simulée**, pas du robot physique ; le diagnostic peut lui-même ajouter du temps CPU. La [suite logicielle durcie compte 190 tests réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697176).

La [seconde exécution P0d avec sonde durcie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697090) confirme **les deux pieds chargés sur 132/132 trames de marche**, un déplacement de **1,597 mm**, et des écarts consigne/angle pour le roulis des hanches et les genoux. L'effort simulé est cohérent avec un gain positionnel d'environ 0,55 N·m/rad déclaré par le constructeur, mais ce rapprochement **n'explique pas encore pourquoi la démarche ne progresse pas**.

Voir le [rapport de preuve P0d](docs/mujoco-p0d-live-solver-2026-10-25.md). **La cause racine est toujours inconnue, et P1a reste bloqué** ; la prochaine étude doit isoler l'écart de suivi des consignes et son rôle causal, sans retoucher les moteurs au hasard.

### P0c — Contacts géométriques reconstruits hors ligne (PR #13)

La [PR #13](https://github.com/Jean-Philippe56520/Microduck/pull/13) conserve le **quaternion WXYZ OEM** et reconstruit hors ligne, via `mj_forward` sur un `MjData` indépendant, les candidats de contact entre la semelle gauche/droite et le sol. Le [scénario officiel MuJoCo](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954) a réussi : **179 tests Python**, 16 relevés `stand` et 24 relevés pendant **un** essai J2e (23 `walk`), les **deux semelles en léger chevauchement géométrique dans 40/40 trames**, déplacement final **1,997 mm**, `robot.stop` confirmé.

Ces contacts sont **reconstitués** à 10 Hz, pas capturés par le solveur pendant l'essai : aucune force de contact, aucun glissement ni preuve de marche. Le [rapport P0c](docs/mujoco-p0c-contact-replay-2026-10-25.md) distingue précisément la proximité des pieds de l'appui dynamique réel ; les précédents relevés P0b dépourvus de quaternion sont rejetés. Aucun code constructeur ni mécanisme moteur n'a été modifié.

### P0b — Comparaison articulations / repos / marche (PR #12)

La [PR #12](https://github.com/Jean-Philippe56520/Microduck/pull/12) ajoute un comparatif **sur le même simulateur OEM épinglé**, avec **16** relevés passifs `stand` puis **24** relevés pendant **un seul essai J2e** existant à 0,12 m/s, strictement protégé par `robotd`. La commande n'est lancée que sur activation explicite (variable `MICRODUCK_SIM_WALK_COMPARE=YES` **et** option `--enable-once`) et après une baseline stable.

Dans le [workflow MuJoCo réussi #40187514292](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514292), la politique a été `walk` sur 23/24 relevés et les genoux ont bougé (gauche ~1,28°, droit ~0,46° d'excursion). **Le déplacement net final de J2e est seulement 1,338 mm**, surtout sur Y du monde ; `robot.stop` est confirmé et la mémoire constate `no_progress_observed`. La comparaison ne révèle **pas** une cause certaine de l'absence de marche.

Voir le [rapport mesuré P0b](docs/mujoco-p0b-stand-walk-comparison-2026-10-25.md) pour les résultats complets et la distinction des fenêtres d'échantillonnage. Les contacts dynamiques et cibles articulaires ne sont toujours pas exposés dans l'API `op=read` ; ils ne sont ni simulés par notre logiciel ni présentés comme mesurés.

### Diagnostic passif P0a (PR #11)

La [PR #11](https://github.com/Jean-Philippe56520/Microduck/pull/11) ajoute
`microduck_companion/sim_joint_trace.py`. Après démarrage du simulateur officiel
épinglé, cet outil échantillonne **sans commande motrice** `body_server` (uniquement
`hello` puis `read`) et les notifications `robot.state` via `robot.subscribe` :

```sh
python3 -m microduck_companion.sim_joint_trace \
  --state-dir "$HOME/.cache/duck-sim-companion" \
  --rl-root "$PWD/upstream/microduck_rl" --port 17801 \
  --samples 8 --hz 5 --output /tmp/microduck-joint-trace.json
```

Le JSON conserve les positions et vitesses des 15 entrées articulaires,
les courants **simulés non calibrés** (proxy de force, pas des ampères réels),
la pose du tronc, les horodatages, et les politiques/vitesses déclarées par
`robotd`. La provenance du simulateur, l'intégrité de la scène et le processus
`body_server` sont vérifiés. Toute donnée invalide ou périmée fait échouer la sonde.

**Limite documentée :** le protocole officiel épinglé ne fournit ni les
**contacts dynamiques des pieds** ni les **consignes articulaires** ; ces champs
restent `null`. La télémétrie passive ne prouve pas une marche. Le workflow
MuJoCo a effectivement archivé `joint-trace.json` dans le [workflow P0a réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580637) : **8 échantillons à 5 Hz**, 1,4 s simulée, `stand` sur 8/8 échantillons, **0 commande motrice**, **0,991 mm de variation nette du tronc au repos**. Il s'agit d'une référence de dérive au repos, pas d'une preuve de translation en marche. Les essais J2e antérieurs
restent des résultats négatifs inchangés. Aucun pilote réel n'a été interrogé.

### Étapes principales

- [x] Récupérer les deux bases officielles sous forme de sous-modules.
- [x] Tester un premier moteur d'autonomie et une mémoire locale.
- [x] Brancher les observations aux démons officiels du simulateur MuJoCo (lecture seule).
- [x] Vérifier la zone plane épinglée, les intentions bornées et l'arrêt via `robotd` en **simulation**, sans preuve de marche effective.
- [ ] Diagnostiquer la locomotion et démontrer une progression mesurée de plus de 10 mm en simulation (critère proposé, pas atteint).
- [ ] Répéter la boucle perception → action → observation → mémoire sur plusieurs cycles et sessions.
- [ ] Développer une perception mesurée d'objets/animaux et les interactions sociales prudentes.
- [ ] Tester Qwen sur le PC en mode **facultatif**, avec repli autonome hors connexion.
- [ ] Vérifier les ressources, la vitesse et la sécurité sur le matériel réel.

**Le robot physique n'est pas encore disponible.** Les étapes P0–P5 peuvent être étudiées en simulation, avec des jeux de test ou sur le PC, sans présenter ces travaux comme une validation matérielle.

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

Le code constructeur choisit la politique de station debout lorsque la norme de la vitesse demandée est au plus égale à **0,05 m/s**. C'est probablement pour cela que le premier essai, à exactement 0,05 m/s, n'a produit qu'une variation de **0,185 mm** (hypothèse à vérifier). Le nouveau module expérimental `sim_walk_trial.py` demande une seule séquence à **0,12 m/s**, donc au-dessus de ce seuil, sans rotation ni déplacement latéral. Il effectue jusqu'à **24 notifications espacées de 0,1 s** sous réserve d'une zone sûre : soit environ 2,4 s de commandes, avec un budget d'exécution maximal de 4,0 s et `robot.stop` obligatoire.

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

En CI, `DUCK_SIM_WALK_TRIAL=YES` est volontairement activé **seulement** sur `feat/measured-sim-walk-learning-v1`. Sur la branche principale, aucun nouveau mouvement n'est autorisé par défaut. Le CLI renvoie **3 si la translation mesurée reste sous le seuil**, ce qui n'est ni un plantage du protocole, ni une validation de marche. Le script CI classe explicitement ce cas `WALK_TRANSLATION_ACCEPTANCE=NOT_MET` et n'accepte aucun échec de communication ou de `robot.stop`.

### Mesures MuJoCo officielles — résultats négatifs

| Essai | Vitesse demandée | Commandes | Politique / vitesse appliquée | Déplacement du tronc | Dérive avant commande | Résultat |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| [J2e-A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175133570) | 0,12 m/s | 12 | non instrumentée | 1,242 mm | 0,105 mm | pas de progression validée |
| [J2e-B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175696383) | 0,12 m/s | 12 | `walk` 11/12 ; 0,12 m/s appliqué | 0,820 mm | 0,037 mm | pas de progression validée |
| [J2e-C](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176018018) | 0,12 m/s | 24 | `walk` 23/24 ; 0,12 m/s appliqué | 1,399 mm | 0,273 mm | pas de progression validée |
| [J2e-D](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) | 0,12 m/s | 24 | `walk` 23/24 ; 0,12 m/s appliqué | **2,574 mm** | 0,192 mm | pas de progression validée |

Dans les quatre essais, `robot.stop` a été accusé, les mesures ont été obtenues du véritable serveur MuJoCo épinglé et la mémoire a consigné `no_progress_observed`, récompense `-0,5`, variation de préférence d'exploration **0 → −0,075**. Ces bases de CI sont **éphémères** ; la persistance entre essais est testée avec SQLite par les tests automatisés, mais les essais CI ne réutilisent pas la même base. Un échantillon de J2e-C/J2e-D mentionne `deadman` parmi les limitations, tout en rapportant une vitesse appliquée nominale lors d'autres échantillons.

**Conclusion : la chaîne décision → commande → stop → observation → mémoire fonctionne en simulation ; aucune marche effective n'est encore validée.** Le fait que `robotd` choisisse `walk` ne prouve pas la translation. Les prochains essais devront analyser les contacts des pieds, la cinématique et le comportement du modèle OEM, sans modifier ni affaiblir ses mécanismes de sécurité.


**Résultat de l'intégration technique :** [GitHub Actions #40176410817](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) a réussi avec **142 tests Python** et le statut explicite `WALK_TRANSLATION_ACCEPTANCE=NOT_MET`. Il atteste la bonne gestion des essais sans progression et non pas une marche fonctionnelle. `robot.stop` exige dorénavant `accepted=true` dans la réponse JSON-RPC.
