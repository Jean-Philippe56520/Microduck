# P15-B18 — sélection facultative DEV du lecteur B12, audit BitBake (02/11/2026)

## Objectif, écart, observation et hypothèses fixés avant implémentation

**Baseline vérifiée** : `main@13245ca53159132e2d4d94112488055011f2c9bd`, PR #271 fusionnée ; gitlinks constructeur `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et simulation `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` ; source Yocto OEM `1ee58387810cebb67ae0d634c351d95024483bce`, OE-core `ae5a301091f5b0574ea7444aab40b309b6d9f3f2`. Qwen PR #97–99 fusionnées mais non utilisées.

**Objectif concret** : prouver qu'une **nouvelle configuration DEV opt-in**, non une image nouvelle, sélectionne exactement une fois le paquet `kwipi-b12-receiver` (les quatre modules B13–B16 de B17) avec les 24 modules B10, les paquets OEM, le compte isolé `kwipi` et aucune sélection dans `microduck-image` shipping.

**Écart démontré** : B17 a livré un paquet **source non sélectionné** (`scripts/per_p15b17_oem_receiver_package.py`, [PR #271](https://github.com/Jean-Philippe56520/Microduck/pull/271), tests source 12/12 et CI 6/6). P15-B10 fournit déjà une couche facultative d'image DEV (19+5). Aucune couche sélectionnant B17 ni preuve `bitbake -p/-e` de `kwipi-b12-receiver` n'existent à cette baseline. Ne pas refaire P14B/B6/B10 ni recompiler les binaires OEM B12 déjà audités.

**Observation OEM** : `mediad.service` épinglé exécute `/opt/robot/daemon/current/bin/mediad` sans `--kwipi-local-detections` ; `DuckDetectorParams::default().enabled=false`, `hz=2.0`. Le producteur et le détecteur restent **inactifs par défaut**. La sélection du lecteur ne déclenche aucun accès `/run`, aucune capture, aucun moteur, aucun SQLite. L'ACL du robot, le modèle RKNN, le binaire réellement exécuté, le rebind et l'identité auto-déclarée ne sont pas vérifiés par cette qualification.

**Hypothèse testable** : la couche facultative contenant uniquement `layer.conf` et un bbappend `microduck-image-dev.bbappend` sera reconnue par BitBake OEM épinglé. Ce test ne prouve pas que des fichiers ont été installés ni que Python AArch64 peut importer les quatre modules.

## Matrice réutiliser / adapter / créer

- **Réutiliser sans modification** : `scripts/per_p15b10_dev_passive_env_gate.py::source_gate/validate/_require_dev_only_append/_private_env`, `per_p15b17_oem_receiver_package.py::verify`, P14C et P15-B9 pour les images/identités, les recettes P11/P12, le workflow B10 KAS exact. B17 reste l'unique paquet à quatre modules, B10 l'unique référence historique 24 modules ; aucun recopiage de l'API B16.
- **Adapter** : une nouvelle sélection *facultative* sous `yocto/meta-kwipi-p15-b12-receiver-selection` et une petite extension de garde dédiée qui compose les vérificateurs existants, sans altérer leurs contrats.
- **Créer au strict nécessaire** : un garde B18 d'image et de recette metadata, ses tests négatifs, un workflow KAS/BitBake `-p/-e` sans tâches de build et cette fiche. Aucun sous-module OEM, fichier service, modèle, capture, permission ou robot modifié. Références communautaires C3 sans apport logiciel justifiant une nouvelle dépendance.

## PASS/STOP préenregistrés

**PASS sources/fixtures** : (1) exactitude des deux fichiers du nouveau layer, pas de symlink ni de recette shipping ; (2) source B17 reproductible 4 modules, P14B/B6 19+5 conservés, `LICENSE=CLOSED`, dépendances déjà prévues ; (3) fausses métadonnées `IMAGE_INSTALL` DEV 19+5+4, shipping 0 Kwipi, `BBLAYERS` complets, `show-appends` DEV seulement ; (4) compte `kwipi` privé, verrouillé, sans groupe moteur, groupe opérateur OEM préservé ; (5) `SRC_URI`, `PV/PN`, `LICENSE`, `PACKAGE_ARCH`, `S/BP/UNPACKDIR`, `PYTHON_SITEPACKAGES_DIR`, SHA effectif et dépendances du paquet B17 conformes ; (6) CI Linux et suite Python générale vertes au SHA final.

**PASS BitBake distinct** : une GitHub Action doit **réellement** installer les prérequis KAS épinglés et appeler `bitbake -p`, `bitbake -e microduck-image-dev`, `bitbake -e microduck-image`, `bitbake -e kwipi-b12-receiver`, `bitbake-getvar ... SRC_URI` (SHA nommé) et `bitbake-layers show-appends` sur la pile immuable. Le vérificateur lit les sorties privées et produit un résumé expurgé sans secrets.

**Négatifs/STOP** : B17 absent/altéré, couche absente/dupliquée ou modifiée, image shipping contaminée, module B6/base supprimé, compte `kwipi` autorisé au groupe `robot`, recette non reconnue, `SRC_URI` supplémentaire, SHA/nom/version erronés, `RDEPENDS` insuffisants, source non immuable, bbappend caché sous une recette shipping ou permissions plus larges ; échec de CI ou BitBake ⇒ ne pas fusionner. Un échec d'outil absent est un manque à diagnostiquer, pas une permission pour contourner les protections. Aucun secret environnemental publié.

## Statut et limites

**Préenregistrement avant implémentation/CI.** La réussite de tests synthétiques signifie `test_logiciel_seul`. Une réussite réelle de `-p/-e` signifie **métadonnées BitBake effectives vérifiées**, PAS `do_unpack/do_package/do_rootfs`, ni installation sur DEV, WIC/RAUC, signature ou robot. Le rootfs historique P16-B10 (24 modules, deux ELF et trois fichiers P15A) reste **immuable**, ses rapports/empreintes sont hors portée. Activation producteur, service OEM, ACL, capteur et ressources RK3566 restent des portes ultérieures.

**Retour arrière** : enlever seulement la couche B18 facultative et les scripts/tests/documentation de cette PR ; ne pas changer P14B/B6/B10/B17 ni la version Yocto, le système de paquets OEM ou les artefacts opérateur WSL2.
