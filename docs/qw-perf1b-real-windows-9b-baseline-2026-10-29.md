# QW-PERF-1B — Premier relevé réel opérateur, PC Windows/Ollama (29/10/2026)

## QW-PERF-1E — Premier test PC sur serveur iGPU autorisé, sans preuve GPU

**Essai opérateur réel du 29/10/2026, résultats reçus en conversation ; mesures non reproduites indépendamment.** Le port `11435` était libre selon `Get-NetTCPConnection`. L'opérateur a exécuté dans un processus PowerShell enfant le **lanceur déjà présent** `scripts/kwipi-vision-test.ps1 -VisionCheck -Port 11435`. Le script source **définit** localement `OLLAMA_VULKAN=1` et `OLLAMA_IGPU_ENABLE=1` avant de lancer son Ollama temporaire si aucun serveur n'écoute sur le port ; **aucun relevé `ollama ps` ou journal de découverte GPU de ce processus temporaire n'a été transmis**.

### Observations du **premier lancement terminé**

| Fixture synthétique | Catégorie attendue | Résultat Qwen | Latence murale rapportée | Statut |
| --- | --- | --- | ---: | --- |
| Image couleur rouge | `red` | `red` | **9,079 s** | `unverified` |
| Image couleur bleue | `blue` | `blue` | **9,031 s** | `unverified` |

Le lanceur affiche `two_colors_distinguished` puis `Serveur Ollama temporaire arrete apres cet essai.` : un **cycle complet de deux appels multimodaux synthétiques** a réussi, sans instruction motrice, écriture mémoire ou lecture de photo privée (`motor_commands_issued=0`, `memory_writes=0`, `private_images_read=0`). Les résultats sont des **annotations de couleur non vérifiées par observation physique**, correspondant aux deux fixtures fabriquées localement.

**Répétition partielle non conclue :** le propriétaire a également commencé une **deuxième invocation identique** et communiqué uniquement les messages initiaux jusqu'à `Acceleration Vulkan demandee, mais utilisation GPU a verifier separement.`. **Aucun résultat de cette deuxième invocation, succès ou échec, n'est disponible dans la preuve reçue**. Ne pas confondre absence de sortie dans un extrait partiel et blocage du modèle ; ne pas ajouter d'essais de répétition sans question nouvelle.

### Ce qui n'est pas établi

- **Vulkan demandé ≠ exécution GPU démontrée.** Le script peut légitimement se replier sur CPU ou échouer lors de la sélection, même quand `-VisionCheck` renvoie deux bonnes couleurs. Un relevé `ollama ps` **pendant l'inférence du serveur 11435** ou des lignes `inference compute` / `library=Vulkan` de **ce processus** sont nécessaires. Après l'arrêt automatique, `ollama ps` vide est normal.
- **9,0 s ≠ accélération par rapport au CPU.** Les appels CPU QW-PERF-1B utilisaient **des prompts et schémas différents**, et un ordre/cache différents ; aucune comparaison appariée CPU/GPU, ni vitesse de traitement réaliste d'une image avec contexte/SQLite, n'a été faite.
- Pas de mesure du GPU%, VRAM, RSS, chauffe, qualité de conseil, ni latence p50/p95. Aucun contrôle d'identité ou sécurité motrice prouvé.
- L'ancien serveur habituel `11434` n'a pas été modifié par les commandes du lanceur décrites. Le retour arrière du serveur **temporaire** a été observé au premier essai ; la fin du **deuxième** est inconnue.

### Question unique avant d'aller plus loin

**Le serveur temporaire sur 11435 a-t-il réellement utilisé Vulkan GPU ?** Si la deuxième session tourne encore, dans une **autre fenêtre PowerShell** seulement :

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"  # seulement cette seconde fenêtre
ollama ps
```

Observer une ligne `PROCESSOR` indiquant GPU/Vulkan pendant l'inférence ; un résultat vide **après la fermeture du lanceur** ne répond pas à la question. Si la deuxième session est déjà achevée, transmettre sa fin (sans relancer) et consulter, si nécessaire, les journaux Ollama **filtrés par date et par processus** en supprimant les chemins privés. Les journaux anciens du 28/10 prouvent le **rejet iGPU de l'ancien serveur**, pas l'utilisation GPU du serveur temporaire du 29/10.

**Décision actuelle :** *test de vision synthétique réel sur serveur temporaire exécuté et réussi au moins une fois* ; *accélération GPU, stabilité comparative et réduction des 30 secondes : inconnues*. Les contrôles du lanceur sont **réutilisés**, sans nouvelle API, driver, modèle, quota, sous-module ni programme moteur. Toute nouvelle comparaison de performance nécessite ensuite **le même protocole QW-PERF-1 sur CPU et GPU, avec mesure CPU/GPU/RSS et arrêt/retour arrière borné**, non un score de couleur isolé.



## QW-PERF-1D — cause locale du repli CPU observée (logs du 28/10 reçus le 29/10)

**Preuve opérateur réelle, mais historique :** cinq lignes filtrées du fichier Ollama `server.log` sont horodatées **2026-10-28 09:11** ; leur transmission date du **29 octobre**. Elles décrivent la configuration de ce serveur du 28 octobre, sans prouver la configuration d'un nouveau processus Ollama ultérieur :

- `OLLAMA_VULKAN:true`, `OLLAMA_IGPU_ENABLE:` *(vide)* : Vulkan activé, sélection d'iGPU non activée dans ce processus.
- `dropping ROCm device ... no rocblas support for gfx target`, `gfx1152` : le backend **ROCm présent** ne peut pas charger ce target dans son inventaire ; **ne pas** suivre la suggestion `HSA_OVERRIDE_GFX_VERSION` et ne pas maquiller le type de GPU.
- `dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1`, `library=Vulkan`, `description=AMD Radeon(TM) 860M Graphics` : **preuve directe que Vulkan a découvert la Radeon 860M, puis qu'Ollama l'a écartée à cause du contrôle d'admission iGPU**. Ce cas est donc distinct d'un problème où Vulkan ne verrait *aucun* GPU (par exemple les symptômes de l'issue historique #14562).
- `inference compute id=cpu` et `total_vram=0 B` : repli CPU cohérent, confirmé séparément par `ollama ps` **100 % CPU** pendant les cinq consultations rapportées.

**Cause démontrée pour cette session :** le filtrage de l'iGPU Vulkan faute de `OLLAMA_IGPU_ENABLE=1`. **Encore inconnu :** si l'admission temporaire de la Radeon 860M produira réellement une inférence GPU fonctionnelle, correcte, plus rapide, stable et sobre en mémoire avec le 9B. Les gains et les traitements QW-1/QW-2 ne sont **pas testés**.

**Réutiliser d'abord l'existant :** `scripts/kwipi-vision-test.ps1` du dépôt épinglé possède déjà un test synthétique `-VisionCheck` (deux carrés rouge/bleu) et démarre un serveur **temporaire** sur `127.0.0.1:11435`, si ce port est libre, avec `OLLAMA_VULKAN=1` et **`OLLAMA_IGPU_ENABLE=1`** ; il arrête seulement le processus qu'il a lancé. Pas de changement de `11434`, pas de média réel, pas de SQL, pas de commande moteur ni de variable système persistante. Le lancer dans **une session PowerShell enfant** pour isoler les variables de processus :

```powershell
# Précontrôle : port temporaire libre ; sortie vide attendue.
Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue
# Si et seulement si le port est libre : essai borné de DEUX images synthétiques.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\kwipi-vision-test.ps1" -VisionCheck -Port 11435
```

**Observation attendue pour conclure :** pendant le test, dans une seconde fenêtre indépendante, `OLLAMA_HOST=127.0.0.1:11435` puis `ollama ps` doit afficher l'utilisation d'un GPU/Vulkan **et pas 100 % CPU**, les deux couleurs doivent être correctement reconnues, le serveur créé doit se fermer, aucune dégradation/erreur mémoire ne doit être apparue. Le serveur peut se replier sur CPU malgré l'option : **échec de l'hypothèse GPU**, pas une réussite. Les deux images et la latence du test ne sont pas équivalentes aux cinq profils QW-PERF-1B ; aucune comparaison chiffrée CPU/GPU ne sera affirmée sans les **mêmes stimuli et réglages**.

**Risques et retour arrière :** GPU intégré partage la RAM avec Windows, quantités de RAM/RSS/thermie et allocation encore inconnues ; possibilité de lenteur, échec Vulkan ou indisponibilité temporaire du modèle. Ne pas modifier pilote, DLL, installation Ollama, HSA override, variables globales, `robotd` ou F5-C ; si le test échoue ou bloque, **arrêter uniquement le serveur temporaire** (le lanceur le fait lors de la fin normale), conserver le serveur habituel `11434` intact, ne pas répéter à l'aveugle. Le test doit rester facultatif et sous supervision de l'opérateur.

**Références :** [GPU Ollama officiel](https://docs.ollama.com/gpu) ; [commentaire d'un mainteneur Ollama sur l'admission d'iGPU](https://github.com/ollama/ollama/issues/18672) (octobre 2026). Les options de la version installée et leurs effets doivent toujours être vérifiés sur **le vrai PC**, pas extrapolés depuis une issue tierce.

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

**Observation :** tous les appels réels ont réussi, mais la charge était au CPU ; version et GPU sont identifiés : **Ollama 0.40.12 / Radeon 860M / driver 32.0.22052.3**. La [liste GPU officielle Ollama Windows ROCm](https://docs.ollama.com/gpu) **ne mentionne pas la 860M** ; Vulkan offre une voie complémentaire et est normalement actif par défaut si le backend est disponible. L'[issue Ollama #14562](https://github.com/ollama/ollama/issues/14562) signale une non-détection **de la même Radeon 860M**, mais sous **Ollama 0.17.4–0.17.5**, et ne prouve pas que 0.40.12 est affecté. **Hypothèses concurrentes :** iGPU absent de la découverte Vulkan, composant backend non chargé, réglage serveur déjà existant, pilote Windows incompatible, ou autre problème. **Cette question a été tranchée pour le serveur du 28/10 par les journaux reçus le 29/10 (voir QW-PERF-1D ci-dessus) : Vulkan voit la 860M mais son admission iGPU est désactivée.** Le paragraphe suivant conserve le diagnostic historique initial.

**Diagnostic exclusivement en lecture seule, depuis PowerShell :**

```powershell
# Version / pilote déjà confirmés le 29/10/2026 ; ne pas répéter inutilement.
$log = Join-Path $env:LOCALAPPDATA "Ollama\server.log"
if (Test-Path -LiteralPath $log) {
    Get-Content -LiteralPath $log -Tail 1200 |
        Select-String -Pattern "ggml_vulkan|gfx1152|Vulkan|ROCm|GPU.*discover|GPU.*detect|inference compute|filtering device|total_vram" |
        ForEach-Object { $_.Line }
} else {
    "Journal serveur introuvable (vérifier le serveur Ollama Windows actif)."
}
```

**Précaution journaux :** la commande ci-dessus lit uniquement un fichier local et filtre des lignes GPU. Avant toute transmission, **supprimer chemins personnels, jetons, contenus de requêtes ou données sensibles** si présents. Les lignes sans correspondance ne prouvent pas qu'aucun GPU n'a été examiné ; consulter la rotation `server-#.log` seulement si nécessaire. La documentation officielle localise les journaux Windows dans `%LOCALAPPDATA%\Ollama\server.log` ([dépannage Ollama](https://docs.ollama.com/troubleshooting)).

Ne pas faire `ollama pull`, `setx`, `stop-process` global, `ollama stop` sur le serveur principal, mise à jour de pilote, remplacement de DLL, surcharge forcée ROCm, allocation VRAM ou second serveur **non isolé**. Un seul serveur **temporaire et supervisé sur 11435**, prévu dans QW-PERF-1D, est le seul essai facultatif proposé. **Critères d'échec :** versions non vérifiées, GPU non détecté, accélération sans amélioration de la qualité ou dégradation mémoire/fiabilité, suppression d'un service existant. **Retour arrière :** aucun réglage durable modifié dans ce lot documentaire ; si une expérimentation active est ensuite autorisée, faire un seul changement temporaire mesuré et restaurer l'environnement immédiatement après, avec témoin CPU.

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
