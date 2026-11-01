# PER-P14C — installation uniquement dans l'image de développement (30/10/2026)

## Objectif, écart, décision avant essai

Base proposée : PER-P14B [PR #230](https://github.com/Jean-Philippe56520/Microduck/pull/230), encore **brouillon**, CI BitBake `do_package` non validée au démarrage de ce lot. PER-P13B1 [PR #229](https://github.com/Jean-Philippe56520/Microduck/pull/229) fusionnée, `main@60e11c64d5b4ae531734e7182d3faf93f7807fcb`. OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, OS `1ee58387810cebb67ae0d634c351d95024483bce` et oe-core `ae5a301091f5b0574ea7444aab40b309b6d9f3f2` restent épinglés. Qwen #97–99 fusionnées, P8/#218 sans parité validée. Le plan `docs/plan-action.md` fait foi.

**Manque attesté :** OEM `meta-microduck/recipes-core/images/microduck-image.bb` installe les daemons constructeur mais pas le candidat `kwipi-companion`. `microduck-image-dev.bb` réutilise cette image et ajoute des outils/root d'administration ; **même une recette P14B construite n'est installée dans aucune image**. Le vrai `microduck-image` est une image de livraison dont les droits des sources Kwipi ne sont pas encore clarifiés ; il ne faut pas l'altérer.

**But mesurable de cette seule porte :** la résolution **effective** de `IMAGE_INSTALL` sous le vrai BitBake inclut `kwipi-companion` une fois dans `microduck-image-dev` et **zéro fois** dans `microduck-image`. Un `bbappend` dirigé **uniquement** vers le vrai fichier OEM `microduck-image-dev.bb` effectue ce changement dans une couche distincte explicitement optionnelle. Aucune compilation de rootfs ni boot, aucune activation de service ni écriture SQLite. C'est une **preuve de choix d'image, pas la preuve d'installation dans une rootfs**.

## Matrice réutiliser / adapter / créer

- **Réutiliser :** `microduck-image.bb` et `microduck-image-dev.bb` OEM à leurs blobs `6ee5d14f7a8ebca2441bdff525ce41705bec935e` et `ec7fa8f82b7685a7da1807c2fee597f9e98e4f8d`; couche P12 `microduck-daemon` version/source exactes et P14B paquet Python fermé, et `kas/microduck.yml` constructeur.
- **Adapter :** une couche `meta-kwipi-dev-image` opt-in composée des deux seuls fichiers `conf/layer.conf` et `recipes-core/images/microduck-image-dev.bbappend` ; pas d'édition de sous-module ni de recette amont.
- **Créer :** un seul validateur du contenu exact de la couche et des deux `bitbake -e` effectifs, tests refusant les changements non autorisés.

## Critères positifs et négatifs

**Positifs :** l'image dev a exactement un `kwipi-companion` dans `IMAGE_INSTALL`, l'image produit zéro ; chacun conserve `microduck-daemon` et `microduck-data` ; couche `kwipidev` résolue dans `BBLAYERS` sur image dev, fichier `.bbappend` reconnu par `bitbake-layers show-appends` ; le paquet `kwipi-companion` provient toujours de la couche Python P14B sélectionnée, pas d'une substitution ; `IMAGE_FEATURES` de prod ne contient pas les facilités de connexion de dev ; `bitbake -p` réel réussit sur OS figé.

**Négatifs :** installation sur `microduck-image`, substitution du daemon OEM, suppression de `microduck-data`, ajout de paquets non autorisés, bbappend de nom `_%.bbappend` ne correspondant pas à l'amont, absence de couche/source, `BBLAYERS` falsifiés, `IMAGE_FEATURES` root dev dans prod, existence d'un service Kwipi ou d'une activation motrice : refus avant fusion.

## Sûreté, licencing et arrêt

La licence des sources du projet Companion n'est pas explicite ; P14B maintient `LICENSE = "CLOSED"`. Même ce prototype dev ne vaut pas permission de redistribution. P8 parité et droits YOLO26 restent non prouvés et les poids ne sont pas embarqués. La couche et le choix d'image ne modifient pas `robotd` ni les gitlinks. Si P14B n'a pas de paquet réel `do_package` vérifié, **ne pas considérer P14C comme capable d'installer du Python**, même si sa résolution `IMAGE_INSTALL` est correcte. Si BitBake manque de disque, consigner le blocage, sans contournement de protection.

**Seuil final :** tests source + `bitbake -p/-e` exacts sur les deux images + CI Python générale verte sur SHA final ; aucune fusion avant succès. La construction réelle `do_rootfs`, le package P13B2 ARM64, la mise en route P15, la signature RAUC P16 et P17 restent séparés. Retour arrière : retirer la couche `kwipidev` des couches KAS ; ne modifier aucun flash, slot ni mémoire.

## Résultats

En attente des CI et de la réussite indépendante P14B.


## Réconciliation de dépendance P14B — 31/10/2026

La PR #231 avait été créée depuis la première version `python_pep517` de P14B. **Cette version n'est pas celle que l'opérateur a validée sur WSL2.** Après audit des blobs, le parent P14B/#230 HEAD `514e89ef10599c9177b056d3497915d92d6c1ec9` a été intégré à la branche P14C, au commit de synchronisation `6129c971f46e5a449a3031fb78886bd9a9ad352d`, sans changer les six fichiers P14C. Le code P14B hérité est désormais exactement `inherit allarch python3-dir` (blob de recette-générateur `214c41435d98c43b3b5772161affc913deed863b`) et **non** `python_pep517`.

Preuves indépendantes : sur WSL2, l'opérateur a fourni `P14B_EXIT_CODE=0` et `bitbake_python_package_files_verified_only` pour les 19 sources du SHA #230, avec `bitbake_task_execution_attested_by_this_script=false`. La CI P14B éphémère est encore rouge par délai ; sa réussite locale ne constitue pas une signature, une licence ni un paquet installé. La CI P14C originale [#41142993543](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41142993543) avait prouvé seulement le choix de l'image sur l'ancien parent ; **revalider le parse P14C sur la branche réconciliée avant fusion.** Aucun `do_rootfs`, `.wic`, unité, RAUC ou robot testé. La PR P15A/#235 doit hériter de ce nouveau parent ; pas de fusion dans le désordre.

## Reprise P14C après fusion squash P14B — 01/11/2026 (porte avant correctif)

Le parent P14B est fusionné dans `main@c2227dd2daf7e61930e9c967c6d226ee9469ab55` : CI GitHub Python et métadonnées BitBake vertes, `do_package` prouvé séparément via WSL2. P14C doit suivre ce commit **sans réintroduire l'ancienne version** de `.github/workflows/per-p14b-yocto-python-package.yml` : sa branche a reçu un commit de réconciliation à deux parents `a1898cd3e8972ab586f75f701adca1213bd44582`, dont l'arbre est la version fusionnée de `main` **plus uniquement les six fichiers P14C originaux** ; la base de PR #231 est maintenant `main`.

**Écart de sûreté observé dans notre CI, à corriger avant fusion.** Le workflow P14C redirige `bitbake -e` DEV et shipping vers des fichiers dans `/tmp` sans créer préalablement les fichiers en `0600`. Cet environnement peut contenir des empreintes de mot de passe OEM ; ne pas publier ni laisser lire les valeurs complètes. P15-B9/P15-B10 démontrent déjà le réemploi d'une création privée préalable avec `umask 077`, tout en conservant l'`umask 022` requis par BitBake.

**Objectif et critère avant essai.** Adapter uniquement le workflow P14C pour (1) refuser tout chemin de sortie préexistant ou symbolique ; (2) précréer les fichiers `DEV_ENV`/`SHIP_ENV` en mode `0600` **avant** la redirection ; (3) vérifier mode `0600` après BitBake et avant lecture par le gate ; (4) garder un seul rapport JSON borné sans secret en artefact ; (5) maintenir exactement la sélection `kwipi-companion` en DEV et zéro en shipping. **STOP** si une permission est incorrecte, si `bitbake -p/-e` ou les négatifs de sélection échouent, ou si la CI générale n'est pas verte. Le témoin est la même recette/source et les mêmes tests positifs/négatifs P14C ; aucun nouveau `do_package/do_rootfs`, pilote, service, ACL, robot ou image. Retour arrière : laisser la PR brouillon, retirer seulement la nouvelle protection CI si elle se révèle incompatible, jamais désactiver les garde-fous OEM.