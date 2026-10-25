# F2-A — Intentions cognitives passives, sans exécution ni moteur

**Date : 25 octobre 2026. État : développé et testé logiciellement sur données entièrement fictives.** F2-A ajoute un choix d'attention en lecture seule, **pas** un nouveau contrôleur, une commande moteur ni une véritable perception de caméra/microphone. Les motivations représentent des variables simulées ; la sécurité, la puissance de calcul et la batterie réelles du robot n'ont pas été mesurées.

**Sources :** [plan directeur](plan-action.md), [pipeline F1-D](f1d-integrated-passive-demo-2026-10-25.md), modules `autonomy.py`, `passive_intentions.py`, `passive_memory.py`.

## 1. Architecture conservatrice

La méthode `AutonomyBrain.propose_passive(reading, journal=..., now_monotonic_s=..., now_wall_epoch_s=...)` est exposée **sur le cerveau existant** ; elle délègue à la fonction pure `propose_passive_intention`. Elle réutilise les valeurs `Motivations` en place et le journal `PassiveObservationJournal` de **la même instance d'`ExperienceMemory`**. Aucune nouvelle table SQLite, politique moteur, boucle d'exécution ou moteur de décision séparé.

```
F1-B PassiveRead (catégories mock seulement)
    -> validation d'origine, canal, âge/TTL et objets/sons admissibles
    -> F1-A summarize_passive (identified / unknown / conflict / stale)
    -> F1-C category_count (souvenirs de catégorie ; lecture SQLite uniquement)
    -> AutonomyBrain.propose_passive(...)
    -> PassiveIntent (observe / inspect / listen / idle / rest)
                      executed=false, motor_commands_issued=0
```

**Frontière impérative :** `AutonomyBrain.choose_from_snapshot` reste **inchangé**. Il continue à refuser toute action motrice lorsque la sécurité du sol, les distances ToF et les autres données de sûreté sont absentes : son résultat est alors `halt`. `propose_passive` propose seulement **une intention mentale fictive**, jamais un déplacement, une rotation de caméra, un mouvement de tête, une capture audio, un son joué, un e-mail ou un appel Qwen. Il ne modifie pas `previous_intention`, les motivations, les préférences, les expériences ni les objets connus.

## 2. Règles déterministes de décision F2-A

Les propositions sont ordonnées, avec **l'option de ne rien faire**. Elles sont évaluées uniquement sur de nouvelles catégories de fixtures à source `mock`, canal `mock_fixture_unix`, séquence et horodatage valides. `status != ok`, trame périmée/future, source illégitime, classe faible ou état de motivations invalide entraînent un **`idle` conservateur**.

| Condition vérifiée sur donnée fictive | Proposition | Justification / limite |
| --- | --- | --- |
| Lecture absente, refusée, déconnectée, périmée ou un événement moteur/sûreté forgé | `idle` | Aucune catégorie ancienne recyclée comme observation actuelle |
| Variable **simulée** `Motivations.energy <= 0.20` après lecture valide | `rest` | Ce n'est **pas** la batterie physique ni une charge réelle |
| Objet `unknown` ou `conflict` courant et curiosité >= 0.45 | `inspect` | Attention intellectuelle seulement ; pas de suivi physique ni d'identité |
| Signal sonore catégoriel courant, incertain ou reconnu, sociabilité >= 0.30 | `listen` | Aucune écoute/activation du micro : signaux de test uniquement |
| Catégorie d'objet courante `identified`, **jamais notée auparavant** dans SQLite (14 jours retenus), curiosité >= 0.30 | `observe` | Découverte de **catégorie**, pas d'un individu ni d'un objet unique |
| Catégorie déjà notée ou aucune condition admissible | `idle` | Ne pas forcer l'activité ni répéter une curiosité artificielle |

Les valeurs `curiosity`, `sociability`, `play`, `energy`, `caution` sont **lues**, et doivent rester finies dans [0,1] ; elles ne sont **pas ajustées** en F2-A. L'arbitrage dynamique, les pénalités de répétition, le repos progressif et les changements durables de préférences appartiennent à **F2-B/F2-C**.

Le résultat immuable `PassiveIntent` refuse les noms d'intentions motrices (par ex. `explore`, `look_at_person`), les catégories libres non autorisées, une cible sur `rest`/`idle`, un indicateur `executed=true`, un compteur de moteurs non nul et toute demande d'analyse sur PC. Il ne contient aucun `track_id` ni identité personnelle.

**Nuance :** une ancienne occurrence de `ball` dans le journal permet de dire « la catégorie `ball` a déjà été vue dans une fixture », **pas** « la même balle est revenue ». Après redémarrage, le temps monotone ancien n'est jamais réutilisé comme preuve de fraîcheur.

## 3. Vérifications accessibles

- [x] **27 nouveaux tests F2-A**, [suite complète : 378 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40236949732) avant mise à jour documentaire.
- [x] Premiers événements fictifs `ball` ⇒ proposition `observe`, seconde occurrence ⇒ `idle` ; `unknown` ou conflit ⇒ `inspect` ; événement `knock` ⇒ `listen` ; énergie motivationnelle fictive basse ⇒ `rest` ; absence de source ⇒ `idle`.
- [x] **Vrais sockets Unix entre processus de test** et `FixtureUnixReader` de F1-B, journal SQLite de F1-C, cerveau `AutonomyBrain`. À chaque cycle, le chemin indépendant de sécurité continue à proposer `halt` faute de garanties de zone/sol.
- [x] **Un autre processus Python** relit la même SQLite et reconnaît uniquement la familiarité de `ball` comme catégorie, sans réutiliser l'horloge monotone ni identifier une balle précise.
- [x] Tests de données illégitimes `robot`/`sensor`/`llm_suggestion`, expiration, sources futures, confiance faible, faux `floor_clear`, statut d'échec, séquence non valide, motivations malformées, DB fermée et absence d'effets sur préférences et journaux d'actions.
- [ ] **Non réalisés :** ordres moteur/servos ou audio, microphone/caméra réels, détection d'animaux/objets effective, moteur de motivations avec cooldown, baisse de consommation réelle, reconnaissance individuelle, Qwen, robot physique.

Pour lancer localement les tests sur Linux ou environnement compatible : `python -m unittest discover -s tests -p test_passive_intentions.py -v`. La suite complète du dépôt reste `python -m unittest discover -s tests -v`.

## 4. Décision de sortie et prochaine PR

**F2-A sera terminé au niveau logiciel dès fusion de la PR et CI verte sur `main`.** Ce jalon n'est ni un animal explorateur autonome réel ni un mouvement ou une interaction physique observée.

**Prochain lot F2-B, et lui seul :** arbitrage des cinq motivations, cooldown, repos et diversification **mesurée** des intentions successives sur scénarios reproductibles ; toujours sans moteur, caméra réelle ni dialogue permanent. F2-C pourra ensuite traiter les conséquences et préférences en distinguant leur provenance ; F2-D les durées, pannes et budgets CPU.

Le chantier locomotion P0/P1 reste **suspendu** sans changement.
