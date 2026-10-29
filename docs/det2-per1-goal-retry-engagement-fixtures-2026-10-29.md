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

## 5. Résultats

En attente de tests ciblés et suite Python/N1. Ne pas transformer `test_logiciel_seul` en capacité autonome réellement démontrée.
