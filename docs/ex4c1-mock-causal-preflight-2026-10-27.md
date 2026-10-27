# EX4-C1 — Précontrôle des chaînes d'effets fictives et refus de causalité physique

**27 octobre 2026 — [PR #90](https://github.com/Jean-Philippe56520/Microduck/pull/90), empilée sur [#89 EX4-B](https://github.com/Jean-Philippe56520/Microduck/pull/89) puis [#88 EX4-A](https://github.com/Jean-Philippe56520/Microduck/pull/88).** Préparation partielle de l'[issue #80](https://github.com/Jean-Philippe56520/Microduck/issues/80). Le vrai robot n'est pas disponible. **EX4-C n'est pas « mémoire causale validée » : ce premier lot est C1, uniquement sur fichiers de fixtures et SQLite de test.** Aucun ordre moteur ou consultation d'IA.

## Audit de réutilisation avant changement

- **Constructeur épinglé** : microduck `942e58e3aa6dbb28e7037203fff11866122c7567`, microduck_rl `b02fdea4902c2b93b7d34a83a6f05da4ececb7`. `robotd` reste seul propriétaire de `RobotIo` et des protections, boucle 50 Hz inchangée. `duck-ipc-proto` API **v44** ; `robot.do` reçoit `IntentResult.accepted` lorsque la demande est en file, **pas** lorsque l'action s'achève. `robot.state` (flux décimé) n'a pas d'identifiant d'action ni de preuve de fin.
- **PR OEM [#381](https://github.com/pollen-robotics/microduck/pull/381) et [#414](https://github.com/pollen-robotics/microduck/pull/414)** : ouvertes et non fusionnées à l'audit du 27/10. La proposition de cerveau et `mapd` v45 ne sont pas dans la version épinglée.
- **Réutiliser** `ExecutionEvidenceAudit` (EX4-A, relit les retraits EX1/EX2 sur la SQLite), `review_oem_wire_fixture` (EX4-B, valide uniquement de la trame OEM fictive), les états `MockExperienceLedger`, `MockEffectJournal` et les règles `_assess` d'EX2. **Pas de nouvelle base, table, migration, écrivain M1-B ni duplication d'évaluation des effets EX2.** Le filtre C1 lit les statuts validés par EX4-A.
- **Tiers du registre C3** : QuackNav/microduck-brain, Quacksat, Twin, GC/Smartulf, quack-control et Lab/Studio ne fournissent pas de reçu de fin d'action OEM authentifié. **Veille sans copier** de code, poids, média ni licence tierce.
- **Créer seulement** [`ex4c_mock_causal_preflight.py`](../microduck_companion/ex4c_mock_causal_preflight.py), un validateur déterministe d'une petite chaîne **scriptée**, et [`test_ex4c_mock_causal_preflight.py`](../tests/test_ex4c_mock_causal_preflight.py).

## Contrat et frontières de preuve

`MockCausalPreflight(ExecutionEvidenceAudit(memory))` utilise la connexion de l'**unique `ExperienceMemory` préexistante**. La requête inspectée est une `OemWireProposal` EX4-B explicitement fictive, ses réponses `OemWireFrame` fictives et au plus **trois** `ScriptedStage` (source `ex4c_scripted_stages_only`, numéro ordinal, identifiant RPC de fixture, horodatage de fixture). Le précontrôle ne construit, n'émet ni ne re-joue **aucun** paquet IPC. Il ne reçoit pas d'authentification robot, pas de `signature` ou `verified=true` érigé en preuve.

Il distingue :

| Domaine examiné | Précautions | Résultat permis |
| --- | --- | --- |
| Intention OEM fictive | Réutilisation intégrale du validateur EX4-B (méthode, réponse RPC, ID, modèle API, télémétrie) | `queued_only`, `refused`, `no_reply`… jamais « exécuté » |
| Historique EX1/EX2 | Relecture à chaque évaluation ; refus des sources, annotations incohérentes et retraits | `proposed`, `mock_resolution_only`, `mock_temporal_only`, `mock_confounded`, `mock_unchanged`, `mock_indeterminate`, corrections |
| Événements scénarisés | Identité session+séquence+ID de RPC, numéros consécutifs, temps strictement croissants et bornés par le cycle EX1 | `mock_started_only`, `mock_completed_only`, `mock_interrupted`, **uniquement au titre du scénario** |
| Observation EX2 avant/après | Même fenêtre du scénario ; la logique EX2 déjà réutilisée sépare changements, inconnus, confusions et événements concurrents | **Association temporelle fictive**, non causalité |
| État publié | Chute, limitation, horloge OEM manquante, ordre des frames, sans certifier le processus émetteur | `unsafe_or_limited_wire`, pas un résultat physique |

En particulier, **EX1 propose des intentions passives (observer, inspecter, écouter), alors que le `robot.do` OEM adresse des animations** : l'égalité des clés de scénario dans ce précontrôle ne prouve **aucune équivalence sémantique**, aucune animation autorisée ni effet indépendant. Les éventuelles chaînes cohérentes sont des exercices d'acceptation/refus du futur contrat, pas une démonstration que le mouvement demandé correspond au souvenir EX1. Une relation sémantique ne doit être ajoutée qu'après choix explicite d'une API d'actions et validation constructive.

Les temps `sent_monotonic_s` EX4-B et `at_epoch_s` des scénarios EX1/EX2 **ne sont pas une horloge commune** ; ils sont évalués **séparément**, jamais soustraits ou corrélés entre systèmes. Aucun réseau, capteur physique, pilote, modèle, contrôle moteur, mémoire privée, nouvelle table, score ou récompense ne résulte d'une comparaison.

**Invariants absolus pour chaque `CausalPreflightVerdict`** : `authorized = not_attested`, `executed = not_attested`, `observations_authenticated = false`, `causality_established = false`, `physical_execution_verified = false`, `physical_learning_allowed = false`, `motor_commands_issued = 0`. Aucune variable `reward` dans le verdict. Même un cas « mock completed + changed + same scene » reste `mock_temporal_only`. Les corrections EX1/EX2 dominent toute donnée d'exécution scriptée.

La méthode `review_batch` limite chaque lot à **32** entrées et rejette des clés (session,séquence) ou IDs RPC répétés **dans le lot**. Aucun journal supplémentaire n'est créé et il ne garantit pas l'idempotence entre processus ou redémarrages ; seules les corrections en SQLite existante sont persistantes.

## Vérification et limites

Exécuter depuis la racine de l'arbre de la PR :

    python -m unittest discover -s tests -p 'test_ex4c_mock_causal_preflight.py' -v
    python -m unittest discover -s tests -v
    python -m compileall -q microduck_companion tests

Les fixtures évaluent scénario complet, événement concurrent, absence d'effet, bruit inconnu ou faible confiance, refus et interruptions, ACK sans début/fin, réponse perdue, étapes mal ordonnées, date future, association de mauvaise session/ID, répétition, hors délai, source usurpée, RPC autre que `robot.do`, chute et limitation fictives, correction/retrait avec **relecture après redémarrage**, absence d'écriture et score inchangé.

La CI GitHub prouve la correction du code **sur ordinateur et fixtures** seulement. Ni la RAM/RSS/CPU/latence incrémentale de C1, ni les coûts de SQLite/WAL sous charge, ni les limites de la carte RK3566 n'ont été mesurés ; les chiffres X2-C précédents ne sont pas transposables au robot. `scripts/resource-audit.sh` et vérification des capacités de l'eMMC restent nécessaires avant portage. Les essais MuJoCo X2-C étaient **passifs**, et C1 ne les transforme pas en essais d'actions exécutées.

## Condition pour EX4-C2 — preuve sur robot (non livrée)

1. **Reçu officiel ou interface constructeur vérifiée** qui expose une ID action univoque, son propriétaire, l'état `authorized/started/finished/refused/interrupted` réellement issu de `robotd`, les horloges, les préemptions, les pertes d'échantillons et la source d'authenticité. L'API OEM v44 épinglée ne fournit pas ce lien aujourd'hui ; discuter avec Pollen plutôt que créer un décideur concurrent.
2. **Deuxième source d'observation vérifiable** adaptée au geste (capteur robuste avant/après ; pas une simple prédiction Qwen), vérification d'identité du capteur, indépendance de la commande, événements concurrents, incertitudes, sol, présence d'enfants/animaux, arrêt prioritaire.
3. **Tests en simulation OEM**, puis **sur robot sous supervision** et après audit thermique, batterie, RAM, latence 50 Hz et sûreté. Sans reçu ou observation indépendante, résultat `indeterminate`, **aucune préférence physique**, aucun entraînement ni souvenir de causalité vérifiée.
4. Pour Cat-A2b [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78), de nouvelles images basses licites et indépendantes restent nécessaires et ne sont pas créées par EX4-C1.

**Décision :** EX4-C1 vérifie uniquement que des données fictives ne franchissent pas le seuil de preuve physique. Il **ne valide pas EX4-C dans son ensemble** et ne clôt pas l'issue #80.
