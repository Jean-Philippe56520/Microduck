# P15-B7 — traversée Unix limitée des métadonnées mediad (01/11/2026)

## Porte fixée AVANT code ou essai

**Objectif utile.** Vérifier, sur un vrai noyau Linux **avec des sockets factices uniquement**, qu'un processus Kwipi doté d'un UID distinct de `mediad` et **sans groupe `robot`** peut accéder à **un seul socket de métadonnées** derrière `/run/mediad/kwipi` de mode `0700`, sans pouvoir ouvrir `/run/mediad/media.sock` (trames) ni `/run/robotd.sock` (moteurs), ni modifier l'identité publiée par `mediad`. Aucune image, modèle, accès OEM réel ou RPC n'est impliqué.

**Manque concret, non déjà testé.** P15-B3 [#241](https://github.com/Jean-Philippe56520/Microduck/pull/241) a prouvé sur noyau Linux le **socket ToF seul** : ACL POSIX dédiée à Kwipi, pas de groupe `robot`, mais ACL du précédent inode perdue à chaque `unlink/bind`. P15-B4 [#242](https://github.com/Jean-Philippe56520/Microduck/pull/242) a compilé et testé un **prototype** de socket `media.detections` détenu par `mediad`, mode `0600`, derrière un répertoire privé `0700`. Il n'y a encore **aucune preuve Linux que l'UID Kwipi séparé puisse franchir ce répertoire**. Appliquer une ACL au socket seulement ne suffit pas. P15-B5/#243 reste lecteur **PC-fixtures**, P15-B6-P/#244 a un `do_package` WSL2 authentifié par les sorties opérateur, mais le paquet n'est dans aucune image.

**Pin et comparaison OEM.** `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068`, parent de travail PR [#244](https://github.com/Jean-Philippe56520/Microduck/pull/244) `bf008bc9b3cf3391995762bd8122cb36beb5242e`, tous deux avec gitlinks OEM `microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` inchangés ; Yocto `microduck_yocto@1ee58387810cebb67ae0d634c351d95024483bce`. Vérification de `pollen-robotics/microduck` amont `main@b2b0d213a402caeac492dd662ea891faa17f67c0` : `tofd` conserve `SOCKET_MODE=0660`, groupe `robot` ; `mediad.service` `User=mediad Group=mediad SupplementaryGroups=video render robot` ; `robotd.service` conserve `Group=robot`. P15-B4 reste **adaptation scratch, non livrée** : `local_detections.rs` crée d'abord un sous-répertoire `0700`, puis un socket `0600`, sans nouveau producteur. Qwen PR #97–99 fusionnées ; aucune incidence sur les permissions.

**Observation → hypothèse → preuve → risque.**
- Observation : deux barrières DAC distinctes sont requises (traversée du répertoire et ouverture du socket). Sous Linux, le droit `x` sur le répertoire permet la traversée, sans nécessairement autoriser son listing ni la modification de fichiers. Le droit d'accès sur un socket Unix est évalué séparément.
- Hypothèse bornée : ACL `u:<uid_kwipi>:--x` sur le **répertoire privé** et `u:<uid_kwipi>:rw-` sur le **socket de métadonnées déjà lié**, vérifiées sur de vrais objets Linux, devraient autoriser ce seul flux. Ce n'est **pas** une politique déployée et l'environnement Yocto peut manquer de `libacl`/outillage.
- Risques : ACL trop large, préexistance de la cible ou lien symbolique, contexte `setfacl` non disponible sur RK3566, autorisation perdue au rebind/restart, identité binaire OEM non prouvée (`DUCK_REVISION`), détection non horodatée au capteur (`Sighting` dépourvu de `t_ns`), `media.frame` exposée via le mauvais socket, prise d'une détection pour catégorie/présence réelle. Une simulation DAC ne prouve ni effet robot ni absence de tout vecteur d'attaque.

## Réutiliser / adapter / créer

| Élément vérifié | Choix |
| --- | --- |
| `tests/test_per_p15b3_oem_unix_dac.py` : `_probe_as`, UID/GID factices et vrais `fork/setuid/connect` | **Réutiliser** sans modification du test ToF existant |
| `.github/workflows/per-p15b3-oem-unix-dac.yml` : Linux root + `acl`, sans accès robot | **Adapter** la même CI pour lancer les deux suites plutôt qu'ajouter un second runner |
| `scripts/per_p15b4_local_detections.rs` : répertoire `0700`, socket `0600` | **Réutiliser comme contrat source**, aucun patch Rust ni nouveau service |
| `P15-B2/B5` et `ExperienceMemory` | **Inchangés**, aucune promotion d'observation/SQLite |
| Références C3 / Yocto | Aucun composant tiers ou outil OEM supplémentaire justifié pour cette fixture |

**Nouveau minimum :** un module de tests Linux P15-B7 pour le couple répertoire/socket, sans toucher à `upstream/`, aux binaires `tofd`, `mediad`, `robotd`, aux sources P11/P12, au sous-module, aux recettes, à la WIC ni aux clés. L'ACL est appliquée **uniquement** à un dossier temporaire de CI, jamais à `/run` sur PC/robot.

## Positifs, négatifs et STOP préenregistrés

**Témoin (avant ACL) :** socket `detections.sock` mode `0600` et répertoire privé `0700`, propriétaires de l'UID factice `mediad` ; socket caméra `media.sock` mode `0660` et socket moteur `robotd.sock` mode `0660` dans des emplacements factices accessibles à traverser, groupe factice `robot`. Un client forké abandonne ses droits root avant `connect`.

**Cas positifs :**
1. L'UID Kwipi isolé reçoit `EACCES/EPERM` partout sans ACL. Mode et UID/GID effectifs des objets vérifiés.
2. ACL socket **seule** = refus, ACL de traversée du répertoire **seule** = refus.
3. ACL de traversée `--x` + ACL socket `rw-` = accès aux **métadonnées uniquement**, jamais aux sockets `robotd` ou `media.frame` ; refus de l'écriture du fichier d'identité `mediad`.
4. Retrait de l'un des droits = nouveau refus. Remplacement de l'inode du socket par `unlink/bind` = refus avant toute réapplication, même avec ACL du répertoire persistante.
5. Les huit tests ToF P15-B3 existants et la suite Python restent verts sur le SHA exact de la PR ; CI Linux spécialisée exécute réellement le noyau ACL sous root sur **fixtures exclusivement**.

**Négatifs/arrêt :** si une permission `robotd` ou caméra est accordée à l'UID Kwipi, si l'ACL permet de modifier l'identité, si un socket de remplacement reste ouvert sans nouvelle ACL, si `setfacl/getfacl`/root ne sont pas disponibles ou si un test échoue : **STOP** et aucune extension de permission proposée. Le groupe `robot` et l'UID `mediad` ne sont jamais affectés au processus Kwipi réel. Ne pas inférer la persistance d'ACL au redémarrage ou la disponibilité de la bibliothèque ACL dans l'image constructeur.

**Succès strict :** CI Linux vraie **et** CI Python au dernier SHA PASS, seulement pour le droit UNIX de *fixtures*. Repli : retirer le fichier de tests, l'invocation ajoutée au workflow et cette documentation ; aucune donnée du robot ne peut être affectée. **Porte OEM déployable toujours fermée** tant qu'un mécanisme constructeur de création/autorisation **après chaque bind/rebind** pour le répertoire et le socket, les versions compilées et les horodatages de capture ne sont pas conçus, audités, autorisés, compilés et qualifiés. Aucun nouveau daemon, groupe `robot`, RCU, serveur caméra ni service systemd permis dans ce lot.

## Résultat

À compléter après CI réelle ; aucun test CI/robot n'est déclaré réussi par anticipation.
