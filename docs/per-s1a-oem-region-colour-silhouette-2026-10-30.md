# PER-S1A — couleur et contour provenant de la région, contrôle OEM indépendant

**Préenregistré le 30/10/2026 AVANT tout nouveau rendu/inférence S1A.** Projet `main@05ab7e31dcd742ae04bb6670ca6f3be2b17a9278`. OEM `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`; `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Références obligatoires : `AGENTS.md`, `docs/plan-action.md`, `docs/development-reuse-protocol.md`, `docs/kwipi-experiential-learning-plan-2026-10-26.md`, `docs/perception-oem-rknn-2hz-plan-2026-10-29.md`, [PER-S0](per-s0-lowview-unknown-regions-2026-10-30.md).

## 1. Objectif, preuve manquante, hypothèse, risques

**Question vérifiable :** lorsque la caméra basse OEM génère un candidat de région par YOLOX-Nano *sans exploiter sa catégorie*, le simple traitement de cette région peut-il fournir **une couleur de premier plan et une silhouette 2D suffisamment fiables pour former ultérieurement un souvenir incertain** ? Critère à comparer au **rectangle seul** et à un **masque indépendant MuJoCo** (plafond oracle, hors algorithme). Une boîte YOLOX n'est pas une forme ni un objet entier ; aucun contour, nombre de roues, type de matériau ou usage ne doit être affirmé si le masque ne passe pas.

**Faits antérieurs :** S0 (PR #211, CI #41066382564) a localisé 2/4 objets hors cinq catégories opérationnelles (pilier et cylindre « plante ») en proposant des **étiquettes fausses** ; cube manqué et canapé IoU 0,245. Les tentatives [VIS-REG-D1, VIS-SEG-L1, VIS-SEG-G1, VIS-APP-1](../README.md) ont échoué sur leurs critères : 0/3 balles « rondes », GrabCut léger 5/10 à IoU55, complet jusqu'à 9,7 s/image, couleurs de boîtes souvent contaminées par fond. **Ne pas réutiliser leurs médias déjà notés, ni réintroduire GrabCut lourd.** À l'inverse, une comparaison contrôlée en simulation faible hauteur sur des objets simples peut décider si **l'approche légère sans modèle** vaut une étude ultérieure, et non livrer la fonction.

**Réutilisation** : `experiments/per_s0_lowview_oem_region.render_case` (étendre uniquement sa liste de cas autorisés et le retour **de masque GT pour évaluation**, option par défaut inchangée), `World/Body/Camera` OEM, `sim_ball_segmentation_gt` et `sim_vis_f_gt_preflight._set_free_joint`, `cata_yolox_categories.prepare_image/validate_model_file` (ONNX YOLOX-Nano SHA `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`, licence Apache-2.0 déclarée), `yolox_attention_candidates.decode_candidates` (score 0,25, NMS 0,50), OpenCV CPU déjà utilisé dans VIS-SEG. Le seul nouveau code est une **fonction pure d'essai** hors `microduck_companion` production, qui reçoit **RGB + région**, et retourne soit `unknown`, soit un masque temporaire et quelques mesures non-sémantiques ; pas de nouveaux modèles, CPU permanent, base, lecteur caméra ni API OEM.

## 2. Cohorte et entrée gelées

**6 cibles positives, une scène négative**, prises statiques MuJoCo avec caméra OEM `head_camera` redressée 360×640 ; angles et objets distincts du lot S0 (mondes/maillages OEM communs, **pas de nouveau corpus réel**). Aucun média personnel. GT = ID de géométrie MuJoCo rendu **au même état** que le RGB, non utilisé comme entrée du descripteur. Toute référence au masque oracle dans une fonction de prédiction ou sélection de région est un **échec de protocole**.

| Ordre | Scène et objet géométrique | Position XY / yaw | Modification locale dans état statique |
|---|---|---|---|
| 1 | `red_cube_near` : `scene_apartment.xml`, `obj_0_geom` (cube rouge) | (2,00; −0,50), +π/2 | Joint libre `obj_0` à **0,42 m devant** et 0,05 m côté gauche, z=0 |
| 2 | `orange_ball_mid` : `scene_apartment.xml`, `ball_0_geom` | (1,85; −0,55), +π/2 | Joint libre à **0,55 m devant**, 0,10 m côté droit, z=0 |
| 3 | `pink_ball_far` : `scene_apartment.xml`, `ball_2_geom` | (1,85; −0,50), +π/2 | Joint libre à **0,75 m devant**, 0,12 m côté gauche, z=0 |
| 4 | `green_pillar_side` : `scene_vslam.xml`, `vs_pil_g` (box verte) | (−3,30; 2,60), 0 | Aucune |
| 5 | `blue_pillar_side` : `scene_vslam.xml`, `vs_pil_b` (box bleue) | (−4,05; −1,60), 0 | Aucune, négatif de couleur contre décor proche |
| 6 | `armchair_side` : `scene_apartment.xml`, union `liv_chair_seat` + `liv_chair_back` | (−2,85; 0,15), 0 | Aucune, objet multi-parties |
| 7 | `floor_empty_control` : `scene.xml`, pas d'objet extérieur | (0;0), 0 | Négatif de contrôle de proposition, déjà utilisé par S0 (ne pas annoncer indépendant) |

**Préflight avant téléchargement ONNX :** 6/6 masques cibles visibles ≥80 pixels, RGB et segmentation exactement alignés, snapshot `qpos`/horloge stable, union correcte pour les deux géométries fauteuil, zéro géométrie extérieure dans le négatif. Si un de ces invariants manque, **STOP** sans inférence ; ne pas déplacer les objets après un résultat observé.

## 3. Algorithme entièrement fixé (sans GT en entrée)

Un seul `decode_candidates(...,max_results=3)` par tête brute, puis **région top1 par confiance** (sans sélection par IoU), quelle que soit la classe COCO erronée ; on compte en plus IoU top3 de localisation, mais on **ne choisit jamais la meilleure région avec le masque oracle**. Sans proposition : `unknown`, zéro attribut.

Pour la ROI top1 de taille ≥9 px, RGB `uint8` uniquement :
1. Semence couleur = **médiane RGB du rectangle central 40 % × 40 %** de la ROI.
2. Masque de proximité RGB = pixels à distance euclidienne ≤ **50 unités sur RGB 0–255** de cette semence. Éliminer les ilots isolés via ouverture+fermeture morphologique **3×3** OpenCV ; garder **la composante connexe contenant le centre de la région** (sinon `unknown`). Ne jamais utiliser le masque MuJoCo pour cette étape.
3. Abstention : composante trop petite (moins de **64 pixels** ou moins de **8 %** de la ROI), plus de **95 %** de la ROI (image uniforme), ROI trop petite, couleur/contour non définis. Si région retenue : couleur RGB médiane **des seuls pixels proposés**, bbox 2D et **circularité** `4πA/P²` (0–1 si valide), **sans mot de forme « ronde »**, classe ou identité. La confidence YOLOX est conservée comme score du modèle, **pas** une probabilité de correction du masque/trait.
4. **Témoin rectangle seul** : même boîte top1, médiane de toute la ROI, masque de tout le rectangle, circularité rectangle ; **témoin oracle** : vrai masque GT geom-ID. Les deux témoins ne peuvent pas être fournis à la fonction de proposition.
5. Mesurer coût de **ce traitement seulement**, inférence PC et rendu séparés. Aucun pixel / silhouette / JPG / poids en rapport GitHub ; chiffres agrégés/cas seulement.

Ce procédé ultra-simple est une **hypothèse à réfuter** sur fonds colorés et silhouettes : il n'est **ni un segmentateur accepté ni un futur code production**.

## 4. Critères de passage ou arrêt (avant résultats)

- **Qualité candidate** : au moins **4/6** boîtes top1 couvrent la géométrie (IoU≥0,50). Parmi les **six scènes**, au moins **3/6** régions produisent conjointement un masque estimé IoU≥**0,55** par rapport au GT, une couleur estimée à distance euclidienne ≤**35** de la médiane couleur des pixels GT, et une différence de circularité absolue ≤**0,20** du masque GT, avec toutes mesures finies.
- **Valeur ajoutée** : le masque proposé fait **strictement mieux que le masque rectangle** en IoU pour **au moins 2/6 cas** ; et la couleur proposée fait strictement mieux que la couleur du rectangle entier sur **au moins 2/6 cas** (mesures uniquement pour ROI top1 IoU≥0,50 afin d'éviter de noter une mauvaise cible comme « bonne couleur »).
- **Fausses certitudes / abstention** : **zéro** trait proposé sur `floor_empty_control` ; **zéro** trait confiant sur les cas où top1 ne couvre pas GT IoU≥0,50 ; test synthétique de fond uniforme/ROI vide doit produire `unknown`, et tests négatifs géométrie/données non finies doivent être refusés.
- **Ressources** : **p95 ≤25 ms** pour le seul traitement de ROI sur les six positifs (PC runner, hors inférence et rendu), sans l'assimiler à RK3566/NPU/2 Hz. Les mesures de six images ne sont pas un budget thermique ni un p95 robuste.
- **Si un critère échoue, STOP :** ne pas adopter le masque/couleur, ne pas intégrer à SQLite/F2/Qwen, ne pas modifier seuils/algorithme/scènes pour obtenir un passage. CI verte signifie que l'étude a vraiment été exécutée et correctement mesurée, **pas** que la porte de qualité passe. Si franchie, le résultat demeure **une preuve PC/MuJoCo étroite**, nécessite un holdout réel ultérieur et une revue OEM/licence/ressources avant tout portage.

**Négatifs logiciels** : ROI traversant hors image, box NaN, RGB taille/type faux, semence uniforme, masque sans centre, changement du GT sans changement de prédiction (test d'indépendance), couleur fausse, rejet d'un output YOLOX invalide, rapport absent/tronqué, emplacement interdit d'image et limite d'inférence. Aucun test ne donne une autorisation d'action ou de mémoire.

## 5. Retour arrière et sorties

Une seule PR de recherche hôte : petit adaptateur du renderer **expérimental S0**, module d'évaluation **expérimental S1A**, tests positifs/négatifs et workflow ponctuel ; après vrai résultat, documenter les chiffres et les limites dans cette note, README, plan, roadmap. État initial `prévu/non exécuté`. Ne jamais toucher `upstream/`, `robotd`, `mediad`, `duck-detect`, politiques ONNX, paramètres d'encaissement, base, Qwen, caméra ou photos privées. Retour arrière = revert de la PR, aucun robot à restaurer.

## 6. Résultats obtenus

**Exécution effective du 30/10/2026 — [CI OEM/ONNX #41068778379](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41068778379), initialisée sur `a1ffc0a40b80738912a00dfe2424fa3572f46a96`** : après une correction **de test synthétique seulement** (la boîte de fixture cercle avait IoU **0,413** et ne pouvait satisfaire l'assertion IoU>0,50), les 12 tests S1A et les tests de non-régression S0 ont passé ; six cibles et un négatif sont valides **7/7** à l'oracle de géométrie, les modèles sont téléchargés **après** préflight, SHA du YOLOX d'origine confirmé, **7/7 inférences réelles CPU**, rien sauvegardé comme RGB/masque/ONNX, rapport numérique seulement. **Aucun seuil, pose, image de test ou poids n'a changé après la découverte des métriques du modèle.** Les deux gitlinks épinglés sont inchangés.

| Cas fixé | Pixels GT indépendants | Proposition top1 et IoU boîte | État de traits RGB-only | Comparaison oracle GT / rectangle |
| --- | ---: | ---: | --- | --- |
| Cube rouge `red_cube_near` | **8 386** | **aucune**, IoU=0 | `unknown` | Le modèle n'offre pas de région |
| Balle orange `orange_ball_mid` | **3 401** | **0,871423**, classe COCO **49** (hypothèse non validée) | Descripteur proposé ; **masque IoU 0,633637**, erreur couleur RGB **33,1662**, erreur de compacité **0,065888** | Rectangle complet : masque IoU **0,670809** (**meilleur**) ; erreur couleur **15,3623** (**meilleure**) |
| Balle rose `pink_ball_far` | **1 761** | **0,877140**, classe COCO **32**, score **0,822014** | Descripteur proposé ; **masque IoU 0,533788** (sous 0,55), couleur erreur **46,6798** (au-dessus de 35), compacité erreur **0,115209** | Rectangle : masque IoU **0,704208**, couleur erreur **21,6102** (tous deux **meilleurs**) |
| Pilier vert `green_pillar_side` | **39 270** | **aucune**, IoU=0 | `unknown` | L'objet est bien visible, mais YOLOX ne fournit aucune ROI |
| Pilier bleu `blue_pillar_side` | **35 966** | **aucune**, IoU=0 | `unknown` | Fond/forme restent sans ROI, l'étiquette ne peut suppléer le masque |
| Fauteuil de côté `armchair_side` | **86 563** | **aucune**, IoU=0 | `unknown` | GT union assise+dossier visible, partiellement tronquée au bord de l'image |
| Témoin `floor_empty_control` | **0** objet extérieur | **0 proposition** | Aucun trait, abstention | Négatif réutilisé de S0, pas un nouveau holdout |

**Décision préenregistrée : `functional_value_gate_met=false` ; `STOP_no_auto_colour_or_shape_to_memory`.** Seulement **2/6** ROI top1 appariées au GT à IoU50 (minimum 4) et **1/6** cas complet masque+couleur+compacité (minimum 3). **0/6** gain de masque et **0/6** gain de couleur par rapport au rectangle seul (min 2 chacun). Zéro fausse proposition confiante sur ROI non localisées ou scène négative, mais cet avantage provient largement de **l'absence de toute ROI** dans quatre images. **Un score de couleur ou de compacité ne doit pas être converti en nom d'objet, « rond », silhouette fiable, trait mémorisé ou entrée Qwen fiable.** Le masque a même réduit la qualité par rapport au rectangle sur les deux images où le détecteur localisait une région.

**Temps observés PC hôte :** inférence ONNX **p50 4,789 ms**, **p95 5,327 ms** pour sept vues ; post-traitement de traits **p95 11,606 ms**, calculé sur les six positifs dont **quatre sans ROI (coût 0)** : donc **pas** une estimation fiable du coût par région, encore moins un budget NPU/RK3566 de production. Aucun modèle nouveau, tâche caméra persistante, commande, mémoire, Qwen, ToF ou modification de sécurité.

**Interprétation et suite anti-dérive :** les cas sont de nouvelles poses/objets par rapport à S0, mais **recyclent les mondes OEM** et les géométries simplifiées ; ce protocole ne teste pas l'usage, la couleur d'une vraie trottinette, un objet vivant, l'écran/photo, la couleur sous éclairage domestique ou le trajet de navigation. Le problème est **double** : région manquante dans 4/6 positifs et segment/colorisation trop incertains dans les deux autres. **Arrêter S1A sur ce modèle** : pas de retuning de seuils RGB, de réordonnancement des régions par oracle, de nouveau GrabCut ou d'extension de `ExperienceMemory`. Conserver les résultats comme preuve négative ; prochain progrès nécessiterait **une source de silhouettes/masques déjà licenciée et adaptée à l'OEM, testée sur scènes réellement nouvelles avec contrefaits**, ou le progrès indépendant M1/Q1 sur fixtures **sans se prétendre alimenté par la caméra réelle**. Aucune fonctionnalité embarquée livrée.
