# PER-P14B — vrai paquet Python Kwipi dans Yocto, candidat sans service (30 octobre 2026)

## Porte 0, manque et seuils avant tout essai

Baseline **`main@f3033ece08186495abf61b7ffcc31e90286e6a98`** et sous-modules immuables OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, sim `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`; Yocto `1ee58387810cebb67ae0d634c351d95024483bce` (OE-core `ae5a301091f5b0574ea7444aab40b309b6d9f3f2`). P11/P12/P13A et P14A fusionnées ; Qwen #97–99 fusionnées, parité P8/#218 fermée sans validation. Plan directeur `docs/plan-action.md`.

**Manque prouvé :** P14A produit un wheel Python pur **19 modules, 66 701 octets sur hôte**, et ses tests prouvent le refus des méthodes motrices ; **aucune recette Yocto ni installation cible n'existe**. `microduck-image` OEM n'installe pas `kwipi-companion`. Tant que cet écart existe, aucune V1 autonome/embarquée ne peut être revendiquée.

**Réemploi constructeur vérifié :** OE-core épinglé `meta/classes-recipe/python_pep517.bbclass` construit et installe les roues avec les outils natifs ; `python3-dir.bbclass` cible Python **3.14** sur la branche épinglée, `python3/python3-manifest.json` énumère `python3-core`, `python3-sqlite3`, `python3-json`, `python3-math`, `python3-io`, `python3-netclient` et `python3-threading` requis par les imports inspectés des 19 modules. Aucun backend externe/paquet pip distant n'est nécessaire. `meta-microduck` constructeur installe `microduck-daemon`/politiques mais n'a aucun Python Companion. Le code original de Companion ne contient **aucun fichier LICENSE explicite** dans la racine ; la recette candidate utilise `LICENSE = "CLOSED"` en attendant un choix explicite de licence de distribution. **Interdiction de publier cette image en produit** avant clarification des droits.

## Objectif, matrice et séparation

**P14B :** produire dans un dossier éphémère une seconde couche source minimale **`meta-kwipi-python`**, recette `kwipi-companion_0.2.0a1.bb`, tar.gz déterministe contenant uniquement les 19 sources P14A inchangées et leur `pyproject.toml`, puis tester `bitbake -p` et `bitbake -e kwipi-companion` sur le vrai kas OEM, et si les ressources le permettent les tâches `do_compile`, `do_install`, `do_package` du paquet **uniquement**. Aucun système, contrôle moteur, média, secret, ajout de service ou image/RAUC modifié. Choisir une **couche séparée** plutôt que modifier le générateur P12 validé ou les sous-modules OEM ; elle se désactive en retirant un seul chemin KAS. L'installation dans une image est une étape P14C/P16 distincte.

**Réutiliser :** `scripts/per_p14a_embedded_wheel.py` et ses 19 fichiers, OE-core `python_pep517`/Python 3.14 et recette constructeur épinglée. **Adapter :** générer une archive P14A sérialisée de manière déterministe et une recette OE. **Créer :** préparateur et validateur de couche, cas positifs/négatifs, CI isolée de parsing/packaging, rien de plus.

## Portes positives/négatives fixées

**Positifs :** (1) liste stricte 19 modules sans `mock_*`, modèles, SDK Qwen, `sim_bridge`, seconde SQLite ou commandes moteur ; (2) deux générations de la couche ont **exactement les mêmes octets**, manifestes et empreintes ; (3) tarball et recette avec SHA256/PV/source indépendants de la branche; (4) `inherit python_pep517`, back-end `python3-setuptools-native`, dépendances Python strictes issues du manifeste OE épinglé, `LICENSE = CLOSED`; (5) `bitbake -p` et `-e kwipi-companion` montrent source unique, cible site-packages correcte, RDEPENDS Python exactes et aucun autostart; (6) si paquet réellement produit, inspecter `PKGDEST`/site-packages et `pkgdata`/RECORD des 19 modules et absence d'exécutable/service; publier **le seul résultat prouvé**, sans équivalence à une image.

**Négatifs :** source symlink/fuite hors arbre, 20e module, poids/secret, modification de l'un des 19 modules, tar ou SHA falsifiés, entête recette inattendue, recette absente dans BitBake, dépendances changées, Python non présent, packaging qui ajoute un service/moteur, build qui dépasse espace/temps -> STOP. Avec `python3-core` et SQLite, l'unique `ExperienceMemory` reste inchangée ; aucune seconde base.

**Stop et retrait :** une CI source/BitBake rouge reste en PR brouillon; les téléchargements/build de dépendances peuvent dépasser 15 Go du runner, donc ne pas forcer l'image OS (>100 Go annoncés OEM) ni désactiver AppArmor. Aucun RAUC, aucun accès robot, aucune clé. Si la porte build ne passe pas, conserver seulement un test métadonnées ou réévaluer le runner. Retrait = supprimer la couche scratch / revert PR. `robotd` seul moteur, détecteur opt-in désactivé.

## Résultats

*En attente des vraies sorties CI ; tests locaux/simulateur ne prouveront ni Python 3.14 sur RK3566 ni installation réelle.*
