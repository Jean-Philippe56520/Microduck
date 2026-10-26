# Cat-A — Première évaluation de catégories pour Kwipi (PC uniquement)

**26 octobre 2026 — Cat-A, lot 1 : modèle externe réutilisé, résultats réels négatifs sur images partielles, sans validation robot.**

**Code :** [cata_yolox_categories.py](../microduck_companion/cata_yolox_categories.py) ; **tests de protocole :** [test_cata_yolox_categories.py](../tests/test_cata_yolox_categories.py) ; [CI initiale de validation et benchmark sur vraies images #40387879069](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40387879069). Les étapes suivantes seront conditionnées aux résultats et ne sont pas lancées.

## 1. Objet et règle de réutilisation

Décision de priorité : [R2-C et Cat-A](r2c-category-first-active-perception-2026-10-26.md), [plan d'action](plan-action.md), [protocole de réutilisation](development-reuse-protocol.md), [registre de références](community-reference-registry-2026-10-26.md).

**Question :** un détecteur **de catégories** réellement entraîné (et non une empreinte d'**identité physique**) sait-il distinguer « chat », « chien », « chaise », « autre/inconnu », et que reste-t-il quand seule la partie inférieure de l'image est visible ?

| Fonction | Décision | Pourquoi |
| --- | --- | --- |
| 20 photos réelles de chats/chiens/autres | **Réutiliser** le [catalogue public CC0 F3-B](../microduck_companion/visual_photo_catalog.py) et son validateur de photographes disjoints | Pas de nouvelles photos privées, pas de nouveaux labels improvisés. Le test de 6 images (2 chats, 2 chiens, 2 autres) est inchangé |
| 12 images réelles de chaises | **Réutiliser** les métadonnées/listings \`CHAIR\`, la sélection de spins et les lecteurs bornés issus de [R2-B+2](r2b2-confusable-objects-2026-10-26.md) | Douze \`item_id\` catalogue différents, une seule pose chacun ; **pas** de boîte annotée, ni preuve que les 12 exemplaires fabriqués sont différents |
| Modèle de détection | **Réutiliser un poids existant, sans l'intégrer au robot** : Megvii [YOLOX Nano](https://github.com/Megvii-BaseDetection/YOLOX), Apache-2.0 | 3,49 Mo, ONNX COCO 80 classes, déjà conçu pour des catégories, contrairement au banc d'empreintes d'identité |
| Extraction/décision | **Créer seulement le banc hôte de comparaison** | Lecture du modèle SHA-256, redimensionnement YOLOX, prédiction 416 px, seuil fixe, étiquettes de présence au niveau image, erreur/rejet et coûts PC |
| Moteurs, vision embarquée, mémoire | **Ne rien dupliquer** | \`robotd\` seul détient la sécurité, \`mediad\` la caméra ; une seule \`ExperienceMemory\` SQLite. Rien n'est connecté à ce banc |

**Modèle :** [Hugging Face, SkillSafe YOLOX-Nano](https://huggingface.co/skillsafe-ai/yolox-nano) préentraîné sur **COCO**, upstream Megvii YOLOX \`0.1.1rc0\`, copyright 2021–2022 Megvii, licence **Apache-2.0**. SHA-256 vérifié avant chargement : \`c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d\`. Modèle ONNX \`images[1,3,416,416]\` → \`output[1,3549,85]\`, étiquettes COCO. Aucun poids ni JPEG committé. Il n'est **pas** présumé compatible avec le RKNN/RK3566.

**Photographies :** 20 fichiers Wikimedia Commons dont les fiches déclaraient CC0 1.0 lors de la revue F3-B, avec auteurs différents entre jeux ; licence et attribution restent déclaratives, pas garanties cryptographiquement. Les 12 autres vues proviennent d'[Amazon Berkeley Objects](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html), **CC BY 4.0, Amazon.com / Guillaumin et al.** Les 32 vrais JPEG sont téléchargés en mémoire pendant la CI puis oubliés, sans archive ni photos de Malo/Kitty/Nessquick.

**Important :** la catégorie \`shoe\` (chaussure), ainsi que \`hand\`, \`foot\`, \`forearm\`, \`paw\` et \`human_head\`, **ne figure pas dans les 80 classes COCO standard**. \`person\` et \`sports_ball\` sont présentes dans le vocabulaire, mais **n'ont pas d'évaluation annotée dans ce pilote**. Le détecteur OEM des autres Microducks n'est pas implicitement un détecteur de chiens/chats/humains.

## 2. Protocole et séparation des mesures

La comparaison garde le découpage existant du jeu CC0 : **8 photos \`train\` historiques, 6 \`validation\`, 6 \`test\` (2 chats, 2 chiens, 2 inconnus)**. Aucune image n'est utilisée pour entraîner/affiner YOLOX, et **le seuil 0,25 est fixé a priori**, avant validation et test. Ce test n'utilise donc pas la validation pour choisir un seuil optimal.

Pour chaque photographie, le modèle voit :
1. l'image complète ;
2. **la moitié inférieure recadrée de la même image** (occultation contrôlée).

Ce deuxième cas **n'est pas une nouvelle photo indépendante ni une prise à 25 cm du sol**. La détection produit de vraies boîtes, mais ce banc évalue uniquement **une étiquette d'image**, choisie comme le meilleur score parmi \`person\`, \`cat\`, \`dog\`, \`sports_ball\`, \`chair\` ; si aucun score ne dépasse 0,25, réponse \`unknown\`. Il n'y a pas d'annotations de localisation permettant un vrai calcul mAP, IoU ou erreur de boîte.

Les **12 photos ABO \`CHAIR\`** sont un **test auxiliaire de changement de domaine**, avec étiquette catalogue et une orientation par produit. Elles sont rapportées à part et n'augmentent pas artificiellement le dénominateur du holdout CC0.

## 3. Résultats mesurés sur de vrais JPEG — première CI

| Ensemble | Image complète | Moitié inférieure artificielle | Type de preuve |
| --- | ---: | ---: | --- |
| CC0 validation (6 images) | **5/6 (83,3 %)** | **4/6 (66,7 %)** | Diagnostic, 2 chats + 2 chiens + 2 autres |
| **CC0 test (6 images)** | **4/6 (66,7 %)** | **3/6 (50 %)** | Test tenu à part, 2 chats + 2 chiens + 2 autres |
| **ABO chaises (12 images)** | **8/12 (66,7 %)** | **0/12 (0 %)** | Catégorie du catalogue, sans boîte annotée |

**Erreurs du test CC0 sur images entières :** un chat pris pour un chien et un chien pris pour un chat ; les deux photos \`unknown\` ont bien été rejetées (**2/2**). Les captures recadrées ne réussissent que **3/6** : un chat pris pour chien, un chien pris pour chat, et une photo inconnue prise pour une personne (fausse association). Les autres images recadrées réussissent leurs catégories. Côté chaises, les **12/12** moitiés inférieures sont rejetées comme \`unknown\`, malgré la présence de chaises connues au niveau du catalogue.

Ce comportement **n'est pas une validation de sécurité ou de fiabilité** : le modèle peut refuser un objet connu et se tromper de catégorie. Les jeux sont très petits. La réussite sur \`unknown\` en pleine image 2/2 n'implique pas un rejet fiable de tous les inconnus. Une fausse détection de \`person\` sur une photo non personnelle montre pourquoi aucune inférence de présence humaine ou décision motrice ne doit être autorisée sans corroboration.

**Coûts hôte Linux GitHub Actions (32 JPEG originaux, 64 inférences avec recadrages) :** inférence ONNX CPU **médiane 10,700 ms** ; CPU utilisateur processus entier **2,703 s** ; RSS processus entier **138 324 Kio** (env. 135 Mio) ; durée murale **10,689 s avec téléchargements**. Aucun chiffre ne décrit RAM libre, cadence caméra/moteur, consommation électrique, température ou performance NPU de Kwipi.

**Statut des preuves :** code testé sur CI et **images réelles publiques**, avec **recadrages artificiels** ; pas de prises authentiquement basses, de suivi, de continuité d'objet, de personnes/balles étiquetées en holdout, de vraies parties du corps, de médialogic OEM, de SQLite mémoire ou de robot physique testé.

## 4. Décisions et prochaine porte Cat-A

**Décision de ce pilote : \`RETESTER\` la reconnaissance de catégories sur un jeu indépendant plus large.** Le modèle montre un potentiel limité pour catégoriser un objet entier, mais le recadrage des chaises est un échec complet ; **ne pas le promouvoir sur le robot**.

Prochain lot éventuel (sur nouveau « Go ») :
- constituer un **vrai corpus de prises basses à ~25 cm**, avec différents angles/éclairages, et annotations de boîtes, y compris \`person\`, \`cat\`, \`dog\`, \`chair\`, \`sports_ball\` ; contrôles de licences, confidentialité et source ;
- distinguer soigneusement les vrais objets invisibles des objets partiellement visibles et des objets inconnus, puis mesurer erreurs de classification, faux positifs, refus, précision localisée/IoU/mAP, coût du pipeline complet ;
- comparer ou adapter des détecteurs existants appropriés pour \`shoe\` et parties du corps, sans déduire une identité d'un membre isolé ni importer automatiquement un nouveau modèle ;
- garder \`unknown\`, ne permettre que l'**intention non motrice** \`inspect\` puis une nouvelle observation sous contrôle de \`robotd\` et après simulation/hardware audit ultérieurs ;
- Qwen reste **facultatif**, sous consentement réseau/quota, les réponses n'écrivent jamais une observation certifiée dans \`ExperienceMemory\`.

**Ne pas lancer Cat-B (recherche de continuité réelle), Cat-C (mémoire de catégories) ni Cat-D (Qwen) à partir de ce seul pilote.** Maintenir \`Hé Kwipi !\` comme **activation prévue, non codée ni validée** et jamais comme autorisation motrice.
