# C/E-1 — Refuser les objectifs MEM-1 actifs mais corrigés à la lecture

**Porte préenregistrée le 04/11/2026, AVANT code correctif et tests.** Base GitHub `main@5b9ed4e034c66cf503125968fbdbc1723f1053c5`, sans sous-module modifié. Pins : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Distribution B11 historique/Yocto `1ee58387810cebb67ae0d634c351d95024483bce` intouchées. Sources : `AGENTS.md`, `docs/plan-action.md` (autorité), `docs/development-reuse-protocol.md`, `docs/cog-a0-reuse-knowledge-oem-matrix-2026-11-03.md`, `docs/e2e1a-f2-memory-pc-contract-ablation-2026-10-29.md`, `docs/sim-s1-passive-memory-ablation-2026-10-30.md`, OEM épinglé et registre C3.

## Observation, manque démontré et risque

`MockGoalMemory.__init__` définit déjà une seule table `mem1_mock_goals` dans l'unique `ExperienceMemory`. Ses contraintes SQL autorisent `active=1` **avec** `correction_reason='source_retracted'` ou `'fixture_annotation_error'`. Les lectures `get()`/`recent()` n'extraient pas `correction_reason` ; `_as_goal()` calcule `corrected` à partir de `active` seulement. `attention_focus()` sélectionne lui aussi les objectifs `active=1` sans examiner leur correction. Une ligne mémorisée contradictoire peut donc redevenir une priorité descriptive DET-1 ; `retry_attention()`/DET-2 et `memory_recall` s'appuient déjà sur `recent()`. Les PR #292 et #293 ont corrigé **d'autres tables** (hypothèses et catégories F4-A), pas MEM-1.

**Objectif borné :** refuser une telle contradiction dans les lecteurs existants, avant toute priorisation. Il s'agit d'une correction de fiabilité **sur SQLite de fixtures PC**, non d'un essai de nouvelles observations, d'un gain sémantique, d'un robot piloté ou d'une validation cognitive indépendante. Aucune nouvelle série de scènes synthétiques n'est présentée comme observations réelles. Les résultats historiques E2E-1A, SIM-S1, MEM-2B-WA et COG-A2-P0 restent acquis sans nouvelle revendication.

## Réutiliser / adapter / créer

- **Réutiliser sans duplication** : `ExperienceMemory` mono-écrivain, `MockGoalMemory` (`get`, `recent`, `attention_focus`, `retry_attention`), F2-B `PassiveRhythm.tick`, les refus `det1_goal_memory_unavailable`/`det2_goal_history_unavailable`, les tests existants DET-1 et MEM-1. Ne pas créer de second lecteur/écrivain, scorer, import Qwen ou pilote.
- **Adapter minimalement** : ajouter `correction_reason` aux SELECT des trois lecteurs déjà présents ; lever `ValueError` si une ligne retournée est simultanément `active=1` et marquée corrigée. Sans filtrage silencieux, réparation, suppression ou écriture à la lecture.
- **Créer seulement** : ce protocole, quelques cas adversariaux dans les tests existants et de brèves notes de reprise sur README/AGENTS/plan/roadmap *si les tests justifient la livraison*. Aucun changement des méthodes d'écriture, schéma SQLite, `robotd`, `mediad`, YOLOX/RKNN, firmware ou distribution B11.

## Comparateur, tests et portes fixés avant exécution

**Témoin** : les mêmes `MockGoalMemory` et F2 de `main@5b9ed4e034c66cf503125968fbdbc1723f1053c5`. F2 reçoit une catégorie `mock_fixture_unix` explicitement fictive et une motivation détermination élevée ; mémoire de but optionnelle, zéro action réelle, zéro image, zéro faux reçu OEM.

- **P1** : objectif fictif créé/activé normalement (`active=1,correction_reason=NULL`) : `get`, `recent`, `attention_focus` et F2 DET-1 donnent la même catégorie/raison que le témoin ; aucune permission motrice.
- **P2** : `retract(...source_retracted)` légitime (`active=0`) reste absent de `get`/`recent`/`attention_focus`, y compris après réouverture ; `include_withdrawn=True` conserve `corrected=True`.
- **P3** : les comportements DET-2 de suspension/reprise fictive, les résumés de buts MEM-2 et les tests historiques restent inchangés.
- **N1/N2** : pour chacune des deux raisons de correction, mutation adversariale *sur DB de test uniquement* de `active=1` conservé : `get`, `recent`, `recent(include_withdrawn=True)`, `attention_focus` et `retry_attention` refusent par `ValueError` ; le contenu SQLite et `conn.total_changes` restent intacts pendant ces lectures.
- **N3** : à travers **le vrai** `AutonomyBrain.propose_balanced_passive`, le but corrompu ne produit ni focus DET-1 ni réengagement DET-2 : `idle`/raison d'indisponibilité existante, pas de changement de motivation-énergie, pas de commande motrice/PC, pas d'écriture mémoire.
- **N4** : la corruption persiste après fermeture/réouverture de la **même** SQLite et est encore refusée ; remise de `correction_reason=NULL` **uniquement dans le banc** restaure les lectures légitimes. Aucune réparation automatique.
- **N5** : les refus historiques de source non fiable, horloge/TTL, catégories invalides, faux gestes OEM, conflits EX1 et privilèges restent inchangés ; gitlinks, B11 et capacités OEM intacts.

**PASS** = P1–P3, N1–N5, tests ciblés et ancienne suite complète, **toutes** les CI du HEAD final vertes, changement limité aux lectures MEM-1, tests et docs. **STOP** = priorité DET-1 obtenue depuis un but corrigé, écriture pendant lecture, observation légitime perdue, régression DET-2, suite/CI non verte, modification de SQLite/OEM/B11 ou fausse revendication physique. **Retour arrière** : laisser la PR brouillon non fusionnée ou revert ciblé après fusion.

## Statuts de preuve séparés

`prévu` : comparaison C/E sur de véritables scènes inédites et vérifiées. `codé/testé PC-fixtures` : garde de lecture MEM-1 si et seulement si tests/CI franchis. `simulé OEM` : non concerné ; `validé robot` : non, robot absent. `robot.do accepted` n'est jamais une fin ou un effet. Qwen 9B PC facultatif et ses nouveaux essais suspendus. La perception COG-A2 attend toujours GT nouvelle et gain contre F2/DET-1/inspection/mémoire.
