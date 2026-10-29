# QW-PERF-1 — Profilage prudent du vrai Qwen3.5 9B sur PC

**Addendum QW-PERF-1B (29/10/2026) :** [cinq mesures réelles opérateur sur `11434`](qw-perf1b-real-windows-9b-baseline-2026-10-29.md) avec 44,234 s initial / 14,750 s même rôle répété, 3,703 s texte court, 7,110 s JSON, 9,109 s JSON + contexte fictif. Ollama affichait `100% CPU` ; le GPU et les pilotes restent à identifier. **Aucune amélioration GPU mesurée, aucune mémoire SQLite, aucun robot.** Les passages historiques disant « performance non mesurée » sont antérieurs à cet addendum.


**Date :** 28 octobre 2026. **Statut :** banc PC codé et testé en CI, [PR #151](https://github.com/Jean-Philippe56520/Microduck/pull/151) fusionnée (`cf8bf760`), [CI Python #40786532440](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40786532440) et [N1 #40786532406](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40786532406) vertes ; vrai 9B non exécuté par la CI. **Autorité :** [plan-action.md](plan-action.md). Version de référence avant ce lot : `main@c87089d105ddffe36e247709ba27fc561ba377f7`, OEM épinglé `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, RL `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Revalider avant exécution et fusion.

## 1. Observation, hypothèses, preuve recherchée et risque

**Observation réelle rapportée par l'opérateur :** le rôle Qwen3.5 9B v2 a pris **30,203 s pour 186 tokens** sur Windows/Ollama, ventilés en chargement **4,103 s**, analyse de l'image et du prompt **11,398 s**, génération **14,671 s**. Un autre essai a pris **30,719 s pour 210 tokens**. Il ne s'agit ni d'un benchmark p50/p95, ni d'une mesure GPU/RSS validée, ni d'une mesure sur le Microduck. Le premier essai a aussi suggéré à tort `ground_pick` pour un chat : **le rôle v2 ne doit pas alimenter la motricité sans garde indépendante**. Voir [rapport v2](kwipi-qwen9b-role-contract-v2-2026-10-28.md).

**Hypothèses à tester sur le vrai PC :**

- Recharger inutilement le 9B peut contribuer à la latence ; le pilote v2 utilise `keep_alive=0`. Comparer une première requête et sa répétition avec le **même JPEG et le même prompt**, `keep_alive=2m`, sans **affirmer que la première est froide** si Ollama était déjà chargé.
- Générer une réponse plus concise et contrainte peut coûter moins de tokens/temps qu'une réponse française détaillée ; **la qualité du conseil reste à mesurer séparément**.
- Quelques souvenirs compacts en entrée peuvent accroître le coût `prompt_eval`, mais pas nécessairement de façon importante ; seule une mesure appariée répond.
- Les coûts d'image, d'encodage, du GPU et des transferts PC/robot ne sont pas déductibles des essais antérieurs.

**Preuve visée :** pour chaque variante, collecter les métriques natives Ollama (`load_duration`, `prompt_eval_duration`, `eval_duration`, `prompt_eval_count`, `eval_count`, `total_duration`) et la durée murale. Rapporter le statut de réponse et, seulement pour les profils JSON, la correspondance à la **forme/couleur de l'image synthétique connue**. La CI n'exécute jamais le modèle réel. Aucun résultat ne sera inventé.

**Échec bloquant :** appel réseau sans accord, connexion hors loopback, image personnelle ou import SQLite, sortie brute enregistrée, texte Qwen traité en permission moteur, échec JSON ignoré, requête infinie, installation cachée de modèle, maintien permanent non mesuré du modèle en RAM, confusion « 5 samples » avec p95. **Retour arrière :** ne pas utiliser le module `qwen9b_perf_probe` ; il n'est importé par aucune boucle de production, n'ouvre aucune base et ne change aucun composant OEM. Même F5-C, mêmes politiques et sous-modules.

## 2. OEM-first, réutilisation et comportement expressif

**Sources OEM épinglées relues :** `robotd/src/idle_head.rs` et `docs/robot/cheatsheet.md` documentent les mouvements **idle** : regards, cou, bec, légère inclinaison de tête **occasionnelle**, sans regard dirigé vers une catégorie d'objet. `robotd/src/intents.rs` conserve des intents atomiques et le deadman ; `docs/design/robotd-design.md` réserve la boucle motrice 50 Hz à `robotd`. `mediad/src/sensor.rs` distingue les variantes caméra IMX219/GC2093. RL épinglé : modèles et entraînement simulé, pas une validation robot. Les versions effectives, `robotctl version/health/policy list/monitor`, RAM et capteurs actifs restent **inconnus** (robot physique absent).

| Composant | Décision | Justification |
| --- | --- | --- |
| `qwen9b_role_preview.make_request` v2 | **Réutiliser** | Vraie consigne de référence, même image/prompt pour premier et second appel |
| `qwen9b_advisor_v2.prepare_jpeg` | **Réutiliser** | Images JPEG sans EXIF, plafonds F5, exclusivement synthétiques ici |
| `ollama_local_client.OllamaEndpoint`, `_strict_json` | **Réutiliser** | IP loopback validée, JSON sans clés dupliquées |
| Ollama `/api/chat` et compteurs natifs | **Adapter pour un seul diagnostic** | Collecte temps/jetons, rejet des réponses brutes, pas d'intégration robot |
| Mémoires `ExperienceMemory` / MEM-2A | **Ne pas ouvrir** | Contexte **fictif fixe** seulement pour isoler le coût du prompt ; QW-1 intégrera une sélection autorisée ultérieurement |
| `robotd IdleHead`, OEM head/idle | **Réutiliser à terme** | La gestuelle curieuse existe déjà ; aucune nouvelle commande moteur ici |
| QuackNav, twin, cerveau OEM #381, Quacksat | **Ne pas importer** | Inutiles pour mesurer le 9B sur PC, pas de changement de version épinglée |

**Comportement cible pendant Qwen :** Kwipi peut, si son contexte et sa sécurité le permettent, cesser de se déplacer et adopter une attention neutre/curieuse ; l'OEM `IdleHead` peut naturellement incliner la tête, sans promettre d'inclinaison à chaque appel. Le système local ne doit pas rester bloqué sur le réseau. Toute sélection volontaire d'une posture ciblée exigera une PR distincte avec contrat OEM, scène, stop, durée maximale et essais MuJoCo puis robot. Aucun geste « réflexion » n'est exécuté dans QW-PERF-1.

## 3. Banc PC créé : `qwen9b_perf_probe.py`

**Sans argument, aucun réseau.** Le script prépare **en mémoire seulement** un dessin synthétique 256×256 (cercle rouge sur blanc), via Pillow et le prétraitement F5 v2. Aucune image réelle ni souvenir personnel n'est lu. Les cinq profils sont demandés **uniquement après accord explicite** :

| Profil | Ce qui est comparé | Limite d'interprétation |
| --- | --- | --- |
| `role_v2_first` | Prompt complet v2, première exécution observée | Première requête ≠ démarrage froid certifié |
| `role_v2_repeat` | **Même** prompt/image/paramètres, après premier appel | Estimation de l'effet warm/chargement, sous même charge |
| `compact_text` | Instruction concise et réponse naturelle courte | Temps seulement, texte **jamais archivé ni exploité** |
| `compact_json` | Même image, sortie JSON fermée de forme/couleur | Seulement micro-qualité visuelle synthétique, **pas** sécurité/raisonnement |
| `compact_json_mock_context` | Même JSON et image, ajout de 200 caractères de contexte **fictif** | Coût du contexte sans lire la SQLite |

Le code laisse `think=false` et `stream=false`, modèle **qwen3.5:9b**, `num_ctx=4096`, `temperature=0`, réponse compacte plafonnée à **96 tokens**, v2 conservant son plafond de **320 tokens**. `keep_alive=2m` est une **option temporaire de ce banc**, pas un changement F5-C/production. Ollama libérera le modèle après inactivité ; si nécessaire, l'opérateur peut consulter `ollama ps` et arrêter le modèle par `ollama stop qwen3.5:9b`. Toute comparaison doit noter la charge GPU/CPU et la RAM du PC **séparément** ; ce banc ne mesure pas ces deux ressources.

**Commande d'inspection, sans inférence ni réseau :**

```powershell
py -3.12 -m microduck_companion.qwen9b_perf_probe
```

**Essai réellement autorisé sur le PC équipé de Qwen3.5 9B et d'Ollama local 127.0.0.1:11435 (cinq appels au maximum) :**

```powershell
ollama ps
py -3.12 -m microduck_companion.qwen9b_perf_probe --run --authorize-five-synthetic-calls --ollama-port 11435 --timeout 120
ollama ps
```

Dans les deux cas utiliser le Python/venv du clone Microduck avec `Pillow` déjà disponible ; aucune installation automatique, aucun `ollama pull`, aucun modèle alternatif. Ne pas exposer le port Ollama au LAN. Sortie : **statuts et nombres exclusivement**, sans image, transcript, texte du modèle, souvenir, identifiant personnel ou empreinte de média. Une réponse refusée peut quand même fournir des durées Ollama ; elle n'est jamais exploitable par Kwipi.

**Règles d'interprétation :** ne conclure ni vitesse cible, ni p50/p95, ni absence d'hallucinations depuis ces **cinq profils isolés**. L'ordre (premier, répétition, compact...) peut introduire un biais de chauffe/cache : si les premiers résultats sont intéressants, répéter ensuite des profils appariés, avec ordre alterné et scènes publiques indépendantes, toujours après consentement. Le contexte ajouté n'est **pas une lecture de SQLite** ; QW-1/QW-2 doivent traiter la recherche mémoire comme un lot distinct. Une sortie JSON valide n'est **pas une observation réelle vérifiée**, et un cercle artificiel ne représente pas une scène de robot.

## 4. Tests, critères de sortie et priorité

```bash
python -m unittest tests.test_qwen9b_perf_probe -v
python -m unittest discover -s tests -v
```

Tests positifs et négatifs : dry-run sans réseau/image, opt-in obligatoire, borne de cinq appels, endpoint non-loopback refusé, mêmes pixels et mêmes prompts pour la répétition v2, requête JSON compacte, faux outil/texte motorisé/JSON à clés dupliquées/requête périmée refusés, zéro fuite de texte et métriques nativement chiffrées. **Ces tests font tourner des fixtures et des faux Ollama : aucune performance 9B n'est mesurée en CI.**

**Suite proposée après QW-PERF-1 :**
1. Une vraie exécution opérateur sur son PC Ryzen AI/64 Go avec cinq requêtes synthétiques et observables ; relever séparément `ollama ps` / occupation GPU, RSS et vérifier la sécurité thermique du PC.
2. Reprofiler la **même question** sur scènes publiques consenties et réponses structurées très courtes : métriques p50/p95 et qualité/abstention indépendantes ; comparer d'abord sans puis avec un contexte mémoire **expurgé** de QW-1.
3. Décider du `keep_alive` opportun, de la taille optimale du prompt/image et du volume de réponses ; mesurer le coût des recherches mémoire et des allers-retours QW-2.
4. **QW-EXPR-1**, distinct : arrêt et expressions/idle OEM pendant consultation non bloquante, sur simulation et avec toutes les portes de sûreté. Pas d'essai moteur au hasard.

**Statut honnête :** QW-PERF-1 = **code de mesure PC fusionné, tests CI verts sur fixtures**, Qwen réellement exécuté dans ce lot = **non**, posture interrogative synchronisée = **prévue uniquement**, robot = **absent**.
