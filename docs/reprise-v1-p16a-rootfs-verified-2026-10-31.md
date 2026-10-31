# Reprise V1 — P16-A rootfs DEV vérifié sur WSL2 (31 octobre 2026)

**P16-K preuve complémentaire (31/10/2026) :** clone du dépôt cache `meta-openembedded` **shallow=true**, deux frontières répertoriées, `.git/shallow` présent ; HEAD local = distant = miroir public. L'échec de `merge-base` s'explique par l'historique Git partiel (hypothèse mécaniste cohérente, à confirmer par approfondissement ciblé). [Contrat de réparation bornée](per-p16ik-manifest-and-kas-pin-diagnosis-2026-10-31.md) préparé sans changement de gitlinks/SHAs, sans compilation ; P16-K non franchi à ce stade.


**Dernier diagnostic P16-K — 31/10/2026 :** HEAD local `origin/wrynose` = HEAD distant de `git.openembedded.org` = HEAD miroir public (`c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e`). Le pin `f28a144...` est ancêtre selon l'API publique, mais `COMMON_ANCESTOR=UNKNOWN` en local : branche locale non périmée, hypothèse de clone shallow/déficit d'historique à tester en lecture seule. [Détails](per-p16ik-manifest-and-kas-pin-diagnosis-2026-10-31.md). Ne pas re-pin ou forcer KAS ; P16-K toujours non levé.


**Complément P16-I/K (31/10/2026) :** contrôle ciblé du manifeste DEV réel **PASS** (1 manifeste, 1 334 paquets, aucun paquet `-dbg`). Le dépôt local KAS `meta-openembedded` possède le pin `f28a144...` et `origin/wrynose` mais `merge-base --is-ancestor` retourne **NO** ; la branche locale diverge de l'ascendance requise. Le miroir public GitHub atteste au contraire une branche `wrynose` **85 commits ahead, 0 behind** depuis ce pin. [Porte et diagnostic détaillés](per-p16ik-manifest-and-kas-pin-diagnosis-2026-10-31.md). Ne pas extrapoler à la branche distante exacte KAS tant que `git ls-remote` et les SHA locaux ne sont pas comparés. Aucun changement d'OEM ni nouveau build.


**Complément P16-W — 31 octobre 2026 :** l'opérateur a transmis la classification expurgée des **32 lignes WARNING** en 8 types : 28 liées aux buildpaths des paquets `-dbg` GStreamer, explicitement traitées comme avertissements dans la recette OEM épinglée, 2 sur `S` de recettes file-only utilisant directement `${UNPACKDIR}`, 1 cache sstate partagé, 1 absence de `CONFIG_TASK_IO_ACCOUNTING` sur hôte WSL2. [Dossier P16-W](per-p16w-rootfs-warning-classification-2026-10-31.md). Aucun nouveau défaut Kwipi démontré ; P16-K (KAS) et P16-I (manifeste global, services OEM, licences) encore ouverts. Cette classification n'efface pas la limitation des droits de redistribution ni le blocage des nouvelles constructions KAS.


## Constat et degré de preuve

**Porte franchie :** compilation du rootfs de développement et audit des fichiers réellement présents dans le système de fichiers Yocto, **localement sur WSL2**, à partir de preuves communiquées par l'opérateur. Ce résultat est distinct des tests de fixtures PC/CI, d'un artefact image amorçable et de tout test sur le robot.

1. Avant construction : P14B `bitbake_python_package_files_verified_only` (19 modules, archive `85c583b86f0c8b5c59e9a547762a223c7ab27dee016c3ec604141907b20b2245`), P15A-P `bitbake_p15a_package_files_verified_only` (3 fichiers et preset `disable`), WSL2 16 CPU, 30 Gio RAM disponible, 880 Gio disponibles sur disque partagé ; Yocto `1ee58387810cebb67ae0d634c351d95024483bce` ; source P15A-P `b5626a2cafabd0836e69685d18988360d3e86f18`.
2. Métadonnées avant construction : `P16_METADATA_GATE: PASS`, 11 contrôles réels `bitbake -e` DEV/shipping (machine `microduck-zero3`, 2 paquets Kwipi uniques en DEV et absents de shipping, OEM préservé, sonde non activée).
3. Construction sur hôte WSL2 : `bitbake -c rootfs microduck-image-dev`, 4515 tâches tentées, 2149 non réexécutées, toutes réussies, **32 avertissements à classifier** ; `P16_ROOTFS_EXIT_CODE=0`, journal local privé indépendant.
4. Première relecture après construction bloquée par `umask 077` ; seconde relecture KAS bloquée avant BitBake : `meta-openembedded/wrynose` ne contenait pas, selon KAS 5.2, le SHA épinglé `f28a144aa0a0ae05ca2ee91e1aef6aa05f6a12db`. **Pas de modification de pin**. Le contrôle a donc réutilisé directement, sans KAS ni compilation, les artefacts préexistants sous `build/tmp/work`.
5. Audit **positif réel** : un seul `rootfs`, un seul `microduck-image-dev-*.manifest` et un seul couple `.exit.txt`/`.log` réussi. Validateur `scripts/per_p16_dev_rootfs_audit.py` depuis le checkout local `p16-pr238@c46fa4acd5188afacb4e4fc011ff1b0b49504b23` : `P16_AUDIT_EXIT_CODE=0`, `status=existing_dev_rootfs_probe_and_package_manifest_checked_only`. **19 modules Python P14B vérifiés octet par octet** contre leur provenance, **3 fichiers P15A** conformes SHA-256, `probe_systemd_symlink_found=false`, paquets manifestés `kwipi-companion=0.2.0a1` et `kwipi-readonly-probe=0.1`.
6. Empreintes P15A-P sur le rootfs : `usr/libexec/kwipi/health_probe.py` : `11e48364630b2c063d173cd1884a19a886a2467ddead19af1636e072f24ccc21` ; unité `kwipi-readonly-probe.service` : `ed0c6cd92e2a76a0f687e8bf4b32a22be01a26decb47f70cb432f4eef22e5d9d` ; preset `98-kwipi-readonly-probe.preset` : `01a3df8c2b3bd1199c18e1ff126bc96ac818262014030beec792f463c8de8ba8`.

**Limites strictes :** ce validateur ne vérifie que ses fichiers et liens systemd contrôlés : `probe_systemd_symlink_found=false` ne prouve pas seul l'absence de toute activation par dépendances ou scripts post-installation. Aucun `do_image`/ext4/WIC vérifié, aucun RAUC/signature/installation/repli, aucun P17 final, runtime ou capteur/moteur 50 Hz/robot. `LICENSE=CLOSED`, `source_license_checked=false` : aucune permission de redistribution établie ; pas de livraison publique. `SupplementaryGroups=robot` n'est pas une ACL de RPC lecture seule.

## Prochain lot borné, sans compilation

**P16-W / Avertissements** : lire uniquement les 32 avertissements du journal WSL2 privé, les classifier par risque (fetch/licence/postinst/QA/signature/outils/réseau) et chercher tout avertissement de paquet, système de fichiers, recette ou script d'installation. Ne pas publier de chemins privés, secrets, environnement brut ni journal complet. Si un avertissement pertinent reste inexplicable : **STOP**. Pas de nouveau build pour obtenir les mêmes warnings.

**P16-K / Référence KAS** : déterminer de façon non destructive si le SHA `f28a144...` est bien absent de `wrynose` dans le dépôt local/amont et si la branche a avancé/réécrit son historique. Comparer avec le KAS Yocto OEM épinglé ; **ne pas changer le SHA, contourner le test, rebaser ou mettre à jour les sous-modules sans accord**. L'audit rootfs existant ne règle pas la reproductibilité du nouvel environnement.

**P16-I puis P17** : seulement si W/K et contrôle indépendant des services/politiques et droits sont satisfaisants, définir l'étape image DEV (image amorçable et analyses de contenu, données et repli), puis RAUC de **développement**, privé, signé, vérifié, sans installation robot. P17 est une qualification séparée, pas un résultat implicite de P16-A.

## Sources et état GitHub

Autorité : [plan d'action](plan-action.md), [protocole P16](per-p16-dev-rootfs-offline-audit-2026-10-31.md), [portes P15–P17](per-p15-p17-v1-release-gates-2026-10-31.md), [reprise P15A](reprise-v1-p15a-package-verified-2026-10-31.md). Source de ce bilan : sortie du shell WSL2 de l'opérateur, non accès distant à son disque ni CI sur une image. `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068` au dernier relevé ; #230 → #231 → #235 → #238 ouvertes en brouillon, non fusionnées. Les CI de fixtures P16 vérifient le code et non le robot. Les preuves privées restent sous `~/kwipi-build-v1/proofs` et ne doivent pas être publiées.
