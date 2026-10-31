# P15-B0/B1 — cycle de vie passif de Kwipi sur PC, sans interface robot (31/10/2026)

## Résultats réels des tests CI P15-B1 (31 octobre 2026)

**Preuve GitHub Actions vérifiée sur le commit `3caecae827686f479fd4abdda034cde0a217349a`** : [PR #239](https://github.com/Jean-Philippe56520/Microduck/pull/239) ; workflow `Python companion tests` **`41240685049`**, suite `python -m unittest discover -s tests -v` : **`Ran 2006 tests in 83.097s` ; `OK (skipped=22)`**. Les **12 méthodes `tests/test_p15b_passive_fixture_runtime.py` ont chacune rendu `ok`**, y compris `test_real_sigterm_stops_a_bounded_subprocess` et `test_real_subprocess_uses_one_fixture_then_exits`. Les étapes `compileall`, audit SQLite N3, budget SQLite N4, Tk GUI, parser PowerShell, simulations fictives F1/F2/F4 ont réussi. P15A workflow `41240685028` et N1 `41240684981` également `success`.

**Négatifs réellement déclenchés durant la revue** : sur un commit précédent, un cas d'entrée `chair` n'appartenait pas au `OBJECT_CATEGORIES` F1-A (remplacé par `toy`, sans extension du modèle) ; le code-test d'arrêt immédiat ciblait encore `sqlite_writer_instances` au lieu de `experience_memory_instances` (corrigé). Une fois corrigés, la **nouvelle** exécution de 2 006 tests a réussi : ne pas attribuer ces deux fautes historiques à la sûreté OEM. Aucun Qwen, robot, NPU, moteur, caméra, backend RAUC ou image Yocto construite dans le lot.

**Décision à cette révision :** P15-B1 a franchi les tests PC-fixtures/CLI/signal, **pas** le portage comme service autonome. Un seul `ExperienceMemory` par processus (qui peut initialiser son fichier local), aucune seconde base SQLite. La PR demeure en brouillon sur #235 ; fusion conditionnée à CI au dernier HEAD et résolution de #230 rouge. L'image P16 déjà validée reste sur une **autre branche**, elle ne contient pas ce nouveau module.


## Objectif et sources de vérité

**Objectif concret :** prouver qu'un *vrai processus Python hôte* peut démarrer, lire au plus 16 observations d'un **socket de fixture indépendant**, réutiliser la cognition/mémoire existantes, se dégrader en inaction et s'arrêter avec SIGTERM, sans piloter de moteurs ni capturer d'image. Le manque face aux démonstrations F1/F2 existantes est **l'acceptation d'une source fictive externe au scénario préprogrammé et un arrêt contrôlé du processus**. Ce n'est ni l'activation d'un service sur le robot ni un nouveau contrôleur.

**Révision de base :** `feature/per-p15a-readonly-health-probe-dev@b5626a2cafabd0836e69685d18988360d3e86f18` (PR #235, CI spécialisée, Python et N1 vertes à cette révision) ; `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068` lors de l'audit. Gitlinks OEM **inchangés** : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Paquets DEV P14B/P15A et WIC P16 déjà évalués sur WSL2 dans PR #238 **distincte** ; ne pas relancer ces builds pour ce lot. `docs/plan-action.md` demeure l'autorité.

## P15-B0 — écart mesuré dans les sources

- Arbre GitHub de la branche P15A parcouru : **134 fichiers Python** dans `microduck_companion/` ; `pyproject.toml` n'annonce pas de `[project.scripts]`, et pas de `microduck_companion/__main__.py`, `cli.py`, `runtime.py` ou `companion.py`. **Cela ne signifie pas « aucun main() »** : `passive_demo.py`, `passive_resilience_demo.py` et plusieurs autres modules possèdent déjà des CLI de **démonstration fictive**.
- `microduck_companion/passive_resilience.py`, `PassiveCycleSupervisor.run_once` : quotas et budget post-hoc, mémoire `ExperienceMemory` unique, repli en absence de source et interdiction de moteur ; exige **`FixtureUnixReader`**, non une caméra ou des événements OEM authentifiés.
- `passive_sources.py` : `FixtureUnixReader` refuse l'usurpation de provenance ; `probe_official_mediad` ne demande que `hello`, **pas `media.frame`** ou détection authentifiée. `sim_ipc.py` est un client RPC lecture seule **au niveau applicatif seulement**, mais le groupe `robot` donne accès Unix à tout le socket, ce qui ne prouve aucun privilège matériel restreint.
- `kwipi-readonly-probe.service` P15A : `Type=oneshot`, manuelle, sans `[Install]`, appelle seulement `robot.health` une fois ; le rootfs P16 a vérifié son inactivation. **Ne pas transformer ce probe en daemon**, ne pas ajouter d'activation automatique, ne pas publier de nouvelle image.
- Tests déjà réutilisables : `tests/test_passive_resilience.py` (F2-D, redémarrages/caches, budgets), `tests/test_passive_sources.py` (vrai faux socket Unix), `tests/test_passive_rhythm.py` (repli), `tests/test_sim_ipc.py` (refus RPC moteur). **Ce sont des fixtures PC, pas de la robotique réelle.**

**Manque concret restant :** aucun contrat de lancement externe et d'arrêt coopératif n'est testé sur un processus factice autonome de durée bornée. Il serait redondant de réinventer une machine de cognition, une SQLite, un bus moteur ou une pile de capture.

## P15-B1 — sélection réutiliser / adapter / créer

| Composant | Décision | Limite prouvée |
| --- | --- | --- |
| `PassiveCycleSupervisor`, `PassiveCycleLimits` F2-D | **Réutiliser tel quel** | Cycles Python hôte seulement ; budgets post-hoc |
| `FixtureUnixReader`, protocole F1-B et `ExperienceMemory` | **Réutiliser tel quel** | Provenance `mock`, pas un capteur OEM |
| `AutonomyBrain`, `PassiveObservationJournal`, `PassiveLearning` | **Réutiliser tel quel** | Une seule SQLite, propositions jamais actions |
| `passive_resilience_demo` | **Réutiliser comme témoin, pas comme service** | Source et chronologie écrites dans le scénario |
| `passive_fixture_runtime.py` | **Créer un seul adaptateur CLI borné** | Accepte un socket fixture externe ; refuse `/run`, `/dev`, `/proc`, `/sys` et les symlinks |
| OEM `robotd`, `mediad`, `tofd`, systemd P15A | **Ne pas modifier ni lancer** | Autorité OEM/sûreté/provenance jamais transférées |

Le nouveau CLI est **hôte/fixture uniquement**, explicitement `--mock-only` ; `--fixture-unix-socket` et `--database` absolus et explicites. Il crée/réutilise **une seule instance de `ExperienceMemory`**, sans deuxième base, boucle interminable, thread de travail, contrôleur moteur, capture ou PC/Qwen. Nombre de cycles `1..16`, attente entre cycles `0,5..2,0 s` ; timeout de lecture 0,4 s, budget de cycle **soft** 1,5 s. Retour de statut synthétique sur stdout sans catégorie/track/identité/fichier média ; erreurs expurgées sur stderr. `SIGTERM`/`SIGINT` posent un `threading.Event` et interrompent l'attente ou la prochaine itération ; une opération SQLite/Unix déjà engagée **n'est pas interrompue brutalement**. Aucun daemon systemd ajouté et **le module n'est pas inclus dans le paquet Yocto actuellement construit**.

### Conditions de tests fixées avant lancement

**Positifs attendus (sur PC avec sockets Unix fictifs seulement) :** un message valide et frais → une catégorie historique `mock` dans la SQLite, zéro effet moteur ; un processus lancé avec `python -m microduck_companion.passive_fixture_runtime --mock-only` termine après ses cycles ; un redémarrage réouvre la même mémoire sans rejouer un ancien événement ; `SIGTERM` provoque un arrêt fini sans lancer de seconde boucle.

**Négatifs :** source absente, JSON invalide ou ancien → `idle` sans nouvelle observation ; chemin OEM (`/run/robotd.sock`, etc.), lien symbolique, chemins relatifs, cycles/intervalle hors bornes ou `--mock-only` omis → STOP avant accès SQLite ; refus des propositions exécutables et aucune commande moteur. Mesurer surtout **nombre de cycles, de lignes inscrites, d'événements acceptés, durée d'arrêt et retour CLI** ; ne pas extrapoler vers CPU/NPU/RSS/thermie du RK3566. Tests de sécurité matériels/permission Unix robot et capture OEM ne font pas partie du lot.

**Critère de passage :** 12 tests `tests/test_p15b_passive_fixture_runtime.py` (dont socket Unix réel factice, deux processus séparés, interruption effective SIGTERM, et négatifs) et CI Python générale vertes au dernier commit de la PR. **En cas de test rouge, erreur de module ou signal non géré : STOP**, corriger dans la branche, ne pas autoriser un déploiement. La PR reste **draft** et dépend de #235 ; aucune fusion si base/CI non conformes. Retour arrière : fermer la PR ou retirer uniquement le module et ses tests, aucune modification OEM/Yocto/robot.

### Exemple de commande de validation (PC Linux uniquement, à ne pas lancer sans source factice)

```sh
python -m unittest discover -s tests -p 'test_p15b_passive_fixture_runtime.py' -v
# Un scénario réel de tests crée temporairement un socket synthétique avant :
# python -m microduck_companion.passive_fixture_runtime --mock-only \
#   --fixture-unix-socket /tmp/kwipi-synthetic.sock \
#   --database /tmp/kwipi-fixture.sqlite3 --cycles 4 --interval-s 0.6
```

## Limites et véritable porte P15 suivante

Le résultat positif **ne rend pas Kwipi autonome, ne fournit pas de perception authentifiée, n'autorise aucune action OEM** et ne prouve ni que `robotd` répond sur RK3566 ni qu'une unité systemd de production peut lire son socket sans privilège moteur. Pour un P15 déployable, il faudra choisir et tester une **observation officielle authentifiée** qui ne monopolise pas `mediad` ni le contrôle 50 Hz, une permission réduite ou décision OEM prouvée, un budget cible et un cycle d'arrêt. Aucun chantier motorisé, aucune politique supplémentaire, aucun binaire d'installation avant preuve. **P16 IMAGE DEV WIC validée séparément, RAUC R0 métadonnées OK mais clés DEV absentes, P17 non qualifié.**
