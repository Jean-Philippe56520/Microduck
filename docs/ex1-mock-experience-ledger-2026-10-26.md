# EX1 — Journal des intentions et résolutions fictives de Kwipi

**26 octobre 2026. Statut : code sur branche [PR #70](https://github.com/Jean-Philippe56520/Microduck/pull/70), [CI hôte réussie #40410788233](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40410788233) : 1 111 tests exécutés, 19 ignorés, zéro échec (dont 12 scénarios EX1) ; aucune action physique et aucun résultat de conséquence/causalité.** Cette phase commence l'[architecture d'apprentissage par l'expérience](kwipi-experiential-learning-plan-2026-10-26.md) sans prétendre que Kwipi a accompli une action réelle. La priorité Cat-A2b, ses vrais angles bas indépendants et les contraintes robotd sont inchangés.

## Objet

Distinguer explicitement trois états : **une proposition** (`proposed`), **la résolution d'une expérience fictive** (`mock_executed`) et **le refus/interruption** (`refused`, `interrupted`). `mock_executed` ne prétend pas mesurer une commande robot, ni même une observation caméra ; il est uniquement fourni par un témoin de scénario fictif. La conséquence positive/négative et la causalité sont le périmètre **EX2**, non EX1.

L'objectif est d'éviter que « Kwipi a envisagé d'inspecter » se transforme en « Kwipi a inspecté et appris ». Aucun résultat n'est transféré dans les préférences F2/P-B/F4-A.

## Matrice réutiliser / adapter / créer

| Source vérifiée | Décision EX1 et motif |
| --- | --- |
| OEM épinglé `942e58e3...` : `robotd`, `mediad`, `tofd`, `pet-detect`, scripts constructeur | **Ne pas modifier.** Pas de primitive physique, de nouvelle acquisition ou de client OEM dans ce lot. `robotd` conserve toute autorité moteur. |
| [OEM PR #381](https://github.com/pollen-robotics/microduck/pull/381), [#414](https://github.com/pollen-robotics/microduck/pull/414) | **Veille, ouvertes à la vérification**. #381 est un document de design sans cerveau livré, #414 cartographie hors périmètre. Aucun import. |
| [`AutonomyBrain`](../microduck_companion/autonomy.py), [`PassiveIntent`](../microduck_companion/passive_intentions.py) | **Réutiliser sans changer** : `record_proposal()` exige l'objet F2 validé, ne crée pas une seconde sélection d'intentions. |
| [`ExperienceMemory`](../microduck_companion/episodic_memory.py) | **Réutiliser la même connexion SQLite**, seul propriétaire du magasin. Ajout minimal de la table EX1 pour une transition d'état d'expérience, sans refonte de la mémoire existante. |
| [P2a `mock_cycles`](../microduck_companion/mock_cycles.py), [F4-A `BehavioralMemory`](../microduck_companion/behavioral_memory.py) | **Ne pas doubler l'écriture** : P2a/F4-A contient des conséquences fictives d'inspection, mais ne décrit pas le cycle **F2 PassiveIntent proposée → résolution**. EX1 n'importe ni ne réécrit P2a/F4-A, ne calcule pas de récompense. Le futur branchement devra choisir une seule écriture autorisée par événement, dans une PR séparée. |
| [F5 Qwen](f5c-sparse-consultations-2026-10-26.md) et [registre C3](community-reference-registry-2026-10-26.md) | **Aucun appel** PC ou modèle ; hypothèses non converties en actes. Tous les tiers restent des références non approuvées. |

**Nouveau code justifié :** `microduck_companion/experience_ledger.py` décrit un état intermédiaire absent des sources, sans boucler, piloter, percevoir ou interroger Qwen. `tests/test_ex1_experience_ledger.py` couvre les transitions et la reprise.

## Contrat et limites

- `MockExperienceLedger(memory: ExperienceMemory)` refuse toute autre base ; crée `ex1_mock_experiences` **dans la connexion existante**, sans toucher aux tables F4-A, M1-A/B ou P2a.
- `record_proposal(intent: PassiveIntent,...)` persiste l'intention F2 non exécutée, la catégorie bornée et le temps du scénario. Il ne sauvegarde ni raison libre, ni image, ni audio, ni identifiant de suivi.
- `resolve(MockResolution(...))` accepte **uniquement** `mock_executed`, `refused` et `interrupted` avec `source='mock_fixture_only'`. Un événement sans proposition, incohérent, périmé (plus de 30 s fictives), rétrodaté ou contradictoire est refusé.
- Un replay strict d'une proposition ou résolution existante est idempotent ; un replay modifiant une preuve est refusé. `retract()` retire une preuve fictive et bloque sa réactivation. `history()` renvoie des traces historiques, toujours `verified_on_robot=False`, `motor_commands_issued=0`.
- Les `session` sont des jetons opaques artificiels `s-<16 hex>` et non des identifiants d'objets/personnes. La `sequence` est contrôlée ; catégories et modalités sont celles de `PassiveIntent`. Personne familière, chat nommé, voix, parole et lieu privé ne sont jamais ajoutés.
- Limites **de laboratoire** : 256 lignes maximum, expiration 14 jours, consultations limitées à 50 lignes, résolution sous 30 secondes fictives. La table et ses index/WAL peuvent occuper plus de place que la donnée logique ; aucune mesure de taille, RAM, CPU ou autonomie sur RK3566 n'est annoncée.
- **Aucun accusé d'exécution physique** n'est accepté. Même une assertion `mock_executed` n'est pas une preuve réelle ; aucune récompense, catégorie confirmée, propriété, action motrice ou mouvement n'en découle.
- La comparaison avant/après, les effets et liens causaux seront définis dans **EX2**, à partir de capteurs réellement autorisés lorsqu'ils existeront. Un avis de Qwen ou une intention F2 ne doivent jamais se transformer en exécution.

## Protocole de tests

Tests ciblés : proposition seule `proposed`, résolution explicite, refus/interruption, expiration, horloge incohérente, source falsifiée, identifiant non opaque, doublon/rejeu divergent, retrait, quota/expiration, lecture interconnexion et **second processus Python** sur la même SQLite. Vérifier **zéro écriture** dans `experiences` ou les préférences, zéro appel `robotd` et absence de promotion d'un mock à un vrai résultat.

Commande standard du dépôt : `python -m unittest discover -s tests -p 'test_ex1_experience_ledger.py' -v`; puis la suite générale en CI de la PR. La réussite de tests software est **uniquement une preuve sur des fixtures**, pas une mesure physique.

## Portes suivantes

1. **Cat-A2b** : photographies réellement basses privées, indépendantes et annotées ; qualité des inconnus et boîtes évaluées avant détection sur robot.
2. **EX2** : relier un avant/après à un identifiant d'exécution explicite, conserver `indéterminé`, séparer retours sociaux et causalité ; scénarios avec faux positifs et rétractions.
3. **EX3** : relecture de conséquences corroborées depuis la **même SQLite** dans F2/P-B, biases faibles, correction, aucune action sans robotd.
4. **EX4–EX7** : Qwen avec consentement, tests de mots sociaux, inventaire des gestes OEM, simulation indépendante, audit matériel F6-D et validation graduelle.

**À ne pas conclure :** que Kwipi a appris d'un humain, d'un chat, d'une balle ou d'une trottinette ; qu'il peut donner un coup de pied, enregistrer de la parole, naviguer ou que le budget 1 Go/32 Go est suffisant. Ce lot ne crée aucune de ces capacités.
