# Cat-A2a — Localization de catégories sur COCO 2017 : banc hôte indépendant

**26 octobre 2026 — première tranche du chantier Cat-A2**, suite à [Cat-A](cata-category-detection-pilot-2026-10-26.md), sans portage sur Kwipi. **La hauteur physique de caméra des photos COCO est inconnue** : ce banc n'évalue PAS le scénario d'une caméra à ~25 cm. Cat-A2b (véritables vues basses vérifiables) reste une porte distincte.

## Résultats réels du premier lot (CI hôte du 26/10/2026)

[GitHub Actions #40400991178 — Cat-A2a sur le SHA de modèle et d'annotations contrôlés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40400991178) : **24 vrais JPEG COCO VAL** à licence *déclarée* CC BY 2.0, **49 instances de cinq classes annotées**, **40 propositions**. À **IoU≥0,50**, **31 vrais positifs**, **9 faux positifs** et **18 faux négatifs** ; **précision 0,775**, **rappel 0,632653**, **AP50 moyenne macro 0,485555** (moyenne sur les cinq classes présentes, AP interpolée à 101 points sur cette petite cohorte seulement).

| Catégorie | Instances annotées | Vrais positifs (IoU50) | Faux négatifs | Faux positifs | AP50 101 points |
| --- | ---: | ---: | ---: | ---: | ---: |
| humain (`person`) | 29 | 23 | 6 | 3 | 0,787510 |
| chat | 4 | 4 | 0 | 0 | 1,000000 |
| chien | 5 | 2 | 3 | 0 | 0,405941 |
| chaise | 7 | 1 | 6 | 4 | 0,148515 |
| balle (`sports_ball`) | 4 | 1 | 3 | 2 | 0,085809 |
| **Total** | **49** | **31** | **18** | **9** | **0,485555 macro** |

Sur **4 images sans aucune des cinq classes cibles**, le système ne produit **aucune fausse détection**. Cet échantillon est trop faible pour conclure que le rejet des inconnus est robuste. Les images sont sélectionnées par ID et SHA avant toute inférence ; certains clichés positifs contiennent simultanément plusieurs catégories.

**Ressources CPU du runner GitHub uniquement :** inférence ONNX médiane **23,037 ms**, p95 **24,504 ms** sur 24 inférences ; pic RSS du **processus Python entier** **174 068 Kio** (~170 Mio), durée totale **3,097 s** avec chargement local et téléchargement de JPEG (hors téléchargement initial des poids et annotations). **Aucune conversion en FPS robot, consommation NPU, énergie, RAM libre ou thermie.** Le précédent résultat Cat-A est mesuré sur d'autres photos et un autre protocole : ces valeurs ne sont pas une amélioration mesurée.

**Décision : RETESTER, pas de déploiement.** Les balles et les chaises sont mal localisées sur ce faible échantillon. Les chats 4/4 sont un résultat de **quatre images**, pas une garantie. **Zéro photographie avec hauteur de caméra certifiée ~25 cm : Cat-A2b reste non réalisé.**

## 1. Comparaison obligatoire « réutiliser / adapter / créer »

| Composant / source | Observé à la révision vérifiée | Décision |
| --- | --- | --- |
| OEM [microduck épinglé 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) : \`duck-detect\`, \`mediad\`, \`robotd\` | \`duck-detect/src/rknn.rs\`/ONNX pour **Microducks** ; \`mediad\` caméra, \`robotd\` sécurité et moteurs. Pas de détecteur général chats/chiens/chaussures validé sur notre robot | **Réutiliser OEM ultérieurement** ; aucun pilote ou NPU concurrent |
| Companion [Cat-A](../microduck_companion/cata_yolox_categories.py), [Cat-A CI](../.github/workflows/cat-a-yolox-categories.yml) | YOLOX Nano 416 px, ONNX COCO 80 classes (Megvii Apache-2.0), modèle 3,49 Mo SHA \`c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d\`, seuil **0,25 fixé a priori** ; Cat-A évaluait **l'étiquette image**, pas la boîte | **Réutiliser sans nouvel entraînement** : \`prepare_image\`, \`_grid\`, validation du SHA du modèle et même seuil |
| [COCO 2017 validation](https://cocodataset.org/) et [copie des annotations](https://huggingface.co/datasets/LibreYOLO/coco2017/blob/main/instances_val2017.json) | 5 000 images de validation COCO annotées en boîtes ; fichier JSON SHA-256 \`e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f\` (COCO annotations CC BY 4.0) ; photos filtrées sur **licence déclarée CC BY 2.0** | **Réutiliser** un sous-échantillon de validation sans stocker de JPEG dans GitHub ; SHA vérifiés avant travail |
| F3-A/F3-B/R2-B catalogues et métriques | Contrats de catégorie image et rappel d'identité de référence, mais **pas** d'évaluateur IoU de vrais objets | **Adapter** seulement un petit lecteur de boîtes YOLOX et IoU/AP50, en signalant qu'il s'agit de métriques non officielles sur une petite cohorte |
| Références tierces [Smartulf123](https://github.com/Smartulf123/microduck-companion), [GC-RENCAO](https://github.com/GC-RENCAO/microduck-companion) | Prototypes de suivi et vision, pas de preuve indépendante de catégorie sur le robot RK3566 | **Veille uniquement**, pas de modèle ni code importé |
| [OEM PR #381](https://github.com/pollen-robotics/microduck/pull/381) et [#414](https://github.com/pollen-robotics/microduck/pull/414) | Ouvertes au contrôle du chantier ; #381 propose un cerveau, #414 une carte, aucune n'est livrée dans le sous-module épinglé | **Aucun lien** avec la performance d'images COCO et aucun droit moteur |

## 2. Protocole réel, source et droits

- **Poids** : strictement les mêmes YOLOX Nano ONNX que Cat-A, SHA-256 vérifié ; aucun autre modèle.
- **Annotations** : [instances_val2017.json](https://huggingface.co/datasets/LibreYOLO/coco2017/blob/main/instances_val2017.json), ~20 Mo, annotations COCO 2017 **validation** ; téléchargement borné, SHA-256 vérifié.
- **JPEG originaux** : compartiment public officiel COCO via son endpoint HTTPS S3 à certificat vérifiable (`https://s3.amazonaws.com/images.cocodataset.org/val2017/` ; l'hôte `images.cocodataset.org` présentait un défaut de certificat TLS en CI) ; serveur officiel \`https://images.cocodataset.org/val2017/\`, fichiers correspondant aux \`image_id\` du JSON ; seuls les enregistrements portant un identifiant de licence **Attribution License / CC BY 2.0** dans les métadonnées sont pris. **La déclaration de licence n'est pas une vérification juridique indépendante du fichier original ; aucune image n'est redistribuée, enregistrée en mémoire durable ou publiée.**
- **Cohorte fixée par le code et le SHA, sans sélection selon le résultat** : tri déterministe SHA-256(\`kwipi-cat-a2a-unbiased-v1:image_id\`) sur les candidats admissibles, **4 images pour chacune des cinq classes** \`person\`, \`cat\`, \`dog\`, \`chair\`, \`sports_ball\` et **4 images sans instance de ces cinq classes**. 24 images uniques ; plusieurs catégories peuvent coexister sur une même image. \`iscrowd\` concernant les classes visées et annotations géométriquement invalides écartent l'image. Pas de fichier privé, nom de personne, portrait individuel ni reconnaissance biométrique.
- **Résolution et classes** : inférence YOLOX Nano en **416 px** ; boîtes reconverties vers les dimensions d'origine, padding écarté, NMS par catégorie à IoU 0,50, score minimal Cat-A 0,25 inchangé. Classes COCO \`person=0\`, \`cat=15\`, \`dog=16\`, \`sports_ball=32\`, \`chair=56\`; autres classes dont \`shoe\`, main/pied et catégories fines restent **non couvertes**.
- **Critères de localisation** : appariement 1:1 par catégorie à **IoU≥0,50** ; vrais positifs, faux positifs, faux négatifs, précision/rappel, **AP50 interpolée 101 points par catégorie** ; moyenne macro uniquement sur les catégories effectivement présentes, et erreurs sur images sans cible. **Ce n'est pas la mAP COCO officielle à IoU 0,50:0,95**, pas un résultat sur tout COCO val ni une évaluation d'identité d'instance.
- **Variabilité et limites** : petit échantillon, photos non triées par hauteur/angles/profondeurs, pré-entraînement COCO train du modèle (absence de fuite indépendante non auditée), auteurs/contrats déclarés. Ne pas optimiser les seuils sur ces résultats ; tout nouvel essai doit conserver les IDs ou choisir une nouvelle validation séparée.
- **Coûts** : inférence médiane/p95 et RSS du **runner CPU Linux seulement**, aucune valeur extrapolée au RK3566, NPU, températures ou batterie.

## 3. Porte Cat-A2b : vraies captures basses

Les recadrages de Cat-A **ne sont pas** des photos prises bas. Les photos COCO de ce lot sont **des vraies photographies** mais **la hauteur de la caméra n'est pas connue**. Aucun des corpus bas généralistes examinés lors de l'audit n'apporte, sans vérification complémentaire, des annotations exploitables des **cinq catégories demandées** avec **hauteur ~25 cm prouvée**, autorisations fiables et prises indépendantes.

**Pour ouvrir Cat-A2b :** obtenir un corpus neuf avec hauteurs/caméra étalonnées et documentées (idéalement à hauteur réelle du capteur robot, non présumée égale aux ~25 cm de hauteur totale du robot), plusieurs pièces/séances, distances, lumières, angles, animaux et balles mobiles. Annoter les boîtes et l'état visible/partiellement visible/absent, organiser des splits disjoints par séance/appareil/lieu, auditer les licences et le consentement (enfants/animaux), vérifier la répétabilité et les échecs « inconnu ». Les images privées ne seront jamais committées ; utiliser un manifeste local et le pipeline COCO existant si les droits le permettent.

**Données supplémentaires manquantes** : hauteur de caméra physique finale, angle du capteur IMX219/GC2093, corpus domestique autorisé, nombre d'exemples statistiques suffisant, modèle de reconnaissance de \`shoe\`/parties du corps et annotations indépendantes. Ne pas utiliser de fausses « images basses » provenant de recadrages pour affirmer un bon résultat.

## 4. Contrôles

- **Tests purement logiciels** : [\`tests/test_cata2_bbox_eval.py\`](../tests/test_cata2_bbox_eval.py) couvre le protocole JSON, sélection reproductible, absence de licence non commerciale, géométrie/IoU, boîtes multiples, confusion classes, NMS, padding et refus des données anormales. Ce sont des cas **synthétiques**.
- **CI distincte sur vraies images** : [\`.github/workflows/cat-a2-coco-bbox.yml\`](../.github/workflows/cat-a2-coco-bbox.yml), déclenchée par PR ou manuellement, récupère temporairement les *vrais* JPEG et les poids hashés, ne publie aucun média. Pour annoncer une précision, **citer le run correspondant**, ne jamais reprendre les résultats Cat-A sans vérification.
- **Décision d'intégration** : tant que les erreurs de classes/boîtes, les inconnus et les angles bas ne sont pas évalués indépendamment, **retester, ne pas déployer**. \`robotd\` reste seul arbitre de la sécurité et des moteurs ; aucun accès \`mediad\`/capteur/SQLite/LLM n'est ajouté ici.

**Statut de preuve** : le lot Cat-A2a est une **évaluation hôte** de catégories (non une fonctionnalité autonome sur Kwipi), et Cat-A2b **reste à réaliser sur de vrais angles bas**. Un score de CI ne peut pas certifier la navigation, l'anti-escalier ni la sécurité auprès d'enfants/animaux.
