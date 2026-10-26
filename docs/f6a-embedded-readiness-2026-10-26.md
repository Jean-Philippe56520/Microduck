# F6-A — Préparation embarquée hors réseau, contrats OEM et persistance conditionnelle

**26 octobre 2026 — [PR #45](https://github.com/Jean-Philippe56520/Microduck/pull/45) fusionnée, niveau : inventaire documentaire et fonctions Python pures testées sur fixtures.** Le robot physique n’est pas disponible. Aucune unité systemd Companion n’est installée, aucun pilote constructeur n’est modifié, et aucune connexion à un socket OEM n’est effectuée par F6-A.

## 1. Sources de vérité inspectées

- [Microduck constructeur épinglé](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567), révision **`942e58e3aa6dbb28e7037203fff11866122c7567`**, telle qu’intégrée dans `upstream/microduck`. Référence de l’API : [`duck-ipc-proto/src/lib.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs). Un fournisseur peut publier une nouvelle version ; cette inspection ne prétend pas suivre automatiquement les changements.
- [Image Yocto constructeur](https://github.com/pollen-robotics/microduck_yocto/tree/91691234f3b518a94ee4391f8567c9486335f507), **snapshot documentaire `91691234f3b518a94ee4391f8567c9486335f507`** consulté pour ce lot. Il ne s’agit **ni d’une image installée sur le robot, ni d’un sous-module épinglé dans notre dépôt**. Voir [l’unité `var-lib-robot.mount`](https://github.com/pollen-robotics/microduck_yocto/blob/91691234f3b518a94ee4391f8567c9486335f507/meta-microduck/recipes-core/microduck-data/files/var-lib-robot.mount).
- Réutilisation de `microduck_companion/passive_sources.py` (sonde existante `mediad` **`hello` uniquement**, version API déclarée 44) et de `ExperienceMemory`, dont la valeur par défaut est déjà `:memory:`. Aucun nouveau module ne remplace ces fonctions.

## 2. Interfaces constructeur vérifiées **dans les sources**, non connectées sur robot

| Responsable OEM | Socket Unix documenté | Lecture potentielle | Niveau réel de l’intégration Companion |
| --- | --- | --- | --- |
| **`robotd`** | `/run/robotd.sock` | `hello`, `robot.health`, `robot.subscribe` (notifications `robot.state`) | **Aucune connexion par F6-A**, aucun adaptateur de commande physique. `robotd` reste seul responsable de la boucle moteur de 50 Hz et des protections constructeur. |
| **`mediad`** | `/run/mediad/media.sock` | `hello`, et dans le SDK constructeur `media.frame` (octets UYVY) | Seul **`hello`** est implémenté dans notre sonde F1-B ; F6-A n’appelle même pas cette sonde. Pas de flux de pixels, de chien/chat/personne ni de modèle embarqué. |
| **`tofd`** | `/run/tofd/tof.sock` | `tof.stream`, notifications `tof.frame` | Format inventorié mais **aucun lecteur live intégré**, aucun modèle spatial fiable ni détection d’escaliers. |

Ces méthodes appartiennent au JSON-RPC 2.0 constructeur, en messages NDJSON sur sockets Unix ; elles **ne garantissent pas** qu’un service est démarré ni qu’une version de firmware est compatible. La fonction `oem_manifest()` publie cet inventaire en marquant toutes les interfaces `connected=False` et `actuator_access_enabled=False`.

**Attention :** le constructeur diffuse `media.detections` sur une voie **WebRTC distincte**. L’URL du flux WebRTC et ses authentifications sont une question séparée ; un `hello` Unix local ne certifie aucune notification réseau. Le ToF frontal 8×8 n’est pas un LiDAR à 360° et ne prouve ni la sûreté des sols, ni l’évitement d’animaux mobiles.

## 3. Fonctions indépendantes du PC : objectifs et état effectif

Le cœur local souhaité doit continuer sans réseau : perception passivement bornée, motivations, choix des intentions `observe`, `inspect`, `listen`, `idle` ou `rest`, SQLite locale et corrections, suggestions sociales silencieuses par défaut et repli sûr si les capteurs sont absents. Ces comportements existent **en prototype sur observations fictives**, sans exécution physique des intentions. La reconnaissance de Nessquick, Kitty ou Malo, la navigation libre, les mots-clés audibles et les sons/mouvements réels sont **non validés**.

La branche PC/Ollama F5 n’est **pas une dépendance de démarrage**. Elle reste désactivée sans consentement explicite ; un avis Qwen ne peut commander les moteurs, devenir observation certifiée ou autoriser une zone. **F6-A n’installe, ne démarre ni n’arrête** de client Ollama ou d’autre service.

Le manifeste statique distingue en code `OFFLINE_FUNCTIONS` (fixtures), `OPTIONAL_PC_ONLY` et `NOT_IMPLEMENTED_ON_HARDWARE`. Ces noms sont **des statuts de capacité documentaire**, pas des promesses de fonctions actives sur RK3566.

## 4. Stockage Yocto : risque de fausse persistance

Le [montage du constructeur](https://github.com/pollen-robotics/microduck_yocto/blob/91691234f3b518a94ee4391f8567c9486335f507/meta-microduck/recipes-core/microduck-data/files/var-lib-robot.mount) est conditionnel : `ConditionPathExists=/dev/disk/by-label/data`, `What=/dev/disk/by-partlabel/data`, `Where=/var/lib/robot`, type `ext4`. **Si la partition est absente ou non formatée, systemd peut ignorer le montage et les services OEM peuvent encore utiliser des dossiers sur la partition système.** La simple présence de `/var/lib/robot` ne prouve donc **pas** l’existence d’un stockage persistant entre bascules A/B.

`embedded_readiness.py` expose deux validations *strictement déclaratives*, pour tester ultérieurement la procédure d’audit sans faire de lecture système dans notre banc :

1. `inspect_claimed_board(machine, compatible)` confronte les revendications fictives `microduck-zero3` / `radxa,zero3w-aic8800ds2` et `microduck-beta` / `pollen,microduck-beta`. Même un appariement fournit **`claimed_family_match`**, jamais une attestation physique.
2. `inspect_data_mount(mountinfo_text, partlabel_device=...)` exige une entrée canonique unique `/var/lib/robot`, une racine `/`, un `ext4` inscriptible **tant côté montage que superbloc**, et un chemin source exactement égal à une revendication de chemin de périphérique indépendante. Il refuse les données surdimensionnées, montages absents/ambiguës, racines de bind, overlay, lecture seule, formats erronés et sources contradictoires. **Il ne vérifie pas réellement le PARTLABEL** : il compare deux informations fournies par appelant sur des fixtures.

Si toutes les revendications correspondent, `StorageInspection.status` vaut uniquement **`persistent_mount_candidate`** et donne un chemin envisagé `/var/lib/robot/companion/experiences.sqlite3`, **jamais ouvert ni créé**. Dans tous les cas **`sqlite_selected = ":memory:"`** et **`installation_authorized = False`**. Les permissions du futur utilisateur, la capacité libre, la santé du système de fichiers, le montage effectif, la durabilité après coupure et la configuration de l’image devront être vérifiés **sur le robot physique** avant d’activer l’écriture durable.

La documentation Yocto beta décrit une carte à eMMC 64 Go et la Zero 3W sur SD ; les capacités annoncées, la partition persistante nominale de 8 Gio et la capacité libre ne doivent pas être confondues. **Aucune valeur d’espace libre n’est mesurée par F6-A.**

## 5. Démarrage, arrêt, permissions : contrat préparatoire, aucune unité installée

Avant l’éventuel déploiement F6-B/F6-C/F7, un service Companion **distinct** devra être évalué et arrêté proprement, sans interférer avec la disponibilité du daemon `robotd` ni charger les moteurs. Principes préparés, **non implémentés en service** :

- Ne pas ajouter de `Requires=`/dépendance réseau au service moteur. Ne pas modifier les unités ou règles d’accès constructeur `robotd`, `mediad`, `tofd` ; préserver la gestion constructeur des correctifs, des redémarrages et de la sécurité.
- Compte utilisateur et permissions minimales à valider. Pas d’accès direct au bus moteur, `/dev/ttyS*`, GPIO, envoi `robot.move` ou autostart d’un contrôleur alternatif. `robotd` reste le **seul** écrivain vers les moteurs.
- Mode initial sans PC ni autorisation de navigation, sans capture persistante d’images/voix. Les sockets de consultation ne seront ajoutés qu’après vérification du protocole et de la provenance ; aucun mot-clé fictif n’autorise un mouvement.
- Stockage SQLite dans une zone persistante **uniquement** après montage garanti, capacités/permissions mesurées, contrôle de cohérence et stratégie de fermeture/redémarrage validés. En cas de doute, rester inactif ou utiliser **le stockage volatil** pour les tests, sans promettre de mémoire inter-redémarrages.

**Compromis explicite :** F6-A n’est pas un service embarqué fonctionnel ; il fait gagner une spécification testable et réduit le risque d’écrire par erreur sur l’une des partitions système.

## 6. Tests et limites

`tests/test_embedded_readiness.py` vérifie sur fixtures : inventaire des trois services OEM et interdiction d’autorité moteur, familles de cartes compatibles/incompatibles, montage `ext4` attendu, montage absent, option lecture seule **superbloc ou montage**, erreur de chemin PARTLABEL, répertoires ressemblants, doublons, dépassement de taille, sortie JSON sans secrets, et impossibilité de promouvoir des revendications vers une installation, une perception réelle ou une navigation autorisée.

`python -m microduck_companion.f6a_preflight_demo` vérifie trois scénarios fictifs : absence de montage, présence du seul système de fichiers racine et faux montage `data` crédible. Le troisième ne conduit **pas** à une écriture durable ; la SQLite sélectionnée reste `:memory:`. La [CI de F6-A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40254981871) a réussi : **830 tests Python**, compilation et démonstration de faux montage réussis, **sans même lire le vrai `/proc/mountinfo` du runner**.

**Validation limitée :** aucune compilation Rust Yocto, aucune installation systemd, aucun socket constructeur contacté, aucun débit ni profil mémoire RK3566 mesuré. Aucun accès à une unité physique Microduck. Le script `scripts/resource-audit.sh` devra être exécuté sur robot réel au repos, puis en vision et seulement après sécurisation de la locomotion en mouvement. La branche F6-A n’augmente pas les capacités physiques.

**Suite F6-B :** comparer les coûts et la simplicité d’un futur noyau Rust minimal contre le prototype Python, **seulement lorsque les contraintes matérielles auront été mesurées**, en conservant toutes les frontières de sécurité constructeur. La validation de Qwen 4B/9B sur le PC reste une tâche distincte.
