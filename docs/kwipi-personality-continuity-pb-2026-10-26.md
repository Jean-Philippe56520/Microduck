# P-B — Continuité de personnalité sur souvenirs et conséquences fictives

**Date : 26 octobre 2026.** Kwipi. **Statut : code expérimental sur PC/fixtures, aucun robot physique.** P-B complète [P-A (16 états historiques)](kwipi-behavior-personality-16states-2026-10-26.md), sans activer les douze états OEM non portés. La priorité Cat-A2 de perception par catégories reste inchangée.

## 1. Matrice de réutilisation vérifiée

| Propriété | Existant revu | P-B : réutiliser/adapter/créer |
| --- | --- | --- |
| Comportements/animations/sûreté | OEM épinglé `942e58e3aa6dbb28e7037203fff11866122c7567`, `robotd/idle_head.rs`, `robotd/sound.rs`, projet d'autonomie [16 états OEM](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md) | **Réutiliser plus tard** l'API officielle ; aucune commande dans P-B |
| Futur cerveau autonome | OEM M9 non porté ; [PR #381](https://github.com/pollen-robotics/microduck/pull/381) ouverte, proposition communautaire de design non livrée | Veille uniquement. **Ne pas copier** le cerveau PR, créer un concurrent ni ouvrir l'arbitrage moteur |
| Variante communautaire | [GC-RENCAO `life.py`](https://github.com/GC-RENCAO/microduck-companion/blob/main/life.py) : logique de caméra/personnalité/mouvement propre au projet tiers | Référence non approuvée, aucun import, aucun apprentissage de ses actions |
| Intention et rythme | `AutonomyBrain`, `PassiveRhythm`, `PassiveIntent` F2 | **Adapter**, paramètre facultatif `behavioral=` ; F2 reste décideur, aucun second ordonnanceur |
| Mémoire catégories | `PassiveObservationJournal`, `PassiveLearning` F1/F2-C | **Réutiliser** : biais faible d'attention, pas un résultat d'action |
| Conséquences fictives | `BehavioralMemory` F4-A et `MockCycleRunner` P2a | **Réutiliser directement** `summary()` avec vérification du suivi explicite et de la provenance |
| Présentation d'état | `behavior_personality.py`, `AutonomyBrain.describe_behavior` P-A | **Étendre** avec un résumé facultatif, stable, révocable et traçable sur la même SQLite |

**Aucun module de stockage supplémentaire**, nouveau schéma SQL, modèle LLM, poids, image ou média. Les modules OEM restent intacts. La licence Apache-2.0 du constructeur a été consultée ; aucun code tiers n'est repris.

## 2. Propriétés exactes de P-B

- **Deux mémoires d'usage, un seul stockage :** F2-C compte la nouveauté de *catégorie* comme priorité d'attention (`attention_bias`) ; F4-A agrège **uniquement** des résultats fictifs explicitement constatés après `inspect_object` (`outcome_bias`). Les deux valeurs ne sont **ni sommées dans une seule mémoire ni présentées comme une expérience physique**.
- **Personnalité stable en lecture seule :** `AutonomyBrain.describe_behavior(..., behavioral=existing_f4a)` expose l'état P-A, le biais de conséquence F4-A, les comptes de réponses fictives positives/négatives et une tendance `neutral`, `inspection_encouraged` ou `inspection_reserved`. Une seule conséquence ne crée **pas** d'habitude ; au moins deux retours concordants sont nécessaires, et l'amplitude est bornée à **±0,12**.
- **Sans duplication :** même connexion `ExperienceMemory` pour cerveau, journal, F2-C facultatif et F4-A facultatif. Pas de table « personnalité », pas de stockage brut, pas de sauvegarde d'identifiant de suivi dans le portrait.
- **Effet sur une décision :** F2-B peut recevoir `behavioral=` en opt-in. Seul le score de l'intention *cognitive non exécutée* `inspect` reçoit le petit biais de F4-A, au maximum ±0,12. L'ordre des décisions et les protections existants restent inchangés si l'option est absente. `PassiveRhythm._score` reste inchangé pour les tests de parité Rust F6-B. Une mémoire ne crée jamais de nouvelle perception ni de certificat de sol.
- **Correction et oubli :** toute correction d'un résultat F4-A à la source via `retract()` recalcule indirectement la tendance par `summary()`. Les données ont la rétention F4-A existante de **14 jours**, au plus **256** enregistrements ; après expiration, le profil est neutre. La mémoire de catégorie F1-C reste indépendante.
- **Dégradation sûre :** source fictive manquante/non fiable ⇒ F2 inactif ; mauvaise origine SQLite ⇒ refus ; historique F4-A inaccessible/incohérent ⇒ `idle` sans dépense d'énergie simulée ou portrait `Chill/quiet/unavailable`. Aucune hypothèse LLM ou intention non exécutée ne devient une récompense.

## 3. Limitations explicites

L'ancienne famille `P2a` exécute seulement une **simulation de retour cognitif sur fixture** ; elle ne prouve pas le succès d'un geste réel. La préférence `inspect_object` de P2a appliquée avec parcimonie à une proposition `inspect` de F2 est **une expérimentation de transfert entre deux bancs fictifs**, pas une aptitude robot approuvée. Rien dans P-B ne confirme un objet individuel, un humain, un animal, une émotion ressentie ou une réaction observable. Les 16 états ne sont pas des commandes embarquées ; P-A en décrit toujours quatre sur source fictive.

La personnalité persistante de P-B est **une tendance bornée dérivée de l'historique**, pas la persistance des cinq valeurs de motivation après redémarrage. La persistance de ces motivations et la continuité de l'expression nécessiteraient une évolution dédiée, à valider sans duplication de M9 et sans écriture spéculative de la réussite des actions.

## 4. Contrôles et prochaines étapes

Les scénarios `tests/test_personality_continuity.py` vérifient : zéro retour, un retour insuffisant, deux résultats positifs/négatifs, correction et réversibilité, expiration, redémarrage avec la même SQLite, opt-in F2 limité, source falsifiée, historique inaccessible, refus de mélanger deux bases, champs d'exécution falsifiés et absence d'effets de bord. La CI hôte et les autres tests de régression déterminent le statut final ; **aucune simulation MuJoCo, mesure sur RK3566 ou robot physique**.

Ensuite : compléter Cat-A2 ; établir des conditions d'expression affective stables **à partir de véritables observations autorisées** après réception du robot, en séparant interactions réellement effectuées et intentions seulement proposées ; revoir le constructeur M9/PR #381 avant tout branchement actionneur. Les états Startle/Petted/Held exigent une provenance et un capteur vérifiés, notamment Held dont le dispositif historique est déprécié.
