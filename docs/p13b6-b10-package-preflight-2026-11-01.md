**Qualification de l'unique WARNING P13B6 (preuve opérateur, 01/11/2026) :** le texte exact de 128 caractères correspond à l'avertissement OpenEmbedded `The Linux kernel on your build host was not configured to provide process I/O statistics. (CONFIG_TASK_IO_ACCOUNTING is not set)` ; SHA-256 du message seul `f91ed3723f631e73efb0af5ff679f6b020ad4bf43386a4b4e9a5daa33265290a`. Cela concerne `buildstats`/les statistiques I/O des processus **de l'hôte Linux**, pas le contenu du RPM, l'OS Yocto cible, la caméra ou les moteurs. **P13B6 : avertissement identifié, non bloquant pour les preuves de paquet et de tâches observées ; aucune modification du noyau WSL2 ni de réglage de sécurité.** L'absence de mesures `buildstats` I/O détaillées reste une limite, et un futur rootfs devra être qualifié séparément. Source externe historique : https://docs.yoctoproject.org/pipermail/yocto/2017-September/038136.html ; source OpenEmbedded `buildstats.bbclass`.

## Clôture du blocage payload P13B6 et contrôle réel du journal (01/11/2026)

**Retour WSL2 opérateur ultérieur (remplace le STOP natif plus bas, historique)** : `rpm2cpio` est un wrapper qui appelle finalement `rpm2archive.real`. Les bibliothèques `libarchive.so.13` et `libbz2.so.1` existaient déjà dans les sysroots Yocto ; chargement local temporaire par `LD_LIBRARY_PATH` **sans installation, symlink ajouté ni recompilation**. L'outil a terminé 0 et produit 20 480 octets GZIP/TAR (pas CPIO brut). Audit TAR en mémoire : exactement cinq `.py` réguliers, aucun fichier supplémentaire, cinq SHA-256 égaux aux sources et `PKGDEST` : `P13B6_PAYLOAD: PASS_5_OF_5`. Les permissions détaillées des membres TAR, la signature et l'authenticité de release ne sont pas qualifiées.

**Journal BitBake réel** : 10 386 octets, SHA-256 `53c906be7c5bf91a707c86dd236a69373f5eb59474d8270d2799293b41560292`, 117 lignes, 23 tâches `Running task` analysées, 0 non analysée, exactement **une** `kwipi-passive-fixture_0.1.0.bb:do_package_write_rpm`, 0 OEM `microduck-daemon:do_compile/do_package/do_install`, 0 `do_rootfs/do_image`, 0 `do_deploy` inattendu. 0 marqueurs `ERROR/FATAL`, résumé `all succeeded`, **un WARNING identifié (`CONFIG_TASK_IO_ACCOUNTING` sur l'hôte)**. `P13B6_REAL_LOG: PASS_TASK_SET`. Pas de reproduction de la compilation en CI ni preuve d'installation. **P13B6 paquet principal et jeu de tâches visible : PASS limité** ; `P16_B10_ROOTFS_24_MODULES=EN_ATTENTE`. Suivre [P16-A/B10 et ses critères](p16b10-offline-rootfs-audit-2026-11-01.md), sans relancer le RPM déjà créé.

---

# P13B5 validé ; P13B6 — décision avant empaquetage DEV B10 (01/11/2026)

## Retour final WSL2 de la session — empaquetage réel réussi, vérification de charge utile STOP (01/11/2026)

**Ce paragraphe prévaut sur les décisions intermédiaires `P13B6_PACKAGE_RUN:false` consignées plus bas**, qui décrivaient alors le dry-run uniquement. Base GitHub avant nouvelle PR documentaire : `main@5842780f6fab4b5bc1a8d997d71a8efeafca7d56` ; #259 est fusionnée (5/5 CI réussies).

| Étape réellement exécutée sur WSL2 | Preuve reçue | Portée |
|---|---|---|
| Préflight avant vrai BitBake | `P13B6_PINS_AND_TASKS: PASS` ; `P13B6_REAL_PACKAGE_PREFLIGHT: PASS_NO_BITBAKE` | Révisions, KAS et 23 tâches dry-run inchangés |
| Écriture ciblée | `P13B6_REAL_PACKAGE_WRITE_TASK: EXIT_0` | Une tâche `bitbake -c package_write_rpm kwipi-passive-fixture` réussie ; **pas** un `do_rootfs` |
| Arborescence `PKGDEST` | `P13B6_PYTHON_MODULES: 5` ; `P13B6_PYTHON_SHA256: PASS` | Cinq modules B6 en paquet séparé conformes à la source |
| Inventaire `DEPLOY_DIR_RPM` | 3 fichiers avec magie RPM valide | Principal `kwipi-passive-fixture-0.1.0-r0.noarch.rpm` **21458 octets**, `-dbg-0.1.0-r0.noarch.rpm` **5869**, `-dev-0.1.0-r0.noarch.rpm` **6009** ; les variantes sont normales, **ne pas exiger un seul RPM global** |
| En-tête paquet principal | `P13B6_RPM_MAIN: PASS_HEADER_AND_FILE_LIST` | Identité `kwipi-passive-fixture|0.1.0|r0|noarch`, cinq fichiers .py attendus, 0 chemin supplémentaire hors répertoires parents, dépendance `kwipi-companion`, aucun scriptlet |
| Digests internes de l'en-tête | `P13B6_RPM_HEADER_SHA256: PASS_5_OF_5` ; `FILEDIGESTALGO=8`, longueur 64 | Les digests déclarés **dans l'en-tête** pour les cinq fichiers correspondent aux sources. Cela **ne compare pas** les octets du payload compressé |
| Lecture CPIO réelle | `P13B6_PAYLOAD_STOP: native_rpm2cpio_unavailable_or_unusable` | Aucun payload décodé ; pas d'accusation de corruption |
| Diagnostic natif ultérieur | `RPM2CPIO_EXIT: 127`, 0 octet, `rpm2cpio.real` : `libarchive.so.13` introuvable ; `RPMKEYS_EXIT: 127`, `rpmkeys` : `libbz2.so.1` introuvable | **Chargeur ELF de l'outillage Yocto hors contexte**, non contenu du RPM. Il faut d'abord résoudre l'environnement de ces outils ; pas de bibliothèque système à installer par défaut |

**Précisions :** les outils existent dans `/home/jp/kwipi-build-v1/build/tmp/sysroots-components/x86_64/rpm-native/usr/bin/`. `rpm` utilisé dans `work/all-poky-linux/kwipi-passive-fixture/0.1.0/recipe-sysroot-native/usr/bin/rpm` peut lire `-qp` mais affiche en `stderr` `error: cannot open Packages database in /var/lib/rpm` ; son code retour pour `--qf %{FILEDIGESTALGO}` était bien **0**, et `stdout='8'`. Un essai `rpm -K --nosignature` a échoué sur le chemin d'`rpmkeys` absent du sysroot ciblé ; l'`rpmkeys` effectivement retrouvé ensuite a l'erreur de chargement `libbz2.so.1`. Ni cet échec, ni `rpm2cpio` 127 **ne démontrent** un RPM mal formé. Aucun digeste du **RPM complet** ni vérification de signature ne remplace la comparaison des octets décompressés à la source.

### Reprise bornée — ne pas refaire les compilations

1. **Lecture seule d'abord :** contrôler le binaire effectivement lancé (script enveloppe `rpm2cpio` vs `rpm2cpio.real`), l'`ldd`/`readelf -d` du vrai exécutable et de `rpmkeys`, et la présence des bibliothèques `libarchive.so.13` et `libbz2.so.1` dans les **sysroots natifs Yocto existants** (`build/tmp/sysroots-components/x86_64` et `recipe-sysroot-native`). Limiter la recherche et n'afficher que chemins/noms/versions utiles ; **ne pas publier d'environnement BitBake complet**, de secrets ni de médias.
2. **Si les bibliothèques exactes sont présentes et compatibles**, utiliser l'environnement natif Yocto correctement initialisé ou un chemin de bibliothèques strictement temporaire **limité au processus d'inspection**, sans créer de symlinks, modifier les binaires, installer d'outils hôte, nettoyer le cache ni répéter la tâche package. **STOP** si bibliothèque inconnue/incompatible ou nécessité de modifier le système.
3. Après relance de l'outil valide, contrôle positif **réel** : décompresser **en lecture seule** le RPM principal déjà produit, comparer *les octets de tous les fichiers réguliers* : **exactement cinq .py**, SHA-256 identiques à `proof["addon_sha256"]`, pas d'autre fichier, lien, device ou permission exécutable inattendus. Contrôle négatif : charge utile vide, tronquée, entrée supplémentaire, symlink, mauvaise somme, outil cassé → **STOP** ; jamais `PASS` sur les seuls en-têtes. Une validation RPM digests (non signée) est distincte de l'authenticité/ signature de release.
4. **Inspecter le journal réel privé** `/home/jp/kwipi-build-v1/p13b5-dev-metadata-20261101/p13b6-package-rpm-real.log` : résumé, erreurs, tâche finale et présence éventuelle de `microduck-daemon:do_compile/do_package/do_package_write_rpm` ou `do_rootfs/do_image` **dans la tâche réelle** ; ne pas conclure à son absence sur le seul dry-run. Si tâche inattendue, journal non vérifiable ou ambigu : **STOP** / preuve inconnue.
5. **Avant un nouveau rootfs**, adapter/faire tester les portes P16-A/B10 pour **24 modules** au lieu des anciens 19, avec SHA source, compte Kwipi isolé, P15A désactivée, shipping inchangé et binaires B12 AArch64 exacts ; **pas** de `do_rootfs` sous ce lot. Aucun firmware signé, WIC/RAUC ou robot validé.

**État de fin de session :** `P13B6_PACKAGE_WRITE=EXIT_0_WSL2` ; `P13B6_PKGDEST=PASS_5_OF_5` ; `P13B6_RPM_HEADER=PASS_MAIN_AND_DIGESTS` ; `P13B6_PAYLOAD=STOP_NATIVE_TOOL_DEPENDENCIES` ; `P13B6_REAL_LOG_AUDIT=EN_ATTENTE` ; `P16_ROOTFS_24_MODULES=EN_ATTENTE` ; `ROBOT_VALIDATED=false`.

---


## État et provenance

- Base de ce lot documentaire : `main@f3ecd8ae5bfe93c893128130f80105e32156659f` ; PR #258 **fusionnée après 5/5 CI vertes**. OEM `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto `1ee58387810cebb67ae0d634c351d95024483bce` ; aucun gitlink à modifier.
- Paquet Rust B12 `0.17.8+kwipi.p12.e2e9bfef7d7c` : `do_compile/do_package` AArch64 **PASS historiques sur WSL2** ; `mediad` et `robotd` ELF64 et empreintes vérifiés (voir [P13B3](p13b3-dev-b12-readonly-integration-gate-2026-11-01.md)). **Rootfs DEV actuel ancien** : `current` référence `...3406fee5428c`, pas B12 ; anciens manifestes `...e4a0a1268c730+bd113f317b` sans rattachement démontré.
- P13B4 : sortie opérateur `P13B4_SOURCE_PROVENANCE=PASS`, `P13B4_SOURCE_STAGE=PASS_SOURCES_ONLY`, `P13B4_B10_SOURCE_GATE=PASS_SOURCE_ONLY`, **19 modules P14B + 5 B6**, source `e2e9bfef7d7c4f46fe51924937e7939d78d00383`; staging `/home/jp/kwipi-build-v1/p13b4-dev-source-stage-20261101`.
- **Nouveau fait P13B5** : la commande `/mnt/c/Users/Jp/Downloads/p13b5_kas_metadata_gate.py --run-metadata` a été exécutée **sur le WSL2 de l'opérateur**, pas par GitHub/CI. Sortie textuelle intégrale des résultats :

```text
P13B5_B12_LAYER_COUNT: 1
P13B5_B12_LAYER: /home/jp/kwipi-build-v1/p13b-e2e9bfef/meta-kwipi
P13B5_KAS_WORK_CANDIDATES: 1
P13B5_STATIC_SOURCE_AND_PINS: PASS
P13B5_KAS_WORK: /home/jp/kwipi-build-v1/kas-work
P13B5_SCRATCH_UNCHANGED: False
P13B5_P12_B12_EFFECTIVE_METADATA: PASS
P13B5_P14B_B6_RECIPE_IDENTITIES_AND_DEPENDENCY: PASS
P13B5_P15A_DISABLED: PASS
P13B5_P15B10_DEV_ONLY_AND_ACCOUNT: PASS
P13B5_METADATA_ONLY: PASS_NO_PACKAGE_OR_ROOTFS_TASK
BINARY_RECOMPILED: false
ROOTFS_BUILT: false
```

Le script B5 réutilise `per_p13a_bitbake_env_gate.validate`, `per_p15a_bitbake_env_gate.validate`, `per_p15b10_dev_passive_env_gate.validate` (qui réutilise P14C et P15-B9). Il exécute réellement `bitbake -p`, six `bitbake -e` et `bitbake-layers show-appends` sur une composition KAS **DEV + shipping**, avec fichiers privés ; **aucune tâche package/rootfs demandée**. Le champ `P13B5_SCRATCH_UNCHANGED: False` indique l'autorisation d'un dossier de métadonnées nouveau, non une erreur. Les sorties complètes `*-env.txt` peuvent contenir des secrets OEM : **ne pas publier**.

**Décision :** `P13B5 = PASS_METADATA_EFFECTIVE_ON_WSL2`. Ce statut prouve la résolution effective de la source/version Rust B12, des deux recettes Python P14B/B6 et de leur dépendance, de P15A désactivée et de B10/compte Kwipi exclusivement DEV. Il ne prouve ni livraison de paquets au gestionnaire d'image, ni `do_rootfs`, ni services actifs, ni RAM/thermique/NPU/robot.

## P13B6 — porte avant toute tâche package

**Manque vérifié** : l'ancien `PKGDEST` B6 n'existe plus et aucun RPM B6 n'a été trouvé dans les motifs inspectés ; ses archives sources et la preuve de packaging historique sont conformes, et sa sélection effective DEV/shipping est maintenant démontrée. Le `do_package` B6 historique ne prouve pas un `do_package_write_rpm` ni la présence actuelle d'un paquet installable. **Gain mesurable** : rendre `kwipi-passive-fixture 0.1.0` disponible dans le format d'installation BitBake réellement configuré, sans recompiler le Rust B12 ni construire une image avant son auditeur 24/24.

**Réutiliser / adapter / nouveau** :
1. Réutiliser **tels quels** la configuration `/home/jp/kwipi-build-v1/p13b5-dev-metadata-20261101/{microduck-pinned.yml,p13b5-offline.yml}`, les couches P12/P13B4/OEM, les caches et validations P13A/P15A/B10 ; ne pas régénérer P12 depuis le SHA documentaire.
2. Vérifier avec le `bitbake -e` privé conservé `PACKAGE_CLASSES`, `PN/PV`, `RDEPENDS`, `PV` OEM et sélections DEV/shipping ; vérifier `PACKAGE_CLASSES=package_rpm` avant de cibler **uniquement** `kwipi-passive-fixture -c package_write_rpm`. Si autre backend : **STOP**, sélectionner explicitement la tâche correspondant au backend, pas une supposition.
3. Demander d'abord **un aperçu des tâches** avec `bitbake -n -c package_write_rpm kwipi-passive-fixture` dans le même KAS ; inspection privée et absence de recompile OEM planifiée avant **autorisation séparée** d'une tâche réelle. `-n` reste une opération d'analyse pouvant actualiser le cache parseur.
4. Après autorisation distincte d'une tâche package ciblée, vérifier frais : nouveau journal de tâche, `PKGDEST` exact de la recette, **exactement 5 .py**, SHA-256 égaux à la provenance B6 stage `e2e9bfef`, une archive RPM effectivement présente avec nom/version/architecture attendus et sa provenance, **aucun changement des deux SHA-256 binaires Rust P13B2**, aucune production WIC/RAUC ni `do_rootfs`. Un paquet enregistré dans le cache ne prouve ni installation ni boot.
5. **Avant tout futur `do_rootfs`**, adapter la porte historique [P16-A](../scripts/per_p16_dev_rootfs_audit.py) qui refuse le troisième paquet et impose 19 modules : exiger **exactement 19+5**, vérifier les 24 empreintes et aucun module supplémentaire, compte Kwipi isolé via P15-B9-R, P15A désactivée, `mediad`/`robotd` B12 et `current`, versions manifestes réellement associées au nouveau rootfs, et refus shipping. N'ajouter aucune permission, service ou auto-start.

**Positif préenregistré pour l'aperçu** : la configuration est encore au B12 `e2e9bfe`, B10 est DEV-only, `PACKAGE_CLASSES` contient bien `package_rpm`, la tâche `package_write_rpm` B6 est connue, `bitbake -n` termine à 0, aucune tâche `microduck-daemon:do_compile`, `do_rootfs`, `do_image` ou autre livraison/sécurité inattendue n'est planifiée. **Négatifs et STOP** : métadonnées absentes/altérées ou accessibles à d'autres utilisateurs, mauvais `PN/PV`, fournisseur B12 divergent, backend absent/différent, nom de tâche erroné, environnement KAS différent, sortie dry-run incomplète, dépendance OEM à reconstruire, erreurs, manque d'espace ou nouveaux fichiers de sortie écrasant un audit existant. Un cas ambigu = `inconnu/en attente`. Pas de `bitbake -c clean*` ni `-f`, pas de service, capture, RPC, mouvement, WIC/RAUC/flash. Retour arrière de l'aperçu : ne rien exécuter d'autre et conserver les caches/journaux.

## Commandes WSL2 (seulement le préflight P13B6)

**A. Contrôle des métadonnées existantes, en lecture seule.** Le script doit s'arrêter si la sortie P13B5 n'est plus accessible ou si un paramètre important est différent. N'imprime aucun `bitbake -e` brut :

```bash
python3 -B - <<'PY'
from pathlib import Path
import re, stat, subprocess

root = Path("/home/jp/kwipi-build-v1/p13b5-dev-metadata-20261101")
project = Path("/home/jp/kwipi-v1-p13b-e2e9bfef/companion")
yocto = Path("/home/jp/kwipi-build-v1/yocto")
def live(repo, *args):
    if not repo.is_dir() or repo.is_symlink():
        stop("missing_or_linked_checkout")
    p = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True, timeout=20)
    if p.returncode:
        stop("git_pin_check_failed")
    return p.stdout.strip()

files = {
    "daemon": "daemon-env.txt", "base": "base-env.txt",
    "addon": "addon-env.txt", "probe": "p15a-env.txt",
    "dev": "dev-env.txt", "shipping": "shipping-env.txt",
}
def stop(s):
    raise SystemExit("P13B6_PREFLIGHT_STOP: " + s)
if live(project, "rev-parse", "HEAD") != "e2e9bfef7d7c4f46fe51924937e7939d78d00383":
    stop("companion_head_changed")
if live(yocto, "rev-parse", "HEAD") != "1ee58387810cebb67ae0d634c351d95024483bce":
    stop("yocto_head_changed")
if any(live(repo, "status", "--porcelain", "--untracked-files=no") for repo in (project, yocto)):
    stop("tracked_files_modified")
for rel, expected in {
    "upstream/microduck": "942e58e3aa6dbb28e7037203fff11866122c7567",
    "upstream/microduck_rl": "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3",
}.items():
    if live(project, "rev-parse", "HEAD:" + rel) != expected:
        stop("oem_gitlink_changed")
def get(text, name):
    rows = re.findall(r"^(?:export )?" + re.escape(name) + r'="(.*)"$', text, re.M)
    if len(rows) != 1:
        stop("missing_or_duplicate_" + name)
    return rows[0]
parts = {}
for label, name in files.items():
    f = root / name
    if not f.is_file() or f.is_symlink() or (stat.S_IMODE(f.stat().st_mode) & 0o077):
        stop("missing_or_nonprivate_" + label)
    parts[label] = f.read_text(encoding="utf-8")
if get(parts["daemon"], "PV") != "0.17.8+kwipi.p12.e2e9bfef7d7c":
    stop("daemon_version_changed")
if get(parts["daemon"], "MICRODUCK_DAEMON_SRCREV") != "e2e9bfef7d7c4f46fe51924937e7939d78d00383":
    stop("daemon_revision_changed")
if get(parts["addon"], "PN") != "kwipi-passive-fixture" or get(parts["addon"], "PV") != "0.1.0":
    stop("addon_recipe_changed")
if get(parts["base"], "PN") != "kwipi-companion":
    stop("base_recipe_changed")
if "kwipi-companion" not in get(parts["addon"], "RDEPENDS:kwipi-passive-fixture").split():
    stop("addon_dependency_missing")
def tokens(v):
    return v.replace("\\n", " ").replace("\\t", " ").split()
if tokens(get(parts["dev"], "IMAGE_INSTALL")).count("kwipi-passive-fixture") != 1:
    stop("addon_not_exactly_once_in_dev")
if tokens(get(parts["shipping"], "IMAGE_INSTALL")).count("kwipi-passive-fixture") != 0:
    stop("addon_leaked_shipping")
if get(parts["probe"], "SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe") != "disable":
    stop("probe_enabled")
classes = tokens(get(parts["addon"], "PACKAGE_CLASSES"))
print("P13B6_BACKEND_CLASSES:", ",".join(classes))
if "package_rpm" not in classes:
    stop("rpm_backend_not_selected")
print("P13B6_METADATA_REUSE: PASS_READ_ONLY")
PY
```

**B. Aperçu des tâches sans construction réelle** (uniquement si A = PASS ; la sortie KAS/BitBake est conservée localement, pas publiée) :

```bash
set -euo pipefail
BASE=/home/jp/kwipi-build-v1
D="$BASE/p13b5-dev-metadata-20261101"
CFG="$D/microduck-pinned.yml:$D/p13b5-offline.yml"
LOG="$D/p13b6-package-rpm-dryrun.log"
if [ -e "$LOG" ] || [ -L "$LOG" ]; then
    echo "P13B6_DRYRUN_STOP: log_already_exists"
else
    (umask 077; : > "$LOG")
    export KAS_WORK_DIR="$BASE/kas-work" KAS_BUILD_DIR="$BASE/build"
    export KAS_CLONE_DEPTH=1 PYTHONDONTWRITEBYTECODE=1 CARGO_NET_OFFLINE=true
    export GIT_TERMINAL_PROMPT=0 GIT_CONFIG_COUNT=1
    export GIT_CONFIG_KEY_0=protocol.https.allow GIT_CONFIG_VALUE_0=never
    umask 022
    if kas shell --skip repos_checkout "$CFG" \
       -c 'set -euo pipefail; bitbake -n -c package_write_rpm kwipi-passive-fixture' \
       >> "$LOG" 2>&1; then
        echo "P13B6_DRYRUN_BITBAKE_EXIT: 0"
        python3 -B - "$LOG" <<'PYLOG'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
txt = path.read_text(encoding="utf-8", errors="replace")
tasks = [ln for ln in txt.splitlines()
         if re.search(r"(microduck-daemon.*do_compile|microduck-daemon.*do_package|do_rootfs|do_image)", ln)]
print("P13B6_DRYRUN_SUSPECT_TASK_LINES:", len(tasks))
print("P13B6_DRYRUN_LOG_PRIVATE: true")
print("P13B6_DRYRUN_REQUIRES_REVIEW: true")
PYLOG
    else
        echo "P13B6_DRYRUN_STOP: see_private_log_no_retry"
    fi
fi
```

Ce `bitbake -n` est un **aperçu**, pas une preuve absolue qu'une exécution ultérieure n'entraînerait aucun autre travail ; les fichiers de métadonnées peuvent être rafraîchis. **Ne pas encore exécuter le vrai `package_write_rpm` ou `do_rootfs`** sans inspection du dry-run. Partager seulement les 3 lignes `P13B6_DRYRUN_...` et, si erreur, le type de blocage sans fuite d'environnements. Ne pas effacer ni réutiliser un scratch préexistant.

## Retour P13B6 — dry-run opérateur (01/11/2026)

La sortie WSL2 fournie est :

```text
P13B6_DRYRUN_BITBAKE_EXIT: 0
P13B6_DRYRUN_SUSPECT_TASK_LINES: 0
P13B6_DRYRUN_LOG_PRIVATE: true
P13B6_DRYRUN_REQUIRES_REVIEW: true
```

**Preuve acquise :** la commande `bitbake -n -c package_write_rpm kwipi-passive-fixture` a terminé sans erreur ; le filtre limité n'a détecté aucun motif de compilation OEM/image. Le mode `-n` n'a exécuté ni la tâche de packaging réelle ni `do_rootfs`. `LOG_PRIVATE: true` est imprimé par le script et **ne prouve pas à lui seul** les permissions du fichier. Le résultat du préflight A n'était pas joint à ce message. **Zéro ligne regex ne garantit pas qu'une future exécution réelle éviterait toutes les dépendances OEM**. STOP pour la vraie tâche jusqu'à relecture minimale du log et des métadonnées.

### Revue privée du journal existant — sans relancer BitBake

```bash
python3 -B - <<'PY'
from pathlib import Path
import re
import stat

d = Path("/home/jp/kwipi-build-v1/p13b5-dev-metadata-20261101")
def stop(msg):
    raise SystemExit("P13B6_REVIEW_STOP: " + msg)
def read_private(name, cap):
    p = d / name
    if (p.is_symlink() or not p.is_file()
            or stat.S_IMODE(p.stat().st_mode) & 0o077
            or p.stat().st_size == 0 or p.stat().st_size > cap):
        stop("file_missing_linked_unprivate_or_size_invalid_" + name)
    return p.read_text(encoding="utf-8", errors="replace")
def bbvar(data, key):
    values = re.findall(r'^(?:export )?' + re.escape(key) + r'="(.*)"$', data, re.M)
    if len(values) != 1:
        stop("variable_missing_or_duplicated_" + key)
    return values[0]
daemon = read_private("daemon-env.txt", 64 * 1024**2)
addon = read_private("addon-env.txt", 64 * 1024**2)
dev = read_private("dev-env.txt", 64 * 1024**2)
shipping = read_private("shipping-env.txt", 64 * 1024**2)
if bbvar(daemon, "PV") != "0.17.8+kwipi.p12.e2e9bfef7d7c":
    stop("daemon_release_changed")
if (bbvar(addon, "PN") != "kwipi-passive-fixture"
        or bbvar(addon, "PV") != "0.1.0"
        or "package_rpm" not in bbvar(addon, "PACKAGE_CLASSES").split()):
    stop("addon_or_backend_changed")
def tokens(v):
    return v.replace("\\n", " ").replace("\\t", " ").split()
if (tokens(bbvar(dev, "IMAGE_INSTALL")).count("kwipi-passive-fixture") != 1
        or tokens(bbvar(shipping, "IMAGE_INSTALL")).count("kwipi-passive-fixture") != 0):
    stop("dev_shipping_selection_changed")
log = read_private("p13b6-package-rpm-dryrun.log", 32 * 1024**2)
lines = log.splitlines()
task_lines = [s for s in lines if "Running task" in s or "Executing task" in s]
refs = re.findall(r'([^\s()]+\.bb):(?P<task>do_[a-zA-Z0-9_]+)', log)
errors = sum(bool(re.search(r'(?i)\b(?:ERROR|FATAL):', s)) for s in lines)
oem = sum("microduck-daemon" in rec and task in
          {"do_compile", "do_package", "do_package_write_rpm"}
          for rec, task in refs)
images = sum(task.startswith(("do_rootfs", "do_image", "do_deploy"))
             for _, task in refs)
summary = any("Tasks Summary" in s or "Task Summary" in s for s in lines)
print("P13B6_LOG_LINES:", len(lines))
print("P13B6_TASK_LINES:", len(task_lines))
print("P13B6_TASK_REFERENCES:", len(refs))
print("P13B6_OEM_COMPILE_OR_PACKAGE_REFERENCES:", oem)
print("P13B6_IMAGE_REFERENCES:", images)
print("P13B6_ERROR_MARKERS:", errors)
print("P13B6_TASK_SUMMARY_PRESENT:", summary)
print("P13B6_METADATA_AND_FILE_PERMISSIONS: PASS_READ_ONLY")
if errors or oem or images:
    print("P13B6_REVIEW: STOP_ANOMALY")
elif not refs or not summary:
    print("P13B6_REVIEW: INCONCLUSIVE_LOG_FORMAT")
else:
    print("P13B6_REVIEW: PASS_BOUNDED_TASK_SCAN_ONLY")
print("P13B6_PACKAGE_RUN: false")
PY
```

La relecture de motifs est **non exhaustive** : elle ne prouve pas que la signature et le runqueue d'une exécution ultérieure sont identiques. Le journal reste privé. Ne pas lancer le vrai `do_package_write_rpm` tant que la revue n'a pas été examinée.

## Second retour P13B6 — STOP borné sur deux tâches de déploiement/image (01/11/2026)

**Sortie WSL2 transmise par l'opérateur, après relecture du journal précédent et des métadonnées privées :**

```text
P13B6_LOG_LINES: 71
P13B6_TASK_REFERENCES: 23
P13B6_OEM_COMPILE_OR_PACKAGE_REFERENCES: 0
P13B6_IMAGE_REFERENCES: 2
P13B6_ERROR_MARKERS: 0
P13B6_TASK_SUMMARY_PRESENT: True
P13B6_METADATA_AND_FILE_PERMISSIONS: PASS_READ_ONLY
P13B6_REVIEW: STOP_ANOMALY
P13B6_PACKAGE_RUN: false
```

**Décision : arrêt correct.** Deux références dans le journal correspondent au **filtre combiné** `task.startswith(("do_rootfs", "do_image", "do_deploy"))` ; elles ne sont **pas identifiées** et le résultat **ne démontre pas** que `do_rootfs` ou `do_image` sont planifiés. En particulier, `do_deploy` peut être une tâche normale de publication d'artefacts BitBake ; la présence d'un tel nom doit être expliquée par la recette et par sa place dans le plan, non assimilée automatiquement à une image livrable. À l'inverse, un `-n` sorti 0 ne garantit jamais l'absence de nouvelles tâches lors d'une exécution réelle ultérieure. Aucun `package_write_rpm` réel ni `do_rootfs` n'a été lancé. Statut `P13B6_DRYRUN = CODE0`, `P13B6_TASK_PLAN = STOP_CLASSIFICATION_PENDING`.

**Seule prochaine opération :** classifier **en lecture seule le même journal**, sans afficher d'environnement BitBake ni de chemin complet privé. Le préflight doit retrouver exactement les 23 références annoncées et les deux anomalies, vérifier l'intégrité/privacy du fichier, présenter les deux couples `recette.bb / nom de tâche` sous forme filtrée, plus les compilations éventuelles. **Le résultat ne donne pas d'autorisation d'empaquetage**.

```bash
python3 -B - <<'PY'
from pathlib import Path
import re
import stat

log = Path("/home/jp/kwipi-build-v1/p13b5-dev-metadata-20261101/p13b6-package-rpm-dryrun.log")
if (not log.is_file() or log.is_symlink()
        or stat.S_IMODE(log.stat().st_mode) & 0o077
        or not 0 < log.stat().st_size <= 32 * 1024**2):
    raise SystemExit("P13B6_CLASSIFY_STOP: log_missing_nonprivate_or_size_invalid")

text = log.read_text(encoding="utf-8", errors="replace")
regex = re.compile(r'([^\s()]+\.bb):(do_[A-Za-z0-9_]+)')
refs = []
for line in text.splitlines():
    for match in regex.finditer(line):
        recipe = Path(match.group(1)).name
        task = match.group(2)
        if not re.fullmatch(r'[A-Za-z0-9_.+-]{1,120}', recipe):
            raise SystemExit("P13B6_CLASSIFY_STOP: unusual_recipe_label")
        scheduled = "Running task" in line or "Executing task" in line
        refs.append((recipe, task, scheduled))

suspects = [(r, t, active) for r, t, active in refs
            if t.startswith(("do_rootfs", "do_image", "do_deploy"))]
print("P13B6_CLASSIFY_TOTAL_REFS:", len(refs))
print("P13B6_CLASSIFY_SUSPECTS:", len(suspects))
if len(refs) != 23 or len(suspects) != 2:
    raise SystemExit("P13B6_CLASSIFY_STOP: journal_has_changed_or_parser_differs")

for recipe, task, scheduled in suspects:
    print("P13B6_TASK_REVIEW:", recipe, task,
          "scheduled" if scheduled else "reference_only")

compile_refs = [(r, t) for r, t, _ in refs if t.startswith("do_compile")]
print("P13B6_COMPILE_REFS:", len(compile_refs))
for recipe, task in sorted(set(compile_refs)):
    print("P13B6_COMPILE_REVIEW:", recipe, task)

print("P13B6_ROOTFS_REFS:",
      sum(t.startswith("do_rootfs") for _, t, _ in refs))
print("P13B6_IMAGE_REFS:",
      sum(t.startswith("do_image") for _, t, _ in refs))
print("P13B6_DEPLOY_REFS:",
      sum(t.startswith("do_deploy") for _, t, _ in refs))
print("P13B6_CLASSIFY: READ_ONLY_NO_BITBAKE")
print("P13B6_PACKAGE_RUN: false")
PY
```

**STOP si `do_rootfs`, `do_image`, recette OEM inattendue, référence sans contexte compréhensible, journal modifié, ou recompilation inconnue**. Ne pas requalifier le STOP en PASS sur la seule absence de `do_rootfs` : les deux recettes/tâches doivent être examinées individuellement. Toujours aucune suppression du cache, aucune tâche réelle, WIC/RAUC/robot.

## Troisième retour P13B6 — identification des deux tâches et décision (01/11/2026)

**Observation exacte du journal privé, communiquée par l'opérateur :**

```text
P13B6_CLASSIFY_TOTAL_REFS: 23
P13B6_CLASSIFY_SUSPECTS: 2
P13B6_TASK_REVIEW: kwipi-passive-fixture_0.1.0.bb do_deploy_source_date_epoch scheduled
P13B6_TASK_REVIEW: kwipi-companion_0.2.0a1.bb do_deploy_source_date_epoch scheduled
P13B6_COMPILE_REFS: 2
P13B6_COMPILE_REVIEW: kwipi-companion_0.2.0a1.bb do_compile
P13B6_COMPILE_REVIEW: kwipi-passive-fixture_0.1.0.bb do_compile
P13B6_ROOTFS_REFS: 0
P13B6_IMAGE_REFS: 0
P13B6_DEPLOY_REFS: 2
P13B6_CLASSIFY: READ_ONLY_NO_BITBAKE
P13B6_PACKAGE_RUN: false
```

**Nature des tâches :** `do_deploy_source_date_epoch` est la tâche OpenEmbedded liée au `SOURCE_DATE_EPOCH` par recette et à la **reproductibilité des artefacts**, pas `do_deploy` d'une image produit ni `do_rootfs` ([référence Yocto](https://docs.yoctoproject.org/5.2.1/ref-manual/variables.html#term-SOURCE_DATE_EPOCH), [implémentation OpenEmbedded historique](https://www.openembedded.org/pipermail/openembedded-core/2018-March/149010.html)). Le filtre précédant `task.startswith("do_deploy")` était trop large ; le STOP a correctement protégé l'opération avant classification. Les deux `do_compile` identifiés sont les **recettes Python pures** P14B et B6 (`inherit allarch python3-dir` + installation de .py déjà révisés), **aucune recompilation Rust OEM n'est montrée dans ce dry-run**. `0 do_rootfs`, `0 do_image`, `0 autre do_deploy` dans les 23 références lues. Cette classification résout **l'anomalie de nom** ; elle n'atteste pas l'absence garantie de changement de signature ni la réussite d'un vrai `do_package_write_rpm`.

**Décision du lot P13B6 :** autoriser un **unique** `bitbake -c package_write_rpm kwipi-passive-fixture` dans **le même KAS** seulement après le contrôle juste avant exécution (source épinglée, 23 références identiques, 2 tâches `SOURCE_DATE_EPOCH` exactes, 2 `do_compile` Python exactes, aucun OEM/image, espace libre et absence de journal existant). **Ne pas** ajouter `-f`, `clean`, `do_rootfs`, WIC, RAUC, service, robot, ni nouvelle copie du fournisseur B12. Repli : STOP et conserver logs/caches si contexte différent, tâche inattendue ou échec. Ce n'est **pas** une autorisation globale de compilation ni de déploiement OEM.

### Préflight P13B6 de l'empaquetage ciblé (lecture seule)

```bash
python3 -B - <<'PY'
from pathlib import Path
import re, shutil, stat, subprocess

base = Path("/home/jp/kwipi-build-v1")
scratch = base / "p13b5-dev-metadata-20261101"
log = scratch / "p13b6-package-rpm-dryrun.log"
package_log = scratch / "p13b6-package-rpm-real.log"
project = Path("/home/jp/kwipi-v1-p13b-e2e9bfef/companion")
yocto = base / "yocto"

def stop(reason):
    raise SystemExit("P13B6_REAL_PREFLIGHT_STOP: " + reason)
def git(folder, *args):
    try:
        p = subprocess.run(["git", "-C", str(folder), *args],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        stop("git_unavailable")
    if p.returncode:
        stop("git_failed")
    return p.stdout.strip()
if git(project, "rev-parse", "HEAD") != "e2e9bfef7d7c4f46fe51924937e7939d78d00383":
    stop("companion_source_changed")
if git(yocto, "rev-parse", "HEAD") != "1ee58387810cebb67ae0d634c351d95024483bce":
    stop("yocto_source_changed")
if any(git(repo, "status", "--porcelain", "--untracked-files=no")
       for repo in (project, yocto)):
    stop("tracked_source_dirty")
for rel, sha in {
    "upstream/microduck": "942e58e3aa6dbb28e7037203fff11866122c7567",
    "upstream/microduck_rl": "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3",
}.items():
    if git(project, "rev-parse", "HEAD:" + rel) != sha:
        stop("gitlink_changed")
if (not log.is_file() or log.is_symlink()
        or stat.S_IMODE(log.stat().st_mode) & 0o077
        or not 0 < log.stat().st_size <= 32 * 1024**2):
    stop("dryrun_log_missing_or_not_private")
if package_log.exists() or package_log.is_symlink():
    stop("real_package_log_already_exists")
expected = sorted([
    ("kwipi-passive-fixture_0.1.0.bb", "do_deploy_source_date_epoch"),
    ("kwipi-companion_0.2.0a1.bb", "do_deploy_source_date_epoch"),
])
expected_compile = sorted([
    ("kwipi-passive-fixture_0.1.0.bb", "do_compile"),
    ("kwipi-companion_0.2.0a1.bb", "do_compile"),
])
body = log.read_text(encoding="utf-8", errors="replace")
refs = [(Path(recipe).name, task) for recipe, task in re.findall(
    r'([^\s()]+\.bb):(do_[A-Za-z0-9_]+)', body)]
suspect = sorted((rec, task) for rec, task in refs
                 if task.startswith(("do_rootfs", "do_image", "do_deploy")))
compile_tasks = sorted((rec, task) for rec, task in refs
                       if task.startswith("do_compile"))
if (len(refs) != 23 or suspect != expected
        or compile_tasks != expected_compile):
    stop("task_set_changed_or_unreviewed")
if any("microduck-daemon" in rec for rec, task in refs):
    stop("unexpected_oem_daemon_task")
if "Tasks Summary" not in body and "Task Summary" not in body:
    stop("missing_bitbake_summary")
if re.search(r'(?im)\b(?:ERROR|FATAL):', body):
    stop("error_in_dryrun")
if shutil.disk_usage(base / "build").free < 16 * 1024**3:
    stop("insufficient_build_disk")
for name in ("microduck-pinned.yml", "p13b5-offline.yml"):
    f = scratch / name
    if f.is_symlink() or not f.is_file() or f.stat().st_size == 0:
        stop("kas_overlay_missing_or_linked")
print("P13B6_PINS_AND_TASKS: PASS")
print("P13B6_TARGET: kwipi-passive-fixture_0.1.0")
print("P13B6_REAL_PACKAGE_PREFLIGHT: PASS_NO_BITBAKE")
print("P13B6_PACKAGE_EXECUTED: false")
PY
```

### Exécution unique B6 — seulement si le préflight précédent est PASS

```bash
set -euo pipefail
BASE=/home/jp/kwipi-build-v1
D="$BASE/p13b5-dev-metadata-20261101"
CFG="$D/microduck-pinned.yml:$D/p13b5-offline.yml"
LOG="$D/p13b6-package-rpm-real.log"
if [ -e "$LOG" ] || [ -L "$LOG" ]; then
    echo "P13B6_PACKAGE_STOP: log_already_exists"
else
    (umask 077; : > "$LOG")
    export KAS_WORK_DIR="$BASE/kas-work" KAS_BUILD_DIR="$BASE/build"
    export KAS_CLONE_DEPTH=1 PYTHONDONTWRITEBYTECODE=1 CARGO_NET_OFFLINE=true
    export GIT_TERMINAL_PROMPT=0 GIT_CONFIG_COUNT=1
    export GIT_CONFIG_KEY_0=protocol.https.allow GIT_CONFIG_VALUE_0=never
    umask 022
    if kas shell --skip repos_checkout "$CFG" \
       -c 'set -euo pipefail; bitbake -c package_write_rpm kwipi-passive-fixture' \
       >> "$LOG" 2>&1; then
        echo "P13B6_REAL_PACKAGE_WRITE_TASK: EXIT_0"
        echo "P13B6_B6_RPM_AND_PKGDEST: MUST_VERIFY_NEXT"
        echo "P13B6_ROOTFS_BUILT: false_not_requested"
    else
        echo "P13B6_REAL_PACKAGE_WRITE_TASK: STOP_NONZERO_SEE_PRIVATE_LOG"
        echo "P13B6_NO_AUTOMATIC_RETRY: true"
    fi
fi
```

**Ne pas conclure PASS paquet** sur `EXIT_0` seul : dans un contrôle ultérieur séparé, lire `PKGDEST` et `DEPLOY_DIR_RPM` **effectifs**, vérifier la présence de cinq fichiers .py exactement, leurs SHA-256 B6 et le RPM `allarch` sans autre contenu inattendu. Vérifier dans le log que `microduck-daemon` n'a pas été replanifié. En cas de STOP : ne pas relancer, conserver les fichiers d'audit et vérifier le motif sans exposer les secrets du `bitbake -e`.

## Statut à ce SHA documentaire

**Statut historique du dry-run, remplacé par le retour WSL2 en tête du document :** `P13B5_METADATA = PASS` (preuve opérateur WSL2) ; `P13B6_PACKAGE_WRITE = NON_EXECUTE` ; `P16_B10_ROOTFS_24_MODULES = EN_ATTENTE` ; `WIC/RAUC/ROBOT = NON_VALIDES`.
