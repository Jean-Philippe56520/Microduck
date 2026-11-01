# P13B3 — qualification hors ligne de la distribution DEV B12 (01/11/2026)

## Objet, provenance et limite

Base vérifiée avant ce lot : `main@c6d0344ee35c49830ac104fe9d07062b2b2764cc`, PR [#256](https://github.com/Jean-Philippe56520/Microduck/pull/256) et [#257](https://github.com/Jean-Philippe56520/Microduck/pull/257) **fusionnées**. Les cinq workflows visibles de #257 et les sept de #256 au HEAD étaient terminés en succès au contrôle GitHub du 01/11. Les preuves opérateur P13B2 WSL2 attestent seulement la compilation et `do_package` de `microduck-daemon` sur AArch64 pour le **SHA source de compilation** `e2e9bfef7d7c4f46fe51924937e7939d78d00383`. Le merge documentaire #257 ne change pas ces octets.

Version exacte de la release B12 compilée : `0.17.8+kwipi.p12.e2e9bfef7d7c`.

| Binaire P13B2 packages-split | Taille | SHA-256 de l'opérateur |
|---|---:|---|
| mediad | 11 160 240 | `2e1319a17072f0c4a7ae1594a785aa987873d15e01d50a435b6772c873c99c1f` |
| robotd | 6 435 872 | `0aa212501839d766d7f138bae25db85949b8eb7a1dac72d70cd7d8db147982dc` |

**Manque attesté :** [P16-A](../scripts/per_p16_dev_rootfs_audit.py) vérifie le manifeste, les 19 modules P14B et les trois fichiers P15A ; [P16-S1](../scripts/per_p16_dev_rootfs_service_gate.py) vérifie les références de démarrage de la sonde ; [P15-B9-R](../scripts/per_p15b9_rootfs_identity_gate.py) contrôle les comptes et groupes du rootfs. Aucun de ces contrôles ne compare **les deux binaires B12 du paquet AArch64** avec **les deux binaires effectivement présents dans le rootfs DEV**. Le `do_rootfs` B9-R antérieur a été attesté sur WSL2 par 4 515 tâches, puis 20/20 tests et audit post-hoc, mais **aucun rootfs B12 requalifié** n'a été produit dans ce lot. Ne pas attribuer automatiquement la version B12 au rootfs historique ; il peut être ancien, et sa version est à mesurer.

## Première exécution opérateur P13B3 — PASS paquet / STOP rootfs (01/11/2026)

**Preuve de sortie communiquée par l'opérateur** après exécution du contrôle P13B3 préenregistré :

```text
P13B3_PACKAGED_B12: PASS
P13B3_STOP: mediad_missing_or_symlink
```

Le script confirme avoir trouvé **un** candidat `packages-split/microduck-daemon` B12 et comparé `mediad` et `robotd` comme fichiers réguliers, ELF64 little-endian AArch64, aux **deux empreintes exactes attendues**. Il a ensuite trouvé **un** rootfs `microduck-image-dev`, mais la cible `/opt/robot/daemon/releases/0.17.8+kwipi.p12.e2e9bfef7d7c/bin/mediad` n'est pas un fichier régulier sans symlink. Ce message regroupe **absence et lien symbolique**, sans trancher entre eux. La version de release du rootfs, la présence d'un autre `mediad`, le binaire `robotd` installé, le lien `current`, les unités et le manifeste **n'ont pas été vérifiés par cette exécution**, puisqu'elle s'est arrêtée au premier STOP. Le caractère historique de la version du rootfs est une **hypothèse plausible**, pas encore un fait mesuré.

**Décision :** `P13B3_PACKAGE_ONLY = PASS` (preuve opérateur, non exécution GitHub), `P13B3_ROOTFS_B12 = STOP` et intégration complète `en attente`. Ne pas relancer `do_compile`, `do_package`, `do_rootfs`, ni toucher aux caches sur cette seule sortie. Faire d'abord une lecture des releases installées, du lien `current` et du manifeste, sans prétendre que le contrôle P16-A historique valide une cible B10.

### Diagnostic suivant — inventaire local sans écriture, WSL2 uniquement

Dans le shell **bash WSL2** (et non dans PowerShell directement), ce bloc ne fait que lire les noms des releases, les deux chemins de binaires, la cible du lien `current`, les unités et quelques versions de paquets des manifestes existants. Aucun BitBake, socket, système monté ni secret :

```bash
python3 -B - <<'PY'
from pathlib import Path

base = Path("/home/jp/kwipi-build-v1")
work = base / "build/tmp/work"
roots = sorted(p for p in work.glob("*/microduck-image-dev/*/rootfs")
               if p.is_dir() and not p.is_symlink())
print("DEV_ROOTFS_COUNT:", len(roots))
if len(roots) != 1:
    raise SystemExit("P13B3_INVENTORY_STOP: expected_one_dev_rootfs")
root = roots[0]
releases = root / "opt/robot/daemon/releases"
print("RELEASES_DIR:", "directory" if releases.is_dir() and not releases.is_symlink() else "missing_or_link")
if releases.is_dir() and not releases.is_symlink():
    for release in sorted(releases.iterdir(), key=lambda p: p.name):
        if release.name.startswith("."):
            continue
        print("RELEASE:", release.name, "dir" if release.is_dir() and not release.is_symlink() else "other")
        for name in ("mediad", "robotd"):
            p = release / "bin" / name
            state = ("symlink" if p.is_symlink()
                     else "regular" if p.is_file() else "missing_or_other")
            print("BIN:", release.name, name, state)
current = root / "opt/robot/daemon/current"
print("CURRENT:", str(current.readlink()) if current.is_symlink() else "missing_or_not_link")
for name in ("mediad.service", "robotd.service", "kwipi-readonly-probe.service"):
    p = root / "usr/lib/systemd/system" / name
    print("UNIT:", name, "regular" if p.is_file() and not p.is_symlink()
          else "symlink" if p.is_symlink() else "missing_or_other")
image_dir = base / "build/tmp/deploy/images"
manifests = sorted(image_dir.rglob("microduck-image-dev-*.manifest")) if image_dir.is_dir() else []
print("DEV_MANIFEST_COUNT:", len(manifests))
for p in manifests[:8]:
    print("MANIFEST:", p.name)
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and parts[0] in {
            "microduck-daemon", "kwipi-companion",
            "kwipi-readonly-probe", "kwipi-passive-fixture"
        }:
            print("PACKAGE:", parts[0], parts[2] if len(parts) > 2 else "version_unknown")
if len(manifests) > 8:
    print("MANIFESTS_TRUNCATED: true")
print("P13B3_INVENTORY: READ_ONLY_COMPLETE_NOT_A_PASS")
PY
```

Ne pas conclure une absence à partir d'un seul manifeste ancien : un `*.manifest` du répertoire `deploy/images` peut provenir d'une image antérieure. Relier d'abord la version du rootfs aux fichiers réellement présents et à sa provenance de build.

## Écart B10 prouvé dans les gardes historiques (audit statique)

**Attention, ne pas réutiliser P16-A inchangé pour prétendre valider la composition V1 avec P15-B10.** La couche `yocto/meta-kwipi-p15-passive-selection` demande `kwipi-passive-fixture` **DEV seulement** et la source du paquet B6 installe cinq fichiers Python supplémentaires aux côtés des dix-neuf de P14B. Or `scripts/per_p16_dev_rootfs_audit.py` impose `EXPECTED = ("kwipi-companion", "kwipi-readonly-probe")`, refuse tout autre paquet `kwipi-` dans le manifeste et exige **exactement 19** `.py` sous `microduck_companion` : un futur rootfs conforme à B10 serait rejeté par cette **ancienne** porte P16-A. `P16-S1` dépend en outre du rapport P16-A.

Le lanceur historique `scripts/per_p15b9_cached_rootfs_runner.py` ne monte pas la couche de sélection B10 et **refuse délibérément** `kwipi-passive-fixture` dans `IMAGE_INSTALL` (`unreviewed P15-B6 package selected`). Son succès passé était légitime pour le périmètre B9-R ; il ne qualifie pas les cinq modules supplémentaires de B10.

**Conséquence décisionnelle, sans nouveau code ici :** le prochain audit du manifeste doit distinguer (a) rootfs B9-R historique, validé uniquement sur sa composition d'époque ; (b) cible DEV B10/B12 complète, **sans validateur P16-A/B9-R compatible prouvé à ce stade**. Ne pas affaiblir `EXPECTED` ni accepter arbitrairement 24 modules : réutiliser les preuves B6 et B10 existantes pour un futur contrôle d'intégrité **19+5 exacts, dépendances et DEV seulement**, avec tests négatifs paquet absent, module altéré, contamination shipping. Aucune exécution BitBake, aucun rootfs B10 prouvé dans cette PR. Cette constatation ne retire aucune preuve antérieure du périmètre B9-R.

## Porte OEM et matrice de réemploi

- **Réutiliser sans changement :** OEM `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto `microduck_yocto@1ee58387810cebb67ae0d634c351d95024483bce`, `robotd` seul propriétaire du moteur, `mediad` seule caméra, `tofd` OEM, scripts d'audit P13/P15/P16 et leurs tests. Aucune synchronisation des gitlinks.
- **Recette constructeur, état statique vérifié :** `meta-microduck/recipes-microduck/microduck-daemon/microduck-daemon.bb` installe les binaires sous `/opt/robot/daemon/releases/\${PV}/bin`, avec `current → releases/\${PV}`, `SYSTEMD_SERVICE` OEM et `SYSTEMD_AUTO_ENABLE = "enable"` (dont `mediad` et `robotd`). **Ne pas imposer la désactivation globale des unités OEM pour compenser l'absence de robot** : contrôler leur composition sans les démarrer.
- **Unités et identité statiques :** `mediad.service` épinglé utilise `User=mediad`, `Group=mediad`, `SupplementaryGroups=video render robot`, `RuntimeDirectory=mediad`; `robotd.service` utilise `User=root`, `Group=robot`, `RuntimeDirectory=robotd`. L'overlay Kwipi `meta-kwipi-p15-account` demande le compte `kwipi` sans privilège moteur, seulement DEV ; `kwipi-readonly-probe.service` est désactivée, mais **possède encore** `SupplementaryGroups=robot` (socket RPC complet au niveau Unix, aucune preuve d'une restriction RPC par méthode).
- **Ne pas créer** de nouveau pilote, service permanent, caméra, permission Unix, base SQLite ou reconstruction pour un audit d'inventaire. Les sources OEM amont et les références tierces C3 ne sont pas des dépendances pour cette qualification.
- **Attention OEM réseau :** la documentation du `mediad.service` épinglé signale un accès WebRTC à examiner avant exposition. Cette lecture n'atteste aucune ouverture de port ni aucun processus actif sur une cible.

## Critères préenregistrés, avant toute commande

**Positifs (PASS nécessaires)** :
1. Paquet AArch64 local B12 unique, `mediad` et `robotd` non symlinks, ELF64 little-endian AArch64, SHA-256 **égaux** aux preuves P13B2.
2. Rootfs DEV existant unique, binaires sous **la même** version de release, SHA-256 **égaux** à ceux du paquet, `current` pointant vers la même release (pas vers une copie précédente).
3. Unités installées `mediad` et `robotd` avec les chemins OEM attendus ; aucun `--kwipi-local-detections` actif dans l'unité `mediad`.
4. Identité P15-B9 et P15A ré-auditée par **les validateurs existants** sur *ce* rootfs, puis vérification de son manifeste DEV, dépendances et état systemd installé. `P16-S1` seulement si son rapport P16-A source existe et correspond réellement à ce rootfs.

**Négatifs et STOP** : archives/paquets absents, candidats multiples, checksum différent, ELF non-AArch64, liens inattendus, release `current` ancienne, unité modifiée, activation imprévue de la sonde, compte `kwipi` avec privilèges, rapport historique non corrélé ou preuve incomplète → **STOP / en attente**, ne pas relancer BitBake automatiquement. **Ne pas traiter l'absence de B12 dans un ancien rootfs comme un défaut du paquet P13B2.** Comparer les versions avant de décider si un nouveau `do_rootfs` DEV aurait un gain réel. Les deux warnings hôte BitBake P13B2 sont non bloquants et ne motivent aucune reconstruction.

**Limites persistantes :** absence de validation de `/run/mediad/identity.json` et des ACL du socket après bind/rebind ; pas de `systemctl start`, d'acceptation de RPC, de caméra, d'inférence RKNN/NPU, de comparaison 50 Hz, de mesure RSS/thermique, de boot, de WIC, de RAUC/signature, de flash ni de robot physique. Même un PASS rootfs ne validerait que les **fichiers d'une composition DEV**, ni un déploiement ni l'exécution réelle de ses unités.

## WSL2 — contrôle immédiat, exclusivement en lecture seule

Ce bloc **ne lance pas BitBake, ne monte pas de partition, ne modifie pas de fichier ni de cache**, ne démarre pas de service et n'imprime pas de secrets. Il s'exécute avec Python de l'hôte ; il lit les artefacts existants dans `/home/jp/kwipi-build-v1`. Il sépare le succès du paquet et l'absence éventuelle de la nouvelle version dans le rootfs.

```bash
python3 -B - <<'PY'
from pathlib import Path
import hashlib

base = Path("/home/jp/kwipi-build-v1")
work = base / "build/tmp/work"
pv = "0.17.8+kwipi.p12.e2e9bfef7d7c"
expected = {
    "mediad": "2e1319a17072f0c4a7ae1594a785aa987873d15e01d50a435b6772c873c99c1f",
    "robotd": "0aa212501839d766d7f138bae25db85949b8eb7a1dac72d70cd7d8db147982dc",
}

def stop(reason):
    print("P13B3_STOP:", reason)
    raise SystemExit(1)

def one(paths, label):
    found = sorted(p for p in paths if p.is_dir() and not p.is_symlink())
    if len(found) != 1:
        stop(f"{label}_count_{len(found)}")
    return found[0]

def check_binary(path, name):
    if not path.is_file() or path.is_symlink():
        stop(f"{name}_missing_or_symlink")
    with path.open("rb") as fh:
        header = fh.read(64)
        fh.seek(0)
        digest = hashlib.file_digest(fh, "sha256").hexdigest()
    if (len(header) < 64 or header[:4] != b"\x7fELF"
            or header[4:6] != bytes((2, 1))
            or int.from_bytes(header[18:20], "little") != 183):
        stop(f"{name}_not_elf64_aarch64")
    if digest != expected[name]:
        stop(f"{name}_sha256_mismatch")
    return digest

if not work.is_dir():
    stop("cached_work_tree_missing")
pkg = one(work.glob(
    f"*/microduck-daemon/*/packages-split/microduck-daemon/"
    f"opt/robot/daemon/releases/{pv}/bin"), "b12_packages_split")
for name in expected:
    check_binary(pkg / name, name)
print("P13B3_PACKAGED_B12: PASS")

root = one(work.glob("*/microduck-image-dev/*/rootfs"), "existing_dev_rootfs")
release = root / "opt/robot/daemon/releases" / pv / "bin"
for name in expected:
    check_binary(release / name, name)
current = root / "opt/robot/daemon/current"
if not current.is_symlink() or current.readlink().as_posix() != f"releases/{pv}":
    stop("current_release_symlink_mismatch")

unit_dir = root / "usr/lib/systemd/system"
units = {
    "mediad.service": {
        "ExecStart=/opt/robot/daemon/current/bin/mediad",
        "User=mediad", "Group=mediad", "RuntimeDirectory=mediad",
    },
    "robotd.service": {
        "ExecStart=/opt/robot/daemon/current/bin/robotd --socket /run/robotd.sock",
        "User=root", "Group=robot", "RuntimeDirectory=robotd",
    },
}
for name, required in units.items():
    path = unit_dir / name
    if not path.is_file() or path.is_symlink():
        stop(f"unit_missing_or_symlink_{name}")
    active = {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.lstrip().startswith(("#", ";"))}
    if not required.issubset(active):
        stop(f"unit_configuration_changed_{name}")
    if name == "mediad.service" and any(
            "--kwipi-local-detections" in ln for ln in active):
        stop("mediad_opt_in_activated_by_unit")
print("P13B3_ROOTFS_B12_FILES_AND_UNITS: PASS")
print("P13B3_SCOPE: offline_files_only; identities_manifest_acl_runtime_not_claimed")
PY
```

La vérification des comptes peut ensuite se faire **sans écrire de rapport** en important directement `verify_rootfs(root)` du script existant `scripts/per_p15b9_rootfs_identity_gate.py` dans le checkout Companion local **dont on aura vérifié la révision**. Ne pas exécuter l'option CLI `--report` pour cette première inspection si l'objectif reste strictement lecture seule. La vérification P16-S1 est conditionnée au rapport P16-A préexistant ; ne pas régénérer une preuve historique juste pour obtenir une sortie PASS.

## Décision après WSL2 et retour arrière

- `P13B3_PACKAGED_B12: PASS` puis `P13B3_ROOTFS_B12_FILES_AND_UNITS: PASS` + P15-B9/P16/manifeste conformes : **composition des fichiers DEV vérifiée**, pas de déploiement. Étudier ensuite seulement les portes RAUC, OEM runtime et ressources séparées.
- Paquet PASS mais rootfs STOP pour version différente/absente : **manque identifié ; décision distincte d'un éventuel nouveau rootfs DEV**, seulement après préflight frais, critères et accord. Ne pas modifier la WIC historique.
- Paquet STOP : préserver logs/PKGDEST/provenance, diagnostiquer avant toute reconstruction ; aucune promotion de version.
- Rapport manquant ou environnement incomplet : `inconnu/en attente` ; ne pas inventer de résultat.

Retour arrière du lot documentaire : fermer la PR sans fusion ; aucun cache, gitlink, modèle, service, binaire, secret ou mémoire privée n'est modifié.
