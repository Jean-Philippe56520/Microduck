# OEM-first — sélection du détecteur multicatégorie (29 octobre 2026)

**Décision : conserver l'architecture OEM de perception, ne pas remplacer le témoin YOLOX-Nano par Rockchip YOLO11n, et ne pas intégrer de nouveau modèle tant que les balles/vues basses ne sont pas évaluées utilement.** Ce lot mesure une aptitude PC sur des photos publiques, **pas** la perception embarquée de Kwipi.

## Porte 0 : objectif, preuve manquante, témoin, arrêt

**Objectif concret :** reconnaître au moins les catégories `person/cat/dog/chair/sports_ball` depuis une caméra basse, sans second propriétaire caméra/NPU ni perturbation du `robotd` OEM à 50 Hz.

**Manque prouvé :** la [PR #182](https://github.com/Jean-Philippe56520/Microduck/pull/182), avec segmentation MuJoCo indépendante, a démontré **1 balle réellement visible manquée par YOLOX** à seuil fixe 0,25. La solution OEM Pollen actuelle `duck-detect`/YOLO11n RKNN **ne reconnaît que les autres Microducks** ; son format [1,5,2100] et son décodeur ne sont pas directement interchangeables avec un YOLO multicatégorie.

**Réutiliser avant de créer :**
- **Pollen épinglé** `microduck@942e58e3aa6dbb28e7037203fff11866122c7567` : `mediad` propriétaire de la caméra, `uyvy` échantillonnage/rotation, `duck-detect` runtime RKNN et repli ONNX CPU, `media.detections` et `robotd` seul propriétaire moteurs/sûreté. Aucune modification OEM ou mise à niveau des submodules.
- **SoC-vendor Rockchip :** [RKNN Model Zoo](https://github.com/airockchip/rknn_model_zoo/tree/837db8e992815ff8647eadb709f07067f4bc3a71/examples/yolo11), version source `837db8e992815ff8647eadb709f07067f4bc3a71`, cible explicite **RK3566**, modèle COCO 80 catégories, format optimisé **9 sorties** ; outillage adapté à une évaluation ONNX CPU hôte. L'ONNX 640×640 fait **10 527 859 octets**, SHA-256 `62a3751662e06c678debb54b113c211d918f245ea6d3aea0b09fc418b8fc7705`. Contrat et digest vérifiés lors de la [CI de préflight #40929896414](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40929896414). **Support dans un exemple ≠ runtime RKNN embarqué prouvé**.
- **Licence :** démo RKNN Model Zoo sous **Apache-2.0**, mais le dépôt d'origine [`ultralytics_yolo11`](https://github.com/airockchip/ultralytics_yolo11/blob/main/LICENSE) contient une licence **AGPL-3.0**. Les droits et obligations applicables aux poids et à l'intégration/distribution doivent être explicitement éclaircis **avant** embarquement. Modèle téléversé **nulle part** dans notre dépôt.
- **Témoin inchangé :** Megvii YOLOX-Nano ONNX (Apache-2.0), SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`; mêmes cinq catégories, score **0,25**, et même corpus. Le code évaluateur, non intégré à `main`, est tracé sur la branche [expérimentale `feat/oem-first-rockchip-multiclass-20261029`](https://github.com/Jean-Philippe56520/Microduck/tree/ffd1e9e40f5049b4232fe064ebc1616788ea684f) (6 contrôles positifs/négatifs du décodeur). Le post-traitement Rockchip dérive de son exemple Python, sans licence du modèle présumée.

**Critère de poursuite défini avant l'essai :** macro AP50 du candidat ≥ macro AP50 du témoin + **0,03**, au moins une **balle supplémentaire correctement localisée**, et au plus une image négative supplémentaire avec fausse alerte. Le test ne doit **pas** devenir une recherche de seuil sur les données évaluées. Si non franchi, **STOP** pour ce modèle/corpus, pas de conversion RKNN ou déploiement.

## Exécution mesurée — [CI OEM-FIRST-RK-A1 #40930605777](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40930605777)

Évaluation réelle ONNX Runtime CPU sur **18 photos COCO2017 val** (42 objets annotés), **distinctes par identifiant des deux lots historiques de 24 + 24**. Sous-ensemble fixe par SHA (3 exemples demandés/catégorie + 3 sans catégorie cible, certains contiennent plusieurs objets). Les boîtes proviennent du COCO officiel, **pas** du détecteur ; image et poids téléchargés temporairement depuis les sources publiques, jamais archivés avec le rapport. Les métadonnées indiquent des licences photo CC BY 2.0 ; les droits de chaque photo originale et la hauteur optique ne sont pas indépendamment vérifiés. Deux vues peuvent partager un lieu : unicité d'ID **n'est pas** indépendance physique de scène. Une évaluation sur images COCO ne remplace pas Cat-A2b à 100–300 mm.

| Mesure sur les mêmes 18 photos | YOLOX-Nano (témoin) | Rockchip YOLO11n (candidat) |
| --- | ---: | ---: |
| TP IoU≥0,50 / FP / FN | **27 / 7 / 15** | **29 / 3 / 13** |
| Précision / rappel | 0,7941 / 0,6429 | **0,9063 / 0,6905** |
| Macro AP50, catégories présentes | 0,546818 | **0,555115** |
| Personnes, TP / GT | 19 / 24 | **21 / 24** |
| Chats, TP / GT | 2 / 3 | 2 / 3 |
| Chiens, TP / GT | 4 / 4 | 4 / 4 |
| Chaises, TP / GT | 2 / 7 | 2 / 7 |
| **Balles, TP / GT** | **0 / 4** | **0 / 4** |
| Images sans catégories cibles provoquant une alerte | 0 / 3 | 0 / 3 |
| Inférence CPU médiane / p95 hôte | **7,377 / 9,353 ms** | 33,985 / 49,159 ms |

[Artefact JSON complet (identifiants, métriques par classe, durées, empreintes)](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40930605777/artifacts/12922821014). Les 6 tests de protocole/sortie Rockchip ont réussi. La comparaison CI est **verte** : cela prouve que l'essai a abouti, **pas** que la porte de qualité est franchie.

**Résultat de décision :** amélioration macro AP50 **+0,008297**, soit **moins** que +0,03 ; balles **0/4 contre 0/4**, aucun progrès ; pas d'alerte négative supplémentaire. La porte est explicitement **`false`**. Rockchip YOLO11n peut avoir un intérêt à explorer ultérieurement, **pas sur la base de ce lot**. Les temps PC ne prédisent pas les performances NPU/CPU/RAM/température du RK3566, ni la continuité du `robotd` à 50 Hz.

## Suite retenue et frontières

- **Conserver** `mediad`, son unique source caméra, `duck-detect`/RKNN/ONNX (mono-classe Microduck), `tofd`, `robotd`. Ne pas créer un second propriétaire de caméra ni piloter des moteurs depuis Companion.
- **Ne pas fusionner** l'adaptateur expérimental Rockchip dans `main` : il n'apporte aucun gain suffisant pour Kwipi ; le code de l'essai et son artefact restent consultables dans la branche/CI. Ne jamais copier le modèle AGPL par défaut dans le firmware.
- **Reprendre la qualité visuelle** seulement lorsque nous disposons d'un nouveau corpus indépendant et utile (balles visibles de différentes tailles/angles, chaises, chat/chien/personnes de près, écrans trompeurs, négatifs, hauteur mesurée), ou d'un candidat existant avec une justification crédible de gain et un protocole pré-enregistré. Les **29 photos privées** ne sont pas une preuve autonome de vérité terrain ni un jeu de test neuf validé ; ne pas les publier.
- **Poursuivre en parallèle les jalons indépendants** de mémoire/motivations/inaction et les contrôles OEM déjà disponibles ; ne pas bloquer tout Kwipi sur une performance de balle encore insuffisante.
- **Risques non levés :** modèle NPU Rockchip non converti ni exécuté sur robot, `mediad` sous simulateur GitHub bloqué par `webrtcsink` (PR #181 brouillon), SIM-E2 #101 non résolu, perception réelle non validée, licence et ressources embarquées non conclues.
- **Rollback du lot documentaire :** supprimer ce rapport et le lien dans `docs/plan-action.md` ; ni code moteur, capteur, ONNX, sous-module, mémoire ou médias privés n'ont changé dans `main`.

**Conclusion :** sélection OEM-first effectuée avec mesures comparables et négatives sur la classe balle. **Aucun nouveau détecteur retenu.** Décision utile, pas nouvelle capacité autonome.
