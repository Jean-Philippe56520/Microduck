# PER-QUAL-1C1 — gel de cohorte publique nouvelle, annotations uniquement

**Date :** 4 novembre 2026. **Autorité :** [plan d'action](plan-action.md). **Préenregistrement AVANT toute image, test modèle ou nouvelle inférence :** [issue #78, porte PER-QUAL-1C1](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6638495898). Le résultat doit rester **INCONNU** tant que le workflow réel n'est pas terminé.

## Pourquoi

La PR #301 a réalisé 42 inférences YOLOX sur des JPEG COCO précédemment inédits, mais a utilisé les indices YOLOX pour lire des boîtes GT indexées par les IDs officiels COCO. Résultats de rappel invalides et PR fermée sans fusion. La PR #302, fusionnée avec 4/4 CI au SHA `8c8e5a05eb903cc9bb7dbf5a02eb7cb3a8e8a64b`, répare le **contrat entre deux espaces d'identifiants** dans la porte des sources, sans avoir validé un modèle embarqué.

**Objectif unique C1 :** geler **un nouveau lot de 42 photos** sur la base exclusive des annotations COCO/Sama, entièrement disjoint des 1 232 images COCO antérieures et des 42 images consommées par #301. Aucun accès image ni modèle dans cette PR.

## Réutilisation et méthode figée

- Même JSON COCO val2017 : SHA256 `e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f` ; même ZIP Sama : SHA256 `c55454f6657ce63891783136cc5dfe5f1e9c5e1748c0d8ca08b456a804eab15f`, mêmes droits déclarés et contrôles de la PR #300.
- Cohorte #301 reconstruite **sans JPEG** et vérifiée par SHA256 `709718feba6185ddd79e2aa492c7eaf74bb2d904dfa6c30e81a25c31dbdb53d5`. **1274 IDs uniques exclus** avant toute nouvelle sélection (1232 historiques et 42 issus de #301).
- Nouvelle graine d'allocation uniquement : `kwipi-per-qual1c1-samacoco-20261104-v1`, tri SHA sur vérités terrain, allocation par rareté, exactement 6 photos pour chacune des sept classes `sports_ball/book/bottle/chair/dog/cat/person`. Aucune optimisation après vision des sorties.
- Le contrat C0 `COCO category_id != yolox_head_idx` doit réussir avec `COCO80_ID_ORDER[head_idx] == category_id` sur sept classes. Les 42 images doivent présenter au moins six boîtes dans chaque annotation pour chacune des catégories assignées, sans groupe/boîte invalide ; l'absence d'annotation ne signifie pas négatif physique vérifié.
- Deux annotations **corrélées**, issues de la même photo COCO et d'un processus Sama qui partait des labels initiaux. Hauteur de caméra inconnue admise uniquement pour une étude PC. Les licences propres aux JPEG restent à contrôler avant tout usage ultérieur, aucune photographie redistribuée.

## Tests positifs / négatifs et arrêts

**Passage C1** : 42/42 nouveaux ID disjoints, signature du nouveau roster rapportée sans identifiant, GT doubles par classe, deux domaines d'ID contrôlés, **0 photo, 0 modèle, 0 inférence, 0 commande OEM**, tests 9 fixtures adversariales et CI générale/spécialisée entièrement vertes sur dernier SHA. **STOP_SOURCE/STOP_SCHEMA** si archive ou cohorte historique divergent, ancienne image récupérée, droits de source non admis, quota insuffisant, modèle/ONNX demandé, source corruptrice ou mapping différent.

**Témoin historique positif** : l'ancien sélecteur avec sa semence par défaut reproduit exactement le roster #300 malgré l'ajout d'une deuxième semence. **Négatifs** : 42 images #301 non exclues, ID historique réutilisé, ancienne empreinte non reconnue, graine arbitraire, catégorie COCO/YOLOX inversée, géométrie ou licence non conformes, absence de GT pour une des classes. Une réussite ne démontre ni fiabilité des 80 classes, ni caméra basse, ni autonomie.

**Suite C2 (non autorisée par une simple PR C1)** : geler SHA du nouveau roster avant tout accès aux pixels, préenregistrer les métriques puis éventuellement évaluer une seule fois les 42 nouveaux JPEG avec les deux identifiants (GT par COCO `category_id`, sortie par `yolox_head_idx`). Les 42 de #301 restent définitivement consommées comme essai invalide ; aucun tuning des poids/seuils sur elles. `STOP_PROMOTION` maintenu.

**OEM et retour arrière** : `mediad`, `duck-detect`, `robotd` 50 Hz, gitlinks, B11/Yocto, ressources RK3566/NPU, SQLite unique et Qwen inchangés. Robot physique absent. Retour arrière = revert du seul sélecteur, de la graine optionnelle, de ses tests et de son workflow. Aucune action physique.
