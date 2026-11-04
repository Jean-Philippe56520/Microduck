# PER-YOLOX-SM-0 — modèles Rockchip S/M, source COCO neuve et préflight ONNX sur PC

**Date :** 04/11/2026. **Autorisation utilisateur :** « Je valide » après proposition explicite de tester **YOLOX-S puis YOLOX-M** sur les mêmes images, sans changement OEM. **Source du projet avant branche :** `main@420664d97f33fff9ffeb8e4caea26f096799da59`. **Protocole préenregistré AVANT code, modèles et images :** [issue #78, commentaire #6643049833](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6643049833). La PR C/E-2 #309 est indépendante et encore à qualifier/fusionner selon ses propres CI.

## Raison de cette expérience

Le `mediad` constructeur contient déjà un détecteur **mono-classe Microduck** à 2 Hz. Nos précédents YOLOX-Nano hôtes étaient limités et plusieurs essais d'évaluation étaient invalides à cause des espaces **COCO category_id** vs **YOLOX head_idx**. Il n'est pas démontré que cela rend impossible une détection multicatégorie sur RK3566. Rockchip publie officiellement des exemples **YOLOX-S/M optimisés pour RKNN** et un banc d'inférence 640×640 INT8 sur RK3566. Les valeurs **15,6 FPS S** et **6,7 FPS M** sont les **benchmarks du fournisseur pour le NPU et modèle seul**, pas sur le robot Microduck ni mediad. La charge mémoire/thermique et les pré/post-traitements ne sont pas inclus dans ces FPS.

**Source officielle figée** : `airockchip/rknn_model_zoo@837db8e992815ff8647eadb709f07067f4bc3a71`, [README du modèle](https://github.com/airockchip/rknn_model_zoo/blob/837db8e992815ff8647eadb709f07067f4bc3a71/examples/yolox/README.md), [post-traitement](https://github.com/airockchip/rknn_model_zoo/blob/837db8e992815ff8647eadb709f07067f4bc3a71/examples/yolox/python/yolox.py), [conversion](https://github.com/airockchip/rknn_model_zoo/blob/837db8e992815ff8647eadb709f07067f4bc3a71/examples/yolox/python/convert.py), [letterbox centrée noire](https://github.com/airockchip/rknn_model_zoo/blob/837db8e992815ff8647eadb709f07067f4bc3a71/py_utils/coco_utils.py), [LICENSE Apache-2.0 du code](https://github.com/airockchip/rknn_model_zoo/blob/837db8e992815ff8647eadb709f07067f4bc3a71/LICENSE). La licence des **checkpoint ONNX hébergés séparément** n'est pas automatiquement établie par celle du code ; aucune redistribution du poids autorisée à ce stade.

## Contrat concret

| Variante | Origine/entrée | Sortie attendue | Portée |
| --- | --- | --- | --- |
| YOLOX-S Rockchip | 640×640, float32 RGB `[1,3,640,640]` sans normalisation, letterbox noire | 3 grilles `[1,85,80,80]`, `[1,85,40,40]`, `[1,85,20,20]` | Candidat compatible RK3566 annoncé, non validé sur robot |
| YOLOX-M Rockchip | **Même** pipeline | **Même** contrat | Candidat plus coûteux, qualité réelle non encore évaluée |
| YOLOX-Nano hôte inchangé | 416×416, `MODEL_SHA256=c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` | `[1,3549,85]` | Témoin sur les **mêmes images** à la phase suivante, NMS différent signalé |

**Post-traitement fournisseur S/M** : score objectness × score max de catégorie ≥0,25, NMS global IoU>0,45, boîtes reprojetées après padding centré, classe YOLOX zéro indexée séparée de l'ID COCO. Limite de 80 propositions et de 1 500 candidates, **refus explicite** au-delà plutôt qu'un résultat trompeur. Le choix de paramètres est figé avant l'inférence ; aucune optimisation opportuniste sur les mêmes images.

### Sources et cohorte

Réutiliser les contrôles **fusionnés** QUAL-R0, PER-80, QUAL-1A/C1 et les sources de labels :
- COCO val2017 SHA `e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f`, annotations CC BY 4.0 ; images seulement sous licence photo COCO `id=4` (CC BY 2.0), sinon STOP ;
- Sama-COCO val SHA archive `c55454f6657ce63891783136cc5dfe5f1e9c5e1748c0d8ca08b456a804eab15f` ; deux GT **corrélées** car annotateurs Sama ont vu COCO, jamais « double vérité indépendante » ;
- exclusion exacte de **1 316 images VAL historiques** : anciennes 432 + PER-80 800 + #301 42 + #304 42. Vérifier les deux derniers SHA rosters `709718feba6185ddd79e2aa492c7eaf74bb2d904dfa6c30e81a25c31dbdb53d5` et `04bae5d7af2e379b81762a75b7965e849d6d972d40dd56ce16bf28a984122b92`. #301/#304 restent non fusionnées, données consommées **non recyclées** ;
- sélection déterministe **nouvelle** de 42 images (6 positives pour chaque catégorie `sports_ball/book/bottle/chair/dog/cat/person`) via le **sélecteur et la graine `SEED_C1` existants**, mais **après** toutes les exclusions, uniquement via annotations avant observation des modèles. Enregistrer SHA du roster avant pixels. Même JPEG pour S/M/Nano au futur score.

Le lot présent est volontairement scindé en deux portes :
1. **PER-YOLOX-SM-0 / SOURCE + ABI** (**objet de cette première PR**) : tests positifs/négatifs hors réseau, GT officielle et cohortes contrôlées, puis téléchargement **éphémère** des deux ONNX optimisés depuis les liens du README Rockchip seulement **après SOURCE PASS**. Calcul des SHA-256 **réels des checkpoints** et vérification par onnxruntime des 3 sorties ; 1 exécution chacun sur image **synthétique noire**. **Aucune photo JPEG récupérée ni aucun score de précision**. Sortie = empreintes, contrat ABI, sélection non révélée et arrêt si accès/model/GT/CI incorrect.
2. **PER-YOLOX-SM-1 / comparaison réelle** (**conditionnelle, pas livrée ici**) : **seulement après** figer en code les deux SHA obtenus en phase 0, activer `benchmark` sur les 42 JPEG approuvés, Nano/S/M identiques, mesurer GT COCO/Sama IoU50, confusions, abstentions, p50/p95 et RSS hôte. Toute absence de poids/source, NMS non vérifiable, catégorie incorrecte, source libre insuffisante ou CI rouge = STOP sans faux score.

## Scénarios et preuve

**P1** : 1 316 anciennes images exclues exactement, sans aucun chevauchement ; 42 nouvelles, 7 classes×6 positifs GT COCO/Sama, licences photo id=4, source/roster hash.
**P2** : 3 têtes de forme exacte même si l'ordre des sorties change, source S/M seulement, RGB/letterbox corrects, 80 classes COCO, candidate et coordonnée de fixture cohérentes.
**P3** : vérification CPU ONNX des deux poids sur entrée synthétique + SHA et taille réellement relevés. Aucun fichier privé, image, ID unique, boîte annotée, poids ni secret dans les artefacts CI ; sortie agrégée numérique.
**N1–N4** : doublon d'ID, collision historique, classe COCO/YOLOX inversée, mauvais header de modèle ou tête Nano simple, NaN, score hors borne, boîte dégénérée, candidate NMS en doublon, effet physique inventé, mémoire modifiée : refus/STOP. Suite générale CI sur SHA final 100 % verte avant fusion. Une erreur de téléchargement externe n'est pas une preuve que RK3566 ne peut pas exécuter YOLOX.

**Porte PASS de phase 0** : **préflight metadata complet + 2 SHA-256 ONNX + 2 exécutions synthétiques + ABI à trois têtes + tests adversariaux/CI verts** ; cela ne dit encore **rien** de la qualité sur images naturelles. Pour phase 1, les nouveaux scores mêmes GT ne permettent que le **diagnostic PC** et un classement sur petite cohorte ; 42 images ne prouvent ni 95–100 % de précision, ni absence de photo d'écran, ni angle bas, ni identité, ni autonomie.

## Contrainte d'intégration et retour arrière

Aucune modification de `robotd`, `mediad`, `duck-detect`, `upstream/`, ONNX embarqué, B10/B11, Yocto, runtime Kwipi, `ExperienceMemory` ou politique de sécurité. Source et poids S/M restent uniquement dans le dossier temporaire CI. Le robot réel n'est pas disponible : pas de preuve RAM/NPU/thermique ni de 2 Hz opérationnel, et le contrôle 50 Hz reste invariant. VIS-FOCUS-A2 (suivi temporel) reste `STOP_A2_SOURCE_NOT_QUALIFIED`, EX4-C2 reste en attente d'une fin OEM et d'un effet indépendant.

**Rollback** : arrêter immédiatement l'expérience en cas de porte source ou ABI échouée, laisser la branche non fusionnée, ne pas relancer des poids/ressources alternatifs pour « sauver » la validation sans nouveau protocole. Aucun déploiement, flash ni image privée.
