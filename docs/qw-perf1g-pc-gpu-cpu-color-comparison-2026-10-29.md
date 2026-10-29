# QW-PERF-1G — comparaison exploratoire CPU / mémoire GPU déclarée sur le PC Windows

**Date :** 29 octobre 2026. **Source :** deux sorties PowerShell réelles fournies par l'opérateur (non reproduites indépendamment par l'agent) ; aucune donnée personnelle, aucun média, aucun journal brut n'est versé au dépôt. **Autorité :** [plan-action.md](plan-action.md). **Code de référence :** Microduck Companion main au SHA 642b2ca9e18f17b6d3450a51f4ec6d78dadd0226 (PR #156 fusionnée), sans modification des sous-modules OEM. **Statut :** *PC réel, deux couleurs synthétiques, placement GPU/CPU déclaré par Ollama ; aucun usage robot.*

## 1. Question, observation et préparation sûre

Question unique : le même test de couleur du véritable qwen3.5:9b sous Ollama Windows est-il plus court sur un processus temporaire demandant Vulkan et l'iGPU AMD Radeon 860M que sur le serveur habituel CPU, et que rapporte chaque serveur sur la résidence du modèle ?

Réemploi du code existant, **aucun nouveau modèle ni nouveau pilote** :

- **GPU candidat / port 11435 :** worktree Windows isolé au commit 642b2ca ; scripts/kwipi-vision-test.ps1 avec les options VisionCheck, ReportPlacement et Port 11435. Le lanceur active localement OLLAMA_VULKAN=1 et OLLAMA_IGPU_ENABLE=1 pour le serveur temporaire qu'il crée, et l'arrête après les deux consultations.
- **CPU témoin / port 11434 :** même commit et mêmes images via microduck_companion.qwen9b_vision_check, avec options ollama-port 11434, timeout 120, report-placement. Serveur habituel préexistant, modèle visible par /api/tags. QW-PERF-1B avait déjà constaté 100 % CPU sur ce serveur ; le présent relevé confirme size_vram=0 pendant le test.
- Deux images **uniquement synthétiques** de couleur rouge et bleue, générées en mémoire par le même code (Pillow 256 × 256 puis conversion JPEG standard), ordre **rouge puis bleu** sur les deux serveurs. Un appel par couleur et par configuration, requêtes séquentielles. Même tag de modèle qwen3.5:9b ; l'identité binaire modèle n'a pas été contrôlée indépendamment.
- Matériel identifié dans les relevés antérieurs : Ollama 0.40.12, Radeon 860M et pilote Windows 32.0.22052.3. Les opérations n'ont ni modifié le serveur principal 11434 ni commandé robotd ou SQLite.
- **Sécurité / retour arrière :** le processus Ollama temporaire a été arrêté normalement après l'essai ; le port 11435 n'a pas été conservé en service. Le worktree de mesure est séparé du clone Windows historique avec ses nombreux fichiers indexés : ne pas réinitialiser ce clone pour récupérer la sonde.

## 2. Données observées (valeurs de sortie, pas inférence matérielle)

| Critère | Serveur GPU candidat 11435 | Témoin CPU 11434 |
| --- | ---: | ---: |
| Rouge, réponse attendue et reçue | red / red | red / red |
| Durée rouge | **8,343 s** | **10,735 s** |
| Bleu, réponse attendue et reçue | blue / blue | blue / blue |
| Durée bleu | **8,891 s** | **11,343 s** |
| Moyenne des deux durées | **8,617 s** | **11,039 s** |
| placement (/api/ps) | **gpu_memory_reported** | **cpu_memory_reported** |
| max_model_size_bytes | 5 614 726 020 | 6 187 856 689 |
| max_reported_vram_bytes | **5 614 726 020** | **0** |
| model_samples | 26 | 35 |
| model_not_loaded_samples | 15 | 18 |
| polls | 41 | 53 |
| unavailable_samples | 0 | 0 |
| Succès du contrôle de deux couleurs | two_colors_distinguished | two_colors_distinguished |
| Codes de sortie | 0 | 0 |

Sur ces **deux paires seulement**, la différence moyenne est de **2,422 s** en faveur du serveur demandant le GPU, soit une diminution descriptive d'environ **21,94 %** de la latence murale et un rapport d'environ **1,281 ×**. Ces chiffres ne sont **ni un estimateur statistique solide ni une preuve d'accélération des calculs GPU**.

L'observateur Ollama a rapporté des allocations de mémoire GPU pour le **tag de modèle Qwen attendu** sur 11435, tandis que le même champ est resté nul sur 11434. La Radeon 860M est un **GPU intégré à mémoire partagée** : size_vram est un indicateur renvoyé par le serveur, pas une mesure de VRAM dédiée, du calcul effectif ou d'une charge GPU %. Les tailles totales de modèles diffèrent entre les processus : cela n'établit pas de différence de poids, de format ou de quantification.

Sur chaque sortie, les champs gpu_compute_independently_verified et gpu_speedup_measured restent explicitement **false** ; motor_commands_issued=0, memory_writes=0 et private_images_read=0. Le statut de chaque réponse est unverified malgré la correspondance avec les deux couleurs synthétiques.

## 3. Ce que ces essais permettent ou non de conclure

**Observé (PC réel, déclaré par Ollama) :** les deux images artificielles sont reconnues sur les deux ports ; le modèle apparaît avec size_vram positif sur 11435, avec size_vram nul sur 11434. Le port 11435 lancé pour le test est arrêté normalement, aucun nouveau problème de disponibilité n'est visible dans ces sorties.

**Indication descriptive :** les latences 11435 sont inférieures aux latences 11434 pour chacune des deux images testées. Le protocole utilise bien le **même code de génération et le même type de requête**, contrairement aux profils QW-PERF-1B antérieurs ; il reste non randomisé, seulement deux observations par configuration et une seule séquence de serveurs.

**Inconnu/non validé :** backend de calcul réellement actif durant chaque token (l'API de placement ne mesure pas l'utilisation des unités de calcul), résidence mémoire mesurée indépendamment, charge GPU et RSS RAM, énergie/température, débit token, caches et amorçage homogénéisés, caractère reproductible du delta, p50/p95, qualité sémantique sur objets réels et risques du conseiller Qwen, performance future QW-1/QW-2. Aucune généralisation à un robot RK3566 et aucune autonomie/causalité physique.

**Échec falsifiant une hypothèse future de gain réel :** effet nul ou inversé après alternance équilibrée sur mêmes paramètres ; erreurs/couleurs erronées ou instabilité/pression RAM ; absence de preuve indépendante du backend. Ne pas conclure à un GPU rapide uniquement depuis size_vram positif.

## 4. Prochaine porte : préparer, ne pas relancer à l'aveugle

1. **Avant toute nouvelle inférence** : relire ces deux sorties, vérifier l'absence de processus temporaire restant et disposer d'un protocole CPU/GPU **apparié et borné** avec cache/chargement identifiés, ordre alterné, compteurs de charge GPU/RSS/température et refus de surchauffe/instabilité.
2. **Comparer le même rôle Qwen utile à Kwipi** : conserver la même image synthétique, le même prompt, contexte et paramètres sur chaque backend, mesurer chargement, préremplissage et génération avec les métriques Ollama existantes ; éviter une série de nouveaux tests de couleurs non informatifs.
3. **Aucune installation non justifiée** : ne pas forcer HSA_OVERRIDE, modifier des DLL/driver, le modèle, F5-C, robotd, la base SQLite ou l'OEM. Attendre une question précise, une durée/quota et un arrêt définis pour le prochain essai.
4. **Pour le projet Kwipi** : Qwen 9B reste **conseiller facultatif sur PC**, pas un contrôleur d'actuateurs ; les observations présentes ne prouvent pas connaissance, causalité, perception d'objets réels ou autonomie.

## 5. Réutilisation et traçabilité

| Décision | Éléments | Justification |
| --- | --- | --- |
| **Réutiliser** | PR #156 fusionnée, qwen9b_vision_check.py, ollama_device_placement.py, API /api/ps, OllamaEndpoint | Une sonde existante satisfait la question de placement ; aucun nouvel outil ni dépendance |
| **Adapter** | Documentation de QW-PERF-1F/README/plan/roadmap/audit/registre | Consigner les mesures réelles et supprimer l'impression que la preuve reste entièrement manquante |
| **Créer** | Ce seul rapport de preuve QW-PERF-1G | Préserver les nombres et les limites sans conserver de données privées |
| **Ne pas modifier** | Sous-modules OEM, moteurs, pilote Windows, configuration système, poids, modèle, SQLite | Hors du chantier PC-only |

Références : [QW-PERF-1F](qw-perf1f-ollama-placement-sampling-2026-10-29.md), [QW-PERF-1B/E](qw-perf1b-real-windows-9b-baseline-2026-10-29.md), [documentation Ollama /api/ps](https://docs.ollama.com/api/ps), [PR #156](https://github.com/Jean-Philippe56520/Microduck/pull/156). Les contrôles CI de la PR #156 ont été verts sur la branche candidate ; ces contrôles PC-fixtures ne comprennent **pas** de Qwen 9B réel ni de preuve de calcul GPU.

**Classification :** prévu (comparaison reproductible et ressources), codé (sonde existante PR #156), testé PC-fixtures (CI PR #156), **testé sur PC réel par l'opérateur** (les deux sorties ci-dessus), simulé OEM (non), **validé robot (non)**.
