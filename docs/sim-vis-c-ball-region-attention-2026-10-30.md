# SIM-VIS-C — détecter une région de balle avant de lui attribuer un sens

**Préenregistrement du 30/10/2026, avant toute inférence de ce lot.** État candidat, résultat non encore observé.

## Question fonctionnelle et manque confirmé

SIM-VIS-B a rendu **3 352 pixels de balle** sur caméra OEM statique puis YOLOX-Nano a produit **0 détection sports_ball** à 0,55 m, sous [GitHub Actions #40927477247](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40927477247). VIS-ATT-1 a montré un gain des propositions génériques top3 sur **d'autres images COCO**, mais ne les a pas comparées à la vérité terrain basse de la caméra OEM. Cette absence empêche de savoir si une région candidate (sans catégorie certaine) peut être observée par Kwipi. Une région détectée ne prouve ni forme, ni objet, ni identité, ni couleur, ni réalité physique chez l'utilisateur.

Réutiliser le **même** `sim_ball_segmentation_gt.py`, `decode_boxes`, `yolox_attention_candidates.decode_candidates` inchangé (`MIN_SCORE=0.25`, NMS 0,50, top 1/3/5) et le modèle Apache-2.0 SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`. La vérité terrain indépendante provient du `mjOBJ_GEOM` de la balle dans les deux rendus d'un **état identique** : RGB et segmentation, sans `mj_step` ni aucune commande. Code OEM épinglé `upstream/microduck@942e58e3`, RL `upstream/microduck_rl@b02fdea4`, sous-modules inchangés. Ce n'est **pas** la chaîne `mediad` de production, qui reste à prouver.

## Cas fixés avant résultats

Dans l'appartement OEM existant, avec la même caméra de tête de 640×360 redressée :
- **Négatif :** `negative_behind`, balles derrière le robot ; 0 pixels de balle dans la segmentation.
- **A — proche gauche :** yaw 75°, balle 0 à **0,42 m devant**, **0,12 m à gauche** relativement à la caméra.
- **B — médiane centrale :** yaw 90°, balle 0 à **0,72 m devant**, sans décalage.
- **C — éloignée droite :** yaw 105°, balle 0 à **0,95 m devant**, **0,16 m à droite**.

Ces poses sont choisies **avant** l'inférence ; elles restent des variantes contrôlées du **même appartement**, ni une vérité terrain domestique, ni un corpus indépendant de photos réelles. Les deux autres balles sont placées derrière. Pour les trois positifs, exiger **au moins 80 pixels de balle** indépendamment de YOLOX ; si l'une est invisible, arrêter et documenter l'échec de la préparation au lieu de la déplacer après résultat. Viser une prise basse avec caméra OEM, sans changer les modèles, la vitesse, les poids, la focale ou la lumière.

## Mesure et portes de décision

Pour chaque positif : meilleur IoU de boîte **à 0,50** entre **une** boîte candidate top1/top3/top5 et la boîte MuJoCo de la balle, indépendamment de la classe COCO proposée, et comparateur catégoriel `sports_ball` existant. Mesurer nombre de régions, inférence et coût de décodeur PC. Négatif : vérifier zéro pixel balle et compter les fausses détections de catégorie sports_ball ; ne pas qualifier arbitrairement les régions sur d'autres objets comme faux positifs.

**Porte envisagée AVANT inférence :** 3/3 positifs avec balle visible ≥80 pixels, négatif sans balle et sans faux `sports_ball`, **au moins 2/3 positifs localisés par une région top3 avec IoU≥0,50**. La localisation top5 est informative et non une raison de changer le seuil. Si la porte échoue, **STOP**, pas de tuning ou de réseau de secours sur ces quatre images. Si elle réussit, elle autorise uniquement à étudier plus tard une **hypothèse de région non sémantique** dans la cognition ; ni catégorie, ni mémoire sémantique, ni déploiement NPU.

## Tests négatifs obligatoires et limites

Cas géométriques synthétiques de non-chevauchement, rejet des sorties invalides, zéro stockage des images rendues, zéro nouveau pilote, contrôleur moteur, autorisation physique, réseau vers Qwen ou SQLite. La CI de ce lot doit exécuter le moteur MuJoCo et les poids ONNX épinglés ; une CI hôte verte pour la procédure n'implique **pas** la porte de reconnaissance. Après résultat, consigner exactement les chiffres et choisir `progres_demontré`, `insuffisant` ou `bloque_source_externe` sans retester les mêmes scènes.

**Suite conditionnelle :** comparer des scènes réellement différentes et des GT indépendantes si la voie de régions apporte un bénéfice ; sinon prioriser une source de perception adaptée et licenciée sur le chemin `mediad/uyvy/duck-detect` OEM, à 2 Hz initiaux si le NPU RK3566 et les ressources permettent. Ne pas porter un modèle sur robot avant mesure ni confondre une image MuJoCo avec `media.detections`.
