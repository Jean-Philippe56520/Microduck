# N2 — Nettoyage du chemin cognitif courant, sans second cerveau

**Date :** 28 octobre 2026. **Nature :** modification ciblée des imports Python, tests sur fixtures/PC, **aucune nouvelle capacité robot**. [`docs/plan-action.md`](plan-action.md) reste l'autorité de priorisation ; N2 ne réouvre pas SIM-E2 et ne remplace pas Cat-A2b/C3-B.

## Porte OEM-first, observation et hypothèse

- Base Companion vérifiée : `main@2ab3e77ec8359a6f16c50bd9a37133bb46754d86`, PR [#129](https://github.com/Jean-Philippe56520/Microduck/pull/129) fusionnée. Sous-modules restés épinglés à `microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, sans mouvement ni reconfiguration.
- Sources OEM relues : [architecture du daemon](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/architecture.md), [configuration moteur](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/deploy/robotd.toml), [idées de cerveau M9](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md) et [robotctl](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md). **`robotd` seul commande les moteurs à 50 Hz** ; M9 demeure absent du daemon à ce SHA. [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) et [#450](https://github.com/pollen-robotics/microduck/pull/450) toujours ouvertes/non fusionnées lors de la revue. Le robot physique est absent, donc sa configuration effectivement chargée est inconnue.
- Réemploi pertinent communautaire : [registre C3](community-reference-registry-2026-10-26.md) — QuackNav/GC-RENCAO et design #381 ne fournissent aucune bibliothèque validée qui justifie de créer ou importer un second arbitre. Aucun code tiers importé.
- **Observation mesurée en processus hôte isolé avant changement :** `import microduck_companion` charge **9** modules Python Companion ; la clôture **statique** de N1b en contient **19** (les imports locaux et `TYPE_CHECKING` sont comptés). Au premier `AutonomyBrain.propose_balanced_passive` sur une source de fixture indisponible, Python importe le laboratoire `mock_cycles` via `behavioral_memory`, alors qu'aucune preuve P2a n'est consultée. Une description de `PassiveIntent('idle', ...)` importe `mock_social_cues` via `behavior_personality`, même sans plan social.
- **Hypothèse falsifiable :** décaler les imports de classes `MockCycleRunner` et `MockSocialPlan` vers les branches qui en ont besoin laisse le choix d'attention et les garde-fous inchangés tout en supprimant ces chargements **inutiles** dans la voie cognitive normale.

## Réutiliser / adapter / créer

| Responsabilité | Propriétaire existant | Décision |
| --- | --- | --- |
| Intention passive, cadence, repos fictif | `AutonomyBrain` → `PassiveRhythm` → `propose_passive_intention` (F2) | **Réutiliser**, pas de nouveau service ni deuxième arbitre |
| Mémoire de catégories et conséquences fictives | Une SQLite `ExperienceMemory`, journaux F1/F4/EX | **Réutiliser** ; provenance `mock` stricte, pas de changement SQL, source ou TTL |
| Historique de cycles P2a | `MockCycleRunner` | **Adapter uniquement l'instant d'import** dans `BehavioralMemory.record` ; le contrôle `isinstance` reste strict |
| Social et personnalité | `MockSocialPlan`, `BehaviorPortrait`, `MockSocialComposer` | **Adapter uniquement l'import** de `MockSocialPlan` dans `_interpret`, après la branche `PassiveIntent` ; ne pas reproduire le compositeur |
| Expression OEM, moteurs et sécurité | `robotd`, `IdleHead`, `pet-detect`, `mediad`, `tofd` | **Ne pas créer ni modifier** de contrôleur, consommateur audio ou réseau ; documenter M9 non livré |
| Qwen PC optionnel | F5 et les garde-fous existants | **Inchangé** ; hypothèse jamais action/fait/récompense |

## Preuves ciblées et cas négatifs

**Après changement, sur les mêmes fixtures locales :** après `propose_balanced_passive` puis `describe_behavior` avec une intention `idle`, **0 module `microduck_companion.mock_*` chargé**, contre deux au total avant ; `sim_*` reste absent. L'intention reste `idle`, le portrait `Chill`, zéro moteur et aucune autorisation physique. Les **4 tests N2 locaux** couvrent :

1. processus Python `-I -B` neuf : attention passive et description de personnalité n'importent ni moteurs simulés ni laboratoires fictifs ;
2. `BehavioralMemory.record` refuse un faux runner et accepte un vrai `MockCycleRunner` uniquement pour vérifier une ligne P2a existante ; absence de conséquence => aucune promotion ;
3. le `MockSocialPlan` explicite reste descriptible, mais un plan déclarant `executed=True` ou un faux objet est rejeté ;
4. un journal et un cerveau sur **deux connexions SQLite différentes** sont refusés.

`python -m unittest discover -s tests -p 'test_n2_cognitive_lazy_imports.py' -v` : **4/4 localement sur copie du code `main` de la PR #129**, avec les deux remplacements exacts. Ce résultat PC local est distinct de la CI de PR, qui doit être vérifiée avant fusion.

## Limites et retour arrière

- **Pas de réduction du nombre de fichiers distribués** : le wheel historique demeure à 121 modules et la clôture AST de N1b peut rester à 19 modules parce que le parseur recense les imports, même locaux.
- Le gain concerne la **dépendance chargée au moment de l'utilisation** de F2/P-A ; **aucune mesure de RAM, RSS, CPU, vitesse ou chaleur n'est extrapolable au RK3566**. Aucune preuve de progrès d'autonomie, de cognition réelle, de nouveau mouvement ou de causalité n'est revendiquée.
- La compatibilité des méthodes `AutonomyBrain.propose_balanced_passive`, `describe_behavior`, `BehavioralMemory.record` et le contrôle de provenance sont préservés. Les classes restent accessibles par leurs modules propriétaires `mock_cycles` et `mock_social_cues`.
- **Échec / arrêt :** test de non-import rouge, type `MockSocialPlan` mal reconnu, faux historique accepté, divergence de SQLite acceptée, ou CI complète rouge → PR non fusionnée. **Retour arrière :** abandon de la branche ou revert du commit ciblé ; aucune migration ni changement OEM à restaurer.

## Décision de suite

**Conserver F2 comme seul prototype d'arbitrage cognitif, P-A/PD comme descriptions *après* intention ; conserver P2a/F4-C comme outils de laboratoire à demande explicite.** Ne pas inventer une deuxième boucle de cerveau. Prochaine étude utile : N3, table d'écrivains de l'unique `ExperienceMemory`, provenance/corrections/quotas, puis sélection raisonnée de la voie embarquable et contrôle des imports dynamiques. M9 sera re-comparé **seulement si une API OEM réellement livrée existe**.
