# PER-P13B1 — BitBake do_fetch/do_unpack, critères préalables (2026-10-30)

**Base :** main f3033ece08186495abf61b7ffcc31e90286e6a98, OEM 942e58e3aa6dbb28e7037203fff11866122c7567, sim b02fdea4902c2b93b7d34a83a6f05da4ececb7d3, Yocto 1ee58387810cebb67ae0d634c351d95024483bce. PR #225–228 fusionnées, CI verte. PR #218 fermée, parité non validée. Qwen #97–99 fusionnées.

**Manque prouvé :** P13A a réalisé le parsing BitBake et contrôlé 568 sources crates, mais pas `do_fetch` ni `do_unpack`. Ces tâches, nécessaires avant toute compilation P13B, n'ont donc pas de preuve réelle.

**Décision :** réutiliser P11 (archive immuable), P12 (couche Yocto et somme des crates), P13A (validation variables effectives), recette et kas Yocto épinglés. Adapter uniquement le workflow pour exécuter `bitbake -c fetch microduck-daemon` puis `bitbake -c unpack microduck-daemon` sur un runner Ubuntu 22.04 sans modifier AppArmor. Créer un validateur de `S`, `UNPACKDIR`, fichiers source et BMI088. Pas de deuxième pilote, modèle, caméra, moteur ou SQLite.

**Positifs prédéfinis :** archive P11 SHA exacte ; 568 crates en métadonnées ; fetch et unpack renvoient 0 ; manifestes Cargo/LICENCE et code noyau du `S` effectif identiques octet pour octet à l'archive ; BMI088 à sa révision épinglée ; chemins `S` dans TMPDIR réel, aucune inclusion des poids Kwipi ; résultat `bitbake_unpacked_source_verified`.

**Négatifs prédéfinis :** mauvais SHA de l'archive ou de BMI088, fichier source modifié/manquant/symlink, version ou chemin `S` hors build, source Git OEM ajoutée, artefact de provenance incohérent => STOP. Une archive générée uniquement en Python ne suffit pas à valider `do_unpack`.

**Arrêt :** ne pas fusionner sans CI verte au SHA final. GitHub runner < capacité d'image constructeur (>100 Go pour image complète) : ne pas lancer de build image, RAUC, signature ou flash. Si fetch dépendance externe indisponible, conserver le blocage documenté, pivot P14B indépendant. Retour arrière : suppression couche et fichiers temporaires, aucune modification de l'OEM. P13B2 (`do_compile`/`do_package`) et P14B/P15–P17 restent des portes distinctes.

## Résultats

En attente d'une exécution réelle du workflow GitHub.
