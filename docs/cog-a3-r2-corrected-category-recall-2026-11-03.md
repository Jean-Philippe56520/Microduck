# COG-A3-R2 — intégrité des corrections des catégories historiques

**Porte préenregistrée le 03/11/2026 avant code et tests.** Référence `main@2f28480bd6f83816027e565aa6e163ffc0b5d6e9`. Pin constructeur inchangé `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Aucune modification Yocto B11 (`1ee58387810cebb67ae0d634c351d95024483bce`).

## Objectif et manque observé

Les deux lecteurs **existants** `CategorySemantics.recall()` et `memory_consolidation.recall_category()` restituent des catégories historiques fictives de `f4a_semantic_categories`, en exigeant `s.active=1`, et les sources F1-C/F2-C encore cohérentes. Mais les contraintes SQL existantes n'interdisent pas `active=1` **avec** `correction_reason='source_retracted'` ou `'fixture_annotation_error'`. Ces lecteurs ne lisent pas `s.correction_reason` et peuvent attribuer à une ligne contradictoirement « corrigée » une observation historique toujours active. `CategorySemantics.hypotheses()` a été durci pour le même type d'incohérence dans COG-A3-R1 / #292, mais **cette autre table historique n'a pas été couverte**. Le risque est une explication de mémoire trompeuse sur fixtures PC, jamais une permission moteur ni une observation physique validée.

**Comparateur** : fonctions existantes à `main@2f28480b`. **Changement minimal** : lire `s.correction_reason` dans les mêmes SELECT et **lever `ValueError` sans écriture** si une ligne sélectionnée active porte une raison de correction. Ne pas supprimer, filtrer silencieusement, autoriser un fait ou créer une troisième lecture. Les lignes `active=0` correctement rétractées restent absentes, conformément à l'existant. Ne pas changer schéma/DB, `CategorySemantics.remember()`/`forget_observation()`, `PassiveLearning`, `robotd`, modèles, caméra ou pin.

## Tests et critères fixés avant essai

- **P1** : `ball` fictive historique valide avec `active=1`, `correction_reason=NULL` : `CategorySemantics.recall` et C1 produisent la même catégorie, modalité, compte et provenance historiques qu'avant la modification, aucun effet réel ni récompense.
- **P2** : `forget_observation(..., reason='source_retracted')` légitime (`active=0`) : les deux lectures restent vides, y compris après réouverture de la même SQLite ; aucune réactivation par rappel.
- **P3** : le lecteur `hypotheses()` et les conflits d'hypothèses de #292 restent inchangés, sans seconde base.
- **N1** : mutation contrôlée dans une SQLite de fixture `active=1`, `correction_reason='source_retracted'` : `ValueError` dans les deux lecteurs, `conn.total_changes` inchangé pendant la lecture, aucune ligne supprimée.
- **N2** : même test avec `fixture_annotation_error`, y compris appel `recall(category=None)` et C1 ; pas de succès silencieux.
- **N3** : après fermeture puis réouverture de la même SQLite contenant une incohérence de correction, les deux lecteurs refusent encore ; retour à `correction_reason=NULL` dans le banc permet le rappel valide.
- **N4** : source de catégorie supprimée/rétractée par F2-C, date périmée ou catégorie inconnue : les refus/abstentions existants restent inchangés.
- **N5** : ni SQL libre, ni moteur, ni caméra, ni Qwen, ni promotion d'une hypothèse en fait, ni effet sur l'image DEV B11.

**PASS** : P1–P3, N1–N5, tests historiques complets, CI du HEAD exact **toutes vertes**, diff seulement aux deux lecteurs, tests et docs ; aucun échec de la porte B10/B11. **STOP** : régression du rappel valide, écriture pendant le rappel, fausse certitude, modification OEM/SQLite, CI non verte ou changements fonctionnels annexes. Retour arrière : PR laissée sans fusion, ou revert ciblé après fusion selon diagnostic.

## Réemploi / vérité des preuves

Réutiliser `ExperienceMemory` unique, `CategorySemantics`, C1, F1-C/F2-C, les corrections F4-A, les deux fichiers de tests existants et les gardes COG-A3-R1. Ne créer **aucun** moteur de consolidation, autre SQLite ou comportement. Testé sur **fixtures PC seulement**, pas une mémoire vécue, pas une observation `mediad`, pas une fin/effet OEM ; COG-A2 toujours **EN ATTENTE** de propriétés indépendantes et de comparaison 4 positifs/8 négatifs face au système complet.

La CI de `main@2f28480b` post-fusion est distincte des 9/9 CI de la PR #292 : ne pas présumer qu'elle est réussie tant que GitHub ne le confirme pas.
