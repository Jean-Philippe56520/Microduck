# P15-B19 — qualification réelle `do_package` de la réception B12 (02/11/2026)

## Objectif et preuve du manque, avant essais

**Base confirmée** : `main@4d4a1d458d53a43d74258d77c8b0e141b956258b`, PR #272 fusionnée. Gitlinks **inchangés** `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Yocto OEM épinglé `1ee58387810cebb67ae0d634c351d95024483bce`, OE-core épinglé `ae5a301091f5b0574ea7444aab40b309b6d9f3f2`. Qwen PR #97–99 fusionnées et hors trajet.

**Écart prouvé** : B17 produit les quatre modules B13–B16 sous une recette privée `kwipi-b12-receiver` vérifiée par source/empreinte. B18 a vérifié par **véritable** KAS/BitBake `-p/-e` la sélection DEV=1, shipping=0, les RDEPENDS et la somme nommée. Mais aucun `bitbake -c package kwipi-b12-receiver` ni contenu réel `PKGDEST` du nouveau paquet n'a été qualifié. Le seul rootfs DEV B10 audité contient **24 modules (19+5)** ; ses deux ELF B12, trois fichiers P15A, comptes et rapports opérateur ne doivent pas être touchés.

**Gain** : prouver la **fabrication du paquet et les quatre fichiers Python exacts dans le split réellement produit**, sans construire d'image ni démarrer `mediad` ; refuser les fichiers ajoutés, remplacés, exécutables ou les chemins trompeurs. Une réussite est un paquet BitBake vérifié sur runner Linux, **pas une installation** dans un rootfs DEV, pas une validation du Python AArch64 exécuté ni une preuve capteur.

## OEM et choix réutiliser / adapter / créer

Les versions OEM épinglées restent le comparateur. `mediad.service` lance `mediad` sans `--kwipi-local-detections` ; `DuckDetectorParams::default` a `enabled=false`, `hz=2.0`. Ne pas activer détecteur, service, modèle, moteur ni réseau. `robotd` demeure seul pilote. Aucune modification OEM/Yocto, aucun déplacement des sous-modules, aucune seconde mémoire SQLite ou pilote.

- **Réutiliser tel quel** : B17 `verify` et archives SHA 19+5+4, B18 `source_gate/validate` et KAS opt-in vérifié, B6-P `scripts/per_p15b6_bitbake_package_gate.py` (référence des contrôles de `PKGDEST`), P13A `bbvar`, P14B, B9, B10, P16-B10. Ne pas refaire la logique de sélection.
- **Adapter au seul écart** : un contrôleur B19 **lecture seule** du répertoire `PKGDEST` du paquet B17 et ses quatre SHA ; une CI dérivée du workflow B18 qui ajoute `bitbake -c package kwipi-b12-receiver`. Source privée `LICENSE=CLOSED` sans redistribution d'une archive/paquet.
- **Créer seulement** : tests host positifs/négatifs, fiche de qualification, statut README/plan/roadmap. Aucun bbappend, recette nouvelle, service, privilège ou accès robot.

## PASS / STOP préenregistrés

**Positifs** : (1) `main`/gitlinks/Yocto épinglés ; (2) B18 et source B17 relus, 19+5 octets historiques inchangés, quatre sources B13–B16 strictes ; (3) réellement exécuter en CI `bitbake -p`, `-e` recette/DEV/shipping, `bitbake-getvar` somme nommée, `show-appends`, puis `bitbake -c package kwipi-b12-receiver` **exit 0** ; (4) dans `PKGDEST/<paquet>/usr/lib/python3.14/site-packages/microduck_companion`, **exactement quatre fichiers ordinaires non exécutables**, octets et SHA identiques aux sources B17, aucun autre fichier, répertoire, média ou modèle dans le split principal, aucun fichier dans un autre split ; (5) shipping=0, compte Kwipi isolé sans moteur, CI complète verte au dernier SHA.

**Négatifs** : chemin hors `TMPDIR`, `PKGDEST` absent, lié ou réassigné, faux dossier `microduck_companion`, doublon/fichier `__init__.py`, modèle ou service supplémentaire, symlink, exécutable, source falsifiée, version/Python ABI/RDEPENDS/SRC_URI/empreinte fausse, DEV manquant ou shipping contaminé, compte moteur autorisé, couche non reconnue. **STOP** sur une de ces violations, timeout ou CI rouge ; aucune fusion en l'absence de véritable preuve du job `bitbake -c package`. Il n'est pas permis de « corriger » en modifiant B10/B17 ou la politique OEM sans nouveau contrat.

## Résultat final effectivement obtenu

Au HEAD `dc0c80dfb92179d8610acea88e93954939c40539`, les **8/8 CI** de la [PR #273](https://github.com/Jean-Philippe56520/Microduck/pull/273) sont vertes. [CI B19 #41455743181](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41455743181) : `bitbake -c package kwipi-b12-receiver`, 522/522 tâches réussies ; `PKGDEST` analysé : 4/4 modules Python source, tous ordinaires 0644, SHA identiques à B17, autres splits vides ; empreinte TAR source `0921b7dacd7a683b0b90ba7a979e20e72aa4a5aeaecb4899ba9cc63a46c7ab6c`. Les tests Python ont exécuté 2 395 cas (52 ignorés), sans échec. La PR a été **fusionnée** sur `main@d8d9047d8433043c0e518e089a2f331daf501003`, gitlinks OEM et simulation inchangés.

**Portée maintenue** : compilation/empaquetage sur Linux hôte, pas `do_rootfs`, WIC, RAUC, exécution du Python du robot, service `mediad`, détection active, identité binaire en mémoire, ACL réelles ni validation du robot. B10 n'est pas modifié. Nouvelle porte : [P16-B11 — rootfs DEV distinct à 28 modules](p16b11-new-dev-rootfs-28-module-audit-2026-11-02.md).

## Frontières et retour arrière

Le build GitHub sera **éphemère** (runner, cache temporaire) ; rapport JSON épuré seulement, aucun `bitbake -e`, RPM privé, archive source propriétaire ou secret en artifact. Le script contrôleur ne peut pas attester à lui seul qu'une commande BitBake a été exécutée ; seul le workflow et son journal peuvent le faire. Aucune `do_rootfs`, WIC, RAUC, package installé, environnement Python AArch64 exécuté, ACL réelle `/run`, perception, moteur ou robot validé. Reprise après succès : **nouveau** rootfs DEV versionné et contrôlé avec son manifeste, sans effacer B10 ; l'activation du producteur est séparée. Retour arrière : revert B19 et aucun changement sur rootfs B10 ou OEM.

**Statut final** : paquet B19 validé par vraie tâche BitBake et audit du split ; aucun rootfs nouveau fabriqué.
