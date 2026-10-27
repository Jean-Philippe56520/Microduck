# Kwipi — premier lot d'exécution du plan de conformité (27/10/2026)

**Statut : [PR #77](https://github.com/Jean-Philippe56520/Microduck/pull/77) ouverte.** Première CI [#40425318908](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40425318908) verte : **1 226 tests, 19 ignorés, zéro échec**, avant un renforcement supplémentaire de la voie de planification historique. Nouvelle CI nécessaire après ce renforcement. **Zéro validation physique.** Ce lot est une **acceptation d'intégration sur fixtures** et une **mise en quarantaine de la voie historique de feedback**. Il n'implémente pas une navigation ni un traitement audio/vidéo réel.

## Audit avant modification — sources et responsabilités

- **Source constructeur épinglée** : `upstream/microduck` au SHA `942e58e3aa6dbb28e7037203fff11866122c7567` selon [R0](oem-reuse-audit-2026-10-26.md), `upstream/microduck_rl` `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` selon [R1.5](r15-retrospective-reuse-audit-2026-10-26.md). Aucun pointeur de sous-module changé.
- **OEM encore en cours** : [#381, cerveau](https://github.com/pollen-robotics/microduck/pull/381) et [#414, maploc v2 / mapd](https://github.com/pollen-robotics/microduck/pull/414), toutes deux **ouvertes, non fusionnées** lors de la vérification du 27/10/2026. Ne pas traiter ces travaux comme distribués par Pollen.
- **Projet existant** : réutilisation de `AutonomyBrain` F2, `PassiveRead`, `PassiveObservationJournal`, `BehaviorPortrait` P-A, `MockBehaviorContinuity` PD2, `ExperienceMemory` et des journaux EX1/EX2/EX3 ainsi que la politique PD3. Le simulateur officiel possède déjà des démons et des politiques ; **aucun second démon, SQLite, moteur ni capteur**.
- **Communauté** : [registre C3](community-reference-registry-2026-10-26.md) consulté, en particulier QuackNav/microduck-brain pour la navigation, Quacksat pour la voix, microduck-twin pour l'audio de simulation et GC-RENCAO/lab pour les scénarios. **Aucun code, poids, média, patch ou licence tierce intégré**. Leur simulation n'autorise pas le mouvement de Kwipi.

## Modifications du premier lot

1. **Réutiliser plutôt que recréer** : `tests/test_kwipi_integrated_host_acceptance.py` traverse les contrats existants avec une seule `ExperienceMemory` SQLite et des prises *fictives* : proposition F2, description P-A/PD2, résolution EX1 et observation EX2, consultation du journal en lecture seule, influence d'une catégorie déjà mémorisée, tendances EX3 sur trois sessions fictives puis correction/rétraction, et triage PD3 sans transmission Qwen.
2. **Fermer une lacune héritée** : `ExperienceMemory.learn_from_outcome` refuse désormais toute récompense valide **sans preuve d'exécution** en levant `PermissionError`. L'ancienne `AutonomyBrain.feedback` conserve son nom public, mais délègue à ce refus et ne modifie plus les motivations. `AutonomyBrain._record` conserve ses choix **en RAM seulement** : il n'insère plus un projet d'action dans `experiences`. Les tests de l'ancienne API vérifient l'absence de récompense, mutation et fausse trace d'action exécutée. Aucun texte libre ou identité n'est journalisé par ce lot.
3. **Ne pas détruire l'historique** : pas de suppression, migration, nouvelle table ni purge de `experiences`. Les enregistrements historiques ne constituent pas des preuves physiques. `MockCycleRunner` P2a et `record_simulated_motion` restent des **voies explicitement fictive et simulée**, distinctes des récompenses physiques.

**Dette préexistante toujours ouverte :** l'API publique historique `ExperienceMemory.record_action()` peut encore écrire explicitement dans la table `experiences` sans quota global, **mais le sélecteur `AutonomyBrain._record` ne l'appelle plus**. Ne pas connecter l'API historique à `robotd`, ne pas interpréter les anciennes lignes comme des gestes, et faire un lot séparé pour l'inventaire des consommateurs ainsi que la politique d'archivage/migration : supprimer automatiquement de vieux souvenirs serait dangereux.

## Critères et statut de preuve

| Critère | Statut de ce lot |
| --- | --- |
| Motif `unknown` observé deux fois peut suggérer une attention | Test de contrat sur fixtures ; non authentifié |
| Même catégorie déjà vue → décision différente et immobile | Test de contrat sur fixtures et SQLite existante |
| EX1 « proposed » différent de « mock_executed » | Test de contrat, **jamais une exécution robot** |
| EX2 « changed » reste « temporal_only », sans récompense causale | Test de contrat, sans effet moteur |
| EX3 trois sessions fictives → biais borné ; rétraction → biais annulé | Test de contrat, pas d'apprentissage d'un animal réel |
| PD3 refuse le transport même après opt-in fictif | Test de contrat, zéro Qwen, zéro pixel, zéro son |
| Feedback historique arbitraire ne met plus à jour `objects.preference` | Régression de sécurité testable |
| Tests dans la CI de la PR | Première CI verte (1 226 tests, 19 ignorés) ; **CI finale à relancer après le dernier changement** |
| Simulateur OEM en boucle fermée avec les démons | **Non exécuté dans ce lot** |
| Caméra, microphone, ToF, Yocto, Qwen réel, RK3566, robot physique | **Non disponibles / non validés** |

## Plan opérationnel après ce lot — portes de passage

**A — Cat-A2b (priorité de perception, bloqué par les prises).** Réutiliser `cata2b_private_low.py` et les métriques Cat-A2a. Il manque des **JPEG réels**, des annotations indépendantes, la hauteur mesurée du **centre optique**, des scènes/sites/sessions distincts, des inconnus et des droits/consentements. Une photo recadrée ou une fixture ne remplace pas une prise basse. Aucun chiffre de performance à inventer.

**B — Simulation constructeur intégrée.** Réutiliser `scripts/duck-sim` et les services réels `robotd/mediad/tofd` en simulation, identifier exactement les contrats de lecture et le statut d'authentification des événements. Exécuter un scénario sans danger « observation → souvenir → intention autorisée → résultat observé » ; tester STOP, capteur absent, faux sol sûr, refus, reprises et journal en lecture seule. Une intention descriptive PD2 ne devient pas un RPC moteur ; vérifier l'API OEM avant de l'adapter.

**C — Mémoire des conséquences vérifiées.** Faire l'inventaire de toutes les écritures historiques, de `MockCycleRunner`, de `ExperienceMemory`, M1-B/F4-A et EX1/EX2 avant tout changement du schéma. Définir une preuve d'exécution explicite avec source, horodatage, action effectivement acceptée/observée, absence de concurrent causal et correction. Pas de réutilisation du statut `mock_executed` comme résultat réel. Quota, WAL et rétention après mesures.

**D — Audio et « Hé Kwipi ! ».** Vérifier d'abord les capacités de `pet-detect`/microphone OEM, puis les contrats et licences Quacksat/Quacksat-core. Tester phrase entière hors ligne, bruit moteur/TV, voix indépendantes, faux réveils/rejets et STOP prioritaire, **sans commander les moteurs à l'activation**. Ne pas confondre mot-clé, reconnaissance de son familier et transcription.

**E — Déploiement physique conditionnel.** Après disponibilité du matériel : `scripts/resource-audit.sh` en lecture seule (repos, vision, déplacement supervisé), RAM/RSS, stockage réellement monté, WAL, CPU, température, charges et cadence moteur 50 Hz ; audit du NPU RKNN, Qwen 4B puis 9B sur PC facultatif, consentement et quotas. Pas de marge 1 Go/32 Go présumée, de navigation libre ou de validation de seize animations sans preuve.

**Règle de décision** : au prochain lot, comparer à nouveau l'OEM épinglé, les PR constructeur, les API Companion et le registre C3 ; choisir `réutiliser / adapter / créer` avec preuves. L'état de `docs/plan-action.md` reste la référence. La présente intégration hôte ne modifie ni ce classement ni la priorité Cat-A2b.
