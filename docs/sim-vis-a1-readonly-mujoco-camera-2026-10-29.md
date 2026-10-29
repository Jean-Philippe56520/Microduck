# SIM-VIS-A1 — premiere chaine visuelle OEM MuJoCo, lecture seule

**Date : 29/10/2026. Etat final partiel : camera MuJoCo directe analysee en CI, voie mediad BLOQUEE et test temps reel non passe.** [Plan directeur](plan-action.md), [scene OEM](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/robot/microduck/scene_apartment.xml), [media.frame](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/frame.rs). **Aucun robot physique.**

## Porte 0 — objectif / ecart / preuve / risque / retour arriere

- **Objectif concret :** voir au moins une vraie image *rendue dans MuJoCo* depuis la camera OEM du robot simule, lire des mesures ToF 8x8 coherentes et appliquer **le detecteur public YOLOX-Nano Cat-A existant**, sans mouvement de Companion. Il s'agit d'un test d'acquisition/chaine visuelle, pas d'une preuve de comprehension du monde.
- **Ecart prouve :** le [smoke OEM actuel](../.github/workflows/mujoco-smoke.yml) definit explicitement `DUCK_SIM_CAMERAS=` et [X2-C](x2c-mujoco-passive-acceptance-2026-10-27.md) ne lit pas les pixels ; les 29 JPEG Cat-A2b sont des prises reelles non annotees independamment, inutilisables comme verite terrain de la scene MuJoCo.
- **Hypothese :** avec `DUCK_SIM_CAMERAS=a` et `DUCK_SIM_SCENE=apartment`, le vrai `mediad --sim-camera` et le vrai `tofd --sim` fournissent des lectures exploitables par les validateurs/YOLOX existants.
- **Comparateur :** ancien smoke headless (ToF + etat, **0 pixel**) vs nouveau smoke A1 (**2 images OEM fraiches, 2 trames ToF, 1 infernce YOLOX**). Les seuils et empreintes du modele restent figes ; aucune experience sur les JPEG prives.
- **Success / negatif :** resultat seulement si medias (UYVY 640x360 rotation 90, horodatages valides, charge utile exacte), robotd sain >=45Hz et ToF 2x64 avec seq croissante, poids Cat-A SHA-256 `c789161e...a20b7d` verifies, interface ONNX valide, resultat du decodeur standard. Rejet automatique si camera absente, mauvaise orientation, flux tronque/perime, ToF absent ou bloque, robotd non sain, modele faux ou runtime manquant. Aucun chiffre de TP/FP/FN sans boite ground truth independante.
- **Arret :** un essai opt-in en CI, sans forcer un echec a reussir par des ajustements de modele/prompt/surete ; probleme de GStreamer/GL ou cadence = resultat d'integration **insuffisant** et preuve du blocage. Le banc habituel conserve la camera desactivee.
- **Retour arriere :** supprimer `microduck_companion/sim_visual_a1.py`, son test et les opt-ins A1 dans `scripts/sim-smoke.sh` et le workflow. Aucun sous-module, daemon OEM, modele, poids ou registre change.

## Inventaire OEM, licences et reuse

| Composant | Source existante | Decision |
| --- | --- | --- |
| Moteur/surete/etat OEM | `robotd` 50 Hz, `robotctl`, `sim_ipc.py`, `sim_probe.py` | **Reutiliser** ; zero appel RPC de mouvement ajoute |
| Camera simulée | `microduck_rl/sim/camera.py` → `mediad --sim-camera` → local `media.frame` | **Reutiliser** ; ajout du seul lecteur ponctuel A1 (pas de pilote, pas de second flux) |
| ToF | `tofd --sim` / parseur `sim_probe` | **Reutiliser sans modification** ; ToF frontal ne certifie pas le sol |
| Detecteur categories | Cat-A `prepare_image` / SHA fixe, Cat-A2a `decode_boxes` / NMS | **Reutiliser** sur une image JPEG en RAM apres conversion UYVY ; pas de nouveau reseau |
| Scene | RL `scene_apartment.xml` → `apartment.xml`, 3 balles `ball_0..2` en corps dynamiques | **Reutiliser**, lire les noms via XML comme **inventaire du monde**, pas labels pixel |
| Tiers/OEM PR | OEM #381, #414, #450 ouvertes (verifiees au 29/10) | Non livrees, non integrees ; aucune dependance ajoutee |

Les sources OEM/RL restent leurs pins : `942e58e3aa6dbb28e7037203fff11866122c7567` et `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Le modele Cat-A Megvii YOLOX-Nano, licence Apache-2.0, est telecharge **public** uniquement dans le runner, digest entier valide. Aucun asset prive. Les composants Python d'hote `Pillow`, `PyOpenGL`, `numpy` et `onnxruntime` restent isoles dans le venv CI ; OSMesa/GStreamer sont des dependances de simulation uniquement.

## Ce que le test ne peut pas conclure

Le vrai [`duck-body` épinglé](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/sim/body_server.py) publie la lecture des articulations/IMU/ToF, **mais pas la segmentation par pixel synchronisee des balles visibles sur l'image**. Trois balles dans le monde ne signifient pas trois balles visibles et le modele peut manquer une balle peu realiste. Les boites YOLOX sont **des propositions** ; aucun rappel, AP50, TP, FP, FN ou succes cognitif n'est revendique.

Ce test ne valide pas la camera physique (famille IMX219/GC2093, exposition, NPU, RK3566), une navigation, un regard autonome, une action, une memoire causale ou une interaction avec un objet. En cas de succes A1, **suite distincte** : obtenir une verite terrain rendue/synchronisee independante pour calculer des metriques de detection sur scene non triviale ; comparer ensuite F2 avec/sans memoire sans confondre GT et observations.

## Mode d'execution (CI optionnelle uniquement)

Branche d'opt-in : `feat/sim-visual-a1-20261029`; `.github/workflows/mujoco-smoke.yml` execute `scripts/sim-smoke.sh run` en isolation. `DUCK_SIM_VIS_A1=YES`, `DUCK_SIM_VIS_MODEL=<public ONNX approuve>`. OSMesa pour le rendu sans ecran ; `mediad` est compile depuis le gitlink exact, non patche. Sortie `sim-visual-a1.json` **agregat seul** ; ni photos ni ToF bruts archives. Le script refuse tout lot moteur simultane. Les tests positifs/negatifs Python couvrent le protocole local et le verificateur de scene sur fixtures synthetiques. **La CI ou son succes ne remplace pas l'observation du rendu ni une evaluation indépendante de reconnaissance.**


## Resultat reel et decision d'arret (29/10/2026)

- **Executable** : commit de test `aa63a6be25a48268f1ddd289a85a73be992653c0`, [Python run #40924901229](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40924901229) **vert** : 1 819 tests, 6 ignores ; [N1 #40924901248](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40924901248) **vert** ; [MuJoCo #40924891002](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40924891002) **rouge** avec [artefacts locaux du runner](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40924891002/artifacts/12919524267). La CI a utilise le vrai gitlink OEM/RL epingle, et le vrai modele public Cat-A sha256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`.
- **A1b : resultat positif partiel** du protocole constructeur `microduck_rl/sim/camera.py` (une trame TCP brute `FrameServer`, sans `mediad`) : longueur **460 800 octets**, UYVY **640×360**, orientation 90° et image RGB **360×640**, contraste **ecart-type 60,041**, empreinte SHA-256 frame `4543f9b5fb459237b154f819527eb643353fedc93b649dfbab31ad6ee48afb90` ; **une vraie inference ONNX CPU en 13,194 ms**, seuil fixe 0,25, **zero boite proposee**. Nombre de balles dans le monde OEM : **3** ; visibles dans ce cadre : **inconnu**, donc **aucun taux de reconnaissance, TP/FP/FN/AP50**. Pas de timestamp sur le TCP, aucune capacite temps reel inferee, aucune photo archivee.
- **ToF/OEM, independamment** : `robot_healthy=true`, `health_achieved_hz=49.923...`, 2 trames ToF sim de **64 zones** et sequences croissantes (vues dans la sortie `sim_probe`). Lecture seule ; 0 ordre moteur/LLM/SQLite, pas de capteur physique.
- **A1 (vrai `mediad`) : negatif**, `mediad` tente le port 17901, puis echoue avec `element factory 'webrtcsink' not found` avant de publier `duck-a-frame.sock`. Le constructeur fournit son plugin [microduck-gst-plugins v3](https://github.com/pollen-robotics/microduck-gst-plugins/releases/tag/v3) pour **aarch64 seulement** ; son installateur OEM refuse x86, pas de plugin x86 librement interchangeable affirme. **MuJoCo : 0,42× temps reel** avec OSMesa, ce qui ne valide aucune locomotion stable, meme si le 50 Hz logiciel reste sain.
- **Decision : STOP** apres l'essai predeclare sur ce runner ; ne pas abaisser le seuil pour fabriquer une balle, ni reconstruire l'OEM, ni installer un plugin ARM sur x86, ni presenter le chemin direct comme chemin `mediad`. La PR reste **brouillon**, non fusionnee. Suite sur hote GPU et plugin compatible uniquement si disponibilite constatee, sans sous-module modifie ; autrement, poursuivre les jalons cognitifs independants sans pretendre que cette boucle est complete.
