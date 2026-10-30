# PER-P5 — Porte matérielle simulée YOLO26n et YOLO26n-seg / RK3566 (préenregistrement, 30/10/2026)

## Objectif
Vérifier, **avant toute adaptation OEM**, si les deux poids officiels déjà évalués en PER-P4 peuvent être convertis en INT8 RKNN pour `rk3566`, s'ils exécutent une inférence sur le simulateur RKNN hôte, et quel coût additionnel (fichiers, sorties, décodeur) impose la segmentation. Cela **ne mesure pas** la RAM, le NPU, l'énergie ou 2 Hz du vrai robot. Aucune nouvelle photo de test visuel requise.

## Référence et écart prouvé
Baseline Companion `main@1e8d83d155a7ee19b03cc2fe188469ab4d429272`, OEM épinglé `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` inchangés ; OEM `duck-detect/src/rknn.rs` refuse `n_output != 1`, `mediad/src/detect.rs` décode la tête mono-classe et ne transporte aucun masque. `PER-P2B/#205` a réellement converti PP-YOLOE-s avec `rknn-toolkit2 2.3.2` sur PC, pas ces modèles. `PER-P4/#214` est une PR ouverte, non fusionnée ; 300 JPEG COCO/900 inférences CPU, masques > rectangles sur 98,36% des 487 régions appariées, mais aucun test RKNN.

## Sources immuables
`ultralytics==8.4.192`, modèles `yolo26n.pt` SHA256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef` et `yolo26n-seg.pt` SHA256 `361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f`, asset `v8.4.0`. Fournisseur export `onnx` puis `ultralytics.utils.export.rknn.onnx2rknn` **inchangés**. Toolkit/Rockchip `rknn-toolkit2@42aa1d426c0a9e0869b6374edba009f7208a1926` (2.3.2), même version de famille que runtime OEM rapporté, sans certifier ABI. Échantillon 20 JPEG COCO public du `rknn_model_zoo@837db8e992815ff8647eadb709f07067f4bc3a71`, `datasets/COCO/coco_subset_20.txt`, sans copie publique. Environnement Linux x86_64 Ubuntu 22.04, Python 3.10, CPU Torch 2.4.0 (contrainte fournisseur SDK 2.3.2 : <=2.4.0), `onnx==1.16.2`, `imgsz=640`, batch 1, ONNX opset 19, `quantize=8`; aucune retouche de poids, modèle ou seuil après résultat.

## Deux essais identiques, un passage chacun
1. Avant modèle : contrôler SHA du HEAD, gitlinks, SHA poids, versions, calibration publique 20/20 ; arrêter sur source absente/invalide. Tester la forme syntaxique du protocole séparément.
2. Dans deux jobs indépendants (détection, segmentation) : export ONNX officiel avec `YOLO(...).export(format="onnx", imgsz=640, opset=19, simplify=False, dynamic=False)`; vérifier entrées/sorties puis appeler `onnx2rknn` officiel en INT8 (head dérivé du modèle) avec les 20 images. Une tentative unique de conversion par modèle, `timeout` ; aucune rétrogradation opportuniste, FP16 de secours ni réglage.
3. Si conversion : empreintes et tailles du RKNN et de `tail.onnx`, liste/dimensions sorties ONNX et détail coût de décodeur, sans publier binaires. Simulateur `rknn.init_runtime()` local (sans cible NPU physique), puis `rknn.inference` sur une entrée RGB synthétique déterministe 640² ; contrôler présence, nombre de sorties, dimensions, toutes valeurs finies, durée hôte et pic RSS processus. Les tests de vision, de précision et de masque demandent des GT et ne sont **pas** revendiqués par cet essai. Des données synthétiques ne mesurent pas la qualité de détection.
4. Comparer les deux rapports. Pas de déploiement, modification de `robotd`, `mediad`, `duck-detect`, SDK Yocto, `upstream/`, Qwen ou SQLite. Artefact JSON uniquement ; aucun poids, JPEG, masque ni modèle RKNN/ONNX publié.

## Critères de passage/arrêt fixés
- **Porte conversion** pour chaque candidat : `load_onnx`, `build` et `export_rknn` réussis, RKNN non vide et <128 Mio, provenance des poids et du toolkit vérifiée. Conversion qui échoue = `conversion_failed`, aucune correction de code tiers ou rerun opportuniste dans ce lot.
- **Porte simulation** : `init_runtime` et inférence hôte terminent correctement avec sorties non vides et finies. Si le simulateur/SDK échoue : `simulation_failed_or_unavailable`, sans conclure à une incompatibilité du robot.
- **Comparaison** : tailles de fichiers, nombre de tenseurs et coût CPU/RSS hôte relevés ; **pas** de seuil trompeur de 1 Go ou 2 Hz sur le runner. Surcoût seg > détecteur = diagnostic, pas échec fonctionnel. Si tous deux passent, `host_conversion_and_simulation_passed` mais `robot_compatibility_unknown`.
- **Décision** : segmentation potentiellement utile pour contours/couleur/mémoire (résultat P4), sans preuve de connaissance ni objets inconnus. Ne choisir aucun poids embarqué tant que licences AGPL/Enterprise (droits code/poids), budget RK3566/1 Go, caméra, 2 Hz, décodage CPU et sûreté OEM 50 Hz ne sont pas vérifiés. Si conversion échoue des deux côtés, arrêter et passer à un autre jalon ; ne pas ajouter d'infrastructure.

## Retrait
Branche expérimentale isolée, suppression/revert possible ; aucune mutation de matériel, mémoire, sous-module ou données privées.

## Historique du préflight, avant tout modèle (30/10/2026)
- CI initiale #41093941644 **arrêtée à l'import SDK**, NumPy 2.2.6 ayant remplacé 1.26.4 et cassé l'ABI SciPy ; 0 conversion. Trois négatifs des fixtures échouaient en testant le SHA du faux poids avant la calibration.
- CI suivante #41094836705 : NumPy fixé, mais `pip check` a démontré `torch 2.4.1 > 2.4.0` supporté par `rknn-toolkit2 2.3.2`, et absence de `tqdm`. Aucun modèle/poids exécuté ou résultat consulté : correction limitée au préflight avec `torch 2.4.0` et `tqdm 4.66.4`, paramètres et critères de conversion inchangés. Ce n'est ni un échec ni une preuve de compatibilité RK3566.
