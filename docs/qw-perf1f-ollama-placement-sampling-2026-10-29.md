# QW-PERF-1F — Échantillonnage automatique du placement mémoire d'Ollama

**Date :** 29 octobre 2026. **Statut :** code candidat PC/fixtures, CI à vérifier, **aucun nouvel essai réel** dans ce lot. **Autorité :** [plan-action.md](plan-action.md). Base initiale de branche : Companion main 7df0adc05007b1591546307d34031e0a0dd76965 ; OEM épinglé upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567 et upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3. Vérifier SHAs/PR/CI avant toute reprise.

## 1. Observations et question unique

- L'opérateur a mesuré un Qwen3.5 9B **100 % CPU** sur Ollama Windows 0.40.12, AMD Radeon 860M, pilote 32.0.22052.3. Le profil QW-PERF-1B a donné **44,234 s** rôle v2 initial, **14,750 s** sur le même prompt répété et **7,110 s** pour JSON synthétique ; autres résultats et limites : [rapport PC](qw-perf1b-real-windows-9b-baseline-2026-10-29.md).
- Les journaux du 28/10 prouvent que le backend Vulkan a **détecté Vulkan0 Radeon 860M**, puis l'a **écartée** faute de OLLAMA_IGPU_ENABLE=1 ; le ROCm livré refuse gfx1152. **Aucune commande HSA override** n'est acceptable.
- Le lanceur Windows OEM/Companion existant scripts/kwipi-vision-test.ps1 active **OLLAMA_VULKAN=1** et **OLLAMA_IGPU_ENABLE=1** pour le serveur **temporaire** 127.0.0.1:11435 ; un premier appel de deux fixtures a reconnu rouge et bleu en **9,079 s et 9,031 s**, puis arrêté le serveur. Un second lancement a seulement été partiellement communiqué. **Aucune preuve de placement GPU**, les journaux du serveur principal du 29/10 ne contenant aucune ligne de sélection GPU utile.
- **Question unique :** pendant le test temporaire sur 11435, Ollama déclare-t-il une partie du modèle dans la mémoire GPU ?

**Hypothèse :** le GPU intégré autorisé peut être retenu par Ollama ; **preuve recherchée :** /api/ps retourne pour qwen3.5:9b des size_vram positifs pendant l'inférence. **Échec possible :** pas de modèle visible, serveur indisponible, size_vram nul, couleur incorrecte, instabilité ; **aucun de ces cas ne permet de déclarer une accélération**. **Risques :** petite charge de sondage HTTP local (≈2,5 requêtes/s), sélection de GPU intégré partageant la RAM du PC, secondes d'inférence supplémentaires. **Retour arrière :** supprimer l'option -ReportPlacement (rien n'est activé par défaut) ; le serveur temporaire existant demeure responsable de son arrêt, le serveur habituel sur 11434 est inchangé. Aucun réglage Windows persistant ni téléchargement.

## 2. Réutiliser / adapter / créer

| Composant | Décision | Motif |
| --- | --- | --- |
| scripts/kwipi-vision-test.ps1 | **Adapter minimalement** | Conserve -VisionCheck et l'arrêt du serveur temporaire ; ajoute -ReportPlacement facultatif, refusé sans -VisionCheck |
| microduck_companion/qwen9b_vision_check.py | **Adapter minimalement** | Réutilise exactement les deux JPEG synthétiques, la validation JSON, les timeouts et quotas PC du pilote existant |
| microduck_companion/ollama_local_client.py | **Réutiliser** | OllamaEndpoint IP littérale loopback et parseur JSON sans clés dupliquées |
| API officielle GET /api/ps | **Réutiliser**, lecture seule | Expose la liste des modèles chargés ainsi que size et size_vram ; [documentation Ollama](https://docs.ollama.com/api/ps) |
| microduck_companion/ollama_device_placement.py | **Créer uniquement le petit moniteur nécessaire** | Le lanceur n'avait pas la capacité de lire /api/ps pendant la requête bloquante ; thread de diagnostic daemon borné, pas de second modèle/serveur |
| robotd/idle_head et intents OEM | **Ne pas toucher** | Aucun robot ni contrôleur moteur dans l'essai |
| QuackNav, cerveau tiers, entraîneur/sim RL | **Ne pas importer** | Aucune fonctionnalité pertinente manquante pour une lecture /api/ps |

L'observateur ne change ni le protocole Qwen, ni la mémoire, ni le réseau sortant : uniquement GET /api/ps vers 127.0.0.1, réponses plafonnées à 24 576 octets, timeout socket 400 ms, sondage plafonné à 1 024 itérations, cadence 400 ms, thread daemon stoppé avec délai borné et aucune sortie brute. Si le service ne répond pas, l'inférence existante continue **sans dépendre du sondage**.

## 3. Plan de preuve / exécution

**Avant tout essai :** confirmer branche Windows main à jour, aucune modification locale à écraser, port 11435 libre, Ollama 11434 habituel inchangé ; ne pas demander un nouvel essai si le deuxième lancement QW-PERF-1E tourne encore.

**Contrôle sans inférence :** exécuter la CI et les tests de fixtures ; aucune connexion à Ollama réel ne doit être faite en CI.

**Un unique test actif, opérateur présent et port temporaire libre :**

\`\`\`powershell
# Depuis le clone Microduck-Qwen9B, sur main à jour.
Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\kwipi-vision-test.ps1" -VisionCheck -ReportPlacement -Port 11435
\`\`\`

Ce sont **les mêmes deux consultations synthétiques autorisées** (rouge et bleu). -ReportPlacement demande uniquement la surveillance simultanée : aucune photo fournie, aucune base, aucune commande moteur. Si le précontrôle retourne une ligne, **ne pas lancer**, d'abord identifier le processus existant. Si des signes de surcharge ou d'instabilité apparaissent, arrêter **uniquement le serveur temporaire créé pour l'essai**, pas Ollama 11434 ; aucun ajustement GPU supplémentaire dans ce lot.

**Rapport numérique attendu** sous la clé ollama_placement, sans texte de modèle ni données privées :

- placement = gpu_memory_reported, max_reported_vram_bytes positif : mémoire GPU **déclarée** par /api/ps pour ce tag Qwen durant les appels, **pas** une preuve d'utilisation des unités de calcul, de la Radeon exacte, ou de gain de vitesse.
- placement = cpu_memory_reported, model_samples > 0 et max_reported_vram_bytes = 0 : aucun placement GPU déclaré dans les **échantillons** observés ; repli CPU plausible, mais ne pas extrapoler à tous les appels.
- placement = mixed_samples : différents échantillons ont rapporté avec et sans mémoire GPU ; investiguer avant de conclure.
- placement = not_observed : modèle jamais observé chargé ; **inconnu, et non CPU**. Un modèle peut être déchargé dès la fin d'un appel à cause de keep_alive=0.
- Toujours gpu_compute_independently_verified=false et gpu_speedup_measured=false : seule une comparaison CPU/GPU appariée sur même entrée, sorties sûres et mesures de ressources réelles pourra valider le bénéfice.

**Aucune capture du résultat Ollama brut, des listes d'autres modèles, ni identité utilisateur n'est publiée**. Les champs d'erreur sont des compteurs et catégories bornées ; ne pas y mettre de chemins privés.

## 4. Tests et critères de fusion

Tests positifs/négatifs dans tests/test_ollama_device_placement.py : fake HTTP sur localhost, vrai serveur HTTP fictif, taille/VRAM valides et invalides, réponse vide, autres modèles, JSON dupliqué, corps surdimensionné, mauvais content-type, timeout, refus de LAN, ports invalides, modèle absent ≠ CPU, arrêt du sondage sans perturber l'inférence, exception non divulguée, flag Windows facultatif et réservé à -VisionCheck. Les tests existants de visions/couleurs et de compatibilité du lanceur sont conservés.

\`\`\`bash
python -m unittest tests.test_ollama_device_placement tests.test_qwen9b_vision_check -v
python -m unittest discover -s tests -v
\`\`\`

CI de PR + inventaire wheel verts avant fusion ; **aucun résultat GPU réel n'est testé par CI**. L'utilitaire ne crée pas de nouvel acteur en boucle moteur, aucune action OEM, aucune écriture SQLite, aucun nouveau modèle ni port public. Après fusion, vérifier CI post-fusion et documenter le SHA final. Pour tout test en dehors de ces fixtures, robot absent, version de robotctl/ONNX/sécurité sur robot inconnue, aucune simulation moteur ni validation matérielle revendiquée.
