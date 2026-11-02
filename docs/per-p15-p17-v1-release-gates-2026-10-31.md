## P17-S0 — réconciliation des preuves V1 après P16-B10/S1/S2 (02/11/2026, décision documentaire)

**Objectif / manque concret :** éviter d'annoncer une « image V1 prête » en additionnant des contrôles qui ont porté sur **deux artefacts différents**. Référence `main@1e44ec0b7e60a354a19aede3c4e7281e8e77a310` après fusion #265 ; gitlinks OEM `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et simulation `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` inchangés. Réemploi des rapports P16 déjà produits et de la matrice P15–P17 existante ; **aucun nouvel utilitaire ou PR de code nécessaire pour ce constat**.

| Porte / objet effectivement vérifié | Verdict borné | Ne prouve pas |
| --- | --- | --- |
| Rootfs DEV B10 (nouvelle composition P15-B9/B10) | P16-B10 `PASS_FILES_ONLY` : 24 Python, 2 ELF B12, 3 fichiers P15A, compte isolé et manifeste DEV | WIC reconstruite avec B10 ou boot réel |
| Services/présélections du même rootfs B10 | P16-S1 `P16_S1_EXIT=0` : 226 autres fichiers systemd, 17 presets, 0 référence d'autoactivation P15A, 0 postinst différé dans les répertoires connus | Scriptlets de tous les RPM, état service au démarrage, ACL du socket moteur |
| RAUC/configuration et modes du même rootfs B10 | P16-S2 `P16_S2_B10_EXIT=0` : 2 CA, 11 champs, 5 modes, groupe `robot` présent | Paire privée de signature, bundle signé/validé, rollback A/B |
| WIC DEV privée qualifiée au 31/10 (12 968 805 376 octets, SHA-256 `c1140e7508559ebc9467c3f97d3c9891452228f05b3baf999ccaa3c0a5f11bc8`) | Intégrité/GPT historiques PASS sur WSL2 ; `rootfs_a` de cette WIC avait **absence du compte kwipi** | Installation du nouveau rootfs B10 ; la WIC historique **n'est pas** la V1 avec B9/B10 |
| RAUC DEV signé, image shipping, licences, runtime P15 complet, robot | **EN ATTENTE** : clés privées DEV non attestées, redistribution `CLOSED` à revoir, P15A oneshot inactif, B6 lanceur de fixtures | Déploiement, autonomie, lecture seule OS, sûreté physique et ressources RK3566 |

**Critères de poursuite (préenregistrés, avant tout nouvel essai P17) :** positif = identifier un seul candidat versionné et **rattacher par empreintes** sources, manifeste, paquets, rootfs, WIC et recette de démarrage effectivement correspondants ; vérifier séparément les scriptlets RPM pertinents, droits d'accès et stratégie de repli, sans prétendre les avoir testés ici. Négatifs/STOP = WIC historique présentée comme contenant B10 ; CA publiques interprétées comme clés de signature ; `robot` interprété comme ACL RPC lecture seule ; entrée de fixture présentée comme Companion autonome ; `status=accepted` présenté comme effet moteur ; sortie S1/S2 interprétée comme validation d'une image shipping/robot. **Prochaine action utile sans robot :** inventaire P17 **lecture seule** de la correspondance artefacts/dev-rootfs et des scriptlets existants, en réutilisant les manifestes/pkgdata/recettes OEM ; **pas de BitBake ni de nouvelle WIC tant que l'écart précis, le budget et les critères de la prochaine construction ne sont pas établis**. P15 service réel sûr est une porte indépendante et demeure ouverte. Retour arrière = conserver le rootfs B10 et la WIC ancienne privés, ainsi que leurs rapports, sans les remplacer.

# PER-P15–P17 — portes de livraison V1 après P14B (31 octobre 2026)

## Preuves et arrêt avant essais

Base `main@e4a0a1268c7335a84262824cade0d5df55c9c5ce`; OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, Yocto `1ee58387810cebb67ae0d634c351d95024483bce`, OE-core `ae5a301091f5b0574ea7444aab40b309b6d9f3f2`. Lire `AGENTS.md`, `docs/plan-action.md` (autorité), `docs/development-reuse-protocol.md`, les recettes OEM et les PR #230/#231/#233 avant tout changement. PR Qwen #97–99 fusionnées ; P8/#218 sans parité. Aucune validation robot.

P13B2 est **rapporté réussi sur le poste WSL2 de l'opérateur** : `bitbake -c compile/package microduck-daemon` exit 0 et deux ELF AArch64 dans PKGDEST (preuves privées de PR #233, fusionnée le 31/10/2026). Ne pas recompiler P13B2 sans écart nouveau. **Depuis le dernier état de cette PR**, P14B local a franchi ses deux critères : `P14B_EXIT_CODE=0` (shell) et `bitbake_python_package_files_verified_only` (validateur 19 fichiers, SHA archive/source conformes). Le JSON annonce `bitbake_task_execution_attested_by_this_script=false` ; il ne constitue pas à lui seul une preuve de la tâche BitBake. #230/#231 restent brouillons ; leurs essais P14B CI éphémère ont expiré, indépendamment du succès WSL2. Aucun rootfs, service installé, signature ou robot validé.

**Porte P14B impérative, avant nouvelle commande BitBake** : lire sur **l'hôte WSL2 réel** `~/kwipi-build-v1/proofs/p14b-package.log`, `p14b-package.json` et l'éventuel `P14B_EXIT_CODE`; vérifier journal complet, `PKGDEST` et **19 fichiers Python/source SHA exacts** via le validateur P14B. Résultat positif uniquement avec `P14B_EXIT_CODE=0` et `bitbake_python_package_files_verified_only`. Si fichier absent, journal incomplet, échec ou dépendances déplacées : **inconnu/STOP**, pas de relance automatique. Les fichiers WSL2 ne sont pas accessibles par le connecteur GitHub.

## Réutiliser / adapter / créer

| Réutiliser, source épinglée | Adapter seulement après preuve | Ne pas créer |
|---|---|---|
| OEM `robotd`, `robotctl`, `mediad`, systèmes d'arrêt et sockets ; `sim_ipc.py` lecture seule P14A et 19 modules ; service OEM et politiques existantes à auditer | P15 : démarrage minimal opt-in et observabilité sans actionneur | Second pilote, arbitre moteur, socket caméra, SQLite concurrente, service réseau, commande Qwen motrice |
| OEM `meta-microduck/recipes-core/images/microduck-image-dev.bb`, `microduck-image.bb`, `recipes-core/bundles/microduck-bundle.bb`, `microduck-bundle-shipping.bb`, `recipes-core/rauc/files/system.conf` | P16 : image dev uniquement puis RAUC de test sous autorisation et clés adaptées | Secret ou clé privée dans dépôt, production `IMAGE_INSTALL` sans droits, substitution OEM, bypass signature |
| CI Python/P14C, audits ressources et QA constructeur | P17 : matrice version/artefacts/installations/repli en environnement non robot | Inférer RAM, NPU 2 Hz, moteur 50 Hz, navigation ou sûreté physique depuis WSL2 |

## P15 — service Kwipi non moteur, porte préenregistrée

**Manque** : P14A fournit des modules et P14B vise le paquet ; aucun processus Kwipi ni cycle de vie prouvé. **Positif cible** : après P14B et P14C attestés, installation contrôlée sur image **dev** seulement ; processus sous utilisateur sans privilèges moteurs, sans activation automatique initiale, lecture seule des API OEM déjà autorisées, `idle` si socket/senseur manquant, arrêt SIGTERM/restart borné et journal sans média privé. Vérifier le véritable code/contrat de lancement disponible (aucun point d'entrée présumé). Tests : démarrage, health, absence de capteurs, désactivation, exception, ordonnance arrêt, refus RPC moteur, aucune nouvelle base ni deuxième capture ; séparer test fixture, rootfs et robot.

**Arrêt** : P14B non prouvé, aucune entrypoint fiable, requête moteur, log secret, perte du repli ou redémarrages incontrôlés => pas d'unité activée, pas d'image installable. Retour arrière = retirer la couche de service opt-in / désactiver la seule unité candidate ; OEM inchangé. **Statut : prévu, non codé, non testé.**

## P16 — image dev, rootfs et RAUC, portes préenregistrées

**Manque** : P14C a seulement démontré via BitBake `IMAGE_INSTALL` pour `microduck-image-dev`, jamais `do_rootfs` ; aucun bundle Kwipi ni signature validée. Les deux recettes OEM de bundle diffèrent : `microduck-bundle.bb` cible `microduck-image-dev`, `microduck-bundle-shipping.bb` cible `microduck-image`, format verity et rootfs ext4 ; les clés privées restent dans un répertoire de build, pas dans Git. Ne pas mélanger dev et shipping.

**Positif cible** : avec dépendances P13B2/P14B/P14C/P15 vérifiées, `bitbake -e` pour les deux images et les bundles, puis vrai `do_rootfs` DEV ; inspecter la liste de paquets/versions et les 19 sources, le service inactif par défaut et les contrôles rootfs ; ensuite **sur machine autorisée avec clés de développement privées hors dépôt**, bundle RAUC dev, `rauc info`/vérification de signature, compatibilité machine, install-check/hook et stratégie de retour arrière de slots sur banc approprié. Le test d'installation sur robot ne peut avoir lieu avant réception et supervision.

**Négatifs** : module absent, production contaminée, clé dev dans shipping, secret committé, bundle sans signature ou avec machine incompatible, hook invalide, absence de possibilité de repli => STOP. Aucun raccourci depuis `do_package` vers `do_rootfs`/RAUC signé. **Statut : prévu, non construit, non signé, non testé.**

## P17 — qualification et décision V1

Préenregistrer avant essais un manifeste reproductible (SHA de code, gitlinks inchangés, source P11/P12, paquet Rust/Python, recettes, image dev, signature/certificat public, révision OEM) et des cas négatifs. Vérifier CI finale au HEAD de chaque PR, inventaire complet source et `PKGDEST`, parité versions OEM, démarrage/arrêt/repli, refus commande moteur, données/privacité/SQLite, ressources disque et régression de l'image production. Sur robot futur seulement : `robotctl version/health/policy list/monitor`, ressources et température, comportement `robotd` 50 Hz, inférence NPU 2 Hz, risques physiques, arrêt et retour arrière, sans désactiver la sûreté.

**Conditions de sortie V1 pré-robot** : paquets cibles prouvés, image DEV produite et auditée, service sûr non moteur effectivement testé sur cible simulée appropriée, bundle dev signé/vérifié et retour arrière documenté ; licences et versions gelées. **À ne pas annoncer** : 95–100 % d'autonomie/interaction réelle, performance NPU ou sûreté matériel en absence du robot. Si une porte échoue : état `inconnu/en attente`, correction ciblée puis retest ; ne pas fusionner une PR rouge.

## Statut de cette PR documentaire

Préenregistrement **uniquement**. Aucun code, couche, sous-module, modèle, clé, moteur, média, robot, BitBake ou image modifié. Les tests des futures étapes sont des **critères à exécuter**, et non des tests passés. Ce document ne dépend pas d'un résultat supposé de P14B.
## Premier jalon P15A en branche dépendante, preuve PC uniquement

La [PR #235](https://github.com/Jean-Philippe56520/Microduck/pull/235) ajoute une **sonde `robot.health` ponctuelle** et une unité systemd **désactivée** dans une couche Yocto **réservée à l'image DEV** (empilée sur #231). Les tests de faux socket, de refus et de source P14A ont une [CI spécialisée verte](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41212996494) après correction d'une assertion confondant commentaire et véritable section `[Install]`. Python général et inventaire N1 sont verts au HEAD `4b9ffab7d169a75a70abb561a6949c6879e1128b`. Cela prouve du code testé **PC-fixtures**, ni un paquet BitBake P15, ni une unité installée, ni la sûreté OS des privilèges du groupe `robot`, ni le cycle de vie d'un compagnon actif. Les portes P16/P17 demeurent bloquées par les preuves `do_rootfs`/RAUC/robot manquantes.
