# PER-QUAL-1B — premier banc de comparaison double GT sur 42 JPEG COCO inedits

**Date :** 04/11/2026. **Preenregistrement avant toute inference :** [issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6637951583) ; source et choix des 42 identifiants ont ete geles **sans pixel** dans [PR #300 PER-QUAL-1A](https://github.com/Jean-Philippe56520/Microduck/pull/300), fusionnee au squash `7e16381d1b0e735f2ab17b894459e52694f92e38`, 4/4 CI vertes.

## Manque prouve et question

COCO et Sama-COCO fournissent deux annotations humaines **correlees** pour les memes photos de validation COCO. Sur les 42 nouvelles photos selectionnees a partir de leurs GT uniquement, #300 a mesure 66 boites de classes allouees COCO, 70 boites Sama et 56 appariements IoU50 inter-annotations. Cela ne designe aucune des sources comme verite physique certaine. Ce lot mesure la **sensibilite des statistiques de YOLOX au choix de GT** a image/prediction strictement identique ; il ne re-execute aucune image des 800 COCO #296 ni des anciennes cohortes.

- Exactly 42 nouvelles photos COCO-val : 6 assignees a chacune des classes `sports_ball`, `book`, `bottle`, `chair`, `dog`, `cat`, `person`. Chaque classe est evaluee sur **les memes 42 images**, les 6 allocations n'etant qu'un quota de couverture par classe.
- Exclusions exactes : **1 232 anciennes photos COCO**, fonte et hash source `e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f`, Sama ZIP `c55454f6657ce63891783136cc5dfe5f1e9c5e1748c0d8ca08b456a804eab15f`, cohort SHA `709718feba6185ddd79e2aa492c7eaf74bb2d904dfa6c30e81a25c31dbdb53d5`. Source et quota **verifies avant toute lecture de poids ou photos**.
- Modele temoin : YOLOX Nano original SHA `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`, ONNX CPU, 416 letterbox, score 0,25, NMS 0,50, IoU50, decodeur 80 classes de PER-80 existant. **Un seul passage ONNX par JPEG** ; chaque sortie est confrontee aux deux annotations, classe par classe, avec appariement maximal un-a-un reemploye de PER-QUAL-1A.

## Mesures, tests et arret fixes AVANT analyse

**Mesures primaires par classe, 42 images :** boites GT COCO/Sama, propositions YOLOX communes, appariements COCO/Sama IoU50, rappel COCO/Sama et difference ; propositions non appariees **pas des faux positifs physiques**. Aucune image sans boite n'est automatiquement negative verifiee ; absence de preuve de 20 cm, de vue reellement basse, d'identite ou de presence d'un vivant. Temps et RSS hote seulement descriptifs. Les deux jeux GT sont issus de processus humains correlés, les deux taux ne sont pas deux estimations independantes.

**Tests positifs/negatifs PC** : six tests de comparaison sur fixtures, plus sept tests de source PER-QUAL-1A : egalite de deux GT identiques, cas d'objet supplementaire dans Sama, absent non transforme en vrai negatif, matching maximal 1:1 non glouton, refus de cas manquant/duplique, refus d'une sortie non finie ; source verifiee avant model. La CI specialisee doit vraiment telecharger **42 JPEG publics inedits** et produire 42 inférences au dernier SHA, en plus des CI generales.

**PASS_B de qualite de preuve uniquement** : 42 sorties reelles/42 images, 7 classes, GT dans les deux schemas, hashes stables, tests et CI du SHA final verts. **STOP_SOURCE / STOP_MODEL** : source/hash/licence incompatible, 42 images indisponibles ou corrompues, poids different, erreur ONNX, test negatif echoue, limites de temps, CI non verte. Aucun resultat ne peut autoriser a lui seul une promotion, meme avec un bon rappel : decision **STOP_PROMOTION** jusqu'a validation OEM physique.

## Securite et retour arriere

Simple recherche CPU hote, photo publique temporaire, aucune redistribution ni photo privee. Statistiques seules publiees ; **aucun JPEG, ID image, position de bbox, poids ni secret**. Pas de modification des moteurs `robotd` 50 Hz, `mediad`, `duck-detect`, F1/F2, NPU/RKNN RK3566, SQLite, Qwen, Yocto B11 ou gitlinks OEM. `viewpoint_height=unknown` admissible pour cette etude PC, jamais preuve de representativite du robot. Retour arriere = revert des nouveaux script/tests/workflow/rapport.

**Etat a la redaction :** implementation hote sur branche candidate ; aucune nouvelle inference 42 JPEG encore attestee. Completer le tableau de resultats seulement d'apres la CI reelle du SHA final, apres tests et verification de provenance.
