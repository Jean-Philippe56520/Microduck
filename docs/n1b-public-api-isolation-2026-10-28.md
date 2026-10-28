# N1b — Isoler sans supprimer : étude du coeur public Python

**Date :** 28 octobre 2026. **Statut initial :** expérimentation de conditionnement sur hôte/CI, non déployable. Priorités effectives : [plan-action.md](plan-action.md). Audit [N0 #127](https://github.com/Jean-Philippe56520/Microduck/pull/127) et outil [N1 #128](https://github.com/Jean-Philippe56520/Microduck/pull/128) sont fusionnés, mais ils ne retirent aucun module.

## 1. Porte de preuve avant le code

**Observation vérifiée :** l'[artefact N1 réel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40741745828) sur le commit de PR `074978031897f8932dd33b1af3e6c2de78798548` contient 121 modules Python dans le wheel normal ; **54 candidats laboratoire par nom**, 67 autres modules à revoir, 16 arêtes d'import d'un module « à revoir » vers un module « labo », zéro import interne absent détecté, **un import dynamique** (dans `f5b_benchmark`). Ces catégories sont des **heuristiques**, pas des preuves qu'un module est ou n'est pas indispensable.

**Hypothèse :** la surface de l'API publique exportée dans `microduck_companion/__init__.py` peut être reproduite dans une archive ZIP source plus petite pour vérifier une future frontière de paquet, **sans retirer de code du paquet actuel**.

**Critères de succès :** clôture des imports explicites calculée depuis le seul `__init__.py`, absence de module commençant par `sim_`, absence de marqueur de commande motrice et d'import dynamique dans cette clôture, test d'import en `python -I -B` ne résolvant que le ZIP isolé, suite complète CI inchangée. Les objets exposés `AutonomyBrain` et `ExperienceMemory` doivent être importables.

**Critères d'échec / retour arrière :** refuser avant écriture si import statique introuvable, import dynamique reachable, module `sim_` ou marqueur RPC moteur dans la clôture. Une CI rouge interdit la fusion. Retour arrière : abandonner la PR ; le paquet normal n'a pas été changé.

**Risques :** analyse AST imparfaite (imports conditionnels, `getattr`, fichiers de données, signatures d'import et dépendances tierces non vérifiés). Les chaînes `robot.move` signalées sont un **garde textuel conservateur**, non une preuve d'accès moteur. Importer l'API ne valide pas les scénarios, la persistance ni les ressources RK3566. **Ce ZIP n'est ni un wheel, ni un exécutable, ni une publication, ni un paquet robot validé.**

## 2. OEM d'abord, puis réemploi local

- OEM épinglé : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` ; `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` ; inchangés. `robotd` reste seul responsable des moteurs à 50 Hz ; `mediad`, `tofd`, `pet-detect`, IdleHead et les politiques OEM ne sont ni importés ni modifiés par N1b.
- M9 dans la version OEM épinglée est **documenté, non livré**. PR constructeur [#381](https://github.com/pollen-robotics/microduck/pull/381) ouverte (conception communautaire, pas intégration moteur) ; [#450](https://github.com/pollen-robotics/microduck/pull/450) ouverte (configuration de simulation, non importée). Pas d'autorité motrice Companion.
- Reprise de `scripts/n1_inventory.py` et de ses métadonnées déjà testées, `zipfile` et `unittest` Python ; aucun nouveau format de SQLite ni modèle, aucun package tiers, Qwen, fichier privé ou capture.

**Choix réutiliser / adapter / créer :** réutiliser N1 pour les métadonnées ; **créer seulement** une clôture de l'API exposée et sa preuve ZIP isolée (N1 n'écrivait pas de sous-ensemble) ; ne pas adapter `pyproject.toml`, `AutonomyBrain`, `robotd` ou les sous-modules dans ce lot.

## 3. Mesure avant changement

Le graphe N1 de l'API publique atteint **19/121 modules** et garde **2 fichiers à préfixe `mock_`** : `mock_cycles.py` et `mock_social_cues.py` par dépendance d'autres modules. **Ils ne doivent pas être supprimés sans migration/refactoring** ; leurs noms ne prouvent ni le rôle déployé ni la nécessité d'embarquer leur logique.

`scripts/n1_public_slice.py` écrit un ZIP déterministe dans un chemin d'hôte choisi et un rapport JSON. Il n'importe **aucun code de Companion pour créer la sélection** et n'exécute aucun moteur. Le test d'import du ZIP se déroule en processus Python isolé **sur CI/PC uniquement**.

```sh
python -m unittest discover -s tests -p test_n1_public_slice.py -v
python -m scripts.n1_public_slice --output /tmp/n1-public-api.zip --report /tmp/n1-public-api.json
python -I -B -c 'import sys; sys.path.insert(0,"/tmp/n1-public-api.zip"); import microduck_companion; assert microduck_companion.AutonomyBrain'
```

Le workflow N1 existant ajoute une étape de test et publie le manifeste ainsi que l'archive en artefacts CI. L'archive n'est pas destinée à l'utilisateur final ni au firmware.

## 4. Interprétation et suite

**N1b est un essai de séparation prouvé/échoué par CI, pas une réduction automatique de la distribution officielle.** La chaîne réellement visée par Kwipi doit encore faire l'objet de N2 : une seule perception OEM → mémoire `ExperienceMemory` → motivation/prudence → choix d'inaction ou suggestion d'intention, jamais de second ordonnanceur moteur ; future fin d'action et effet indépendant exigés pour tout apprentissage causal. Avant tout portage, auditer la disponibilité des services OEM, leurs interfaces actives, les nouveaux états M9 effectivement livrés, le stockage, les quotas et la sécurité. Si le paquet complet et la tranche prototype divergent dans un scénario réel de l'API, corriger ce scénario avant de parler d'installation.
