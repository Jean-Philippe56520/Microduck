# N1 — Graphe statique d'imports et contenu réel du wheel

**Date :** 28/10/2026. **Statut :** instrument d'inventaire, sans nettoyage destructif. [Audit N0 en PR #127](https://github.com/Jean-Philippe56520/Microduck/pull/127) ; autorité : [plan-action.md](plan-action.md).

**Observation :** `pyproject.toml` référence l'ensemble de `microduck_companion*` ; `main@71a876b` comprend 121 modules Python, dont les outils MuJoCo et les démonstrations. Une présence dans un wheel n'est pas une exécution, ni une preuve d'installation robot.

**Hypothèse / preuve / échec :** les modules de laboratoire pourraient être empaquetés par défaut. N1 crée un graphe **statique** des imports explicites `import` et `from`, relève un indicateur d'import dynamique, les gardes CLI conventionnels, les chaînes RPC motrices, et compare les fichiers `.py` du **véritable wheel** aux sources. Si un import n'est pas résoluble dans les fichiers présents, il est signalé mais **pas exécuté**. Imports dynamiques, accès via réflexion, chargements conditionnels, données package, liens natifs, dépendances externes et effets d'import ne sont pas entièrement couverts : aucune suppression ne peut reposer seulement sur ce manifeste.

**Réutiliser / adapter / créer :** `ast` et `zipfile` Python standard pour une inspection passive ; `setuptools` actuel **non modifié** ; nouveaux outils N1 limités à un script et tests de fixtures. M9 non porté, propriétaire de `robotd` inchangé, outils OEM `robotctl` non remplacés. Aucun moteur/capteur/Qwen/SQLite privé.

## Exécution et preuves

```sh
python scripts/n1_inventory.py --output /tmp/n1-source.json
python -m unittest discover -s tests -p test_n1_inventory.py -v
python -m pip wheel --no-deps --wheel-dir /tmp/n1-wheels .
python scripts/n1_inventory.py --wheel /tmp/n1-wheels/microduck_companion-0.2.0-py3-none-any.whl --output /tmp/n1-wheel.json
```

Le dernier nom de wheel dépend des métadonnées et du constructeur ; le workflow **détecte le chemin** après construction. La CI N1 réalise ces étapes et dépose un JSON comme artefact GitHub, ne publie pas de photographies, souvenirs, clés ou données privées. Le rapport utilise `review_required` comme valeur par défaut : `lab_candidate` est un **signal de triage** par nom de fichier, jamais une permission automatique de supprimer.

**Cas négatifs couverts :** une syntaxe Python invalide est refusée ; un import dynamique est signalé comme incomplet ; la comparaison wheel/source échoue si les listes diffèrent ; une fixture déclenchant une exception à l'import n'est jamais importée.

**Limites :** le runner GitHub ne représente pas le RK3566, aucun calcul de RSS/T°/latence/batterie ni comportement moteur n'est testé. N1 ne produit pas de paquet embarqué ni de nouvelle politique de démarrage ; ne pas traiter une CI verte comme validation de sûreté robot.

**Critère N1 avant N5 :** conserver le manifeste horodaté de wheel et le SHA de PR, auditer manuellement tous les imports dynamiques/points d'entrée, construire un graphe de dépendances inverses et des tests d'empaquetage avec une liste positive de composants embarquables. La décision de retrait sera une PR séparée et réversible après CI verte. Ne pas fusionner les composants historiques ni toucher aux gitlinks sans preuve.
