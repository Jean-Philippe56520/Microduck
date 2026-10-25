# F3-C — Contrat de notifications constructeur et signaux sonores fictifs

**26 octobre 2026 — [PR #34](https://github.com/Jean-Philippe56520/Microduck/pull/34), non fusionnée.**

## Objet et frontière des preuves

Cette étape **n'établit pas de connexion au robot**. Elle confronte le contrat de nos modules F1/F2/F3 au code constructeur `pollen-robotics/microduck` à la **révision épinglée** `942e58e3aa6dbb28e7037203fff11866122c7567`, puis construit un parseur sécurisé qui traite uniquement des **fixtures JSON reproduisant les formats officiels**. Aucun moteur n'est commandé, aucun microphone n'est écouté, aucune image ou parole brute n'est lue, transmise ou enregistrée.

Les seules véritables perceptions visuelles traitées à ce jour sont les **20 photos CC0 externes** du banc hôte F3-B, avec un test de seulement six images ; elles n'étaient ni issues de `mediad` ni évaluées sur le Rockchip.

## 1. Ce que dit le constructeur — vérifié dans les sources épinglées

| Source OEM | Ce qui est exposé | Ce qui n'en découle pas |
| --- | --- | --- |
| [`mediad/src/session.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/session.rs) | Notification JSON-RPC **`media.video`** au client WebRTC : dimensions, rotation, horodatages monotone/temps réel et paramètres optiques optionnels | Ni pixels, ni classification d'animaux, ni calibration physique automatiquement établie |
| [`mediad/src/detect.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/detect.rs) | Notification **`media.detections`** avec `width`, `height`, `took_ms` et `boxes` (`x0/y0/x1/y1/score`) ; détecteur **une classe Microduck**, désactivable | Une boîte n'est **pas** un chat, un chien ni une personne ; le score OEM peut dépasser **1** (exemple 1,38), donc n'est pas une probabilité calibrée |
| [`mediad/src/frame.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/frame.rs) et [`duck-ipc-proto`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs) | Le socket Unix local `/run/mediad/media.sock` accepte **`hello`** et **`media.frame`**. Le second fournit un en-tête JSON puis des octets **UYVY** bruts, sans base64 | **Il ne diffuse pas `media.detections`** ; la sonde `probe_official_mediad` de F1-B ne lit que `hello` et ne donne donc pas accès à des observations |
| [`pet-detect/README.md`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/pet-detect/README.md) et [`pet-detect/src/lib.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/pet-detect/src/lib.rs) | Modèle local de **son de caresses sur la tête** exploité par `robotd`, avec états de début et fin | Pas de classe d'animaux, ni reconnaissance du nom du robot, de « stop » ou de « viens », ni notifications sonores fournies par `mediad` |
| [`mediad/src/main.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/main.rs) | Diffusion des notifications aux clients de canal de contrôle WebRTC, et socket local de frames | **Pas de voie locale de notifications authentifiées** utilisable par notre cerveau sans autre intégration |

**Point de sécurité OEM :** le commentaire du serveur `mediad` précise que le service WebRTC accessible sur le LAN ne réalise pas d'authentification locale. F3-C ne démarre **aucune session WebRTC** et ne transforme pas un JSON reçu d'un autre processus ou d'un client réseau en perception « vérifiée ». Une connexion `hello` réussie à un socket indépendant n'authentifierait pas non plus automatiquement les notifications d'un autre transport.

## 2. Code livré

- `microduck_companion/passive_media_router.py` : `parse_oem_shape_notification(raw)` ne reconnaît que `media.video` et `media.detections`, avec enveloppe JSON-RPC exacte et **absence d'identifiant** (ce sont des notifications). La taille de message est limitée à **4 096 octets**, les dimensions à **4 096 px** et les boîtes à **32**. Types, nombres finis, rotations 0/90/180/270, coordonnées cohérentes et métadonnées intrinsics sont validés. Les identifiants, classes et champs inconnus sont rejetés.
- Le retour `MediaMetadata` inclut la **provenance invariable** `oem_notification_shape_unverified`, `verified_sensor=False` et `category="unknown"` ; seul un **nombre de candidats Microduck** et éventuellement un score **brut, non probabiliste** sont exposés. Aucune boîte précise, empreinte d'image, identité ou calibration complète ne ressort. Une trame `media.detections` vide est signalée comme **absence de candidat**, pas comme un objet toujours présent.
- `MockAudioCueRouter` accepte un format de **faux signaux sonores** (`petting_start`, `petting_end`, `ambient_change`, `keyword_microduck`, `keyword_stop`, `keyword_viens`) avec séquence croissante, horloge monotone, âge maximal **2 s** et cadence minimale **0,5 s**. Ces valeurs ne décrivent pas un détecteur vocal développé : la sortie reste `mock_audio_fixture_only`, `verified_microphone=False`, `category="unknown"`.
- Un mot-clé **`stop` fictif** n'est **jamais** converti en ordre `robot.stop` et ne remplace jamais la sécurité de `robotd`.
- `microduck_companion/passive_media_demo.py` : **3** notifications OEM de forme officielle et **5** signaux sonores fictifs, sans réseau, caméra, audio ou mouvement. La CI Python intègre le nouveau scénario.

Les module F1-B (`probe_official_mediad`), F1-C (SQLite), F2 (motivations/intentions) et le pilote constructeur restent **inchangés**. Il est volontaire de ne **pas** soumettre les candidats Microduck au cerveau : le flux WebRTC n'est pas authentifié ici, les scores ne sont pas calibrés et les catégories animales ne sont pas disponibles.

## 3. Vérifications et reproduction

Le fichier `tests/test_passive_media_router.py` contient **31 tests supplémentaires** couvrant :

- Formats officiels `media.video` et `media.detections`, avec et sans intrinsics, rotation, comptes de boîtes, score brut **supérieur à 1**.
- Rejet des commandes `robot.*`, requêtes `media.frame`, réponses JSON-RPC dotées d'un ID, fausses étiquettes `dog/cat`, prétentions d'authentification, dimensions incorrectes, coordonnées, NaN/Inf, clés JSON dupliquées, médias bruts et volumes dépassés.
- Signaux sonores entièrement fictifs, rejets de doublons, horodatages périmés/futurs, horloge régressive, cadence et faux mots-clés dangereux. **Aucun arrêt moteur** exécuté.

```bash
python -m unittest discover -s tests -p test_passive_media_router.py -v
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.passive_media_demo
```

Sur branche, la [suite complète a réussi avec **551 tests**](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40243777520) (520 tests F3-B existants + 31 tests F3-C). La preuve du **dernier commit** doit encore être confirmée avant fusion ; ce rapport ne prétend pas qu'un robot ou `mediad` live a été testé.

## 4. Éléments non réalisés et prochaine décision

**Non réalisés :** authentification d'un flux de métadonnées réel, client WebRTC embarqué, réception de vrais événements depuis `mediad`, traitement du socket `media.frame`, décodage caméra UYVY, suivi d'animaux, mots-clés vocaux réellement classifiés, mesure de précision des sons, exécution d'intentions, ressources/thermique sur RK3566 et pilotage moteur.

La feuille de route doit distinguer l'intégration future de la vraie caméra et du son des **simples interfaces de métadonnées validées logiciellement**. Le prochain lot **F3-D**, dans une PR indépendante après revue/merge de F3-C, examinera un jeu de test plus large, les faux positifs et les limites CPU/RAM des bancs accessibles, ainsi que les conditions nécessaires à une acquisition réelle sûre. Ne pas conclure que six photos F3-B ou des mots-clés fictifs suffisent pour une autonomie sociale ou motrice.
