# QW-PERF-1I — Résultat du banc PC Qwen 9B : cinq profils CPU / iGPU déclaré

**Date :** 29 octobre 2026. **Source :** sorties PowerShell réelles communiquées par l'opérateur (non reproduites indépendamment) ; **aucun journal brut, photo personnelle, identifiant, chemin utilisateur ou réponse du modèle versé au dépôt**. **Autorité :** [plan-action.md](plan-action.md). Version exécutée : `main@a037778b6eaf4261deb3d67e2e2ecc3cf64fff96` après [PR #158](https://github.com/Jean-Philippe56520/Microduck/pull/158) et [PR #159](https://github.com/Jean-Philippe56520/Microduck/pull/159) fusionnées et CI vertes. Provenance du protocole : [QW-PERF-1H](qw-perf1h-pc-role-benchmark-placement-2026-10-29.md).

**Classification :** prévu (répétabilité, charge GPU indépendante, RSS et température, qualité du conseil, intégration QW-1/QW-2), **codé** (banc existant QW-PERF-1H), **testé PC-fixtures** (CI #158/#159), **testé sur PC réel par l'opérateur** (une séquence de cinq requêtes par configuration), simulé OEM (non), validé robot (non). Tous les résultats s'appliquent à **Qwen3.5 9B sur PC**, jamais au Microduck RK3566.

## 1. Porte de preuve : question, hypothèse, échec, sûreté

**Question unique déjà prévue par QW-PERF-1H :** sur le même banc de cinq profils synthétiques du conseiller 9B, les compteurs Ollama et durées sont-ils différents lorsque `/api/ps` déclare une allocation mémoire GPU sur le port temporaire `11435`, comparé au témoin CPU existant `11434` ?

**Hypothèse :** l'autorisation Vulkan + iGPU Radeon 860M pour le serveur temporaire peut s'accompagner de durées plus courtes que le serveur habituel CPU. La résidence en mémoire GPU **n'est pas** une preuve indépendante d'exécution de kernels GPU.

**Précontrôles attestés dans le transcript :** le worktree PC séparé était propre avant `git fetch origin main`, puis passé en HEAD détachée au commit `a037778`, avec l'environnement Python préexistant et le nouveau flag PowerShell présents. Le port `11435` n'était pas occupé ; `11434` répondait à `/api/tags` et proposait `qwen3.5:9b`. Aucune installation, commande moteur ou changement de poids. Le lanceur `-PerfCheck -AuthorizeFiveSyntheticCalls -ReportPlacement -Port 11435` a créé et arrêté normalement son serveur temporaire ; l'opérateur a ensuite exécuté le même module de banc sur `11434` avec `--report-placement`. Les deux appels de groupe ont terminé avec un code de sortie **0** (le premier via poursuite après vérification `LASTEXITCODE`, le second affiché explicitement).

**Risque/retour arrière :** ce test réel est **déjà terminé**, ne nécessite aucune nouvelle relance. Le port `11435` a été contrôlé libre après l'arrêt ; le serveur habituel `11434` n'a pas été arrêté par le banc. Ne modifier ni les pilotes AMD, ni ROCm/HSA, ni les modèles, ni SQLite/robotd. Conditions d'échec pour une validation ultérieure : erreur de requête, biais de cache/charge, changement de modèle, instabilité, pression mémoire ou température anormale, non-reproductibilité des différences, absence de mesure GPU indépendante.

## 2. Données numériques réellement observées

Même tag Ollama `qwen3.5:9b` et même programme `microduck_companion.qwen9b_perf_probe`, même JPEG synthétique 256×256 contenant un **cercle rouge sur fond blanc** (aucune image personnelle), mêmes cinq **noms de profils** et leur ordre : `role_v2_first`, `role_v2_repeat`, `compact_text`, `compact_json`, `compact_json_mock_context`. `think=false`, `keep_alive=2m` dans ce banc ; la réponse structurée comporte un identifiant de requête aléatoire, différent entre les deux exécutions.

| Profil | GPU candidat 11435 : wall_s | CPU témoin 11434 : wall_s | Baisse descriptive (CPU → GPU) | eval_count GPU / CPU | prompt_eval_count GPU / CPU |
| --- | ---: | ---: | ---: | ---: | ---: |
| `role_v2_first` | **22,891 s** | 39,812 s | **42,50 %** | 142 / 134 | 1 909 / 1 909 |
| `role_v2_repeat` | **13,078 s** | 14,125 s | **7,41 %** | 169 / 134 | 1 909 / 1 909 |
| `compact_text` | **2,438 s** | 3,407 s | **28,44 %** | 15 / 15 | 134 / 134 |
| `compact_json` | **5,656 s** | 7,734 s | **26,87 %** | 61 / 61 | 134 / 134 |
| `compact_json_mock_context` | **6,359 s** | 9,859 s | **35,50 %** | 58 / 59 | 178 / 178 |
| **Somme des 5 durées murales** | **50,422 s** | **74,937 s** | **32,714 %** | **445 / 403** | — |

Ces cinq tâches séquentielles ont pris **24,515 s de moins** en total sur la configuration iGPU déclarée ; le rapport CPU/GPU des sommes est **1,486×**. La moyenne arithmétique des cinq durées est de **10,0844 s contre 14,9874 s**. **Ce pourcentage est seulement descriptif pour une seule séquence dans cet ordre fixe ; ne pas le présenter comme un speedup GPU prouvé, un intervalle statistique, ni un délai typique de consultation de Kwipi.**

**Compteurs natifs utiles pour interpréter le rôle v2 :**

| Compteur Ollama | GPU candidat 11435 | CPU témoin 11434 |
| --- | ---: | ---: |
| `role_v2_first.load_s` | 2,8577 s | 3,6013 s |
| `role_v2_first.prompt_eval_s` | 9,2640 s | 21,8523 s |
| `role_v2_first.eval_s` | 10,7570 s / 142 tokens | 14,3383 s / 134 tokens |
| `role_v2_repeat.prompt_eval_s` | 0,1422 s | 0,1494 s |
| `role_v2_repeat.eval_s` | 12,9248 s / 169 tokens | 13,9466 s / 134 tokens |
| `compact_text.prompt_eval_s` | 1,2478 s | 1,9574 s |
| `compact_json.eval_s` | 5,4672 s / 61 tokens | 7,5531 s / 61 tokens |
| `compact_json_mock_context.prompt_eval_s` | 1,2480 s | 2,5713 s |

Le débit calculé à partir des compteurs Ollama est d'environ **13,20 tokens/s** en génération sur le premier rôle v2 GPU déclaré contre **9,35 tokens/s** CPU (et **13,08 contre 9,61 tokens/s** pour la répétition). L'effectif de tokens générés est plus élevé sur iGPU pour les deux rôles v2 : **il ne faut pas attribuer directement toute différence de durée à la puce graphique ou supposer des réponses identiques**. Les durées de préremplissage du prompt du rôle v2 chutent pour les deux systèmes au deuxième appel, compatibles avec un cache chaud mais **sans mesure indépendante des hits de cache**.

**Rapport de placement Ollama :**

| `/api/ps` | GPU candidat 11435 | CPU témoin 11434 |
| --- | ---: | ---: |
| `placement` | `gpu_memory_reported` | `cpu_memory_reported` |
| `max_model_size_bytes` | 5 614 726 020 | 6 187 856 689 |
| `max_reported_vram_bytes` | **5 614 726 020** | **0** |
| `model_samples` | 113 | 172 |
| `model_not_loaded_samples` | 7 | 9 |
| `polls` | 120 | 181 |
| `unavailable_samples` | 0 | 0 |

Les tailles de modèle **rapportées par les deux serveurs diffèrent**, malgré le même tag logique `qwen3.5:9b`. L'identité binaire du modèle, les poids effectivement chargés et les couches exécutées n'ont **pas** été contrôlés indépendamment. Une Radeon 860M intégrée partage la mémoire du système ; les 5,615 Go correspondent à la **taille déclarée par Ollama**, pas à une VRAM dédiée indépendante ni à une mesure des unités de calcul ou de la charge GPU %.

**Validité des réponses :** les dix profils rapportent `status=unverified`, `diagnostic=none` ; seuls les **deux JSON par serveur** ont `fixture_shape_color_match=true`, sur le cercle rouge artificiel. Les profils texte et v2 n'ont **aucune évaluation sémantique** (`fixture_shape_color_match=null`) : nous ne savons pas s'ils donnent des hypothèses utiles, des stratégies sûres, de la compréhension ni des conséquences cohérentes pour Kwipi. Les champs `gpu_compute_independently_verified=false`, `gpu_speedup_measured=false`, `model_identity_independently_verified=false`, `rss_and_gpu_placement_measured=false`, `memory_used=false`, `memory_writes=0`, `private_images_read=0`, `motor_commands_issued=0` restent valides et ne doivent pas être convertis en validations.

## 3. Interprétation, réutilisation et prochaine décision

**Ce qui est prouvé par les sorties opérateur :** les cinq profils ont produit un résultat acceptable pour le validateur de transport sur chaque port ; le placement *déclaré* est distinct (positif sur 11435, nul sur 11434) ; toutes les durées murales sont plus courtes avec le serveur iGPU demandé, y compris les JSON à effectifs de tokens similaires. Cela confirme **une association dans cette session**, pas sa cause matérielle précise.

**Ce qui n'est pas prouvé :** accélération calcul GPU confirmée matériellement, comparaison équilibrée (groupe GPU **avant** groupe CPU), départ à froid identique, absence de charge Windows concurrente, p50/p95, température/puissance/RSS/pression mémoire, identité binaire modèle, qualité du conseiller pour les objectifs et les souvenirs, robustesse sur objets réels, sécurité d'action, autonomie du robot. Aucun résultat n'autorise une consultation non consentie de Qwen ou un pilotage `robotd` depuis le LLM.

**Matrice réutiliser / adapter / créer :**
- **Réutiliser** le banc QW-PERF-1H fusionné et ses sorties numériques, l'API officielle Ollama `/api/ps`, les schémas et validations F5 ; **aucun nouveau code de benchmark**.
- **Adapter** uniquement README, plan, roadmap, audit matériel, registre C3, reprise et ce rapport pour consigner la preuve observée.
- **Créer** seulement ce rapport de constat QW-PERF-1I ; **aucun** modèle, driver, backend, SQLite, agent, contrôleur, sous-module ou dépendance tierce.
- **OEM inchangé :** `robotd` conserve seul la boucle motrice 50 Hz, aucun test robot, MuJoCo ni effet causal moteur.

**Prochaine porte utile plutôt que relancer des benchmarks de couleurs :** concevoir un essai de qualité **sémantique et de prudence** sur scènes synthétiques inédites, en jugeant les propositions du conseiller Qwen **sans ordre moteur ni validation causale supposée** ; en parallèle, un diagnostic **indépendant et borné** de l'activité GPU/RSS/thermie et, seulement si nécessaire, un protocole CPU/GPU à ordre contrebalancé. Les consultations réelles doivent conserver consentement, quotas, timeout, chiffrement/auth si à distance et repli local sûr. Tant que ces preuves manquent, aucune optimisation motrice ou intégration robot n'est justifiée.

Références internes : [QW-PERF-1H (banc)](qw-perf1h-pc-role-benchmark-placement-2026-10-29.md), [QW-PERF-1G (deux couleurs)](qw-perf1g-pc-gpu-cpu-color-comparison-2026-10-29.md), [QW-PERF-1 (banc initial)](qw-perf1-pc-synthetic-benchmark-2026-10-28.md), [PR #158](https://github.com/Jean-Philippe56520/Microduck/pull/158), [API Ollama `/api/ps`](https://docs.ollama.com/api/ps).
