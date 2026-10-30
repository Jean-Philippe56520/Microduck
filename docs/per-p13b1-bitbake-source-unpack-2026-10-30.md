# PER-P13B1 — BitBake do_fetch/do_unpack, critères préalables (2026-10-30)

**Base :** main f3033ece08186495abf61b7ffcc31e90286e6a98, OEM 942e58e3aa6dbb28e7037203fff11866122c7567, sim b02fdea4902c2b93b7d34a83a6f05da4ececb7d3, Yocto 1ee58387810cebb67ae0d634c351d95024483bce. PR #225–228 fusionnées, CI verte. PR #218 fermée, parité non validée. Qwen #97–99 fusionnées.

**Manque prouvé :** P13A a réalisé le parsing BitBake et contrôlé 568 sources crates, mais pas `do_fetch` ni `do_unpack`. Ces tâches, nécessaires avant toute compilation P13B, n'ont donc pas de preuve réelle.

**Décision :** réutiliser P11 (archive immuable), P12 (couche Yocto et somme des crates), P13A (validation variables effectives), recette et kas Yocto épinglés. Adapter uniquement le workflow pour exécuter `bitbake -c fetch microduck-daemon` puis `bitbake -c unpack microduck-daemon` sur un runner Ubuntu 22.04 sans modifier AppArmor. Créer un validateur de `S`, `UNPACKDIR`, fichiers source et BMI088. Pas de deuxième pilote, modèle, caméra, moteur ou SQLite.

**Positifs prédéfinis :** archive P11 SHA exacte ; 568 crates en métadonnées ; fetch et unpack renvoient 0 ; manifestes Cargo/LICENCE et code noyau du `S` effectif identiques octet pour octet à l'archive ; BMI088 à sa révision épinglée ; chemins `S` dans TMPDIR réel, aucune inclusion des poids Kwipi ; résultat `bitbake_unpacked_source_verified`.

**Négatifs prédéfinis :** mauvais SHA de l'archive ou de BMI088, fichier source modifié/manquant/symlink, version ou chemin `S` hors build, source Git OEM ajoutée, artefact de provenance incohérent => STOP. Une archive générée uniquement en Python ne suffit pas à valider `do_unpack`.

**Arrêt :** ne pas fusionner sans CI verte au SHA final. GitHub runner < capacité d'image constructeur (>100 Go pour image complète) : ne pas lancer de build image, RAUC, signature ou flash. Si fetch dépendance externe indisponible, conserver le blocage documenté, pivot P14B indépendant. Retour arrière : suppression couche et fichiers temporaires, aucune modification de l'OEM. P13B2 (`do_compile`/`do_package`) et P14B/P15–P17 restent des portes distinctes.

## Résultats

En attente d'une exécution réelle du workflow GitHub.

## Résultat réel du premier banc `do_fetch` / `do_unpack`

[Run #41140064244](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41140064244) terminé en succès sur `22a4317247613aba4d6aced3a7ac0e4a4a08087f`. Les tâches `bitbake -c fetch microduck-daemon` et `bitbake -c unpack microduck-daemon` se sont **terminées code 0** en utilisant le `kas` constructeur réellement épinglé, et la sortie des variables effectives a été contrôlée par le validateur P13A. Six fichiers dans `S` ont été comparés **octet pour octet** à l'archive P11 : `Cargo.toml`, `Cargo.lock`, `LICENSE`, `mediad/Cargo.toml`, `duck-detect/Cargo.toml`, `kwipi-seg-mask-core/Cargo.toml`. Le checkout déballé `bmi088-rs` a été validé au SHA `bd113f317b14923f50f9a12a06678fe162b7fe06` par `git rev-parse HEAD`. Pour ce seul commit P11, le tar SHA-256 vaut `1819399813cba1ecfd66abc8ecbb0141d80e1e31bb2b9337ec6b271c39c7fe08`. Les **10 tests P13B1**, les **11 tests P13A** et l'ensemble Python ont été verts. Le premier lancement de test s'était arrêté sur une faute de nom `PINN`/`PINNED`, corrigée sans changer les sources OEM. La CI du nouveau commit documentaire doit être verte avant fusion.

**État de preuve** : `bitbake_unpacked_source_verified`, 568 crates sélectionnées en métadonnées ; `do_compile`/`do_package` non exécutés, aucune ELF/aarch64 et aucune image produites. Ni Qwen 9B, ni SQLite embarquée, ni YOLO26 sous licence ni NPU, ni service moteur ajoutés. Répéter le test au SHA documentaire final et vérifier qu'il reste vert. Retour arrière : ne pas activer la couche opt-in.
