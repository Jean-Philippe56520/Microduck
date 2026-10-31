# Reprise V1 — P16-A rootfs DEV vérifié sur WSL2 (31 octobre 2026)

## Reprise P16-IMAGE-B1c — WIC DEV vérifiée sur vrai WSL2, B2a ensuite (31 octobre 2026)

**Preuve opérateur réelle, à conserver et ne pas relancer :** après checkout de #238 au commit `3af5314a36c75208dde9c96d3adac06fa6183e5d`, `scripts/per_p16_b1b_wic_artifact_gate.py` a rapporté `WIC_MATCHES: 2` pour une WIC régulière `microduck-image-dev-microduck-zero3.rootfs-20261031195334.wic` et son alias `microduck-image-dev-microduck-zero3.rootfs.wic`. Une seule cible physique ; taille `12968805376` octets ; GPT principal 8 partitions avec offsets/tailles OEM, CRC header/table conformes, `P16_B1B_STAGE_GPT: PASS`. SHA-256 réel `c1140e7508559ebc9467c3f97d3c9891452228f05b3baf999ccaa3c0a5f11bc8`, `P16_B1B_SHA256: PASS`. **La sortie `WIC absente ou multiple` d'avant est un faux positif de la cardinalité** et ne doit plus être traitée comme échec de BitBake. Tout cela reste une preuve WSL2 transmise par l'opérateur, sans accès direct à son disque depuis l'assistant. Aucune nouvelle compilation nécessaire pour recommencer ces contrôles.

**Étape suivante P16-IMAGE-B2a** : relecture **dry-run seule** de `bitbake -n -c image_complete microduck-image-dev` avec les quatre fichiers KAS/caches épinglés et journal privé neuf. Contrôler que les conversions OEM `wic.zst`, `wic.bmap`, `wic.zst.sha256sum` sont prévues sans `do_rootfs` ni recompilation cible, puis autoriser B2b privé uniquement si le log est conforme. Ne pas lancer `do_image_complete` réel sans ce contrôle ; ne pas inventer la présence des artefacts, d'un boot robot ou de signatures. [Dossier B2a](per-p16-dev-rootfs-offline-audit-2026-10-31.md#p16-image-b1c--validation-reelle-de-la-wic-brute-et-preparation-b2a-31-octobre-2026).


## Reprise après B1b : validateur de fichier WIC testé sur fixtures (31 octobre 2026)

`do_image_wic` a terminé avec code 0 sur WSL2, mais le contrôleur initial attendait `len(glob('*.wic'))==1` et a affiché `WIC absente ou multiple`. Le constructeur OE-core épinglé peut créer un alias `IMAGE_LINK_NAME.wic`. La PR #238 possède désormais `scripts/per_p16_b1b_wic_artifact_gate.py`, testé 9/9 sur images creuses synthétiques. Il **recherche sans modifier** le seul fichier physique (alias tolérés), vérifie huit partitions GPT et les CRC, calcule SHA-256 une fois ces vérifications réussies. **Aucun résultat WSL2 réel n'a encore été obtenu avec ce code**. Si `P16_B1B_AUDIT_STOP`, conserver la sortie et ne pas reconstruire.

Après récupération de #238, exécuter depuis `~/kwipi-build-v1` : `PYTHONDONTWRITEBYTECODE=1 python3 p16-pr238/scripts/per_p16_b1b_wic_artifact_gate.py` ; voir [P16-B1c](per-p16-dev-rootfs-offline-audit-2026-10-31.md#p16-image-b1c--correctif-de-verification-des-artefacts-sans-reconstruction-31-octobre-2026). Ne jamais joindre la WIC ou les données privées. `do_image_complete` et la qualification de l'image publiée/RAUC/robot restent séparés.


## Reprise P16-IMAGE-B1b — do_image_wic WSL2 réussi, garde d'artefact STOP (31 octobre 2026)

**Nouvelle preuve opérateur** : `P16_B1B_PREFLIGHT: PASS` (850,1 Gio), `P16_B1B_EXIT_CODE=0`, `microduck-image-dev:do_image_wic: Succeeded`, `Attempted 5683 tasks of which 4515 didn't need to be rerun and all succeeded`, deux warnings connus. L'étape Python suivante s'est arrêtée sur `P16_B1B_STOP: WIC absente ou multiple` parce qu'elle exigeait `len(list(glob('*.wic'))) == 1`, sans distinguer fichier régulier et lien symbolique. Le code OE-core épinglé prévoit `IMAGE_LINK_NAME.wic` → `IMAGE_NAME.wic` si l'alias est activé. **C'est une hypothèse de faux positif, pas encore une preuve du fichier réel.** Ne pas relancer ni WIC ni rootfs, ne pas nettoyer les caches.

**Prochaine preuve** : sous le seul WORKDIR de `microduck-image-dev`, inventorier de manière bornée les `*.wic` dans `deploy-microduck-image-dev-image-complete`, et contrôler l'emplacement final si nécessaire, ainsi que les liens/cibles ; ensuite taille/GPT/SHA-256 en lecture seule. Le retour `do_image_wic` n'est pas à lui seul une attestation de partitionnement ou de démarrage ; **ni RAUC, ni production ni robot**. [Autorité P16](per-p16-dev-rootfs-offline-audit-2026-10-31.md#p16-image-b1b--tache-wic-reelle-reussie-controle-de-cardinalite-a-corriger-31-octobre-2026).


## Reprise après revue complète P16-IMAGE-B1a (31 octobre 2026)

La sortie opérateur du journal dry-run existant donne `TOTAL_TASKS=5683`, `ALREADY_UP_TO_DATE=4515`, `REMAINING_TASKS=1168`, `TASK_LINES_PARSED=1166`, `NATIVE_FETCH=5`, `NATIVE_COMPILE=5`, `STRICT_DO_ROOTFS=0` et quatre seules opérations cible `do_deploy` (`u-boot-rockchip`, `linux-rockchip`, `grub-efi`, `systemd-boot`). La sortie `P16_B1_GATE: STOP_REVIEW_TARGET_TASKS` vient du prédicat conservateur, **pas d'un échec de BitBake**. La source OE-core `ae5a301...` confirme `WKS_FILE_DEPENDS_BOOTLOADERS:aarch64 = "grub-efi systemd-boot"` et `do_image_wic[recrdeptask] += "do_deploy"`; WKS OEM utilise U-Boot, pas EFI. Les deux dépendances EFI génériques ne sont pas des preuves d'une mauvaise image. Aucun paquet cible ou rootfs ne doit être recompilé à la main.

**Décision opérationnelle :** un essai B1b `bitbake -c image_wic microduck-image-dev` privé, borné et journalisé peut être effectué dans le même KAS/pins et caches si espace >=100 Gio et aucun .wic DEV antérieur ; stop sur toute divergence, aucun retry automatique. `image_types_wic.bbclass` produit d'abord `IMGDEPLOYDIR/${IMAGE_NAME}.wic`, et la tâche distincte `do_image_complete` expose ensuite l'artefact final dans `tmp/deploy/images`; une réussite de B1b ne valide donc pas bmap/zst ni amorçage. Voir [protocole source/critères](per-p16-dev-rootfs-offline-audit-2026-10-31.md#p16-image-b1a--quatre-do_deploy-expliques-par-openembedded-epingle--b1b-autorise-sous-conditions-31102026). P16-A/W/I/K/PF1/S1/S2 ne sont pas à rejouer ; PR #238 draft, non fusionnée ; pas de signature RAUC, robot, licence de diffusion.


## Reprise après P16-S2 PASS WSL2 (31 octobre 2026)

**Preuve opérateur réelle, à ne pas répéter :** checkout `p16-pr238@0bbe7658deaf2a3e8c43bb9eea8c97b9690e3966`, script S2 lecture seule sur le rootfs DEV : statut `p16_s2_rauc_pinned_ca_and_rootfs_mode_gate_pass`, 2/2 CA OEM RAUC, 11/11 paramètres, cinq fichiers inspectés pour bits de permission dangereux, groupe Unix `robot` présent. Les 4 workflows GitHub Actions étaient verts sur ce commit. `image_built=false`, `rauc_bundle_signed_verified=false`, `robot_validated=false`, permissions RPC lecture seule et UID/GID cibles non attestés ; licences et scriptlets postinst exhaustifs non validés.

**Prochaine action concrète P16-IMAGE-B1a :** dry-run de `bitbake -n -c image_wic microduck-image-dev` depuis le KAS OEM + overlays locaux P13B2/P14B/P15A déjà vérifiés. Ne pas construire WIC tant que le plan réel des tâches et l'absence de reconstruction de `do_rootfs`/`do_compile` non nécessaire ne sont pas lus. Aucun flash ni signature RAUC, image DEV strictement privée, notes/rollback dans le [protocole B1](per-p16-dev-rootfs-offline-audit-2026-10-31.md#p16-image-b1--plan-de-construction-wic-dev-privee-porte-de-planification-uniquement-31102026). Pas de nouvel outil, pas de sous-module modifié.


## Reprise P16-S1 — validations WSL2 ajoutées (31 octobre 2026)

**Entrées opérateur :** `p16-pr238@92985a0bcd787b7ad05254439c8f356b4853beec`, valideur de schéma WIC constructeur `layout ok` (12,08 Gio), et contrôle P16-S1 sur vrai rootfs : rapport P16-A réexaminé, 3 SHA P15A, 226 autres fichiers systemd, 17 presets, 0 référence de démarrage suspecte, 0 script différé dans les emplacements connus. Statut exact `p16_s1_no_observed_probe_autostart_references_in_scanned_rootfs` ; `image_built=false`, `robot_validated=false`. Aucun nouveau build exécuté. Les lignes `command not found` concernent uniquement le collage de l'exemple JSON dans Bash après les deux validations, pas les tests.

**Reprise après S1 :** contrôler les effets de post-installation des paquets, la keyring/config RAUC DEV réellement installées et les droits du service, sans activation, démarrage, `do_rootfs` ou modification de configuration. Le groupe Unix `robot` demeure un privilège étendu au niveau OS ; autorisation de déploiement non acquise. Ensuite seulement envisager `do_image`/WIC privée dans un lot séparé. [Dossier P16](per-p16-dev-rootfs-offline-audit-2026-10-31.md).


## P16-IMAGE-PF1 — résultat WSL2 corrigé : PASS (31 octobre 2026)

**Preuve opérateur transmise après réinitialisation de conversation :** commande de préflight exacte de la section historique ci-dessous, exécutée depuis `~/kwipi-build-v1`. Sortie : `DISK_FREE_GIB: 850.2`, `YOCTO_PIN: PASS`, `P15A_PIN: PASS`, `PROBE_SECTION_CHECK: PASS (comment ignored; no actual [Install])`, `PROBE_DISABLED_PRESET: PASS`, `P16_IMAGE_PREFLIGHT: PASS`, `IMAGE_BUILT: False`. Il ne s'agit pas d'un résultat GitHub Actions ni d'un accès direct au stockage WSL2 par l'assistant. **Le STOP lié au commentaire `[Install]` est levé** ; l'espace libre dépasse le seuil préenregistré de 100 Gio. P16-A/W/I/K conservent leurs preuves, sans nouvelle recompilation ni modification des SHA ou gitlinks.

**Décision :** préflight clos dans ce périmètre uniquement. Avant `do_image`/WIC : auditer le contenu effectif du rootfs (références et activations systemd, presets, permissions, scripts post-installation et composants de confiance), vérifier le schéma WIC avec le validateur constructeur, puis fixer critères d'arrêt et inspection des artefacts. `IMAGE_BUILT: False` : aucun `do_image`, bundle RAUC signé/vérifié, P17, diffusion ou robot validé. L'image DEV possède un login root sans mot de passe et ne doit pas être distribuée.


## P16-IMAGE-PF1 — arrêt faux positif du préflight WIC, 31 octobre 2026

**Dernier résultat opérateur : `P16_IMAGE_STOP: unite avec section Install`.** Cela vient **du contrôle ad hoc transmis dans le chat**, et non d'un changement du rootfs. Le code fautif utilisait `if "[Install]" in unit.read_text():` ; l'unité **constructeur Companion P15A** contient précisément le commentaire `# PER-P15A: deliberately no [Install] / WantedBy; manual DEV probe only.`. Cette mention ne constitue pas une section systemd. Le vrai template a uniquement `[Unit]` et `[Service]`, la recette `kwipi-readonly-probe_0.1.bb` déclare `SYSTEMD_AUTO_ENABLE:${PN} = "disable"`, et l'audit réel P16-A a déjà vérifié l'empreinte exacte de cette unité (`ed0c6cd92e2a76a0f687e8bf4b32a22be01a26decb47f70cb432f4eef22e5d9d`) et l'absence des liens d'activation dans son périmètre.

**Correction** : détecter uniquement une vraie ligne de section `[Install]` par `re.fullmatch(r"[ \t]*\[Install\][ \t]*", line)` sur les lignes du fichier. Ce motif ignore les lignes commentées et les mentions au milieu de valeurs ; un vrai `[Install]` est refusé. **Essais PC synthétiques positifs/négatifs : 5/5** (commentaire source, section réelle, entête commentée, section indentée, mention dans `Description`), sans preuve d'une nouvelle exécution du préflight dans WSL2.

**Décision** : **ne pas toucher au service, au rootfs, au validateur P16, ni à la recette OEM ; ne pas relancer BitBake/KAS/git fetch**. Le `P16_IMAGE_PREFLIGHT: PASS` reste **en attente** parce que le script s'est arrêté avant le calcul de l'espace libre et des messages de succès. Préflight limité à la prochaine WIC **DEV privée**, pas une autorisation de `do_image`/RAUC, de diffusion ni d'installation robot. Éviter de publier le journal privé, les clés ou l'image DEV (accès root sans mot de passe, CA et clé de développement).

### Commande de reprise, Ubuntu WSL2 uniquement (lecture seule ; aucune génération d'image)

```bash
cd ~/kwipi-build-v1 || exit 1
python3 - <<'PY'
from pathlib import Path
import hashlib, json, re, shutil, subprocess

base = Path.cwd()
def stop(s):
    raise SystemExit('P16_IMAGE_STOP: ' + s)

pins = {
    'yocto': '1ee58387810cebb67ae0d634c351d95024483bce',
    'p15a-pr235': 'b5626a2cafabd0836e69685d18988360d3e86f18',
}
for d, sha in pins.items():
    got = subprocess.check_output(
        ['git', '-C', str(base / d), 'rev-parse', 'HEAD'], text=True
    ).strip()
    if got != sha:
        stop(d + ' SHA changed')

roots = [p for p in (base / 'build/tmp/work').glob(
    '*/microduck-image-dev/*/rootfs') if p.is_dir() and not p.is_symlink()]
if len(roots) != 1:
    stop('rootfs absent or ambiguous')
root = roots[0]
report_path = base / 'proofs/p16-rootfs-audit.json'
if not report_path.is_file() or report_path.is_symlink():
    stop('validated P16 report missing')
data = json.loads(report_path.read_text())
if (data.get('status') != 'existing_dev_rootfs_probe_and_package_manifest_checked_only'
    or data.get('python_modules_verified') != 19
    or len(data.get('probe_sha256', {})) != 3
    or data.get('probe_systemd_symlink_found') is not False):
    stop('P16-A report not conforming')

paths = {
    'usr/lib/systemd/system/kwipi-readonly-probe.service':
        'ed0c6cd92e2a76a0f687e8bf4b32a22be01a26decb47f70cb432f4eef22e5d9d',
    'usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset':
        '01a3df8c2b3bd1199c18e1ff126bc96ac818262014030beec792f463c8de8ba8',
}
for rel, expected in paths.items():
    p = root / rel
    if not p.is_file() or p.is_symlink():
        stop('missing/symlinked file: ' + rel)
    if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        stop('installed file hash drift: ' + rel)
    if data['probe_sha256'].get(rel) != expected:
        stop('P16-A proof hash drift: ' + rel)

unit = (root / 'usr/lib/systemd/system/kwipi-readonly-probe.service').read_text()
if any(re.fullmatch(r'[ \t]*\[Install\][ \t]*', line) for line in unit.splitlines()):
    stop('actual [Install] section exists')
preset = (root / 'usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset').read_text()
if preset.strip() != 'disable kwipi-readonly-probe.service':
    stop('unexpected systemd preset')

free_gib = shutil.disk_usage(base / 'build').free / (1024 ** 3)
print('DISK_FREE_GIB:', round(free_gib, 1))
if free_gib < 100:
    stop('insufficient space')
print('YOCTO_PIN: PASS')
print('P15A_PIN: PASS')
print('PROBE_SECTION_CHECK: PASS (comment ignored; no actual [Install])')
print('PROBE_DISABLED_PRESET: PASS')
print('P16_IMAGE_PREFLIGHT: PASS')
print('IMAGE_BUILT: False')
PY
```

**Succès** : sortie `P16_IMAGE_PREFLIGHT: PASS`, SHA toujours épinglés, aucun nouvel artefact image. **Arrêt** : n'importe quel `P16_IMAGE_STOP` ; ne pas éditer le service ou relancer une compilation pour satisfaire le garde. L'exécution du script corrigé sur WSL2 n'est **pas encore rapportée**. Avant WIC : examen séparé de post-installation/permissions/systemd OEM, image DEV strictement privée, borne stockage/temps, et critères de succès/retour arrière. La WIC et RAUC restent des jalons distincts.


**Reprise au 31/10/2026, 20:13 — P16-K FERMÉ (métadonnées KAS validées).** Sortie opérateur réelle après un approfondissement ciblé de 128 commits : KAS 5.2 sélectionne correctement `openembedded-core@ae5a3010`, `bitbake@6e260eb6`, `meta-yocto@79b6d870`, `meta-openembedded@f28a144a`, `meta-rockchip@f2fa9fd1` et `meta-rauc@38da0e58`; `bitbake -e microduck-image-dev >/dev/null` passe, `P16_K_KAS_METADATA: PASS`. Git HEAD `yocto@1ee58387810cebb67ae0d634c351d95024483bce` et `p15a-pr235@b5626a2cafabd0836e69685d18988360d3e86f18` conservés. [Dossier complet](per-p16ik-manifest-and-kas-pin-diagnosis-2026-10-31.md). **Historique** : toutes mentions « KAS reste à vérifier » qui suivent précèdent ce nouveau résultat. P16-A/W/I/K acquis à leurs niveaux WSL2, pas de génération WIC, RAUC/P17, installation, robot ni droit de redistribution.


**P16-K — résultat réparation, 31/10/2026 :** cache Git local `meta-openembedded` approfondi une fois de 128 commits ; `P16_K_FETCH_EXIT_CODE=0`, `P16_K_ANCESTRY=PASS`, `HEAD_UNCHANGED=True`, `OEM_PIN_UNCHANGED=True`, `WORKTREE_UNCHANGED=True`. Copie privée des frontières `proofs/p16k-history-1mkm0nkt`. [Dossier P16-K](per-p16ik-manifest-and-kas-pin-diagnosis-2026-10-31.md). La relecture KAS est **en attente** ; aucune compilation supplémentaire ni fusion. A/W/I toujours validés localement, P17/RAUC/image amorçable non prouvés.


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
