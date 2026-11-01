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

## P13B4 — preuves opérateur du staging P14B/B6 et de la porte source B10 (01/11/2026)

**Sortie WSL2 observée et communiquée** (la commande a été exécutée par l'opérateur, pas par GitHub) :

```text
P14B_SOURCE_MODULES: 19
P15B6_SOURCE_MODULES: 5
P13B4_SOURCE_PROVENANCE: PASS
P13B4_SOURCE_STAGE: PASS_SOURCES_ONLY
P13B4_B10_SOURCE_GATE: PASS_SOURCE_ONLY
BITBAKE_EXECUTED: false
ROOTFS_BUILT: false
```

**Provenance et réemploi :** checkout propre `/home/jp/kwipi-v1-p13b-e2e9bfef/companion@e2e9bfef7d7c4f46fe51924937e7939d78d00383`, gitlinks OEM inchangés ; staging neuf `/home/jp/kwipi-build-v1/p13b4-dev-source-stage-20261101/{meta-kwipi-python,meta-kwipi-passive}`, 19+5 sources exactes. Les contrôles réutilisés `scripts.per_p14b_yocto_python_layer.{stage,verify}`, `scripts.per_p15b6_passive_python_addon.{stage,verify}` et `scripts.per_p15b10_dev_passive_env_gate.source_gate` ont réussi. Les deux dépôts candidats précédents étaient `Microduck-P15B6@702115e` et `kwipi-v1-p13b-e2e9bfef/companion@e2e9bfe` ; le second a été choisi **explicitement**, car le premier ne contient pas encore P15-B10. Aucun code n'a été changé ni recompilé pour résoudre la découverte de deux checkouts. P14B inventorie en outre `pyproject.toml` : le contrôle de concordance doit comparer **les 19 Python communs**, non une égalité aveugle entre 20 entrées et 19.

**Ce que le PASS prouve et ne prouve pas :** deux couches sources Python mutuellement cohérentes, avec recette et archive conformes à ce SHA ; le fichier `yocto/meta-kwipi-p15-passive-selection` répond à la porte source B10. Ce n'est **pas** une validation des `BBLAYERS` ou `IMAGE_INSTALL` réellement développés par BitBake, du paquet B6, de son `do_package_write_rpm`, d'une nouvelle composition rootfs, d'un service ni du robot.

**Prochain essai enregistré avant exécution (P13B5, métadonnées uniquement) :** conserver la couche P12 B12 `e2e9bfe` et son `PV` exact, réutiliser le staging P13B4, puis superposer uniquement les couches DEV P14C/P15A/P15-B9/P15-B10 au KAS constructeur épinglé. Lire `bitbake -e` et `bitbake-layers show-appends` en fichiers privés 0600 sans publier les contenus (les paramètres OEM peuvent contenir des hashes de mots de passe). Rejouer les portes déjà codées : P13A sur `microduck-daemon` pour `SRC_URI/PV/DUCK_REVISION`, P15A pour son auto-enable `disable`, P15-B10 pour sélection **exactement une fois en DEV, zéro shipping**, maintien de l'opérateur OEM, création DEV du compte `kwipi` sans groupe `robot`, 19+5 sources. Vérifier indépendamment `RDEPENDS:kwipi-passive-fixture` incluant `kwipi-companion` et `PN/PV` exacts. Critères négatifs/STOP : gitlinks, révision B12, source ou licence changeant ; couche inconnue, B10 active shipping, mots de passe exposés, service activé, module supplémentaire, paquet manquant, incohérence `KAS_WORK_DIR`, sortie de métadonnées manquante, erreur parser/BitBake. **Ne pas invoquer les runners historiques B9-R ni leurs anciens auditeurs P16-A tels quels**, qui interdisent B10 / refusent 24 modules. Un PASS de métadonnées n'autorise pas encore `do_rootfs`; toute compilation/installation serait un autre lot avec témoins/risques et contrôles de ressources, sans WIC/RAUC.

---
## Sixième diagnostic WSL2 — P12 B12 conservé et sstate B6 non localisé (01/11/2026)

**Sortie opérateur, préflight strictement en lecture seule :**

```text
B6_RECIPE_IDENTITY: True
B6_RECIPE_VERSION: 0.1.0
B6_SSTATE_CANDIDATES: 0
B6_SSTATE_PACKAGE_CANDIDATES: 0
B6_SSTATE_REUSE_NOT_YET_PROVEN: True
P12_STAGED_LAYERS_FOUND: 3
B12_STAGED_ARCHIVE_MATCH: True
B12_STAGED_RECIPE_MATCH: True
B12_STAGED_REVISION_MATCHES: 1
P13B3_CACHE_PREFLIGHT: READ_ONLY_COMPLETE
```

**Constats exacts :** le contexte B6 `recipe-env.txt` identifie `PN=kwipi-passive-fixture`, `PV=0.1.0` ; le motif de recherche borné dans `SSTATE_DIR` ne retrouve **aucun candidat au nom B6** (ni de fichier `:package:` selon le critère de comptage), ce qui ne démontre **pas** la purge complète des artefacts sstate ni la possibilité de réutiliser les signatures. Trois couches P12 ont été recherchées : **une seule** porte `companion_sha=e2e9bfef7d7c4f46fe51924937e7939d78d00383` avec `kwipi-v1-oem-source.tar.gz` SHA-256 `1763291f62c1e29ff248000dfc27564404dd1e37eb2845e1dd917ec315ae2da3` et les deux affectations `MICRODUCK_DAEMON_SRCREV`/`VERSION` exactes. Ce test ne valide ni `BBLAYERS` effectif ni l'entrée `do_rootfs` et ne donne pas le chemin de la couche correspondant à B12.

**Décision et limites :** préserver cette couche P12 B12 et son `packages-split` AArch64 (P13B2/P13B3 PASS), sans régénérer le fournisseur OEM depuis un nouveau commit documentaire : `scripts/per_p12_yocto_layer.py` construit `PV` à partir de `companion_sha[:12]`, ce qui pourrait réétiqueter le paquet Rust et invalider sa réutilisation. Les 24 sources Python 19+5 restent identiques entre `702115e`, `e2e9bfe` et `c6d0344`. B6 a une archive et provenance validées, un `PKGDEST` historique manquant et aucun sstate nominal retrouvé : une **nouvelle étape de packaging B6** pourrait être nécessaire pour rendre son paquet installable, mais **aucun `do_package` n'a été exécuté ou autorisé** dans ce lot.

**Porte suivante avant toute tâche BitBake :** localiser de façon non ambiguë les chemins physiques de la couche P12 B12, de la couche B6 `-b`, de P14B Python, des trois overlays DEV P14C/P15A/P15-B9 et de P15-B10 ; valider leur contenu et les gitlinks sans changement. Préparer dans un lot distinct une composition KAS DEV unique qui conserve le fournisseur Rust B12, les modules P14B 19 et B6 5, et sélectionne B10 **seulement en DEV**. Son préflight devra comparer les variables BitBake **effectives** `PV/SRCREV/DUCK_REVISION`, `IMAGE_INSTALL`, `RDEPENDS` et `BBLAYERS`, vérifier que shipping ne sélectionne ni Kwipi B10 ni compte DEV, conserver P15A désactivée et les unités OEM, puis produire un audit d'installation strict **24/24** (P16-A actuel n'accepte que 19). STOP si contradiction ou version B12 changée ; aucune nouvelle tâche moteur, `do_rootfs`, WIC, RAUC, flash ni essai robot dans cette preuve. La source `CLOSED` B6 garde sa revue juridique séparée.

---

## Cinquième diagnostic WSL2 — archives B6 conformes, PKGDEST historique absent (01/11/2026)

**Observation opérateur, strictement en lecture seule :**

```text
SCRATCH: p15b6p-cache-scratch-20261101
B6_PROOF_PRESENT: False
B6_PROVENANCE_PRESENT: True
B6_STAGE_REVISION: 9ca3dd3f7d8d71c95160e3896cbce05c3860c61f
B6_STAGE_FIVE_HASHES: True
B6_ARCHIVE_SHA_MATCH: True
B6_ARCHIVE_5_GITHUB_BLOBS_MATCH: True
B6_RECIPE_ENV: NOT_AVAILABLE
SCRATCH: p15b6p-cache-scratch-20261101-b
B6_PROOF_PRESENT: True
B6_PROVENANCE_PRESENT: True
B6_PROOF_STATUS: bitbake_passive_addon_package_files_verified_only
B6_PROOF_REVISION: 702115e44e919178007a46d1ff10a8ab787a6c18
B6_PROOF_FIVE_HASHES: True
B6_STAGE_REVISION: 702115e44e919178007a46d1ff10a8ab787a6c18
B6_STAGE_FIVE_HASHES: True
B6_ARCHIVE_SHA_MATCH: True
B6_ARCHIVE_5_GITHUB_BLOBS_MATCH: True
B6_PROOF_STAGE_MATCH: True
B6_PKGDEST_EXISTS: False
B6_PACKAGED_FILES: NOT_FOUND
B6_AUDIT: READ_ONLY_COMPLETE
```

**Portes réellement franchies :** chacune des deux archives de source staged a un SHA-256 correspondant à sa provenance ; ses 5 membres correspondent octet pour octet aux blobs GitHub. Le scratch `-b` contient un `package-proof.json` dont `packaged_sha256`, révision source et SHA de l'archive correspondent à sa provenance. Le premier scratch n'a pas de rapport de packaging ni d'environnement `recipe-env`. Le `PKGDEST` enregistré dans l'environnement privé du scratch `-b` **n'existe plus** au moment du contrôle ; aucune disponibilité actuelle des cinq fichiers empaquetés n'est attestée.

**Ne pas confondre :** archive source B6 validée ≠ paquet actuel disponible, historique `package_split_files_verified=true` ≠ nouveau `do_package` exécuté, absence de RPM ≠ échec de `do_package`, et similarité des 24 blobs Git entre anciennes révisions ≠ preuve de dépendances installées ou fonctionnement sur le robot. Aucun nouveau paquet n'a été construit, aucune tâche n'a été lancée. Le statut est `B6_SOURCE_ARCHIVE = PASS`, `B6_HISTORICAL_PROOF = CONSISTENT`, `B6_CURRENT_PKGDEST = ABSENT`, `B6_SSTATE_REUSE = UNKNOWN`, `B10_DEV_EFFECTIVE_SELECTION = UNKNOWN`.

**Décision suivante :** ne pas refaire P11/P12/P13B2 ni modifier les sous-modules. Vérifier uniquement la présence des objets sstate B6 et les chemins effectifs de `recipe-env.txt` existant sans imprimer d'environnement brut ; ensuite préparer un overlay KAS **DEV seulement** qui réutilise la source B12 à provenance fixe, P14B (19 modules), P15-B6 (5 modules), P15-B10, P15A inactive, P15-B9 (compte isolé), et audit d'installation 24/24 révisé au lieu de P16-A historique. La préparation doit prouver le fournisseur Rust B12 et l'absence de contamination shipping avant toute tâche `do_rootfs`. Aucun cache n'est nettoyé, aucun `do_package`/nouveau rootfs, WIC, RAUC, service ou robot entrepris par ce diagnostic. La licence de redistribution `CLOSED` reste un blocage séparé pour diffusion réelle.

---

## Quatrième diagnostic opérateur — empreinte B6 historique retrouvée (01/11/2026)

**Sortie WSL2 reçue, lecture seule, sans exécution distante GitHub :**

```text
B6_RPM_COUNT: 0
B6_PKGDATA_COUNT: 0
B6_PACKAGE_STAMPS_COUNT: 0
B6_KAS_OR_STAGE_PATHS_COUNT: 4
B6_KAS_OR_STAGE: kwipi-build-v1/p15b6p-cache-scratch-20261101/meta-kwipi-passive
B6_KAS_OR_STAGE: kwipi-build-v1/p15b6p-cache-scratch-20261101/p15b6p-offline.yml
B6_KAS_OR_STAGE: kwipi-build-v1/p15b6p-cache-scratch-20261101-b/meta-kwipi-passive
B6_KAS_OR_STAGE: kwipi-build-v1/p15b6p-cache-scratch-20261101-b/p15b6p-offline.yml
B6_CANDIDATE_PROOFS_COUNT: 1
B6_PROOF: package-proof.json status= bitbake_passive_addon_package_files_verified_only package_split_files_verified= True source_revision= 702115e44e919178007a46d1ff10a8ab787a6c18
B6_DISCOVERY: READ_ONLY_ONLY_NO_BITBAKE
```

**Preuve indépendante GitHub :** les **19 fichiers P14B** (sélection explicite `n5.APPROVED_FILES - n6.OMITTED + sim_ipc.py`) et les **5 fichiers supplémentaires P15-B6** ont **exactement les mêmes SHA de blobs Git (24/24)** aux commits `702115e44e919178007a46d1ff10a8ab787a6c18`, `e2e9bfef7d7c4f46fe51924937e7939d78d00383` (B12) et `c6d0344ee35c49830ac104fe9d07062b2b2764cc` (main). **Pas de dérive des 24 sources Python sélectionnées entre ces trois commits.** Cela ne remplace pas la vérification des fichiers dans les archives et paquets locaux, ni une preuve de fermeture/dépendances/installation sur cible.

**Interprétation stricte :** deux anciens dossiers de staging sont trouvés ; un rapport privé affirme le contrôle exact de cinq fichiers du **`packages-split` B6 à sa date**. Sa propre source `scripts/per_p15b6_bitbake_package_gate.py` annonce explicitement `bitbake_task_execution_attested_by_this_script=false` : le rapport à lui seul n'atteste pas qu'une tâche `do_package` a été réellement exécutée, et **n'atteste pas la présence actuelle** de `packages-split`. Le `0 RPM` n'est pas un échec `do_package` : cette tâche ne force pas `do_package_write_rpm`. Les recherches `tmp/pkgdata` et `tmp/stamps` sont bornées aux motifs précédents ; absence dans ces motifs ≠ disparition de tous les caches. Ne pas faire de `bitbake -c clean*`, ni copier aveuglément une archive historique dans une recette de la nouvelle image.

**Prochaine étape avant toute écriture :** retrouver le `package-proof.json` exact dans les deux `scratch`, vérifier son `packaged_sha256` (5 clés) contre le `kwipi-passive-source-provenance.json` de la **même** couche, son archive `kwipi-passive-fixture-0.1.0.tar.gz`, et, si le `recipe-env.txt` privé subsiste, lire uniquement la variable effective `PKGDEST` en mémoire pour vérifier ce répertoire et les cinq `.py` sans exposer de `bitbake -e` brut. STOP si preuve absente/altérée, fichiers manquants, couche étrangère, permissions douteuses ; ne pas reconstruire automatiquement. Si les artefacts de paquet ont été éliminés, les **sources B6 restent disponibles et inchangées** ; un éventuel `do_package` ciblé serait un lot ultérieur avec justification explicite, après qualification de la composition DEV/shipping.

---

## Troisième préflight opérateur — BBLAYERS et B6 (01/11/2026)

**Sortie transmise, audit en lecture seule d'un `bblayers.conf` et d'un chemin `packages-split` précis :**

```text
BBLAYERS_CONF_PRESENT: True
LAYER_REFERENCE: P12_OEM_SOURCE True
LAYER_REFERENCE: P14B_PYTHON False
LAYER_REFERENCE: P15B6_PASSIVE_PACKAGE False
LAYER_REFERENCE: P14C_DEV_IMAGE False
LAYER_REFERENCE: P15A_PROBE False
LAYER_REFERENCE: P15B9_ACCOUNT False
LAYER_REFERENCE: P15B10_SELECTION False
P15B6_CACHED_PACKAGE_COUNT: 0
P13B3_NEXT_PREFLIGHT: READ_ONLY_COMPLETE
```

**Interprétation exacte :** le fichier `/home/jp/kwipi-build-v1/build/conf/bblayers.conf` inspecté ne comporte pas les noms recherchés, **mais ce n'est pas une preuve de la sélection BitBake DEV/shipping effective pour une nouvelle commande KAS**. Les lanceurs P15-B6-P et P15-B9-R utilisent des **overlays KAS temporaires** dans un répertoire `scratch` et définissent `KAS_BUILD_DIR` ; un autre contexte peut avoir produit les anciens paquets/rootfs. `P15B6_CACHED_PACKAGE_COUNT=0` signifie seulement qu'aucun paquet n'a été trouvé sous le motif `build/tmp/work/*/kwipi-passive-fixture/*/packages-split/kwipi-passive-fixture` ; cette absence **n'invalide pas** les preuves WSL2 historiques `do_package` B6 (5 modules), ni ne démontre qu'aucune archive RPM/sstate ne subsiste. Les **versions B12/B10 installées, le BBLAYERS effectif futur et l'existence d'un RPM B6 réutilisable sont toujours inconnus**.

**Porte suivante (lecture seule, aucune nouvelle compilation) :** inventorier dans le `KAS_BUILD_DIR` actuel les preuves privées B6 (sans publier environnement complet, mots de passe ou secrets), `tmp/deploy/rpm`, `tmp/pkgdata`, les stamps existants et les overlays KAS `scratch` déjà utilisés. Ne pas parcourir tout le disque ni déplacer/supprimer les caches. Si des fichiers sont absents, état `inconnu/en attente` ; décider ensuite seulement si la couche B6 source existante doit être réinstanciée dans une nouvelle **composition DEV opt-in**. Tester une fois, sur configuration KAS effective, les protections B10 : cinq fichiers B6 exacts et leur RDEPENDS P14B, sélection DEV unique, absence shipping ; conserver B9 identités, P15A inactive et OEM `robotd`/ `mediad` inchangés. **Le lanceur B9-R actuel refuse B10 et ne peut pas servir d'intégrateur tel quel.** Aucune commande `do_rootfs`, service ou déploiement n'est autorisée par le présent inventaire.

---

## Second diagnostic opérateur P13B3 — rootfs ancien confirmé (01/11/2026)

**Lecture seule WSL2 transmise, sans accès direct du connecteur GitHub à la machine opérateur :**

```text
DEV_ROOTFS_COUNT: 1
RELEASES_DIR: directory
RELEASE: 0.17.8+kwipi.p12.3406fee5428c dir
BIN: 0.17.8+kwipi.p12.3406fee5428c mediad regular
BIN: 0.17.8+kwipi.p12.3406fee5428c robotd regular
CURRENT: releases/0.17.8+kwipi.p12.3406fee5428c
UNIT: mediad.service regular
UNIT: robotd.service regular
UNIT: kwipi-readonly-probe.service regular
DEV_MANIFEST_COUNT: 2
MANIFEST: microduck-image-dev-microduck-zero3.rootfs-20261031175742.manifest
PACKAGE: kwipi-companion 0.2.0a1
PACKAGE: kwipi-readonly-probe 0.1
PACKAGE: microduck-daemon 0.17.8+kwipi.p12.e4a0a1268c730+bd113f317b
MANIFEST: microduck-image-dev-microduck-zero3.rootfs.manifest
PACKAGE: kwipi-companion 0.2.0a1
PACKAGE: kwipi-readonly-probe 0.1
PACKAGE: microduck-daemon 0.17.8+kwipi.p12.e4a0a1268c730+bd113f317b
P13B3_INVENTORY: READ_ONLY_COMPLETE_NOT_A_PASS
```

**Faits désormais distingués :**
- **Paquet B12 AArch64** `0.17.8+kwipi.p12.e2e9bfef7d7c` : PASS antérieur par relecture du paquet `packages-split`, deux empreintes conformes.
- **Rootfs DEV unique réellement inspecté** : `mediad` et `robotd` sont présents sous la release **antérieure** `0.17.8+kwipi.p12.3406fee5428c`, et `current` pointe vers elle. Le rootfs inspecté **n'intègre pas les binaires sous le chemin de release B12 attendu**. Cela explique le STOP précédent sans incriminer `do_compile`/`do_package`.
- **Deux manifestes existants** affichent la version de paquet `e4a0a1268c730+bd113f317b`, qui ne correspond **ni** au suffixe de la release active `3406fee5428c` **ni** à celui de la release B12 `e2e9bfef7d7c`. Ils sont des artefacts historiques distincts dont l'association au répertoire `rootfs` n'est **pas prouvée**. Ne pas prétendre connaître la cause de ce décalage ni attribuer l'un des manifestes au rootfs par simple proximité de nom.
- Les trois unités systemd sont **présentes comme fichiers réguliers**, sans inspection de leur contenu ni du statut runtime ; la sonde P15A ne doit toujours pas être démarrée. `kwipi-passive-fixture` n'apparaît dans **aucun des deux manifestes consultés**, sans que cela prouve une quelconque composition d'un nouveau rootfs.
- Le périmètre de cet essai reste `lecture_fichiers_WSL2` ; aucune installation, commande système, écritures, capteurs, ACL runtime, boot, WIC, RAUC ni robot.

**Critères de décision révisés par preuve :** un **nouveau rootfs DEV avec B12** serait nécessaire pour obtenir une **nouvelle composition** contenant cette release ; le besoin n'autorise pas automatiquement `do_rootfs`. Avant tout essai, vérifier les `BBLAYERS` et `IMAGE_INSTALL` DEV/shipping **effectifs**, la provenance/chemin des archives et des paquets B12 déjà construits, et la sélection de la couche P15-B10 (5 modules) avec contrôle strict 19+5. L'ancien lanceur P15-B9-R refuse B10 et l'ancien auditeur P16-A refuse 24 modules : ils ne doivent **pas** être réutilisés tels quels pour déclarer la cible complète conforme. Une nouvelle source P11 générée au SHA documentaire peut modifier `DUCK_REVISION` et `PV` : **préserver/réutiliser la source et les artefacts B12 `e2e9bfef...` vérifiés**, sans reconstruction par changement de SHA purement documentaire, sous réserve de vérifier l'environnement BitBake effectif. Préflight/critères positifs et négatifs, provenance des manifestes et accord sur la seule tâche `do_rootfs` doivent être distincts de l'observation présente.

**Statut opérationnel :** `P13B3_PACKAGE_B12 = PASS`, `P13B3_ROOTFS_B12 = NOT_PRESENT_AT_EXPECTED_VERSION`, `P13B3_IMAGE_MANIFEST_PROVENANCE = INCONNUE`, `P15B10_IN_NEW_ROOTFS = NON_VERIFIE`. Aucun PASS d'intégration, de service ou de robot.

---

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
