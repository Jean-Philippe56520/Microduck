# F3-B — Première ligne de base sur des photographies réelles sous CC0

**25 octobre 2026 — [PR #33](https://github.com/Jean-Philippe56520/Microduck/pull/33), branche testée, en revue.**

## 1. Résumé des preuves : deux méthodes, même petit échantillon

Pour la **première fois dans F3**, des JPEG **réels** de chats et de chiens ont été téléchargés depuis les pages publiques Wikimedia Commons et décodés en mémoire sur **GitHub Actions Ubuntu, Python 3.11 et CPU de l'hôte**. Le catalogue couvre **20 photographies**, 20 auteurs crédités distincts : 8 entraînement, 6 validation, 6 test. Les deux images de la classe `unknown` dans chaque ensemble de validation/test sont des oiseaux ou fleurs. Les images ne sont **ni copiées dans GitHub, ni stockées en SQLite**, ni mises en artefact ; seul le code et les mesures sont versionnés.

L'expérimentation compare :
- **Référence minimale RVB/kNN 3 voisins** : 8 photos d'entraînement, des caractéristiques artisanales RGB 16×16, seuil choisi sur validation ; presque tout est refusé dans le test, et le modèle n'est pas utile pour reconnaître un animal.
- **MobileNetV2 ONNX Model Zoo, Apache-2.0, ImageNet préentraîné** : poids **13 964 571 octets** obtenus hors dépôt à partir d'une source publique, empreinte SHA-256 attendue `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`, testés avec `onnxruntime` CPU uniquement. **Aucun réentraînement** sur nos huit photos : le jeu `train` reste réservé et non utilisé par ce modèle. Les classes ImageNet sont regroupées en `dog` (indices 151–268), `cat` (281–285), et `unknown` sous un seuil fixé **uniquement sur validation**.

### Résultats réels mesurés, petits effectifs

[Exécution du banc visuel réel (CI #40242876466)](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40242876466) :

| Mesure sur 6 photos de test non utilisées pour les seuils | kNN RVB artisanal | MobileNetV2 ONNX CPU |
| --- | ---: | ---: |
| Prédictions correctes / test | **2/6** (33,3 %) | **5/6** (83,3 %) |
| Chats reconnus | **0/2** | **2/2** |
| Chiens reconnus | **0/2** | **1/2**, 1 refus `unknown` |
| Cas hors domaine correctement refusés | **2/2** | **2/2** |
| Faux animaux annoncés sur les deux photos hors domaine | **0** | **0** |
| Couverture (réponse autre que `unknown`) | **0/6** | **3/6** |
| Latence médiane d'inférence individuelle | non isolée | **6,985 ms** environ, sur CPU CI |
| Latence d'inférence maximum parmi 20 images | non isolée | **7,209 ms** environ, sur CPU CI |

Pour le modèle ONNX, seuil de masse de classes ImageNet `cat+dog` **0,7059011**, sélectionné sur 6 photos de validation (4 connues + 2 hors domaine). La validation affichait 6/6 réponses correctes ; **cela ne vaut pas performance généralisable**. Le test comprenait **deux chats corrects, un chien correct, un chien correctement traité comme incertain selon le seuil mais classé faux vis-à-vis de son étiquette, et deux non-animaux annoncés `unknown`**.

**Très faibles effectifs : 6 photos de validation et 6 de test, avec seulement deux photos hors domaine chacune ; ces pourcentages n'estiment pas de manière fiable la précision, le rappel, ni le taux de faux positifs dans une maison.** Les photographes sont séparés entre partitions, mais l'absence de chevauchement avec les **données massives préalables d'ImageNet n'a pas été auditée**. Il ne faut pas publier ce 83,3 % comme une précision validée du Microduck.

## 2. Données et droits : catalogue public revu, limites des déclarations

Les pages suivantes ont été repérées dans Wikimedia Commons comme **« Own work » + CC0 1.0** par les détenteurs déclarés, et les catégories ont été choisies selon les descriptions publiques. **Il n'est pas démontré que chaque contributeur possède réellement l'intégralité des droits** ni qu'une deuxième personne a vérifié visuellement toutes les étiquettes. Le code impose un catalogue fermé, des auteurs distincts par partition, un contrôle des empreintes SHA-256 des octets réellement lus, et réutilise le manifeste strict F3-A en mémoire. Les droits et annotations sont **déclaratifs**, pas une preuve juridique ni biométrique.

| Page publique Wikimedia Commons | Étiquette | Partition | Auteur indiqué | Licence indiquée |
| --- | --- | --- | --- | --- |
| [Picture_of_cat.jpg](https://commons.wikimedia.org/wiki/File:Picture_of_cat.jpg) | `cat` | `train` | Theeyes 07 | CC0 1.0 déclaré sur la page |
| [Kitten_on_the_tree.jpg](https://commons.wikimedia.org/wiki/File:Kitten_on_the_tree.jpg) | `cat` | `train` | Jelesije I | CC0 1.0 déclaré sur la page |
| [A_black_and_white_kitten.jpg](https://commons.wikimedia.org/wiki/File:A_black_and_white_kitten.jpg) | `cat` | `train` | Jeromi Mikhael | CC0 1.0 déclaré sur la page |
| [Cat_is_standing.jpg](https://commons.wikimedia.org/wiki/File:Cat_is_standing.jpg) | `cat` | `train` | Zhmila | CC0 1.0 déclaré sur la page |
| [Photo_of_a_dog.jpg](https://commons.wikimedia.org/wiki/File:Photo_of_a_dog.jpg) | `dog` | `train` | ContaDeletada2906 | CC0 1.0 déclaré sur la page |
| [Pet_animal_photography.jpg](https://commons.wikimedia.org/wiki/File:Pet_animal_photography.jpg) | `dog` | `train` | Obusaranya sekar | CC0 1.0 déclaré sur la page |
| [My_little_dog.jpg](https://commons.wikimedia.org/wiki/File:My_little_dog.jpg) | `dog` | `train` | Sowmiyamuruganmba | CC0 1.0 déclaré sur la page |
| [Dog_IMG_1057.jpg](https://commons.wikimedia.org/wiki/File:Dog_IMG_1057.jpg) | `dog` | `train` | JasonAstros123 | CC0 1.0 déclaré sur la page |
| [Cat_looking.jpg](https://commons.wikimedia.org/wiki/File:Cat_looking.jpg) | `cat` | `validation` | Ani Vincent | CC0 1.0 déclaré sur la page |
| [Cute_cat_2024.jpg](https://commons.wikimedia.org/wiki/File:Cute_cat_2024.jpg) | `cat` | `validation` | Ahmadjonova Azizaxon | CC0 1.0 déclaré sur la page |
| [Dog_in_forest.jpg](https://commons.wikimedia.org/wiki/File:Dog_in_forest.jpg) | `dog` | `validation` | Ssroldan | CC0 1.0 déclaré sur la page |
| [My_cute_dog.jpg](https://commons.wikimedia.org/wiki/File:My_cute_dog.jpg) | `dog` | `validation` | Doglover41 | CC0 1.0 déclaré sur la page |
| [Flower_photo_normal.jpg](https://commons.wikimedia.org/wiki/File:Flower_photo_normal.jpg) | `unknown` | `validation` | LorelMan | CC0 1.0 déclaré sur la page |
| [Bird_image.jpg](https://commons.wikimedia.org/wiki/File:Bird_image.jpg) | `unknown` | `validation` | Darakshanehaluddin | CC0 1.0 déclaré sur la page |
| [Kitten_Looking.jpg](https://commons.wikimedia.org/wiki/File:Kitten_Looking.jpg) | `cat` | `test` | Saral Shots | CC0 1.0 déclaré sur la page |
| [Kitts01e01.jpg](https://commons.wikimedia.org/wiki/File:Kitts01e01.jpg) | `cat` | `test` | Coolbrizzy | CC0 1.0 déclaré sur la page |
| [Sleeping_Brown_Dog.jpg](https://commons.wikimedia.org/wiki/File:Sleeping_Brown_Dog.jpg) | `dog` | `test` | Nikkaella | CC0 1.0 déclaré sur la page |
| [Cute_dog_sitting_in_forest.jpg](https://commons.wikimedia.org/wiki/File:Cute_dog_sitting_in_forest.jpg) | `dog` | `test` | Hamoma30 | CC0 1.0 déclaré sur la page |
| [Small_bird.jpg](https://commons.wikimedia.org/wiki/File:Small_bird.jpg) | `unknown` | `test` | Kyreb | CC0 1.0 déclaré sur la page |
| [Flower_vv6.jpg](https://commons.wikimedia.org/wiki/File:Flower_vv6.jpg) | `unknown` | `test` | Dinkum | CC0 1.0 déclaré sur la page |

Le chargeur `fetch_thumbnail` suit seulement les redirections HTTP HTTPS vers les hôtes Wikimedia **explicitement autorisés** (`upload.wikimedia.org`, `thumb.wikimedia.org`, `commons.wikimedia.org`) et refuse les autres domaines, les contenus non-JPEG, les trames anormales et les données de plus de **1,2 Mo**. Le téléchargement initial a révélé que Wikimedia redirige certains fichiers vers `thumb.wikimedia.org` : la vérification a été étendue **à ce domaine officiel exact**, sans ouverture générique à Internet. Indisponibilité/réponse inattendue : le banc **échoue**, sans annoncer un score partiel.

Les informations de provenance (URL du fichier, auteur, classe) sont publiques ; **aucune photo ni voix privée, nom d'enfant, identité du foyer, transcript ou biométrie personnelle** ne figure dans le dépôt. Le fichier `docs/f3a-visual-dataset-protocol-2026-10-25.md` conserve le contrat des identifiants opaques et les limites de détection des quasi-doublons. Une empreinte SHA-256 des JPEG reçus est contrôlée en cours d'exécution pour les doublons exacts, **mais pas épinglée dans le dépôt**, donc une modification de vignettes chez l'hébergeur peut nuire à la reproductibilité exacte des métriques.

## 3. Ce que fait le code et ce qu'il ne fait pas

- `microduck_companion/visual_photo_catalog.py` : vingt pages sources CC0 avec auteur, classe, partition.
- `visual_photo_baseline.py` et `visual_photo_baseline_demo.py` : contrôle d'accès, extraction de caractéristiques RVB, kNN à trois voisins, arbitrage connu/`unknown`, mesures sur validation/test et interaction explicite avec le contrat F3-A.
- `visual_photo_mobilenet_demo.py` : lecture de poids ONNX **préentraînés (non livrés dans Git)**, empreinte SHA attendue, prétraitement RGB 224×224 normalisé selon ImageNet, inférence `CPUExecutionProvider`, regroupement des classes chat/chien, seuil validé hors test, rapport de confusion.
- `tests/test_visual_photo_baseline.py` et `tests/test_visual_photo_mobilenet.py` : tests hors réseau pour protection des domaines, types, fichiers, classes, métriques et seuils ; aucune photographie n'est nécessaire aux tests de non-régression.
- `.github/workflows/f3b-real-photos.yml` : workflow **séparé** des tests Python généraux, sur la PR F3-B ou à la demande, installation explicite Pillow/NumPy/ONNX Runtime, téléchargement en RAM des photos CC0, récupération des poids ONNX uniquement dans un fichier éphémère de CI, contrôle SHA-256 préalable, publication **uniquement des résultats chiffrés** dans les logs.

**Non fait :** classification de `person`, `ball`, `toy` ou `microduck`, boîtes englobantes, masque animal, suivi temporel/individuel, identification de chat/chien familier, détection d'obstacles, commande `mediad`/`robotd`, export RKNN INT8, entraînement sur la carte, pilotage moteur, mesure embarquée CPU/RSS/NPU/température et répétitions sur gros jeu indépendant.

## 4. Licence du modèle et prudence sur l'embarqué

La carte de modèle ONNX Model Zoo MobileNetV2 est déclarée **Apache 2.0** ; ses poids sont téléchargés depuis [onnxmodelzoo/mobilenetv2-12](https://huggingface.co/onnxmodelzoo/mobilenetv2-12) et ne sont **pas publiés dans notre dépôt**. La licence s'applique à la distribution et au code/poids, pas comme garantie que les photos ImageNet originales sont libres pour tous usages. Le pipeline n'inclut **aucune API payante**, ne suppose aucune accélération NPU/GPU et fonctionne **hors réseau après préparation des poids et photos**, sur PC. Les chiffres **6,985 ms** et **13,96 Mo** ne constituent **ni une mesure de la RAM réelle à l'inférence ni une preuve que le modèle tournera à cette cadence, ou même pourra être intégré sans optimisation sur le RK3566**. Le détecteur constructeur RKNN de Microduck est un autre modèle et ne donne pas automatiquement la reconnaissance des animaux.

## 5. Reproduire les contrôles

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
# Sur une machine Linux/Unix connectée à Internet, après revue des droits :
python -m pip install Pillow==11.3.0 numpy==1.26.4 onnxruntime==1.21.0
python -m microduck_companion.visual_photo_baseline_demo
# Télécharger le MobileNetV2 ONNX original vers un emplacement local,
# vérifier impérativement son SHA-256 puis lancer :
python -m microduck_companion.visual_photo_mobilenet_demo --model /chemin/local/mobilenetv2-12.onnx
```

L'exécution du premier banc kNN a échoué **sur le plan de la reconnaissance**, mais ses tests et mesures ont identifié honnêtement cette faiblesse. La comparaison ONNX constitue le premier signal positif sur **quelques vrais pixels**, pas une validation d'usage. **La PR #33 reste à revoir et fusionner** après preuve de sa dernière CI.

## 6. Suite après revue

F3-B est un **jalon de laboratoire**. Pour préparer une vraie capacité Microduck, des tests sur **beaucoup plus d'images hors entraînement**, la gestion d'autres animaux/objets, des annotations de boîtes/vidéo et des comparaisons de faux positifs sous différentes lumières sont indispensables. F3-C (intégration prudente de `mediad` et sons) peut être traitée dans une PR distincte après validation F3-B, mais aucun résultat de ce banc ne permet d'autoriser un déplacement autonome. Le portage CPU/RKNN, les limites de ressources et l'inférence sur carte restent soumis à la phase F6/F7 et à `scripts/resource-audit.sh`.
