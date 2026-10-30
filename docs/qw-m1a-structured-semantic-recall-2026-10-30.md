# QW-M1A — transmettre au conseiller PC les propriétés fictives déjà mémorisées (préenregistrement)

**30/10/2026 — préenregistrement AVANT code et essais.** Base `main@450d010dbdffef8c3633a04696f62ec7aa8661a5`. OEM `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et RL `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` **inchangés**. Autorités : `AGENTS.md`, `docs/plan-action.md`, `docs/development-reuse-protocol.md`, `docs/kwipi-experiential-learning-plan-2026-10-26.md`, `docs/perception-oem-rknn-2hz-plan-2026-10-29.md`.

## Décision et manque prouvé

**Question de valeur :** sans appel PC réel ni photo, la **demande QW-1A déjà existante** peut-elle transmettre uniquement les **hypothèses de propriétés effectivement visibles dans la lecture corrigible C1/C2**, afin qu'un Qwen facultatif puisse ultérieurement en tenir compte sans consulter SQLite et sans les transformer en observations ? Aujourd'hui, `qwen9b_goal_advice.build_goal_question` appelle déjà `memory_recall.recall_memory`, mais ne conserve que les états `category_history.status` et les `prior_proposals` MEM-1/EX1 ; `ConservativeCategoryRecall.property_hypotheses` et `conflicting_hypothesis_properties` sont **ignorés**. Les données existent mais **n'atteignent pas le conseil**. C'est une lacune d'interface vérifiable indépendamment d'un vrai modèle.

**Délimitation** : ce lot **ne met pas la réponse de Qwen en mémoire** et ne réalise ni reconnaissance d'instance ni description d'une trottinette. Le vocabulaire F4-A existant est **fermé** : propriétés `texture`, `movement`, `affordance` avec leurs enums. L'ancien test réel des 180 images ABO a donné **0/48** correspondances M1-B au seuil en vigueur [MEM-2B-R](mem2b-r-abo-chairs-candidate-gate-2026-10-29.md), donc **ne relier aucune empreinte M1-B à une propriété de catégorie ni à une personne**. `S1A` a échoué sur formes/couleurs : aucun pixel inventé pour compléter ce manque.

## Réemploi plutôt que nouveau système

| Composant | Décision | Risque contrôlé |
| --- | --- | --- |
| `ExperienceMemory` + `CategorySemantics.hypotheses` et `memory_consolidation.recall_category` | **RÉUTILISER** la même SQLite et le même lecteur corrigible (F4-A/C1/C2) | Pas de nouveau writer, table ou cache ; aucune annotation de source réelle |
| `memory_recall.recall_memory` / `QW-1A build_goal_question` | **ADAPTER le contrat existant**, pas de second chargeur de mémoire | Séparer état historique, hypothèses fictives, oppositions, décisions |
| `QW-1A GoalQuestion` et `make_wire` | **ADAPTER** le JSON de consultation **opt-in PC seulement** | Liste d'enums validés, aucun ID, score interprété, texte libre, média, SQLite, requête autonome |
| `QW-1A parse_advice/query_one`, F5-C, Qwen v2, F2, M1-B, OEM | **INCHANGÉS** | Réponses unverified et non écrites, aucun pouvoir moteur ; l'essai PC réel QW-1A antérieur est négatif et n'est pas réinterprété |
| Tiers C3 (QuackNav/brain/twin) | **AUCUNE DEPENDANCE** | Ne résoudraient pas ce champ perdu, aucun coût/propriété du code tiers nécessaires |

## Contrat et corpus figés AVANT code

**Objet de test = catégorie publique `ball`** et son objectif MEM-1 existant `observe_category` suspendu ; un seul `ExperienceMemory(":memory:")`, sans personne ni média. F4-A comporte trois familles d'indices hypothétiques : `texture soft/hard`, `movement moving/stationary`, `affordance playable/not_playable`. Les valeurs sont **fictions de laboratoire**, et peuvent être contradictoires sans présumer qu'une balle est réellement douce/jouable.

**Transport QW-1A supplémentaire** : `prior_unverified_properties` (couples `{property,value,source:"fictional_llm_hypothesis_only",verified:false}`) triés et limités à **9** pour une catégorie, et `conflicting_unverified_properties` (liste ordonnée de seules familles opposées). **Ne pas exporter** confiance « calibrée », identifiant de ligne, horodatage individuel, groupe/image M1-B, nom ou clé F0, texte libre, corps complet SQLite ou observation vraie. **Sans mémoire**, les deux listes doivent rester **vides**. Lorsque la mémoire est activée, chaque hypothèse vient **uniquement** de `ConservativeCategoryRecall.property_hypotheses` conservées par C2, non de la réponse du modèle ni d'une annotation physique ; une rétraction apparaît immédiatement à la lecture suivante. Une contradiction reste visible et non résolue ; la demande ne peut pas attribuer l'autorité `verified`.

**Positifs fixés** :
1. Sur une hypothèse fictive `ball:affordance=playable`, wire avec mémoire **contient uniquement ce couple**, wire sans mémoire **n'en contient aucun** ; catégorie, but, stratégies et autres champs identiques ; pas de nouvelle écriture lors des lectures.
2. Sur `texture soft` + `texture hard`, les deux valeurs apparaissent avec le signal `texture` contradictoire, **aucune** priorité ou vérité choisie.
3. Après `retract_hypothesis`, valeur effacée de la **lecture suivante**, y compris après réouverture SQLite (corrections C2 persistantes), jamais réactivée implicitement.
4. D'autres catégories, nouvelles stratégies et images ne sont jamais associées implicitement au même objet. Le wire garde les limites QW-1A et la provenance `mock_fixture_only`.

**Négatifs fixés** : nom/texte libre, personne, propriété inconnue, valeur contradictoire fabriquée, propriété prétendue `verified:true`, liste non triée/dupliquée/au-delà 9, source falsifiée, autre base SQLite, ID/leak ou injection de SQL, réponse Qwen avec ordre moteur, horodatage invalide, conseil périmé, et champ de résultat Qwen tenté comme écriture → rejet. La réponse simulée est **uniquement** une stratégie passive pour revue humaine, Qwen réel **0 appel** en CI et `memory_writes=0` pendant construction/transport. Les tests existants QW-1A restent verts après mise à jour de l'exact contrat JSON attendu. Pas de test d'image, d'identité ni de sémantique réelle.

**Critères d'arrêt préfixés** : 100 % des positifs ci-dessus dans les fixtures, 100 % des négatifs refusés, diff minimal **avec/sans mémoire** sur le contenu des hypothèses, zéro écriture pendant le rappel, `make_wire` toujours ≤4096 octets, ancienne interface manuelle PC inchangée (seulement deux champs JSON supplémentaires). **Si une propriété supprimée réapparaît, si un texte privé passe, ou si une réponse PC devient une observation/action, STOP et revert.** CI Python générale et N1 vertes avant fusion. **CI verte signifie uniquement contrat logiciel validé.** Aucune preuve Qwen3.5 9B réel, qualité de la réponse, navigation, perception, correction autonome, 2 Hz RKNN ou autonomie de Kwipi.

**Risques et retour arrière** : de nouveaux champs peuvent influencer un vrai modèle s'il est appelé plus tard, **sans garantie de qualité** ; ils portent donc explicitement l'origine fictive et ne sont **jamais** requalifiés en fait. Retour arrière = suppression du champ optionnel et des tests de contrat ; pas de migration SQLite, aucun poids ou protocole OEM touché.

## Résultat

**Non exécuté au moment de l'enregistrement de cette porte.**
