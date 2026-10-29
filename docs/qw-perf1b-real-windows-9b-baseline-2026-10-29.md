# QW-PERF-1B — Premier relevé réel opérateur, PC Windows/Ollama (29/10/2026)

**Statut : relevé opérateur réel, transmis en conversation, non reproduit indépendamment sur son ordinateur.** Aucun moteur, Qwen automatique, photo personnelle, SQLite, capteur physique ou commande OEM. **Autorité :** [plan-action.md](plan-action.md) ; [protocole QW-PERF-1](qw-perf1-pc-synthetic-benchmark-2026-10-28.md). Dépôt de référence : `main@9eab4aefd89b00c3caef0df7979d25b7632b19ad`, sous-modules inchangés `microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`.

## Observation indépendante du code : ce qui a été communiqué

Le propriétaire a exécuté **sur son PC Windows** `python -m microduck_companion.qwen9b_perf_probe --run --authorize-five-synthetic-calls --ollama-port 11434 --timeout 120`, avec l'image artificielle du banc (cercle rouge, JPEG en mémoire). Le serveur local Ollama `127.0.0.1:11434` répondait et listait le tag `qwen3.5:9b`. L'ancien port `11435` était fermé ; un essai sur ce port avait donné cinq échecs de transport proches de deux secondes **sans mesure d'inférence**.

**Réponse du banc sur `11434` :** cinq statuts `unverified`, aucun rejet, modèle déclaré `qwen3.5:9b`, charge initiale inconnue, provenance exacte du binaire modèle non vérifiée. Pas de données mémorielles (`memory_used=false`), ni écriture (`memory_writes=0`), ni commande motrice (`motor_commands_issued=0`), ni média privé (`private_images_read=0`), ni transcription enregistrée. La qualité sémantique des réponses **n'a pas été jugée** ; seul le couple couleur/forme du cercle est contrôlé pour les deux sorties JSON.

| Profil | Mur, s | Ollama total, s | Chargement, s | Prompt/image, s | Génération, s | Tokens prompt | Tokens générés | Correspondance couleur/forme |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `role_v2_first` | 44.234 | 44.2347 | 7.1650 | 22.3634 | 14.6899 | 1 909 | 134 | non évaluée |
| `role_v2_repeat` | 14.750 | 14.7511 | 0.0058 | 0.1308 | 14.6028 | 1 909 | 134 | non évaluée |
| `compact_text` | 3.703 | 3.7001 | 0.0052 | 2.0556 | 1.6093 | 134 | 15 | non évaluée |
| `compact_json` | 7.110 | 7.0786 | 0.0087 | 0.1717 | 6.8933 | 134 | 60 | **oui sur fixture** |
| `compact_json_mock_context` | 9.109 | 9.1061 | 0.0057 | 2.2976 | 6.7988 | 178 | 60 | **oui sur fixture** |

Après les appels, l'opérateur a exécuté `ollama ps` et rapporté : **`qwen3.5:9b`, 6,2 GB chargés, `PROCESSOR=100% CPU`, `CONTEXT=4096`, `RUNNER=llamacpp`**. Ce relevé constitue une preuve directe de l'absence d'utilisation du GPU **pour ce serveur et ce modèle à cet instant**, non une preuve que le matériel ne supporte aucun backend accéléré. **Diagnostic logiciel reçu ensuite (29/10/2026, rapport opérateur) :** `ollama version is 0.40.12` ; `Get-CimInstance Win32_VideoController` : `AMD Radeon(TM) 860M Graphics`, `DriverVersion=32.0.22052.3`. `ollama ps` a ensuite été affiché vide, compatible avec l'expiration du `keep_alive=2m` du banc ; ce n'est pas une panne. La **détection effective de la 860M par Vulkan/ROCm dans les journaux Ollama reste inconnue** ; un `100% CPU` ne prouve pas que Vulkan/ROCm fonctionne ou ne fonctionne pas au niveau de Windows. Les 6,2 GB correspondent au **SIZE affiché par Ollama**, pas à une mesure indépendante de RSS système.

## Interprétation et limites

- **Premier/répété sous `keep_alive=2m` :** 44,234 s → 14,750 s, soit environ **3,00×** plus rapide sur le **même JPEG et le même prompt**. Le gain combine la réduction du chargement **7,1650 → 0,0058 s** **et surtout** du traitement du prompt déjà réutilisé **22,3634 → 0,1308 s**. Il ne serait pas rigoureux d'attribuer les 29,484 s gagnées au seul maintien du modèle chargé. Les images différentes, souvenirs renouvelés et questions nouvelles peuvent perdre le bénéfice de cache.
- **Génération CPU :** rôle long **134 tokens en ~14,6 s** (environ **9,1 tokens/s**) ; JSON compact **60 tokens en ~6,9 s** (environ **8,7 tokens/s**). Le nombre de tokens générés reste coûteux. `compact_text` ne produit que 15 tokens, donc ses 3,703 s ne prouvent pas qu'il remplace un conseil structuré fiable.
- **Contexte fictif :** JSON seul 7,110 s vs JSON + note fictive 9,109 s (**+1,999 s**, un seul échantillon). Le nombre de tokens prompt est 134 vs 178 ; la durée prompt `0,1717 → 2,2976 s`. Il est interdit d'en déduire un coût fixe de SQLite réelle ou de la recherche multi-tours.
- **Qualité :** les deux JSON décrivent correctement **le cercle rouge synthétique**, et non un objet réel, une stratégie sûre, une conséquence, une identité ou un raisonnement causalisé. Aucun test de décision de Kwipi, locomotion, OEM 50 Hz ou autonomie n'a été effectué.
- **Statistiques :** un seul appel par variante, ordre fixe et charge thermique inconnue : **ni p50/p95, ni accélération GPU, ni qualité généralisable, ni promesse de moins de dix secondes**.
- **Priorité matérielle :** vérifier d'abord la sélection GPU. En octobre 2026, la documentation officielle d'Ollama décrit ROCm/HIP sous Windows et Vulkan comme possibilité de prise en charge ; une [issue constructeur Ollama #14562, ouverte le 02/03/2026](https://github.com/ollama/ollama/issues/14562), décrit spécifiquement des retours CPU sur **Radeon 860M Windows malgré Vulkan fonctionnel**. **L'issue correspond à une configuration tierce, pas à un diagnostic prouvé de ce PC**, et ses contournements ne sont pas prescrits. [Document Ollama GPU](https://github.com/ollama/ollama/blob/main/docs/gpu.mdx).

## Porte avant tout nouvel essai ou installation

**Observation :** tous les appels réels ont réussi, mais la charge était au CPU ; version et GPU sont identifiés : **Ollama 0.40.12 / Radeon 860M / driver 32.0.22052.3**. La [liste GPU officielle Ollama Windows ROCm](https://docs.ollama.com/gpu) **ne mentionne pas la 860M** ; Vulkan offre une voie complémentaire et est normalement actif par défaut si le backend est disponible. L'[issue Ollama #14562](https://github.com/ollama/ollama/issues/14562) signale une non-détection **de la même Radeon 860M**, mais sous **Ollama 0.17.4–0.17.5**, et ne prouve pas que 0.40.12 est affecté. **Hypothèses concurrentes :** iGPU absent de la découverte Vulkan, composant backend non chargé, réglage serveur déjà existant, pilote Windows incompatible, ou autre problème. **Prochaine question unique :** que signalent les journaux du serveur Ollama actuel sur la détection GPU au démarrage ?

**Diagnostic exclusivement en lecture seule, depuis PowerShell :**

```powershell
# Version / pilote déjà confirmés le 29/10/2026 ; ne pas répéter inutilement.
$log = Join-Path $env:LOCALAPPDATA "Ollama\\server.log"
if (Test-Path -LiteralPath $log) {
    Get-Content -LiteralPath $log -Tail 1200 |
        Select-String -Pattern "ggml_vulkan|gfx1152|Vulkan|ROCm|GPU.*discover|GPU.*detect|inference compute|filtering device|total_vram" |
        ForEach-Object { $_.Line }
} else {
    "Journal serveur introuvable (vérifier le serveur Ollama Windows actif)."
}
```

**Précaution journaux :** la commande ci-dessus lit uniquement un fichier local et filtre des lignes GPU. Avant toute transmission, **supprimer chemins personnels, jetons, contenus de requêtes ou données sensibles** si présents. Les lignes sans correspondance ne prouvent pas qu'aucun GPU n'a été examiné ; consulter la rotation `server-#.log` seulement si nécessaire. La documentation officielle localise les journaux Windows dans `%LOCALAPPDATA%\\Ollama\\server.log` ([dépannage Ollama](https://docs.ollama.com/troubleshooting)).

Ne pas faire `ollama pull`, `setx`, `stop-process`, `ollama stop`, mise à jour de pilote, remplacement de DLL, surcharge forcée ROCm, allocation VRAM ou second serveur concurrent pour ce diagnostic. **Critères d'échec :** versions non vérifiées, GPU non détecté, accélération sans amélioration de la qualité ou dégradation mémoire/fiabilité, suppression d'un service existant. **Retour arrière :** aucun réglage durable modifié dans ce lot documentaire ; si une expérimentation active est ensuite autorisée, faire un seul changement temporaire mesuré et restaurer l'environnement immédiatement après, avec témoin CPU.

**Après diagnostic confirmé :** concevoir, si nécessaire, **un** essai GPU **isolé et réversible** avec le même JPEG, le même prompt, la même résolution, les mêmes quotas et mesure `ollama ps` + `load/prompt/eval` + RSS/thermique ; vérifier compatibilité exacte avant de lancer, et ne pas changer les paramétrages OEM. Ensuite seulement étudier le raccourcissement sémantique des réponses, l'amortissement du cache sur objectifs différents et l'accès mémoire QW-1/QW-2.

## Réutiliser / adapter / créer

| Source existante | Décision |
| --- | --- |
| `qwen9b_perf_probe.py` et cinq résultats numériques | **Réutiliser** sans nouveau programme : ces mesures suffisent pour établir la baseline |
| `qwen9b_role_preview.py`, `OllamaEndpoint`, F5-C | **Ne rien modifier** avant le diagnostic du PC |
| Documentation GPU officielle Ollama et issue Radeon 860M | **Comparer** version/driver avec le PC, ne pas supposer une résolution ou importer de patch tiers |
| Code OEM `robotd`, `IdleHead`, Yocto/RL | **Ne pas toucher** ; la posture interrogative synchronisée reste un lot séparé |
| Éventuel nouveau backend, fork ou wrappers | **Ne pas créer ni installer maintenant** ; priorité à l'existant et à la preuve |

**États finaux :** banc QW-PERF-1 **codé/testé PC-fixtures** (#151), cinq appels **réels PC rapportés par l'opérateur** (#QW-PERF-1B), décision de meilleure configuration **prévue**, Qwen associé à SQLite **non codé**, posture questionnement **non codée**, **aucun robot validé**.
