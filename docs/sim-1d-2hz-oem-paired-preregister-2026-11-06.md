# SIM-1D/A — deux séquences réelles de caméra MuJoCo et cadence initiale 2 Hz

**Préenregistrement du 06/11/2026, AVANT inférences du nouveau lot.**

## Observation, hypothèse, preuve et risque

- **Acquis** : [SIM-1C OEM réellement exécuté](sim-1c-oem-live-camera-results-2026-11-05.md), un seul cycle, `mediad` 640x360, modèle Nano CPU 10,212 ms, un score YOLOX 0,402887 et F2 `idle`. Simulateur OEM épinglé `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` ; [#323](https://github.com/Jean-Philippe56520/Microduck/pull/323) fusionnée sur `main@bc7d9e2fcd6d367417116a4110fd5f1fa39c4740`.
- **Manque prouvé** : ce seul cycle ne démontre ni cadence soutenue, ni continuité d'attention, ni comparaison de scénarios, ni GT caméra indépendante synchronisée.
- **Hypothèse** : la chaîne déjà codée peut effectuer dix acquisitions/décisions consécutives par session à un départ chaque 500 ms *sans dégrader la télémétrie OEM à 50 Hz*. Les scores de régions entre les deux mondes doivent être rapportés même s'ils sont faibles ou erronés.
- **Risques** : surcharge CPU du rendu 30Hz+inférence, frame répétée ou vieillie, saturation des requêtes ToF, fraude de niveau de preuve en appelant la balle présente « visible ». **Pas de deuxième caméra, nouveau pilote, commande moteur, modèle, seuil ou SQLite**.

## Scénarios préfixés et vérité indépendante disponible

Deux **séquences temporelles nouvelles**, sur **deux scènes constructeur existantes**, sans retouche d'images, de positions, de poids ou de paramètres de détection :

1. **B** : `scene_ball.xml`, `DUCK_SIM_KEYFRAME=HOME`. L'XML OEM inclut `ball.xml` avec une balle 70 mm à `(0.30,0,0.035)`. Vérité indépendante **seulement** : **balle existante dans le monde XML**. *Sa présence dans les pixels du capteur à l'instant exact n'est pas établie*.
2. **C0** : `scene.xml`, `DUCK_SIM_KEYFRAME=SIT` ou `HOME` si déjà préfixé pour le comparateur. L'XML constructeur ne contient **aucune balle dédiée**. Vérité indépendante **seulement** : **pas de balle dans ce monde** ; les autres motifs (robot, sol) peuvent parfaitement susciter des propositions YOLOX. Aucun score classe/IoU n'est autorisé sans masques de GT horodatés.

La borne **GT par image / visible-hors champ** reste `UNKNOWN` car le service OEM `mediad` ne publie pas d'identifiant de pas MuJoCo synchronisé avec `MjData` ni de masque de segmentation. Il est interdit d'aligner a posteriori une segmentation statique sur une frame vivante et de publier des TP/FP/IoU. **La suite SIM-1D/B** devra d'abord qualifier cette passerelle de vérité indépendante (puis scènes réellement inédites) avant d'annoncer une reconnaissance.

## Protocole avant code et résultats, commun aux deux sessions

- Reprendre le workflow de démarrage éprouvé de SIM-1C, son plugin Pollen Reachy x86 v0.14.4 SHA `3045989c437be6f7859262f1970c550d6fc92d9ea9b59e49a05d5ec7bc4afbe9` (**diagnostic PC non parité OEM v0.15.3**), le Nano ONNX SHA `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`. Réutiliser `read_simulator_telemetry(hz=10)`, `acquire_simulated_oem_frame`, `evaluate_simulated_camera_cycle`, `AutonomyBrain` F2 *mock*.
- **10 cycles par monde**, un départ programmé toutes les **500 ms** en horloge monotone ; **pas de nouveau thread**, pas de découpage de flux OEM, pas d'adaptation dynamique de FPS. Une erreur = arrêt de la séquence et rapport d'échec, aucune réussite accordée aux cycles manquants.
- **P1** : 10/10 trames fraîches et timestamps caméra strictement croissants, 10/10 F2 `idle` ou `inspect unknown`, gardes `robotd/tofd=coherent` à 10/10, 0 commande moteur, 0 écritures ExperienceMemory, 0 catégorie/promesse source authentifiée.
- **P2 cadence 2 Hz** : début de chaque cycle au plus 125 ms en retard sur sa date planifiée, intervalle entre **captures** médian dans **[0,40;0,60] s**, et au moins 9/9 intervalles entre captures dans **[0,35;0,70] s**. Si non, `FAIL_2HZ` même avec dix décisions réussies. Mesurer p50/p95/max cycle total, inférence ONNX CPU, âge de l'image et nombre de cycles `idle`/`inspect` ; aucun extrapolation au robot.
- **N1 fail-closed** : trame identique, périmée, erreur de sockets, `robotd` inférieur à 45 Hz, absence de modèle ou décision non mock => STOP et pas de promotion. Fixture PC valide/rejet et tests sur les statuts conservés.
- **N2 témoin C0** : aucun score `ball_detected`, identité ou mémoire causale n'est produit, y compris si YOLOX propose une boîte sur le sol ; comptabiliser régions non vérifiées sans appeler cela `FP`.
- **STOP systématique** : simulation sans vrai `mediad`, absence de plugin/model SHA, capteur/temps/CPU non cohérents, une seule commande moteur émise par Companion, toute inférence GT injectée dans F2, tentatives de modifier le constructeur et toute image ou audio enregistrés. Les échecs restent documentés sans retoucher seuils.
- **Témoin historique** : SIM-1C a réussi une acquisition et une décision `idle`. Le nouveau résultat est **cadence/continuité**, pas un score de classification ou un test de nouvelle scène géométrique.

## Autorité, retour arrière et limites

`robotd` OEM seul contrôle les moteurs/ONNX/sûreté à 50 Hz ; `mediad` seul rend/sert l'image. Le nouvel observateur ne fait que des appels de lecture `robot.health`/`robot.subscribe`/`tof.stream` et `media.frame`. Ses propositions F2 restent `mock`, ses observations non authentifiées et sa mémoire in-memory sans écriture. Pas de Qwen, pas de modèle RKNN/NPU, pas de test sur robot réel. Le script est un banc d'essai PC temporaire ; suppression du script et des ajouts de workflow rétablit SIM-1C. Ce lot ne valide **aucun** des 95–100 % d'acceptation perceptive sans GT indépendante visible.

**Statut initial** : `NOT_RUN`, jusqu'au compte rendu de la CI / session OEM réelle. Aucune correction d'échec n'autorise à changer après coup les critères de succès, les 10 cycles ou la liste des scènes.
