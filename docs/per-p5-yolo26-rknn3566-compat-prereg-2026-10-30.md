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

## Résultat P5 initial — constat au 30/10/2026 avant P5-SIM1
[CI #41095173416](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41095173416) : deux ONNX `opset 19` réellement exportés à 640², YOLO26n **9,4 Mo ONNX** (poids PyTorch 5,3 Mo), YOLO26n-seg **10,6 Mo ONNX** (poids 6,4 Mo). Deux `load_onnx`, `build` INT8 et `export_rknn` officiels ont retourné 0 ; logs **« rknn building done »**. Sur le détecteur, `load_rknn` avait ensuite retourné 0, mais `init_runtime()` a échoué `-1` : le toolkit 2.3.2 explique qu'**un RKNN rechargé ne peut être inféré sur son simulateur hôte**, qui exige l'instance ayant fait `load_onnx + build`. Sur `-seg`, la bibliothèque Ultralytics 8.4.192 échoue **après export RKNN** : `onnx.utils.extract_model` signale `KeyError: 'output1'` lors du découpage de `tail.onnx`. **Aucun `tail.onnx` validé, aucune inférence simulée, pas de mesure robot.**

Valeurs hôte de compilation **non extrapolables** : pics RSS de processus 613 156 Kio (détection) / 671 136 Kio (seg), qui mélangent Python, Torch, compilateur et fichiers ; **ne représentent ni RAM résidentielle embarquée ni taille du RKNN ni coût NPU**. La CI Python indépendante [#41095173868](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41095173868) est verte. Ce bilan est un **succès de compilation**, non un essai de bout-en-bout.

## P5-SIM1 — protocole complémentaire gelé AVANT l'essai (justifié par le message SDK)
**Manque prouvé :** le script initial utilisait `load_rknn → init_runtime()`, voie déclarée impossible sur simulateur hôte par Rockchip 2.3.2. Il est légitime de tester **une fois** la seule voie indiquée par ce SDK : `config → load_onnx → build INT8 → export_rknn → init_runtime → inference` **sur la même instance**. Ce n'est **pas** une nouvelle étude qualité, ni un réglage de modèle. La voie officielle Ultralytics de préparation des sorties convoitées est reproduite à l'identique dans la sonde hôte et sa provenance AGPL est citée ; SDK Rockchip, modèles/empreintes, ONNX 640² opset 19, dataset officiel 20 photos et seuils de sortie inchangés. Aucun `load_rknn` hors NPU ni nouveau décodeur.

- **Objectif positif** par modèle : `build` INT8 et `export_rknn` retournent 0, modèle 0 < taille < 128 Mio, puis `init_runtime()` sur **le même objet** réussit, et **une** inférence sur un tableau RGB synthétique 640² génère des sorties finies, non vides, avec dimensions/nombre consignés ; relever temps hôte d'un seul échantillon, RSS global de processus, tailles ONNX/RKNN/tensors. Cette entrée synthétique ne démontre **aucune** précision.
- **Témoin négatif préfixé :** refuser poids/empreinte/calibration non conformes ; refuser sorties/cropping impossibles, retour SDK non zéro, nombre nul ou NaN. Ne pas remplacer un résultat absent par une sortie synthétique fabriquée.
- **Masques :** `-seg` doit exposer les têtes et prototypes (référence sortie `output1`), mais **le décodeur complet `tail.onnx` reste non validé**. Ne pas corriger l'erreur Ultralytics dans ce lot ni prétendre avoir reconstruit des masques ou mesuré un gain cognitif.
- **Arrêt :** une seule construction et une seule inférence par modèle, sans diminuer `imgsz`, changer de SDK, modifier quantification/sources ou répéter selon les résultats ; en cas d'échec, `simulation_failed` avec cause exacte et STOP. Si l'essai passe, `host_simulation_passed` **sur PC seulement** ; le coût NPU/RAM/2 Hz/50 Hz/thermie sur vrai RK3566 demeure inconnu, droits AGPL/Enterprise et interface OEM toujours non validés. Aucun modèle publié.

## Résultats définitifs P5-SIM1, 30/10/2026 — sortie brute seulement

**Preuve :** [CI P5 #41095986462](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41095986462), deux jobs **succès**, [suite Python #41095986450](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41095986450) **succès** (tests positifs et négatifs inclus). SHA de branche testé `daec1db5306e9036850488129f75151d85c4eae6`. Environnement Linux Ubuntu x86_64, `rknn-toolkit2 2.3.2`, Torch CPU 2.4.0, Ultralytics 8.4.192, ONNX opset 19, 20 images de calibration Rockchip officielles, **une seule compilation et une seule simulation synthétique par modèle** dans P5-SIM1 ; seules statistiques JSON publiées. `upstream/` inchangés.

| Mesure mesurée sur PC / SDK simulé | YOLO26n | YOLO26n-seg |
|---|---:|---:|
| Taille ONNX (octets) | 9 894 053 | 11 165 280 |
| Taille RKNN INT8 (octets) | **6 934 946** | **8 019 237** |
| Construction+export RKNN, processus hôte (s) | 11,920 | 15,766 |
| Sorties brutes, nombre de tenseurs | **6** | **10** (9 têtes + prototype `output1`) |
| Sorties brutes matérialisées en float32 par le simulateur (octets) | **2 822 400** | **7 174 400** |
| Une inférence synthétique simulateur x86 (ms) | **459,63** | **668,18** |
| Pic RSS du processus hôte incluant Torch et compilateur (Kio) | **674 640** | **727 308** |
| `init_runtime` même instance et sorties finies | **oui** | **oui** |
| `tail.onnx` / construction de vrais masques | **non testée** | **non validée (erreur officielle `output1` au P5 initial)** |
| Robot RK3566 / NPU, mémoire Yocto, 2 Hz, 50 Hz, chaleur | **inconnu** | **inconnu** |

**Delta constaté :** `-seg` ajoute **1 084 291 octets de binaire RKNN (+15,6 %)**, et **4 352 000 octets de sorties float32 simulées** (+154,2 % de sorties). Les quatre sorties supplémentaires incluent la branche de coefficients de masque et la carte de prototypes `[1,32,160,160]` ; leur décodage, NMS et l'extraction fiable des contours ne sont pas exécutés. Le temps 668,18 ms est **une inférence du simulateur x86**, **PAS un débit NPU de 1,5 Hz** ; on ne peut le comparer à la cible 2 Hz embarquée. Le pic RSS total du processus Python/compilation n'est **pas** la RAM consommée par un service Rust sur Microduck. Les tailles float32 ne sont ni la taille des sorties quantifiées du pilote ni un pic réel de mémoire NPU.

**Porte franchie :** `YOLO26n` et `YOLO26n-seg` sont compilables en **RKNN ciblé rk3566** avec le SDK fournisseur 2.3.2 et produisent des **sorties numériques valides dans son simulateur hôte**. Pas d'inférence sur puce, pas de comparaison quantifiée contre vérité terrain, pas de preuve de décodage de masque utilisable ou de catégories inconnues, pas de caméra/robot. Les fichiers RKNN (hashs conservés dans les rapports numériques), modèles ONNX, JPG et images ne sont pas publiés.

**Décision 30/10 — avancer sans détour :** `YOLO26n-seg` demeure candidat cognitif conditionnel après la preuve P4 (masque > rectangle sur 98,36 % des régions déjà appariées) et non un modèle adopté. `YOLO26n` est témoin de moindre coût. **Un seul obstacle logiciel concret à traiter si `-seg` est retenu :** l'extraction `tail.onnx` du fournisseur (`KeyError: 'output1'`) et son décodage complet avec coûts CPU/masques ; **ne pas créer de second service vidéo/SQLite**. Vérifier licences code+poids AGPL/Enterprise et interface constructeur une sortie avant toute modification OEM ; sur matériel futur mesurer NPU/quantification, RAM/RSS, 2 Hz, températures et l'impact éventuel sur `robotd` 50 Hz. En attendant : **pas de nouvel entraînement, pas de centaines de photos ni de nouveau sous-module**.

**Maintien de la traçabilité des échecs :** les premières CI ont échoué à l'installation NumPy, aux fixtures puis à `load_rknn` sur simulateur et à `tail.onnx` sur `-seg`, ce qui ne constitue pas un échec d'inférence NPU. Ces événements restent référencés ci-dessus et aucun score ne leur est attribué.
