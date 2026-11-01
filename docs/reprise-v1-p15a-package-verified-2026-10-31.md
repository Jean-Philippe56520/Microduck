# Reprise V1 — P15A-P paquet vérifié sur WSL2 (31 octobre 2026)

## Décision vérifiable

**Dernière preuve transmise par l'opérateur :** `P15A_EXIT_CODE=0` pour `bitbake -c package kwipi-readonly-probe` (**643 tâches, 633 déjà à jour, 0 échec, 2 avertissements**) et ensuite `P15A_PACKAGE_VERIFY_EXIT_CODE=0` après l'exécution locale en lecture seule de `scripts/per_p15a_yocto_package_gate.py`. Rapport JSON local : `schema=kwipi-p15a-real-bitbake-package-proof-v1`, `status=bitbake_p15a_package_files_verified_only`, `reviewed_source_files=5`, `package_files_verified=3`, `systemd_unit_packaged=true`, `service_auto_enable=disable`, `motor_commands_issued=0`. Le validateur retourne `bitbake_task_execution_attested_by_this_script=false` parce qu'il **ne lance pas BitBake** ; le journal de la tâche réussie et son code retour constituent une preuve indépendante communiquée. La vérification des octets du paquet est donc **validée localement** ; aucune revendication de test robot.

### Empreintes SHA-256 des fichiers `packages-split/kwipi-readonly-probe`

| Fichier dans le paquet | Taille | Mode | SHA-256 |
|---|---:|:---:|---|
| `usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset` | 37 o | `0644` | `01a3df8c2b3bd1199c18e1ff126bc96ac818262014030beec792f463c8de8ba8` |
| `usr/lib/systemd/system/kwipi-readonly-probe.service` | 977 o | `0644` | `ed0c6cd92e2a76a0f687e8bf4b32a22be01a26decb47f70cb432f4eef22e5d9d` |
| `usr/libexec/kwipi/health_probe.py` | 1498 o | `0644` | `11e48364630b2c063d173cd1884a19a886a2467ddead19af1636e072f24ccc21` |

Le rapport vérifie la conformité du script à sa source épinglée, de l'unité au template avec substitution de `libexecdir`, ainsi que le contenu exact `disable kwipi-readonly-probe.service` du preset. La sonde est `Type=oneshot`, inactive par défaut et limitée par son code à une requête OEM `robot.health` ; elle ne remplace pas `robotd` et ne crée ni moteur, ni caméra, ni SQLite, ni boucle autonome.

**Limites que le JSON confirme explicitement :** `rootfs_installed=false`, `service_executed_on_target=false`, `signed_release=false`, `robot_validated=false`, `oem_socket_group_is_not_readonly_acl=true`. L'accès `SupplementaryGroups=robot` au socket `/run/robotd.sock` permet en droit Unix des RPC non-read-only ; la restriction applicative seule ne prouve pas une séparation des privilèges. Ne pas démarrer cette sonde sur robot ni la promouvoir en production sans revue dédiée et tests matériel supervisés.

## Versions, PR et sources de vérité au constat

| Élément | État / identifiant |
|---|---|
| `main` avant la présente mise à jour documentaire | `6acf210fb48b291fc41905e189f7cbf2a34d8659` (revérifier après fusion) |
| OEM Microduck épinglé | `942e58e3aa6dbb28e7037203fff11866122c7567` |
| Yocto constructeur | `1ee58387810cebb67ae0d634c351d95024483bce` |
| OE-core | `ae5a301091f5b0574ea7444aab40b309b6d9f3f2` |
| PR #230 P14B | ouverte/draft, HEAD `514e89ef10599c9177b056d3497915d92d6c1ec9`, CI BitBake distante expirée ; `do_package` WSL2 réussi et 19 modules vérifiés |
| PR #231 P14C | ouverte/draft, HEAD `3bb83e3922d6a1db3d61cf2737a229bbcd99d604`, empilée sur #230 ; sélection de l'image DEV prouvée, pas de rootfs |
| PR #235 P15A | ouverte/draft, HEAD `b5626a2cafabd0836e69685d18988360d3e86f18`, empilée sur #231 ; fixtures 13/13 + 9/9 et tests Python/N1 verts, vérifier toujours le statut actuel de la CI complète |
| PR #233 et #234 | fusionnées, preuves Rust/Python précédentes et portes P15–P17 |
| Qwen PR #97–99 | fusionnées ; sans lien avec les autorisations motrices |

Le plan opérationnel faisant autorité est [docs/plan-action.md](plan-action.md) ; appliquer `AGENTS.md`, [protocole de réemploi](development-reuse-protocol.md), [portes V1 P15–P17](per-p15-p17-v1-release-gates-2026-10-31.md) et [dossier technique P15A](per-p15a-readonly-health-probe-2026-10-31.md) sur la branche #235. Les mentions anciennes « P14B encore en cours » ou « P15A-P à vérifier » sont historiques et remplacées par les résultats ci-dessus. Robot absent. Aucune actualisation de sous-module, aucun secret ou média privé.

## Hôte WSL2 persistant : retrouver les preuves sans relancer de build

Machine déclarée : Ubuntu 26.04/WSL2, `kas 5.2`, environnement `~/kwipi-build-v1`. Couches déjà présentes `meta-kwipi/`, `meta-kwipi-python/` ; checkout P15A `p15a-pr235/` détaché au SHA #235. `yocto/kas/microduck.yml`, `yocto/kas/kwipi-p13b2-local.yml`, `yocto/kas/kwipi-p14b-local.yml`, `yocto/kas/kwipi-p15a-local.yml` **tous dans le même dépôt Git**, faute de quoi KAS refuse la concaténation. `KAS_BUILD_DIR=$HOME/kwipi-build-v1/build`, `KAS_WORK_DIR=$HOME/kwipi-build-v1/kas-work`, `DL_DIR=$HOME/kwipi-build-v1/downloads`, `SSTATE_DIR=$HOME/kwipi-build-v1/sstate`.

Preuves locales à relire **avant toute nouvelle exécution** : `proofs/p14b-package.log`, `proofs/p14b-package.json`, `proofs/p15a-verified.env`, `proofs/p15a-package-retry1.log`, `proofs/p15a-package-verify.json`. Le dernier fichier contient les trois empreintes ci-dessus. Ne pas publier de `bitbake -e` brut (il peut contenir des chemins et de l'environnement local). Aucun besoin de recompiler P13B2, P14B ou P15A si code, caches et sources ne changent pas.

## Prochain chantier : P16 — image de développement, puis RAUC séparément

**Porte atteinte :** la validation du paquet P15A-P local. **Non atteinte :** P15 complet (aucun service réellement démarré sur cible), image DEV `do_rootfs`, bundle RAUC vérifié, validation robot et qualification P17. Ne pas inventer un état « V1 prête à 95–100 % ».

**Avant P16, lecture seule :** (1) vérifier HEAD/CI et dépendances de PR #230→#231→#235, politique de fusion sans CI rouge ; (2) vérifier P13/P14/P15 sources et empreintes ; (3) mesurer disque et espace caches sur hôte ; (4) comparer `IMAGE_INSTALL` DEV/shipping aux recettes OEM épinglées ; (5) contrôler les droits de redistribution (`LICENSE=CLOSED`, P14B `source_license_checked=false`, droits du détecteur/poids YOLO26) ; (6) inventorier les services, presets désactivés, commandes et permissions OEM. Pré-enregistrer négatifs/arrêt et plan de repli avant un `bitbake -c rootfs microduck-image-dev` ; aucun `do_rootfs` n'est autorisé par ce seul document, ne pas toucher à l'image de production. S'assurer que les binaires OEM et le cycle 50 Hz restent détenus exclusivement par `robotd`, et qu'aucun nouveau service ne prend la caméra ou les moteurs.

**Conditions d'arrêt :** manque de droits, image shipping contaminée, service activable automatiquement, paquet manquant, ressources hôte insuffisantes, schémas/modes ou configurations non conformes, CI rouge non justifiée, absence de possibilité de retour arrière. Après rootfs DEV validé, considérer les contrôles de bundle/signature RAUC en lot distinct, clés privées **hors dépôt**, puis P17 qualification ; aucun essai moteur ni validation physique avant robot reçu et supervision.

## Phrase de reprise pour une nouvelle conversation

> Reprends Microduck/Kwipi V1 sur GitHub après P15A-P validé localement le 31/10/2026. Lis README, docs/plan-action.md et docs/reprise-v1-p15a-package-verified-2026-10-31.md ; vérifie main, PR #230/#231/#235, SHA et CI. P13B2 et P14B sont réussis sur WSL2 ; P15A-P est réussi (`P15A_EXIT_CODE=0`, `P15A_PACKAGE_VERIFY_EXIT_CODE=0`, `bitbake_p15a_package_files_verified_only`, 3 fichiers/5 sources, preset disable). Aucun rootfs/RAUC/service sur robot. Ne relance pas les builds précédents. Prépare puis avance P16 sur l'image DEV sous portes OEM, licences, ressources et sûreté, et mets à jour GitHub.
