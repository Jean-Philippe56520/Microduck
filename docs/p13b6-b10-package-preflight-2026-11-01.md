# P13B5 validé ; P13B6 — décision avant empaquetage DEV B10 (01/11/2026)

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

## Retour opérateur P13B6 — dry-run exécuté, aucune tâche réelle (01/11/2026)

**Nouvelle sortie WSL2 transmise :**

```text
P13B6_DRYRUN_BITBAKE_EXIT: 0
P13B6_DRYRUN_SUSPECT_TASK_LINES: 0
P13B6_DRYRUN_LOG_PRIVATE: true
P13B6_DRYRUN_REQUIRES_REVIEW: true
```

**Ce qui est prouvé :** `bitbake -n -c package_write_rpm kwipi-passive-fixture` sous la configuration KAS P13B5 est sorti avec le code 0 ; le filtre simple des lignes suspectes du script n'a trouvé **aucun motif** de compilation OEM ou d'image dans ce journal. `P13B6_DRYRUN_LOG_PRIVATE` est une valeur déclarée par le script, **pas** une lecture indépendante de ses droits Unix. La sortie de la porte A `P13B6_METADATA_REUSE` n'a **pas** été transmise dans ce message (même si la commande B était prévue seulement après A). La classification du runqueue n'a pas été examinée intégralement : **zéro ligne regex ≠ preuve qu'aucun travail OEM ne serait replanifié lors d'une future exécution réelle**. Aucun RPM n'a été produit ni inspecté, `do_package_write_rpm` réel **non exécuté**.

**Prochaine porte courte, sans nouveau BitBake :** lire uniquement `p13b6-package-rpm-dryrun.log` et les variables nécessaires des `*-env.txt` conservés pour confirmer les droits privés, backend RPM, version Rust B12, sélection DEV/shipping et présence/format des lignes de runqueue. Ne publier que les compteurs, pas de log intégral. Si le journal est vide, ne comporte aucune ligne tâche identifiable, n'est pas privé ou contient erreur/anomalie : `INCONNU / STOP`, **pas d'autorisation implicite du vrai package**. Les critères initiaux ci-dessus restent inchangés.

### Relecture bornée du journal P13B6 (sans nouvelle tâche)

```bash
python3 -B - <<'PY'
from pathlib import Path
import re, stat

base = Path("/home/jp/kwipi-build-v1/p13b5-dev-metadata-20261101")
log = base / "p13b6-package-rpm-dryrun.log"
def stop(reason):
    raise SystemExit("P13B6_LOG_REVIEW_STOP: " + reason)
def read_private(path, max_bytes):
    if (not path.is_file() or path.is_symlink()
            or stat.S_IMODE(path.stat().st_mode) & 0o077):
        stop("missing_linked_or_nonprivate_file")
    if not 0 < path.stat().st_size <= max_bytes:
        stop("empty_or_oversized_file")
    return path.read_text(encoding="utf-8", errors="replace")
def variable(content, key):
    values = re.findall(r'^(?:export )?' + re.escape(key) + r'="(.*)"

`P13B5_METADATA = PASS` (preuve opérateur WSL2) ; `P13B6_PACKAGE_WRITE = NON_EXECUTE` ; `P16_B10_ROOTFS_24_MODULES = EN_ATTENTE` ; `WIC/RAUC/ROBOT = NON_VALIDES`.
,
                        content, re.M)
    if len(values) != 1:
        stop("missing_or_duplicate_variable_" + key)
    return values[0]
daemon = read_private(base / "daemon-env.txt", 64 * 1024**2)
addon = read_private(base / "addon-env.txt", 64 * 1024**2)
dev = read_private(base / "dev-env.txt", 64 * 1024**2)
shipping = read_private(base / "shipping-env.txt", 64 * 1024**2)
if variable(daemon, "PV") != "0.17.8+kwipi.p12.e2e9bfef7d7c":
    stop("daemon_release_changed")
if (variable(addon, "PN") != "kwipi-passive-fixture"
        or variable(addon, "PV") != "0.1.0"
        or "package_rpm" not in variable(addon, "PACKAGE_CLASSES").split()):
    stop("addon_identity_or_backend_changed")
def tokens(value):
    return value.replace("\\n", " ").replace("\\t", " ").split()
if (tokens(variable(dev, "IMAGE_INSTALL")).count("kwipi-passive-fixture") != 1
        or tokens(variable(shipping, "IMAGE_INSTALL")).count("kwipi-passive-fixture") != 0):
    stop("dev_or_shipping_selection_changed")
data = read_private(log, 32 * 1024**2)
lines = data.splitlines()
task_lines = [s for s in lines if re.search(
    r"(?i)\b(?:Running task|Executing task|do_[a-z][\w]*)\b", s)]
task_refs = re.findall(r'([^\s()]+\.bb):(?P<task>do_[a-zA-Z0-9_]+)', data)
errors = sum(bool(re.search(r"(?i)\b(?:ERROR|FATAL):", s)) for s in lines)
oem = sum(("microduck-daemon" in recipe and task in {"do_compile", "do_package", "do_package_write_rpm"})
          for recipe, task in task_refs)
images = sum(task.startswith(("do_rootfs", "do_image", "do_deploy"))
             for _, task in task_refs)
target = sum("kwipi-passive-fixture" in recipe and task == "do_package_write_rpm"
             for recipe, task in task_refs)
summary = any("Tasks Summary" in s or "Task Summary" in s for s in lines)
print("P13B6_LOG_LINES:", len(lines))
print("P13B6_LOG_TASK_LINES:", len(task_lines))
print("P13B6_LOG_RECIPE_TASK_REFERENCES:", len(task_refs))
print("P13B6_LOG_TARGET_PACKAGE_WRITE_REFERENCES:", target)
print("P13B6_LOG_OEM_PACKAGE_OR_COMPILE_REFERENCES:", oem)
print("P13B6_LOG_IMAGE_TASK_REFERENCES:", images)
print("P13B6_LOG_ERROR_MARKERS:", errors)
print("P13B6_LOG_TASK_SUMMARY_PRESENT:", summary)
print("P13B6_LOG_METADATA_AND_PERMISSIONS: PASS_READ_ONLY")
if errors or oem or images:
    print("P13B6_LOG_REVIEW: STOP_ANOMALY")
elif not task_refs or not summary:
    print("P13B6_LOG_REVIEW: INCONCLUSIVE_NO_RECOGNIZED_RUNQUEUE")
else:
    print("P13B6_LOG_REVIEW: PASS_TASK_REFERENCE_SCREEN_ONLY")
print("P13B6_NO_PACKAGE_RUN: true")
PY
```

L'inventaire de lignes tâche est un **contrôle de cohérence supplémentaire**, non une preuve de cause, d'absence exhaustive de dépendances ni de stabilité des signatures. Le plan de tâche réel devra rester borné à `kwipi-passive-fixture` avant autorisation du package.

## Statut à ce SHA documentaire

`P13B5_METADATA = PASS` (preuve opérateur WSL2) ; `P13B6_PACKAGE_WRITE = NON_EXECUTE` ; `P16_B10_ROOTFS_24_MODULES = EN_ATTENTE` ; `WIC/RAUC/ROBOT = NON_VALIDES`.
