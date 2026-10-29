# DET-2 / PER-1 — répétitions d'objectif et engagement prudent F2

**Porte 0 préenregistrée le 29 octobre 2026 AVANT les modifications du comportement/tests. Base `main@2bfea46366254763b1567b614a2e79fbb0eb4aa7`.** Contrat F2 **fictionnel** et passif, sans robot connecté. `docs/plan-action.md` demeure l'autorité de chantier.

## 1. Manque observé, objectif et hypothèse

- **DET-1 actuel** : `MockGoalMemory.attention_focus()` ne donne un biais qu'à un objectif actif encore **sans lien EX1**. Après un premier lien, le biais disparaît mais `PassiveRhythm.tick` peut reproposer **la même catégorie** à la fin du cooldown, même lorsque aucune stratégie ou information nouvelle n'a été enregistrée. Pour Kwipi, cela n'est ni détermination utile ni apprentissage.
- **MEM-1 actuel** : `MockGoalMemory` stocke déjà objectifs, révisions, transitions, stratégies et références EX1 de fiction dans l'unique `ExperienceMemory`. Les états de but `suspended/abandoned/mock_closed` ne prouvent aucun résultat physique ; la rétractation interdit la résurrection du but.
- **PER-1 actuel** : F2 possède déjà repos avec deux seuils et coût d'activité simulé ; `MockBehaviorContinuity` PD2 produit déjà une inertie **descriptive, après F2**. Ne pas recopier ce système. Le manque résiduel est un coût d'engagement facultatif pour passer d'une décision d'inaction à une attention faible, **dans le même F2**.
- **Hypothèse mesurable** : une option conservatrice `guard_attempted_goals` retiendra les **intentions ciblant un but déjà tenté ou suspendu** jusqu'à un changement explicite de révision ; une reprise déclarée en fixture restera possible sur une **stratégie inédite** et ne sera proposée qu'une fois par révision et par processus. Une option `personality_pacing` réduira les transitions faibles depuis l'inaction, sans empêcher une attention très motivée, sans changer sécurité ni introduire un autre arbitre.

## 2. Comparateurs et critères fixés avant tests

- **A sans DET-2 (témoin)** : après un lien EX1 `observe_from_distance` et un nouveau `PassiveRead` frais de même catégorie, **une répétition `observe` est possible** une fois le cooldown expiré.
- **B avec DET-2** : sur le **même flux de snapshots factices**, la répétition est remplacée par `idle` (ou par une autre catégorie admissible), **même avec détermination à 1**, si le but actif a une tentative et aucune reprise prouvée ; un but `suspended` reste bloqué. Aucun signal de type `new_view` fourni seulement par un autre `PassiveRead` ne suffit.
- **Reprise contrôlée (fixture uniquement)** : transition MEM-1 `suspended → active` avec raison égale à `resume_when`, révision plus récente que le dernier lien, et **au moins une autre stratégie compatible non encore liée**. Prévoir **une seule proposition cognitive** de reprise par `(goal_id, revision)` et par processus, jamais une tentative physique. Une réouverture d'un autre processus peut refaire une proposition tant qu'aucun lien EX1 n'a été enregistré ; **ne jamais qualifier cela de quota durable**. Après un autre lien EX1 et épuisement des stratégies : `idle`.
- **PER-1 optionnel** : après `idle`, le **coût d'engagement fixe** peut conserver `idle` face à une motivation modérée ; sans option, la même nouvelle catégorie faible mène à `observe`. Une motivation forte doit conserver son droit à une **attention passive** sans effets. Repos F2 existant et PD2 descriptif inchangés.
- **Négatifs obligatoires** : source non fiable, horloge/période invalides, énergie faible, détermination élevée en contexte bloqué, mémoire corrompue, objectif rétracté/périmé, essais EX1 rétractés mais liens conservés, stratégie déjà utilisée, autre SQLite, absence de but avec gate activé, redémarrage, aucune écriture pendant l'arbitrage ni commande OEM/Qwen. **Critère d'arrêt :** zéro répétition du but ciblé sans changement déclaré ; zéro déblocage d'action ni faux succès ; les tests A/B et négatifs doivent passer. Sinon retour à DET-1/F2.

## 3. Revue OEM et décision réutiliser / adapter / créer

| Composant | Décision | Justification |
| --- | --- | --- |
| `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `robotd` 50 Hz, `mediad` et `duck-detect` | Conserver | Seul `robotd` commande moteurs et arrêts ; pas de permission moteur issue de F2/EX1 |
| `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` | Conserver | Simulation MuJoCo non équivalente à robot réel ; SIM-E2 non résolue |
| OEM main `a360b384`, RL main `bae39f59` ; OEM #381, #414, #450 ouvertes au 29/10 | Observer, ne pas mettre à jour | Aucun contrat livré sur la répétition des objectifs fictifs Compagnon, aucune API motoriste créée |
| `MockGoalMemory`, liens EX1, `ExperienceMemory` | Adapter **lecture seule** (API de candidature retenue) | Les tables et preuves existantes suffisent ; aucun deuxième writer ou champ SQLite |
| `AutonomyBrain.propose_balanced_passive`, `PassiveRhythm.tick` | Adapter **optionnellement** | Une seule voie d'arbitrage, F2-A et tous cooldowns/sécurités d'abord |
| `behavior_personality` + PD2 `MockBehaviorContinuity` | Réutiliser sans deuxième humeur | Affect descriptif post-décision déjà existant ; pas de nouveau personnage/contrôleur |
| QuackNav, microduck-brain, Twin, Quacksat, Smartulf, quack-control | Références seulement | Pas de dépendance/migration nécessaire pour ce lot PC-fixtures |

## 4. Limites et retour arrière

L'inscription d'un lien EX1, même `mock_executed`, ne signifie pas qu'un capteur a constaté un échec moteur. La reprise `new_view` est **une transition de fiction déclarée**, jamais une preuve du nouvel angle physique, de succès ou de sécurité. Les engagements `rest` ne restaurent pas une batterie ; l'inertie PD2 n'est pas une émotion ni une expression OEM chargée. Les futures observabilité/effets moteurs exigent audit OEM puis robot.

**Retour arrière :** options désactivées par défaut ; anciens DET-1, F2 et PD2 inchangés. Écarter les deux options pour le comportement historique. Aucun schéma, poids, réseau, média privé, Qwen, moteur ou nouvelle dépendance.

## Résultats mesurés et décision (29 octobre 2026)

**Mesure de fonctionnement réelle sur code et fixtures PC** : [Python CI #40903201395](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40903201395), commit `9e678db1f96544020c9fe6db294d86635054db88`, **1 785 tests exécutés, 6 ignorés, 0 échec**, dont **10 nouveaux tests DET-2/PER-1** réussis. Pas de capteur réel ni inférence Qwen, pas d'acte/effet moteur. L'exécution est celle d'un runner Linux hôte, aucune performance thermique/RSS RK3566 mesurée.

**A/B préenregistrés sur la même scène fictive** : avec un objectif `observe_category/dog` actif ayant un lien EX1 initial, DET-1/F2 témoin peut reproposer `observe dog` (**1/1**), alors que DET-2 optionnel retourne `idle` (**0/1** répétition de cette catégorie). Après la suspension, `idle` ; après `suspended → active` déclaré avec `new_view` et une deuxième stratégie `observe_over_time` inutilisée, **une seule nouvelle proposition cognitive dans le même processus** ; à la prochaine observation fraîche, `idle`. Si les deux stratégies sont liées, aucune nouvelle proposition. Le lien EX1 rétracté ne redevient pas une preuve de nouveauté, un but rétracté ne fournit plus de biais et une autre catégorie sûre reste disponible. Aucun changement de la SQLite pendant F2. Les sources obsolètes/non fiables et une table corrompue conduisent à l'inaction.

**PER-1** : avec même lecture, mêmes motivations modestes et un cycle d'inaction précédent, F2 sans option propose une attention `observe ball` (**1/1**), et F2 avec coût d'engagement fixe `0,12` reste `idle` (**0/1**). Avec curiosité/jeu élevés, l'option propose toujours une attention passive. Le repos avec hystérésis et le portrait PD2 (`Chill`, `Nap`) sont **réutilisés**, pas remplacés par un nouvel état émotionnel ni une expression constructeur. Le coût est arbitraire **pour fixtures** et ne doit pas être calibré sur ces mêmes scénarios pour un robot.

**Limite positive volontairement exposée par un test** : après redémarrage, l'historique EX1 et le blocage d'un but déjà tenté restent dans l'unique SQLite. Mais si `suspended → active` avait autorisé une proposition nouvelle **non enregistrée en EX1**, la mémoire ne contient pas de reçu de consommation : **un nouveau processus peut proposer une nouvelle fois cette reprise**. Le compteur anti-boucle est strictement **local au processus**. C'est acceptable pour examiner des intentions de fixtures, **pas** comme quota d'essais physiques ; une future intégration devrait exiger un reçu durable dans la mémoire existante et des effets indépendants avant chaque action OEM. Aucune requalification en autonomie, en détermination physique ou en apprentissage réel.

**Décision** : `test_logiciel_seul` ; le garde facultatif réduit la répétition de propositions fictives et rend le repos/engagement plus cohérents en F2. Ne pas brancher la reprise sur un geste OEM, une catégorie douteuse ou Qwen. Ne pas étendre artificiellement les fixtures pour faire croire à un gain inter-scènes. Le prochain jalon indépendant réellement mesurable est E2E-1 sur scènes distinctes quand des données et un témoin adaptés sont présents, ou QW-1 sur PC avec consentement et un test prospectif de valeur, sans transformer le texte LLM en fait.

**Ressources et retour arrière** : lecture bornée à `MAX_GOALS=32` et `MAX_LINKS_PER_GOAL=8` liens EX1, sans nouvelle table ; pas d'exécution sur RAM/NPU/thermique robot ; désactiver `guard_attempted_goals` et `personality_pacing` pour retrouver DET-1/F2 d'origine, sans migration ni changement OEM.
