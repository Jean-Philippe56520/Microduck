# PER-P15A — sonde de santé OEM à démarrage manuel, image de développement (31/10/2026)

## Porte 0 — utilité, preuve, limites, arrêt

Base de cette PR **empilée sur P14C/#231 HEAD `3bb83e3922d6a1db3d61cf2737a229bbcd99d604` (synchronisé avec le P14B final)**, elle-même dépendante de P14B/#230 HEAD `514e89ef10599c9177b056d3497915d92d6c1ec9`. `main` lu : `e4a0a1268c7335a84262824cade0d5df55c9c5ce`. OEM `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, Yocto `1ee58387810cebb67ae0d634c351d95024483bce`, OE-core `ae5a301091f5b0574ea7444aab40b309b6d9f3f2`. P8/#218 non validée, Qwen #97–99 fusionnées. Robot physique absent.

Le 31/10, l'opérateur a fourni **deux preuves distinctes** de P14B WSL2 : `P14B_EXIT_CODE=0` à la sortie du shell, et le validateur `status=bitbake_python_package_files_verified_only` avec **19 sources exactes vérifiées** et archive `85c583b86f0c8b5c59e9a547762a223c7ab27dee016c3ec604141907b20b2245`. Le validateur affiche **`bitbake_task_execution_attested_by_this_script=false`** : il ne se suffit pas à lui-même pour affirmer l'exécution. CI spécialisée #230 sur runner jetable demeure expirée/rouge ; #230/#231 sont brouillons. Aucun `do_rootfs` ni présence Python sur image ne découle de ce résultat.

**Manque prouvé** : P14B installe seulement 19 modules, dont `sim_ipc.read_health`, et aucun point d'entrée ni unité systemd. P15 complet exige des cycles de vie et replis ; commencer par une vérification **une seule fois**, pas un cerveau autonome ou une boucle motrice. **Succès minimal préalable au portage** : couche source DEV opt-in, service `Type=oneshot` sans `[Install]` (non activable au boot), import de la télémétrie P14A existante, **exactement un** RPC `robot.health`, réponse inconnue/timeout/absente => état `idle` sans action, sans mémoire et sans journal privé. L'action manuelle de démarrage ne sera proposée qu'après contrôle explicite des permissions et `do_rootfs` sur environnement approprié.

## Réutiliser / adapter / créer

| Matériel inspecté | Décision |
|---|---|
| OEM `robotd/systemd/robotd.service` au SHA épinglé : `/run/robotd.sock`, socket 0660, groupe `robot`, seul maître moteurs, `robot.health` côté OEM | **Réutiliser**, sans modifier robotd/robotctl/permissions OEM |
| `microduck_companion/sim_ipc.py` et 19 fichiers P14A, garde `_ALLOWED_READS` et `ReadOnlyUnixRpc(..., role='robotd')` | **Réutiliser** sans changement ; conserver la fermeture P14B |
| OEM Yocto images `microduck-image-dev.bb` / `microduck-image.bb` et système `inherit systemd` ; couches P14B/P14C | **Adapter** via couche séparée désactivable, bbappend de **dev seulement**, recette `kwipi-readonly-probe` |
| Nouvelle logique | **Créer uniquement** un `health_probe.py` one-shot, unité template, recette/couche DEV et fixtures tests. Ni DB ni caméra ni agent motorisé |

**Risque explicite de sécurité** : le groupe Unix `robot` est nécessaire pour contacter le socket 0660 ; **ce groupe ne donne PAS une permission OS de lecture seule**, il donne accès à toutes les méthodes RPC du socket, y compris celles de mouvement. Le code de cette sonde n'envoie que `robot.health` grâce au client P14A, mais cette garde applicative n'est pas une séparation matérielle ni une garantie contre du code compromis. Pour cette raison, P15A est **DEV uniquement, non démarré par défaut, aucune autorisation de déploiement sur le robot**. Aucun nouveau broker/ACL/contrôleur n'est créé par ce lot ; le passage production demanderait une revue sécurité spécifique du chemin de lecture.

## Fichiers et caractéristiques

- `yocto/meta-kwipi-p15-readonly/` : une recette `allarch systemd` fermée, unité manuelle et un `microduck-image-dev.bbappend`; **jamais** de bbappend shipping.
- Script Python en `${libexecdir}/kwipi/health_probe.py`, **en dehors** du paquet P14B, aucun 20e module installé dans `microduck_companion`; `RDEPENDS` sur `kwipi-companion` et runtime Python.
- `Type=oneshot`, `After=robotd.service` sans `Wants`/`Requires` pour ne pas démarrer le contrôleur en cascade, `TimeoutStartSec=4s`, timeout RPC 1 s, aucune boucle ni restart, `DynamicUser`, journal d'un seul statut de catégorie, pas de pourcentage de batterie, image, identifiant, SQLite ou détail de socket.
- Repli `idle_no_verified_telemetry` en cas de socket absent / erreur / délai ; `idle_reported_unhealthy` pour réponse OEM négative ; `reported_healthy_unverified` est **une déclaration non authentifiée**, jamais une permission de mouvement ni une validation physique.

## Tests positifs et négatifs préenregistrés

Positifs : un vrai socket Unix **factice** reçoit une seule méthode `robot.health` et sans paramètres ; réponse booléenne validée, pas de motor RPC ni écriture ; 19 sources P14A inchangées ; service uniquement DEV, aucun auto-enable ; comportement borné.

Négatifs : socket absent, timeout, JSON faux/non booléen, état unhealthy => idle ; aucune requête `robot.do` / `robot.move` / `robot.stop`, modèle, Qwen, SQLite, caméra, boucle, redémarrage automatique ; refus test en cas d'ajout `[Install]` ou `SYSTEMD_AUTO_ENABLE=enable`. **Test PC-fixtures seulement** : même si CI passe, ne pas annoncer paquet BitBake P15 produit, rootfs, service réellement lancé, contrôle de sécurité OEM physique, RAUC ou autonomie.

**Critère d'arrêt** : CI source/fixtures rouge, changement des 19 modules P14B, accès hors socket OEM, service activé en production/au boot, entrée réseau, media, mémoire, moteur ou changement de gitlink => rester brouillon, revert layer. Dépendances P14B et P14C non fusionnées => pas de tentative d'image P16 ni d'installation P15.

## P16/P17, séparés

P16 = vrai `do_rootfs` de l'image DEV, manifestes de paquets dont P15A **inactif**, signatures RAUC DEV, `rauc info`, retour arrière A/B ; **non exécuté**. P17 = qualification d'intégrité/version, limites/ressources et scénarios de défaillance, robot physique ensuite ; **non exécuté**. Voir `docs/per-p15-p17-v1-release-gates-2026-10-31.md` (PR #234). Aucun poids YOLO26/seg, sous-module, NPU, moteur ou clé ajouté.

## Résultats

Premier test réel **PC-fixtures** : [CI spécialisée #41212996494](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41212996494) verte au commit `4b9ffab7d169a75a70abb561a6949c6879e1128b`, **9/9 tests** après correction d'une assertion qui cherchait `[Install]` jusque dans un commentaire de l'unité. Un vrai serveur Unix **factice** a reçu exclusivement `robot.health` une fois, erreurs et données invalides ont produit `idle`, les 19 modules P14A sont restés identiques, unité non activée, aucune action motrice. Au même commit, CI Python générale et N1 sont vertes. **Tests spécifiques CI du dernier commit documentaire à revérifier avant fusion**, aucun BitBake P15A, `do_rootfs`, service OEM déployé, signature ou robot testé.


## Porte P15A-M — réel BitBake metadata, préenregistrée avant implémentation (31/10/2026)

**Problème concret** : P15A source et fixtures 9/9 verts, mais BitBake n'a pas encore chargé la recette `kwipi-readonly-probe`. Son `SRC_URI`, `inherit systemd`, `SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe`, le chemin `S`, les dépendances et son `IMAGE_INSTALL` réel pourraient différer du texte de recette ; le robot reste absent. L'objectif du lot est de **mesurer la résolution réelle** sous la configuration officielle Yocto figée, sans faire tourner la sonde ni modifier P14B/P13B2.

**Réutilisation** : workflow et vérificateur `PER-P14C` (#231) pour la construction de trois couches opt-in et le contrôle `microduck-image-dev` / `microduck-image`; `bbvar` P13A ; recettes OEM `microduck-image*.bb` au SHA `1ee58387`, OE `systemd.bbclass` et `allarch.bbclass` au SHA `ae5a3010`. **Adapter** uniquement la validation de la quatrième couche P15A et des nouvelles variables. **Créer** un validateur ciblé, ses négatifs et une CI de métadonnées ; aucun deuxième service, modèle, SDK, dispositif/capteur, moteur, base ou commande `do_rootfs`.

**Positif à démontrer** : `kas==5.2`, `bitbake -p`, `bitbake -e kwipi-readonly-probe`, `bitbake -e microduck-image-dev`, `bitbake -e microduck-image`, `bitbake-layers show-appends` contre pins identiques ; une seule recette de sonde depuis couche P15A, `PV=0.1`, `LICENSE=CLOSED`, `S=UNPACKDIR`, `RDEPENDS` contenant `kwipi-companion` et Python, `SYSTEMD_SERVICE=kwipi-readonly-probe.service`, `SYSTEMD_AUTO_ENABLE=disable`, couche P15A présente, `kwipi-companion` et `kwipi-readonly-probe` chacun exactement une fois dans **DEV**, tous deux absents de shipping. Aucun changement de `microduck-daemon` / `microduck-data`. Artefact de preuve JSON compact sans dump complet d'environnement.

**Négatifs à refuser** : couche P15A supprimée/substituée, recette hors couche, unité auto-enable, `LICENSE` modifiée, RDEPENDS absent, sélection deux fois, installation en shipping, perte de base OEM, `BBLAYERS` trompeurs, bbappend non reconnu. Toute modification d'OEM ou de ses gitlinks est interdite. **Arrêt/retour arrière** : BitBake absent, parse/echec/timeout, CI rouge ou signature de recette différente => garder #235 en brouillon, ne pas prétendre package, ne pas lancer `do_package` sur runner éphémère ni `do_rootfs`. Retrait = désélectionner la couche P15A. **P15A-M reste exclusivement un contrôle de métadonnées, jamais un paquet, un service actif ni une preuve robot.**

**Résultat** : en attente du vrai parse et de la CI sur le SHA final.


### Synchronisation P14B/P14C préalable à P15A-M

L'audit de dépendances de la PR #235 a prouvé que ses anciens parents #231/#235 contenaient encore la recette P14B `python_pep517`, **différente** de celle validée sur le poste WSL2. Les branches ont été synchronisées sans réécrire les 19 modules ni toucher aux gitlinks : P14B/#230 HEAD `514e89ef10599c9177b056d3497915d92d6c1ec9`, générateur source Git blob `214c41435d98c43b3b5772161affc913deed863b`, recette `inherit allarch python3-dir`; P14C/#231 commit `3bb83e3922d6a1db3d61cf2737a229bbcd99d604`. Cette correction **ne valide pas** l'installation ni le rootfs. Les CI P14C/P15A-M doivent être rejouées sur ces nouveaux commits.

La CI Python complète a aussi constaté que l'import de la sonde par une fixture déposait un `__pycache__/*.pyc` dans la couche source, faisant échouer un test de fermeture. Le test a été adapté pour empêcher cette génération transitoire ; les cinq fichiers de la recette restent strictement contrôlés et aucun `.pyc` n'est ajouté au paquet. Une faute de nom dans la première correction a provoqué un échec intermédiaire et a été corrigée ; seul le dernier SHA CI peut être utilisé comme preuve.

## Résultat réel P15A-M (31/10/2026)

[CI spécialisée #41214303436](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41214303436) **verte** sur HEAD `11aa1491d1deafed38239a6bd12835569cd36e09` après synchronisation de P14B `allarch python3-dir` et P14C. Exécution effective de `bitbake -p`, trois `bitbake -e` et `bitbake-layers show-appends` dans `kas==5.2` sur Yocto épinglé ; 8 tests négatifs de métadonnées, 9 tests du probe et 11 contrôles P14C réussis. Rapport JSON : `real_bitbake_p15a_metadata_dev_only_verified`, cinq fichiers source exacts, `p15a_dev_count=1`, `p15a_shipping_count=0`, `systemd_auto_enable=disable`, `python_modules_from_p14b=19`, `motor_commands_issued=0`. Les assertions `bitbake_package_run=false`, `rootfs_built=false`, `service_installed=false`, `signed_release=false`, `robot_validated=false` empêchent toute promotion trompeuse. Les CI du **dernier commit de documentation** doivent être revérifiées avant fusion ; cette PR reste draft/dépendante de #231/#230. Ne pas relancer P13B2/P14B sur runners éphémères.

## P15A-P — porte PKGDEST locale après do_package (31/10/2026)

**Observation WSL2 transmise par l'opérateur (et non CI/robot) :** `P15A_EXIT_CODE=0`, `bitbake -c package kwipi-readonly-probe` fini avec `do_fetch`, `do_unpack`, `do_compile`, `do_install`, `do_package` réussis ; 643 tâches tentées, 633 à jour, toutes réussies, 2 avertissements. La première tentative avait échoué avant BitBake à cause du chemin KAS ; seul le second essai réussit. Aucun besoin de recompiler P13B2/P14B. Les caches sont maintenus ; 633 tâches inchangées n'attestent pas la stabilité des ressources ni un rootfs.

**Manque avant P16 :** `PKGDEST` n'est pas visible depuis GitHub ; la sortie de BitBake ne révèle pas si le script, le service et le preset systemd présents dans `packages-split/kwipi-readonly-probe` sont conformes à la recette. Ne pas assimiler `do_package` réussi à « fichiers audités », ni service empaqueté à service installé ou démarré.

**Préenregistrement P15A-P, avant exécution sur WSL2 :** réutiliser le validateur `bbvar` P13A, la vérification de cinq blobs P15A-M et la classe constructeur `systemd.bbclass` OE épinglée (`ae5a3010`) : cette classe produit un preset `disable kwipi-readonly-probe.service`. Adapter uniquement à l'inspection du `PKGDEST` réel ; nouveau code permis : `scripts/per_p15a_yocto_package_gate.py` et fixtures positives/négatives. Test positif : `PN=kwipi-readonly-probe`, `PV=0.1`, `LICENSE=CLOSED`, vrai `FILE` sous couche P15A, `PKGDEST` dans `TMPDIR`, `SYSTEMD_AUTO_ENABLE=disable`, `RDEPENDS` conservées, 3 fichiers réguliers exacts en `0644`, script identique à la source, unité identique au template avec substitution de `libexecdir`, preset exact `disable`, aucune activation/commande moteur. Résultat cible : `bitbake_p15a_package_files_verified_only` sans prétendre au `do_package` observé par le validateur lui-même.

**Négatifs/arrêt :** fichier manquant/modifié, modèle ajouté, symlink, droits exécutables inattendus, service avec `[Install]`/`WantedBy`/`Requires`/`Restart`, commande remplacée, preset `enable`, couche/recette différente, `PKGDEST` extérieur à `TMPDIR`, licence promue ou dépendance Python manquante => STOP. Tests sur fixtures PC **ne valident pas WSL2** : exécuter une fois le validateur sur `proofs/p15a-verified.env`, sans écraser son JSON et sans relancer BitBake. Aucun paquet, modèle, service, rootfs, RAUC ou pilote OEM modifié par ce contrôle. Repli : ne pas sélectionner la couche P15A dans la future image.

**P16/P17** restent bloqués jusqu'à contrôle PKGDEST positif, puis `do_rootfs` DEV et vérification indépendantes ; aucune signature ni déploiement sur robot. Même avec fichier conforme, le groupe OS `robot` permet d'autres RPC : **pas de preuve d'isolement en lecture seule**, donc pas d'autorisation de démarrage production/robot.
