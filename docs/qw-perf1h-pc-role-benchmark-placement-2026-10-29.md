# QW-PERF-1H — Banc PC du rôle Qwen 9B avec placement Ollama observé

**Date :** 29 octobre 2026. **Autorité :** [plan-action.md](plan-action.md). **Statut initial :** code candidat sur branche dédiée, tests PC-fixtures en CI à vérifier ; **aucun essai réel QW-PERF-1H encore exécuté sur le PC Windows**. Base : main@85b802b43034c1af1f679acc2186ef3607094d43, [PR #157 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/157). OEM épinglé documenté : microduck@942e58e3aa6dbb28e7037203fff11866122c7567 et microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3 ; gitlinks inchangés.

## 1. Observation → hypothèse → preuve → échec → risque / retour arrière

**Observation PC réelle QW-PERF-1G :** sur les deux mêmes images synthétiques rouge/bleu, le port temporaire 11435 (OLLAMA_VULKAN=1 + OLLAMA_IGPU_ENABLE=1 dans le processus enfant) a rapporté `gpu_memory_reported`, `size_vram=5614726020` octets, latences 8,343 et 8,891 s ; le 11434 habituel a rapporté `cpu_memory_reported`, `size_vram=0`, latences 10,735 et 11,343 s. Deux couleurs correctes, deux codes 0. La baisse descriptive moyenne de 21,94 % ne prouve **ni calcul GPU effectif, ni gain reproductible, ni conseil fiable**. [Rapport source](qw-perf1g-pc-gpu-cpu-color-comparison-2026-10-29.md).

**Question unique pour QW-PERF-1H :** sous les mêmes cinq profils cognitifs **synthétiques** de QW-PERF-1, les latences/tokens et les compteurs natifs Ollama sont-ils différents entre le serveur temporaire qui déclare de la mémoire GPU et le témoin CPU ?

**Hypothèse :** la résidence GPU déclarée peut être associée à une baisse des durées `load`/`prompt_eval`/`eval` sur les rôles Qwen v2 et JSON comparables. **Preuve visée :** cinq sorties par environnement avec les métriques Ollama natives et l'observateur `/api/ps`, sous contexte et limites identiques. On compare **par profil**, jamais la latence d'un JSON compact avec celle d'un rôle v2 long. Le premier appel peut être froid et les autres utiliser cache/keep_alive=2m ; l'étiquette `first` ne prouve pas un démarrage totalement froid.

**Échec / arrêt :** port temporaire occupé, serveur indisponible, modèle absent, statut rejeté/non disponible, sortie non valide, `placement=not_observed`, pression mémoire/thermie anormale, changement de modèle/driver ou inconfort de l'opérateur. Pas de boucle de répétition automatique. Les cinq appels sont un **maximum** par commande et ont une limite de temps par appel ; un échec peut laisser des profils restants dans le banc historique et impose donc une lecture prudente du statut de chaque profil avant toute nouvelle tentative. **Retour arrière :** ne pas activer `-PerfCheck` ni `--report-placement` ; le serveur éphémère `11435` est arrêté par le lanceur existant, `11434` n'est jamais arrêté ou modifié par cet outil. Aucune installation ou variable persistante.

## 2. Réutiliser / adapter / créer (OEM-first)

| Composant | Décision | Contrat et justification |
| --- | --- | --- |
| `qwen9b_perf_probe.py` de PR #151 | **Réutiliser et adapter minimalement** | Cinq profils déjà testés : `role_v2_first`, `role_v2_repeat`, `compact_text`, `compact_json`, `compact_json_mock_context`. Même JPEG synthétique cercle rouge 256×256 et mêmes systèmes de requêtes, `think=false`, `keep_alive=2m` uniquement dans le banc ; UUID de corrélation nouveaux à chaque profil, donc les requêtes JSON ne sont pas strictement identiques octet pour octet entre sessions. |
| `LocalOllamaModelSampler` de PR #156 | **Réutiliser** | GET `/api/ps` sur IP littérale loopback, 400 ms de cadence / timeout, résumé numérique ; échoue sans bloquer l'inférence. `size_vram` = mémoire GPU **déclarée**, pas calcul ni RSS indépendants. |
| `scripts/kwipi-vision-test.ps1` | **Adapter** | Ajouter `-PerfCheck -AuthorizeFiveSyntheticCalls` exclusivement sur 11435 et `-ReportPlacement` optionnel ; mêmes protections image privée / processus enfant / arrêt. Refuser serveur déjà en écoute sur ce port pour ne pas attribuer GPU à un serveur inconnu. |
| `OllamaEndpoint`, validation JSON F5, API `/api/chat` | **Réutiliser** | Pas d'autre client HTTP, aucune réponse brute dans le rapport ; statut `unverified` n'est jamais une qualité sémantique validée. |
| OEM `robotd` 50 Hz, `idle_head.rs` épinglé | **Ne pas toucher** | L'idle du constructeur est autonome vis-à-vis de Qwen ; aucun mouvement ou instruction motrice issue de cet essai. |
| QuackNav, Quacksat, microduck-twin, M9, modèles tiers | **Ne pas intégrer** | Aucun apport pour mesurer le 9B local. Aucun package, poids, firmware, driver ou sous-module ajouté. |

Le robot physique est absent ; ses paramètres actifs, ses ressources, les services OEM et son modèle ONNX exécuté **ne sont pas vérifiables depuis ce banc PC**. La simulation MuJoCo et la mémoire `ExperienceMemory` ne sont pas concernées.

## 3. Protocole Windows (seulement après PR fusionnée / contrôles verts)

L'opérateur dispose d'un worktree séparé `$HOME\Microduck-Qwen9B-GPU-Probe` ; le clone historique `Microduck-Qwen9B` porte des fichiers locaux indexés et **ne doit pas être réinitialisé**. Dans le worktree propre, lire `git status --short` et refuser toute bascule si non vide ; actualiser depuis `origin/main` sans toucher au clone historique.

**Précontrôles en lecture seule** dans PowerShell : vérifier Ollama 0.40.12 et GPU/driver connus (ne pas installer), modèle `qwen3.5:9b` présent sur 11434, port 11435 libre, assez de RAM/ressources et absence d'autre test. La comparaison doit utiliser **la même révision de code, les mêmes poids, paramètres et cinq profils**, l'ordre des serveurs reste séquentiel et non contrebalancé : aucun p50/p95 ni attribution causale de gain à une seule paire.

**Groupe G — serveur temporaire 11435, cinq consultations autorisées :**

```powershell
Set-Location "$HOME\Microduck-Qwen9B-GPU-Probe"
# Aucune sortie attendue ; sinon ne pas lancer.
Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\kwipi-vision-test.ps1" -PerfCheck -AuthorizeFiveSyntheticCalls -ReportPlacement -Port 11435
"Code de sortie GPU candidat : $LASTEXITCODE"
```

Le lancement crée un serveur local seulement si le port 11435 est libre, demande Vulkan et l'iGPU pour ce processus, collecte les cinq profils existants, puis arrête **uniquement ce serveur temporaire**. Une réponse numérique est affichée dans PowerShell, sans image ni génération de fichier. Si l'utilisateur interrompt l'essai, **vérifier en lecture seule** qu'aucun ancien serveur 11435 ne reste actif ; ne pas arrêter 11434.

**Groupe C — témoin serveur CPU habituel 11434, cinq consultations autorisées :**

```powershell
Set-Location "$HOME\Microduck-Qwen9B-GPU-Probe"
$py = Join-Path $HOME ".venv-qwen9b\Scripts\python.exe"
# Ne lancer que si 11434 existe deja, contient qwen3.5:9b et reste CPU.
& $py -m microduck_companion.qwen9b_perf_probe --run --authorize-five-synthetic-calls --ollama-port 11434 --timeout 120 --report-placement
"Code de sortie CPU temoin : $LASTEXITCODE"
```

**Ne pas exécuter ces commandes en automatique/CI :** elles font **dix appels réels maximum sur PC** (cinq par groupe) et exigent la présence/validation de l'opérateur. Pour garder la comparaison contrôlée, conserver la même révision, ne pas changer `num_ctx`, `num_predict`, GPU/driver, cache et prompt entre les deux groupes. Vérifier `cpu_memory_reported` sur le témoin, `gpu_memory_reported` sur le candidat ; ne pas convertir `not_observed` en CPU.

## 4. Interprétation attendue et limites

- Comparer **profil contre profil**, avec `wall_s`, `load_s`, `prompt_eval_s`, `eval_s`, `prompt_eval_count`, `eval_count`, `total_s` ; ces métriques peuvent être nulles en cas de réponse indisponible, ne jamais inventer des zéros.
- Les sorties JSON `compact_json*` sont vérifiables **uniquement** sur cercle rouge : `fixture_shape_color_match` ; les rôles v2 et texte sont simplement `status=unverified`, sans mesure de compréhension, hypothèse, prudence ni stratégie. La mémoire contextuelle est une phrase **fictive** ; aucune SQLite n'est consultée.
- `ollama_placement` indique une allocation mémoire GPU **rapportée**, et peut représenter de la RAM partagée pour la Radeon 860M. La **charge GPU de calcul, le RSS, le thermique et l'énergie restent à mesurer indépendamment** avant d'affirmer une accélération. Pas de démonstration d'un fonctionnement normal hors du test, ni de qualité multimodale robuste.
- Un seul couple séquentiel de groupes, ordre fixe et UUID aléatoires pour JSON : gain **exploratoire**, pas p50/p95, optimisation garantie, débit causal, vitesse de production ou aptitude à décider des actions Kwipi.
- Aucun serveur de production modifié, aucune mémoire, aucun média privé, aucun moteur ni auto-apprentissage ; `robotd` reste seul responsable de la sûreté 50 Hz.

## 5. Tests et fusion

Les tests `tests/test_qwen9b_perf_probe.py`, `tests/test_qwen9b_perf_placement.py` et `tests/test_ollama_device_placement.py` couvrent le dry-run sans réseau, l'opt-in du sampler, l'arrêt du sampler même après erreur, le refus de port LAN, les rapports numériques sans texte, l'autorisation PowerShell explicite, l'absence de téléchargement/variables persistantes et les tests existants. **La CI ne peut pas valider le vrai 9B, le GPU Radeon 860M, Vulkan ni la vitesse**. Fusion uniquement après checks GitHub verts ; puis revérifier le SHA `main` et guider l'opérateur, sans modifier la branche F5 historique.

**Classification :** prévu (essai réel PC sur cinq profils), codé (adaptation du banc et du lanceur, sous réserve CI), testé PC-fixtures (attente des checks), simulé OEM (non), validé robot (non).
