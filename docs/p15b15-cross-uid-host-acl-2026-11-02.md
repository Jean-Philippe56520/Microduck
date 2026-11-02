## Résultat candidat de CI (02/11/2026)

**PR #269 / HEAD fonctionnel `c6e05a435bfdcb3684f0df28c5f28aa8d9d9860f` : 5/5 workflows réussis.** La CI Linux privilégiée existante a réellement exécuté **8/8 tests B3, 8/8 tests B7 et 9/9 tests B15** sur le même SHA (aucun skipped dans la porte dédiée). La suite Python non-root a exécuté **2 345 tests, 47 skipped, 0 erreur/échec** ; neuf skips B15 attendus. Les contrôles P15A, P16 (fixtures de rootfs) et N1 sont verts. Après mise à jour documentaire, la CI devra être recontrôlée au dernier SHA avant fusion. **Toujours non testé sur robot, NPU, service ou fichier `/run` de la cible.**

# P15-B15 — preuve Linux multi-UID et contrat ACL OEM B8 (02/11/2026)

## Décision avant essais

**But fonctionnel nécessaire :** tester de bout en bout le futur trajet `mediad` → `kwipi` entre **deux UID Linux distincts** : droit de traversée nominatif sur le dossier privé, droit nommé sur le seul socket, identité auto-publiée par l'OEM, identité du pair Linux, et notification B12 fraîche. La sortie doit rester **unknown / inaction**, sans croire une caméra fictive ni écrire en mémoire.

**Manque comparé à l'existant :** P15-B7 ([CI Linux](https://github.com/Jean-Philippe56520/Microduck/actions/workflows/per-p15b3-oem-unix-dac.yml)) a prouvé les ACL B8/DAC sur de faux sockets entre UID distincts, mais pas la lecture conjointe des métadonnées B12 et de `identity.json`. P15-B14 (PR #268 fusionnée, 5/5 CI vertes dont 2 336 tests Python, 38 ignorés) a testé les deux sources mais avec **un seul UID propriétaire/lecteur**. Ces deux résultats ne prouvent pas leur composition ; P15-B15 l'évalue sur hôte.

## Sources et choix de réutilisation

- Dépôt `main@9b2b307e21e56ea807be436ea279b9e047bf9f64`, OEM épinglé `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, MuJoCo `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto OEM `1ee58387810cebb67ae0d634c351d95024483bce` ; source compilée B12 `e2e9bfef7d7c4f46fe51924937e7939d78d00383`. Qwen PR #97–99 fusionnées et indépendantes. Aucun gitlink modifié.
- **OEM** : `duck_ipc_proto::publish_identity` écrit `/run/mediad/identity.json`, `mediad.service` déclare `User=mediad`, `RuntimeDirectory=mediad`. L'émetteur B8 applique une ACL POSIX **exactement 44 octets** au sous-répertoire `kwipi` (accès `--x` nommé, mode observable `0710`) et au seul `detections.sock` (accès `rw-`, mode `0660`). `media.sock` et `robotd.sock` restent au groupe `robot`, jamais au compte `kwipi`.
- **Réemployer** `B12LocalSequenceGate`, `parse_b12_local_shape_notification`, `_pinned_identity` B14, `_connect_unix`, `_recv_line` et le workflow Linux DAC B3/B7 existant. **Créer seulement** `b15_cross_uid_host_gate.py` (garde **strictement temporaire, non empaqueté**) et `test_p15b15_cross_uid_host_gate.py` ; aucune deuxième caméra, socket OEM, DB, dépendance externe, modèle ou service.

## Seuils et tests définis avant lancement GitHub

**Positif** : exécuter sous noyau Linux un émetteur factice ayant abandonné définitivement root pour UID/GID `31052/31064` et un lecteur `31053/31062`, groupes secondaires vides et hors `robot`; le serveur possède les inodes, applique les **deux ACL B8**, publie `identity.json` (0644), puis envoie une notification de forme B12. Le lecteur confirme `SO_PEERCRED` UID/GID/PID + identité déclarée, ACL byte-pour-byte, inode stable, fraîcheur ≤ 2 s et séquence. Résultat : `host_two_uid_claim_consistent_not_sensor`, catégorie `unknown`, `verified_sensor=False`, **zéro** média/mémoire/moteur.

**Négatifs/STOP** : ACL répertoire seule ou socket seule, permission dossier élargie ou ACL UID étranger, identité non lisible par `kwipi` ou erronée (PID/révision), rebind sans réapplication de l'ACL, erreur d'horloge future/périmée, séquence rejouée, accès aux faux sockets `media.sock` et `robotd.sock`, groupe `robot` accordé, chemin `/run` réel, symlink, fichier remplacé, ou régression P16 des SHA B6. Au premier doute, **refus sans événement**. Retour arrière : revert des deux fichiers B15, de l'ajout au workflow et de la documentation. Aucune donnée/permission sur l'hôte WSL2 ou robot n'est modifiée.

**CI vérifiable** : conserver les tests B3/B7 sous `sudo` dans leur workflow existant et **ajouter un test B15 explicitement lancé sous root Linux**, dont les enfants perdent les privilèges. La suite Python non privilégiée peut **ignorer ces neuf tests** ; la CI dédiée doit les **exécuter**, sans skip ni échec. Le blocage d'une CI fait STOP de fusion.

## Observations et limites

- **Avant intégration à GitHub** : 9/9 tests du nouveau module sur noyau Linux x86_64 dans un conteneur root, avec dépendances B13/B14 minimales reproduites ; de véritables UID différents, de vrais inodes/ACL/connexions Unix. **Ce n'est pas le dépôt complet ni une CI GitHub**.
- **B14 antérieur** : 11/11 WSL2 utilisateur avec modules Microduck réels, puis CI du dernier SHA 5/5 réussie ; fusion #268, non embarqué.
- **Porte cible toujours fermée** : aucun processus `mediad` OEM réel, aucun modèle RKNN/NPU, ni test du binaire Yocto B12 en exécution ; les identités publiées sont auto-déclarées, non des signatures du code chargé. Le répertoire `/run`, la lisibilité réelle de `identity.json` pour un UID isolé, le support POSIX ACL sous le noyau cible, le redémarrage réel/rebind et les ressources ne sont pas validés sur le robot. Les nombres UID/GID ne sont **que des fixtures** et ne sont pas les UID cible. Aucun lecteur B15 n'est empaqueté, aucune reconnaissance multi-catégorie/SQLite/autonomie prouvée.

**Ne pas confondre** : CI/Linux ACL réussi ≠ accès au robot, identité déclarée ≠ exécutable mesuré, détection de forme ≠ catégorie ou personne reconnue, réception d'une notification ≠ causalité d'action. Toute intégration embarquée nécessite une révision indépendante de la configuration et des droits OEM, de la provenance des paquets, puis des tests physiques supervisés.
