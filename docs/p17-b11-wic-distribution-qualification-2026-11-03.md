# P17-S12 — Qualification statique des artefacts de distribution DEV B11 (03/11/2026)

> **État : PASS sur WSL2 (artefacts réels), non validé sur robot.** Cette note récapitule les sorties de l'opérateur, pas une CI ni une expérience sur RK3566. Le [plan directeur](plan-action.md) reste la source d'autorité.

## Références épinglées et séparation des générations

- Dépôt Microduck : `main@df95910f3c26dc0f1083b3c6fa70292560795e5a` au début de cette documentation, après [PR #276 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/276). Les preuves intermédiaires P17-S3 à S12 sont consignées dans les commentaires de cette PR, dont [S12](https://github.com/Jean-Philippe56520/Microduck/pull/276#issuecomment-6599616018).
- Checkout WSL2 B11 : `/home/jp/kwipi-build-b11/companion@659008ecf5d3a1eccd957e9ea2b1df4abaab21a1`, Yocto OEM épinglé `/home/jp/kwipi-build-b11/yocto@1ee58387810cebb67ae0d634c351d95024483bce`.
- Gitlinks `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` inchangés.
- **B10 historique** (`/home/jp/kwipi-build-v1`) distinct, préservé ; sa WIC ne contenait pas la nouvelle identité Kwipi dans `rootfs_a` et **ne doit pas** être présentée comme B11.
- **WIC B11 privée :** `/home/jp/kwipi-build-b11/build/tmp/deploy/images/microduck-zero3/microduck-image-dev-microduck-zero3.rootfs-20261103082641.wic` ; taille **12 968 805 376 octets** ; SHA-256 **`5c1d033962cdd19444192e4c06cd496f924531913ac0db3adb18278cc241d411`**.
- WIC compressée du même stem : **310 266 743 octets**, SHA-256 **`c2b727f7261589576889b72689165d91a5f57d61b6b78dda8e1156c50c38bc3f`**.
- Manifeste B11 préservé `microduck-image-dev-microduck-zero3.rootfs-20261102155642.manifest` : SHA-256 **`48acc8d7ce3b00c0ccfa355ca4247fe29859743918c5d0a9b67f83c1b858dc53`**.

## Preuves réalisées sur WSL2 (et limites exactes)

| Porte | Preuve positive | Limite restante |
| --- | --- | --- |
| B11 rootfs DEV | `bitbake -c rootfs` exit 0 rapporté ; 28 sources Python, 2 ELF AArch64, P15A désactivée, compte Kwipi non privilégié, manifeste et release contrôlés | Aucun démarrage ou capteur OEM |
| P17-S3 : WIC réelle | `bitbake -c image_wic microduck-image-dev` PASS ; WIC physique de 12 968 805 376 octets ; manifeste B11 inchangé | Pas une image shipping |
| P17-S4/S6 : GPT | 8 partitions OEM, table primaire et secondaire CRC corrects, tables miroir octet pour octet et LBA croisés | Ne prouve pas le chargeur et le noyau |
| P17-S5 : `rootfs_a` et `rootfs_b` | Ext4 montés en `ro,noload`, 28 fichiers Python identiques au rootfs B11, fichiers d'identité/sonde et binaires `robotd`/`mediad` B11 comparés | Ne constitue pas un audit de tous les fichiers, propriétaires et ACL des slots |
| P17-S7/S8 : `data` | Ext4 `ro,noload`, contenu initial `/var/lib/robot` identique hors `lost+found`, `network=0700:0:0`, `journal=2755:0:0`, démontage et détachement PASS | Pas de persistance après reboot physique |
| P17-S9/S11 : distribution | Dry-run `do_rootfs=0`, `do_package=0`, `do_image_wic=0` ; `bitbake microduck-image-dev` **6118 tâches toutes réussies** ; WIC et manifeste SHA préservés dans `DEPLOY_DIR_IMAGE` | Le stage `IMGDEPLOYDIR` n'est pas conservé après `do_image_complete` : ne plus y chercher la WIC |
| **P17-S12 : artefacts** | `P17_B11_ARTIFACTS_AND_ALIASES: PASS`, `P17_B11_BMAP_STRUCTURE: PASS`, `BMAP_MAPPED_BLOCKS: 263302`, `P17_B11_MANIFEST: PASS`, `P17_B11_COMPRESSED_SHA256: PASS`, `P17_B11_RAW_WIC_SHA256: PASS`, `P17_B11_ZST_EQUIVALENCE: PASS`, `P17_B11_DISTRIBUTION_INTEGRITY: PASS_READ_ONLY` | BMAP contrôlé **structurellement** : sommes éventuelles des plages de blocs non validées indépendamment ; aucun flash |

**Correction d'une fausse alerte :** après `do_image_complete`, le stage `deploy-microduck-image-dev-image-complete` a disparu, car le déploiement final relève du mécanisme `sstate` d'OE-Core. Le contrôle initial a échoué sur le chemin périmé (`STOP_WIC_SHA`), **sans perte ni altération** de la WIC ou du manifeste : leurs empreintes ont ensuite été revérifiées dans `build/tmp/deploy/images/microduck-zero3`.

**Correction d'un faux critère dans `data` :** le `rootfs` physique sous WSL2 présentait `network=700:1000:1000`, `journal=755:1000:1000`, alors que les métadonnées réellement **embarquées** sont `network=700:0:0` et `journal=2755:0:0`, conformes à `microduck-data.bb`. Ne pas exiger l'égalité stricte des UID/GID et modes de l'arbre de travail hôte et de l'ext4 construit sous fakeroot.

**Réemploi du validateur :** `scripts/per_p16_b2c_final_artifact_gate.py` conserve les constantes de la WIC **B10** (stem et SHA historiques) et un présupposé stage+final ; **ne pas l'exécuter tel quel sur B11**. Seule sa fonction `validate_bmap` (blob `1f27fa42bf0b1ab0adccf4c3a5f60eeeac9cc7f3`) a été réutilisée sans modification. La décompression ZSTD B11 a été validée indépendamment **en flux** avec `pipefail` et SHA-256 de la WIC brute ; aucun second fichier de 13 Go généré.

## Portes encore ouvertes et prochaine reprise

1. **Vérification en lecture seule des plages BMAP et de leurs éventuels checksums** via l'outil existant, avec comparaison indépendante de la WIC brute, sans flash ou modification du fichier. Établir si une preuve nouvelle est nécessaire ; refuser de déduire des checksums de blocs du seul XML structurel. Examiner aussi les fichiers ext4/tar finaux uniquement si un contrôle manque pour une décision concrète.
2. P17 inventaire **des RPM/scriptlets complets** (dont `microduck-daemon-devkey` et `microduck-daemon-padd`) et licences/redistribution, sans installation ni exécution de scripts sur l'hôte. Six RPM seulement avaient été revus au préalable.
3. RAUC : paire de signature privée DEV compatible avec la chaîne de confiance, bundle signé/vérifié, test de stratégie de repli/rollback sur environnement sûr puis robot ; **absent, en attente**, ne pas fabriquer de nouvelle CA ni activer de service.
4. P15/PER/OEM : runtime/ACL `mediad`, ressources RK3566 (RAM/RSS, température, 2 Hz vision sans nuire aux 50 Hz moteurs), sûreté moteur, perception et autonomie ; **en attente robot**. `robotd` reste l'unique pilote moteur.
5. **Image DEV seulement** : comporte le mode développement constructeur, y compris accès root de diagnostic ; **ne pas publier, flasher, qualifier shipping ni distribuer** comme une V1 finale.

**Critères préalables au prochain essai :** positif = nouvelle preuve manquante et reproductible, comparaison avec réemploi OEM, témoin négatif et arrêt fixé avant action ; STOP = SHA/manifestes incohérents, tentative de modifier la WIC, de signer avec des clés non maîtrisées, ou de confondre CI et robot. Aucun sous-module, ONNX, matériel, clé ou image ancienne à modifier sans accord. Prochaines modifications de Kwipi pourront reconstruire **une nouvelle release** sur cette architecture, sans présumer que les artefacts B11 reflètent du code ultérieur.
