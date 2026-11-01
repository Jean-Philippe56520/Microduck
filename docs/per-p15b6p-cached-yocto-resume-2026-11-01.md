# P15-B6-P-Cache — reprise ciblée du packaging avec cache WSL2 (01/11/2026)

## Décision fixée avant code ou essai

**Problème réel.** [GitHub CI #41257921306](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41257921306), source SHA `c50e703f6d1a2f13c5ed4c461f83394ec23c600f` : la commande réelle `bitbake -c package kwipi-passive-fixture` a atteint **489/522 tâches**, bloquée à `cmake-native:do_compile` par le **délai 1600s**, code 124. Aucun `do_package` de Kwipi ni audit `PKGDEST` réussi. Le BitBake réel `do_unpack` et les SHA des cinq modules sont déjà prouvés [B6-M #41257161976](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41257161976) et #41257921366. Les anciens essais locaux de l'opérateur ont obtenu `P14B do_package` (19 modules) et `P15A do_package` (643/643 tâches) dans un environnement WSL2 réutilisé. **La présence et la compatibilité du cache WSL2 actuel sont inconnues** : ce lot ne les invente pas.

**But mesurable.** Préparer **une seule** exécution du vrai `bitbake -c package kwipi-passive-fixture` dans la configuration KAS **déjà construite et cachée** chez l'opérateur, suivie de la vérification **octet par octet** du paquet principal dans `PKGDEST` par le validateur existant `scripts/per_p15b6_bitbake_package_gate.py`. Aucune installation, `do_rootfs`, `do_image`, WIC, RAUC, service, moteur ou robot. L'outil local proposé n'est pas une preuve de commande exécutée sur le PC tant que l'opérateur ne l'a pas effectivement lancé.

**Reuse/Adapt/Create.** Réutiliser sans changement `per_p11_v1_source_release` (archive constructeur au gitlink), `per_p12_yocto_layer` (recette daemon OEM), `per_p14b_yocto_python_layer` (19 sources), `per_p15b6_passive_python_addon` (5 sources), `per_p15b6_bitbake_package_gate` (PKGDEST), KAS 5.2 et le même commit OEM Yocto `1ee58387810cebb67ae0d634c351d95024483bce`. Créer **un seul orchestrateur minimal** pour le PC, uniquement préparation de couches scratch + overlay KAS et commande BitBake bornée, et des tests de refus sans lancer KAS. Ne pas ouvrir de PR indépendante ni modifier les recettes ou sous-modules. Registre tiers C3 : aucun composant pertinent justifiant un ajout ; classes natives BitBake restent l'autorité.

**Entrées locales explicites, jamais devinées.** Chemin du checkout Companion, SHA exact de la branche autorisée, checkout Yocto constructeur épinglé, `KAS_WORK_DIR`, `KAS_BUILD_DIR` qui contient les artefacts des builds antérieurs, et dossier scratch **nouveau et absent**. Les chemins anciennement observés `/home/jp/kwipi-build-v1/yocto` et `/home/jp/kwipi-build-v1/build` sont des **pistes, pas une observation en direct ni une valeur implicite**. Aucune clé/signature/transfert de secrets.

**Observations/risques.** Un cache peut être absent, périmé, construit sur un autre Yocto ou incompatible avec la nouvelle couche (sstate miss). KAS réécrit les métadonnées de **son** build dir et peut récupérer des dépendances s'il en manque : préserver les répertoires source, ne jamais effacer `build/tmp`, `sstate-cache`, `downloads`, ni essayer `clean/cleansstate/cleanall/purge`, ni exécuter une compilation simultanée. Il faut s'assurer que les chemins sont existants et extérieurs au checkout scratch, que l'espace libre est supérieur à 16 GiB et que KAS vaut 5.2 avant `--run`. Utiliser les chemins transmis, aucun répertoire utilisateur détruit. Hypothèse : les artefacts P14B/P15A permettent le `do_package` B6 en moins de 1 600 s ; **ce n'est pas une garantie**.

**Positifs à constater.** (1) préflight SHA du checkout et deux gitlinks OEM, Yocto exact, état Git suivi propre ; (2) cache déjà présent dans `KAS_BUILD_DIR/conf/local.conf` et `tmp/`, espace ≥16 GiB ; (3) aucune sortie ni sous-processus BitBake sans opt-in explicite ; (4) génération P11/P12, P14B/B6 en scratch de provenance vérifiée, overlay KAS sans `do_rootfs` ; (5) vrai BitBake `-p/-e/bitbake-getvar -f` et `-c package kwipi-passive-fixture` avec délai ≤1600s ; (6) contrôle exact de cinq .py dans PKGDEST, SHA des sources, Python 3.14, RDEPENDS P14B, complément absent de DEV et shipping ; (7) rapport JSON **local** sans export de l'environnement `-e`, aucun fichier OEM/sous-module modifié. Les tests PC synthétiques démontrent seulement le refus/le plan, pas la construction Yocto.

**Négatifs et STOP prédéfinis.** SHA inattendu, gitlink manquant, Yocto hors pin, checkout modifié, cache/build absent, collision de chemins, scratch préexistant, version kas différente, disque insuffisant, échec/timeout P11/P12/KAS/BitBake, PKGDEST non conforme, checksum absent/faux, paquet supplémentaire/symlink/modèle/SQLite/secret, image sélectionnant B6 => **STOP**, garder logs localement, ne revendiquer aucun succès de packaging. Pas de relance aveugle, de réparation du constructeur ni de sûreté désactivée. Retour arrière : ne pas exécuter `--run` ; sinon supprimer **manuellement seulement le nouveau scratch** après audit, jamais les caches. Un délai/échec implique « inconnu/en attente » et passage à un autre jalon.

**Déclencheur GitHub protégé.** Le workflow [B6-P](../.github/workflows/per-p15b6-bitbake-package.yml) exige le label explicite `run-b6p-bitbake` ou un dispatch. Les PR synchronisées **sans label** ne réexécutent plus la compilation de 522 dépendances. Un résultat `skipped` n'est **jamais** une preuve BitBake.

## Résultat

**Préparation/code/tests :** suite Python + B6-M + P15A + P15-B3 + N1 **CI success** au SHA `702115e`; B6-P GitHub **skipped** volontairement. **BitBake WSL2 : `do_package` et audit `PKGDEST` PASS d'après l'opérateur au même SHA**, voir le résultat complémentaire ci-dessous. Pas d'image ou de robot.

## Procédure locale WSL2 — uniquement sur décision explicite

Préconditions : checkout de la PR #244 au SHA exact affiché sur GitHub, sous-modules OEM présents aux gitlinks épinglés, checkout Yocto au SHA 1ee58387810cebb67ae0d634c351d95024483bce, KAS_WORK_DIR réellement utilisé lors des anciens builds (six clones OE/BitBake/Rockchip/RAUC), KAS_BUILD_DIR avec conf/local.conf, tmp/work et un cache-stamp cmake-native déjà terminé. KAS 5.2 et cargo requis : le mode `--check` vérifie désormais aussi leur disponibilité (`kas --version` et recherche locale de `cargo`), sans lancement de BitBake. Ne pas substituer des répertoires vierges ou réinstaller des dépendances au hasard. Les chemins WSL2 cités dans les logs antérieurs sont des pistes, non des chemins vérifiés aujourd'hui.

Depuis la racine du checkout Microduck dans WSL2, renseigner **les chemins réels** et conserver un scratch inexistant. Le SHA doit être recopié depuis la page de PR, pas auto-déduit comme une preuve indépendante.

```bash
PROJECT="$PWD"
YOCTO="/home/jp/kwipi-build-v1/yocto"       # verifier sur votre WSL2
WORK="/chemin/existant/du/KAS_WORK_DIR"       # repos OE deja presents
BUILD="/home/jp/kwipi-build-v1/build"       # verifier sur votre WSL2
SCRATCH="$HOME/kwipi-b6p-scratch-20261101"   # doit ne PAS exister
EXPECTED_SHA="<SHA complet du HEAD PR #244 lu sur GitHub>"

python3 -m scripts.per_p15b6_cached_package_runner --check \
  --project "$PROJECT" --yocto "$YOCTO" --work-dir "$WORK" \
  --build-dir "$BUILD" --scratch "$SCRATCH" --expected-sha "$EXPECTED_SHA"

# Uniquement apres preflight PASS, sans autre BitBake concurrent :
python3 -m scripts.per_p15b6_cached_package_runner --run \
  --project "$PROJECT" --yocto "$YOCTO" --work-dir "$WORK" \
  --build-dir "$BUILD" --scratch "$SCRATCH" --expected-sha "$EXPECTED_SHA"
```

Le mode --check ne cree aucun fichier ni ne lance kas, mais prouve seulement l'existence de sources epinglees et d'un cache eligible : status p15b6p_local_cached_preflight_only (PAS paquet verifie). L'option --run cree les couches P11/P12/P14B/B6 dans scratch en reutilisant les generateurs existants, impose CARGO_NET_OFFLINE et BB_NO_NETWORK via un overlay scratch, refuse toute recuperation Git HTTPS, saute checkout KAS des depots deja controles, n'invoque que BitBake parse/-e/getvar/do_package et le validateur existant. Le vrai BitBake est limite a 1600 s. Aucune commande clean, do_rootfs, do_image, service ou moteur.

**Verdict :** seule une commande --run reellement executee avec code de sortie 0 de BitBake, suivi de l'audit des fichiers et du rapport SCRATCH/package-proof.json avec status bitbake_passive_addon_package_files_verified_only, constitue une preuve de packaging LOCAL. En cas d'absence de cache, echec, expiration, interruptions, SHA differents ou fichier supplementaire : STOP, aucune preuve de paquet. Le dossier scratch n'est jamais supprime automatiquement ; conserver les logs localement sans publier les sorties -e, secrets ou fichiers prives. Le build cache sera susceptible d'etre modifie par BitBake pendant --run, d'ou la necessite d'un environnement sans autre compilation concurrente et d'un plan de restauration si ses artefacts sont critiques.

**A ce stade (historique avant l'exécution du 01/11/2026) :** le runner était uniquement préparé. Son exécution WSL2 est maintenant attestée par l'opérateur au SHA `702115e`; elle valide le paquet principal, pas un runtime OEM ni le robot.

## Incident local KAS du 01/11/2026 — STOP avant BitBake

Sur le run local du SHA `9ca3dd3f7d8d71c95160e3896cbce05c3860c61f`, les quatre générateurs ont réussi. KAS 5.2 a refusé l'assemblage d'une configuration sous le dépôt Git Yocto et d'un overlay hors dépôt : `All concatenated config files must belong to the same repository or all must be outside of versioning control`. Aucun `do_package`, aucun paquet. Le correctif copie **exactement** `yocto/kas/microduck.yml` dans le scratch, place l'overlay dans le **même scratch non versionné** et ajoute `repos.microduck_os.path` au checkout Yocto épinglé. Aucun fichier constructeur ni cache ancien n'est modifié pour contourner KAS. Les tests de fixtures vérifient la copie, le chemin OEM et le refus d'un KAS OEM lié ; le vrai montage KAS local a ensuite été validé par un `kas dump` WSL2, sans lancement de BitBake ; il ne constitue pas la preuve du paquet en lui-même. **Ne pas réutiliser le scratch précédent** : il contient les fichiers de l'essai arrêté. Pour le prochain `--check` et `--run`, utiliser un dossier scratch distinct, neuf et inexistant, après CI verte au nouveau SHA. Ne jamais considérer la génération des couches comme un packaging réussi.

## Résultat final de la reprise par cache (01/11/2026)

Le checkout local épinglé `702115e44e919178007a46d1ff10a8ab787a6c18` a passé le préflight, puis `kas dump` a affiché `P15_B6P_KAS_CONFIG_OK`, `OEM_CONFIG_UNCHANGED=true`, `BITBAKE_EXECUTED=false`. Sur un **nouveau scratch**, le second `--run` WSL2 a ensuite réussi : `bitbake_do_package_exit_code=0`, **522/522 tâches réussies, 512 non rejouées, 120,5 s**, `package_split_files_verified=true`, **5/5 SHA vérifiés**, statut `bitbake_passive_addon_package_files_verified_only` (rapport local sous `package-proof.json`). L'archive B6 correspond à `sha256:8d6939db16b507a12651f18e8486ad24b8ef5b6110b0bdca6407da0af5427c3d`. Le scratch du premier arrêt KAS a été conservé, aucun nettoyage de cache ou sous-module n'a été demandé. L'ensemble est une **preuve communiquée par l'opérateur**, non un accès direct au PC. **Fin de la porte de packaging B6-P ; ne pas réexécuter `--run` pour confirmer ce résultat déjà établi.** La preuve de paquet installé dans une image et la validation réelle OEM/robot restent en attente, avec l'audit P16 `R0/VARFLAGS` séparé.
