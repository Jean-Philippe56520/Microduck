# P16 — contrôle hors ligne du rootfs DEV, sans construction (31/10/2026)

## Pré-enregistrement

**But :** inspecter une image DEV *réellement construite* avant toute proposition de RAUC ou P17. Aucun `do_rootfs`, signature, service cible ou test robot exécuté par ce lot. Branche empilée sur #235 → #231 → #230 ; `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068`. OEM `942e58e3`, Yocto `1ee58387`, OE `ae5a3010` ; gitlinks inchangés. Les SHA réels P15A-P sont ceux de `docs/reprise-v1-p15a-package-verified-2026-10-31.md`.

**Réemploi :** recettes OEM `microduck-image-dev.bb` et `microduck-image.bb`, bundle de développement `microduck-bundle.bb` (verity, `RAUC_SLOT_rootfs=microduck-image-dev`) et shipping séparé. Couche P14C et paquet P15A restent opt-in. Aucune nouvelle recette, daemon, caméra, socket ou permission motrice.

## Portes et arrêt

1. Avant toute nouvelle commande BitBake sur WSL2, consulter les preuves déjà conservées (`proofs/p14b-package.json`, `proofs/p15a-package-verify.json`) et vérifier les HEAD, sstate, disque, sources, droits `LICENSE=CLOSED` / `source_license_checked=false` et la présence des couches parentales. Une erreur, incompatibilité, manque de retour arrière, service activé ou contamination shipping = **STOP**.
2. Après autorisation et exécution réelle, séparée, de `do_rootfs microduck-image-dev`, collecter séparément le code de sortie **0**, `IMAGE_ROOTFS` et le véritable manifeste `microduck-image-dev-*.manifest` correspondant au même build. Ne pas fabriquer les chemins ni les extraire du chat ; aucune image n'existe dans GitHub pour ce contrôle.
3. Exécuter `python -m scripts.per_p16_dev_rootfs_audit --rootfs <chemin IMAGE_ROOTFS> --manifest <chemin image.manifest> --do-rootfs-exit 0 --source-head <SHA40 exact> --report <nouveau rapport privé>`. Les chemins doivent être les sorties réelles de la tâche. Le validateur refuse overwrite et toute anomalie dans ses fichiers contrôlés.
4. Le validateur vérifie la présence de 4 paquets, les 3 empreintes immuables P15A-P et l'absence de lien d'activation `kwipi-readonly-probe.service` dans les emplacements systemd contrôlés. Ce **n'est pas** un audit exhaustif des dépendances, des scripts post-install, de toutes les unités systemd ni de l'image shipping ; ces contrôles indépendants restent obligatoires.
5. **RAUC étape distincte**, jamais déduite du rootfs : contrôler `bitbake -e` des bundles dev/shipping, compatibilité `MACHINE`, hook install-check OEM, verity, paire de développement *hors dépôt*, `rauc info`/signature et repli A/B avant toute installation. L'image DEV OEM autorise root sans mot de passe : **jamais livraison shipping**.
6. P17 reste ensuite une qualification distincte : manifeste de provenance source/OEM/Yocto/paquets/image, comparaison shipping, démarrage/repli sur cible autorisée, ressources, journaux et permissions. Robot/NPU/50 Hz/locomotion non validés ; aucun essai robot avant réception et supervision.

**Résultat à l'ouverture :** validateur source-only et cas négatifs fixtures, `rootfs_built=false`, `rauc_signed=false`, `p17_validated=false`. Un validateur positif ultérieur ne prouve pas le démarrage ni la sûreté du service sur RK3566.
