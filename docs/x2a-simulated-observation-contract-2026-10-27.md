# X2-A — Contrat de lecture de télémétrie simulée sans autorité (27 octobre 2026)

**Statut : implémentation sur branche de PR, résultats CI à rattacher après exécution ; tests de fixtures uniquement pour les changements X2-A.** Ne pas confondre ce lot et la démonstration P2b antérieure réellement passée sur les démons OEM dans MuJoCo.

## Justification — réutiliser / adapter / créer

**Source** : état `main` après X1 [PR #77](https://github.com/Jean-Philippe56520/Microduck/pull/77) et [P2b](p2b-passive-mujoco-cycles-2026-10-25.md), interfaces OEM épinglées `942e58e3aa6dbb28e7037203fff11866122c7567` et microduck_rl `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` selon R0/R1.5 (à confirmer par `git submodule status` dans un checkout complet). Selon l'audit du 27/10/2026, [OEM #381](https://github.com/pollen-robotics/microduck/pull/381) et [OEM #414](https://github.com/pollen-robotics/microduck/pull/414) sont ouvertes, **non fusionnées**. Le cerveau OEM envisagé et maploc v2 ne sont pas des dépendances livrées.

- **Réutiliser** : `ReadOnlyUnixRpc`, `parse_health`, `parse_state`, `parse_depth`, `SimulatorTelemetry`, `read_simulator_telemetry`, `AutonomyBrain`, `PassiveSimCycleRunner`, l'unique `ExperienceMemory` et le banc `scripts/sim-smoke.sh` / tests P2b.
- **Adapter** deux modules existants sans créer de socket, contrôleur ni démon. `sim_ipc.ReadOnlyUnixRpc` accepte un rôle facultatif `robotd` ou `tofd`, contrôlé **localement** à la requête ; `read_simulator_telemetry` sélectionne ces rôles pour les sockets existantes. `read_health` se limite à `robotd`.
- **Créer uniquement** un résultat de **qualité de télémétrie** immuable `SimulatorTelemetryAssessment` dans `sim_bridge.py`, et ses tests d'acceptation négatifs. Il n'est **pas** un accusé d'exécution, un capteur de nouveaux objets, une autorisation de mouvement, un classificateur ou une preuve d'identité OEM.
- **Comparer la communauté** : QuackNav, microduck-brain et microduck-twin (registre [C3](community-reference-registry-2026-10-26.md)) ajoutent notamment navigation, évitement et/ou audio de simulation, mais cela excède X2-A. Pas de code, dépendance, modèle ou poids communautaire importé, ni licence tierce requalifiée.

## Matrice de source et de capacité

| Lecture | Méthode OEM épinglée | Propriétaire | Ce que l'on admet | Ce que l'on refuse d'inférer |
| --- | --- | --- | --- | --- |
| Santé, batterie et cadence de boucle | `robot.health` | `robotd` | Un compte rendu du démon sur **la simulation** ; fraîcheur au temps local | Sol sûr, état réel du robot, énergie réellement disponible sur RK3566 |
| Chute, limp, cadence et horloge d'état | `robot.subscribe` → `robot.state` | `robotd` | Déclaration de sécurité/temps du démon, à mettre en cohérence | Exécution d'une action, mouvement autorisé, capteur externe authentifié |
| Trame ToF 8×8, statut par zone, séquence et horloge | `tof.stream` → `tof.frame` | `tofd` | Présence, dimensions et ordre d'une trame simulée | Anti-escalier, sol traversable, obstacle sûr, catégorie d'objet, identité |
| Caméra, sons, Qwen, photos, souvenirs causaux | Aucune lecture autorisée en X2-A | Aucun | Rien | Nouvelle catégorie, émotion réelle, cause-à-effet, récompense |

`ReadOnlyUnixRpc` conserve les seules méthodes `robot.health`, `robot.subscribe` (1–10 Hz) et `tof.stream`. Il refuse localement toute requête motrice ou étrangère au rôle attendu, **avant** d'ouvrir une connexion. Un chemin de socket, un rôle attendu, une réponse JSON et le statut `coherent` **ne prouvent pas** l'identité de son émetteur ni son authenticité matérielle. La vérification de la version, des permissions et des identifiants de processus OEM restera un chantier distinct du portage réel. Le constructeur garde la boucle moteur 50 Hz.

## Qualité et comportement de repli

Le contrôle `SimulatorTelemetry.assess(now=…, max_age_s=…)` classe un reçu fictif/simulé, sans mutation, selon les cas :

- `source_error` : erreur de lecture signalée ;
- `missing_stream` : santé, état ou ToF absent ;
- `invalid_payload` : mauvais type, dimensions/valeurs incohérentes, NaN, horodatage non numérique ou valeur hors domaine ;
- `unsafe_state` : démon malsain, chute ou mode `limp` ;
- `slow_control` : cadence déclarée absente/inférieure à **45 Hz**, seuil **hérité du pont P2b** et non nouvelle mesure matérielle ;
- `future_sample`, `stale_sample` : temps local hors `[0, max_age_s]` pour l'un des flux ;
- `timestamp_skew` : écart des deux horloges robotd/tofd connu et supérieur à **1 seconde**, seuil P2b hérité ;
- `coherent` : uniquement cohérence **interne** de l'échantillon reçu, jamais authentification.

Les seuils X2-A sont les seuils déjà présents dans P2b : `max_age_s=2` secondes par défaut (maximum 5) ; la cohérence ne certifie ni sol ni identité ni exécution. Un échec produit un `PerceptionSnapshot` vide, le cerveau existant se limite à `halt`. Même une lecture cohérente ne peut produire qu'une éventuelle valeur `battery_pct`, et jamais `safe_area`, `floor_clear`, `object_label`, `person`, `sound_label` ou récompense. Une batterie basse peut entraîner une intention **non motrice** `rest`, mais pas un déplacement.

La classe `SimulatorTelemetryAssessment` porte des attributs explicitement faux : `physical_robot_verified`, `floor_certified`, `motor_authorized`, `semantic_category_verified` ; toute tentative de les promouvoir est rejetée.

## Tests, statut de preuve et impact

- Ajouter `tests/test_x2a_simulator_source_contract.py` : lecture cohérente sans autorité, batterie inconnue, flux manquants, payloads invalides, chute/limp/santé, cadence, horloges et fraîcheur, fausses autorisations, tentative `robot.move`, méthodes sur mauvais rôle, conservation de P2b en SQLite sans exécution/récompense.
- Réexécuter la suite complète et les tests existants de `sim_ipc`, `sim_bridge`, `sim_passive_cycles`. **CI à vérifier dans la PR**, aucun test physique et **pas de nouvelle exécution du simulateur OEM dans X2-A** ; P2b a historiquement passé son propre smoke MuJoCo.
- Aucun nouveau paquet, stockage, boucle, microphone, image, RPC moteur, Qwen, système de récompense, sous-module ni changement `robotd`.
- Aucun coût CPU/RSS/RAM/stockage ajouté quantifié sur RK3566 ; profilage/latences réels attendent X2-C et [#82](https://github.com/Jean-Philippe56520/Microduck/issues/82).
- **Porte X2-B** : relire cette matrice avant de partager de l'historique simulé avec les cinq motivations. F2/ex1/ex2 acceptent actuellement des **fixtures mock** ; interdit de réétiqueter une trame OEM en `mock` pour les contourner. Si seuls batterie/santé/ToF non sémantique sont disponibles, rester sur `idle/rest/halt`, pas de catégorie chat/chien/personne inférée.

Cat-A2b [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78) demeure bloqué par de vraies prises privées basses. Suivi [#79 — X2](https://github.com/Jean-Philippe56520/Microduck/issues/79).
