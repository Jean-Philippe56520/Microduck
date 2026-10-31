# P16-I / P16-K — manifeste DEV et anomalie de référence KAS (31 octobre 2026)

## Faits et preuve

**P16-I (contrôle ciblé) : PASS.** L'opérateur a interrogé en lecture seule le manifeste réel déjà construit du `microduck-image-dev` dans `build/tmp/work`. Résultats : `MANIFEST_COUNT=1`, `PACKAGE_COUNT=1334`, `DEBUG_PACKAGES=0`, `P16_I=PASS`. Cela confirme l'absence de paquets dont le nom se termine par `-dbg` **dans ce rootfs DEV**, et explique que les avertissements QA de `gstreamer1.0-plugins-rs-dbg` (déjà classifiés [P16-W](per-p16w-rootfs-warning-classification-2026-10-31.md)) ne représentent pas une installation de ces paquets de debug dans l'image inspectée. **Ne prouve pas** l'absence de toute information de débogage dans d'autres paquets, ni le comportement d'un système démarré, ni la shipping image.

**P16-K (état local) : divergence confirmée, cause pas encore identifiée.** Le contrôle du dépôt sous `kas-work` retourne : `REPOSITORIES_FOUND=1`, `PIN_EXISTS=True`, `BRANCH_EXISTS=True`, `PIN_ANCESTOR_OF_BRANCH=NO` pour `f28a144aa0a0ae05ca2ee91e1aef6aa05f6a12db` et `refs/remotes/origin/wrynose`. Cela concorde avec l'arrêt antérieur de KAS 5.2 : la branche locale actuelle ne contient pas le commit épinglé dans son historique. **N'implique pas** que la référence distante officielle soit corrompue, que le pin soit erroné ou que la construction antérieure ait échoué.

## Contre-vérification publique, distincte des observations WSL2

Le miroir GitHub `openembedded/meta-openembedded` (lecture du 31/10/2026) donne `wrynose@c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e`. Sa comparaison publique [`f28a144...wrynose`](https://github.com/openembedded/meta-openembedded/compare/f28a144aa0a0ae05ca2ee91e1aef6aa05f6a12db...wrynose) renvoie `status=ahead`, `ahead_by=85`, `behind_by=0`, `merge_base_commit=f28a144aa0a0ae05ca2ee91e1aef6aa05f6a12db` : **le pin est ancêtre de ce miroir public**. L'[appel amont wrynose du 29 octobre 2026](https://patchwork.yoctoproject.org/project/oe/patch/cover.1793262316.git.anuj.mittal%40oss.qualcomm.com/) part également de `f28a144...`, mais ne suffit pas à établir l'état instantané de `git.openembedded.org`.

**Conclusion limitée :** l'erreur KAS peut être due à une référence locale `origin/wrynose` périmée/divergente, à la configuration d'origine/miroir ou à une évolution distante ; il reste à comparer le SHA de `origin/wrynose` local avec celui de la branche distante effective **sans `fetch` ni modification**. Le miroir GitHub est une contre-vérification utile, pas une autorisation de changer les SHA OEM.

## Porte P16-K suivante — diagnostic non destructif

Sur le poste WSL2, localiser **le même** dépôt sous `kas-work` (aucun chemin non vérifié), puis relever en lecture seule les valeurs :
- `git rev-parse --verify refs/remotes/origin/wrynose` : SHA de la référence locale ;
- `git cat-file -t f28a144...` et `git show -s --format=%P f28a144...` : type et parent du pin ;
- `git merge-base f28a144... refs/remotes/origin/wrynose` : plus récent ancêtre commun, et état tracked du dépôt ;
- `git ls-remote --heads origin wrynose` : SHA de la **branche distante effective** ; c'est une requête réseau en lecture seule, **pas un `fetch`**. Ne publier que les SHA et le nom d'hôte non sensible, pas l'URL brute si elle contient des identifiants.

**Arrêt :** commande distante inaccessible ou référence différente de la branche publique => laisser P16-K **inconnu/STOP** ; pas de retouche des couches, pas de `fetch`, `git reset`, changement de branch/commit KAS ou `--force-checkout`. Même si le problème est une référence locale périmée, toute correction du checkout et nouvelle invocation KAS restent un lot distinct avec décision préalable explicite et retour arrière.

## État V1 après P16-I/K

- **P16-A :** `do_rootfs` DEV et audit 19/19 + 3/3 conformes sur WSL2, `P16_AUDIT_EXIT_CODE=0` ([reprise](reprise-v1-p16a-rootfs-verified-2026-10-31.md)).
- **P16-W :** 32 avertissements classifiés selon recettes OEM ([rapport](per-p16w-rootfs-warning-classification-2026-10-31.md)).
- **P16-I :** contrôle **ciblé** du manifeste DEV réussi, 1 334 paquets, aucun paquet `-dbg`.
- **P16-K :** blocage de l'appartenance du pin **local** à `origin/wrynose` ; le miroir public conserve l'ancêtre, cause locale/distant officiel à établir.
- **Toujours non prouvé :** `do_image`/WIC amorçable, services en exécution, image shipping, RAUC/signature/rollback, P17, matériels/moteurs/robot, droits de redistribution `LICENSE=CLOSED`. PR #230 → #231 → #235 → #238 ouvertes/drafts, aucune fusion autorisée.

Pas de compilation, installation ni changement de gitlink dans ce lot.

## P16-K — nouvelle preuve locale/distante : SHA identiques (31/10/2026)

L'opérateur a exécuté un diagnostic sans fetch/reset : `REMOTE_HOST=git.openembedded.org`, `PIN=f28a144aa0a0ae05ca2ee91e1aef6aa05f6a12db`, `LOCAL_WRYNOSE=c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e`, `REMOTE_WRYNOSE=c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e`, `LOCAL_EQUALS_REMOTE=True`, `REMOTE_EQUALS_PUBLIC_MIRROR=True`, `COMMON_ANCESTOR=UNKNOWN`.

**Constat :** l'hypothèse de branche locale simplement périmée est **écartée** à l'instant du test : local, origine Git effective et miroir public ont le même HEAD. L'API publique avait démontré que le SHA épinglé est bien ancêtre de ce HEAD. Le `merge-base` **local** introuvable indique donc un défaut de visibilité du graphe d'ancêtres dans le dépôt local ; **l'hypothèse prioritaire, non encore vérifiée, est un clone superficiel** (Git `shallow` marque des commits frontières comme des racines et peut rendre `merge-base` trompeur). Un dépôt partiel/missing objects ou des remplacements locaux demanderaient d'autres preuves avant conclusion.

**Porte immédiate, en lecture seule :** `git rev-parse --is-shallow-repository`, chemin `git rev-parse --git-path shallow` et nombre de lignes de ce fichier, ainsi que vérification d'intégrité limitée `git status --porcelain --untracked-files=no` et `git merge-base --is-ancestor`. Ne lancer ni `git fetch`/`--unshallow`, ni `kas shell`, ni nouveau build tant que la cause ne sera pas établie. **Si clone shallow confirmé**, proposer un correctif *borné au cache Git de meta-openembedded*, avec sauvegarde de références et retour arrière prévus, sans changer les SHA des fichiers OEM, et vérifier ensuite `merge-base` puis la porte KAS. Ce n'est pas une permission de nouvelle distribution/RAUC/P17.

Voir la [documentation Git sur les clones shallow](https://git-scm.com/docs/shallow), qui confirme que les frontières artificielles peuvent rendre l'ascendance invisible.
