# VIS-FOCUS-A2 — porte de source temporelle indépendante (audit en lecture seule, 04/11/2026)

**État : `STOP_A2_SOURCE_NOT_QUALIFIED`.** Aucun essai temporel multimodal, programme de suivi, modèle, image, inférence, cadence adaptative, modification OEM ou nouvelle base SQLite dans ce lot. Une absence de source qualifiée est un **blocage**, pas une permission de fabriquer une GT ou d'augmenter les scores. [Autorité : plan d'action](plan-action.md). [Préenregistrement/audit sur l'issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6641402524) **avant ce document**.

## Référence GitHub et niveaux de preuve

- [QUAL-R0 #305](https://github.com/Jean-Philippe56520/Microduck/pull/305) fusionnée (10/10 CI) ; [VIS-FOCUS-A1 #307](https://github.com/Jean-Philippe56520/Microduck/pull/307) fusionnée après **9/9 CI** sur `de12252599b109c016b853d699998d2cc0a96442`.
- `main@fce5d138bb1a1130091d921ba10352a8ec770400` **vérifié après #307** ; sous-modules **inchangés** : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`.
- A1 : **15/15 tests spécialisés**, suite Python générale **2 517 tests** dans la CI #41901833007. `experiments/vis_focus_a1_host.py` décrit une **piste d'événements mock explicitement fraîche**, après le F2 existant, sans nouvelle écriture SQLite ni commande ; il n'est **pas** importé par le logiciel embarqué. `microduck_companion/autonomy.py` a été restauré au blob historique `476051625738c8102918c91fd0293c629620bce1` pour préserver B10/B11.
- Les **1 316 IDs COCO consommés**, dont les PR #301 et #304 fermées sans fusion, ne peuvent pas être rejoués comme validation indépendante. Résultats de reconnaissance de ces PR **invalides**.
- **A2 audit seulement** : sources lues sur GitHub OEM / documentation officielle ; **aucune** vidéo, annotation, modèle, donnée privée, GT indépendante de série temporelle ou robot physique téléchargés/testés. Pas de mesure FPS/IoU/reacquisition A2.

## Déficit démontré et risque scientifique

Le `PassiveIntent` de F2-B choisit déjà une **catégorie** dans un instantané contenant potentiellement plusieurs observations ; il ne distingue pas deux instances d'une même catégorie. A1 peut sélectionner un `track_id` **fourni par une fixture**, et le décrire lors d'une autre observation uniquement si le même jeton est expressément présent et frais. Mais un jeton de fixture ne prouve ni le maintien d'un objet réel, ni une position, ni la capacité d'un détecteur à fournir cette association.

**Témoin** : F1 + F2 + une SQLite ExperienceMemory sans complément. **Candidat actuel** : A1 non embarqué, catégorie choisie par le même F2 puis indice de fixture à la source. **Erreur à refuser** : nourrir le candidat avec des identifiants issus de la GT et ensuite calculer un taux de suivi contre ces mêmes identifiants. Ce résultat serait circulaire, et non un gain. Une IA ou une mémoire ne doit jamais transformer l'ancienne piste en position toujours actuelle.

## Matrice de réemploi : existant exact vs manque

| Source/code épinglé | Capacité réellement constatée | Manque pour A2 |
| --- | --- | --- |
| `microduck_rl/src/mjlab_microduck/sim/camera.py` | Caméra simulée opt-in, ~15 FPS, flux UYVY 640×360 via TCP à longueur préfixée | Pas d'étiquettes, de `track_id` authentifié, ni GT indépendante **dans le flux caméra** |
| `microduck_rl/.../apartment.xml` | Appartement avec trois balles libres et géométries de chaises | Décor existant ; aucun protocole de nouvelles trajectoires temporelles disjointes et validées |
| `microduck_companion/sim_ball_segmentation_gt.py`, `sim_vis_d_new_scenes_f2_fixture.py`, `sim_vis_f_gt_preflight.py` | Masques `mjOBJ_GEOM` sur poses RGB/segmentation **statiques** et mesures de visibilité | Pas de séquence multi-instance indépendante horodatée, associée à un candidat de détection aveugle |
| `mediad/src/detect.rs` + `duck-detect/src/lib.rs` OEM épinglés | Boîtes + scores mono-classe, détecteur off par défaut, cadence 2 Hz de paramètre | `media.detections` sans catégorie multi-classe ni identifiant temporel réel ; ne pas inventer d'adaptateur |
| `experiments/vis_focus_a1_host.py` | Comparaison synthétique de l'intérêt courant sur jetons frais mock | Aucun tracker géométrique, aucune identité physique, aucun effet robot |
| `ExperienceMemory`, F1/F2/DET | Contexte, motifs, familiarité SQLite unique, abstention | Souvenir ≠ observation courante, récompense ≠ preuve d'effet, aucune permission motrice |

**STOP SIM-VIS-F maintenu** : [rapport de préflight](sim-vis-f-oem-gt-preflight-2026-10-30.md), 3/4 cas statiques géométriquement valides mais l'occultation par fauteuil `ball_hidden_by_chair` **non prouvée** par le rayon OEM. Ne pas reposer ni inférer à nouveau ces cas pour améliorer leur score.

## Corpus publics : candidats, PAS données adoptées

| Corpus | Intérêt documenté | Porte manquante / décision |
| --- | --- | --- |
| [PUMaVOS / XMem++](https://github.com/mbzuai-metaverse/XMem2/tree/adc7d4cd26b7b7592d37f0bea97dbfb8b3990281) | **24 vidéos, 21 187 images annotées denses à 30 FPS**, occultations, mouvements, objets semblables ; [README épinglé](https://github.com/mbzuai-metaverse/XMem2/blob/adc7d4cd26b7b7592d37f0bea97dbfb8b3990281/README.md) et [LICENSE_PUMaVOS](https://github.com/mbzuai-metaverse/XMem2/blob/adc7d4cd26b7b7592d37f0bea97dbfb8b3990281/LICENSE_PUMaVOS) indiquent **CC BY 4.0, y compris commercial avec attribution** | **Candidat prioritaire de préflight metadata uniquement**, pas adopté. Vérifier provenance et droits sous-jacents *de chaque vidéo*, contenu, classes exactes, nombre d'instances simultanées, masques et timestamps réels/indices, disjonction scènes. 30 FPS déclaré pourrait permettre une comparaison 2/1,5/1 Hz par sous-échantillonnage **si** les images/GT sont effectivement synchrones, sans interpolation. Aucun fichier importé |
| [SA-V / Meta](https://ai.meta.com/datasets/segment-anything-video/) | **51 000 vidéos, 643 000 pistes masquées**, [fiche officielle](https://ai.meta.com/datasets/segment-anything-video/) : **CC BY 4.0**, annotations humaines ou assistées puis relues ; données collectées par prestataire | Candidat de continuité **agnostique aux classes**. La fiche précise **aucune catégorie sémantique** : **ne peut pas valider** « deux balles », le classement F2 par catégorie ni la reconnaissance chat/chien/chaise sans annotation indépendante supplémentaire. Vérifier droits, horodatages, nombre de pistes et séquences avant téléchargement ; aucun média importé |
| [YouTube-VIS officiel](https://youtube-vos.org/dataset/vis/) | Vidéos avec masques/identités d'instance multi-images, plusieurs catégories, occultations possibles | [Conditions officielles](https://youtube-vos.org/dataset/term/) : annotations CC BY 4.0, **données pour recherche non commerciale uniquement** ; droits des vidéos non garantis. Vérifier licences **pour l'usage concret**, catégories et densité/horodatage des labels avant sélection. **Aucun fichier téléchargé** |
| [TAO](https://taodataset.org/) | 2 907 vidéos / 833 classes / GT de pistes, diversité d'objets | [Article officiel](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123500426.pdf) : GT à **1 image/s**, insuffisante pour chiffrer de manière indépendante les points intermédiaires à 1,5 ou 2 Hz sans interpolation non prouvée ; origines/licences vidéo hétérogènes. **Ne pas choisir comme témoin de comparaison des trois fréquences** |
| [DAVIS 2017](https://davischallenge.org/davis2017/code.html) | Masques multiples densément annotés par image train/validation ; potentiel témoin d'instance | **Métadonnée officielle du [site DAVIS](https://github.com/davisvideochallenge/davisvideochallenge.github.io/blob/master/index.html) : données sous CC BY-NC 4.0** (distincte de la licence BSD du code d'évaluation). Donc **non retenu pour un usage commercial** sans droits supplémentaires. Vérifier aussi les droits de chaque séquence, classes, horloges et disjonction avant tout usage de recherche non commerciale ; aucun téléchargement |

**Résultat de l'audit des droits renforcé (lecture seule, sources publiques, pas de fichiers)** : le référentiel DAVIS annonce explicitement **CC BY-NC 4.0**, donc il ne constitue pas un corpus commercial par défaut. PUMaVOS et SA-V annoncent **CC BY 4.0** dans leurs sources officielles, ce qui rend l'étude des droits plus prometteuse mais **ne qualifie pas à elle seule chaque vidéo, la classe, l'identité perceptible ou la fréquence effective**. La priorité de **vérification de métadonnées** est PUMaVOS 30 FPS ; SA-V est une alternative agnostique aux classes. Les restrictions YouTube-VIS et la GT 1 FPS TAO restent inchangées. Les licences du code XMem++, SAM 2 ou des modèles ne sont **pas** des permissions implicites d'installer leur tracker, leurs poids ou leurs scripts dans Kwipi. Aucun outil supplémentaire ni préflight pixels autorisé par ce constat.

Les corpus ne valent **pas** caméra OEM basse ni GT de distance métrique ; sans calibrage, `viewpoint_height=unknown`, `distance=unknown`, `angle=unknown`. Données publiques ≠ droits automatiquement compatibles avec redistribution/CI/travail commercial.

## Porte A2 à franchir AVANT code ou essai vidéo

**Observation/risque** : une GT indépendante ne suffit pas à elle seule à fournir un suivi prédictif ; l'identité GT doit servir de **comparateur caché**, jamais d'entrée F1 ou d'identifiant de décision. Sans détecteur de catégorie réellement vérifié ou sans identifiants d'instances de provenance connue, la seule mesure pertinente est la **qualité des données et éventuellement une borne de visibilité**, pas la continuité de Kwipi.

**Préflight positif** :
1. Source/version/empreinte/licence et droit de stockage/CI vérifiés ; pas de média privé ni d'extraction de données personnelles, cohorte de séquences disjointe des anciens tests ; les 1 316 IDs COCO ne sont pas réutilisés.
2. Au moins une séquence **inédite** avec ≥3 instances simultanées dont ≥2 de même catégorie, observations négatives, occultation, changement de vue ou objet déplacé. **Vérité terrain indépendante** de localisation et d'identité d'instance, par image pertinente.
3. Provenance/frame index/timestamps mesurés, sans inventer une fréquence ni interpoler une GT ; pour 2/1,5/1 Hz choisir une grille temporelle **identique** et préenregistrer ses offsets/fenêtres. GT assez dense aux instants échantillonnés.
4. Si un détecteur est évalué : version/poids/empreinte/licence contrôlés **avant** inference, même sortie et seuil fixe pour les 3 grilles ; GT identités strictement masquée pour F1/F2/A1. À défaut de correspondance de piste de perception réelle, **ne pas appeler le résultat suivi**.
5. Définir à l'avance les métriques par scène : événements visibles, omissions, FP, commutations d'intérêt, erreurs de correspondance, abandons corrects, délai de réacquisition et taux d'abstention ; arrêt si manque de négatifs/GT ou fuite GT→entrée. Budget PC explicite ; CPU/NPU/thermique/RSS robot **inconnus** jusqu'au matériel.

**Tests négatifs de porte** : classe confondue, absence d'image, timestamps faux/inversés, GT d'une autre image, piste déplacée, deux instances de même catégorie interverties, écran/photo/peluche non distinguable d'une présence réelle, faux IDs issus de la GT, source à 1 FPS utilisée pour conclure sur 2 Hz, licence incompatible, image déjà consommée, sûreté absente/STOP. Toute erreur de provenance ou de comparabilité ⇒ **STOP et aucun score promu**.

**Succès de cette étape de qualification** = source effectivement accessible **sans fuite**, séquences/clocks/GT/licence/splits audités et protocole d'ablation gelé **avant tout modèle**. **Non succès aujourd'hui** : ces vérifications ne sont pas réalisées. Les chiffres d'une série temporelle ne doivent donc pas être calculés.

## Suite / retour arrière

Maintenir `STOP_A2_SOURCE_NOT_QUALIFIED` et **ne pas ajouter** tracker, filtre temporel, modèle, nouveau processus caméra, autre arbitre F2, autre SQLite ou service moteur. Réutiliser **d'abord** les sources vidéo/métadonnées officielles si la porte des droits et de GT est franchie ; sinon revenir à PER-DATA-GATE / autre jalon indépendant du plan directeur, **sans inventer de preuve**. `robotd` seul pilote et sûreté à 50 Hz, `mediad` seule caméra, Qwen PC facultatif. Comparer éventuellement 2/1,5/1 Hz uniquement avec données et mesures fiables, jamais pour déduire une économie d'énergie sur RK3566 depuis des fixtures.

**Retour arrière :** aucune source de production modifiée ; si un futur audit révèle un défaut de droit/GT, rejeter le corpus, conserver #307 comme expérimentation PC hôte et ne pas toucher aux archives B10/B11 ou aux sous-modules. L'absence de comparabilité = `unknown/en attente` et non zéro performance ou autonomie acquise.
