# Cat-A2b — Réelles captures basses : protocole local privé et banc de test

**26 octobre 2026. Statut : code de VALIDATION DES CAPTURES ET d'ÉVALUATION locale, PAS résultats de reconnaissance ni mesures sur Kwipi.** Le robot n'est pas disponible. Aucun corpus privé ni photographie à hauteur de capteur n'est fourni ou publié dans ce lot.

La [PR Cat-A2a](https://github.com/Jean-Philippe56520/Microduck/pull/67) a évalué un **petit corpus d'images publiques COCO dont la hauteur caméra est inconnue** : 24 images, 49 instances, 31 détections justes, 9 FP, 18 FN (IoU50), rappel 63,3 %, AP50 macro 0,486. Ces valeurs ne s'appliquent **pas** à une caméra située 25 cm du sol.

## 1. Audit « réutiliser / adapter / créer » et candidats externes

| Source | Vérifié | Décision |
| --- | --- | --- |
| OEM épinglé [microduck 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567), \`duck-detect/src/lib.rs\`, \`mediad\`, \`robotd\` | \`duck-detect\` est entraîné à **détecter d'autres Microducks**, et non les classes générales du foyer. \`mediad\` possède la caméra, \`robotd\` la commande motrice et la sécurité | **Réutiliser plus tard** leurs contrats sans pilote, ordonnanceur ou NPU concurrent |
| [Cat-A YOLOX](../microduck_companion/cata_yolox_categories.py) et [Cat-A2a](../microduck_companion/cata2_bbox_eval.py) | Modèle ONNX Megvii YOLOX Nano Apache-2.0, SHA-256 vérifié, seuil fixe 0,25, prétraitement, \`decode_boxes()\`, appariement IoU50/AP50 | **Réutiliser tel quel**, sans nouveau détecteur, modèle entraîné, méthode de score ni réglage sur test |
| [F3-A métadonnées](../microduck_companion/visual_dataset.py) | Protocole d'IDs opaques, SHA, split de groupes, mais **sans véritables boîtes, hauteur de caméra ni lecture d'image** | **Adapter les principes de validité** ; nouveau schéma local uniquement parce que F3-A/COCO ne décrivent pas ces prises |
| [OpenLORIS-Scene](https://lifelong-robotic-vision.github.io/dataset/scene.html) | Son protocole annonce des caméras montées **vers 1 m**, incompatible avec la cible basse de Kwipi | **Ne pas présenter** comme vues à 25 cm |
| [OCID, TU Wien](https://www.acin.tuwien.ac.at/vision-for-robotics/software-tools/object-clutter-indoor-dataset/) | **Deux hauteurs de caméra**, vues basses/hautes et annotations d'instances de scènes encombrées ; le détail cité ne prouve **ni hauteur optique 100–300 mm pour les images choisies, ni couverture des cinq catégories** | **Candidat de recherche**, pas une preuve Cat-A2b en l'absence de métadonnées et de licence des images validées |
| Registre communautaire C3 : Smartulf / GC-RENCAO, [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) | Références de vision/cerveau non intégrées. La PR OEM #381 n'est pas fusionnée | **Aucun import**, aucune duplication de boucle de comportement |

**Création ciblée :** [\`cata2b_private_low.py\`](../microduck_companion/cata2b_private_low.py) lit seulement des **JPEG locaux privés** (capture et preuve de mesure de hauteur), refuse les métadonnées non autorisées, confirme les SHA/dimensions, contrôle les groupes et utilise **la même** inférence Cat-A2a uniquement sur la partie TEST. Une nouvelle table SQLite, un nouveau LLM, une capture audio et la navigation n'ont aucune raison d'être.

## 2. Ce qu'est une prise réellement basse

- Mesurer la hauteur du **centre optique de la caméra**, verticale depuis le **sol**, à chaque séance. **La taille totale du robot (~25 cm) n'est pas la hauteur de son capteur.** En attendant de connaître sa vraie hauteur et son inclinaison, le protocole accepte **100–300 mm** comme plage de prises volontairement basses, sans présumer que tout cet intervalle correspond au futur robot.
- Documenter **localement** la mesure par une image de règle/centre optique séparée de la scène. Son SHA-256 et les images sont vérifiés, **mais l'existence du fichier ne prouve ni la hauteur déclarée ni une calibration indépendante**. Ces preuves privées ne sortent jamais du PC.
- Photographier une vraie scène sous cet angle. **Ne pas utiliser un recadrage de photo prise debout** : une image basse doit être une prise distincte, avec perspective réelle.
- Varier distance, orientation, obscurité/lumière, encombrement, sols et mobilier, puis classes \`person\`, \`cat\`, \`dog\`, \`chair\`, \`sports_ball\` ; inclure explicitement des images sans cible. Les animaux sont observés sans les poursuivre ; pas de prise de vue de mineur ni personne identifiable sans consentement rigoureux. Les instances personnelles ne sont jamais identifiées.
- Pour chaque image, tracer les **boîtes rectangulaires en pixels originaux** et la visibilité de chaque objet : \`full\` ou \`partial\`. Si aucune cible n'est visible, une liste \`boxes: []\` doit être explicitement contre-annotée. Marquer \`all_targets_reviewed=true\` et \`privacy_and_consent_reviewed=true\` seulement après vérification par l'opérateur : **le programme ne peut pas certifier cette vérification humaine.**
- Affecter tous les angles d'une même scène au **même groupe opaque** ; séparer **séances ET lieux** entre train, validation et test. Empêcher qu'un objet filmé plusieurs fois soit compté comme échantillon indépendant. L'algorithme rejette les duplications d'octets et les groupes qui traversent les splits. Un simple identifiant d'angle ne prouve pas de nouveaux objets.

## 3. Schéma de données LOCAL (pas de photos dans GitHub)

Arborescence conseillée, déjà couverte par le \`.gitignore\` du projet :

\`\`\`text
.local_visual_data/cat-a2b/
    manifest.json
    images/
        s-0000000000000001.jpg
        s-0000000000000002.jpg
        ...
    evidence/
        e-0000000000000001.jpg
        ...
\`\`\`

Le manifeste JSON \`schema_version:1\`, \`source:"operator_private_capture"\` contient :

\`\`\`json
{
  "schema_version": 1,
  "source": "operator_private_capture",
  "sessions": [
    {
      "session_id": "g-0000000000000001",
      "site_group_id": "g-0000000000000011",
      "camera_height_mm": 200,
      "ruler_evidence_file": "e-0000000000000001.jpg",
      "ruler_evidence_sha256": "SHA256_HEX_REEL_DU_FICHIER",
      "measurement_method": "ruler_at_optical_center"
    }
  ],
  "samples": [
    {
      "sample_id": "s-0000000000000001",
      "session_id": "g-0000000000000001",
      "scene_group_id": "g-0000000000000021",
      "split": "test",
      "image_sha256": "SHA256_HEX_REEL_DU_JPEG",
      "image_width": 640,
      "image_height": 480,
      "boxes": [
        {"category": "chair", "xyxy": [30, 40, 260, 420], "visibility": "partial"}
      ],
      "all_targets_reviewed": true,
      "privacy_and_consent_reviewed": true
    }
  ]
}
\`\`\`

**Cet extrait est illustratif et n'est pas un jeu de test utilisable** : remplacer les hashes par les SHA-256 des fichiers réels, conserver des IDs non identifiants, fournir au moins **1 image train, 1 validation, 2 test**, avec au moins une cible et une image sans cible dans TEST. **Ne jamais remplir GitHub avec ces données.** Un jeu aussi petit est techniquement accepté pour vérifier le protocole, mais n'est pas une preuve de performance. Pour un véritable benchmark, augmenter la diversité et le nombre de séances, inclure plusieurs exemples de chaque catégorie et des scènes négatives.

Le programme refuse les champs \`person_name\`, \`face_id\`, \`location\`, URL, audio, chemins, transcriptions, catégories \`shoe/hand/foot\` non présentes dans YOLOX, images non JPEG, EXIF rotation, horodatages non valides si ajoutés comme champs inconnus, JPEG/boîtes hors bornes, hash incohérent, symlink et regroupements douteux. Les images restent en mémoire uniquement le temps de la lecture/évaluation ; les sorties ne contiennent ni nom de fichier privé, ni sample_id, ni scène, ni identité.

## 4. Commandes locales

À lancer sur le PC après installation de \`Pillow\`, \`numpy\` et \`onnxruntime\` avec les versions déjà employées par Cat-A ; dans un dossier local privé **ignoré de Git** :

\`\`\`bash
python -m microduck_companion.cata2b_private_low \
  --manifest .local_visual_data/cat-a2b/manifest.json \
  --validate-only \
  --approved-private-local-media
\`\`\`

Ensuite, lorsque les photographies et les annotations réelles sont contrôlées, lancer **le même modèle ONNX approuvé de Cat-A** (3,49 Mo, SHA-256 vérifié), depuis un fichier local hors Git :

\`\`\`bash
python -m microduck_companion.cata2b_private_low \
  --manifest .local_visual_data/cat-a2b/manifest.json \
  --model-path .local_visual_data/models/yolox_nano.onnx \
  --approved-private-local-media
\`\`\`

- Première commande : vérifie le fichier de mesure et chaque image, les dimensions, les droits déclarés et l'absence de fuite de groupes. **Ne produit AUCUN taux de reconnaissance.**
- Deuxième commande : effectue la vraie inférence **sur TEST seulement**, puis utilise **l'appariement IoU50/AP50 existant**. Les sous-groupes \`has_partial\`/\`full_only\`/\`no_target\` décrivent les **images**, pas la détection individuelle de chaque partie. Plafonds : 128 images au total, **25 en test** ; élargir le protocole par lots indépendants après audit statistique plutôt qu'un résultat trop fin.
- **Aucun entraînement, aucune sélection de seuil sur TEST et aucune comparaison de modèles biaisée.** Les images de train/validation sont contrôlées mais jamais utilisées ici pour entraîner. Les mesures RSS/latence seraient celles du **PC**.

## 5. Confidentialité, qualité et fin du chantier

Le dépôt ne reçoit ni photo, ni voix, ni image d'enfant, ni emplacement GPS, ni identité de personne/animal, ni secrets, ni poids. Seuls sont committés le code, les tests avec **JPEG générés sans personnes** et la documentation. Tous les tests GitHub Actions de cette PR se déroulent sur des **fixtures**, **sans véritable corpus bas** : succès CI ≠ taux d'erreur de vision réel.

**Cat-A2b peut être considéré « protocole codé » seulement après tests CI verts. Pour dire « réellement évalué à hauteur de Kwipi » :** il faudra recevoir/produire un jeu indépendant de vraies prises basses, confirmer manuellement les mesures de hauteur et droits, tester les cinq catégories avec suffisamment d'images et montrer une couverture d'inconnus/occlusions. Sur le **robot réel**, il faudra en plus \`scripts/resource-audit.sh\`, l'interface \`mediad\` officielle et la sûreté \`robotd\` : **aucun portage/validation ici**.

**Étapes futures** : (1) données sous angles bas indépendantes, (2) vraie localisation, seuil de rejet et confusion par catégorie, (3) benchmark modèle raisonnable ou abandon de la catégorie défaillante, (4) étude RKNN/ressources séparée, (5) seulement alors observation active contrôlée. Ne pas revenir à une identité individuelle non fiable.
