# PER-QUAL-1C2 — un YOLOX CPU, deux GT corrélées, 42 nouveaux JPEG COCO

**Protocole enregistré AVANT toute inférence** dans [l'issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6638653074). À la rédaction, **aucun nouveau résultat YOLOX n'est revendiqué**. Seule la PR #303 a sélectionné et gelé la nouvelle cohorte **à partir des annotations**.

## Manque et témoin

La PR #301 a réellement exécuté 42 images, mais ses rappels étaient invalides : `coco_category_id` a été confondu avec `yolox_head_idx`. L'essai a été arrêté et la PR fermée sans fusion ; ces 42 images sont définitivement consommées. PR #302 a corrigé le contrat de source et #303 a gelé **42 nouveaux JPEG**. Le présent lot mesure, pour ces 42 images inédites, comment un modèle YOLOX fixe est évalué sous les deux annotations humaines COCO et Sama-COCO **corrélées**.

**Sources et conditions figées avant pixels** :
- `main` de départ `fec98d46de5787651ff1ba379887278b7edbe741` (#303 fusionnée 5/5 CI).
- COCO val2017 SHA256 `e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f`, Sama COCO val ZIP `c55454f6657ce63891783136cc5dfe5f1e9c5e1748c0d8ca08b456a804eab15f`, ancienne cohorte #301 `709718feba6185ddd79e2aa492c7eaf74bb2d904dfa6c30e81a25c31dbdb53d5`, nouvelle cohorte `04bae5d7af2e379b81762a75b7965e849d6d972d40dd56ce16bf28a984122b92`, **1 274 images consommées exclues**, 7 classes × 6 images assignées.
- Baseline YOLOX Nano ONNX original SHA256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`, CPU, 416, score 0,25, NMS 0,50 et IoU50 ; **aucune modification du poids, du décodeur PER-80 ni du seuil**. Un seul appel modèle par JPEG, la même sortie comparée aux deux GT.

## Contrat de validité P0 obligatoire

La vérité terrain est lue avec **l'identifiant officiel COCO** : `person=1`, `cat=17`, `dog=18`, `sports_ball=37`, `bottle=44`, `chair=62`, `book=84`. Le détecteur YOLOX est filtré par **indice de tête zéro-based** : `person=0`, `cat=15`, `dog=16`, `sports_ball=32`, `bottle=39`, `chair=56`, `book=73`. Pour chaque classe, `COCO80_ID_ORDER[head_idx]==coco_category_id` doit réussir. Les six vues assignées à chaque classe portent des GT valides dans **les deux** annotations ; aucune classe ne peut apparaître artificiellement sans GT.

Le nouveau test de régression crée des boîtes sous l'ID COCO réel et des propositions sous la tête YOLOX réelle. Il démontre que `person COCO=1` et `YOLOX=0` donnent un vrai appariement, et que les inversions d'IDs échouent en `STOP_SCHEMA`. Autres cas : objets supplémentaires Sama, absence de GT allouée, matching maximal un-à-un, doublons, sorties non finies/invalides et propositions non appariées jamais qualifiées de « faux positifs physiques ».

**Métriques fixées** : chaque classe sur les mêmes 42 images (pas seulement ses six positives assignées) ; nombre de GT COCO et Sama, propositions YOLOX communes, appariements IoU50 1:1 indépendants, rappels et différence de rappel, propositions non appariées sans attribution de faux positif physique. p50/p95 temps ONNX et RSS hôte descriptifs. **Hauteur inconnue** admise pour diagnostic PC, pas preuve de caméra basse ni de présence réelle.

## Passage, STOP et retour arrière

**PASS scientifique hôte** exige 42/42 vraies images nouvelles contrôlées et 42 sorties modèle, métriques comparables à double identifiant sur sept catégories, checks spécialisés et suite générale **tous verts sur dernier SHA** ; artefact uniquement agrégé sans image, ID, boîte individuelle, poids ni donnée privée. **STOP_EVALUATION** si source, hash, classe, annotation, taille JPEG, ONNX, tests ou CI divergent ; ne pas publier de rappel invalide comme résultat. Quel que soit le rappel : **STOP_PROMOTION**, aucune intégration dans F1, `mediad` ou RKNN sans essai sur robot OEM.

La CI spécialisée ne télécharge le modèle qu'après porte source. Réutilisation : sélecteur #303, mapping #302, décodeur PER-80, `_official_jpeg`, matcher 1:1 existant. Aucun sous-module constructeur, moteur `robotd` 50 Hz, SQLite, Qwen, B11, Yocto, NPU, camera ou politique de sécurité modifié. Retour arrière = retrait des seuls fichiers C2. L'essai sur PC n'autorise pas l'autonomie de Kwipi.

**État :** candidat PR sur GitHub, résultats réels de 42 inférences et CI finale encore à vérifier.
