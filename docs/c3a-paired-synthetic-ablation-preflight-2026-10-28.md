# C3-A — banc d'ablation appariée sur fixtures uniquement (28 octobre 2026)

**Statut : code et tests candidats en [PR #116](https://github.com/Jean-Philippe56520/Microduck/pull/116), [CI #40703181909](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40703181909) réussie : 1 535 tests, 5 ignorés, 0 échec. Fusion à confirmer.** Ce lot ne démontre pas la généralisation C3 sur scènes inédites. Aucun JPEG, caméra, Qwen réel, mémoire robot, ONNX ou moteur.

## 1. Porte OEM-first et preuves recherchées

**Observation :** C1 (memory_consolidation.py) ne fournit que des historiques F1-C/F2-C mock ; des sessions ne prouvent pas des scènes indépendantes. C2 conserve les 54 rétractions de propositions F4-A. L'évaluateur F3-A (visual_dataset.py) contrôle déjà les splits train/validation/test, les groupes de capture et empreintes SHA, le vocabulaire fermé, la présence de cas unknown et la complétude des prédictions. L'évaluation Cat-A2b privée reste bloquée par la vérité terrain indépendante.

**Hypothèse :** deux ou trois résultats fictifs comparés sur le même TEST, avec des groupes de captures pondérés équitablement, permettent de vérifier un futur protocole C3 sans affirmer que C1 ou Qwen ont réellement été utilisés.

**Preuve visée :** tests positifs/négatifs de fuite de groupes et de contenu, duplication, source non fictive, confiance invalide, classe inconnue, fausse acceptation sur unknown, résultat PC non mock ; comparer le score par échantillon et le score par groupe déclaré sur des entrées strictement appariées.

**Échec/stop :** données TEST distinctes entre modes, photographie privée ou source extérieure en CI, score de fixture présenté comme gain cognitif réel, faux certificat d'indépendance, passage à une action OEM, écriture SQLite ou compensation d'un résultat moteur. **Risque :** conclure abusivement à une amélioration de la mémoire ; les marqueurs de non-validation sont constants. **Retour arrière :** abandonner le module, tests et documentation ; aucune migration, donnée ou configuration motrice à restaurer.

## 2. Réutiliser / adapter / créer

| Source | Décision | Justification |
| --- | --- | --- |
| F3-A visual_dataset.py, visual_dataset_demo.py | **Réutiliser** | Parseur, provenance, split/groupe/SHA et métriques déjà testés. |
| C1/C2, ExperienceMemory, F1-C/F2-C | **Ne pas modifier** | Les sources sont mock et la SQLite unique reste propriétaire des corrections. |
| Cat-A2b #78 | **Prévoir réutilisation locale** | Vraies scènes et annotations indépendantes nécessaires avant toute conclusion. |
| OEM microduck 942e58e3 ; RL b02fdea4 ; robotd/mediad | **Ne pas modifier** | Ni moteur, ni API, ni sous-module ni vidéo ouverte dans ce lot. |
| Communauté : QuackNav, microduck-brain, Twin, GC/Smartulf, Quacksat ; OEM #381/#414 | **Ne pas importer** | Aucun composant tiers n'est requis ; compatibilité et licences ne sont pas démontrées. |
| c3_mock_ablation.py + test_c3_mock_ablation.py | **Créer adaptateur minimal** | Réutilise le scoring F3-A ; ajoute moyenne par groupe déclaré, fausses acceptations unknown et écarts appariés. |

## 3. Contrat

La fonction compare_mock_category_ablations reçoit un manifeste F3-A en JSON et au moins deux jeux de prédictions mock (sans mémoire ; avec mémoire), éventuellement un troisième jeu appelé avec PC. **Ces étiquettes de lanes sont déclaratives** : aucune instrumentation ne prouve que les décisions utilisent C1/F2 ou un vrai Qwen. Chaque jeu doit couvrir le même TEST validé une seule fois. Les scores par groupe pondèrent chaque groupe déclaré également, mais n'authentifient pas l'indépendance réelle des scènes.

Le rapport impose : ablation_execution_verified=False, independent_scenes_verified=0, real_sensors_verified=False, memory_benefit_verified=False, qwen_called=False, causal_effects_verified=0, physical_actions_authorized=False, memory_writes=0 et motor_commands_issued=0. Une différence chiffrée sur fixtures ne devient jamais une conclusion de généralisation ou de causalité.

**Tests :** invariance d'une paire identique, trois corrections artificielles, troisième lane fictive, groupe répété dans TEST, faux connu sur unknown, refus par faible confiance, groupe ou digest communs entre splits, source privée déclarée, duplicat/incomplétude, source Qwen non mock, TEST sans unknown, confiance invalide, aucune ouverture socket/SQLite.

## 4. Portes restantes

Ce banc n'exécute pas de véritable ablation de décision F2 avec/sans C1 ; n'a pas accès aux 29 images privées Cat-A2b ni aux nouvelles scènes indépendantes ; ne lance pas Ollama/Qwen 9B ; n'implique aucune action OEM ni apprentissage des effets EX4-C2. Aucune mesure robot RK3566 : RAM/RSS, CPU, disque/WAL, chaleur, 50 Hz ou autonomie.

**C3-B conditionnel :** lorsque Cat-A2b fournit des scènes annotées indépendamment, avec groupes de lieu/séance/objet disjoints et consentements, utiliser un banc privé et read-only sur les véritables sorties des deux branches de décision. Geler les seuils hors TEST, mesurer erreurs, refus et intervalles par groupe, comparer sans PC puis conseiller facultatif. Ne pas promouvoir Qwen en fait ni autoriser une commande motrice.

## 5. Traçabilité

Sources de vérité : plan-action.md, AGENTS.md, README.md, docs/development-reuse-protocol.md, docs/community-reference-registry-2026-10-26.md, docs/c1-conservative-category-recall-2026-10-28.md et docs/oem-pr450-c3-independent-scenes-gate-2026-10-28.md. Tests dans tests/test_c3_mock_ablation.py ; [CI #40703181909](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40703181909) réussie, 1 535 tests dont 5 ignorés, zéro échec. [PR #116](https://github.com/Jean-Philippe56520/Microduck/pull/116) ouverte au moment de ce constat.