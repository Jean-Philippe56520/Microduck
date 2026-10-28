# CAM-OEM-1 — fidélité matérielle des essais visuels (28 octobre 2026)

**Statut : candidat en branche, tests PC/fixtures à vérifier en CI.** Aucune caméra physique, image privée, poids ONNX, SQLite, modèle, sous-module OEM, politique de marche ou moteur touchés. **Un précontrôle des métadonnées n'est pas une validation de la caméra du robot.** Le plan directeur reste [plan-action.md](plan-action.md).

## 1. Porte OEM-first : observation, hypothèse et échec

**Observation vérifiée sur le code OEM épinglé :** le matériel n'est pas un profil caméra unique. `Board::Zero3` utilise un IMX219 monté à 90° et `Board::Beta` un GC2093 à 0°. `mediad` épinglé définit pour l'IMX219 un champ horizontal nominal/famille de **62°**, avec une calibration familiale à 1280×720, mais n'en fournit **pas** pour le GC2093. La qualité vidéo `[media] quality` par défaut est **720p30 (1280×720 à 30 i/s)**, distincte du mode de lecture capteur épinglé **1920×1080**. L'image simulée épinglée est **640×360 à 15 i/s** : le `mediad` virtuel utilise la géométrie MuJoCo **45° verticaux** (soit environ 72,7° horizontaux si 16:9), sans calibration optique du vrai robot. **La hauteur et l'inclinaison réelles de l'axe optique de Kwipi n'ont pas été mesurées.** La plage de 100–300 mm de Cat-A2b est un protocole de collecte, pas un profil OEM.

**Hypothèse de travail :** une comparaison de détection qui ne consigne ni la variante carte/capteur ni le champ optique, l'orientation, la résolution, la qualité vidéo et la hauteur ne permet pas d'affirmer une représentativité OEM. Une petite barrière de validation déclarative peut bloquer cette *formulation* avant un bilan, sans toucher au pipeline OEM.

**Preuve visée :** un rapport reproductible sur des **déclarations synthétiques** distingue les profils matériels, le rendu MuJoCo et les captures publiques/privées ; refuse les incohérences et les champs non mesurés ; jamais de `robot_hardware_verified=True`, même lorsque la déclaration correspond à un profil familial.

**Critères d'échec/stop :** affirmer que `62°` est mesuré sur l'exemplaire de l'utilisateur ; remplacer l'intrinsèque inconnu du GC2093 par celui de l'IMX219 ; confondre `640×360` MuJoCo et une capture réelle ; accepter une hauteur de 250 mm parce que le robot fait ~25 cm ; publier une image privée ; activer une caméra, une inférence ou une commande moteur en CI ; introduire une deuxième boucle, une seconde SQLite, ou une dépendance tiers. **Risques :** fausse assurance de représentativité et faux positif de correspondance de métadonnées. **Retour arrière :** retirer uniquement `camera_fidelity.py`, les tests et ces mentions documentaires ; aucune donnée, firmware ou configuration de robot à restaurer.

## 2. Révisions, réutilisation et non-duplication

| Source réellement examinée | Révision / preuve | Décision |
| --- | --- | --- |
| `upstream/microduck` : `robotd-params/src/board.rs`, `src/lib.rs`, `mediad/src/sensor.rs`, `mediad/src/camera.rs` | [OEM 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567), profils, rotation, modes et géométrie publiable | **Réutiliser les constantes comme référence**, sans copier le daemon, ni prétendre interroger l'unité réelle |
| `upstream/microduck_rl/src/mjlab_microduck/sim/camera.py` | [RL b02fdea4](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3), 640×360/15 fps | **Séparer du capteur physique**, ne pas modifier la scène |
| `cata2b_private_low.py`, comparateur aveugle #118, éditeur #120 et essais #123 | `main` 939c2ba1 ; manifest privé v1, SHA/JPEG, hauteur déclarée, splits et boîtes | **Réutiliser sans changer le schéma** ; une hauteur déclarée n'est pas attestée |
| Registre communautaire C3 : QuackNav, microduck-brain, Quacksat, Twin, GC/Smartulf, Lab/Studio | [Registre](community-reference-registry-2026-10-26.md) ; aucun accès caméra signé ni calibration certifiée pour notre unité | **Ne pas importer** : ajouter un pilote, une caméra ou un détecteur serait redondant et risqué |
| `microduck_companion/camera_fidelity.py` et tests | Nouveau validateur pur standard-library, sans I/O | **Créer un précontrôle optionnel** car aucun lecteur existant ne distingue ces profils ; pas un service ni une authentification |

`robotd` reste propriétaire des moteurs, `mediad` de l'image, `ExperienceMemory` seule SQLite. Aucune PR OEM #381/#414/#450 (non livrée au pin) n'est assimilée à une capacité installée ; #450 reste ouverte au contrôle GitHub du 28/10.

## 3. Contrat et conditions d'emploi

Entrée : `CameraDeclaration` (source, dimensions livrées, carte, capteur, rotation **annoncée par `media.video`** plutôt que rotation du JPEG, palier de qualité `mediad`, source d'intrinsèques, angle horizontal facultatif, hauteur mesurée **déclarée**). `assess_camera_fidelity(..., target_board=...)` ne lit **aucun fichier, réseau ou périphérique**. Sans identification de `target_board`, pas de comparaison OEM. La reconnaissance par défaut du capteur est simplement un attendu OEM : une substitution `[media] sensor` ou `--rotate` doit être auditée séparément plutôt que normalisée en silence.

Verdicts :

- `insufficient_for_oem_camera_comparison` : métadonnées insuffisantes, incohérentes, publiques ou MuJoCo ; raisons fixées et sans chemin/ID privés.
- `declared_oem_metadata_consistent_only` : *seule* la déclaration est cohérente avec le profil épinglé et la plage de collecte. Ne signifie **ni** que `mediad` fonctionne réellement, **ni** que la caméra est calibrée, **ni** que la capture est indépendante, **ni** que les catégories sont reconnues.
- Les drapeaux `robot_hardware_verified` et `real_camera_performance_verified` sont toujours **faux**.

**Limite importante :** pour le GC2093, aucun angle nominal ne peut être substitué ; une déclaration de mesure `intrinsics_source="robot"` est admissible **pour contrôle de cohérence seulement**, sans authentification. Pour IMX219, `62°` est familial/nominal et les distorsions, l'inclinaison, le centrage optique et les modifications ISP ne sont pas mesurés ici. Le `fovy` du simulateur, son orientation et son rendu couleur ne doivent pas devenir des performances matérielles.

**Ne pas introduire ce garde comme un verrou bloquant dans le validateur privé v1 :** ses 29 photographies anciennes et leurs manifestes ne disposent pas d'un relevé authentifié du matériel ; les écarter silencieusement ou les présenter comme non conformes à un robot inconnu fausserait le rapport historique. Ce précontrôle est un outil d'audit séparé, exigible seulement avant toute **nouvelle revendication de comparaison OEM**.

## 4. Tests et suites de vérification

Tests positifs : constantes OEM épinglées, mode 720p30 livré contre 1920×1080 du capteur, profil Zero3, Beta avec calibration par unité *déclarée*, intervalle optique explicite, rotation. Tests négatifs : variante inconnue, capteur/rotation erronés, GC2093 sans intrinsics, angle nominal incohérent, `NaN`/type booléen, qualité incompatible, image publique/privée même basse, MuJoCo 45°/640×360, source non autorisée. Vérification AST : zéro import capteur/réseau/SQLite/moteur. Tous exécutables sur PC avec `python -m unittest tests.test_camera_fidelity -v`.

**Inconnus bloquants** : exemplaire/board réel, `robotctl health`, `/etc/robot/robotd.toml`, `media.video` effectivement reçu, capteur/lentille/montage, calibrage par unité `[media.intrinsics]`, hauteur du centre optique, inclinaison, éclairage, déformations, débit et latences RK3566. Le vrai passage Cat-A2b #78/C3-B demande les deux relectures humaines indépendantes, scènes disjointes, effets de projection TV vs monde réel, et benchmark sur **véritables captures de l'optique concernée**, puis l'audit `scripts/resource-audit.sh` sur matériel. Sans cela, **aucune précision ou fiabilité caméra de Kwipi n'est démontrée**.

## 5. État de livraison

Renseignement à mettre à jour d'après le SHA final PR et les CI. Le lot n'a pas exécuté Qwen, MuJoCo, YOLOX ni `mediad` ; c'est une porte documentaire et des fixtures, pas une progression de l'autonomie.
