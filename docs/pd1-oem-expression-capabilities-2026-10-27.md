# PD1 — Inventaire de disponibilité des seize états et expressions OEM

**Date : 27 octobre 2026. Statut : candidat logiciel, uniquement en lecture/description sur fixtures, aucune exécution physique.** [PD0](pd0-behavior-states-selective-qwen-2026-10-27.md) est la cible. Le [plan directeur](plan-action.md) fait foi : Cat-A2b (captures authentiques à hauteur de Kwipi) reste le prochain jalon de perception. Le robot n'est pas disponible pour un test.

## 1. Périmètre effectivement développé

Un **inventaire déclaratif** `BehaviorExpressionCapability` a été ajouté **dans le module P-A existant** [`behavior_personality.py`](../microduck_companion/behavior_personality.py), et non dans un second décideur. Les fonctions :
- `expression_capability_catalog()` : renvoie **exactement** les 16 noms existants dans `HISTORICAL_OEM_STATES`, avec le statut P-A `mock_description_only` pour les **quatre états descriptifs** et `requires_oem_m9_or_sensor_review` pour les douze autres.
- `expression_capability_for(state)` : renvoie un constat statique typé ou refuse un nom inconnu, une fausse provenance et une prétention d'exécution.
- `inspect_expression_capability(portrait, hint=None)` : **après** l'arbitrage F2/F4, interprète le portrait `BehaviorPortrait` déjà calculé et éventuellement un `MockExpressionHint` P-C déjà validé. **Ne choisit aucun geste**, ne rappelle pas le cerveau, ne lit pas l'OEM, n'appelle pas de modèle, ne stocke pas de mémoire.

Chaque résultat impose `named_state_command_available=False`, `expression_executed=False`, `hardware_verified=False`, `physical_execution_authorized=False`, zéro commande moteur, son, PC et zéro écriture SQLite. Ces invariants sont validés à la construction, avec rejet des preuves falsifiées.

**Ne pas confondre preuve dans les sources et équipement réel :** `oem_expression_evidence` est une indication **statique** fondée sur la révision épinglée `942e58e3`. Elle ne prouve pas qu'une expression a effectivement été jouée ni que la capacité soit exposée en JSON-RPC aux applications.

## 2. Matrice exhaustive (catalogue historique, pas 16 commandes OEM)

| Nom OEM historique | Statut P-A de Companion | Expression partielle existante dans l'OEM épinglé | Commande d'état spécifique vérifiée |
| --- | --- | --- | --- |
| Chill | Descriptif fictif | **Regards / respiration de fond**, possédés par `IdleHead` | **Non** |
| LookAround | Descriptif fictif | **Regards autonomes au repos**, pas de regard ciblé vers l'objet détecté | **Non** |
| Wander | Historique, à revoir | Aucune correspondance portative attestée | **Non** |
| TurnInPlace | Historique, à revoir | Aucune correspondance de l'**état** portée et attestée ; ne présume pas l'absence d'autres commandes de rotation OEM | **Non** |
| Zoomies | Historique, à revoir | Aucune compétence autonome d'état attestée | **Non** |
| Startle | Historique, à revoir | La sentinelle OEM journalise les bruits ; la réponse réflexe n'est **pas** portée | **Non** |
| Stretch | Historique, à revoir | Aucune compétence d'état attestée | **Non** |
| Ruffle | Historique, à revoir | Aucune compétence d'état attestée | **Non** |
| Preen | Historique, à revoir | Aucune compétence d'état attestée | **Non** |
| Sneeze | Historique, à revoir | Aucune compétence d'état attestée | **Non** |
| Dance | Historique, à revoir | Éventuels sons/politiques OEM à inventorier dans PD5 ; **pas** de commande de l'état historique attestée | **Non** |
| GroundPick | Historique, à revoir | Manipulation, contact, sol et sécurité non validés | **Non** |
| Nap | Descriptif fictif | **Bâillement silencieux pendant l'idle**, pas de mode Nap complet ni de consommation batterie réduite prouvée | **Non** |
| BallPlay | Descriptif fictif | P-A décrit seulement un `play_cue` ; aucun jeu de balle physique confirmé | **Non** |
| Petted | Historique, à revoir | **`coo` conditionnel**, déjà joué par `robotd` à `PettingEvent::Start` si non tombé/occupé ; pas de second son Companion | **Non** |
| Held | Historique, à revoir | Historique de détection de prise en main **déprécié**, pas de signal validé pour une réaction | **Non** |

**Comptage exact : quatre correspondances de source partielles** (`Chill`, `LookAround`, `Nap`, `Petted`) ; **douze états sans correspondance partielle qualifiée dans cet inventaire**. Parmi ces quatre, trois sont déjà **descriptions P-A** et `Petted` reste l'événement OEM P-C. `BallPlay` est le **quatrième descriptif P-A**, mais ne possède aucune expression physique attestée. Ce tableau n'attribue donc pas « 4/16 fonctionnalités implémentées » au robot.

## 3. Sources et réutilisation vérifiées

| Référence | Décision |
| --- | --- |
| [OEM `942e58e3` — design du comportement autonome](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md) | Les seize noms proviennent **du projet historique non porté**, et non d'une liste de commandes JSON-RPC livrées ; **réutiliser les noms** seulement. |
| [`robotd/src/idle_head.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/idle_head.rs) | `IdleHead` possède les regards, inclinaisons, dérive et bâillements silencieux. Réutiliser cet existant **sans le reconstruire** et sans assimiler chaque sous-geste à un état complet. |
| [`robotd/src/main.rs` — PettingEvent](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/main.rs#L2604-L2628) et `pet-detect/src/worker.rs` | `coo` sous conditions appartient à `robotd`. P-C indique `oem_owned`, mais l'indication ne **joue aucun son**. Bruit ambiant `SoundEvent::Noise/Voice` : journal uniquement, pas de `Startle`. |
| [`sounds/src/personality.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/sounds/src/personality.rs) | La personnalité vocale constructeur est déjà stable selon une graine. **Ne pas développer de double personnage vocal**. |
| [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) et [#414](https://github.com/pollen-robotics/microduck/pull/414) | **Ouvertes/non fusionnées le 27/10/2026**. #381 est une proposition de design du cerveau ; #414 cartographie n'autorise ni navigation ni contact. Rester en veille pour PD5. |
| [P-A `behavior_personality.py`](../microduck_companion/behavior_personality.py), [P-C `oem_expression_hints.py`](../microduck_companion/oem_expression_hints.py) | **Adapter un module existant**, réutiliser `HISTORICAL_OEM_STATES`, `BehaviorPortrait`, `MockExpressionHint` ; ne pas créer un second magasin ou arbitre. |
| F2/F4/EX1–EX3/F5 et [registre communautaire C3](community-reference-registry-2026-10-26.md) | Ne pas écrire d'autre SQLite, ne pas adopter de cerveau externe QuackNav/GC/Smartulf ou télécommande `quack-control`, ni ajouter de poids/son/média. Qwen F5-C reste totalement distinct. Aucun code/média tiers copié, licence OEM Apache-2.0 déjà identifiée. |

## 4. Tests, exigences et limites

[`tests/test_pd1_oem_expression_capabilities.py`](../tests/test_pd1_oem_expression_capabilities.py) comprend **17 nouveaux cas** : ordre et unicité des 16 noms, deux vues du statut P-A, quatre indices OEM partiels, douze états sans indice, liens sourcés, interprétation `Chill/Nap/Petted/Startle/Voice`, refus `STOP`/chute/activité/absence d'opt-in, indice périmé, incompatibilité portrait→hint, nom ou source usurpé, faux drapeaux de permission/commandes et égalité du schéma et du nombre d'écritures SQLite après des relectures répétées, puis réouverture.

**Aucune réponse de Qwen, aucune RPC, aucun appel `voice.play`, aucun mouvement de tête ni capture n'est produit par PD1.** Même `oem_expression_evidence='conditional_oem_petting_coo'` ne garantit pas qu'un vrai son ait été émis. La CI hôte doit réussir avant toute fusion ; **aucune preuve sur RK3566, MuJoCo ou appareil physique** n'en découle.

## 5. Prochaines étapes

1. **Cat-A2b reste prioritaire** pour les vraies images à hauteur basse et les confusions `unknown`.
2. **PD2** : continuité des motivations/affects sans seconde mémoire et sans transitions arbitraires, sur fixtures ; ne pas augmenter la mémoire embarquée sans mesure.
3. **PD3** : qualifier uniquement les besoins sémantiques persistants et non privés pour **F5 existant** ; ni `Startle` immédiat ni chaque regard déclenchent Qwen. Le prompt F5 actuel ne voit **aucune image** et répond en laboratoire `unknown`.
4. **PD5** : au moment du portage, auditer l'inventaire exact des commandes `robotd` et animations offertes, recontrôler PR #381/#414 et l'OEM épinglé, simuler, puis autoriser seulement des intentions filtrées ; **aucun second décideur moteur**.
5. **PD6–PD7** : `scripts/resource-audit.sh`, mesures RSS/CPU/thermique/SQLite/WAL/latence moteurs, observations sur robot réel sous supervision, rapport par état « annoncé / émis / confirmé / refusé ». Une description ou un accusé de commande seul ne prouve pas une exécution.

**Décision :** ne pas revendiquer « les 16 humeurs sont jouées ». PD1 établit une **base de vérification traçable** pour savoir quelles expressions réutiliser, sans créer une animation concurrente. Aucun contrôle moteur, son ou Qwen n'est ajouté.
