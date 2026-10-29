# QW-QUAL-2A-P2 — Import volontaire des quatre JSON originaux depuis le presse-papiers Windows

**29 octobre 2026 — outil de récupération opérateur sur PC, sans consultation du vrai Qwen, sans évaluation humaine réalisée.** Base auditée : `main@82872244a71ec45fbb5000a77432a506e54059b9`, [PR #170](https://github.com/Jean-Philippe56520/Microduck/pull/170) fusionnée (CI Python et N1 vertes). Autorité : [plan-action.md](plan-action.md). Réutilise le [paquet QW-QUAL-2A-P1](qw-qual2a-private-packet-preparation-2026-10-29.md) et le [protocole aveugle](qw-qual2a-blind-independent-human-review-protocol-2026-10-29.md).

## 1. Problème et porte de preuve

**Observation vérifiée :** quatre appels `qwen3.5:9b` ont été déclarés sur le PC de l'opérateur pour `scene_a/b/c/d` ; QW-QUAL-1F conserve des **résumés** et compteurs, pas les quatre textes intégraux. Le banc initial annonçait `model_text_saved_by_probe=false` : **aucun JSON d'origine n'est prouvé archivé sur disque**. Il est possible que les quatre sorties complètes restent consultables dans les anciens messages ChatGPT ou dans une transcription PowerShell volontaire, mais **cela n'a pas été confirmé sur le PC**. L'historique standard PSReadLine conserve d'abord les commandes et ne saurait être présenté comme une archive certaine des sorties.

**Hypothèse de travail :** si une sortie JSON complète est encore visible à l'opérateur, celui-ci peut la copier **exactement** (sans résumé, sans code fence, sans commande PowerShell) et l'importer hors dépôt sans re-saisir ou réinventer les mots de Qwen.

**Preuve visée / critères d'échec :** contrôle strict du `case_id`, du tag Qwen, du rôle v2, de `study`, de `status=unverified`, du texte complet, du blocage machine, des compteurs à zéro et du budget 32 768 octets ; échec fermé si autre scène, HTML/Markdown, sortie coupée, mauvaise révision, objet JSON à clés répétées, presse-papiers indisponible, dossier Git, doublon ou fichier déjà présent. **Un JSON conforme ne prouve PAS l'identité du vrai modèle, la provenance historique du texte ou la correction sémantique.** Le coordinateur doit attester la fidélité de la copie et conserver son contexte de source.

**Risque / retour arrière :** le presse-papiers Windows contient potentiellement des informations sensibles. Il n'est lu **qu'après** `--capture-clipboard-case` + `--authorize-private-source-write` ; rien de son contenu n'est imprimé, envoyé au réseau, à GitHub, à Qwen, à robotd ou à SQLite. Le fichier local est créé une seule fois, sans remplacement, et les répertoires Git sont refusés. En cas de refus, rien n'est écrit dans le dossier de destination ; après capture, la suppression éventuelle doit être décidée **manuellement** par l'opérateur, sans nettoyage automatique. Les permissions POSIX `0o700/0o600` sont indicatives et ne garantissent pas les ACL Windows ni le chiffrement : choisir un emplacement **local non synchronisé**, accessible uniquement à l'opérateur.

## 2. Procédure minimale sur le PC Windows (aucun appel Ollama)

Après mise à jour du dépôt, ouvrir PowerShell **dans la racine du dépôt Microduck**, avec son Python déjà préparé pour le banc. Exemple utilisant le Python de l'environnement existant :

```powershell
$py = Join-Path $env:USERPROFILE ".venv-qwen9b\Scripts\python.exe"
$src = Join-Path $env:LOCALAPPDATA "Kwipi-QW-Originals"
$dst = Join-Path $env:LOCALAPPDATA "Kwipi-QW-Review-2A"
```

Retrouver **la réponse JSON entière** de `scene_a` dans la conversation d'origine ou dans une sortie PowerShell réellement conservée. Sélectionner uniquement l'objet JSON complet, le copier dans le presse-papiers Windows. Puis lancer :

```powershell
& $py -m microduck_companion.qwen9b_blind_review_packet --source-dir "$src" --capture-clipboard-case scene_a --authorize-private-source-write
```

Reprendre la même opération manuelle pour `scene_b`, `scene_c` et `scene_d` (une copie de presse-papiers **distincte**, avec le bon `case_id` et les deux mêmes drapeaux d'autorisation). Un texte absent ou mal copié provoque un refus ; **ne pas** remplacer une sortie par une génération Qwen nouvelle, un extrait GitHub ou une paraphrase du chat. Si le fichier existe déjà, l'outil refuse de l'écraser ; revoir son contenu localement avant de poursuivre.

Après les **quatre** imports, lancer d'abord le précontrôle **strictement en lecture seule** :

```powershell
& $py -m microduck_companion.qwen9b_blind_review_packet --source-dir "$src"
```

Si les quatre JSON sont valides, créer uniquement sur accord de l'opérateur le paquet neuf (dossier `$dst` **absent**) :

```powershell
& $py -m microduck_companion.qwen9b_blind_review_packet --source-dir "$src" --output-root "$dst" --write-private-packet
```

**Ne partager avec le relecteur que `$dst\REVIEWER_SHARE_ONLY`**, après contrôle de `READY.txt`. Ne jamais transmettre `COORDINATOR_PRIVATE`, les JSON opérateur, les chemins locaux, les analyses historiques ou le dossier parent. Un « 4/4 » **ne signifie pas** que les réponses sont authentifiées ni évaluées. Ne jamais pousser ces fichiers dans GitHub. Le dossier peut contenir des propos non vérifiés du conseiller et doit être lu comme tel.

Si le Python `.venv-qwen9b` se trouve plutôt sous la racine Microduck, adapter seulement la variable `$py` à **l'environnement déjà utilisé**. Un Windows sans Tcl/Tk/accès presse-papiers renverra « clipboard unavailable » ; ne pas installer de dépendance ou contourner une protection par cette procédure. L'exécution réelle Windows **n'a pas été effectuée** dans cette PR.

## 3. Réutiliser / adapter / créer et essais

| Choix | Source | Décision |
| --- | --- | --- |
| **Réutiliser** | `qwen9b_blind_review_packet._valid_report`, `_safe_absolute_directory`, `collect_reports`, `make_packet` | Même contrôle de quatre sources que QW-QUAL-2A-P1 ; pas de deuxième format ou banc |
| **Adapter** | CLI existant : `--capture-clipboard-case` + `--authorize-private-source-write` | Capture **une seule scène**, validation avant écriture, aucun écrasement |
| **Créer seulement** | `_read_clipboard_text` (Tk standard lib à l'appel explicite) et six tests PC-fixtures à presse-papiers **mocké** | Aucun service, socket, journal, recherche automatique dans les fichiers privés, modèle, deuxième SQLite, moteur ou réseau |
| **Ne pas importer** | QuackNav, microduck-brain, Twin, Quacksat, détecteur ou nouveau LLM | Aucune pertinence pour retrouver des textes historiques, duplication/sûreté non justifiées |

**Tests visés :** six nouveaux tests positifs/négatifs + sept tests historiques du paquet. Vérifier l'ensemble via la CI Python et N1 sur la PR ; les fixtures **ne prouvent pas** le comportement réel du presse-papiers sous Windows. Cas négatifs : copie tronquée ou Markdown, mauvais cas, champ de sécurité altéré, dépassement 32 Ko, destination Git, consentement absent, doublon, chemin existant.

**OEM épinglé et inchangé :** `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` (`robotd` 50 Hz, [politiques](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/policy-channel-design.md), [robotctl](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md), [intentions/deadman](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/intents.rs)) ; `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. OEM #450 encore ouverte au contrôle ; aucune version, policy list, température, scène ou caméra du robot réel disponible. Quatre sorties PC historiques ≠ perception, motricité ou effet validé.

**Après ce lot :** `QW-QUAL-2A: independent_review_pending` tant que **les quatre avis d'un humain extérieur non exposé** ne sont pas reçus ; le codage et les tests PC ne substituent pas cette preuve. **QW-QUAL-2B après 2A**, conformément au plan directeur, et QW-QUAL-2C seulement si justifiée.
