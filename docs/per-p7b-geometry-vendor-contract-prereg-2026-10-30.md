# PER-P7b — Géométrie des masques à la frontière de l'image (préenregistrement, 30/10/2026)

## Décision, faits et manque vérifié

**V1 sur PC avant robot :** le noyau Rust P7 existe dans `main@879a7f11ed7abf821c79b92241db1df385abf880` et a 7 tests synthétiques verts + cross-check ARM64 ; il n'est connecté ni au runtime RKNN ni à `mediad`, ni à une SQLite. Aucun moteur, capture ou arbitrage ajouté.

**Résultat négatif préservé :** PER-P8 [PR #218](https://github.com/Jean-Philippe56520/Microduck/pull/218), [CI #41104491069](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41104491069), fermée sans fusion : RKNN et décodage de masques officiels réussis sur un JPEG public de calibration ; le noyau Rust a **refusé** les mêmes tenseurs avec `InvalidBox`. Cette erreur agrège une boîte inversée, non finie ou des coordonnées hors cadre : **le sous-type concret n'a pas été journalisé** et reste inconnu. Aucune parité numérique n'est revendiquée, aucune nouvelle analyse/compilation de ce modèle ni photo prévue dans ce lot.

**Écart logiciel prouvé indépendant du cas P8 :** le noyau Rust P7 rejette toutes les boîtes dont une coordonnée sort du `[0,640]`. Le fournisseur officiel épinglé, `ultralytics==8.4.192` (AGPL, ne pas copier le code), dans `ultralytics/utils/ops.py::crop_mask` accepte des coordonnées hors image et applique le recadrage par comparaison de pixels de la carte. Il peut donc traiter un objet partiellement hors champ ; P7 ne le peut pas. Ce contrat n'est pas un nouvel entraînement ni une décision de déploiement.

## Hypothèse, risque et adaptation minimale

**Hypothèse indépendante à éprouver sur fixtures synthétiques :** pour une boîte `xyxy` de surface strictement positive, finie, possiblement partiellement ou entièrement hors du repère modèle `640×640`, le masque doit être projeté uniquement sur les cellules de `160×160` qui appartiennent à l'intersection entre boîte et image. Conserver les quatre coordonnées brutes en métadonnées pour que les consommateurs sachent qu'elles peuvent dépasser le cadre ; la géométrie n'est pas une localisation du robot. Ne jamais allouer hors du masque fixe. **Ne pas assimiler une boîte entièrement hors champ à un objet détecté sur l'image** : son masque doit contenir zéro pixel et sa connaissance demeure incertaine.

**Réutiliser :** `rust/kwipi-seg-mask-core/src/lib.rs`, ses 7 tests, `cargo test` et le workflow Rust P7 déjà fusionné. **Adapter seulement :** `checked_box` pour ne plus refuser *uniquement* le dépassement de cadre ; maintenir le rejet `NaN/Inf`, boîte inversée/non strictement positive, classe fractionnaire/hors COCO, score invalide, tenseur malformé, max 10 masques et sortie < ou = 256 000 octets par image. L'algo de crop `x >= x0, x < x1, y >= y0, y < y1` ne change pas ; il assure déjà la restriction à la grille 160.

## Critères préfixés avant code

- **Positif A (bord gauche)** : boîte `[-40,80,200,240]`, coefficients/prototypes uniformes `1` sur le canal 0, score 0,9, classe 32, attend exactement **2 000 pixels vrais** dans `x=0..49, y=20..59`, tous les autres à zéro, métadonnées `[-40,80,200,240]` conservées.
- **Positif B (bord inférieur droit)** : boîte `[600,600,680,680]`, attend exactement **100 pixels vrais** `x=150..159, y=150..159`, aucune sortie hors tableau.
- **Négatif informatif C (totalement hors image)** : boîte `[700,700,800,800]`, sortie d'un **masque entièrement vide**, `foreground_pixels=0` ; ne pas compter comme reconnaissance d'un objet.
- **Négatifs de sûreté inchangés** : `NaN/Inf`, géométrie inversée ou de surface nulle, score/classe invalides, entrées de tailles erronées => erreur explicite sans conversion. L'ordre des lignes de type `end2end` demeure celui du fournisseur (pas de tri de score).
- **Passage logiciel** : tests P7 existants + A/B/C + négatifs verts, `cargo fmt`, `clippy -D warnings`, et `cargo check --target aarch64-unknown-linux-gnu` verts dans CI. **Arrêt** en cas de divergence de l'une des valeurs préfixées. Ne pas ajuster des seuils après résultat, ne pas essayer le JPEG P8 à nouveau pour obtenir un résultat favorable, ne pas toucher aux poids, aux licences ou à l'OEM.
- **Portée** : cela valide **une fonction Rust sur des boîtes synthétiques**, et non la cause exacte du `InvalidBox` de P8, la parité du modèle ni la validation NPU/thermie/2 Hz. Les prérequis de déploiement (droits des poids Ultralytics AGPL/Enterprise, entrée caméra OEM, synthèse des sorties RT `tail.onnx`, comportement de `robotd` 50 Hz) restent inconnus et ne sont pas contournés.

## Retour arrière

PR isolée, un prédicat de géométrie et des tests seulement. Aucun gitlink `upstream/` modifié ; pas de média, modèle, Qwen ou SQLite publié.
