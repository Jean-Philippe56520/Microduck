# COG-A2-P0 — porte optique appariée OEM : un indice de déplacement, pas le roulement

**Préenregistrement : 03/11/2026, AVANT code de l'expérience et avant son inférence.** Base `main@0ddc9862cc5476d88b2a3b27cdfce19231b1110e`. OEM épinglé `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, scènes `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto historique `1ee58387810cebb67ae0d634c351d95024483bce`. Aucun sous-module changé.

## Question / manque / comparateur

COG-A1 propose `ball.possible_rolling`, mais F1 livre une étiquette/TTL/piste éphémère et ne constate **aucun** changement de position ou roulement. Avant de développer A2, vérifier si la chaîne **déjà existante** de propositions de régions YOLOX (Megvii, poids ONNX SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`) peut seulement **localiser la même cible géométrique dans deux images**. Le comparateur F1 label seul ne possède pas de déplacement mesuré. Il n'existe ni flux temporel OEM authentifié ni identité d'objet entre vues. Si le modèle manque l'objet, la réponse demeure **inconnu**, pas une propriété acquise.

**Type exact de preuve :** paire de vues distinctes MuJoCo obtenue en changeant **manuellement la pose d'une balle libre** entre deux états figés, sans `mj_step`, robotd ni commande motrice. Ce test mesure une **différence d'image sous caméra fixe**, pas un mouvement observé au fil du temps, et encore moins le roulement, un effet causal ou la reconnaissance de la même instance physique. La vérité terrain indépendante vient des ID de géométrie MuJoCo au même état que chaque rendu RGB et sert **uniquement au score**, jamais au choix de la région dans le modèle. Caméra OEM `head_camera`, correction OEM `Camera`, 360×640 après rotation. Aucun résultat n'est une observation `mediad` réelle ni une propriété dans ExperienceMemory.

## Cohorte et seuils figés

Chaque cas = **deux RGB rendus en RAM** et leurs deux masques d'ID de géométrie, puis au plus deux inférences du **modèle existant inchangé** avec préparation `prepare_image` et `decode_candidates(max_results=1)`. Aucun réglage de seuil : YOLOX `MIN_SCORE=0.25`, NMS 0,50, top1 uniquement, IoU avec le rectangle géométrique ≥0,50. Une paire ne prouve pas une association d'identité; les `top1` sont sélectionnés SANS consulter le masque.

| Cas | Scène constructeur et pose | Manipulation entre deux images | Attente |
| --- | --- | --- | --- |
| P1 `flat_ball_shift` | `scene_ball.xml`, robot XY=(0,0), yaw=0 ; balle `ball/ball_geom` à 0,60 m devant, -0,10 m latéral | Ballon à 0,60 m devant, +0,10 m latéral | déplacement d'image candidat |
| P2 `office_ball_shift` | `scene_apartment.xml`, robot XY=(2,15,-0,55), yaw=90° ; `ball_1/ball_1_geom` à 0,60 m devant, -0,10 m latéral | Ballon à 0,60 m devant, +0,10 m latéral | transfert à un autre fond |
| N1 `flat_ball_still` | `scene_ball.xml`, mêmes paramètres P1 | Ballon sans déplacement | pas de déplacement revendiqué |
| N2 `empty_floor` | `scene.xml`, robot XY=(0,0), yaw=0 | Aucun objet cible | aucun signal balle |
| N3 `camera_yaw_confounded` | `scene_ball.xml`, mêmes paramètres P1 | Balle immobile, **caméra/robot tourné de +20°** pour l'image 2 | refus explicite `camera_confounded`, sans inférence valorisable |

Préflight obligatoire : P1/P2/N1/N3 ont chacun ≥80 pixels de balle aux deux vues et des boîtes GT valides ; P1/P2 ont centre GT différant d'au moins **20 pixels** entre vues, N1 moins de **5 pixels**. N2 = 0 pixel cible ; N3 = orientation caméra changée, refus sans attribution d'effet. Les positions de la caméra doivent être identiques sur P1/P2/N1 à 0,002 m et 0,01 rad près; aucune paire dont le contrôle échoue ne passe à l'inférence. Si une pose/masque est non valide : **STOP AVANT tout téléchargement du modèle**, ne pas déplacer le robot ou l'objet après résultat pour rendre le jeu favorable.

**Succès technique préfixé :** P1/P2 valides géométriquement, **au moins 1 des 2** paires positives localisée top1 dans les deux vues à IoU50 **et** différence de centres top1 ≥20 pixels et erreur de déplacement de centre ≤25 pixels par rapport au déplacement GT, 0 faux déplacement ≥20 sur N1, 0 proposition de balle/identité sur N2, rejet N3. Mesurer et publier aussi **chaque échec** et le coût hôte, sans cacher les absences de modèle. Une CI verte pour script/tests ne fait pas passer le critère optique.

**STOP :** une image positive non visible, la caméra non fixe sans rejet, l'accès du décodage aux GT, modèle modifié, poids non conformes, indice d'identité/roulement/effet déclaré, ou moins d'une paire positive remplissant la porte. Ne pas retuner ces paires après observation. Les scènes OEM déjà connues ne constituent pas une cohorte de généralisation réelle ; même si la porte optique passe, **COG-A2 4 positifs / 8 négatifs reste EN ATTENTE**, sans raccordement F2, pas de propriétés persistées ni catégorie OEM.

## Réutiliser / adapter / créer et repli

Réutiliser `per_s0_lowview_oem_region.py` (rendu OEM, `decode_candidates`, code d'inférence), `sim_ball_segmentation_gt.visible_geom_bbox`, `sim_vis_f_gt_preflight._set_free_joint`, `cata_yolox_categories.prepare_image/validate_model_file`. **Créer un banc hôte expérimental court + tests**, pas un nouveau composant Companion, modèle, caméra ou service. Expériences avec `MUJOCO_GL=osmesa` sous CI, aucune photo privée, résultat **numérique seulement**, aucun fichier RGB/masque/poids publié.

Si la porte échoue, enregistrer les chiffres, retirer l'implémentation expérimentale de la PR finale et ne fusionner éventuellement qu'un rapport qui modifie la décision de chantier ; sinon soumettre le banc uniquement après CI entièrement verte. **Jamais** de modification des moteurs `robotd` 50 Hz, `mediad`, ONNX OEM, protections, sous-modules, WIC B11, SQLite ou Qwen. Robot absent, test RKNN 2 Hz/latence/RSS embarqués inconnu.