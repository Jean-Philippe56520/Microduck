# C/E-2 — Refus d'écriture sur objectif MEM-1 actif mais corrigé

**Date :** 04/11/2026. **Statut :** correctif candidat **PC/fixtures seulement** ; tests et CI au HEAD final à vérifier avant toute fusion. **Base GitHub réellement vérifiée :** `main@420664d97f33fff9ffeb8e4caea26f096799da59` (après #308). [Porte C/E-2 fixée sur #294 AVANT code et test](https://github.com/Jean-Philippe56520/Microduck/pull/294#issuecomment-6642577539). Le [plan d'action](plan-action.md) demeure l'autorité.

## Question / observation / preuve de manque

**Question :** une correction de provenance d'un objectif fictif persistant est-elle respectée avant toute **écriture**, et pas seulement lors du rappel/choix F2 ?

La PR [#294 C/E-1](https://github.com/Jean-Philippe56520/Microduck/pull/294), déjà fusionnée, fait refuser par les **lecteurs** MEM-1 un enregistrement SQLite contradictoire `active=1,correction_reason!=NULL`. Le schéma de fixtures peut délibérément contenir cette anomalie pour les tests négatifs. La revue de `microduck_companion/mock_goal_memory.py` sur le `main` cité a montré trois absences distinctes de contrôle d'écriture :

| Méthode existante | Avant ce candidat | Conséquence indésirable |
| --- | --- | --- |
| `create()` | Ne lit que `active` pour une fiche existante | Une fiche contradictoire peut être traitée comme doublon valide (`False`) |
| `transition()` | Vérifie `active`, révision et transition, mais pas `correction_reason` | Peut faire évoluer un état/revision corrigé à tort |
| `link_attempt()` | Vérifie `active/state` et l'EX1 mock, pas `correction_reason` | Peut persister une nouvelle référence EX1 pour une fiche corrigée |

Ce manque est un **défaut de cohérence MEM-1 de laboratoire**, pas une observation sur robot ni une cause physique. La voie `learn_from_outcome` reste interdite sans preuve EX4-C2 ; `robot.do accepted` n'atteste que la mise en file.

## Réutiliser, adapter, créer

**Réutiliser :** unique `ExperienceMemory.conn`, table `mem1_mock_goals` déjà définie, `MockExperienceLedger` EX1, mêmes refus des lecteurs C/E-1, tests existants `tests/test_mem1_mock_goal_memory.py`, EX4-A/B/C1 et DET-1/2. **Adapter seulement trois SELECT et leurs gardes**, avant idempotence ou mutation : extraire `correction_reason` et lever `ValueError("inconsistent active mock goal correction")` pour `active=1` avec marqueur. Garder `retract()` accessible pour rendre la ligne inactive **par demande explicite**, sans réparation silencieuse. **Créer :** quatre cas de régression dans le fichier de tests existant et le présent rapport ; aucune table, migration, seconde base, écrivain, RPC, capteur, agent, modèle ou autorisation moteur.

## Porte de succès / d'arrêt gelée avant exécution

**Témoin :** ces trois méthodes sur la version antérieure `main@420664d...` et SQLite fictive altérée ; **candidat :** mêmes méthodes et même fixture avec garde, sous les mêmes paramètres. Les exemples artificiels de corruption ne constituent ni des rencontres indépendantes ni des données de perception.

**Positifs (P1/P2) :** les anciens tests d'idempotence, création, transitions, EX1 lié, suspension/reprise, correction/relecture, DET-1/2, résumés et rétraction restent verts ; une fiche `active=0` reste inaccessible aux écritures normales. Les cas légitimes ne perdent pas d'expérience déjà documentée.

**Négatifs (N1–N4) :**
- Pour `source_retracted` **et** `fixture_annotation_error` insérés en fixture sur `active=1`, `create` ne rend pas un faux doublon : `ValueError` sans écriture.
- Pour ces deux marqueurs, `transition` refuse avant modification de `state` / `revision`.
- Pour ces deux marqueurs, un EX1 validement proposé/résolu **n'autorise pas** `link_attempt` à créer un lien ou à augmenter le compte d'effets.
- Après fermeture/réouverture de la **même SQLite** encore contradictoire, les trois méthodes continuent de refuser ; la seule `retract` explicite marque inactive, sans créer d'essai ni supprimer silencieusement la correction.

**Mesures de porte :** `conn.total_changes` identique avant/après chacun des appels interdits ; `state/revision/active/correction_reason` inchangés ; nombre de `mem1_mock_goal_links` stable, aucun effet/intent preference, **zéro** action moteur. **PASS** uniquement si les quatre nouveaux tests + tous tests existants + tous workflows CI au dernier SHA sont réussis. **STOP** en cas d'idempotence normale dégradée, d'un appel interdit modifiant SQLite, de régression des lecteurs, de nouveau schéma, de CI en attente/rouge ou de modification d'une sélection P14B/P15B6/P15B17.

## Frontières OEM, provenance, ressources et retour arrière

- Source OEM épinglée `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, simulation `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` ; `robotd` reste maître exclusif des moteurs et de la sûreté à **50 Hz**, `mediad` propriétaire caméra, aucune interface modifiée.
- Les 19+5+4 modules de packaging B11 sont **strictement épinglés** et restent intacts ; le fichier corrigé `mock_goal_memory.py` est **hors** de cette fermeture de 28 fichiers. Vérifier tout de même **toutes les CI** et les gitlinks avant fusion.
- Qwen 9B PC facultatif, aucune nouvelle requête, aucun secret, média, nom privé ni image COCO. Les **1 316 images COCO** déjà consommées ne sont pas réutilisées. `VIS-FOCUS-A2: STOP_A2_SOURCE_NOT_QUALIFIED` et `EX4-C2: EN ATTENTE REÇU OEM+EFFET` maintenus.
- Aucun essai sur robot absent, aucune mesure RAM/RSS/thermique NPU, aucun effet causal. **Retour arrière** si FAIL : laisser la PR non fusionnée ou revert ciblé des trois gardes et quatre tests, sans modifier les données réelles ni les archives.

**Niveaux de preuve :** *prévu* = usage de corrections sur observations physiques ; *codé* = garde MEM-1 de fiction ; *testé PC-fixtures* uniquement après CI réussies ; *simulé OEM* = non concerné ; *validé robot* = non.
