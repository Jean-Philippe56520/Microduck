# X2-B — Attention cognitive passive et contexte simulé en SQLite (27 octobre 2026)

**Statut : codé dans la branche X2-B, validation CI à confirmer ; tests de fixtures et sur hôte uniquement.** Ce lot prépare une future acceptation MuJoCo X2-C. L'essai P2b du 25 octobre avait déjà démontré **six cycles cohérents** (deux sessions de trois) sur les vrais démons du simulateur, mais tous en `halt`, sans conséquences.

## Audit et décision réutiliser / adapter / créer

- **Révisions OEM épinglées dans le registre R0/R1.5 :** `upstream/microduck` `942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl` `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` (pointeurs effectivement résolus à confirmer par `git submodule status` en checkout). Version X2-A [PR #84](https://github.com/Jean-Philippe56520/Microduck/pull/84) fusionnée : les sockets `robotd` et `tofd` ne portent qu'une **provenance déclarée**, pas une authentification robot.
- **OEM en cours de proposition :** [#381](https://github.com/pollen-robotics/microduck/pull/381) (cerveau), [#414](https://github.com/pollen-robotics/microduck/pull/414) (maploc/mapd) **ouvertes et non fusionnées** à la revue du 27 octobre ; aucune fonctionnalité de ces PR n'est présumée livrée.
- **Réutiliser** : `AutonomyBrain` et ses cinq motivations, `SimulatorTelemetry.assess` X2-A, `PassiveSimCycleRunner` P2b, `PerceptionSnapshot`, la **même instance** `ExperienceMemory` et la table `sim_passive_cycles`, les tests existants. La seule observation de type PerceptionEvent produite par le pont reste, éventuellement, la **batterie déclarée**.
- **Adapter** : ajout d'une **méthode pure** de proposition d'attention à `AutonomyBrain` (`consider_simulator_status`) et de trois champs à l'enregistrement P2b existant. **Pas** de second cerveau, stockage, pilote, démon, contrôleur de mouvement, classification ToF, source `sensor`, catégorie fictive OEM ou moteur de récompense.
- **Créer** : tests négatifs et document de traçabilité seulement.
- **Communauté** : [registre C3](community-reference-registry-2026-10-26.md), notamment QuackNav/microduck-brain (contrôle de mouvements et navigation), microduck-twin (audio simulé), lab/studio. Aucun code, poids, licence ou contrôleur externe intégré : le périmètre X2-B n'a besoin ni de navigateurs tiers ni d'un pipeline voix/vidéo.

## Cycle de cognition réellement traité

```text
robotd + tofd (simulateur déclaré, lecture seule)
  -> X2-A: cohérence, fraîcheur, santé, chute, cadences, ToF 8x8
  -> P2b: snapshot batterie seulement -> AutonomyBrain.choose_from_snapshot
  -> rappel de la dernière ligne sim_passive_cycles (même SQLite)
  -> vérification continuité de la session, du temps et des séquences OEM
  -> consider_simulator_status : abstain / idle / rest / observe_status
  -> INSERT dans sim_passive_cycles : intention + statut + comparaison
  -> cycle suivant (sans autorité motrice, sans récompense)
```

**Limite cruciale :** `observe_status` désigne seulement le constat d'une transition de batterie faible vers normale ; ce n'est pas une animation `LookAround`, une observation caméra, une recharge mesurée par Kwipi, une preuve de consommation d'énergie ou une action exécutée. Si aucune différence défendable n'est présente, rester `idle` ou `abstain`. Le résultat moteur reste `halt` lorsque le sol n'est pas attesté. `rest` reste un **plan**, jamais une recharge accomplie.

Le contexte historique utilise **une seule ligne immédiatement précédente** (`ORDER BY id DESC LIMIT 1`), conservée en base. Pour être comparable, cette ligne doit avoir `source='simulator_ipc'`, `quality='coherent'`, `outcome='no_action_executed'`, `reward IS NULL`, `motor_commands=0`, batterie connue, horloge monotone et compteurs ToF + horloges OEM strictement croissants. Le délai entre deux prises est borné à **60 secondes** (fenêtre expérimentale de contexte, pas seuil OEM/robot). La récupération entre sessions est autorisée seulement lorsque les preuves de continuité restent compatibles ; pas de reprise après remise à zéro des séquences ou des horloges. Une ancienne mesure n'est **jamais** utilisée comme une mesure actuelle.

### Classes de comparaison

| Comparaison | Signification / comportement |
| --- | --- |
| `no_reference` | Aucun cycle antérieur ; état neutre |
| `interrupted` | Dernier cycle absent, invalide ou non comparable ; ne pas sauter au-dessus d'une panne |
| `incompatible_clock` | Horloge retournée, séquence/horloge ToF non croissante ou absente ; pas de reprise sémantique |
| `expired` | Ancien cycle hors fenêtre mémoire de 60 s ; référence rejetée |
| `unknown_battery` | Batterie précédente ou actuelle absente ; aucune transition inventée |
| `stable_band` | Batteries connues du même côté du seuil hérité de 15 % |
| `normal_to_low` | Batterie courante faible ; intention cognitive `rest` si qualité valide |
| `low_to_normal` | Observation de plage normale après basse ; `observe_status` seulement si les motivations existantes le permettent, sinon `idle` |

L'évaluation `consider_simulator_status` **ne modifie ni énergie, ni prudence, ni préférence**. L'ancien `AutonomyBrain._record` est également corrigé : une **intention proposée** de repos ne recharge plus l'énergie interne, et une intention de déplacement non exécutée ne la réduit plus. Cela respecte le principe « apprendre uniquement de résultats observés », sans créer une seconde politique de motivation.

## SQLite et compatibilité P2b

- **Une seule base `ExperienceMemory` et un seul flux d'écriture** : extension de `sim_passive_cycles` par `attention`, `comparison`, `reference_id`. `CREATE TABLE IF NOT EXISTS` prend en charge les bases neuves ; `PRAGMA table_info` + `ALTER TABLE` migre les bases P2b préexistantes en place, en conservant les lignes et en affectant `not_evaluated` aux champs nouveaux des lignes historiques.
- La requête de rappel lit **au plus un enregistrement**, sans nouvelle table ou index, photo, voix, empreinte de personne, identité, carte, matrice ToF brute ni copie de tous les événements.
- **Aucune purge historique automatique** : cette modification ne limite **pas** le volume total de la table P2b déjà potentiellement croissante. La stratégie globale de rétention/migration est réservée à [EX4 #80](https://github.com/Jean-Philippe56520/Microduck/issues/80) après inventaire et mesures.
- Les tables `experiences`, `sim_motion_trials`, `intent_preferences`, les modules EX1/EX2 fictifs et la mémoire M1-B ne sont pas modifiés.

## Vérifications et critères de sortie

Les tests `tests/test_x2b_sim_passive_memory.py` doivent vérifier les transitions, l'absence de référence, les interruptions, une batterie inconnue, la chute, les échantillons répétés/périmés, le redémarrage de session, les horloges manquantes, la comparaison bornée, une migration P2b, la réouverture du fichier SQLite et **zéro** récompense, appel Qwen ou commande moteur. Les anciennes suites P2b, X1 et X2-A doivent rester vertes.

**Niveaux de preuve :** code Python proposé ; tests CI à vérifier ; aucune nouvelle simulation officielle MuJoCo exécutée dans ce lot ; aucune caméra/son/NPU ni validation matérielle RK3566. Les indices de la télémétrie sim restent **non authentifiés comme robot réel** ; les seuils batterie 15 %, cadences 45 Hz et fenêtre 60 s sont des conventions de laboratoire, pas une garantie de sûreté domestique.

**Suite : [X2-C #79](https://github.com/Jean-Philippe56520/Microduck/issues/79)** : exécuter les deux sessions sur les **vrais démons du simulateur** avec `scripts/sim-smoke.sh`, mesurer latences, RSS, taille SQLite et erreurs, sans autorité motrice, sans Qwen, sans fausse cause. La collecte Cat-A2b [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78) reste en attente de vraies images privées basses.
