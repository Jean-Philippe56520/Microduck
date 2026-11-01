# P15-B10 — sélection DEV opt-in du paquet passif déjà empaqueté (01/11/2026)

## Contrat et arrêt décidés AVANT code

**Objectif mesurable.** Préparer `microduck-image-dev` à installer les cinq modules P15-B6 (`kwipi-passive-fixture`) **en plus** des dix-neuf modules `kwipi-companion` P14B, sans installation dans `microduck-image` shipping, sans démarrage de service et sans droit moteur. Il s'agit d'une sélection de paquets **DEV seulement**, pas du cycle embarqué autonome ni d'une image nouvellement construite.

**Écart vérifié.** P15-B6-P a réussi `bitbake -c package kwipi-passive-fixture` sur WSL2 (522/522 tâches) et l'audit PKGDEST des cinq modules. Son générateur `scripts/per_p15b6_passive_python_addon.py` ne crée volontairement **aucun** bbappend image ; P14C ne sélectionne que `kwipi-companion`. Le rootfs P15-B9-R (4515/4515 tâches, audit post-hoc PASS, compte Kwipi isolé) a été composé **sans** la couche P15-B6. Installer ce complément dans un futur DEV nécessite une sélection explicite nouvelle. Rejouer les 4515 tâches pour ce diagnostic serait inutile.

**Sources et réemploi.** `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068` ; branche parente P15-B9 #247 au SHA `c1f625e87fd09fe9f3256eab565f417ac5a1918d`. Gitlinks inchangés : `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto OEM `1ee58387810cebb67ae0d634c351d95024483bce`. Réutiliser **sans changer** les recettes P14B/P14C/B6, le générateur P15-B6, la sélection P14C et le parseur `bbvar`/vérificateur `show_appends_selects_file` de P13A. Le constructeur reste propriétaire des composants `mediad`, `tofd` et `robotd` ; les références C3 ne fournissent aucun mécanisme de packaging nécessaire ici. Qwen PR #97–99 fusionnées mais sans incidence.

**Modification minimale envisagée.** Une couche optionnelle P15-B10 à **deux fichiers** : `conf/layer.conf` dépendant de la couche B6 `kwipipassive`, et `recipes-core/images/microduck-image-dev.bbappend` ajoutant exactement `kwipi-passive-fixture`. Ne pas modifier P14C/P15A/B6/B9, `upstream/`, le constructeur, les modèles, la mémoire, `RAUC`, les clés ou une image existante. Aucun nouveau logiciel exécuté sur le robot.

## Témoin, critères positifs et négatifs

- **Témoin** : P14C sans P15-B10 sélectionne les 19 modules seulement ; P15-B6 seule produit un paquet additif **non sélectionné**.
- **PASS source** si layer DEV strictement fermé (deux fichiers exacts, aucune recette shipping, aucune unité, symlink ou privilège), couche B6 vérifiée au SHA et au contenu, `kwipi-companion` conservé avec OEM daemon/data, et contrôles de métadonnées synthétiques DEV/shipping acceptent **un seul** `kwipi-passive-fixture` en DEV et **zéro** en shipping.
- **Négatifs obligatoires** : absence/duplication du complément ou de `kwipi-companion`, ajout shipping, disparition OEM daemon/data, couche absente de BBLAYERS, faux show-appends, lien symbolique, mauvais PN, fonctionnalité shipping de root-login, source B6 non attestée et ajout de commande d'activation dans la couche. Toute anomalie ⇒ **STOP**, pas de contournement.
- **PASS BitBake, distinct** : sur une configuration KAS DEV/ship OEM épinglée et les couches P12/P14B/P14C/P15A/B6/B9/P15-B10 opt-in, `bitbake -e` + `bitbake-layers show-appends` prouvent la sélection effective unique DEV et l'absence shipping. Le `do_rootfs` local P15-B9-R **ne doit pas être rejoué** pour prouver ce fait.
- **Image et service** : l'étape rootfs/WIC/RAUC nouvelle n'est **pas** autorisée par ce lot ; aucune affirmation d'installation sur le rootfs P15-B9-R ou d'exécution sous l'UID Kwipi.

## Risques, limites et retour arrière

Le paquet P15-B6 contient un **lanceur de fixtures** (refus des vrais chemins OEM), pas encore une boucle de détection réelle authentifiée. L'installer ne valide pas la version compilée `DUCK_REVISION`, la fraîcheur de `Sighting`, les ACL effectives `/run` ou le montage runtime. B8 n'est pas encore intégré à la release Yocto. Aucun accès de Kwipi au groupe `robot`, au capteur brut ou aux moteurs. En cas d'échec, retirer **uniquement** cette couche des BBLAYERS et de la pile Git, laisser la WIC historique et les caches intacts. La future qualification P17 et les mesures RK3566 attendent le robot, après V1 préparée.

**Verdict prévu** : `test_logiciel_seul` avant CI BitBake ; éventuellement `bitbake_metadata_dev_only_verified` après preuve réelle, jamais `rootfs_deployable` ni `robot_validated`.
