# SIM-VIS-F — prévalidation géométrique OEM avant YOLOX

**Préenregistrement du 30/10/2026 — avant tout rendu ou résultat SIM-VIS-F.** Sources : `main@9baa6497147da1828e685032198c051c5b16a7b1`, `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Gitlinks inchangés.

## Pourquoi ce lot apporte une preuve utile

Le lot SIM-VIS-E, PR #200 **fermée sans fusion**, s'est arrêté dans son **premier cas** `box_corridor` avant toute nouvelle inférence (le message `preregistered target not visibly measurable` est émis dans `one_case`, appelé en premier sur cette cible). Les neuf tests logiciels ont passé, **aucune** qualité multiobjet YOLOX n'a été mesurée. L'écart du banc : la boucle arrêtait tout au premier masque invalide, sans rapport par cas. **But limité de SIM-VIS-F :** fournir des GT de géométrie / occultation traçables *avant* toute inférence, ou conclure que les scènes restent inutilisables. Ce n'est pas un détecteur ni un nouveau service.

## Scènes nouvelles, gelées indépendamment de YOLOX

Toutes les coordonnées sont **MuJoCo au repos**, pas des estimations de localisation réelle. Le modèle et la correction caméra proviennent de l'OEM épinglé ; segmentation geometrie `mjOBJ_GEOM` rendue sans RGB, modèle, Qwen, SQLite ni moteur. Les 4 cas suivants diffèrent des cinq positions de SIM-VIS-E.

| Cas | Monde OEM | Pose du tronc (x,y; yaw) | Géométrie de référence | Attendu |
|---|---|---|---|---|
| `cube_south_living` | `scene_apartment.xml` | (-2,8; -2,2; +90°) | `obj_0_geom` (boîte 7 cm), placé sur le sol à 0,45 m **devant la caméra**, selon son axe projeté au sol | ≥80 px |
| `chair_near` | `scene_apartment.xml` | (-2,55; 0,05; 0°) | `liv_chair_seat` (fauteuil fixe OEM) | ≥80 px |
| `pillar_cyan_near` | `scene_vslam.xml` | (3,40; -1,20; +90°) | `vs_pil_c` (pilier cylindrique fixe OEM) | ≥80 px |
| `ball_hidden_by_chair` | `scene_apartment.xml` | (-2,55; 0,05; 0°) | `ball_0_geom` au sol, centre du corps (-1,55; 0,05), fauteuil `liv_chair_seat` devant | 0 px balle + ≥80 px fauteuil + rayon `mj_ray` caméra→centre de balle intercepté par fauteuil avant la balle |

Le cas occultation est un **témoin négatif physique** et n'a pas valeur de perception « objet absent ». Le rayon de témoin vient de MuJoCo et est strictement une évaluation hors robot, **jamais** une mesure ToF ou un feu vert de sécurité. En cas d'incohérence de la segmentation et du rayon, le cas est invalide.

## Porte préfixée et comparateurs

**Succès de préparation GT** : exactement trois positives à ≥80 pixels, un négatif avec balle à 0 pixel, fauteuil visible ≥80 px ET interception géométrique avant la balle, même `qpos/time` figés, même conversion caméra OEM. Toute autre situation → `preflight_gate_met=false` et **aucune inférence YOLOX sur ce jeu** ; enregistrer le masque/bbox/raison de chaque cas, sans déplacer un objet après résultat pour atteindre le seuil. Tous les cas seront examinés même si le premier échoue, pour éviter l'arrêt opaque de SIM-VIS-E. Ne pas entraîner, modifier la focalisation, la caméra ou les seuils sur ces cas.

**Comparaison** : SIM-VIS-E annonçait « cible non visible » sans origine précise ; SIM-VIS-F doit identifier précisément la préparation non valide de chaque scène, à géométrie source OEM vérifiable. Tests PC de refus : géométrie fausse, masque absent, rayon non intercepté, rapport incomplet, horodatage/pose modifiée. `CI green` valide l'exécution et les garde-fous ; **ne prouve PAS** `preflight_gate_met=true`.

Réutiliser : `World/Body/Camera` constructeur et `visible_geom_bbox` de SIM-VIS-B, **aucun** modèle/décodeur/futur code moteur. Règle d'arrêt après cette passe : si la porte n'est pas franchie, ne pas rééchantillonner ces poses pour obtenir une réussite ; passer à des GT préexistantes (COCO/photographies autorisées nouvelles) ou au prochain jalon indépendant. Si elle passe, le prochain lot pourra utiliser les images **désormais prévalidées**, sans retoucher les poses et avec un critère de détection fixé *avant* l'inférence.
