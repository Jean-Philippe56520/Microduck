# P13B6 WSL2 terminé et P16-A/B10 prêt pour qualification hors ligne (01/11/2026)

**Qualification de l'unique WARNING P13B6 (preuve opérateur, 01/11/2026) :** le texte exact de 128 caractères correspond à l'avertissement OpenEmbedded `The Linux kernel on your build host was not configured to provide process I/O statistics. (CONFIG_TASK_IO_ACCOUNTING is not set)` ; SHA-256 du message seul `f91ed3723f631e73efb0af5ff679f6b020ad4bf43386a4b4e9a5daa33265290a`. Cela concerne `buildstats`/les statistiques I/O des processus **de l'hôte Linux**, pas le contenu du RPM, l'OS Yocto cible, la caméra ou les moteurs. **P13B6 : avertissement identifié, non bloquant pour les preuves de paquet et de tâches observées ; aucune modification du noyau WSL2 ni de réglage de sécurité.** L'absence de mesures `buildstats` I/O détaillées reste une limite, et un futur rootfs devra être qualifié séparément. Source externe historique : https://docs.yoctoproject.org/pipermail/yocto/2017-September/038136.html ; source OpenEmbedded `buildstats.bbclass`.

## Autorité et faits vérifiés

Base GitHub de travail : `main@c13e490b86dec1d3a9f02b86cb3e17876330611f`, PR #260 fusionnée après 5/5 CI vertes. Gitlinks constructeur préservés : `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` ; Yocto de l'opérateur `1ee58387810cebb67ae0d634c351d95024483bce`. Source des paquets B12 / P14B / B6 : `e2e9bfef7d7c4f46fe51924937e7939d78d00383`. Aucun gitlink ni fournisseur B12 n'a été modifié.

**Preuves opérateur WSL2 (pas GitHub CI, pas robot)** :

- `bitbake -c package_write_rpm kwipi-passive-fixture` réel a terminé avec `EXIT_0` (un seul lancement autorisé). `PKGDEST` B6 : cinq modules et SHA-256 égaux aux sources. Trois RPM distincts attendus : principal `kwipi-passive-fixture-0.1.0-r0.noarch.rpm` 21 458 octets, `-dbg`, `-dev`. Principal : en-tête 5 fichiers, dépendance `kwipi-companion`, aucun scriptlet ; cinq FILEDIGESTS SHA-256 conformes.
- Le problème `rpm2cpio` exit 127 provenait de l'environnement des bibliothèques natives, pas d'une corruption démontrée du RPM. Les bibliothèques `libarchive.so.13.8.7` et `libbz2.so.1.0.8` sont déjà dans les sysroots Yocto ; aucun outil n'a été installé ni recompilé.
- Le lanceur `rpm2cpio` résout `rpm2cpio.real -> rpm2archive -> rpm2archive.real`. Avec `LD_LIBRARY_PATH` limité au processus, conversion exit 0 ; sortie **GZIP contenant une archive TAR** (pas CPIO brut), 20 480 octets. Lecture TAR directement en mémoire : cinq fichiers réguliers exactement, zéro fichier supplémentaire, cinq SHA-256 identiques aux sources B12 et PKGDEST. `P13B6_PAYLOAD: PASS_5_OF_5`, sans écriture ni extraction sur disque. Les permissions détaillées des membres TAR n'ont pas été auditées séparément.
- Journal BitBake réel privé : 10 386 octets, SHA-256 `53c906be7c5bf91a707c86dd236a69373f5eb59474d8270d2799293b41560292`, 117 lignes ; 23 tâches `Running task` reconnues, aucune ligne non analysée, une tâche B6 `do_package_write_rpm`, aucune tâche `microduck-daemon:do_compile/do_package/do_install`, `do_rootfs`, `do_image` ou autre déploiement repérée. 0 ERROR/FATAL, résumé `all succeeded`, **1 WARNING identifié comme manque de statistiques I/O du noyau hôte**. `P13B6_REAL_LOG: PASS_TASK_SET`. Cette lecture filtrée ne certifie pas les événements absents du journal ni le caractère bénin de l'avertissement.

**Décision P13B6** : preuve suffisante pour **le payload du RPM principal** et **le jeu de tâches visible du journal réel** ; signature RPM, authentification cryptographique de release, installation dans un rootfs B10 et runtime OEM demeurent **non validés**. Ne pas relancer le package ni modifier les caches. Ne publier ni journal brut ni environnement BitBake complet.

## Nouveau chantier P16-A/B10 : objectif et écart

**Résultat utile** : avant de qualifier toute nouvelle image DEV, exiger la présence **exacte de 24 modules Python installés** (P14B 19 + B6 5), les deux ELF64 AArch64 B12 attendus et la release `current` correcte, le compte `kwipi` non privilégié et la sonde P15A désactivée. Il s'agit d'une **porte documentaire et de contrôle post-hoc**, pas d'une capacité de robot.

**Manque prouvé** : `scripts/per_p16_dev_rootfs_audit.py` historique exige deux paquets Kwipi et 19 modules ; `scripts/per_p16_dev_rootfs_service_gate.py` acceptait uniquement un rapport 19. Ces scripts **ne peuvent pas** qualifier le nouveau B10, et l'ancien rootfs DEV inspecté conserve la release `...3406fee5428c` au lieu de B12.

**Réutiliser / adapter / créer** :

- Réutiliser les listes et sources déterministes P14B, B6, `per_p16_dev_rootfs_audit` (`_under`, manifestes, SHA P15A), la porte `per_p15b9_rootfs_identity_gate.verify_rootfs` (identité/preset et liens systemd), les empreintes B12 déjà mesurées, ainsi que le contrôle de sélection DEV/shipping `per_p15b10_dev_passive_env_gate`.
- **Créer** un petit auditeur distinct `scripts/per_p16b10_dev_rootfs_audit.py` pour conserver l'ancien P16-A et refuser un rootfs obsolète. **Adapter** uniquement P16-S1 à son rapport B10, sans modifier son contrôle des unités/autostarts.
- Aucun paquet, bibliothèque, modèle, ACL, service, pilote ni sous-module tiers n'est introduit. Les sources CLOSED ne sont pas déclarées redistribuables.

## Contrôles du candidat (non exécutés sur rootfs B10)

1. Entrées obligatoires : rootfs DEV **déjà existant**, manifeste DEV explicitement fourni, `--do-rootfs-exit 0` **déclaré par l'opérateur**, checkout source B12 `e2e9bfef...`. La déclaration `--do-rootfs-exit` ne prouve pas l'exécution elle-même.
2. Manifeste : trois paquets Kwipi `kwipi-companion`, `kwipi-passive-fixture`, `kwipi-readonly-probe` et les deux paquets OEM `microduck-daemon` / `microduck-data`. Refus d'un Kwipi supplémentaire, de B6 manquant, d'un manifeste shipping ou d'une version B12 erronée. **L'association entre le manifeste et le rootfs n'est pas attestée indépendamment**.
3. Sources P14B/B6 : préservation de l'archive P14B épinglée, des SHA connus B6, des 19 SHA de base cohérents et du SHA git B12. Installation `usr/lib/python3.14/site-packages/microduck_companion` : 24 fichiers `.py` exacts, mode `0644` et hash par fichier ; refus de lien, fichier supplémentaire, `.pyc` non contrôlé ou dérive de source. **Un éventuel bytecode légitime généré par Yocto devra faire l'objet d'un audit séparé ; STOP plutôt qu'un PASS trompeur.**
4. OEM : `mediad` 11 160 240 octets SHA-256 `2e1319a17072f0c4a7ae1594a785aa987873d15e01d50a435b6772c873c99c1f` ; `robotd` 6 435 872 octets SHA-256 `0aa212501839d766d7f138bae25db85949b8eb7a1dac72d70cd7d8db147982dc`. Exiger ELF64 little-endian AArch64, exécutable et `current -> releases/0.17.8+kwipi.p12.e2e9bfef7d7c`. Pas de commande motrice.
5. P15A/P15-B9 : trois fichiers hachés, preset `disable`, aucun lien d'activation, compte Kwipi isolé, non-root, verrouillé, sans groupe moteur, opérateur `microduck` préservé. P16-S1 fait une analyse complémentaire des références systemd et postinst **dans les chemins vérifiés**, sans prouver runtime, ACL réelle ou sécurité au boot.
6. **Shipping** : le contrôle post-hoc d'un rootfs DEV ne peut **pas** prouver l'image shipping. Avant une future construction, refaire distinctement les portes P13B5/P15-B10 sur les métadonnées effectives DEV **et shipping** pour prouver 1 sélection DEV, 0 sélection shipping, compte DEV-only et P15A désactivée. L'auditeur retourne délibérément `shipping_image_checked=false` et `dev_shipping_effective_metadata_rechecked_by_this_gate=false`.

**Positif préenregistré** : fixtures de 24 modules, B12 contrôlé par ses octets/empreintes (pas une signature release), compte non privilégié et sonde inactive produisent un rapport explicite *files-only*. **Négatifs obligatoires** : module absent/supplémentaire/modifié/liens, provenance différente, mauvais ELF, ancien `current`, mauvais manifeste/B6 absent/version OEM, compte dans groupe `robot`, P15A activée, rapport P16-S1 incomplet, build exit non zéro. STOP au premier écart, pas d'assouplissement ni nouvelle construction automatique.

**Reste inconnu** : résultat de tests CI au SHA du candidat avant leur exécution, véritable rootfs B10, installation sur microduck-zero3, démarrage ou ressources du robot RK3566, température/RSS/CPU, caméra/NPU, sockets ACL, WIC, RAUC, signature et licences de redistribution. Une CI verte ne change pas ces inconnues.

## Prochaine autorisation distincte

1. CI vertes au SHA candidat, revue des tests négatifs et du contrat OEM ; aucun sous-module changé.
2. Sur WSL2, **lecture seule** de la composition KAS déjà conservée, des fichiers/sstate/versions B12 et B6 et revalidation des sélections DEV/shipping ; classifier l'avertissement du journal P13B6 sans imprimer le contenu privé.
3. **Seulement ensuite** décider explicitement si une unique tâche `bitbake -c rootfs microduck-image-dev` est nécessaire et sans reconstruction B12 inattendue. Budget et espace disques, validation des tâches planifiées et témoins fixés avant l'exécution.
4. Contrôle post-hoc B10 du nouveau rootfs, puis P16-S1 selon les preuves obtenues. **Pas de WIC, RAUC, firmware signé, robot ou mouvement** dans ce lot ; retour arrière : aucune tâche build exécutée, abandon du candidat et conservation des artefacts existants.
