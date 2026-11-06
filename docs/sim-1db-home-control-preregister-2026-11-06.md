# SIM-1D/B1 — comparaison HOME/HOME préenregistrée (06/11/2026)

**Statut lors de ce préenregistrement : prévu, pas encore exécuté.** Base : `main@7e966b7464cbacff4f126af1b2d7763f68516627`, #324 fusionnée après neuf CI réussies sur `6c4072857fff7b0076eeed6b416741376dbe0628`, fil de revue corrigé et résolu. [Porte avant code](https://github.com/Jean-Philippe56520/Microduck/pull/324#issuecomment-6690457416). Les vingt cycles historiques A restent conservés, sans nouvelle qualification rétroactive.

## Question et manque attesté

Le témoin A démarrait à SIT contre HOME pour la scène balle. Le code disponible sait déjà acquérir les images `mediad`, appliquer Nano CPU, projeter les régions vers F2 mock, vérifier cadence et contexte OEM. Il manque une comparaison à **initialisation HOME identique** et une qualification du contrôle de lancement sur de vrais processus OEM. Aucun nouvel algorithme de perception n'est nécessaire pour mesurer cet écart.

`HOME` n'est pas une pose caméra maintenue : `duck-sim up` active et stabilise `robotd`. La pose réelle et le pas de simulation de chaque image restent inconnus. Zéro commande émise par Companion ne signifie donc pas absence de mouvement OEM.

## Réutiliser / adapter / ne pas créer

Réutiliser sans modification `experiments/sim1d_oem_2hz_series.py`, `sim1d_launch_context.py`, `microduck_companion/sim_media_frame.py`, `sim_vis_oem_cycle.py`, `sim_bridge.py`, F2 et l'unique mémoire éphémère sans écritures. Adapter seulement le workflow `.github/workflows/sim-1c-oem-live-camera.yml` avec un mode B1 explicite, indépendant du mode historique A. Aucun nouveau service, pilote, caméra, modèle, SQLite ou module de production.

Sources relues : `duck-sim`, `body_server.py`, `camera.py`, `scene.xml`, `scene_ball.xml`, `mediad/src/frame.rs`, les scripts/tests Companion et les protocoles d'autorité. Pins inchangés : OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Les deux XML partagent `robot_groundcontact.xml`, décor et éclairage ; vérifier structurellement cette égalité après exclusion du seul ajout `ball.xml`, des noms de modèle et des keyframes inutilisées avec HOME. Aucun XML modifié.

Nano CPU historique SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`, mêmes seuils et prétraitement. Plugin x86 Pollen Reachy v0.14.4, SHA `3045989c437be6f7859262f1970c550d6fc92d9ea9b59e49a05d5ec7bc4afbe9`, témoin hôte déjà audité, distinct de Microduck v0.15.3 ; aucune adoption ni redistribution de poids ou de nouvelles dépendances. Les limites C3/SIM-1C restent applicables.

## Campagne fixée avant les sorties

Une campagne bornée : `scene_ball.xml/HOME`, puis redémarrage officiel `scene.xml/HOME` ; **dix cycles par monde**, départ toutes les 500 ms. Pas d'inférence SIM-1C supplémentaire en mode B1. Le préflight d'acquisition OEM existant peut lire une image sans inférence ; elle ne compte pas parmi les vingt cycles.

Les critères A restent inchangés : retard de départ maximal 0,125 s ; chaque intervalle caméra dans [0,35 ; 0,70] s, médiane dans [0,40 ; 0,60] s ; horodatages strictement croissants ; télémétrie cohérente et gardes existantes. Le collecteur vérifie le contexte avant et après chaque série. Les comptes de régions et d'intentions sont descriptifs ; aucun seuil de succès sémantique fixé après observation.

**Négatif de provenance avant chaque série :** vérifier d'abord que le contexte demandé correct existe et annonce HOME, demander ensuite le cas opposé au collecteur existant avec des callbacks interdisant toute acquisition/inférence. Exiger `STOP_ACTIVE_WORLD_UNVERIFIED`, zéro cycle, contenu du monde inconnu et zéro écriture/commande. Cela évite un faux succès du négatif dû à l'absence de tout simulateur. Aucun poids chargé pour ce négatif.

**Succès B1 :** deux négatifs réussis, deux séries complètes et cadencées avec contexte stable et HOME, aucune catégorie promue, aucun moteur Companion ou apprentissage causal. Conserver la durée CPU, l'âge des images, les intervalles et les intentions exactes. Le workflow produit un JSON de comparaison dont le verdict est explicitement limité à l'initialisation commune.

**STOP :** source différente, mauvais contexte, changement de PID/socket/scène, télémétrie inadéquate, image absente/périmée, dépassement de cadence ou autorité non permise. Conserver tout échec dans le bilan ; ne pas déplacer les objets, changer de modèle ou seuil, ni relancer jusqu'à réussite. Une correction d'exécution purement technique doit conserver la première tentative et produire une tentative distincte justifiée.

## GT indépendante — porte distincte non franchie par B1

Le flux OEM épinglé transmet longueur puis UYVY, sans identifiant de rendu ni pas MuJoCo. `media.frame` expose un temps de capture côté mediad, pas l'état complet de la scène rendu. Le masque statique de `sim_ball_segmentation_gt.py` existe déjà, mais n'est pas automatiquement la vérité des images dynamiques de mediad. Le fichier `mediad/src/frame.rs` avait le même blob `80f23c59dff7c03c718a0f8bb0dc8d3fefa57026` dans le pin et l'amont `4a763dd893f3982c3a11c136468ccf5d26bcc28a` contrôlé lors de la reprise.

Sans appariement indépendant exact, aucun IoU/TP/FP/FN, taux de reconnaissance, présence visible certifiée, suivi d'identité ou effet causal. Ni proximité d'horodatages, ni reconstruction de pose approximative, ni hash de pixels ambigu ne suffisent. Une éventuelle instrumentation du rendu OEM doit être revue explicitement : pas de patch silencieux, de second flux caméra ou de vérité injectée dans F2.

## Risques, confidentialité, retour arrière

Services officiels et sûreté inchangés ; `robotd` seul pilote à 50 Hz. Ports WebRTC non locaux filtrés comme dans SIM-1C. Aucun accès au robot physique, WSL utilisateur ou médias privés. Archives uniquement JSON numériques, pas de pixels, poids, flux audio ou SQLite.

Retour arrière : supprimer uniquement le mode B1 candidat du workflow en conservant ses résultats. Pas de modification de sous-module, ONNX ou garde pour obtenir PASS. PR après mesure nouvelle ou échec décisif, pas une PR de simple préparation ; fusion seulement après neuf CI du HEAD final. NPU/RK3566, thermique, autonomie réelle et cible V1 95–100 % restent non démontrés.
