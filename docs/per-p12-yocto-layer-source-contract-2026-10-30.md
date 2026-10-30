# PER-P12 — intégration Yocto préparatoire, archive P11 dans une couche séparée (30/10/2026)

## Porte 0 : gain fonctionnel, preuves et arrêt avant code

**Base vérifiée :** `main@a2d0d161b920e32b580251f7081da2dccf4fddd6`. Gitlinks inchangés : OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Yocto `1ee58387810cebb67ae0d634c351d95024483bce`; OEM main observé `b2b0d213a402caeac492dd662ea891faa17f67c0`. Qwen PR #97–99 fusionnées. P8/#218 fermée sans parité réelle. P11/#225 fusionnée et CI finale P11/Python/inventaire verte ; la CI générale post-merge main est verte.

**Besoin** : P11 produit une archive source déterministe de P10A/B/C qui compile sur hôte, mais le Yocto OEM `microduck-daemon.bb` pointe sur une release OEM et ne peut donc inclure les modifications de Kwipi. Un paquet Python Companion embarqué n'existe pas encore. Ne pas confondre une nouvelle PR/CI avec une capacité robotique.

**Objectif de P12** : produire dans un dossier éphémère une **couche Yocto séparée**, contenant un `.bbappend` de la recette du constructeur épinglé, alimentée par les **octets exacts d'une archive P11 vérifiée**, et auditer le verrou Cargo, les sources constructeur et la sélection d'une seule caméra/daemon. Conserver `upstream/`, les moteurs, les services, la base SQLite, et le mécanisme de mise à jour OEM inchangés. L'artefact sera classé *candidat source/recette*, pas firmware ni release signée.

## Matrice de réemploi

- **Réutiliser** : `scripts/per_p11_v1_source_release.py`, manifest SHA-256, P10A/B/C, `meta-microduck/recipes-microduck/microduck-daemon/microduck-daemon.bb`, `microduck-daemon-crates.inc`, `kas/microduck.yml`, `bmi088`, recettes ORT/GStreamer, utilitaires de contrôle Git ; `robotd` reste seul moteur.
- **Adapter** : seulement l'assemblage hors robot et la source du `microduck-daemon` de la recette dans une *couche de développement complémentaire* ; conserver tous les fichiers `file://` de l'OEM et sa déclaration `bmi088`, et expliciter la version de paquet distincte.
- **Créer** : un préflight et un préparateur de couche locale, tests positifs/négatifs et CI source-only, sans fork constructeur, second pilote, modèle additionnel, service, téléchargement de médias ni secret.

## Tests enregistrés avant essai

**Positifs** : exiger une archive P11 avec SHA, manifest OEM + Companion exact, absence de nouveaux poids, (a) `cargo metadata --locked` déjà prouvé par P11, (b) mêmes dépendances crates.io/checksums que le Cargo.lock OEM, (c) sha exact du dépôt Yocto et de `microduck-daemon.bb`, (d) remplacement explicite de la seule entrée Git `daemon` par le tar P11 sans retirer le dépôt `bmi088` ni les trois ressources locales, (e) générateur déterministe et contenu de la couche vérifié, (f) aucun changement de gitlink/recipe OEM.

**Négatifs** : refuser mauvais SHA Yocto, recette modifiée, source non P11, archive altérée, version/commit incohérents, ajout modèle non licencié, disparition `bmi088`, perte des fichiers OEM, perte `enabled=false`, lien sortant et double daemon; aucun état positif sans preuve. Tests sur **sources exactes** et non sur une recette fabriquée en fixture seulement.

**Arrêt** : ne pas fusionner si la CI source-only échoue. `bitbake -p` ou `do_compile` ne pourront être revendiqués que s'ils sont réellement exécutés. Ne pas publier d'image sans compatibilité réelle de la version `robotctl`/`updaterd`, `bitbake` complet, validation RAUC et licences des poids. Retour arrière = supprimer la couche éphémère ou la PR ; aucune modification système/robot.

## Risques et limites explicites

- La recette OEM attend un code de release avec une version identifiable par `updaterd`. **Une version de package distincte ne rend pas une version constructeur signée.** Les binaires et manifestes devront être harmonisés dans un lot ultérieur avant installation.
- Même une éventuelle vérification de parsing `bitbake -p` n'est pas un build d'image ni un test de services sur le robot. Sans espace disque (Yocto exige des dizaines à plus de 100 Go), classer la construction réelle **bloquée/en attente**.
- YOLO26n-seg sous AGPL-3.0 ou licence Enterprise, droits des poids et du `tail.onnx` à vérifier ; aucun poids ajouté. Détecteur désactivé, parité RKNN P8 et budget NPU/thermie/RSS inconnus.
- P13 (paquets ARM64 BitBake), P14 (véritable runtime Python sans moteurs fictifs), P15 (service/health), P16 (image/RAUC), P17 (matrice V1) restent des portes distinctes et non validées par ce lot.

## Résultats

*À compléter uniquement après CI au SHA final.*

## Résultat CI sur les sources constructeur

[CI P12 #41135329389](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41135329389) **verte** sur le commit candidat `4a99a144c1645b2ead44501c1b781da6fbf3a15b` : 8 tests purs et 3 tests de sources réelles, soit **11/11** ; deux générations de couche identiques au niveau fichiers, sortie `verify` réussie et refus de modifications de provenance, source et `.bbappend`. Préflight vérifie le `git archive` P11, la recette constructeur, les quatre blobs Yocto épinglés et les gitlinks ; sortie `crates_generated=568`, `crates_regenerated=true`, `archive_sha256=9f7813bf5e7a2cc92a21635c51d4b778df436d37d516fd1547f96d16956d5ce6` **pour ce seul SHA de PR**. CI générale Python et fusion à contrôler au SHA documentaire final.

**Important :** la nouvelle liste de crates ne prouve pas que BitBake la parse, la télécharge ou la compile. `SRC_URI` et `require` dans le `.bbappend` sont un **candidat** à vérifier par `bitbake -e`/`-p` sur les layers officiels avant utilisation. Aucun clone constructeur, suite d'installation ou paquet publié n'est modifié. Les scripts `scripts/build-local.sh` et `daemon-release.sh` OEM continuent de résoudre des releases constructeur, **pas** notre version candidate ; ne pas flasher. Retour arrière : détruire la couche temporaire.
