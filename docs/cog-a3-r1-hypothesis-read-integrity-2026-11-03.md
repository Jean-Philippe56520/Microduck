# COG-A3-R1 — refus des hypothèses F4-A persistées incohérentes

**Préenregistrement 03/11/2026 — AVANT toute modification des sources/tests.** Base `main@0ddc9862cc5476d88b2a3b27cdfce19231b1110e`. OEM/Yocto inchangés : microduck `942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto B11 `1ee58387810cebb67ae0d634c351d95024483bce`.

## Porte 0 — manque démontrable et résultat fonctionnel

**Observation source** : `CategorySemantics.__init__` ne pose aucun CHECK SQL sur les valeurs `category/property/value` de `f4a_property_hypotheses`; il ne lie pas `active=1` à `correction_reason IS NULL`. Le seul lecteur `CategorySemantics.hypotheses()` fait actuellement `SELECT id,category,property,value,proposed_confidence` avec `WHERE active=1 ...`, puis construit `PropertyHypothesis` sans revérifier **le vocabulaire fermé ni l'absence de marqueur de correction**. Ces incohérences peuvent être introduites par `UPDATE` de la SQLite existante. Le validateur `_prune()` vérifie les clés à l'écriture/maintenance, pas à la lecture seule ; `memory_consolidation.recall_category()` réutilise ce lecteur. Une propriété inventée ou une hypothèse marquée corrigée pourrait ainsi être restituée en tant qu'hypothèse active dans le diagnostic et les rappels. Il ne s'agit pas de faits physiques ni d'autorisations d'action ; l'erreur réside dans la **véracité des rappels**.

**Hypothèse du correctif** : ajouter une unique vérification **lecture seule** des colonnes récupérées (type/valeur de `id`, `category`, `property`, `value`, `source`, `active`, `correction_reason`) et refuser explicitement les lignes incohérentes plutôt que les normaliser en connaissance. Retenir la confiance bornée existante et les mêmes quotas/TTL. Aucun schéma, writer, stockage, seuil de perception ou historique ne change.

## Témoin pré-déclaré / cas positifs et négatifs

**Témoin** = même `ExperienceMemory` unique, mêmes lignes d'hypothèses, C1 `recall_category` inchangé, lecture `CategorySemantics.hypotheses()` avant correctif, et observation sans Qwen ni moteur.

- **P1** : ligne valide `cat/texture/soft` à confiance 0,72 => même `PropertyHypothesis`, `source=fictional_llm_hypothesis_only`, `confirmed=False`, `can_authorize_actions=False` ; appel sans `conn.total_changes`.
- **P2** : deux hypothèses valides contradictoires `dog/movement/moving` et `stationary` => les deux restent **non vérifiées**, C1 conserve le conflit, sans arbitrage.
- **P3** : correction légitime par `retract_hypothesis`, lecture et C1 ne renvoient plus l'hypothèse ; après réouverture de la SQLite la rétraction est encore respectée.
- **N1/N2** : altération persistée `property='motor_permission'` ou `value='safe_to_kick'` sur une ligne active => `ValueError` en lecture directe, également via C1 ; pas d'invention de possibilité d'action.
- **N3** : `active=1, correction_reason='source_retracted'` => `ValueError` ; la présence d'une raison de correction ne peut coexister avec une proposition active.
- **N4** : `id` invalide (0 ou négatif), lorsqu'insérable sous la clé SQLite, => `ValueError`.
- **N5** : source incohérente ou fausse, si injectée dans une copie adversariale de la base en contournant le CHECK SQL => `ValueError` ; le comportement normal du CHECK reste inchangé.
- **N6** : autre DB, source expirée, copie corrigée, confiance non finie ou hors plage => refus/filtres existants inchangés ; aucune écriture de lecture ni réactivation de correction.

**Succès** : P1–P3 conservés, N1–N6 refusés, `memory_recall`/C1 et les tests F4-A originels sans régression ; CI GitHub du nouveau SHA entièrement verte, incluant intégrité historique B11. Une différence de rappel **sur entrée volontairement corrompue** est un gain de sûreté des données PC-fixtures, pas un apprentissage, une perception, une causalité ni une compétence OEM. **STOP** en cas de lecture qui répare/détruit les données, de nouvelle SQLite, d'échec CI, de perte d'hypothèses valides ou d'effet moteur. Retour arrière : revert ciblé de ce prédicat et de ses tests/documents.

## Réutilisation / restrictions

**Réutiliser** `ExperienceMemory` et le même `CategorySemantics`, `PROPERTIES`, `HYPOTHESIS_CATEGORIES`, `CORRECTION_REASONS`, `_confidence`, `memory_consolidation.recall_category` et `tests/test_category_semantics.py`. **Adapter uniquement** `hypotheses()` et tests sur les tables existantes. **Ne pas créer** de second writer, SQLite, couche de rappel, modèle, réseau Qwen, service OEM, API motrice, caméra, paquet Yocto, modification de l'archive historique B10/B11 ou du gitlink. COG-A2 demeure EN ATTENTE de propriétés observées et 4 positifs/8 négatifs ; ce correctif de rappel ne débloque pas A2.
