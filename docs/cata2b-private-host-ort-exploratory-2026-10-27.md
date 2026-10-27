# Cat-A2b — prises basses privées : essai CPU Windows et relecture exploratoire V3

**27 octobre 2026 · Compte rendu agrégé uniquement · Aucune photographie ni annotation privée dans GitHub.**

## Statut et périmètre

- **Évalué localement sur PC :** 29 JPEG privés capturés au ras du sol, intégrité locale vérifiée, inférence réelle YOLOX-Nano sur CPU Windows 11 avec ONNX Runtime 1.21.0, comparaison des propositions avec OpenCV DNN et relecture *exploratoire* des annotations V3.
- **Non validé :** vérité terrain indépendante, séparation de sites/séances, hauteur du **centre optique** mesurée avec règle, précision de reconnaissance généralisable, rejet d'inconnus, fonctionnement du capteur Kwipi/RK3566/NPU ou sécurité motrice.
- **Provenance :** hauteur **20–30 cm déclarée par l'opérateur**, non instrumentée ; photos d'un environnement domestique présumé unique, comprenant **12 sous-scènes et 8 groupes de vues liées**. L'image basse réelle d'un smartphone ne constitue pas une calibration de la caméra finale du robot.
- **Confidentialité :** clichés, boîtes par image, empreintes privées et sorties détaillées restent sur le PC. Aucun visage, nom, identité, audio, adresse ou support privé n'est joint à cette PR. Le consentement/droit des prises reste à confirmer pour un éventuel réemploi ; **aucune mise à disposition publique n'est autorisée**.

## 1. Inférence réelle ONNX Runtime, sans adaptation du modèle

Le même YOLOX-Nano COCO de [Cat-A](../microduck_companion/cata_yolox_categories.py) et le même décodage IoU/NMS de [Cat-A2a](../microduck_companion/cata2_bbox_eval.py) sont réutilisés : entrée **416 × 416**, seuil de confiance **0,25 inchangé**, poids ONNX SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` (licence modèle Apache-2.0, upstream Megvii).

L'opérateur a exécuté sur son **PC Windows 11**, sous Python 3.12 isolé, avec `onnxruntime==1.21.0`, `numpy==1.26.4`, `Pillow==11.3.0` et `opencv-python-headless==4.10.0.84`. Sortie textuelle locale rapportée :

| Indicateur sur hôte Windows | Résultat |
| --- | ---: |
| JPEG contrôlés et inférés | **29 / 29** |
| Boîtes proposées par ONNX Runtime | **66** |
| Appariements très proches avec les 66 propositions OpenCV DNN | **66 / 66** |
| Médiane des durées d'inférence CPU ONNX Runtime | **13,109 ms** |
| P95 des durées d'inférence CPU ONNX Runtime | **13,622 ms** |
| RSS maximal déclaré du processus entier | **107 808 Kio** (≈ 105,3 Mio) |
| Images transmises à un service externe ; appels Qwen ; commandes moteurs | **0 ; 0 ; 0** |

Le protocole de concordance rapportait des paires par **même catégorie, IoU ≥ 0,99 et écart de score ≤ 0,001**. Cela confirme une **parité de sorties entre moteurs sur ce lot**, pas l'exactitude de la perception. Les mesures PC ne prédisent ni le temps d'inférence RKNN, ni RAM, ni thermique, ni batterie sur RK3566. Cet essai **n'a pas été exécuté en CI GitHub** ; les valeurs ci-dessus proviennent du journal Windows fourni par l'opérateur.

Répartition des **propositions du modèle, non des objets réellement identifiés** : `person` **27**, `cat` **11**, `dog` **9**, `chair` **18**, `sports_ball` **1**.

## 2. V3 : confrontation aux annotations encore non indépendantes

Après lecture des images et des propositions du modèle, l'assistant a corrigé un premier brouillon de **48** boîtes pour proposer une V3 de **50** boîtes ; **12 annotations restent ambiguës**. Le réexamen a notamment montré que deux boîtes initiales de balles étaient mal positionnées dans les pixels originaux. Une balle est finalement localisée, l'autre non ; ne pas réutiliser l'ancienne conclusion « 0/2 ».

Le diagnostic suivant réutilise les **66 sorties OpenCV DNN sauvegardées**, le seuil **0,25** et l'appariement **IoU ≥ 0,50** ; les 66 sorties ONNX Runtime sont concordantes d'après le journal Windows, mais **les coordonnées détaillées ONNX Runtime n'ont pas été vérifiées indépendamment dans cette revue**.

| Catégorie COCO | TP illustratifs | FP illustratifs | FN illustratifs |
| --- | ---: | ---: | ---: |
| `person` (enfants et adultes, sans identification) | 10 | 17 | 6 |
| `cat` | 5 | 6 | 0 |
| `dog` | 4 | 5 | 1 |
| `chair` (certaines chaises/tabourets ambigus) | 6 | 12 | 16 |
| `sports_ball` (balle jouet, correspondance sémantique à confirmer) | 1 | 0 | 1 |
| **Total** | **26** | **40** | **24** |

**Calculs exclusivement illustratifs**, d'après le brouillon V3 : précision micro **26 / 66 = 39,4 %**, rappel micro **26 / 50 = 52,0 %**, AP50 macro des classes présentes **≈ 0,503** (valeur du calcul exploratoire antérieur, non recalculée indépendamment ici). Les annotations V2 conduisaient à **21 TP / 45 FP / 27 FN** : l'écart démontre la sensibilité au brouillon d'annotation. **Ne pas qualifier ces valeurs de précision, rappel ou AP50 validés de Kwipi.**

**Écrans :** parmi les 27 propositions `person`, **quatre** étaient attribuées à des personnes affichées sur une télévision, et non présentes physiquement dans la pièce. La différence « représentation à l'écran » / « présence physique » doit être tracée séparément ; une proposition de `person` sur une image TV n'est pas une rencontre. [Piste TV-CURIOSITY #95](https://github.com/Jean-Philippe56520/Microduck/issues/95) : *conception prévue seulement*, sans nouvelle capture ou consultation Qwen.

## 3. Pourquoi Cat-A2b #78 reste ouvert

Le [validateur privé Cat-A2b](../microduck_companion/cata2b_private_low.py) exige **une mesure documentée du centre optique**, des annotations `all_targets_reviewed` et `privacy_and_consent_reviewed` dûment confirmées et des **splits sans fuite entre scènes, séances et sites**. Il borne aussi **TEST à 25 images** : le lot exploratoire de 29 vues liées **n'a donc pas été injecté frauduleusement dans le protocole de benchmark formel**. Les annotations ne sont pas contresignées indépendamment et le même assistant les a relues **après** les prédictions (risque d'ajustement a posteriori). Des clichés différents du même chat, chien ou mobilier ne sont pas des observations indépendantes.

**À faire pour une évaluation plus probante :**
1. Contrôler toutes les boîtes, les négatifs et les droits par une personne **sans voir les propositions du modèle**, puis geler la vérité terrain locale.
2. Photographier une règle placée au niveau du centre optique pour chaque séance ; confirmer la hauteur, l'inclinaison et la compatibilité future du capteur robot.
3. Collecter d'autres séances et sites distincts, répartir les groupes entiers entre `train`, `validation` et `test`, documenter les classes/occlusions/négatifs.
4. Exécuter **localement** le protocole Cat-A2b officiel sur `test` (25 JPEG maximum par lot), sans ajuster seuil ni poids au test, puis publier **seulement les résultats agrégés**.
5. **Quand le robot est disponible :** `scripts/resource-audit.sh`, validation `mediad` et protections `robotd` en conditions supervisées ; aucune conclusion PC ne vaut validation robot.

## 4. Décision de réutilisation et statut du chantier

- **OEM épinglé :** `mediad` reste propriétaire de la caméra, `robotd` des moteurs et de la sûreté ; aucune interface OEM n'est changée. Les [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) (cerveau) et [#414](https://github.com/pollen-robotics/microduck/pull/414) (carte/navigation) étaient **ouvertes et non fusionnées lors de la vérification du 27/10/2026**.
- **Companion :** réutilisation du modèle fixé Cat-A, de son prétraitement et de la métrique Cat-A2a ; [protocole privé existant](cata2b-private-low-camera-protocol-2026-10-26.md), [registre de réutilisation C3](community-reference-registry-2026-10-26.md). Aucun moteur de détection concurrent, nouvelle SQLite ou poids entraînés.
- **Tiers communautaires :** aucune dépendance ou revendication de résultat importée (QuackNav, Quacksat, Twin, Smartulf, Lab/Studio).
- **Livré par la PR documentaire :** seulement texte public sans données individuelles. **Pas de nouveau code ni entraînement, simulation, déploiement, test physique, téléchargement d'image privée ou changement des sous-modules.** Les tests logiciels antérieurs et l'exécution Windows locale sont des preuves **distinctes** des éventuels contrôles CI de cette PR.

Suivi : [Cat-A2b #78](https://github.com/Jean-Philippe56520/Microduck/issues/78).
