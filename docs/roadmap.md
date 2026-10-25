# Feuille de route — Microduck Companion

Mise à jour : 2026-10-25. Document de planification : une case cochée indique du code ou des fichiers déjà présents, pas nécessairement une validation sur robot.

## Vision et périmètre

Créer un Microduck discret, curieux, explorateur et social : percevoir, retrouver ses souvenirs, choisir une intention sûre, agir, observer le résultat et adapter progressivement ses préférences. Il peut décider de ne rien faire. Le dialogue est secondaire.

Le robot doit conserver les fonctions essentielles sans PC ni Internet. `robotd` reste seul maître des moteurs et de la sécurité. Le modèle Qwen, facultatif, propose des hypothèses ; il ne commande jamais les moteurs et ne certifie jamais une observation. Priorité au Microduck, sans travail pour d'autres matériels à ce stade.

## État vérifié au départ

- [x] Dépôt de développement, tests Python et GitHub Actions présents.
- [x] Sources officielles `upstream/microduck` et `upstream/microduck_rl` liées par sous-modules Git sur des révisions précises.
- [x] Prototype Python : `AutonomyBrain`, motivations, intentions, garde-fous initiaux, mémoire SQLite d'objets/expériences et rétroaction sur les préférences.
- [x] Les hypothèses du LLM restent distinguées des étiquettes issues d'observations déclarées par les capteurs.
- [x] Treize cas de test automatisés dans `tests/test_autonomy.py` ; les exécutions CI consultées avant ce plan étaient réussies.
- [x] Audit documentaire du matériel et script `scripts/resource-audit.sh` préparés.
- [x] Connexion **en lecture seule** du compagnon aux vrais démons `robotd` et `tofd` exécutés en simulation MuJoCo (essai CI 2026-10-25).
- [ ] Boucle perception-décision-**action** autorisée en MuJoCo ; connexion de `mediad` et perception visuelle.
- [ ] Inférence visuelle chien/chat/personne, reconnaissance individuelle, intégration Qwen.
- [ ] Mesures et validation sur un Microduck physique.

Les scènes du prototype sont **fictives**. Aucun mouvement réel, capteur réel, taux de reconnaissance ou budget de ressources matériel n'a été validé. Le robot physique n'est pas encore disponible.

## Avancement du jalon J1 — 2026-10-25

- [x] `PerceptionEvent` et `PerceptionSnapshot` v1 ajoutés : horodatage monotone, durée de validité, provenance, confiance, identifiant d'objet suivi et distinction des environnements `mock`, `simulator` et `robot`.
- [x] Le moteur accepte `choose_from_snapshot` ; les données de sécurité manquantes, périmées, contradictoires, de faible confiance ou attribuées à une source non autorisée conduisent à `halt` (avec exception du repos sur batterie basse vérifiée).
- [x] La mémoire SQLite conserve la provenance `mock` / `simulator` / `sensor` d'une étiquette, et les hypothèses LLM restent distinctes.
- [x] 40 tests Python passés localement et sur GitHub Actions sur la branche de développement (13 tests historiques + 27 tests de perception).
- [ ] Lier les événements aux démons du constructeur et **authentifier leur provenance** dans un adaptateur dédié ; le texte `source="sensor"` n'est pas une preuve matérielle.
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
- [ ] Démarrage réel de MuJoCo et du `duck-sim` officiel sur Linux/WSL2 (Rust/Cargo, Python 3.12 et téléchargement de dépendances nécessaires).
- [ ] Vérifier les trames avec les vrais démons simulés, mesurer l'état du contrôleur et le facteur temps réel.
- [ ] Convertir les lectures vérifiées en `PerceptionSnapshot` avec gestion d'incertitude ; les données ToF ne prouvent pas `floor_clear`.
- [ ] Développer et tester ensuite les intentions autorisées via `robotd`.

**Historique J2a :** les premiers tests utilisaient uniquement de faux sockets. **Mise à jour :** l'exécution CI du 25 octobre a depuis confirmé `robot.health`, `robot.state` et `tof.frame` sur les démons officiels sous MuJoCo. Toujours aucune mesure sur robot physique ni commande motrice issue du compagnon.

## Avancement J2b — pont télémétrie → cerveau (25 octobre 2026)

- [x] `microduck_companion/sim_bridge.py` : acquisition des télémétries officielles en lecture seule, contrôle de fraîcheur, santé, cadence moteur, chute et cohérence temporelle des sources ; `PerceptionSnapshot` conservateur (aucun sol ou espace déclaré sûr par le ToF).
- [x] `microduck_companion/sim_observer.py` : diagnostiquer une décision du cerveau sans envoyer de commande motrice.
- [x] `scripts/sim-smoke.sh` : contrôle des prérequis, lancement prévu de `duck-sim` sans interface graphique ni caméra, probes, puis arrêt propre ; réservé au clone Linux/WSL2.
- [x] **81 tests logiciels** exécutés en local : 65 tests existants + 16 tests de pont IPC, données absentes et réponses sûres, dont de faux sockets Unix.
- [x] Exécuter `scripts/sim-smoke.sh run` dans un environnement Linux GitHub Actions avec Rust/Cargo, Python 3.12, `uv`, sous-modules épinglés et politiques ONNX officielles.
- [x] Vérifier `robot.health`, `tof.frame`, la cadence effective de `robotd`, la vitesse MuJoCo et les décisions observées sur l'exécuteur CI.
- [ ] Certifier une zone simulée adaptée sans présumer que le ToF 8×8 voit les escaliers, puis seulement envisager l'adaptateur de commandes autorisées.

**Statut actualisé : codé / tests logiciels verts / observé en MuJoCo officiel (lecture seule) / non validé sur robot.** L'environnement local n'avait pas Rust/Cargo, mais l'exécuteur Linux distant a fourni les prérequis et terminé l'essai avec succès ; le sol reste non certifié.

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

## Phase 2 — Démarrer et observer le simulateur officiel (V1a ; prioritaire)

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
- [ ] Autoriser seulement ensuite une intention courte en simulation, limitée en vitesse/durée et protégée par arrêt/deadman de `robotd`.
- [ ] Aucun portage des preuves MuJoCo vers un Microduck physique : il faudra des sources de sécurité adaptées au matériel réel.

**Statut : contrôles de zone codés, 103 tests logiciels verts et preuve sur MuJoCo officiel validée en lecture seule.** Déplacements encore interdits jusqu'à l'ajout d'un adaptateur motrice spécialement borné ; aucune transposition sur robot réel.

## J2d — Une seule intention robot.move bornée (25 octobre 2026)

- [x] `sim_motion.py` : vitesse avant fixée à **0,05 m/s**, quatre notifications sur ~0,4 s, sans rotation ; lecture de la vraie pose MuJoCo et de la santé `robotd` avant chaque commande.
- [x] `robot.stop` (appel discret) vérifié en fin d'essai, y compris sur pertes de capteur pendant une séquence de mouvement ; deadman constructeur conservé.
- [x] Double consentement explicite `--enable-once` + `MICRODUCK_SIM_MOTION_TEST=YES` ; le workflow normal sur `main` ne lance pas de mouvement.
- [x] 12 tests de contrôle de mouvement avec faux services Unix, **115 tests logiciels** réussis.
- [x] Impulsion exécutée sur le vrai `robotd` simulé : [CI #40173809463](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173809463), 4 `robot.move`, `robot.stop` confirmé, contrôleur sain ~50 Hz, MuJoCo 1,00×. Déplacement observé du tronc **0,185 mm** (trop faible pour valider la marche).
- [ ] Après cet essai, développer une vraie boucle continue perception → décision → action → conséquence → mémoire, avec limites réévaluées, sans Qwen.

**Statut : code + tests vérifiés ; chemin de commande et arrêt testés en vrai MuJoCo.** Une intention `explore` a déclenché un essai très bref sans preuve de locomotion effective. Aucun moteur réel ni pilote constructeur modifié.

## J2e — Translation mesurable et mémoire des conséquences (en cours, 25 octobre 2026)

- [x] Revue du constructeur : le seuil par défaut de la politique station debout / marche est `0,05 m/s` ; précédente commande `vx=0,05 m/s` au seuil, seulement 0,185 mm de variation de position du tronc.
- [x] `sim_walk_trial.py` : essai unique `vx=0,12 m/s`, 12 notifications espacées de 0,1 s au maximum, observation de la dérive au repos, contrôles des zones et santé avant chaque commande, `robot.stop` confirmé.
- [x] `episodic_memory.py` : persistance en SQLite des essais simulés ; résultats fiables distingués des hypothèses, préférences qui évoluent doucement et décisions suivantes adaptées. Aucun effet sur les intentions du vrai robot.
- [x] Tests unitaires avec faux sockets et mémoire persistante, y compris reprise, refus pour zone/connexion, apprentissage négatif et absence d'effet des résultats incertains.
- [ ] Exécuter l'essai avec les démons officiels MuJoCo sur GitHub Actions, consigner déplacement, dérive, contrôle d'arrêt, santé et éventuels échecs.
- [ ] Mesurer ensuite la locomotion effective (contacts au sol et vitesse soutenue), pas seulement la translation du tronc ; aucune validation physique possible pour l'instant.

**Portée :** un seul essai autorisé volontairement sur la branche expérimentale. Le workflow standard et le robot réel ne reçoivent aucune commande.

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

## Premier jalon exécutable et ordre de travail

**Jalon J1 :** stabiliser les contrats de perception et les gardes de sécurité (phase 1), puis démontrer le démarrage sain d'un seul Microduck virtuel par `duck-sim` (phase 2).

**Jalon J2 :** connecter un événement fictif contrôlé et l'état simulé à la boucle de décisions, exécuter une intention admissible par `robotd` et enregistrer l'effet en mémoire (phase 3).

**Jalon J3 :** remplacer les événements fictifs par une perception mesurée, puis ajouter l'analyse Qwen facultative (phases 4 et 5).

**Jalon J4 :** porter et valider sur matériel réel dès qu'il sera disponible (phase 6).

Le contrat de perception versionné et ses tests sont désormais codés. **Prochaine modification fonctionnelle :** mesurer la translation du robot virtuel sous une commande au-dessus du seuil de sélection de marche, puis enregistrer le résultat vérifié dans la mémoire SQLite. Ne pas confondre translation et locomotion stable. Suivre le [plan d'intégration MuJoCo J1b → J2](mujoco-integration-plan.md), qui distingue clairement lecture des capteurs, preuve du sol sûr, commandes autorisées et mémoire des conséquences. Pas de fonctionnalité vocale, de reconnaissance individuelle ni de portage Rust avant la première boucle complète en simulation.

## Références

- [README du projet](../README.md)
- [Audit matériel et limites](hardware-feasibility-audit-2026-10-25.md)
- [Simulateur officiel](https://github.com/pollen-robotics/microduck/blob/main/docs/robot/simulation.md)
- [Source simulation RL](https://github.com/pollen-robotics/microduck_rl)
- [Système Yocto officiel](https://github.com/pollen-robotics/microduck_yocto)

## Idées à tester plus tard (hors périmètre des jalons actuels)

Après la simulation d'autonomie et la perception : proposer des automatisations sous contrôle explicite, par exemple détecter l'ouverture d'une porte puis suggérer une alerte. Une détection fiable exigera un capteur adapté ou une validation visuelle mesurée ; tout envoi de message nécessitera un service de messagerie autorisé et une connexion. Aucune automatisation ou auto-modification de code n'est actuellement intégrée.
