# R2-B+2 — Reconnaissance d'objets ressemblants : banc ABO de chaises et résultats négatifs

**26 octobre 2026 · évaluation réelle effectuée sur ordinateur en CI ; aucun modèle d'identification d'instance retenu, aucune validation robot.**

**Preuve principale :** [GitHub Actions R2-B+2 #40380437787](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40380437787) (succès d'exécution). [Tests Python #40380437776](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40380437776) : **1001 tests découverts, 1 ignoré, aucun échec**. Code et règles de sélection : [`r2b2_abo_confusables.py`](../microduck_companion/r2b2_abo_confusables.py), [scoreur R2-B existant](../microduck_companion/r2b_independent_capture_eval.py).

## 1. Question, provenance et non-duplication

**Question :** le même objet est-il retrouvé sous de nouveaux angles lorsqu'il faut aussi rejeter **d'autres produits de même catégorie**, contrairement au [premier banc ABO de 12 séquences variées](r2b-independent-capture-evaluation-2026-10-26.md) ?

Le [plan R2-B+2](r2-follow-up-execution-plan-2026-10-26.md), le [protocole réutiliser/adapter/créer](development-reuse-protocol.md), le [registre communautaire](community-reference-registry-2026-10-26.md), les sources OEM épinglées et nos modules R2-B/M1-B2 ont été consultés avant réalisation.

| Élément | Décision |
| --- | --- |
| Acquisition de vues originales et contrôle de sources | **Réutiliser** le lecteur HTTPS borné officiel `_abo_https_bytes` du banc R2-B et le parseur de métadonnées `_abo_spin_sample`, étendu à un filtre de séquences **choisi avant les scores** |
| Descripteurs, modèles et décisions | **Réutiliser sans modifier** le 64-octets M1-B, MobileNetV2 ImageNet (1 000 probabilités), `_image_learned`, `_negative_scores`, `conservative_threshold`, `_predict`, `_metrics` et les garde-fous |
| Nouveau uniquement | Lecture en flux de **deux shards de catalogue ABO**, sélection des objets `product_type=CHAIR`, contrôle des `item_id` distincts, constitution de groupes, diagnostics anonymisés et tests de non-fuite |
| Non créé / non activé | Aucun troisième modèle, nouvelle SQLite, nouvelle empreinte, pilote caméra, connexion robot, commande moteur, Qwen, identité d'animal, stockage de photographies |

**Licence :** [Amazon Berkeley Objects](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html), **CC BY 4.0**, attribution à **Amazon.com et Guillaumin et al.** ; le code externe du dataset n'a pas été copié. Le modèle ONNX est le [MobileNetV2-12 existant](../microduck_companion/visual_photo_mobilenet_demo.py), déjà épinglé par SHA-256 et exécuté sur CPU dans le runner hôte. Aucun fichier JPEG, poids, nom de produit ou `item_id` n'a été enregistré dans GitHub ni diffusé comme artefact.

## 2. Cohortes sélectionnées avant toute inférence

La première et la deuxième partition officielles `listings/metadata/listings_0.json.gz` et `listings_1.json.gz` donnent **136 entrées `CHAIR` possédant un spin_id**, après suppression de doublons de `item_id`. La lecture des métadonnées de vues sélectionne **les 30 premières séquences complètes** à six poses dans cet ensemble, dans l'ordre du CSV constructeur, sans observer les scores.

| Sous-groupe | Références inscrites | Produits inconnus | Vues interrogées |
| --- | ---: | ---: | ---: |
| Validation (seuil uniquement) | 8 `item_id` | 4 `item_id` | 32 connues + 16 inconnues |
| **Test gelé** | **12 `item_id`** | **6 `item_id`** | **48 connues + 24 inconnues** |

Au total : **30 `item_id` distincts, 30 `spin_id` distincts, 180 JPEG réels** (6 orientations par séquence). Les angles **0 et 36** sont les références, et **9, 18, 45, 54** les interrogations. Tous les inconnus sont **aussi des chaises** ; un détecteur de catégorie seul ne suffit donc pas. Aucune source, photographie ni séquence n'est réutilisée entre validation et test.

**Limites du groupe :** le libellé catalogue `CHAIR` est un **proxy de ressemblance sémantique**, pas un audit visuel prouvant que tous les produits se ressemblent fortement. Deux `item_id` distincts ne prouvent **pas** deux objets fabriqués physiquement distincts. Les vues de chaque `spin_id` sont **corrélées dans une séance de plateau tournant** : les 72 vues de requête sur le test ne sont donc **ni 72 objets** ni des reprises à des dates/distances/micros/éclairages/arrière-plans différents. Aucun animal, enfant ou objet domestique privé utilisé.

La sélection et le jeu de médias ont des empreintes SHA-256 reproductibles dans la CI :

- SHA-256 des `spin_id` sélectionnés (digest de roster, **pas une identité**): `67c7f9163694977a5f6ac562e8d9c3a457ffb351050ba45ed184772655018e4a`.
- SHA-256 combiné des 180 SHA-256 JPEG : `58ffdd59bea2fc6c64eb31467ac5597bc4cc34a2bd959e1b9e600a22fd9376e6`.

## 3. Mesures réelles de reconnaissance sur le jeu de test

**Seuil calculé sur validation uniquement, sans aucune adaptation ultérieure au test.**

| Indicateur | M1-B classique, 64 octets | MobileNetV2 ImageNet, 1 000 scores |
| --- | ---: | ---: |
| Seuil validation figé | **0,876838** | **0,999730** |
| Validation : reconnues parmi 32 vues connues | 9/32 (28,1 %) | 2/32 (6,3 %) |
| Validation : inconnues rejetées parmi 16 vues | 16/16 | 16/16 |
| **Test : correctes parmi 48 vues familières** | **10/48 (20,8 %)** | **4/48 (8,3 %)** |
| Test : produits connus ayant **au moins une vue correcte** | 8/12 | 1/12 |
| Test : refus d'une vue pourtant familière | **38/48** | **44/48** |
| Test : associations erronées entre les 12 produits inscrits | 0/48 | 0/48 |
| **Test : vues d'inconnus rejetées** | **22/24 (91,7 %)** | **24/24 (100 %)** |
| **Test : faux rapprochements d'inconnus avec une référence connue** | **2/24** (2 produits inconnus différents) | **0/24** |
| Test : abstentions explicitement « ambigu » (sous-ensemble des refus) | 3 | 11 |

Les deux faux rapprochements M1-B associent des objets **non inscrits mais du même type `CHAIR`** à des références connues. Le rapport `test_confusions` les restitue par **indices anonymes**, sans identifiants de catalogue ni données personnelles. La capacité à rejeter l'inconnu n'est pas une preuve de reconnaissance satisfaisante quand le rappel des familiers est si faible.

**Par angle, uniquement dans ce test :** M1-B retrouve 1/12 à l'angle 9, 4/12 à 18, 4/12 à 45 et 1/12 à 54 ; MobileNetV2 1/12 à chaque angle. Il est interdit de choisir ensuite les angles ou les images du test pour optimiser un modèle.

**Comparaison au [premier pilote ABO](r2b-independent-capture-evaluation-2026-10-26.md) :** MobileNetV2 y obtenait 15/16 vues connues sur un jeu réduit de 4 séquences inscrites et 2 inconnues ; sur 12 références connues et 6 inconnues **de même catégorie**, il n'en retrouve que 4/48. **Ne pas appeler cette baisse « dégradation quantifiée du modèle à difficulté égale » : les cohortes diffèrent et ne constituent pas une expérience jumelée.** Les probabilités de classes ImageNet ne prouvent pas une identité physique.

**Verdict R2-B+2 :** deux modèles réutilisés, **aucun suffisamment robuste sur ce banc** ; **ne pas porter ni sélectionner M1-B visuel/MobileNetV2 comme identité d'instance embarquée**. Garder `unknown` et les fausses associations visibles. Une comparaison plus avancée des seuils/coûts et des représentations est du ressort de **R2-C (non lancé)**, pas un réglage rétroactif de ce test.

## 4. Coûts et niveaux de preuve

**Sur le runner Linux GitHub Actions uniquement**, pour 180 inférences MobileNetV2 CPU :

- inférence ONNX **médiane 8,959 ms, p95 9,159 ms, maximum 11,549 ms**, **sans** le prétraitement, le téléchargement ou la recherche d'identité ;
- consommation CPU utilisateur **9,634 s** et pic RSS du processus **143 224 Kio** (environ 140 Mio), durée murale **56,452 s** **avec le réseau** ;
- les valeurs sont attachées à ce run hôte et ne préjugent en rien de la RAM libre, du CPU/NPU, de la température, des délais moteurs ou de l'autonomie RK3566.

**Tests :** 8 nouveaux tests purement synthétiques vérifient l'unicité des `item_id`, le rejet des doubles références, les quatre partitions, les requêtes inconnues, l'absence de fuites de noms, les contraintes de taille et les erreurs de métadonnées. Le job Python global a achevé **1001 tests dont 1 ignoré**, aucun échec. Les tests unitaires ne sont **pas** les images réelles ; les images réelles ont été évaluées dans le job CI dédié. [CI de l'ancien benchmark ABO R2-B #40380437829](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40380437829) et [CI audio R2-B+1 #40380437828](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40380437828) réussissent également, sans constituer une validation matérielle.

**Restant à prouver :** ressemblances visuelles établies par annotation, photographies différentes d'un même objet sous d'autres angles/éclairages, fond/échelle/occlusion, plusieurs appareils et sessions physiques ; robustesse des labels et du rejet sur des animaux mobiles et objets domestiques. **R2-B+2 est un banc réel de catégorie difficile, non une validation d'identification domestique.**

## 5. Décision, tâches hors périmètre et arrêt

- **Codé / testé sur fixtures :** filtre de métadonnées, cohorte déterministe, ouverture bornée des JPEG, réutilisation du modèle et métriques par source, erreurs anonymes.
- **Évalué sur données réelles :** 180 images originales de séquences ABO sur PC en CI, avec résultats négatifs documentés.
- **Simulé robot / validé robot :** non ; robot physique absent.
- **Réutiliser/adapter/créer** : aucun modèle nouveau ; seulement un filtre de catalogue ABO et une paramétrisation contrôlée de son lecteur existant. Aucun sous-module constructeur modifié.
- **Prochain lot : R2-C, uniquement après un nouveau « Go » de l'utilisateur.** Ne pas déclencher automatiquement R2-D, Qwen, navigation, biométrie ou mémoire physique.
