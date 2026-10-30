# SIM-VIS-E — objets divers et occultation physique OEM, préenregistrement

**30 octobre 2026 — cas et critères fixés avant inférence sur ce lot.**
Base exacte : \`main@9baa6497147da1828e685032198c051c5b16a7b1\`.
OEM \`microduck@942e58e3aa6dbb28e7037203fff11866122c7567\`, simulation \`microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3\`.
Autorité : \`docs/plan-action.md\`, \`docs/development-reuse-protocol.md\` et PER-OEM-0.

## Valeur, témoin, réemploi

Manque **attesté** : SIM-VIS-D localise la balle OEM \`scene_ball.xml\` (IoU 0,931) mais ne propose *aucune* région sur un pilier pourtant visible (94 576 pixels GT). Il ne démontre donc aucune généralisation de régions à des formes inconnues. Le besoin de Kwipi n'est pas « détecter les balles du test » mais disposer de **régions potentiellement intéressantes**, avec possibilité de rester inactif sans prétendre identifier l'objet.

Réemployer **inchangés** : \`World/Body/Camera\` du \`microduck_rl\` épinglé, \`visible_geom_bbox\`, \`prepare_image\`, \`validate_model_file\`, \`decode_candidates\` top1/3/5 (seuil score 0,25/NMS 0,50), \`mock_f2_from_regions\` de SIM-VIS-D (fixture uniquement). Pas de modèle, seuil, nouveau pilote, caméra, base de données, moteur ni source OEM modifiés. Les vues sont nouvelles, les modèles de mondes OEM **déjà connus** : il ne s'agit pas d'un jeu indépendant de maisons réelles.

## Cas gelés avant inférence

Les coordonnées ci-dessous concernent la position en mètres du tronc MuJoCo **statique**, et non une position estimée du robot réel. La correction d'orientation de la caméra demeure OEM. Toute modification suivante pour obtenir un score est interdite.

| Cas | Monde OEM | Pose et cible constructeur | Attendu de l'oracle géométrique |
|---|---|---|---|
| A \`box_corridor\` | \`scene_apartment.xml\` | robot (0,0), yaw +90° ; \`obj_0_geom\` rouge, boite OEM 7 cm placée **0,52 m devant la caméra**, sur le sol | ≥80 px |
| B \`chair_living\` | \`scene_apartment.xml\` | robot (-2,90 ; 0,05), yaw 0° ; fauteuil **fixe** \`liv_chair_seat\` | ≥80 px |
| C \`pillar_yellow\` | \`scene_vslam.xml\` | robot (1,90 ; -4,10), yaw +90° ; pilier constructeur \`vs_pil_y\` | ≥80 px |
| D \`ball_beside_chair\` | \`scene_apartment.xml\` | robot (-2,90 ; 0,05), yaw 0° ; \`ball_0_geom\` à (-1,70 ; 0,45) sur sol, à côté du fauteuil | ≥80 px |
| E \`ball_behind_chair\` | \`scene_apartment.xml\` | même robot ; \`ball_0_geom\` à (-1,70 ; 0,05), **derrière** \`liv_chair_seat\` | **0 px balle**, **≥80 px fauteuil**, rayon caméra→centre balle heurtant le fauteuil avant la balle |

Le cas E est un témoin **d'occultation physique**, distinct du « derrière la caméra » de SIM-VIS-D. Sa preuve est indépendante du réseau : masque MuJoCo et \`mj_ray\` à l'état figé. Si le rayon et le masque ne corroborent pas la géométrie prévue, l'essai est **invalide**, pas « occultation réussie ».

## Contrat de mesure et arrêt

À partir du même état immobile \`MjData\`, capturer RGB + segmentation géométrique (aucun \`mj_step\`), redresser comme l'OEM. Ne jamais transmettre les geom-IDs, la vérité terrain, les couleurs nominales ni un nom d'objet à F2. Mesurer pixels cible, boîtes GT, régions top1/top3/top5, **meilleur IoU à 0,50**, scores et cadence *hôte seulement*. Les propositions hors boîte GT ne sont **pas** automatiquement de faux objets : le décor contient d'autres géométries.

**Porte fixée AVANT mesure :** géométrie valide dans les 5 cas, **≥1/3 nouvelles cibles non-ballons (A/B/C) localisées en top3 avec IoU≥0,50**, et **≥2/4 cas positifs localisés** au total (A/B/C/D). Le cas E doit prouver **physiquement** l'occultation. Si ces conditions échouent, conclure \`insuffisant\`, **ne pas régler YOLOX sur ces images et ne pas rejouer les poses**. Le succès autoriserait uniquement une prochaine revue des régions « unknown » ; jamais une reconnaissance de forme générale ou une intégration RKNN.

Comparateur F2 facultatif mais non modifiable : mêmes régions top3 et scores d'origine → ancienne projection **explicitement mock** SIM-VIS-D. \`inspect unknown\` si elle est admise par F2, sinon \`idle\` ; jamais de catégorie sémantique, connaissance, récompense, effet, commande moteur ou vérité terrain réinjectée. Tester le refus du spoof de source, des données invalides, des images/régions périmées et d'un oracle incohérent. Ne pas publier les images RGB/segmentation, aucun média privé.

**Limites :** MuJoCo OEM ne simule pas une distinction télévision/photo/présence réelle ; ce test n'invente pas d'écran OEM. Ni caméra physique, ni \`mediad\` multicatégorie, ni RKNN/NPU, ni MuJoCo dynamique, ni OEM \`robotd\` 50 Hz/état de sol, ni déplacement, ni mesure énergétique. Les scénarios disponibles ne permettent pas de déclarer « généralisation réelle ».
