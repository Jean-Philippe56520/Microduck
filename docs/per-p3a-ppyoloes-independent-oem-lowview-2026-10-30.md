# PER-P3A — PP-YOLOE-s, qualité visuelle basse et contrat RKNN/mediad (PC uniquement)

**Porte 0 préenregistrée le 30/10/2026 AVANT toute inférence PP-YOLOE-s de ce lot.** Base `main@a93852bd9827a5d04aaa6276b2b67c46a2e0e6e5` ; gitlinks `microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` inchangés. Autorités : [plan d'action](plan-action.md), [perception OEM](perception-oem-rknn-2hz-plan-2026-10-29.md), [réemploi](development-reuse-protocol.md), [P2B](per-p2b-ppyoloes-rknn232-host-conversion-2026-10-30.md).

## Question utile et témoin existant

P2B #205 a **prouvé une conversion PC** du PP-YOLOE-s Rockchip en RKNN INT8 `rk3566`, **pas son identification sur caméra basse**. L'OEM `duck-detect/src/rknn.rs` rejette `n_output != 1`, `duck-detect::decode` traite uniquement `[1,5,N]` mono-classe et `mediad/src/detect.rs` appelle ce décodeur. L'ONNX candidat a **neuf sorties DFL 68 / classes 80 / auxiliaire 1**, trois résolutions 20/40/80 : remplacement direct impossible. Pas de modification OEM, poids, paramètres, gitlinks, moteurs ou modèle de production autorisée.

**Réutiliser** les mondes et la caméra `World/Body/Camera` MuJoCo épinglés, les deux fabricants d'oracle `sim_vis_d_new_scenes_f2_fixture._prepare_static_world` et `sim_ball_segmentation_gt._rig_scene/visible_geom_bbox`, le code de masque préflight SIM-VIS-F, le prétraitement/DFL/NMS **officiels** Rockchip (`examples/ppyoloe/python/ppyoloe.py` et `py_utils/coco_utils.py`), et `onnxruntime` CPU. Ne créer **aucun décodeur OEM** ou service caméra. Une petite étude sans effet et ses tests de refus servent à décider si l'adaptation serait utile ; pas de promesse de portage.

## Données et témoins gelés avant le chargement de l'ONNX

Cinq observations **statiques MuJoCo à caméra de tête OEM basse**, RVB et segmentation `mjOBJ_GEOM` du *même état figé*, réorientés comme les essais SIM-VIS précédents ; image `640x360` affichée, entrée modèle letterbox `640x640`. Ces scènes/poses ont été employées dans des études YOLOX ou préflights antérieurs : **elles sont indépendantes du candidat PP-YOLOE-s et de ses prédictions, mais ne constituent pas une nouvelle cohorte universellement inédite**. Aucun réglage de pose, modèle, seuil ou sélection après observation.

| Cas | Source OEM et géométrie de référence | Oracle attendu |
| --- | --- | --- |
| `flat_ball_ahead` | `scene_ball.xml` / `ball_geom`, préparation SIM-VIS-D à 0,62 m | Balle >=80 pixels |
| `s2_far_right_yaw105` | `scene_apartment.xml` / `ball_0_geom`, S2 SIM-VIS-C à 0,95 m et décalage +0,16 m | Balle >=80 pixels |
| `chair_near` | `scene_apartment.xml` / `liv_chair_seat`, tronc (-2,55 ; 0,05), yaw 0 | Fauteuil >=80 pixels |
| `vslam_pillar` | `scene_vslam.xml` / `vs_pil_r`, préparation SIM-VIS-D | Pilier >=80 pixels, sans catégorie COCO « pilier » |
| `flat_ball_behind` | `scene_ball.xml` / `ball_geom`, préparation SIM-VIS-D | **0 pixel balle** ; des objets d'autres classes peuvent rester visibles |

**Arrêt préalable :** taille/orientation du rendu, version/pin OEM, cohérence du masque, pose statique, oracle absent, positif <80 px, négatif contenant la balle : cas invalide, **aucune inférence sur ce cas** et aucun ajustement a posteriori. Les 5 cas sont tous traités dans le préflight ; si moins de 4 valides dont au moins un cas balle, la chaise et le négatif, arrêter **toute** l'inférence. Aucun fichier d'image, masque ou tensor n'est enregistré ou publié.

**Modèle unique :** PP-YOLOE-s ONNX officiel Rockchip SHA256 `af72d05b33723f6d18f9784f6bba8e593a5554f465f1800d7ad1ba1e33e38b8a`, 31 734 323 octets, URL du `download_model.sh` épinglé `rknn_model_zoo@837db8e992815ff8647eadb709f07067f4bc3a71`. Télécharger une fois via HTTPS autorisé, 128 KiB–64 MiB, erreur de SHA = **STOP**. Une seule inférence ONNX CPU par cas valide ; aucun téléchargement ni exécution du RKNN exporté en #205. Rockchip `OBJ_THRESH=0.25`, `NMS_THRESH=0.45` et letterbox noir inchangés ; ni réentraînement ni calibration de score. Vérifier que les 9 têtes sont exactement `(1,68,20/40/80,20/40/80)`, `(1,80,...)`, `(1,1,...)` dans l'ordre constructeur ; rejet sur non-fini/mauvaise forme.

**Métriques préannoncées** : chaque GT indépendante a `IoU>=0.50` avec au moins une détection de **la bonne classe COCO** (`sports ball` et `chair`) pour compter « localisée et reconnue ». Rapporter également le meilleur IoU d'une boîte **toute classe**, sans le confondre avec une bonne catégorie. Pour `flat_ball_behind`, compter toute prédiction `sports ball` comme alerte négative ; pas de taux générique FP sur le pilier, les objets réels ou les arrière-plans non annotés. Répertorier score, catégorie et rang sans identité. Durées hôte p50/p95 d'inférence et post-traitement uniquement ; **pas** de chiffres NPU, de 2 Hz RK3566, RAM/thermie ou `robotd` 50 Hz.

**Porte de sélection (à lire AVANT résultats) :** poursuivre l'étude d'un adaptateur OEM **seulement si 2/2 balles IoU50 de classe correcte + 1/1 chaise IoU50 correcte + zéro faux `sports ball` sur le négatif**, avec géométrie valide et licence des poids explicite. Sinon **candidat non choisi** ; ne pas adapter `mediad` ni optimiser sur ces vues. Un résultat positif reste un test de cinq *rendus simulés*, sans validation robot. CI verte = programme exécuté/tests de contrat positifs/négatifs passés, **pas** réussite de la porte de sélection.

## Audit licence et compatibilité provisoire

- [Rockchip rknn_model_zoo@837db8e](https://github.com/airockchip/rknn_model_zoo/tree/837db8e992815ff8647eadb709f07067f4bc3a71) : **code de démonstration** et dépôt sous Apache-2.0 ; le README PP-YOLOE référence l'ONNX binaire sur `ftrg.zbox.filez.com` et [PaddleDetection release/2.6](https://github.com/PaddlePaddle/PaddleDetection/tree/release/2.6/configs/ppyoloe). [PaddleDetection](https://github.com/PaddlePaddle/PaddleDetection) : code Apache-2.0.
- **Non vérifié** : licence attachée spécifiquement à ce binaire ONNX préentraîné, chaîne de droits de conversion/redistribution, SDK runtime binaire en firmware et obligations applicables. La seule licence Apache du dépôt source **ne prouve pas** la permission de republier les poids. **Ne pas publier ONNX, RKNN ni médias**, ne pas activer ou installer sur robot, aucune commercialisation présumée.
- [OEM épinglé `rknn.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-detect/src/rknn.rs) : une entrée, **une sortie seulement** ; `want_float=1` déquantifie une sortie avec SDK dans le pilote. Le RKNN PP-YOLOE a 9 sorties : il faudrait **réutiliser** la déquantification par runtime pour chaque tenseur, vérifier attributs/ordre/quantification/ABI réels, puis seulement brancher le décodeur constructeur 80 classes, préserver `uyvy` et convertir les boîtes en coordonnées du flux.
- [OEM `mediad/src/detect.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/detect.rs) sérialise `media.detections` **sans catégorie**, ce qui ne permet pas aujourd'hui d'envoyer les 80 catégories à Kwipi sans modification du contrat et accord spécifique. Son modèle est désactivé par défaut et `hz=2.0` est une cadence initiale future, pas une validation multicatégorie.
- L'amont OEM `main@e1b49bf20c5efcbe187553e7b2210ec3df2cd788` a les mêmes blobs `duck-detect/{lib,rknn}.rs` et `mediad/detect.rs` que le pin. **Retour arrière :** branche expérimentale supprimable, rien à reconfigurer ou restaurer sur le matériel.

## Statut

**Préenregistrement uniquement, aucune qualité PP-YOLOE-s mesurée dans cette note.** Un rapport d'exécution pourra compléter cette section sans modifier a posteriori les seuils, les scènes et les critères ci-dessus.
