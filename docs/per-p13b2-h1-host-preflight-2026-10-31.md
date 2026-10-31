# PER-P13B2-H1 — préflight hôte Yocto persistant, sans compilation (31 octobre 2026)

## Décision et preuves disponibles avant code

- Base `main@60e11c64d5b4ae531734e7182d3faf93f7807fcb`; OEM épinglé `942e58e3aa6dbb28e7037203fff11866122c7567`, simulation `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto OS `1ee58387810cebb67ae0d634c351d95024483bce` et OE-core `ae5a301091f5b0574ea7444aab40b309b6d9f3f2`.
- P11/#225 et P12/#226 sources et couche candidates, P13A/#227 vrai parseur vert, P13B1/#229 vrai `do_fetch/do_unpack` et six fichiers source vérifiés ; aucun `do_compile/do_package` ARM64 validé. P14A/#228 roue Python hôte, P14B/#230 ouverte en brouillon : `python_pep517` timeout [#41140552303](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41140552303) après **990/1006 tâches**, `allarch python3-dir` timeout [#41144655887](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41144655887) après **488/522 tâches**, erreur 124, aucune erreur démontrée des modules Kwipi. P14C/#231 ouverte en brouillon : `bitbake -e` dev/production vert, mais aucun `do_rootfs`.
- Qwen #97–99 fusionnées, P8/#218 fermée sans parité. Robot absent, licence YOLO26/poids non vérifiée, modèle non distribué, détecteur off par défaut.

**Manque prouvé :** le vrai `do_compile/do_package` nécessite plusieurs centaines de Go et un état des dépendances/sstate conservé ; le runner éphémère recommence la compilation d'outils natifs (OpenSSL/CMake), ce qui échoue au timeout sans attester le paquet. L'OEM prescrit explicitement `KAS_BUILD_DIR`, `DL_DIR`, `SSTATE_DIR` persistants et `kas-container` pour le build ; son `scripts/build-local.sh` appelle `daemon-release.sh` qui résout un **release constructeur différent**. Ce wrapper ne doit PAS écraser la source/version candidate P12, ni recréer les crates amont en modifiant un fichier suivi.

## Objectif du lot H1 et matrice réutiliser/adapter/créer

**Objectif borné :** un **contrôle local lecture seule** qui vérifie les SHA et la couche P12, les répertoires séparés du code, le matériel/stockage suffisants pour une construction Yocto longue, les outils disponibles, et qui distingue `host_resource_preflight_passed` de toute preuve BitBake. Pas de build automatisé, ni `sudo`, ni réseau, ni disque écrit, ni droits matériels. Testé en fixtures PC et contrôlé par CI. Ce lot ne relève pas le nombre de fonctionnalités livrées.

| Réutiliser | Adapter | Créer |
|---|---|---|
| `scripts/per_p11_v1_source_release.py`, `scripts/per_p12_yocto_layer.py.verify/check_yocto`, la couche `meta-kwipi` et `kas/microduck.yml` OEM, `scripts/resource-audit.sh --plan` pour les besoins matériel ultérieurs | La manière de préparer une chaîne `kas shell` **sans** exécuter `scripts/build-local.sh` (qui injecterait la release OEM) ; vérifier `bitbake -e` avant compilation | `scripts/per_p13b2_host_preflight.py` et fixtures `tests/test_per_p13b2_host_preflight.py` ; courte CI syntaxe/positifs/négatifs |

## Seuils de décision **préenregistrés**, pas des minima fabricant

- Linux x86_64, au moins **4 CPU**, **16 Gio de RAM totale et 8 Gio disponibles**. Ce sont des seuils de lancement prudents de notre essai, **pas des spécifications OEM**, sans déduction de vitesse.
- Répertoires existants et canoniques `KAS_BUILD_DIR`, `DL_DIR`, `SSTATE_DIR`, extérieurs aux dépôts et à la couche. Exiger **200 Gio libres pour `TMPDIR`**, **30 Gio pour les téléchargements**, **60 Gio pour le cache sstate** ; pour des chemins sur le même système de fichiers, **additionner ces réserves** (exemple 290 Gio disponibles sur un disque commun) plutôt que compter le même espace trois fois.
- SHA `git` OEM/RL/Yocto exacts, répertoires non symlinkés, couches P12 exactes et manifest SHA source P11 sans nouveaux poids. `kas`/git détectables sur PATH, aucune authentification SSH exigée puisque P12 source file tar, `bmi088` téléchargé en HTTPS.
- P13B2 ne doit jamais appeler `scripts/build-local.sh` ni un `daemon-release.sh` de substitution ; la couche P12 épinglée fournit `SRC_URI`, `PV`, `SRCREV` et 568 crates. Avant compilation effective, exiger séparément `bitbake -e microduck-daemon` et `bitbake-layers show-appends`, puis `do_compile`, `do_package`, vérification ELF AArch64/ressources et aucun fichier secret.

**Négatifs à tester** : SHA amont ou vendor différent, couche P12 altérée, symlink / chemin de build dans dépôt, disque partagé compté plusieurs fois, 1 CPU / mémoire ou mémoire disponible insuffisante, exécutable kas absent, politique reformatant les sources, statut `ready` donné malgré absence d'outil. Échec = `blocked`, sans lancer de commande moteur, réseau ni BitBake, aucune modification de `upstream/`.

**Arrêt** : si les tests et CI de cette porte ne sont pas verts, rester en PR. Si la machine adaptée n'est pas disponible, **`P13B2/P14B = inconnu/en attente`**, ne pas ajouter une troisième tentative CI éphémère ni simuler un ELF. La validation physique 50 Hz, NPU, image/dev, RAUC signée et autonomie restent hors de cette porte. Retour arrière : supprimer le préflight (aucun système/sous-module touché). Licences et secrets avant P16.

## Résultats

En attente de la CI source-only et de son inspection. `--plan` ne mesure rien, `--check` ne lance aucun build, même quand il passe.
