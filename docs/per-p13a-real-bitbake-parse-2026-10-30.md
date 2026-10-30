# PER-P13A — parser BitBake réel de la couche Kwipi, sans firmware (30 octobre 2026)

## Observation et manque prouvé avant code

`main@9ede20893ac1a21dae4dda737753bd870ee91bdd`, OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto `1ee58387810cebb67ae0d634c351d95024483bce`. PR #225 P11 et #226 P12 fusionnées, CI spécialisées vertes. Qwen #97–99 fusionnées, P8/#218 fermée sans parité. **P12 ne teste pas BitBake** : il génère des `.bbappend`, un `layer.conf` et un include de 568 crates depuis la source P11 ; seules les vérifications Python et Git ont tourné. Les règles BitBake de `SRC_URI`, `subdir=${BP}`, `SRCREV_FORMAT`, `require` et `PV` ne sont donc **pas encore démontrées** par un véritable parseur.

## Objectif et économie

Réutiliser les scripts P11/P12 et **le `kas/microduck.yml` officiel**, les SHA des dépôts OE et la recette `microduck-daemon.bb` figée. Créer uniquement un workflow ciblé **P13A** pour exécuter un vrai `kas shell` et `bitbake -p` sur les sources épinglées, puis `bitbake -e microduck-daemon` pour examiner **l'environnement EFFECTIF**. Couche Kwipi éphémère référencée par un second fichier KAS temporaire local. Aucun fork de Yocto, changement de gitlink, contrôle moteur, service, modèle ni second pilote.

## Tests fixés avant essai

**Positifs :** vérification SHA main/Yocto/OEM/RL ; génération P11 et P12 ; source OEM dans l'archive, fermeture `crates.io` de 568 entrées et BMI088 épinglé ; `kas` v5.2 (plugin shell) clone le jeu de layers Yocto épinglés avec `KAS_CLONE_DEPTH=1` ; `bitbake -p` revient code 0 ; `bitbake -e microduck-daemon` prouve via `SRC_URI` **un seul tar P11** et aucune URL `microduck_daemon.git`, **un seul BMI088**, trois ressources OEM présentes, références crates exactes, `PV` distinct, `S` cohérent avec le tar sous `${BP}`.

**Négatifs :** mauvaise version, SHA/manifest source/recette, dépendance ancienne conservée, double source, archive non autorisée, modèle non licencié ou absence d'entrée `microduck-daemon` → STOP. Exiger le nom `microduck-daemon.bbappend` correspondant au vrai nom recette OEM. Vérifier aussi `bitbake-layers show-appends` si disponible.

## Arrêt/retour arrière et limites

Le runner standard GitHub a environ 14 Go libres et **n'a pas les ressources démontrées pour une image Yocto complète** (l'OEM prévient que TMPDIR peut dépasser 100 Go). **P13A n'exécute ni `bitbake -c compile`, ni installation, ni RAUC, ni image**, et ne prétend pas que le package est compilé. Si les clones sont indisponibles, la version `kas` incompatible, le parseur casse ou la sortie effective contredit P12 : conserver la PR non fusionnée, enregistrer l'erreur précise et ne pas changer les pins. Si le parseur réussit, la porte P13A est franchie mais **P13 compilation ARM64 reste bloquée** jusqu'à un runner suffisamment dimensionné et un paquet signé cohérent. Revenir en arrière = supprimer les fichiers temporaires/branch; aucune donnée utilisateur, média ou secret impliqué.

**Sources** : [Yocto OEM](https://github.com/pollen-robotics/microduck_yocto/tree/1ee58387810cebb67ae0d634c351d95024483bce), [kas 5.2 — shell](https://kas.readthedocs.io/en/5.2/userguide/plugins.html), [kas 5.2 — repo path et clone](https://kas.readthedocs.io/en/5.2/userguide/project-configuration.html).

## Résultats

À compléter **après** l'essai dans GitHub Actions ; aucune réussite n'est présumée.
