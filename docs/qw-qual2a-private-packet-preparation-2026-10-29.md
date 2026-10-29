# QW-QUAL-2A-P1 — Paquet local de relecture aveugle (préparation, sans évaluation réalisée)

**Date :** 29 octobre 2026. **Autorité :** [plan-action.md](plan-action.md). **Base vérifiée :** `main@2ea26193cc9531ceefa6c276c9756ebab2e8bbab` après [PR #169 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/169) et contrôles Python/N1 réussis. **Statut :** utilitaire PC candidat / tests sur fixtures ; **aucune source privée reçue, aucun paquet réel produit, aucune contre-annotation indépendante**. Voir le [protocole QW-QUAL-2A](qw-qual2a-blind-independent-human-review-protocol-2026-10-29.md) et la [grille vierge](qw-qual2a-independent-review-worksheet-2026-10-29.md).

## 1. Observation, hypothèses, preuve recherchée et arrêt

**Observation :** les quatre réponses `scene_a/b/c/d` proviennent de consultations réelles déclarées par l'opérateur sur PC, mais le générateur QW-QUAL-1A indiquait `model_text_saved_by_probe=false`. Les rapports GitHub de QW-QUAL-1F **ne conservent pas les quatre textes intégralement**. Une analyse à partir de paraphrases ne serait pas une contre-annotation des sorties originales. Le robot physique est absent.

**Hypothèse vérifiable de ce lot logiciel uniquement :** si l'opérateur possède encore les quatre JSON **exacts** de la console, on peut constituer un dossier de quatre stimuli et quatre réponses complètes, pseudonymisées et séparées d'une table privée, sans jamais appeler Qwen, créer une seconde mémoire ni piloter `robotd`.

**Preuve recherchée :** test positif sur quatre JSON de fixtures distincts, test négatif sur source absente/tronquée, mauvais modèle/version, doublons, drapeaux d'autorisation, entrée dans le dépôt Git, sortie déjà existante, chemin relatif, correspondance exposée. **L'outil vérifie la cohérence du format, pas l'authenticité historique cryptographique des textes** : le coordinateur doit attester leur provenance.

**Critère d'arrêt :** si l'un des quatre JSON originaux ou son champ `advisor_text_for_human_only` manque, **refus** ; ne pas recréer une sortie en relançant Qwen ni en reprenant un résumé GitHub/chat. Si un relecteur a déjà lu les conclusions, sa relecture n'est pas aveugle. **Retour arrière :** n'effacer, si nécessaire et manuellement, que le dossier de sortie *nouvellement créé* ; ne rien modifier dans les sources, le dépôt, les poids ou le robot.

## 2. Utilitaire livré — hors ligne et sans effet par défaut

**Code candidat :** [`qwen9b_blind_review_packet.py`](../microduck_companion/qwen9b_blind_review_packet.py) ; [tests adversariaux](../tests/test_qwen9b_blind_review_packet.py). Il réutilise **directement** `qwen9b_semantic_quality.make_synthetic_png` (quatre dessins originaux 320×240), `CASE_IDS`, les constantes du rôle v2 et le budget du garde. Aucune bibliothèque nouvelle, service, CLI OEM, réseau, caméra, SQLite, GPU, modèle, sous-module, policy ou moteur.

Sur **Windows PowerShell**, depuis la racine du dépôt à jour, après avoir déposé manuellement, **hors du dépôt Git**, les quatre sorties JSON exactes dans un dossier personnel (noms imposés `scene_a.json`, `scene_b.json`, `scene_c.json`, `scene_d.json`) :

```powershell
$src = Join-Path $env:USERPROFILE "Kwipi-QW-Originals"
$dst = Join-Path $env:USERPROFILE "Kwipi-QW-Review-2A"

# Toujours commencer en lecture seule. Aucun dessin ni fichier cree.
python -m microduck_companion.qwen9b_blind_review_packet --source-dir "$src"

# Seulement apres controle explicite des quatre JSON complets.
# Dossier destination neuf ; commande qui ecrit uniquement des medias synthetiques.
python -m microduck_companion.qwen9b_blind_review_packet --source-dir "$src" --output-root "$dst" --write-private-packet
```

Si `python` pointe vers un environnement sans Pillow, utiliser **l'environnement Python existant du banc Qwen** ; ne pas installer automatiquement de modèle, paquet ou composant sur le robot. L'exécution réelle Windows et les entrées originales de l'opérateur **restent à vérifier**.

**Conditions d'entrée :** quatre JSON séparés, `study=QW-QUAL-1A-PC-synthetic-human-review`, `model=qwen3.5:9b`, `role_version=kwipi-qwen9b-role-v2-candidate`, `status=unverified`, texte complet de 1 à 1200 caractères, `quality_score=null`, `machine_use=blocked`, `physical_actions_authorized=false`, `robot_validated=false`, compteurs moteurs/mémoire/photos privées à 0. Aucun texte libre de réponse n'est imprimé sur stdout par cet outil. Attention : `unverified` qualifie seulement la réception, **pas** la qualité.

**Sortie à destination inédite hors Git :**

| Chemin relatif | Contenu | Destinataire |
| --- | --- | --- |
| `REVIEWER_SHARE_ONLY/R01..R04.png` | Même générateur des quatre dessins originaux, ordre mélangé | Relecteur externe |
| `REVIEWER_SHARE_ONLY/R01..R04.txt` | Textes intégraux **des JSON fournis**, sans reformulation | Relecteur externe |
| `REVIEWER_SHARE_ONLY/BLIND_REVIEW_FORM.txt` | Questions C1–C8 vierges, avertissement de prudence et attestation d'indépendance | Relecteur externe |
| `REVIEWER_SHARE_ONLY/READY.txt` | Créé en dernier ; dossier incomplet en son absence | Coordinateur, puis relecteur |
| `COORDINATOR_PRIVATE/mapping.json` | Correspondance Rxx / scene_x ; empreintes SHA-256 des entrées, textes et PNG **non probantes d'authenticité** | Coordinateur seulement |
| `READ_THIS_PRIVATE.txt` | Règles de confidentialité et de transmission | Coordinateur seulement |

**Partager seulement `REVIEWER_SHARE_ONLY` après contrôle de `READY.txt`**. Ne jamais partager le dossier parent complet, la correspondance, les quatre JSON source ou les anciennes analyses ; ne pas publier le paquet dans GitHub, ChatGPT, un dépôt de fichiers public ou une CI. Les permissions de dossier `0o700` sont une précaution POSIX, **pas une preuve de chiffrement ni de protection ACL Windows**. L'opérateur reste responsable du canal d'envoi et de l'accord du relecteur.

## 3. Indépendance et qualification

La permutation aléatoire et les identifiants R01–R04 **réduisent un biais de présentation**, mais ne prouvent ni l'indépendance humaine, ni l'authenticité du source. Un relecteur doit répondre avant d'accéder à QW-QUAL-1B/C/D/E/F, déclarer toute exposition antérieure et citer de courts éléments du texte/image. Le coordinateur garde les annotations d'origine intactes et n'effectue la comparaison avec QW-QUAL-1F qu'après leur clôture.

**2A est encore ouvert scientifiquement** tant que les quatre grilles datées et l'attestation extérieure ne sont pas effectivement obtenues. Les quatre scènes sont **déjà vues** par l'équipe : ne jamais les recycler comme *holdout* inédit pour un prompt v3. **Selon `plan-action.md`, 2B (scènes inédites) vient après cette porte**, et 2C reste conditionnel.

## 4. Matrice réutiliser / adapter / créer et limites OEM

| Choix | Source inspectée | Portée |
| --- | --- | --- |
| **Réutiliser** | [QW-QUAL-1A](../microduck_companion/qwen9b_semantic_quality.py), `qwen9b_role_preview.MODEL/ROLE_VERSION_V2`, `qwen9b_action_guard.MAX_PREVIEW_CHARS` | Générateur synthétique et validation de forme ; jamais de relance Qwen |
| **Adapter** | [QW-QUAL-2A](qw-qual2a-blind-independent-human-review-protocol-2026-10-29.md), grille C1–C8, séparation coordinateur/relecteur | Emballage local de preuves **déclarées** |
| **Créer seulement** | Un petit module Python de paquet et tests sans dépendance nouvelle | Aucun second juge, modèle, mémoire, planning ni commande moteur |
| **Ne pas importer** | QuackNav, microduck-brain, Quacksat, Twin, OEM M9 non livré | Inutiles pour la relecture indépendante ; risques et duplication évités |

**OEM épinglé consulté :** [`robotd` 50 Hz](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/robotd-design.md), [`intents` et deadman](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/intents.rs), [`policy-channel`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/policy-channel-design.md), [`robotctl`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md). Gitlinks observés : `upstream/microduck@942e58e3` ; `upstream/microduck_rl@b02fdea4`, tous deux **inchangés**. OEM PR #450 **ouverte, non fusionnée au contrôle**. Robot absent ; version, health, policy list, moteurs/caméra/sol/ONNX actifs, horloges et températures du **robot réel inconnus**, sans incidence sur ce paquet PC sans mouvement.

**Résultats à ne pas confondre :** prévu = réception des JSON historiques et revue extérieure ; codé = utilitaire PC candidat ; testé PC-fixtures = tests locaux et CI si verts ; simulé OEM = non ; validé robot = non. Le paquet n'ajoute aucun taux de qualité Qwen, effet, apprentissage, navigation, observation active ou autonomie.
