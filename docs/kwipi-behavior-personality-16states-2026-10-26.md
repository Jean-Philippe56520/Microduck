# Kwipi — personnalité et 16 états OEM : contrat d'intégration prudent

**Statut du lot :** nouvelle **vue de personnalité sur décisions fictives**, sans installation embarquée. L'objectif à long terme est une personnalité reconnaissable qui évolue lentement avec les observations et les conséquences *réellement constatées*. Aucun état humain/animal ressenti n'est revendiqué : « humeur » désigne un résumé de variables de décision et d'expression.

## 1. Audit réutiliser / adapter / créer

| Élément | Source et preuve | Décision |
| --- | --- | --- |
| Regard animé / bâillement / posture au repos | OEM épinglé `942e58e3...`, `robotd/src/idle_head.rs` ; présent dans les sources | **Réutiliser**, ne pas coder un second générateur de gestes |
| Sons et caresses | OEM `robotd/src/sound.rs`, `pet-detect` | **Réutiliser**, sans activation physique dans ce lot |
| 16 états historiques | OEM `docs/ideas/autonomous_behavior.md` ; M9 absent du daemon épinglé, état à revérifier | **Référencer** ; ne pas copier un ancien contrôleur |
| Proposition communautaire de cerveau | [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381), ouverte, documentation/expérimentation externe | **Comparer**, aucun code tiers importé |
| Motivations, sélection d'intentions, mémoire | `AutonomyBrain`, F2 `PassiveRhythm`, F1 `PassiveObservationJournal`, F2-C `PassiveLearning`, F4-C `MockSocialComposer`, une `ExperienceMemory` SQLite | **Réutiliser les mêmes instances et règles** |
| Vue de personnalité non exécutable | `behavior_personality.py` | **Créer un adaptateur en lecture seule**, car le dépôt n'avait pas de sortie commune reliant l'état F2/F4, les motivations et le rappel de catégorie |

Le code OEM est sous Apache-2.0 (licence vérifiée). Aucun code, modèle, média ou poids communautaire n'est repris. L'interface ne crée ni table SQLite ni nouvelle écriture, n'établit aucune identité d'instance et n'attribue aucun fait à Qwen.

## 2. Les 16 comportements historiques : statut individuel

Ces noms proviennent **du prototype historique** décrit par le constructeur, **pas** de seize commandes actuellement livrées.

| État historique | Intention / déclencheur envisagé | État de l'intégration Companion |
| --- | --- | --- |
| Chill | Rester calme, observer sans agir | **Description fictive** de F2 `idle` et F4 silence |
| LookAround | Attention / curiosité face à une observation | **Description fictive** de F2 `observe/inspect/listen` ou F4 regard ; aucun moteur |
| Wander | Découverte d'un espace | Différé : navigation, sol, ToF et sûreté non validés |
| TurnInPlace | Rechercher une direction | Différé : pas d'autorité motrice Companion |
| Zoomies | Élan de jeu | Différé : locomotion et sécurité, pas de hasard incontrôlé |
| Startle | Réaction à une nouveauté brusque | Différé : entrée sonore/visuelle réelle et inhibition nécessaires |
| Stretch | Étirement après repos | Différé : animation/skill OEM vérifié et sûr nécessaire |
| Ruffle | Petit mouvement de plumage simulé | Différé : animation OEM à auditer |
| Preen | Toilette | Différé : animation OEM à auditer |
| Sneeze | Éternuement expressif | Différé : sons/gestes OEM à auditer |
| Dance | Jeu musical | Différé : réutiliser musique et politiques OEM sans second moteur |
| GroundPick | Observer / ramasser au sol | Différé : contact, obstacle, sol sûr, compétence OEM |
| Nap | Fatigue et repos | **Description fictive** de F2 `rest` et F4 repos ; aucune économie d'énergie prouvée |
| BallPlay | Invitation au jeu | **Description fictive** de F4 `play_cue` ; ni frappe ni mouvement |
| Petted | Caresses | Différé : relier l'événement OEM, consentement et validation matérielle |
| Held | Robot tenu en main | Différé : détection de soulèvement OEM non validée, pas d'inférence sans capteur |

**Quatre** états ont un résumé *cognitif non exécuté* ; **douze** restent référencés et conditionnels. Ceci n'est **pas** un système complet à seize comportements opérationnels.

## 3. Contrat logiciel du premier lot

1. Le système existant décide d'abord via F2 (`PassiveIntent`) ou F4-C (`MockSocialPlan`). `AutonomyBrain.describe_behavior(...)` intervient **après**, ne déclenche aucune nouvelle décision et ne change ni le rythme, ni l'énergie simulée.
2. Il produit `BehaviorPortrait` avec état historique descriptif, tonalité affective simulée, motivation dominante, familiarité de **catégorie**, nombre borné d'observations historiques, biais d'attention existant, origine et motif. Aucune sortie motrice/sonore/PC/écriture.
3. Le même objet `ExperienceMemory` est obligatoire pour le cerveau, le journal et l'apprentissage facultatif ; référence `unknown` = identité non établie. Le rappel ne prouve jamais un animal ou un objet précis, la disponibilité d'un capteur ou la sécurité du sol.
4. Historique absent ou SQLite défaillante ⇒ description `Chill/quiet` avec familiarité `unavailable`, sans comportement fabriqué. Récupération d'une ancienne observation ⇒ **catégorie connue**, jamais action réelle ou souvenir d'une interaction physique.
5. Toute évolution future devra apprendre uniquement des conséquences enregistrées et vérifiables, après accord sur la source et la correction. Les `PassiveLearning` et `BehavioralMemory` actuels sont des expériences fictives, non des succès moteurs réels. Éviter double comptage et variations arbitraires.
6. Aucun mot-clé, appel réseau ou Qwen n'intervient ici. Le nom du robot reste **Kwipi**, activation « Hé Kwipi ! » uniquement prévue.

## 4. Portes suivantes

- **P-A (ce lot)** : catalogue 16/16, portrait cognitif quatre états, lecture mémoire F1/F2, motivations F2, gestes sociaux F4 descriptifs ; vérification des refus d'accès, réouvertures et effets de bord.
- **P-B** : tester une cohérence de caractère sur plusieurs *sessions fictives* ; séparer apprentissage d'attention vs expérience réalisée ; mesurer répétitions et dérives ; utiliser `BehavioralMemory` existante pour les conséquences autorisées plutôt que bâtir une autre mémoire.
- **P-C** : après maturité Cat-A2/vision/sons, préciser les signaux indépendants et les conditions d'apparition de Startle/Petted, sans présumer d'une identité ni agir physiquement.
- **P-D** : réévaluer l'OEM M9, l'API et les capacités de sécurité, puis adapter les comportements moteurs uniquement via `robotd`, en simulation contrôlée et enfin sur robot reçu et audité.
- **P-E** : mesurer RSS/CPU/thermique, mémoire et taux d'erreurs sur RK3566 ; tests de stabilité et présence enfants/animaux sous supervision.

**Vérification :** tests `tests/test_behavior_personality.py` + régression générale Python en CI de la PR ; déclarer distinctement les tests faits sur hôte, la simulation et toute validation robot. Ne pas présenter ce document comme validation matérielle.
