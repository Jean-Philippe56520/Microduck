# C2 — Retenues de correction F4-A durables et bornées, sans nouvelle SQLite

**28 octobre 2026 ; statut : correctif Python et tests de fixtures candidats, CI/PR à vérifier avant fusion.** Suite de [C1 — rappel historique](c1-conservative-category-recall-2026-10-28.md), conformément au [plan directeur](plan-action.md). Ce lot ne modifie ni OEM, ni ONNX, ni moteur, ni analyse Qwen réelle, ni M1-B. **Aucune preuve robot ni apprentissage causal.**

## 1. Porte d'ingénierie : observation, hypothèse, preuve, échec, risques, retour arrière

**Observation vérifiée sur le code de main :** F4-A utilise déjà une table de propositions avec la clé UNIQUE (category, property, value), les champs active et correction_reason et une commande explicite retract_hypothesis. Son nettoyage supprimait pourtant toutes les propositions (actives **et rétractées**) après 14 jours, puis toutes celles hors du top 64, ce qui supprimait aussi les rétractions. Après suppression, INSERT OR IGNORE autorisait silencieusement la même combinaison auparavant rétractée. Ce défaut ne concerne pas uniquement le rendu C1 : il affecte la prévention des propositions erronées après redémarrage.

**Hypothèse testable :** le vocabulaire **fermé** suffit pour garder les rétractions dans la **même** table, sans tombstone supplémentaire. Les catégories de conjectures sont au nombre de **six** (ball, toy, cat, dog, microduck, other_object) ; les propriétés texture, movement et affordance ont chacune trois valeurs contrôlées. Le produit fait **6 × (3 + 3 + 3) = 54 clés** théoriques, en dessous du quota historique **64**. La table ne peut donc pas croître au-delà de 54 lignes avec des entrées exclusivement créées par l'API validée.

**Preuve visée :** un retrait de conjecture conserve la clé et le motif après 14 jours, plusieurs TTL, redémarrage et nouvelles propositions similaires ; une variante différente peut être enregistrée sans réactiver la variante fautive ; **54/54 retraits conservés**, aucune deuxième base ou nouvelle table, et les propriétés restent hypothèses non vérifiées. Les anciens fichiers avec schéma F4-A déjà créé doivent être ouverts sans migration intrusive ; les anciennes corrections encore présentes doivent être gardées.

**Risque et critères d'échec :** purge silencieuse d'une rétraction ; promotions de fiction Qwen en vérité ; ajout de catégorie/valeur libre ; corruption du dictionnaire ou nombre de lignes supérieur au quota ; adaptation qui ralentit le propriétaire moteur ou crée une seconde SQLite. **Refus** en cas de table non conforme ou de modification du dictionnaire faisant dépasser le quota. **Retour arrière :** ce changement ne crée pas de table ni de migration, mais un retour à l'ancien code réactiverait l'effacement des corrections ; sauvegarder/inspecter une copie locale SQLite avant toute restauration d'ancienne version, sans utiliser de données privées sur GitHub. Ne jamais promettre de reconstruire des corrections déjà purgées dans l'ancien historique.

## 2. Audit OEM, sources, réutilisation

| Source vérifiée | Réutiliser / adapter / créer | Constat, limite |
| --- | --- | --- |
| [OEM épinglé microduck 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) et [RL b02fdea4](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3) | **Ne pas modifier** | robotd seul pilote les moteurs et la sûreté ; la mémoire C2 n'utilise aucune API OEM |
| [ExperienceMemory](../microduck_companion/episodic_memory.py) et [CategorySemantics F4-A](../microduck_companion/category_semantics.py) | **Adapter le nettoyage existant** | Table déjà UNIQUE, active, correction_reason, source fictive et dates ; aucun nouveau schéma SQL |
| [F1-C et F2-C](../microduck_companion/passive_memory.py), [C1](../microduck_companion/memory_consolidation.py) | **Réutiliser sans double écriture** | Catégories historiques toujours issues de fixtures actives ; C1 ignore les hypothèses rétractées et ne les transforme pas en faits |
| [M1-B / R2-A](r2a-single-memory-selection-2026-10-26.md) | **Laisser inchangé** | Seul écrivain sélectionné de signatures 64/16 octets, pas d'identité ni de détection sémantique |
| [EX1–EX4-C1](ex4c1-mock-causal-preflight-2026-10-27.md), [registre communautaire C3](community-reference-registry-2026-10-26.md) | **Ne rien copier/créer** | Aucune conséquence, fin d'acte OEM ou causalité ; les tiers et PR OEM #381/#414 ne livrent pas de correction F4-A à importer |

**Choix : conserver les corrections dans la table existante** au lieu de créer un journal parallèle, une seconde SQLite ou une tâche de nettoyage. Aucun modèle 9B, service ou librairie additionnelle. Les droits/licences constructeur et tiers ne changent pas : aucun code tiers importé.

## 3. Modification contrôlée et contrat de rétention

- Le nettoyage F4-A conserve la purge habituelle des **propositions actives** de plus de 14 jours ou trop futures, mais **ne supprime plus les lignes active=0** ayant un motif de rétraction valide. La clé UNIQUE empêche l'insertion du même (category, property, value) via hypothesize, même après redémarrage.
- Une rétraction explicite inscrit active=0, le motif source_retracted ou fixture_annotation_error, et **remet proposed_confidence à zéro** afin de ne pas garder une confiance de conjecture périmée. Elle ne confirme ni la négation de la propriété ni une autre valeur.
- L'expiration des propositions actives intervient maintenant **avant** l'insertion ; un candidat actif expiré peut être proposé à nouveau une seule fois, sans contourner une rétraction.
- MAX_HYPOTHESIS_KEYS=54 doit rester inférieur ou égal à MAX_HYPOTHESES=64. La validation parcourt au plus 65 clés, refuse une catégorie/propriété/valeur hors vocabulaire, une ligne retirée sans motif, une ligne active avec motif ou un total >64. En cas de refus pendant prune ou hypothesize, la transaction SQLite est annulée : **aucune correction supprimée en compensation**.
- Les conjectures retirées ne sont **pas retournées** par hypotheses() ou recall_category(), ne sont pas des observations sensorielle et ne portent aucune autorisation physique. Une variante contradictoire, non retirée, peut rester une hypothèse non confirmée, sans devenir une connaissance.
- **Aucune modification du schéma** : la table et le UNIQUE historiques existent déjà. Les corrections anciennes encore présentes survivent ; celles que l'ancienne purge a déjà effacées sont irréversiblement **inconnues**. Pas de récupération par imagination, Qwen, similarité d'empreinte ou retour moteur.

Une suppression explicite/levée de correction serait une fonctionnalité administrative à contractualiser séparément : **C2 n'introduit pas de réhabilitation automatique**, pour éviter qu'une même erreur soit réapprise sans preuve nouvelle.

## 4. Limites de la garantie

Cette conservation « durable » porte sur les **clés de conjecture F4-A à vocabulaire fermé**, pas sur tous les événements du robot, ni sur des corrections de photos, de catégories réelles ou sur un nombre infini de détails. La garantie est bornée par les 54 clés du dictionnaire et par la persistance effective du fichier SQLite ; panne/disque perdu, restauration d'une sauvegarde antérieure, écriture SQL externe, et changement du schéma/dictionnaire sont **hors contrat**. La taille physique du fichier SQLite ou de son WAL peut rester supérieure au nombre de lignes en vie.

Les **corrections d'observations à ID dynamique** dans f4a_semantic_categories et F2-C suivent encore leurs propres rétentions/source F1-C ; elles ne bénéficient pas de l'immortalité des 54 clés. On ne peut pas leur appliquer une persistance perpétuelle sans budget supplémentaire et sans preuve d'origine. **Ne pas prétendre que C2 conserve toute correction jamais vue.** Les catégories présentes dans Qwen PC mais absentes de F1-C (ex. chaise) restent non intégrées aux observations OEM.

## 5. Tests de validation

Les tests supplémentaires couvrent : le dictionnaire à 54 clés, plusieurs expirations, redémarrage d'une ancienne SQLite, tentative de réinsertion après suppression logique, rétraction répétée sans changer le motif, nouvelles variantes, 54/54 corrections, régression de la TTL des propositions actives, horloge en arrière/futur, ligne rétractée sans raison, valeur de catégorie forgée, 65+ lignes de base altérée et capacité diminuée, absence de nouvelle table, zéro action moteur/effet/reward. L'ancien test F4-A de suppression totale est corrigé pour refléter cette nouvelle garantie.

**Preuves de sortie attendues** : CI Python complète et tests positifs/négatifs verts, diff sans gitlinks, revue de schéma, mention de l'absence de mesure RK3566. Tests sur fixtures ≠ performance embarquée, ≠ mémoire opérationnelle, ≠ lecture d'image réelle ou effet d'action. Avant robot physique, effectuer l'audit OEM, la mesure de stockage/montage, RSS, WAL, CPU, thermique et deadlines de la boucle 50 Hz.

## 6. Après C2

**C3** : mesurer sur **scènes indépendantes** les gains/erreurs de décision passive avec et sans rappel, sans PC puis avec Qwen facultatif, après validation de la source de catégories (Cat-A2b #78). **SIM-E2 #101** reste séparé, sans locomotion validée. Toute attribution causale réelle reste bloquée sans fin d'acte OEM et effet indépendant (EX4-C2).
