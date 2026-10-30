# SIM-S1 — ablation passive de l'attention sur les mêmes télémétries OEM simulées

**Date :** 30/10/2026. **Statut :** candidat sur branche, tests et CI à contrôler. Aucun robot, aucun mouvement autonome, aucune caméra ni Qwen exécutés par ce lot.

## Objectif, écart et arrêt fixés avant contrôle

Objectif : déterminer si un souvenir vérifiable de l'état de batterie simulée modifie une attention descriptive de Kwipi, par comparaison avec la **même observation actuelle sans contexte historique**. Ce gain est très limité : une attention descriptive différente n'est ni une meilleure décision physique, ni un apprentissage causal.

Écart : X2-C valide 6 cycles OEM `robotd/tofd`, une SQLite unique et des références historiques correctes, mais son vérificateur contrôlait les valeurs des champs `attention` sans recalculer leur conformité. Il ne rapportait pas de contrefactuel sans mémoire. Réutilisation : `PassiveSimCycleRunner`, `AutonomyBrain.consider_simulator_status`, `ExperienceMemory`, `sim_x2c_acceptance.validate_acceptance` et les six cycles déjà produits par le simulateur épinglé. Aucune nouvelle DB, classe de décision, table, service, dépendance ou commande.

**Témoin préannoncé :** sur chaque cycle source cohérent, le courant `battery_pct` vaut `rest` si ≤15 %, `idle` sinon, et `abstain` si inconnu. La variante avec mémoire ne peut donner `observe_status` que sur une transition précédente `low_to_normal` prouvée par le lien historique validé. Ce contrat correspond aux **motivations par défaut** de X2-C ; ce n'est pas un arbitre universel. L'écart est calculé sur les six mêmes lignes persistées (lecture SQLite strictement seule), pas avec un deuxième scénario ou une seconde exécution OEM.

**Succès du lot :** la vérification accepte les données originales cohérentes ; compare exactement six paires ; détecte et refuse les faux `observe_status` ajoutés symétriquement au JSON et à la SQLite ; refuse une transition valide occultée ; garde 0 moteur, 0 effet, 0 préférence ; préserve toutes les CI de base. Un cas fixture positif contient une transition basse→normale ; les six cycles OEM X2-C peuvent **ne pas** en contenir : 0 différence est une réponse légitime, pas une erreur de CI.

**Arrêt :** une différence `attention` n'autorise ni apprentissage, ni mouvement, ni affirmation d'amélioration sémantique. Si les schémas / motivations OEM diffèrent, arrêter plutôt que reconstituer ou forcer des données. Sans accès au runtime OEM, déclarer l'essai réel de simulateur « en attente » : les tests de fixtures ne le remplacent pas.

## Résultats et provenance

La PR de ce lot ajoute uniquement l'analyse `attention_ablation` au vérificateur X2-C et trois tests de fixtures. Elle ne modifie pas `robotd`, `mediad`, `tofd`, les sous-modules, ONNX, `PassiveSimCycleRunner`, les schémas SQLite ni les données privées.

Le nombre de `memory_dependent_differences` **mesure une différence de suggestion cognitive**, pas sa qualité, son effet ou un avantage sur le terrain. Les champs `semantic_gain_verified=false` et `motor_effect_verified=false` restent faux. X2-C doit continuer de provenir des démons MuJoCo lancés par CI, pas de rapports fabriqués ; la voie `F1→F2` sur catégories reste séparée (E2E-1A, fixtures exclusivement). En l'absence de données d'objet catégorisées authentifiées dans l'IPC X2-C, aucun faux objet n'est ajouté pour simuler artificiellement la découverte.

## Matrice de réemploi / phases suivantes

- **S0** : épingles immuables `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` ; contrôles CI de référence.
- **S1** : réutiliser X2-C et analyser la mémoire en lecture seule ; aucun nouveau pilote ou arbitre.
- **S2 (parallèle)** : reprise du jalon Cat-A2b/PER-OEM sur vues basses indépendantes. La PR SIM-VIS-A1 #181 reste brouillon : `mediad` non validé sur runner x86. Ne pas bricoler un second flux de production.
- **S3–S5** : scénarios multi-vues, Qwen PC facultatif et effets OEM indépendants uniquement après preuves propres ; SIM-E2 #101 toujours ouvert ; ne jamais confondre `robot.do accepted` et effet vérifié.
- **Navigation** : OEM mapd #414 non fusionnée ; QuackNav tiers référence seulement, sans portage. Ressources RK3566/NPU et robot réel non mesurés.

**Reprise :** contrôler SHA/CI de la PR, puis seulement conclure « testé fixtures » / « simulé OEM » selon les traces effectivement obtenues.
