# Cat-A2b-R — contre-annotation aveugle locale, sans validation automatique

**28/10/2026 · Lot Cat-A2b-R candidat**. Code `microduck_companion/cata2b_blind_review.py` et tests sur images JPEG **entièrement générées**, sans photos privées, vrais annotateurs, caméra robot, inférence de modèle, SQLite, Qwen ou commandes moteurs. [Issue prioritaire #78](https://github.com/Jean-Philippe56520/Microduck/issues/78). [Plan directeur](plan-action.md) et [protocole Cat-A2b](cata2b-private-low-camera-protocol-2026-10-26.md).

## 1. Porte : constat, hypothèse, preuve, risque et retour arrière

**Observation (référence du 27/10) :** les 29 JPEG privés pris à 20–30 cm déclarés ont produit 66 propositions YOLOX, mais les 50 boîtes V3 ont été ajustées après connaissance des prédictions du modèle ; 12 sont ambiguës. Elles ne constituent **pas** une vérité terrain indépendante. Les 29 photos proviennent d'un seul site présumé ; distinguer des sessions au sein d'un site ne garantit pas l'indépendance des scènes. Le protocole existant `cata2b_private_low.py` vérifie SHA, dimensions JPEG, hauteur **déclarée**, consentement **déclaré**, split lieu/séance/scène et boîtes, mais un booléen `all_targets_reviewed` n'atteste pas l'indépendance de l'annotation.

**Hypothèse testable :** un contrôle de deux nouvelles annotations **déclarées aveugles** sur le même ensemble TEST peut isoler les désaccords avant l'évaluation et empêcher de traiter silencieusement V3 comme une vérité établie. Il ne prouve jamais que les relecteurs étaient distincts, ne regardaient pas les prédictions ou ont mesuré la hauteur optique.

**Preuves attendues :** un rapport agrégé sans chemins, SHA, sample IDs, textes libres ou boîtes privées ; accord/désaccord à IoU ≥ 0,50, **même catégorie ET même visibilité**, association un-à-un non gloutonne ; négatifs communs, incertitudes et divergences avec les boîtes préexistantes signalés. Les faux doublons, annotations manquantes, revue non déclarée aveugle, valeurs hors vocabulaire, géométries invalides, lien symbolique, digest falsifié, contenu hors TEST, fuite de split et tentative sans consentement doivent être refusés. **Une bonne concordance ne débloque PAS le benchmark ni C3** : l'indépendance et les corrections restent à confirmer humainement.

**Risque / critères d'échec :** mêmes annotations copiées entre deux fichiers, deux sessions inventées, auteur influencé par V3, hauteur de caméra présumée valide, site non indépendant, récompense causale ou publication d'une donnée privée. Indicateurs toujours faux : `reviewer_independence_authenticated`, `blindness_to_predictions_authenticated`, `ground_truth_adjudicated`, `benchmark_authorized_by_this_review`, `c3_generalization_validated`. Si une incertitude ou une divergence subsiste, résoudre **localement à partir des originaux**, jamais des propositions du modèle. **Retour arrière :** retirer le module, les tests et ce document ; aucune migration, capture ou modification OEM.

## 2. OEM / tiers : réutiliser avant de créer

| Source examinée | Décision | Limite |
| --- | --- | --- |
| OEM épinglé `microduck@942e58e3` : `duck-detect/src/lib.rs` | **Réutiliser uniquement comme référence** | Détecteur mono-classe des autres Microducks (RKNN) ; pas de détecteur général `cat/dog/chair` |
| OEM `mediad/src/main.rs`, `robotd` | **Ne pas brancher** | `mediad` possède la caméra ; sa signalisation locale ne doit pas devenir une exposition des JPEG privés. `robotd` reste propriétaire moteur, 50 Hz |
| RL `microduck_rl@b02fdea4`, OEM PR #381/#414/#450 | **Ne pas modifier ni importer** | PR ouvertes à la vérification ; aucune n'apporte un corpus annoté à 25 cm |
| `cata2b_private_low.py` | **Réutiliser tel quel** | Contrôle existence, SHA, JPEG, hauteur déclarée, partitions étanches train/validation/test, catégories/boîtes |
| `cata2_bbox_eval.iou`, `MATCH_IOU`, `Box` | **Réutiliser** | IoU50 d'origine ; comparaison annoteur/annoteur, pas AP50 détecteur |
| C1/C2/C3-A, registre QuackNav/Twin/Smartulf/Quacksat | **Ne pas brancher** | Aucune scène indépendante ni preuve causale ; pas de second écrivain SQLite ni import tiers |
| Petit vérificateur local Cat-A2b-R | **Créer** | Deux fichiers JSON opaques de contre-annotations ; pas de nouvelle boucle caméra, moteur, réseau, DB ou modèle |

## 3. Contrat des deux fichiers privés

Les JPEG, preuves de règle et manifeste Cat-A2b normal demeurent exclusivement dans un dossier local privé ignoré par Git. Créer **deux nouveaux fichiers** dans `reviews/`, à partir des originaux et **sans montrer les sorties YOLOX ni les annotations V3**. Chacun comporte exactement un enregistrement pour chaque image du **TEST**, identifié par l'ID opaque et le SHA-256 du manifeste initial. Ne pas copier-coller les annotations de l'autre relecteur.

Exemple **partiel et fictif**, non utilisable seul (il faut tous les TEST, des hachages réels conservés localement et deux fichiers distincts) :

```json
{
  "schema_version": 1,
  "source": "declared_blind_manual_test_review",
  "role": "first",
  "review_session_id": "g-0000000000000901",
  "blind_to_model_predictions_declared": true,
  "manual_independent_review_declared": true,
  "samples": [
    {
      "sample_id": "s-0000000000000003",
      "image_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "boxes": [
        {"category": "chair", "xyxy": [10, 20, 35, 55], "visibility": "partial"}
      ],
      "all_targets_reviewed": true,
      "uncertain": false
    }
  ]
}
```

Pour une personne ou un animal visible uniquement sur une TV, affiche ou photographie, ne pas transformer la détection en présence physique ; marquer \`uncertain: true\` en attendant une annotation de provenance écran/monde réel séparée (issue #95). L'outil ne peut pas certifier ce contexte visuel.\n\nLe second fichier utilise `role: "second"` et un autre `review_session_id` opaque ; il ne contient **ni identité, prénom, texte, commentaire, chemin, URL, origine GPS, visage extrait ou preuve personnelle**. `boxes: []` signifie qu'aucune des cinq classes cibles n'est annotée ; une scène ambiguë doit avoir `uncertain: true`. Les deux relectures sont des **déclarations**, non des certificats d'indépendance. Ne pas réétiqueter V3 comme première relecture aveugle.

Commande locale **sous Linux/Ubuntu WSL** (les imports des outils Cat-A existants utilisent \`resource\` Unix), lecture seule après revue explicite des droits et du dossier. Le programme n'a pas été testé dans un interpréteur Python Windows natif :

```bash
python -m microduck_companion.cata2b_blind_review \
  --manifest .local_visual_data/cat-a2b/manifest.json \
  --review-first .local_visual_data/cat-a2b/reviews/r-0000000000000001.json \
  --review-second .local_visual_data/cat-a2b/reviews/r-0000000000000002.json \
  --approved-private-local-media
```

Le résultat JSON n'indique **que des compteurs agrégés** : images TEST revues, accords, négatifs en accord, désaccords, incertitudes, boîtes appariées, différences de chaque relecture par rapport au manifeste historique (ce dernier n'est pas un relecteur indépendant). Aucune décision automatique sur la « vérité » ; en cas d'incertitude, il faut un arbitrage humain distinct, puis de nouvelles scènes disjointes avant d'interpréter les scores Cat-A2b.

## 4. Exécution et limites

- **Tests CI prévus :** JPEG artificiels, confusion classe, visibilité, boîtes éloignées, plusieurs instances et permutation, incertitude, mêmes tokens de session, refus de déclaration aveugle, texte privé, hors TEST, SHA, géométrie invalide, JSON ambigu, chemin extérieur ou symlink, leakage train/TEST, consentement absent, zéro réseau/SQLite/moteur.
- **Tests matériel :** aucun. Pas de capteur Microduck, RKNN, CPU/RSS/thermie du RK3566, consommation, contrôles temps réel ni navigation. Ressources PC non mesurées par ce lot.
- **C3-B reste bloqué :** cet outil n'évalue ni un détecteur sur vraies annotations indépendantes ni l'utilité de C1/Qwen. L'étape suivante nécessite deux relectures réellement indépendantes, une résolution externe des divergences et des sites/scènes distincts, sans fuite et hors Git. Ne pas entraîner ni choisir un seuil sur TEST.
- **Audit confidentialité :** la validation locale existante recharge les JPEG pour vérifier SHA/dimensions, aucune image ou résultat individuel n'est envoyé, stocké ailleurs ou imprimé. Ne jamais lancer de capture réseau locale `mediad` pour cette tâche.

Le protocole complète le dossier [Cat-A2b privé](cata2b-private-host-ort-exploratory-2026-10-27.md) sans effacer les limites des anciennes métriques exploratoires. [PR #118](https://github.com/Jean-Philippe56520/Microduck/pull/118) ouverte à cette rédaction ; [CI Python #40707844533](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40707844533) réussie (1 554 tests, 5 ignorés, zéro échec), dont 19 nouveaux scénarios Cat-A2b-R. Fusion à vérifier.
