# SIM-1C — porte OEM MuJoCo en direct, avant la première capture (05/11/2026)

## But et sources exactes

**Banc d'essai indépendant, non un composant déployé.** À partir de #322 (`849e9357aa7d9959ce8c8cf34f2c052023a6c018`, PR encore ouverte à l'établissement du test), démarrer **le constructeur épinglé** : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, via son `scripts/duck-sim up`, avec `DUCK_SIM_SCENE=ball` et `DUCK_SIM_CAMERAS=a`. Demander une seule trame **à mediad** (`media.frame`), lire `robotd/tofd` et essayer une seule inférence sur le modèle YOLOX Nano SHA épinglé, puis F2 **mock**. Trace JSON métadonnées seulement. Aucun robot physique, nouvelle caméra, commande motrice Companion, contenu média publié ou second SQLite.

**Obstacle C3 préalable :** `mediad` requiert le plugin GStreamer `webrtcsink` absent du runner Ubuntu normal. Le dépôt Pollen `reachy-mini-desktop-app@c6ea61a5d57dc069e01aab07c723402b3d8263f5` publie un binaire Linux x86_64 `libgstrswebrtc.so` hash SHA256 `3045989c437be6f7859262f1970c550d6fc92d9ea9b59e49a05d5ec7bc4afbe9`, qualifié en amont par `reachy_mini/.github/actions/webrtc-plugin/action.yml` (Pollen). **Version 0.14.4**, différente de la version Microduck 0.15.3. Usage strict **diagnostic PC temporaire**. Ce n'est ni remplacement ni validation de la dépendance OEM robot ; ne pas le publier, le vendor ou l'installer dans Yocto. `gst-inspect` puis `mediad` doivent confirmer concrètement sa compatibilité, sinon STOP. Aucun WebRTC distant/compte utilisé.

## Test préenregistré, mesurable et arrêt

| Cas | Succès/observation attendue | STOP |
|---|---|---|
| S0 source | Deux SHA gitlinks conformes, `robotctl/robotd/mediad` OEM constructeur construits, plugin C3 x86 SHA conforme et `webrtcsink` reconnu, ONNX exact | SHA, élément, modèle ou ordonnance constructeur différent |
| S1 caméra | Un vrai `duck-a-frame.sock` généré par `mediad`, `media.frame` répond `UYVY` intégral, 640x360 attendu initial, capture ≤2 s, aucune image écrite | Aucun socket, trame tronquée, trop ancienne, classe inventée |
| S2 cognition | Lecture `robotd/tofd` cohérente à ≥45 Hz, **vrai appel ONNX CPU**, 0–3 régions non certifiées, F2 projection mock `idle` ou `inspect unknown` selon scores, journal horodaté | Télémétrie incohérente, pas d'inférence, observation simulée déguisée en capteur, action ou apprentissage |
| N1 source/échec | Si S0/S1/S2 non atteints, afficher `STOP_SIM1C` avec l'étape réelle fautive, zéro crédit de réussite ; tests négatifs logiciels #322 maintenus | Essayer d'inventer les pixels, retoucher scène/poids/seuils ou déclarer PASS |
| Témoins | SIM-VIS-D image + GT géométrique statique séparée, X2-C `robotd/tofd` sans caméra. Leur résultat n'est pas recompté en nouveau comportement | gain comparatif non mesuré revendiqué |

**Succès limité de SIM-1C :** fournir un **premier exemple daté** issu des mêmes *processus* OEM simulés, avec lecture frame réelle, télémétrie cohérente, inférence modèle approuvé et intention non motrice ; indiquer dans le rapport scores et durée CPU. *PAS* de GT indépendante synchrone, contrôle de même pas MuJoCo, taux de détection sur objets, maîtrise multiobjets, 2 Hz soutenus, mémoire on/off, effets moteurs, autonomie ou fiabilité à 95 %. La balle est dans la scène constructeur mais sa visibilité n'est pas présumée.

**Arrêt immédiat et repli :** runner à délai borné ; si plugin 0.14.4 n'est pas compatible, `mediad` ne démarre pas ou `robotd` descend sous 45Hz, consigner l'échec et ne pas remplacer le simulateur par une fixture. La CI détruit l'instance à la fin et ne conserve que traces JSON/logs sanitizés sans image, tokens, audio ni DB. Le constructeur, les gitlinks et les poids du dépôt restent inchangés. Réseau entrant bloqué pour les ports WebRTC/console du lancement officiel sur runner partagé. Un essai robot physique demande un autre protocole.

## Verdict

**Non évalué avant premier lancement GitHub Actions.** Aucun pourcentage de réussite crédible sans exécuter S0–S2. L'exécution est enregistrée par le nouveau workflow isolé `.github/workflows/sim-1c-oem-live-camera.yml` sur la branche `test/sim-1c-oem-live-camera-20261105`; ne pas fusionner ce protocole pilote si le bilan est bloqué.
