# N3 — Inventaire des tables, écrivains et corrections SQLite (sans migration)

**Date :** 28 octobre 2026. **Statut de cette étape :** [PR N3 #131](https://github.com/Jean-Philippe56520/Microduck/pull/131), [CI complète #40747572022 réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40747572022) au commit `1d4d2732`, audit statique et tests sur fixtures, **pas de nettoyage destructif ni de validation sur Microduck**. Autorité pour les priorités : [plan directeur](plan-action.md). Le lot suit N2 ([PR #130](https://github.com/Jean-Philippe56520/Microduck/pull/130), fusionnée) et ne retarde ni Cat-A2b/C3-B ni le PC Qwen 9B.

## 1. Porte préalable : observation → hypothèse → preuve → arrêt

**Observation (source `main@5c521db90766750f129ea01a99290f694e7d3fad`) :** `ExperienceMemory` ouvre la SQLite principale dans [`episodic_memory.py`](../microduck_companion/episodic_memory.py). Les modules F1/F2/F4/EX/M1/F5-C créent des tables supplémentaires via la **connexion passée** (`memory.conn`). Les propositions et les effets fictifs vivent dans des tables différentes. `kwipi_journal.py` ouvre en plus **deux** connexions `sqlite3.connect(...?mode=ro, uri=True)` avec `PRAGMA query_only`; `sim_x2c_acceptance.py` ouvre un **troisième lecteur** `mode=ro, uri=True` pour vérifier un fichier de simulation sans le modifier. Une connexion de lecture distincte **n'est pas une deuxième autorité d'écriture**.

**Hypothèses à tester :** (H1) le code source du package conserve un seul **site** d'ouverture écrivable, dans `ExperienceMemory`, et aucun deuxième fichier SQLite autonome créé ailleurs ; (H2) les corrections `f4a_property_hypotheses` ne sont supprimées que si l'hypothèse est encore active ; (H3) M1-A, M1-B et les autres familles ont des propriétaires explicites, à documenter avant toute fusion de tables ; (H4) certains fichiers historiques, comme `mock_cycles.py`, modifient des tables créées ailleurs, mais cela reste une expérience fictive, pas un second cerveau.

**Preuve visée :** un inventaire reproductible de **tous les modules Python du package**, des opérations SQL littérales, des tables déclarées, des modules écrivains et des ouvertures de connexion, avec artefact JSON de CI et tests négatifs. **Critères d'arrêt :** nouveau site de connexion écrivable, disparition/duplication du propriétaire d'une table sensible, SQL `DROP TABLE` / `ATTACH DATABASE` / `DETACH DATABASE`, suppression de `f4a_property_hypotheses` sans condition `WHERE active=1`, ou CI générale rouge. Le programme refuse les liens symboliques et les erreurs de syntaxe au lieu de les ignorer.

**Risque et retour arrière :** faux positifs dus à la reconnaissance textuelle SQL, opérations SQL construites dynamiquement non suivies, accès indirect à une base inconnue via une bibliothèque tierce, et confusion entre **site d'ouverture dans le code** et nombre de connexions/processus réellement actifs. L'audit **n'ouvre aucune SQLite** ; aucun schéma, donnée, média, clé, taille de base, WAL, modèle ou service OEM n'est modifié. Revert de la PR suffit ; **aucune migration à inverser**.

## 2. Vérifications OEM et réemploi avant création

- **OEM épinglé inchangé :** [`microduck@942e58e3`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567), [`microduck_rl@b02fdea4`](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3). `robotd` seul contrôle les moteurs à 50 Hz ; `vetbook` est un journal de fonctionnement matériel, pas une mémoire de catégories/souvenirs comparable à `ExperienceMemory`. M9 n'est pas livré au SHA épinglé ; [design communautaire #381](https://github.com/pollen-robotics/microduck/pull/381) toujours ouvert, non une API intégrable ; [#450](https://github.com/pollen-robotics/microduck/pull/450) toujours ouverte, aucun modèle moteur importé.
- **Companion existant :** [R1.5](r15-retrospective-reuse-audit-2026-10-26.md), [R2-A](r2a-single-memory-selection-2026-10-26.md), [C2 — corrections durables](c2-durable-hypothesis-corrections-2026-10-28.md), [EX4 — preuve de conséquences](ex4a-execution-evidence-audit-2026-10-27.md). Ces contrats sont conservés. **M1-B `r2a_single_writer=True` fonctionne à la frontière de son API, pas comme verrou global contre un ancien programme M1-A** ; il doit continuer à échouer fermé en présence de lignes M1-A.
- **Tiers pertinents :** [registre C3](community-reference-registry-2026-10-26.md) : QuackNav/mapd candidat pour mémoire spatiale/navigabilité, distinct des souvenirs cognitifs. Aucun code tiers, schéma externe ou poids importé.

| Réutiliser | Adapter | Créer |
| --- | --- | --- |
| `ExperienceMemory`, méthodes `r2a_single_writer`, tombstones C2 et tests existants | Workflow CI Python existant (aucun nouveau workflow), rapports pour la provenance des écrivains | Un scanner AST hors runtime utilisant seulement `ast`, `re`, `json`, et 7 tests de refus sur fixtures |

## 3. Tables observées sur les modules ciblés avant CI

**22 tables déclarées** sur **121 modules** dans le rapport complet de la [CI diagnostique #40747029850](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40747029850), artefact JSON N3 téléchargé et vérifié. La première CI était **rouge** parce que le garde n'avait pas encore répertorié le lecteur RO X2-C, et non parce qu'une seconde base écrivable existait :

| Famille | Tables | Provenance et statut |
| --- | --- | --- |
| F0 | `objects`, `experiences`, `sim_motion_trials`, `intent_preferences` | Socle `ExperienceMemory` ; `sim_motion_trials` et ses préférences sont **simulation**, pas action robot |
| F1/F2 | `passive_observation_log`, `passive_learning_events`, `passive_attention_preferences` | Observations et préférences **mock**, corrections distinctes |
| P2 | `mock_cognitive_cycles` | Résultats scénarisés, jamais exécution moteur autonome |
| X2-C simulation | `sim_passive_cycles` | Cycles passifs MuJoCo fictifs ; une évolution historique du schéma ajoute trois colonnes par SQL construit sous liste fermée |
| F4-A | `f4a_mock_behavior_outcomes`, `f4a_semantic_categories`, `f4a_property_hypotheses` | Conséquences simulées / sémantique / hypothèses ; rétractions à préserver |
| F4-B/C/D | `f4b_mock_spatial_observations`, `f4c_mock_social_proposals`, `f4d_mock_optin_associations` | Repères/échanges/jetons fictifs, aucune localisation ni identité physique |
| M1-A/B | `m1a_compact_patterns`, `m1b_groups`, `m1b_signatures` | Deux prototypes historiques ; **une seule voie M1-B recommandée en R2**, M1-A témoin |
| EX1/EX2 | `ex1_mock_experiences`, `ex2_mock_effects` | Intentions, statuts et effets fictifs, **pas de causalité robot** |
| F5-C | `f5c_pc_uses`, `f5c_pc_state` | Quotas/état des consultations PC ; pas une deuxième base |

**Chevauchement à ne pas confondre avec un doublon de schéma :** `mock_cycles.py` met à jour les colonnes de `objects` et insère `experiences`, bien que ces tables soient créées par `episodic_memory.py`. Cette **écriture intermodule historique** doit rester étiquetée mock ; elle ne doit pas être branchée aux effets réels. `ExperienceMemory.intent_preferences`, `passive_attention_preferences` et `f4a_mock_behavior_outcomes` servent des types de préférences/observations différentes ; les fusionner effacerait leur provenance.

### Bilan machine de l'artefact N3 initial

- **121 modules analysés, 22 tables, 95 occurrences SQL littérales** recensées par les expressions du scanner.
- **4 ouvertures SQLite directes** : 1 site avec capacité d'écriture dans `episodic_memory.py`, **3 sites `mode=ro, uri=True`** dans `kwipi_journal.py` (2) et `sim_x2c_acceptance.py` (1). Ce sont des **sites de code**, pas le nombre de connexions actives sur une machine.
- **2 écritures intermodules** dans `mock_cycles.py` vers `objects` et `experiences` ; elles sont des traces fictives P2a, pas des mesures d'effet réel.
- **4 appels SQL construits dynamiquement** et non résolus par le scanner : `experience_expectations.py` (SELECT avec placeholders de catégories de cues bornées), `kwipi_journal.py` (SELECT par fragments/conditions validées, connexion lecture seule), `passive_learning.py` (SELECT avec clauses `IN` de placeholders), `sim_passive_cycles.py` (**ancien `ALTER TABLE` dynamique** de trois colonnes prévues par dictionnaire fermé en simulation). Ces quatre cas ont été localisés et lus ; **aucun n'est déclaré automatiquement sûr par N3**, toute modification de structure ou de données devra être testée séparément.
- **Aucun `DROP TABLE`, `ATTACH/DETACH DATABASE` littéral**, aucun schéma critique dupliqué trouvé par cet outil ; les SQL dynamiques, les imports réfléchis et les migrations historiques nécessitent encore une analyse plus profonde avant portage.

## 4. Outillage et tests N3

- `scripts/n3_sqlite_audit.py` parcourt les sources Python en AST **sans importer le package**. Il reconnaît les SQL **littéraux** de `.execute`, `.executemany` et `.executescript` (CREATE TABLE, INSERT/REPLACE, UPDATE, DELETE), les `sqlite3.connect` directs (y compris alias d'import), les connexions URI lecture seule, et les écritures sur tables créées par un autre module. Les appels à SQL dynamique sont **rapportés comme inconnus**, pas déclarés sûrs.
- `tests/test_n3_sqlite_audit.py` : **9 tests de fixtures** (un écrivain + lecteur RO, lecteur de simulation existant autorisé, autre lecteur RO inconnu refusé, deuxième écrivain refusé, `uri=False` refusé, suppression de correction refusée, DROP refusé, SQL dynamique détecté, source Python invalide refusée).
- Le workflow Python existant exécute en plus l'inventaire sur **tout** `microduck_companion/`, refuse les limites destructives et téléverse un rapport **sans image ni souvenir**. Ces contrôles AST ne remplacent **pas** les tests de comportements C2/R2-A/EX, déjà dans la suite et à maintenir.

Commande de vérification sur un clone public du dépôt :
```sh
python -m unittest discover -s tests -p test_n3_sqlite_audit.py -v
python -m scripts.n3_sqlite_audit --output /tmp/n3-sqlite-audit.json
```

**Statut des preuves :** les 9 tests sur fixtures ont été exécutés localement avec succès sur la copie isolée de l'outil, **sans le dépôt complet** ; l'inventaire de 121 modules/22 tables est le résultat de la première CI diagnostique. La correction du lecteur X2-C a passé la [CI complète #40747572022](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40747572022) ; **contrôler les tests du dernier commit documentaire avant fusion**.

## 5. Décision de nettoyage après inventaire

**Conserver les tables sans migration.** Le nombre de tables ne mesure pas à lui seul une surcharge : une table vide peut occuper très peu d'espace et les indexes/WAL dépendent des données réelles. Le prochain travail pertinent est de mesurer (sur une copie de fixtures) l'empreinte et les accès des tables réellement actives, puis de définir **le seul chemin de mémoire à porter**. En particulier, toute consolidation devra distinguer observation, hypothèse, correction, intention, acceptation OEM, achèvement et **effet indépendant** ; un `robot.do accepted` ou résultat EX2 scripté ne mérite jamais un crédit causal.

Aucun test physique ni estimation de RAM/stockage RK3566 ne peut être fourni actuellement. Le pack ne devient pas embarquable par ce rapport.
