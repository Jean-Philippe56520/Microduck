# SIM-VIS-D — scènes OEM distinctes et frontière F2 « unknown »

**Préenregistrement : 30 octobre 2026, AVANT exécution de ce lot.** Autorité : [plan d'action](plan-action.md), [PER-OEM-0](perception-oem-rknn-2hz-plan-2026-10-29.md), [protocole de réemploi](development-reuse-protocol.md). **N'est ni une intégration `mediad`/RKNN ni une validation robot**.

## Objectif et manque prouvé

SIM-VIS-C [CI #41026957215](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41026957215) a localisé la balle **3/3** (IoU top3 >0,50), mais dans **le même appartement**, sans reconnaissance de sa catégorie (0/3 `sports_ball`). F1/F2 n'accepte aujourd'hui que `mock_fixture_unix`; l'OEM ne livre pas une chaîne perception multicatégorie authentifiée vers Kwipi. Il reste à vérifier sur un **autre monde constructeur** si une région détectée peut donner, dans une projection de test **explicitement fictive**, `inspect unknown` ou `idle` via le vrai F2 (aucune nouvelle logique cognitive), **sans réutiliser le masque de vérité terrain pour décider**.

Code existant réutilisé : `World`, `Body`, `Camera` constructeur, `sim_ball_segmentation_gt.visible_geom_bbox`, `cata_yolox_categories.prepare_image/validate_model_file`, `yolox_attention_candidates.decode_candidates` (seuil d'origine `0,25`, NMS inchangée), `AutonomyBrain.propose_balanced_passive`, `PassiveObservationJournal` et **une seule** `ExperienceMemory(":memory:")` par cas de test. Un seul petit banc hôte, sans nouveau pilote ou arbitre, aucune modification des sources épinglées, aucun modèle/driver/capture nouveau.

## Cas fixés et témoins (avant inférence)

Utiliser le modèle OEM `microduck_rl@b02fdea4` **en lecture seule** avec une seule instance statique :

| Cas | Scène OEM | Situation préfixée | Vérité terrain indépendante |
|---|---|---|---|
| A | `scene_ball.xml` | balle 70 mm à **0,62 m devant la caméra** selon son axe au sol | Masque geom `ball_geom`, ≥80 pixels pour cas positif valide |
| B | `scene_ball.xml` | même balle **0,70 m derrière la caméra** | **0 pixel** de `ball_geom` visible, témoin hors champ |
| C | `scene_vslam.xml` | robot placé statiquement à **(1,65 m; 1,80 m)**, yaw 0, face au **pilier OEM `vs_pil_r`** | Masque geom `vs_pil_r`, ≥80 pixels pour cas positif valide |

Ces scènes contiennent respectivement la balle OEM de **70 mm** et des repères **non-ballons** : elles sont distinctes de `scene_apartment.xml` de SIM-VIS-C. Le cas B est **hors champ**, **pas** une occultation physique par un obstacle. Les occultations partielles et les trompe-l'œil écran/photo demandent d'autres GT/sources : **non validés par ce lot**. Aucun déplacement motorisé, `mj_step`, changement de poids, de caméra ou de seuil.

Les RGB OEM et masques géométriques sont pris **au même état immobile**, tournés à 90° comme `mediad`. Une boîte de géométrie sert **uniquement** à évaluer l'IoU des régions ; elle **ne sert jamais** à créer une observation pour F2. Compter top1/3/5, IoU≥0,50 sur géométrie cible, score du modèle, temps d'inférence et de décodeur.

## Comparateur F2 et règle de décision préalable

Chaque lot de régions top3 est projeté dans **une fixture hôte `mock`**, avec uniquement `object_label="unknown"`, **confiance exactement égale** au score YOLOX, piste éphémère synthétique et `source="mock"`. Ce transport est déclaré **fictif et hors production** ; il **ne transforme pas une caméra simulée en capteur OEM authentifié**. F2-B existant est appelé **une seule fois** avec ses motivations par défaut et une SQLite temporaire en RAM ; aucune entrée de souvenir, catégorie, récompense, objet ou préférence n'est écrite. Les champs de classe COCO de YOLOX ne peuvent pas devenir un fait.

**Témoin négatif** : même F2 avec régions vides ou score < seuil F2 `DETECTION_CONFIDENCE=0,80` ; attente `idle`, sans `inspect`. **Positif synthétique F2** : une région de fixture à score ≥0,80 et fraîche peut proposer `inspect unknown` ; le verdict sur les vraies régions OEM simulées dépendra de **leur score mesuré**, non d'une confiance gonflée. **Négatifs adversariaux** : provenance `sensor` présentée dans un `snapshot mock`, horodatage périmé/futur, score NaN, région malformée, absence de cible GT, et prétention de catégorie reconnue doivent être refusés ou rester `idle` sans mouvement.

## Critère de succès et arrêt

1. Trois scènes construites sans modifier `upstream/`, géométrie OEM vérifiable : A ≥80 pixels, B=0 pixel, C ≥80 pixels ; sinon **arrêt `insuffisant`**.
2. **Au moins 1 des 2 positifs** localisé par top3 à IoU≥0,50 (la classe COCO est ignorée) ; sinon `insuffisant`, aucun tuning sur ces scènes. Top1/top5 sont des comparateurs.
3. F2 vrai code : quand score ≥0,80 `inspect unknown` ou abstention due à ses motivations ; score insuffisant, source périmée/non fiable, région vide : `idle`. Aucune sortie `ball`, `person`, `known`, moteur, Qwen, identité, localisation métrique ou effet causal.
4. CI Python + vraie exécution MuJoCo/ONNX sur les SHAs épinglés ; aucune image brute, photo privée, sous-module, SQLite sur disque ou rapport de caméra personnelle publié.

**Décision stricte :** un résultat positif ne permet qu'une **preuve de compatibilité de la chaîne de test MuJoCo→région→F2 via mock**. Il ne permet pas le transport OEM de production, la mémoire des objets, la navigation ou une reconnaissance de balle. Un échec sur la scène indépendante stoppe ce sous-chantier ; ne pas déplacer les objets, adapter les scores ou recommencer la même évaluation pour fabriquer un succès. Si F2 s'abstient sur les scores véritables, consigner cette limitation plutôt que baisser `DETECTION_CONFIDENCE`.

## Résultats mesurés — vrai rendu MuJoCo OEM, chaîne F2 mock seulement

[CI constructeur et ONNX #41028975787](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41028975787) **réussie** sur le SHA de code `02c8a7bab651da95c45aa28672186c6442e7d402`. Les tests du banc MuJoCo (10 SIM-VIS-B + 7 SIM-VIS-D) ont réussi, sans modifier les deux gitlinks OEM, la caméra ou les poids YOLOX. Le verdict ci-dessous provient du JSON imprimé dans les logs de ce run, et non de fixtures fabriquées.

| Cas | Pixels de la géométrie cible | Régions top3 | IoU top3 | Score candidat maximal | Réponse F2 **dans la fixture** |
| --- | ---: | ---: | ---: | ---: | --- |
| A `scene_ball` à 0,62 m | 1 990 | 1 | **0,931329** | **0,876814** | `inspect unknown` |
| B `scene_ball` hors champ | 0 | 0 | n/a | aucun | `idle` |
| C `scene_vslam` pilier | **94 576** | 0 | 0 | aucun | `idle` |

Le masque indépendant confirme le pilier géométrique **visible** : son absence de région est donc un **échec de généralisation pour ce repère**, pas un problème d'invisibilité. Le cas A apporte une localisation géométrique réussie sur une scène autre que l'appartement, mais n'apporte **aucune reconnaissance de catégorie**. La borne préenregistrée de **≥1/2 positifs localisés** est atteinte (1/2) ; le témoin hors champ a zéro pixel/zéro région. **Ne pas relever** le score du pilier, déplacer le robot ou répéter ce jeu pour obtenir 2/2.

Le test logiciel F2 réutilise vraiment `AutonomyBrain.propose_balanced_passive` ; son entrée est fabriquée comme `mock_fixture_unix` par le banc et **non** acquise auprès de `mediad`. Pour la seule région A, le score ONNX 0,876814 est conservé tel quel (> seuil F2 0,80), ce qui produit `inspect unknown` et non `observe ball`. B et C rendent `idle`. Tests négatifs : score <0,80, NaN, fausse catégorie, horodatages dépassés/futurs et source `sensor` illégitime sont refusés ou conduisent à l'inaction.

Coût des seules trois inférences sur exécuteur CI hôte : **6,958 / 6,824 / 6,818 ms**. Ce n'est ni un échantillon significatif de p95, ni une mesure de `mediad`, RK3566, RAM totale, NPU, température, batterie ou disponibilité motrice 50 Hz. `mj_step` jamais appelé ; caméra et rendu statiques. Zéro écriture d'expérience, zéro moteur, Qwen, identité, effet ou média personnel.

**Décision** : `progres_demontré` sur **une** nouvelle scène de balle et sur **le contrat logiciel F2 via fixture mock** ; `insuffisant` pour détection générale d'objets inconnus et pour intégration de perception OEM. Suite : GT inédites pour des objets variés et, si gain prouvé, audit du vrai flux `mediad`/RKNN 2 Hz sans second pilote ni attribution de catégorie à partir d'une simple région.
