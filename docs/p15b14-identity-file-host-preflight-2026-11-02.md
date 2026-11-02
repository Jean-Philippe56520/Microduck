# P15-B14 — garde de provenance locale (PC Linux, 02/11/2026)

## Décision / écart établi

**Objectif :** vérifier sur un véritable socket Unix de fixture que le producteur de `media.detections` et l'identité OEM publiée à côté désignent le même processus, avant de considérer la forme B12 comme transport admissible. Le résultat **ne devient pas une observation physique de confiance**.

**Baseline :** `main@4362682534aaf68c11497bc89f217ac57a405c4c`, code B13 de la PR #267. OEM épinglé `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, simulation `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto OEM `1ee58387810cebb67ae0d634c351d95024483bce` ; source B12 `e2e9bfef7d7c4f46fe51924937e7939d78d00383`. PR Qwen #97–99 fusionnées, sans lien avec ce lot. Pas de mise à jour des sous-modules.

**Manque prouvé :** le décodeur B13 sait lire la forme des détections B12, mais ne vérifie pas l'identité d'un producteur Unix. Une simple chaîne `hello` de l'ancien `probe_official_mediad` ne résout pas l'authentification B12 : `media.sock` est le socket OEM `media.frame` accessible au groupe `robot`, interdit au compte Kwipi isolé.

**Réutilisation OEM vérifiée :** `duck-ipc-proto/src/lib.rs` définit `Identity` et `publish_identity` ; `mediad/src/main.rs` appelle `log_startup_identity!("mediad")` et `mediad/systemd/mediad.service` déclare `User=mediad`, `RuntimeDirectory=mediad`. Le constructeur écrit `identity.json` avec `service`, `version`, `revision`, `pid`, `built_at`, `exe`. Le fichier est **auto-déclaré** par le processus, non attesté cryptographiquement. L'idée retenue est un seul socket de détections et un fichier d'identité, plutôt que deux sockets dont `media.sock`.

## Réutiliser / adapter / créer

Réutiliser `SO_PEERCRED`, `_connect_unix`, `_recv_line`, `_strict_json` et le validateur B13 `parse_b12_local_shape_notification` ainsi que `B12LocalSequenceGate`. Le module de **fixture hôte** `microduck_companion/b14_host_identity_gate.py` est neuf et **non sélectionné dans la composition Yocto B10** ; aucun module B6 épinglé n'est modifié.

Le lecteur de fixture n'accepte qu'un répertoire temporaire direct `kwipi-b14-*` détenu par son UID non-root, mode `0700`. Il exige `identity.json` régulier, non symlink, taille ≤ 2048 octets, lecture `openat(O_NOFOLLOW)` et bornée ; socket nommé `detections.sock`, mode `0600` ; correspondance PID/UID `SO_PEERCRED` et PID du document, révision B12 exacte ; même document/empreinte et même inode de socket avant/après, notification ≤ 4096 octets, horodatage frais et séquence croissante.

**Portée limitée :** dans cette fixture le serveur et lecteur ont volontairement le même UID hôte. **Sur robot, `mediad` et `kwipi` auront des UID distincts**, le répertoire et le socket utiliseront les ACL constructeur ; ce module n'accepte jamais `/run` et **n'est pas le lecteur cible**. La valeur renvoyée est `host_fixture_identity_claim_consistent_not_sensor` avec `category=unknown`, `verified_sensor=false`, zéro stockage, moteur et mémoire. Aucune capture, aucun `robot.do`, aucun `media.frame`, aucun appel WebRTC/Internet/SQLite, aucune activation de service.

## Critères positifs / négatifs fixés avant essai

**Positif :** fixture Linux non-root, un seul socket Unix émetteur passif, 11 tests, zéro octet de requête, PID UID correspondant à `identity.json`, révision exacte, forme B12 valide/fraîche, aucune capacité physique revendiquée.

**Négatifs/STOP :** absence de socket ou d'identité, mauvais PID ou révision, deuxième processus Unix réel, clé JSON dupliquée/supplémentaire, fichier symlink/altéré/remplacé, permissions excessives, contenu trop gros, horodatage futur/périmé, séquence rejouée, mauvais UID/timeout, tentatives de chemin `/run`, nouveau groupe `robot`, changement de SHA des modules B6, régression CI. Le repli est toujours le **refus** et l'inaction. Rollback : supprimer les trois nouveaux fichiers du lot ; aucune intervention WSL2/robot nécessaire.

## Preuves et portes restantes

- **PC Linux isolé antérieur :** 11 tests hôte positifs/négatifs réussis avec dépendances simulées ; ne pas présenter comme exécution du vrai dépôt.
- **WSL2 opérateur, 02/11/2026 :** patch appliqué dans checkout séparé au commit de base `4362682534aaf68c11497bc89f217ac57a405c4c` ; exécution réelle `python3 -B -m unittest discover -s tests -p test_p15b14_host_identity_gate.py -v` : **11 tests, `0,224 s, `OK`, `P15_B14_TESTS: PASS`, `P15_B14_EXIT: 0`**. Les modules Microduck réels du checkout ont été utilisés ; il ne s'agit ni d'une CI GitHub ni d'un test de `mediad` sur robot.
- **GitHub :** la branche P15-B14 contient les fichiers source et tests vérifiés par SHA Git contre le patch WSL2 ; la suite complète CI du dernier HEAD doit réussir avant fusion. Aucun déploiement B14 dans le rootfs B10.
- **Cible en attente :** ACL et lisibilité effective de `/run/mediad/identity.json` sous l'UID `kwipi`, appartenance aux groupes, identité du binaire B12 exécuté (la seule révision déclarée n'est pas une empreinte du code en mémoire), remplacement/restart de socket et fichier, protection des chemins, montage `/run`, charge CPU/RSS/NPU et moteur 50 Hz. Si une preuve manque, **STOP, inconnu/inaction**. La future adaptation runtime exigera revue OEM, version/packaging et portes P16/P17 nouvelles.

**Aucune modification** du `robotd`, `mediad`, de `upstream/`, des poids, des services, du rootfs, de la WIC ou des clés RAUC.
