# P15-B17 — préparation d'un paquet DEV inerte pour le lecteur B12 (02/11/2026)

## Résultat hôte, sans distribution

[CI P15-B17 #41439809872](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41439809872) au SHA fonctionnel `f588c4cbc018e541c83289212fbd9276f07a32cd` : **12/12 tests PASS**, sans skipped dans la porte dédiée ; deux couches sources préparées indépendamment et comparées par `diff -rq` (identiques), archivage et vérification SHA réussis, sélection 19+5+4 respectée, refus des changements B10/symlinks/source/arbitrary imports/écritures. Les contrôles OEM gitlinks sont verts. **Cette CI n'a exécuté ni BitBake ni la recette dans une image :** les champs de provenance restent `bitbake_executed=false`, `dev_image_selected=false`, `shipping_image_selected=false`, `service_installed=false`, `oem_producer_enabled=false`, `robot_validated=false`. Les autres CI GitHub au dernier HEAD, après documentation, devront être vertes avant fusion. Le paquet B17 n'est donc toujours pas livré.

## Objectif et écart mesurable, fixés avant code

**Base** : `main@f2ab144e23f13729495b31959e34c4110c48cad7`, PR #270 fusionnée après 5/5 CI vertes. P16-B10 a audité le **rootfs DEV B10 existant** : 19 modules P14A + 5 modules B6, deux binaires AArch64 B12, compte `kwipi` isolé. Les quatre sources `b12_local_wire_contract.py`, `b14_host_identity_gate.py`, `b15_cross_uid_host_gate.py` et `b16_oem_readonly_reader.py` ne sont pas dans ces 24 modules et **ne peuvent pas être importées par la distribution B10**. Les recoder serait un doublon ; le résultat B16 reste une affirmation cohérente d'un producteur Linux, pas une attestation du capteur.

**Bénéfice fonctionnel du lot** : rendre ces quatre sources **empaquetables, avec dépendances closes et contenu reproductible**, en les laissant **non sélectionnées** dans toute image, sans démarrer ni modifier `mediad`. Une future porte de sélection DEV/test réel devient possible sans modifier B10 ni les rapports P16 historiques.

## Sources constructeur et décision de réemploi

- Gitlinks invariants : `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Yocto OEM épinglé `1ee58387810cebb67ae0d634c351d95024483bce` ; OE-core `ae5a301091f5b0574ea7444aab40b309b6d9f3f2`.
- **Réutiliser**, sans altérer : P14A (19 modules), P15-B6 (5), `per_p14b_yocto_python_layer._tar_bytes` (archive reproductible), `per_p15b6_passive_python_addon.audit_imports` (dépendances), B16 (socket, PID/UID/GID/ACL B8, forme B12), recettes BitBake `allarch python3-dir`.
- **Adapter uniquement l'empaquetage** : une couche source candidate temporaire contenant **exactement quatre modules**, une recette DEV `kwipi-b12-receiver` avec `RDEPENDS` sur les deux paquets précédents et les dépendances Python ; `LICENSE = "CLOSED"`, diffusion/redistribution **non approuvée**. Pas de nouvelle caméra, moteur, détecteur, daemon, SQLite ou mémoire.
- OE-core épinglé `python3-manifest.json` décrit `grp` et `select` dans `python3-core`, `socket`/`tempfile` dans les portions core/netclient. **La vérification par import réel sur l'interpréteur AArch64 de l'image reste à faire** : un manifeste source n'est pas une preuve de distribution.
- `robotd-params::DuckDetectorParams::default` : `enabled=false`, `hz=2.0`. L'adaptation B4 propose `--kwipi-local-detections`, off par défaut, mais `mediad.service` constructeur épinglé lance le binaire **sans cette option**. Il faudra une décision distincte d'activation DEV, avec contrôle du modèle, ressources, sûreté et retour arrière. **Aucune modification d'unité OEM** dans B17.

## Essais et critères STOP préenregistrés

**Positifs** : (1) inventaire 19+5 historiques identique aux empreintes B10, (2) quatre modules B13–B16 uniquement, sans import Companion hors des 28 modules clos et sans import réseau/moteur/SQLite nouveau, (3) archive TAR reproductible, 4 membres réguliers 0644, UID/GID/mtime zéro, source et SHA vérifiés, (4) recette `allarch python3-dir` installant seulement ces 4 fichiers, `RDEPENDS` strict, sans image, service, groupe, modèle ou exécution, (5) staging/verification dans un dossier temporaire en dehors du checkout, deux sorties identiques, tests positifs et négatifs et CI finale verte.

**Négatifs/STOP** : 19 ou 5 empreintes changées ; quatrième module absent, duplicat ou symlink ; import Companion non empaqueté ; écriture ou commande motrice ajoutée ; membre TAR supplémentaire, mode non conforme, contenu/sha falsifié ; tentative de sélection `microduck-image` shipping, de création de service, d'activation `mediad` ou d'accès `robot` ; dérive des sous-modules/OEM ; CI rouge => **aucune fusion**.

**Portée** : code de staging + tests sur hôte uniquement. Aucun `bitbake -p`, `do_package`, `do_rootfs`, WIC, RAUC, scriptlet, image shipping, installation, permission cible, détection NPU, capteur ni robot qualifiés. Le nouveau paquet est **source candidate non sélectionnée**, et non une distribution DEV prête. `B10` et ses deux rapports hors dépôt restent inchangés.

**Suite et retour arrière** : une porte ultérieure devra contrôler avec `bitbake -e` et les paquets installés l'absence shipping et une éventuelle sélection DEV optionnelle, puis qualifier séparément le vrai producteur actif, le rebind/seq après redémarrage, les ACL de `/run`, l'import Python cible et les ressources RK3566. Retour arrière = retirer le générateur et cette couche candidate hors checkout ; rien n'est activé ou modifié sur la cible.
