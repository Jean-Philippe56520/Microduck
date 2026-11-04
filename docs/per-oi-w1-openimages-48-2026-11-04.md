# PER-OI-W1 — contre-évaluation publique Open Images V7, 48 JPEG, 3 classes faibles

**Date :** 04/11/2026. **Preuve réelle de première exécution :** [GitHub Actions #41868616826](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41868616826), **job spécialisé terminé avec succès** sur la branche `8aee65758a5fa81a1044c2882db7c46294a53679`. Source et sélection préenregistrées dans [#78 commentaire 6636036545](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6636036545) **avant toute inférence**. **PR #298 :** candidate au moment de la rédaction, CI générale du dernier HEAD à vérifier avant fusion. Aucune CI verte ne démontre une capacité de robot.

## Question et témoin

Sur le précédent PER-80 (#296), COCO 800 JPEG, `book` = 5/104 boîtes IoU50, `bottle` = 34/117, `chair` = 65/225. Ces images sont consommées et **ne sont pas relancées**. PER-OI-W1 utilise **Open Images V7 validation** avec annotations de boîtes et votes binaires humains explicites, et le **même modèle figé** YOLOX Nano ONNX SHA256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`, 416 pixels, score 0,25, NMS 0,50, match IoU50. **Ce sont deux populations sélectionnées différemment, leurs pourcentages ne mesurent pas un effet causal du corpus ou du modèle.**

Réemploi : préflights, SHA, votes humains, annotations et contrôles Cat-A2d ; décodeur expérimental 80 classes de PER-80 ; IoU générique existant. Adaptation : sélection strictement disjointe 8 positives + 8 négatives par classe et agrégation ciblée. Aucun réentraînement, nouveau modèle, service, SQLite, commande ou chemin OEM.

## Sources / échantillonnage gelé

- **48/48 JPEG réels** Open Images V7, 8 positifs + 8 négatifs humains par cible `book` / `bottle` / `chair`.
- **240 anciens IDs Open Images exclus** : 48 Cat-A2c + 192 Cat-A2d. Unicité et absence de chevauchement vérifiées avant modèle.
- Empreinte cohorte ordonnée : `6954c9a0136d262a01eeba44b1da35319cf5323d270c73bc306cfd7f5f33179a` ; agrégat empreintes JPEG `21beb1644ee71f9e9553ff0d4ba67d55dad6a4b90e063ed2137a66c6e5c70d7f`.
- Métadonnées officielles Cat-A2d réutilisées avec SHA d'identité, dont boîtes `d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2`. Droits Flickr déclarés, **pas authentifiés photo par photo** ; pas de redistribution, média, ID ou poids dans le dépôt. Pas de preuve de hauteur basse.

## Résultat effectivement inféré sur CPU GitHub Actions

| Catégorie | Positives image proposées | Négatifs humains avec proposition | Boîtes GT | TP IoU50 | Rappel boîte |
|---|---:|---:|---:|---:|---:|
| `book` | 5/8 (62,5 %) | 0/8 | 30 | 6 | 20,0 % |
| `bottle` | 5/8 (62,5 %) | 1/8 (12,5 %) | 14 | 7 | 50,0 % |
| `chair` | 8/8 (100 %) | 0/8 | 30 | 11 | 36,7 % |

Détails : une boîte `book` est marquée `IsDepiction=1` ; ses coordonnées ne garantissent pas une présence physique. Une proposition sur un négatif humain pour `bottle` désigne **un désaccord avec l'annotation humaine**, non un événement dangereux physiquement démontré. Les propositions d'autres classes par image existent dans l'agrégat : 30 livre, 22 bouteille, 44 chaise ; elles ne constituent pas automatiquement des confusions avec la vérité terrain non exhaustive.

**Temps ONNX hôte :** p50 17,380 ms, p95 17,583 ms ; RSS pic processus 311 816 Kio. Ces mesures ne prédisent pas la RAM, les 2 Hz, la chaleur ou l'ordonnancement moteur du RK3566.

## Décision aux seuils FIXÉS avant le run

Critère hôte par classe : sensibilité image ≥70 %, propositions sur négatifs ≤10 %, rappel boîte IoU50 ≥50 %. Livre : échoue sensibilité et rappel ; bouteille : échoue sensibilité et négatifs ; chaise : échoue rappel. **`STOP_PROMOTION`**, comme annoncé avant inférence. **Aucune retouche** des poids, seuils, NMS, liste de JPEG ou règle de détection à partir de ce jeu désormais consommé.

Les tests hôte positifs/négatifs (7/7 sur la dernière CI spécialisée) et les sources/provenance sont validés à l'échelle des outils ; **pas de perception fiable, pas de classification de présence physique, pas de caméra basse attestée, pas de modèle NPU ni d'autonomie**. `robotd` 50 Hz, `mediad`, `enabled=false`, F1, la SQLite, B11, Yocto, Qwen et sous-modules restent inchangés.

**Prochain critère utile (non exécuté)** : chercher un corpus réellement renseigné sur les prises proches du sol / hauteur caméra et les cas écran/photo/inconnu ; ne pas déduire une qualité robot d'une troisième série de photos de hauteur inconnue. Toute nouvelle cohorte doit être gelée avant prédiction et testée contre un témoin déjà défini, sans photographies personnelles exigées.
