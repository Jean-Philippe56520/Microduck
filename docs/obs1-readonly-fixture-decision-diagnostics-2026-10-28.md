# OBS-1 — diagnostic borné des épisodes fictifs, lecture seule

**Date :** 28 octobre 2026. **Statut :** code et tests de fixtures soumis à CI, **aucun robot réel**. Document d'exécution du [plan objectifs/détermination/observabilité](kwipi-goals-determination-memory-qwen-observability-plan-2026-10-28.md) et de l'autorité [plan-action](plan-action.md).

## Porte préalable OEM-first

**Observation :** EX1/EX2 ont déjà une SQLite commune et le lecteur à la demande `kwipi_journal.read_journal` ouvre en `mode=ro` et `PRAGMA query_only=ON`. Son export JSONL/CSV existant ne fournit pas les champs diagnostiques explicites distinguant la **résolution fictive** d'une exécution OEM authentifiée. Le constructeur épinglé `942e58e3` fournit `robotctl monitor --json`, `robotctl logs`, `robotctl health` et `robotctl policy list`, mais pas une corrélation fiable `robot.do accepted → début → fin → effet`. Son journal `/var/log` sur zram n'est pas durable après coupure.

**Hypothèse :** une projection déterministe de l'export EX1/EX2, sans modifier la SQLite ni réouvrir de connexion, rend explicite ce qui est connu/inconnu avant le futur OBS-2. **Preuve :** tests positifs, faux reçu, provenance, rétraction, entrée malformée, limites de débit, octets SQLite avant/après, CLI et retour sans média privé. **Échec/stop :** toute preuve motrice inventée, écriture, second writer/base, champ libre non filtré, commande robot, source nouvelle présentée comme attestée ou sortie contradictoire. **Retour arrière :** retirer l'option CLI et la projection ; anciennes commandes et schémas restent inchangés.

| Choix | Justification |
| --- | --- |
| **Réutiliser** `kwipi_journal.read_journal`, EX1/EX2, `ExperienceMemory`, F2 et EX4 | Le lecteur vérifie déjà source, statut, rétention et correction sans écriture |
| **Adapter** `kwipi_journal.py` | Ajouter une projection explicite sans seconde CLI/socket/SQLite |
| **Créer** un test isolé et ce rapport | Contrôler cas positifs/négatifs et maintenir la frontière de preuve |
| **Ne pas créer** un démon/agent/moteur ni importer QuackNav/Twin/GC | Aucun flux moteur ni navigation requis ; projets tiers = références à auditer dans leurs propres lots |

## Contrat et emploi hôte volontaire

```sh
python -m microduck_companion.kwipi_journal /chemin/vers/fixture.sqlite3 \
  --at 1770000009 --diagnostic --include-withdrawn --limit 20
```

Ce mode ne lit **que** les épisodes EX1/EX2 `mock_fixture_only` déjà présents ; format de sortie JSONL fermé, au plus 50 enregistrements, un par paire `session/sequence`, tri chronologique décroissant. Les noms privés, texte libre, médias, traces articulaires brutes, souvenirs non reliés et données Qwen sont exclus. Une résolution `mock_executed` reste **scripted-only** : `oem_execution=not_attested`, `physical_effect=not_attested`, `causality=unproven` même si un cue EX2 a changé. `decision_context` et `qwen_context` sont explicitement `not_recorded`.

L'option `--diagnostic` n'accepte ni CSV ni `--trend`. Elle n'enregistre rien toute seule, n'ouvre aucun réseau et ne capte aucune caméra. La lecture manuelle d'un snapshot SQLite stable en PC n'atteste ni la synchronisation horloge/robot ni l'exécution d'un geste. Aucune donnée privée ne doit être committée ou transmise par défaut.

## Tests et limites de la preuve

`python -m unittest discover -s tests -p 'test_obs1_episode_diagnostics.py' -v`. La CI complète doit rester verte avant fusion. Tester aussi le scanner N3 pour absence de nouveau writer, les deux workflows existants et le diff (aucun OEM, ONNX, modèle, changement de package).

**Limites actuelles :** pas de trace décisionnelle réelle, pas d'identifiant d'action OEM authentifié, pas d'humeur ni objectif enregistré dans EX1, pas de vision réelle, pas de garantie de complétude, aucune mesure RK3566. Cette première tranche ne livre **pas** la boîte noire physique, le monitoring direct, la détermination ni le rappel Qwen ; ils restent dans les lots OBS-2/MEM/DET/QW. Les traces OEM seront à corréler plus tard seulement lorsqu'un identifiant et une preuve adéquate existent.

Sources constructeur : [commande monitor/logs](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md), [design de la boucle](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/robotd-design.md). Registre de réutilisation : [C3](community-reference-registry-2026-10-26.md).
