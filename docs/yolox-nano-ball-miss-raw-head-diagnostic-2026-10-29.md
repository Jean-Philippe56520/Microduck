# PUBLIC-VIS-DIAG — Pourquoi YOLOX-Nano rate les balles de Kwipi

**29 octobre 2026 — diagnostic hôte, sans réentraînement, remplacement, réglage du modèle ni action sur le robot.**

## Question et méthode

Après la [PR #187](https://github.com/Jean-Philippe56520/Microduck/pull/187), la baseline YOLOX-Nano (Megvii, Apache-2.0, ONNX SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`) obtenait **0 proposition de balle sur trois images**, au seuil fixe 0,25. Les photos et les résultats initiaux sont conservés dans [public_vision_smoke](../tests/assets/public_vision_smoke/README.md).

Sur la [CI diagnostique réussie #40953575507](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40953575507), on a **réutilisé exactement la même inférence 416×416**, le même prétraitement et les poids inchangés, puis lu les 80 scores COCO avant filtrage : `objectness × probabilité_classe`. Les boîtes des meilleures hypothèses ont été décodées avec la grille YOLOX déjà utilisée. Les 13 mêmes images sont reprises pour identifier le mécanisme **sans faire de ce jeu un benchmark indépendant supplémentaire**. [Mesures brutes par image](../tests/assets/public_vision_smoke/yolox_raw_head_diagnostic.json).

## Faits observés

| Fichier | Score maximal `sports_ball` | Meilleure classe COCO, score | Boîte de la meilleure classe (pixels de l'image prétraitée) |
|---|---:|---|---|
| `ball_01.jpg` (ballon bleu et jaune) | 0,0536963 | Parapluie (index 25), 0,1383191 | [224,6 ; 557 ; 515,5 ; 856,1] sur 720×1280 |
| `ball_02.png` (tennis) | 0,0139059 | Orange (index 49), 0,6693028 | [59,5 ; 61 ; 141,4 ; 144,3] sur 200×204 |
| `ball_03.png` (baseball) | 0,0015993 | Gâteau (index 55), 0,6770669 | [53,3 ; 47,9 ; 148,8 ; 148,8] sur 200×203 |

Sur ces trois photos, les boîtes correspondent visuellement à la zone de la balle. **Le modèle a donc des propositions spatiales, mais donne les mauvaises classes**. Ce n'est pas un simple échec du NMS : le score de balle reste très inférieur à 0,25. Baisser légèrement ce seuil ne remettrait pas les bonnes catégories en tête. Le cas `cat_02.jpg` est différent : la meilleure classe est **chat**, score **0,206998**, juste sous 0,25, mais régler le seuil sur cette seule image serait un surajustement.

Les deux images étiquetées `unknown` n'ont pas de **catégorie cible** parmi les cinq classes, mais présentent des structures visuelles. Sur la roche, une région reçoit la classe *cheval* (0,298255). Sur l'observatoire, une petite zone reçoit *horloge* (0,738979). **Utiliser aveuglément toutes les 80 classes pour déclarer un objet confirmé donnerait aussi des hypothèses erronées.** Ce ne sont toutefois pas des scènes entièrement vides et elles n'ont pas de boîtes de référence pour le statut « objet générique » ; on ne peut pas y mesurer sa précision.

## Interprétation et décision

1. **Démontré par l'essai :** confusion des catégories de deux balles isolées, avec localisation grossière visible ; un ballon présente un signal plus faible. Notre filtre limité aux cinq catégories masque les autres hypothèses, d'où « aucune proposition ».
2. **Non démontré :** cause d'entraînement (distribution COCO, fond, couleurs, perspective), effet d'une autre taille d'entrée, gains sur de nouvelles photos, fiabilité NPU et reconnaissance sur la caméra réelle. Le fait que le réseau trouve une boîte ne prouve pas une bonne classification.
3. **Ne pas faire :** abaisser le seuil à partir de ces trois photos, réétiqueter « orange » ou « gâteau » en balle, inventer une catégorie balle, mettre un deuxième détecteur en continu, modifier `mediad`, `robotd`, ONNX ou les sous-modules.
4. **Piste minimale sans entraînement :** réutiliser éventuellement des propositions non ciblées parmi les 80 classes comme **« forme/objet possible, catégorie inconnue »**, sans valider sa réalité ni provoquer de mouvement. **Pas encore codé** : mesurer d'abord, sur de **nouvelles images** avec cas négatifs et annotations spatiales, si ces propositions apportent des objets utiles sans multiplier les faux positifs.

**Critère futur préannoncé :** gain visible sur des objets auparavant manqués, pas de détérioration sensible sur humain/chat/chien/chaise, faux positifs contrôlés et coût CPU/RSS acceptable. Si ces conditions échouent, arrêter l'extension et comparer une alternative existante, sans entraîner sur les trois images utilisées ici.

**État :** diagnostic PC GitHub Actions réussi, pas une modification des capacités de perception embarquées. Robot absent, NPU/motricité/sûreté inchangés.
