# C1 — Rappel conservateur des catégories et hypothèses, sans second écrivain

**28 octobre 2026.** Chantier C du [plan directeur](plan-action.md). Ce lot ajoute **une lecture dérivée non persistée** de la seule SQLite ExperienceMemory, sans moteur ni autonomie. Le code F4-A existant, les protections F2-C, les signatures M1-B/R2-A et les historiques EX restent propriétaires de leurs propres données.

## 1. Porte de preuve, hypothèses et risques

**Observation :** CategorySemantics.recall() liste au plus 50 observations historiques sans bilan par catégorie, modalité ou session. F4-A peut conserver jusqu'à 256 lignes ; des hypothèses de propriétés contradictoires sont lues séparément. Une source rétractée ou expirée ne doit pas compter comme une nouvelle observation. M1-B ne démontre ni identité individuelle ni sémantique réelle ; EX1–EX4-C1 ne certifient pas une exécution moteur réelle.

**Hypothèse testable :** compter toutes les observations F4-A encore corroborées par F1-C et F2-C, sans cache ni écriture, permet un rappel utile mais strictement historique. La session de journal représente un processus de fixture, **pas** une scène indépendante. Les propriétés attribuées par une hypothèse fictive restent des hypothèses même si plusieurs sessions rapportent une catégorie.

**Critères de réussite :** trois observations de chien dans deux sessions fictives donnent trois occurrences, deux sessions et **zéro scène indépendante attestée** ; une correction F2-C ou F4-A retire immédiatement sa contribution ; deux hypothèses opposées sont signalées comme contradictoires, jamais arbitrées ; une nouvelle connexion à la même SQLite retrouve uniquement les preuves actives ; aucune table, ligne, préférence ou commande écrite par le lecteur.

**Échecs/refus :** preuve absente, périmée, rétractée ou modifiée, catégorie hors vocabulaire, horloge non finie ou historique corrompu dépassant 256 lignes. Risques : gonfler artificiellement une certitude par des observations répétées, traiter les sessions comme preuves indépendantes, ou convertir la sortie Qwen en connaissance ou permission. **Retour arrière :** suppression du seul nouveau module, de son test et de la documentation ; aucune migration ni données à restaurer.

## 2. Sources inspectées et matrice réutiliser / adapter / créer

| Composant | Réutilisation existante | Frontière de confiance |
| --- | --- | --- |
| [OEM robotd épinglé 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) et [simulation b02fdea4](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3) | Robotd seul propriétaire moteur/sûreté | Aucun appel OEM ou modèle nécessaire pour ce rappel |
| [F1-C](../microduck_companion/passive_memory.py), [F2-C](../microduck_companion/passive_learning.py) | Journal fictif, provenance, statut, correction active | Exiger source mock, canal mock_fixture_unix, statut identified et conséquence F2-C active |
| [F4-A](../microduck_companion/category_semantics.py) | SQLite existante, tables de catégories et hypothèses, date, confiance déclarée, TTL 14 jours, 256 lignes / 64 hypothèses | Réutiliser les validations et les jointures ; une confiance de fixture n'est pas une probabilité réelle |
| [M1-B / R2-A](../microduck_companion/multiview_pattern_memory.py), [contrat R2-A](r2a-single-memory-selection-2026-10-26.md) | Seul écrivain choisi pour signatures 64 octets image/16 audio | Aucune lecture ou double écriture de signature comme preuve de catégorie ou d'individu |
| [EX1–EX3](../microduck_companion/experience_ledger.py), [EX4-C1](ex4c1-mock-causal-preflight-2026-10-27.md) | Épisodes et conséquences fictives réversibles | Aucune causalité attribuée, aucun crédit sur simple intention ou accusé robot.do |
| [Registre C3](community-reference-registry-2026-10-26.md) | QuackNav, Twin, GC/Smartulf, Quacksat, propositions OEM #381/#414 | Pas de second moteur, migration, dépendance ou mémoire tierce introduite |

**Réutiliser :** F1-C, F2-C, F4-A et la connexion ExperienceMemory existante. **Adapter :** stratégie de rappel avec jointures et agrégation bornée. **Créer :** seulement le module de lecture memory_consolidation.py et ses tests adversariaux. Pas de modèle supplémentaire, ORM, seconde SQLite, table, portage RK3566, service, fichier privé, récompense ou pilote.

## 3. Contrat du nouveau rappel

La fonction [recall_category()](../microduck_companion/memory_consolidation.py) prend l'instance CategorySemantics déjà attachée à ExperienceMemory, une catégorie contrôlée et une date murale valide. Le résultat ConservativeCategoryRecall contient :

- **Evidence par modalité** (visual_label ou sound_label) : nombre d'observations F4-A appuyées par les sources F1-C/F2-C toujours actives, nombre de sessions de fixture distinctes, dernière date, minimum/maximum des confiances **déclarées**. Les champs real_sensor_verified=false et independent_scenes_verified=0 empêchent toute interprétation physique.
- **Hypothèses de propriétés séparées** : le lecteur F4-A existant reste l'unique source. Les oppositions soft/hard, moving/stationary et playable/not_playable sont signalées, pas résolues. La source reste fictional_llm_hypothesis_only, jamais une photo certifiée ou un vrai conseil Qwen inscrit en mémoire.
- **Statut** : historical_mock_only, hypotheses_only ou unknown. Aucun statut n'autorise le moteur, ni une préférence physique. Les indicateurs motor_commands_issued, memory_writes, causal_effects_verified et verified_real_observations restent à zéro.
- **Budget** : parcourir au maximum 256 sources actives pour une catégorie, et refuser le bilan si une base altérée dépasse cette limite ; ne pas tronquer silencieusement des observations pour créer un faux total.

La fonction **n'écrit rien**, ne réactive pas M1-A, n'ouvre pas de socket robotd et ne déclenche aucun modèle local ou distant. **Limite de vocabulaire :** le dictionnaire passif F1-C actuel n'inclut pas encore la catégorie chaise (chair), bien que celle-ci soit disponible dans le pilote Qwen PC. C1 refuse cette valeur tant qu'une évolution de perception catégorielle F1 n'est pas étayée, plutôt que l'inventer. Une catégorie rapportée par les fixtures ne vaut ni validation visuelle basse Cat-A2b, ni connaissance d'un animal réel, ni preuve d'effet.

## 4. Tests et limites

Les fixtures testent : vide/unknown, répétitions au sein d'une session puis dans une seconde session, preuve de 0 scène indépendante, retrait F2-C et correction F4-A, altérations de catégorie/confiance/heure/statut, expiration, hypothèses contradictoires et rétractées, réouverture du même fichier SQLite, aucun nouvel écrivain ou table M1-B, paramètres invalides, base fermée, surcharge volontaire de 257 preuves et refus sans rapport partiel.

**Niveau de preuve attendu :** tests Python sur hôte en CI ; pas de Qwen, capteur, MuJoCo, robot réel, causalité, mémoire embarquée ou essai moteur. Le coût SQLite/WAL, CPU, RSS, chaleur et autonomie sur RK3566 reste inconnu ; avant portage, scripts/resource-audit.sh et audit OEM.

## 5. Lacune identifiée mais non corrigée dans C1

Le nettoyage F4-A supprime physiquement les hypothèses et leurs corrections à expiration. Après disparition de la ligne rétractée, la contrainte UNIQUE(category,property,value) ne suffit plus à empêcher la réintroduction de la même hypothèse erronée. Des corrections F2-C peuvent également disparaître avec des observations F1-C périmées. **C1 n'apporte aucune rétention durable de tombstone**, et ne prétend pas que les corrections sont inaltérables.

**C2 recommandé :** concevoir des marqueurs de rétraction strictement bornés aux catégories/propriétés fermées, avec migration/reprise testées, sans suppression aveugle des corrections ni croissance illimitée du fichier. **C3 ensuite :** évaluer le rappel sur des scènes réellement inédites avec/sans mémoire, sous l'autorité de Cat-A2b #78. SIM-E2 #101 et la réponse Pollen Robotics restent des sujets séparés.
