# PER-P4L1 — première comparaison YOLO26n-seg en vue basse OEM (préenregistrement)

**Date et ordre : 03/11/2026, consigné AVANT inférence de ce lot.** Base `main@318c8fb01f00ba55e2facafb4d7958bce4eb3e87`. Sous-modules conservés : OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, simulation `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Autorités : `AGENTS.md`, `docs/plan-action.md`, `docs/development-reuse-protocol.md`, `docs/perception-oem-rknn-2hz-plan-2026-10-29.md`.

## Décision et manque attesté

La [PR #214](https://github.com/Jean-Philippe56520/Microduck/pull/214) est encore **brouillon** ; sa CI a mesuré 300 photos COCO (rappel de régions prioritaires YOLO26n-seg 0,7522), mais **aucune image OEM à hauteur basse**. P5/P6/P7/P9/P10 préparent une chaîne logicielle et non la qualité de perception sur RK3566. L'essai ne concerne que les deux poids officiels de P5, en **PyTorch/Ultralytics CPU PC**, pas l'extension RKNN OEM.

**Réutiliser** le rendu/masque MuJoCo du `SIM-VIS-F` et de `PER-S0`, `visible_geom_bbox`, `_set_free_joint`, les SHA des modèles de `experiments/per_p5_yolo26_rknn_compat.py` et l'API d'inférence officielle Ultralytics. **Adapter** un banc hôte court et un appariement de régions. **Ne pas créer** de nouveau pilote, webcam, service, SQLite, politique motrice, modèle, décodeur OEM, gitlink, données privées, artefact de poids ni image publiée. Aucun code AGPL tiers recopié ; **licence des poids pour un produit/redistribution non acquise**.

## Cohorte figée avant observation

Caméra `head_camera` MuJoCo constructeur, RGB et masque d'ID géométrique au **même état figé**, image upright 360 × 640, sans `mj_step`. **Trois scènes déjà précontrôlées pour leur GT, mais jamais soumises à YOLO26n-seg dans nos essais**, plus un témoin négatif optique à nouvelle orientation. Elles ne représentent ni des lieux nouveaux, ni un échantillon statistique indépendant de scènes physiques.

| Cas | Monde OEM | Tronc XY, yaw | Géométrie GT | Préflight |
| --- | --- | --- | --- | --- |
| `cube_south_living` | `scene_apartment.xml` | (-2,80 ; -2,20), +90° | `obj_0_geom`, joint libre au sol à 0,45 m devant l'axe horizontal de caméra | ≥80 pixels |
| `chair_near` | `scene_apartment.xml` | (-2,55 ; 0,05), 0° | `liv_chair_seat` | ≥80 pixels |
| `pillar_cyan_near` | `scene_vslam.xml` | (3,40 ; -1,20), +90° | `vs_pil_c` | ≥80 pixels |
| `empty_floor_yaw27` | `scene.xml` | (0 ; 0), +27° | aucun objet externe, plancher OEM / propre robot autorisés | aucun geom externe nommé |

Le cas historique `ball_hidden_by_chair` est **exclu** : rayon invalidé par la GT, ne pas le réparer après coup. Ces quatre points ne permettent **pas** de mesurer chat/chien/humain réel, balle, écran, photo, peluche, profondeur ou sécurité de collision. La vision de sa propre silhouette sur le négatif n'est pas un objet externe. Tout objet absent, hors champ, ambigu ou sans référence vérifiable reste `unknown`.

**Préflight STOP avant téléchargement/inférence** si scène, géométrie, dimensions, pose, masques ou visibilité invalides ; vérifier les 4/4 cas avant chargement d'un seul poids. Rendre les RGB et masques **uniquement en RAM** ; transmettre aux modèles les RGB seuls, jamais les masques.

## Comparaison et critères préfixés

- `yolo26n.pt` et `yolo26n-seg.pt`, empreintes P5 vérifiées ; `ultralytics==8.4.192`, `imgsz=640`, `conf=0.25`, `iou=0.50`, `max_det=100`, `device=cpu`, `retina_masks=true` pour segmenter. Même image et configuration, un passage par modèle et scène, sans réglage après résultat.
- Associer pour chaque cible le meilleur rectangle de région, **étiquette ignorée**, à la boîte GT indépendante, `IoU≥0,50`; distinguer réussite de région, classe COCO proposée non validée et omis. Pour les régions appariées du modèle segment, mesurer `IoU(masque prédit, masque geom GT)` contre `IoU(rectangle prédit rempli, même GT)`. Les masques ne sauvent pas une cible non détectée.
- Déclarer médiane/p95 de temps CPU et RSS **hôte** uniquement ; la comparaison est trop petite pour prétendre à une vitesse RK3566. Compter les prédictions parmi les **cinq catégories prioritaires de Kwipi** sur la scène vide, notamment celles de score ≥0,80 ; diagnostic de risques, pas métrique globale de FP.
- **Critère favorable de valeur, fixé avant inférence :** YOLO26n-seg récupère au moins **2/3 régions** cibles à IoU50, n'en récupère pas moins que YOLO26n, ses masques sont meilleurs que leurs rectangles sur **≥60 % des régions effectivement appariées**, et **zéro** proposition de l'une des cinq catégories à score ≥0,80 dans le négatif. Moins de deux régions retrouvées, masque moins bon, modèle inférieur au témoin, ou forte proposition négative => `INSUFFISANT`, sans nouveau réglage de ces vues. Le critère n'est **pas** un seuil de déploiement ou de sécurité.

## Tests, arrêt et preuves

Positifs : nombre et ordre des 4 poses, image/mask alignés et figés, 3 GT ≥80 px, score d'un vrai appariement, calcul d'IoU masques. Négatifs : ordre, cible absente, masque mal dimensionné, nombre incorrect de prédictions, score NaN/inf, fausse image « négative » dotée de geom externe, mauvaise source/poids/version, tentative d'écraser un rapport, promotion de classe en identité. Les tests de contrat sans modèle **ne prouvent aucun rappel**. Une CI verte atteste uniquement l'exécution réussie ; enregistrer séparément la qualité mesurée. Si le preflight échoue, STOP sans inférence. Le résultat n'autorise ni nom d'objet inconnu, ni mémoire, ni geste OEM, ni flash, ni licence commerciale. Après CI, noter succès/échec et limites sans ajuster les critères.

**Retour arrière :** supprimer cette branche et son rapport CI. B11 et les deux gitlinks restent immuables ; aucun état robot à restaurer.


## Résultat après essai — CI réelle du 03/11/2026 (critères inchangés)

- **Protocole pré-enregistré dans le premier commit `a87efc7487dd8171a167959487731d2cfa6606a2`**, suivi du banc, des tests et du workflow. Exécution sur `64b9d369a1c7293b28c74d87b3c058066fbe360f` : [CI hôte PER-P4L1 #41627165137](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41627165137), job `paired-lowview` réussi ; revue de résultats [PR #280, commentaire](https://github.com/Jean-Philippe56520/Microduck/pull/280#issuecomment-6602556108). Le code et le workflow de l'essai restent consultables à leur SHA historique même s'ils ne sont pas conservés dans la version finale de la PR.
- **Préflight OEM : PASS 4/4** — cube 7 012 pixels, fauteuil 171 720, pilier cyan 137 496, sol vide 0 objet externe ; toutes poses statiques avec RGB/GT alignés. Ce sont des vérités terrain de géométries simulées, pas d'objets reconnus.
- **Deux poids officiels vérifiés et huit véritables inférences PC** : `yolo26n` **0/3** cibles localisées à IoU boîte ≥0,50 ; `yolo26n-seg` **0/3**. Chaque modèle propose une région sur l'image du cube, mais **IoU=0** avec la cible ; zéro proposition sur les vues fauteuil/pilier et sur le sol vide. Zéro étiquette des cinq classes cibles à score fort sur le négatif.
- **Aucune région appariée** : gain de masque *non mesurable*, fraction `null` et non `0 %`. Le seuil de rappel 2/3 fixé avant essai échoue sans ambiguïté ; **décision `INSUFFICIENT_no_lowview_model_promotion`**. Ne pas modifier la géométrie, confiance, modèles ou poids sur ce corpus et ne pas conclure à une infériorité générale hors ces scènes synthétiques.
- Durées CPU **hôte** médianes 51,619 ms (détection) et 70,871 ms (segmentation), premier passage froid détection jusqu'à 3 092 ms ; pic RSS du processus hôte ~1 446 208 KiB, après exécution successive des deux modèles. **Ni 2 Hz sur NPU RK3566, ni ressource réelle de robot, ni sécurité 50 Hz** ne sont établis. Aucune commande moteur, caméra réelle, mémoire ou Qwen.
- **Décision anti-dérive** : garder la preuve numérique et fermer le lot sans intégrer le banc expérimental comme nouveau composant permanent de Companion. L'étude COCO #214 demeure un résultat PC dans un autre domaine ; ce test est insuffisant pour promouvoir YOLO26n-seg, surtout pour objets inconnus. Passer à l'axe C / mémoire sur observations réellement indépendantes, sans fonder identité/causalité sur ces masques manqués. Aucune livraison de modèle ni poids AGPL.

