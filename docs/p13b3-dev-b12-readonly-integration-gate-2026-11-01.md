# P13B3 — qualification hors ligne de la distribution DEV B12 (01/11/2026)

## Objet, provenance et limite

Base vérifiée avant ce lot : `main@c6d0344ee35c49830ac104fe9d07062b2b2764cc`, PR [#256](https://github.com/Jean-Philippe56520/Microduck/pull/256) et [#257](https://github.com/Jean-Philippe56520/Microduck/pull/257) **fusionnées**. Les cinq workflows visibles de #257 et les sept de #256 au HEAD étaient terminés en succès au contrôle GitHub du 01/11. Les preuves opérateur P13B2 WSL2 attestent seulement la compilation et `do_package` de `microduck-daemon` sur AArch64 pour le **SHA source de compilation** `e2e9bfef7d7c4f46fe51924937e7939d78d00383`. Le merge documentaire #257 ne change pas ces octets.

Version exacte de la release B12 compilée : `0.17.8+kwipi.p12.e2e9bfef7d7c`.

| Binaire P13B2 packages-split | Taille | SHA-256 de l'opérateur |
|---|---:|---|
| mediad | 11 160 240 | `2e1319a17072f0c4a7ae1594a785aa987873d15e01d50a435b6772c873c99c1f` |
| robotd | 6 435 872 | `0aa212501839d766d7f138bae25db85949b8eb7a1dac72d70cd7d8db147982dc` |

**Manque attesté :** [P16-A](../scripts/per_p16_dev_rootfs_audit.py) vérifie le manifeste, les 19 modules P14B et les trois fichiers P15A ; [P16-S1](../scripts/per_p16_dev_rootfs_service_gate.py) vérifie les références de démarrage de la sonde ; [P15-B9-R](../scripts/per_p15b9_rootfs_identity_gate.py) contrôle les comptes et groupes du rootfs. Aucun de ces contrôles ne compare **les deux binaires B12 du paquet AArch64** avec **les deux binaires effectivement présents dans le rootfs DEV**. Le `do_rootfs` B9-R antérieur a été attesté sur WSL2 par 4 515 tâches, puis 20/20 tests et audit post-hoc, mais **aucun rootfs B12 requalifié** n'a été produit dans ce lot. Ne pas attribuer automatiquement la version B12 au rootfs historique ; il peut être ancien, et sa version est à mesurer.

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
