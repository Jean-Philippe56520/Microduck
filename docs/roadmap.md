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
- [ ] Connexion du compagnon à MuJoCo, aux vrais flux `robotd`, `tofd` ou `mediad`.
- [ ] Inférence visuelle chien/chat/personne, reconnaissance individuelle, intégration Qwen.
- [ ] Mesures et validation sur un Microduck physique.

Les scènes du prototype sont **fictives**. Aucun mouvement réel, capteur réel, taux de reconnaissance ou budget de ressources matériel n'a été validé. Le robot physique n'est pas encore disponible.

## Avancement du jalon J1 — 2026-10-25

- [x] `PerceptionEvent` et `PerceptionSnapshot` v1 ajoutés : horodatage monotone, durée de validité, provenance, confiance, identifiant d'objet suivi et distinction des environnements `mock`, `simulator` et `robot`.
- [x] Le moteur accepte `choose_from_snapshot` ; les données de sécurité manquantes, périmées, contradictoires, de faible confiance ou attribuées à une source non autorisée conduisent à `halt` (avec exception du repos sur batterie basse vérifiée).
- [x] La mémoire SQLite conserve la provenance `mock` / `simulator` / `sensor` d'une étiquette, et les hypothèses LLM restent distinctes.
- [x] 40 tests Python passés localement et sur GitHub Actions sur la branche de développement (13 tests historiques + 27 tests de perception).
- [ ] Lier les événements aux démons du constructeur et **authentifier leur provenance** dans un adaptateur dédié ; le texte `source="sensor"` n'est pas une preuve matérielle.
- [ ] Lancer `duck-sim` sur Linux/WSL2, relever sa santé et sa vitesse, puis connecter les observations MuJoCo.
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

## Phase 2 — Démarrer et observer le simulateur officiel (V1a ; prioritaire)

**But :** obtenir une base MuJoCo reproductible avant de connecter le cerveau.

Travaux :
1. Sur Linux ou WSL2, initialiser les deux sous-modules épinglés, préparer l'environnement Python de `upstream/microduck_rl` et les dépendances Rust/ONNX requises.
2. Utiliser `upstream/microduck/scripts/duck-sim` en mode `up` (sans conteneur) avec `DUCK_SIM_RL` pointant sur notre sous-module RL ; commencer **sans caméra** et avec un seul robot.
3. Confirmer le démarrage de `robotd` et `tofd`, `duck-sim status`, `duck-sim ctl health`, `duck-sim realtime` et l'arrêt propre.
4. Documenter les commandes, versions, téléchargements initiaux des politiques ONNX, erreurs de dépendances et mesures de référence. N'activer la caméra simulée qu'après cette validation.

Exemple de commandes depuis la racine du projet (à exécuter sur un environnement Linux équipé ; **non exécutées à ce stade**) :

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

La prochaine modification fonctionnelle devrait cibler **un contrat de perception versionné et des tests sur les observations périmées**. Pas de nouvelle fonctionnalité vocale, de reconnaissance individuelle ou de portage Rust avant la première boucle complète en simulation.

## Références

- [README du projet](../README.md)
- [Audit matériel et limites](hardware-feasibility-audit-2026-10-25.md)
- [Simulateur officiel](https://github.com/pollen-robotics/microduck/blob/main/docs/robot/simulation.md)
- [Source simulation RL](https://github.com/pollen-robotics/microduck_rl)
- [Système Yocto officiel](https://github.com/pollen-robotics/microduck_yocto)

## Idées à tester plus tard (hors périmètre des jalons actuels)

Après la simulation d'autonomie et la perception : proposer des automatisations sous contrôle explicite, par exemple détecter l'ouverture d'une porte puis suggérer une alerte. Une détection fiable exigera un capteur adapté ou une validation visuelle mesurée ; tout envoi de message nécessitera un service de messagerie autorisé et une connexion. Aucune automatisation ou auto-modification de code n'est actuellement intégrée.
