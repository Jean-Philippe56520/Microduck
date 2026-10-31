# P16 — contrôle hors ligne du rootfs DEV, sans construction (31/10/2026)

**P16_METADATA_GATE — PASS, sortie WSL2 opérateur du 31/10/2026 :** onze contrôles positifs des véritables `bitbake -e` (DEV `PN=microduck-image-dev`, shipping `PN=microduck-image`, `MACHINE=microduck-zero3` dans les deux, `kwipi-companion` et `kwipi-readonly-probe` chacun une fois en DEV et absents en shipping, `microduck-daemon`/`microduck-data` présents des deux côtés, `SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe=disable`). Le script temporaire efface les trois sorties `bitbake -e` locales. GitHub #238 : quatre CI vertes sur `daf16ca80141850d9873fe85d03029b5184d1cd1` ([P16 fixtures](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41226714044)). **Autorisation technique limitée au test `bitbake -c rootfs microduck-image-dev` local privé, après préflight hôte confirmé et sans droits de redistribution présumés** ; aucune image créée à ce stade. Arrêt sur code différent de zéro, changement de source/couches/MACHINE/IMAGE_INSTALL, espace insuffisant, scripts inattendus ou problème de licence connu. Ne pas créer de RAUC, ne pas toucher shipping ni actionner de robot.


**Préflight WSL2 complémentaire transmis (31/10/2026) :** les cinq contrôles indépendants de rapport sont `OK` : P14B 19 fichiers, source identique, archive SHA-256 attendue, P15A 3 fichiers, preset `disable`. Les six entrées attendues existent (`yocto/kas/microduck.yml`, trois overlays KAS P13B2/P14B/P15A, `meta-kwipi`, `meta-kwipi-python`). `yocto@1ee58387810cebb67ae0d634c351d95024483bce`, 16 CPU, 30 Gio de RAM disponible, swap 8 Gio ; espace disponible partagé 880 Gio. Les deux chemins déclarés dans l'overlay P15A pointent vers `p15a-pr235/yocto/meta-kwipi-dev-image` et `p15a-pr235/yocto/meta-kwipi-p15-readonly`. **Preuve : affichage opérateur WSL2 ; pas un rapport CI ni une mesure cible.** Il reste avant `do_rootfs` la vérification effective sur l'hôte de `IMAGE_INSTALL` DEV/production, `MACHINE`, activation systemd et de la composition KAS complète. `LICENSE=CLOSED` et droit de redistribution P14B non levé : **construction pour usage privé de développement uniquement**, aucune distribution, signature/installation ou autorité moteur. Après ces contrôles et succès BitBake réels, auditer le rootfs puis reprendre RAUC/P17 séparément.


## Pré-enregistrement

**But :** inspecter une image DEV *réellement construite* avant toute proposition de RAUC ou P17. Aucun `do_rootfs`, signature, service cible ou test robot exécuté par ce lot. Branche empilée sur #235 → #231 → #230 ; `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068`. OEM `942e58e3`, Yocto `1ee58387`, OE `ae5a3010` ; gitlinks inchangés. Les SHA réels P15A-P sont ceux de `docs/reprise-v1-p15a-package-verified-2026-10-31.md`.

**Réemploi :** recettes OEM `microduck-image-dev.bb` et `microduck-image.bb`, bundle de développement `microduck-bundle.bb` (verity, `RAUC_SLOT_rootfs=microduck-image-dev`) et shipping séparé. Couche P14C et paquet P15A restent opt-in. Aucune nouvelle recette, daemon, caméra, socket ou permission motrice.

## Portes et arrêt

1. Avant toute nouvelle commande BitBake sur WSL2, consulter les preuves déjà conservées (`proofs/p14b-package.json`, `proofs/p15a-package-verify.json`) et vérifier les HEAD, sstate, disque, sources, droits `LICENSE=CLOSED` / `source_license_checked=false` et la présence des couches parentales. Une erreur, incompatibilité, manque de retour arrière, service activé ou contamination shipping = **STOP**.
2. Après autorisation et exécution réelle, séparée, de `do_rootfs microduck-image-dev`, collecter séparément le code de sortie **0**, `IMAGE_ROOTFS` et le véritable manifeste `microduck-image-dev-*.manifest` correspondant au même build. Ne pas fabriquer les chemins ni les extraire du chat ; aucune image n'existe dans GitHub pour ce contrôle.
3. Exécuter `python -m scripts.per_p16_dev_rootfs_audit --rootfs <chemin IMAGE_ROOTFS> --manifest <chemin image.manifest> --do-rootfs-exit 0 --source-head <SHA40 exact> --source-root <checkout Microduck au SHA exact> --report <nouveau rapport privé>`. Les chemins doivent être les sorties réelles de la tâche. Le validateur refuse overwrite et toute anomalie dans ses fichiers contrôlés.
4. Le validateur vérifie la présence de 4 paquets, les 19 fichiers Python P14B (comparés à l'archive reproductible au SHA-256 épinglé), les 3 empreintes immuables P15A-P et l'absence de lien d'activation `kwipi-readonly-probe.service` dans les emplacements systemd contrôlés. L'argument `--do-rootfs-exit 0` **ne prouve pas** que BitBake a réellement exécuté la tâche : le journal et la sortie de l'opérateur sont une attestation indépendante à joindre. Ce **n'est pas** un audit exhaustif des dépendances, des scripts post-install, de toutes les unités systemd ni de l'image shipping ; ces contrôles indépendants restent obligatoires.
5. **RAUC étape distincte**, jamais déduite du rootfs : contrôler `bitbake -e` des bundles dev/shipping, compatibilité `MACHINE`, hook install-check OEM, verity, paire de développement *hors dépôt*, `rauc info`/signature et repli A/B avant toute installation. L'image DEV OEM autorise root sans mot de passe : **jamais livraison shipping**.
6. P17 reste ensuite une qualification distincte : manifeste de provenance source/OEM/Yocto/paquets/image, comparaison shipping, démarrage/repli sur cible autorisée, ressources, journaux et permissions. Robot/NPU/50 Hz/locomotion non validés ; aucun essai robot avant réception et supervision.

**Résultat de la PR #238 (31/10/2026) :** 11 tests de fixtures P16 verts sur CI [#41225584674](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41225584674) après réparation d'un manifeste de fixture ; le contrôle de provenance des 19 sources est intégré, mais non exécuté sur rootfs WSL2 réel. Les scripts ne lancent jamais BitBake. `rootfs_built=false`, `rauc_signed=false`, `p17_validated=false`. Un validateur positif ultérieur ne prouve pas le démarrage ni la sûreté du service sur RK3566.

## Démarche WSL2 opérateur, après préflight et autorisation du lot image

La présente PR **ne lance aucune de ces commandes**, et n'atteste pas le disque ni l'état du PC de l'opérateur. Réutiliser les preuves et caches WSL2 existants, sans reconstruire P13B2/P14B/P15A. Contrôler d'abord les HEAD #230/#231/#235/#238, les SHA OEM, l'espace hôte et les cinq fichiers source P15A. Garder le manifeste de sortie de BitBake privé. Les fichiers `yocto/kas/*.yml` combinés doivent résider dans le même dépôt Yocto, comme indiqué dans le dossier de reprise. Ne pas utiliser `scripts/build-local.sh` qui peut sélectionner une version constructeur différente.

Après un **do_rootfs DEV** explicitement autorisé et terminé avec code retour 0, obtenir ses chemins effectifs **dans le même environnement BitBake** : `IMAGE_ROOTFS`, `IMAGE_MANIFEST`, `MACHINE`, `TMPDIR`, `IMAGE_INSTALL` (DEV et production), plutôt que deviner des chemins dans le shell. Ne pas publier la sortie brute de `bitbake -e`. Archiver séparément journal de l'exécution `do_rootfs`, code retour, provenance des couches et rapport de contrôle.

Puis, dans le checkout complet de la branche P16 au SHA exact, le paquet Python et les fichiers de la sonde seront comparés aux empreintes locales :

```sh
python -m scripts.per_p16_dev_rootfs_audit \
  --rootfs "$IMAGE_ROOTFS" \
  --manifest "$IMAGE_MANIFEST" \
  --do-rootfs-exit 0 \
  --source-root "$P16_SOURCE_CHECKOUT" \
  --source-head "$(git -C "$P16_SOURCE_CHECKOUT" rev-parse HEAD)" \
  --report "$P16_PRIVATE_REPORT"
```

Ces variables sont des **emplacements à résoudre par une vérification préalable** et non des variables inventées ou garanties dans le shell. Sans valeurs effectives, preuve d'exécution, espace hôte, licence et retour arrière, **STOP** ; ne pas lancer `do_rootfs`, RAUC ou P17. La sonde reste sans activation et son groupe Unix `robot` ne constitue pas une ACL lecture-seule.

## Porte hôte WSL2 partiellement vérifiée, 31/10/2026

Sortie opérateur communiquée après P15A-P : `proofs/p14b-package.json` = `bitbake_python_package_files_verified_only`, `proofs/p15a-package-verify.json` = `bitbake_p15a_package_files_verified_only`, checkout `p15a-pr235` = `b5626a2cafabd0836e69685d18988360d3e86f18`. `df -h build downloads sstate` renvoie pour les trois chemins le même support `/dev/sdd`, 1007 Gio de capacité, 77 Gio occupés et **880 Gio disponibles**. Budget préenregistré sur volume partagé = 290 Gio, donc **porte disque satisfaite au moment de la mesure** (pas une garantie de ressources au terme de la construction).

Cette sortie ne vérifie pas le contenu JSON complet, la RAM/CPU actuels, le SHA du checkout Yocto, les quatre couches KAS effectives, `IMAGE_INSTALL` DEV vs shipping, les licences et les conditions de retour arrière. **La porte complète P16 `do_rootfs` reste en attente**, et aucune commande `bitbake -c rootfs` n'a été attestée. Le validateur P16 présente désormais **13/13 tests fixtures** et la [CI spécialisée #41225751042](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41225751042) verte sur `ef89d48274ad229b88022872a25356b375681e6a` ; CI Python générale, P15A et N1 également vertes au même HEAD. Cela ne remplace pas la preuve hôte.
