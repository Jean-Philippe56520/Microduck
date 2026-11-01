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

**Négatif crucial OEM à mesurer :** dans le prototype P15-B4, `safe_dir(private=true)` exige exactement les bits de mode `0700`. Une ACL POSIX de traversée nommée peut faire apparaître un masque de groupe dans `st_mode` (`0710`), même si `group::---` interdit tout accès générique. Mesurer cette dérive sur le vrai système de fichiers et confronter à l'invariant source : si la création/relance OEM refuse l'inode ACL malgré une permission limitée, **STOP intégration**, sans assouplir à l'aveugle la vérification `safe_dir` ni masquer le test. Cette observation éventuelle est distincte de la preuve qu'un UID isolé peut se connecter au premier bind.

**Négatifs/arrêt :** si une permission `robotd` ou caméra est accordée à l'UID Kwipi, si l'ACL permet de modifier l'identité, si un socket de remplacement reste ouvert sans nouvelle ACL, si `setfacl/getfacl`/root ne sont pas disponibles ou si un test échoue : **STOP** et aucune extension de permission proposée. Le groupe `robot` et l'UID `mediad` ne sont jamais affectés au processus Kwipi réel. Ne pas inférer la persistance d'ACL au redémarrage ou la disponibilité de la bibliothèque ACL dans l'image constructeur.

**Succès strict :** CI Linux vraie **et** CI Python au dernier SHA PASS, seulement pour le droit UNIX de *fixtures*. Repli : retirer le fichier de tests, l'invocation ajoutée au workflow et cette documentation ; aucune donnée du robot ne peut être affectée. **Porte OEM déployable toujours fermée** tant qu'un mécanisme constructeur de création/autorisation **après chaque bind/rebind** pour le répertoire et le socket, les versions compilées et les horodatages de capture ne sont pas conçus, audités, autorisés, compilés et qualifiés. Aucun nouveau daemon, groupe `robot`, RCU, serveur caméra ni service systemd permis dans ce lot.

## Résultat réel — 16/16 tests POSIX ACL sur noyau Linux (01/11/2026)

**Source de preuve :** [GitHub Actions #41295547232](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41295547232), **SUCCESS** au SHA de code et de documentation `b65aab491a9ffa76cf16c1bee0263c177faa1c05`. Sous `sudo` sur le runner Linux, avec `setfacl/getfacl` réels, **8/8** tests P15-B3 ToF anciens et **8/8** tests P15-B7 mediad nouveaux **PASS**, les deux suites indépendantes enregistrent chacune `Ran 8 tests ... OK`. Vérification `ast.parse` également PASS ; aucun déploiement ni accès `/run` sur une machine réelle.

**Positif confirmé sur fixtures :** sans ACL aucune connexion de Kwipi ; ACL socket seule = refus car parent privé non traversable ; ACL `--x` sur le répertoire seule = refus car socket `0600`. Avec les deux ACL nominatives, l'UID simulé Kwipi **sans `robot`** peut se connecter à `detections.sock`, mais **pas** à `media.sock` ou `robotd.sock`, ni lister le répertoire ni modifier `identity.json`. Retrait de l'une des deux ACL = refus. Recréation du socket = ACL de l'ancien socket perdue, client refusé jusqu'à réapplication sur le nouvel inode. Tous ces essais ont exercé de véritables `fork/setgroups/setgid/setuid/connect` Linux sur des sockets temporaires, sans RPC.

**Résultat négatif déterminant, validé en CI :** l'ACL de traversée change le mode Unix visible du répertoire privé hors de l'exact `0700`. Or [le prototype P15-B4](../scripts/per_p15b4_local_detections.rs) applique `safe_dir(private=true)` avec la condition `(mode & 0o777) != 0o700`. Le test `test_08_posix_acl_mask_conflicts_with_exact_0700_oem_binder` a réussi **parce qu'il a prouvé cette incompatibilité**. Une adaptation OEM qui réutiliserait tel quel ce garde ne pourrait pas garantir un bind/redémarrage après application d'ACL. **Ne pas contourner ce garde par un chmod aveugle, ni installer une unité `setfacl` post-start, ni élargir les groupes.**

**Décision :** `PASS` pour faisabilité **des deux ACL POSIX sur fixtures Linux uniquement**, et **STOP intégration OEM et image DEV**. Prochaine décision distincte : concevoir une politique OEM appliquée par le processus propriétaire après chaque bind/rebind et validant correctement l'ACL nominative du répertoire (y compris masque/group/other), ou refuser ce chemin au profit d'un accès contrôlé équivalent. Il faudra ensuite vérifier disponibilité ACL dans Yocto et l'identité compilée `DUCK_REVISION`, ainsi que l'origine et fraîcheur des horodatages `Sighting` avant toute observation authentifiée. La permission motrice `robotd` ne peut jamais résulter d'une extension du groupe `robot`.

Au moment de cette preuve, les workflows P15A et N1 sont verts au même SHA ; la suite Python générale était encore en cours au dernier contrôle. La PR [#245](https://github.com/Jean-Philippe56520/Microduck/pull/245) reste **brouillon** empilée sur #244, et ne modifie pas l'OEM, les modèles, les services, la WIC, RAUC ou le robot.

## Réconciliation à la pile actuelle — 01/11/2026

**Manque/précondition vérifiés avant l'intégration :** #243 est fusionnée dans le `main` révisé et #244 est maintenant candidat au SHA `3ec412d554e7a6aed424c1f257be3c117d66e0ba` avec les 19+5 sources inchangées ; #245 repose encore sur l'ancien parent #244. Il faut préserver la CI P15-B3 courante et les documents d'état WSL2 V1 plus récents, sans élargir la politique de droits. Le projet OEM ne fournit **aucune** ACL réelle à installer dans ce lot.

**Objectif/critère fixés :** mettre #245 sur la base du candidat #244 courant en modifiant **uniquement trois fichiers propres B7** : la présente fiche, `tests/test_per_p15b7_mediad_private_dac.py`, et le workflow Linux de P15-B3 **étendu aux tests de socket privé**. Blob du workflow P15-B3 dans le nouveau parent doit être identique au blob historique du parent B7, sinon STOP (pas de réécriture aveugle). Préserver les quatre documents généraux actuels et les gitlinks. **Positifs/négatifs** : kernel DAC réel sur sockets temporaires + refus d'accès aux sockets factices moteur/caméra, ACL répertoire seule/socket seule, rebind perdant les droits, symlink/fichier identité, suite Python ; pas de `/run` réel, groupe `robot` ni capture. **Fusion uniquement après CI verte au nouveau SHA**, STOP si besoin d'un service/runtime/ACL OEM ou de droit moteur. Retour arrière : retirer le test et la modification du workflow, sans changer Yocto/robot.
