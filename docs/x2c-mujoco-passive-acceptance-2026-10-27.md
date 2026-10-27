# X2-C — Acceptation de la cognition passive dans MuJoCo OEM (27 octobre 2026)

**Résultat observé : réussi dans GitHub Actions sur les véritables démons simulés `robotd` et `tofd`.** [CI MuJoCo #40472442011](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40472442011) (étape « Run pinned simulator safety gate » réussie, artefact `mujoco-headless-diagnostics` conservé 7 jours). [CI Python #40472441954](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40472441954) : **1 260 tests exécutés, 19 ignorés, zéro échec**, dont huit nouveaux tests d'acceptation X2-C. Revalidation éventuelle sur la révision finale de PR à signaler séparément.

**Portée :** six cycles *sans moteur* en simulation constructeur, deux sessions Python indépendantes de trois cycles sur la **même SQLite**, mesures hôte et souvenir contextuel vérifié. **Aucune validation sur RK3566, robot physique, caméra, microphone, navigation, reconnaissance de catégories ou apprentissage causal.**

## Réutiliser avant de créer

- **Code constructeur épinglé et confirmé par la CI**, deux fois : gitlinks du dépôt parent **et** HEAD des checkouts sous-modules :
  - `upstream/microduck` : `942e58e3aa6dbb28e7037203fff11866122c7567` ;
  - `upstream/microduck_rl` : `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`.
- À la revue du 27/10/2026, les PR constructeur [#381 — cerveau](https://github.com/pollen-robotics/microduck/pull/381) et [#414 — maploc/mapd](https://github.com/pollen-robotics/microduck/pull/414) restent **ouvertes, non fusionnées**. Aucune API, politique de mouvement ou concept non livré n'est utilisé.
- **Réutilisé** sans remplacement : `scripts/sim-smoke.sh`, `.github/workflows/mujoco-smoke.yml`, `duck-sim`, `robotd` (boucle OEM 50 Hz), `tofd`, `sim_ipc`, `sim_bridge`, `PassiveSimCycleRunner` P2b, `AutonomyBrain`, `ExperienceMemory` et `sim_passive_cycles` X2-B.
- **Adapté** : instrumentation volontairement limitée à `run_session` avec `time.perf_counter()`, `time.process_time()`, le pic `resource.ru_maxrss` sur Linux et la taille des fichiers SQLite/WAL. La mesure p95 suit le **rang le plus proche** : sur trois cycles isolés, p95 = maximum ; sur six cycles, p95 reste le maximum de l'échantillon.
- **Créé** : `sim_x2c_acceptance.py` (vérificateur de deux fichiers JSON et d'une SQLite existante, **ouverte en lecture seule**), huit tests de refus et un artefact JSON de synthèse. Aucun nouveau contrôleur moteur, capteur, classificateur, modèle, journal SQL séparé ou base SQLite.
- **Tiers consultés, non intégrés** : QuackNav/microduck-brain (navigation, protection de chute supplémentaire propre à leurs contrôleurs), microduck-twin (extension audio), microduck-lab/studio (bancs et outils). Résultats/versions tiers non transférables à notre système ; pas de code, poids ou média tiers copiés.

## Scénario réellement exécuté

Le workflow a installé les dépendances du corps MuJoCo headless et lancé `upstream/microduck/scripts/duck-sim up` sur les **deux gitlinks exacts**. Il a conservé le `sim_probe`, le `sim_observer` et les diagnostics historiques, puis, par opt-in exclusif à la branche X2-C, exécuté :

1. Processus indépendant A : `sim_passive_cycles`, `x2c-session-a`, **3 lectures fraîches**, nouvelle SQLite `x2c-passive.sqlite3`.
2. Processus indépendant B : même commande, `x2c-session-b`, **3 nouvelles lectures**, **même fichier SQLite**, sans le supprimer ou recréer.
3. Processus d'acceptation : contrôle des révisions, de six lignes SQL, de la correspondance exacte aux deux JSON, des liens mémoriels, de l'intégrité SQLite, de l'absence de récompense/identité/préférence/mouvement, et édition de `x2c-acceptance.json`. Les données brutes des 8×8 zones ToF, images, audio et identifiants de personne ne figurent pas dans ce rapport.

Les seules méthodes de télémétrie demandées par Companion restent `robot.health`, `robot.subscribe`, `tof.stream`. Les opt-in des tests de mouvement de la famille J2/P0 sont **refusés en parallèle** de X2-C. Le simulateur lui-même peut faire jouer ses politiques OEM de mise debout ; cela **ne constitue pas** une commande motrice de Companion.

## Preuves effectivement constatées

| Contrôle | Résultat de la CI MuJoCo #40472442011 |
| --- | --- |
| Session A | 3/3 cycles cohérents |
| Session B | 3/3 cycles cohérents, deuxième processus |
| Intentions du plan existant | **6 × `halt`**, aucune marche ou repos exécuté |
| États descriptifs attention X2-B | **6 × `idle`** ; pas de transition de batterie faible inventée |
| Comparaisons | Première `no_reference`, puis **5 × `stable_band`** |
| Souvenirs référencés vérifiés | **5**, dont **1 franchissant la séparation des sessions** |
| SQLite persistante | **6 lignes**, intégrité `ok`, **40 960 octets** ; WAL **0 octet** après fermeture |
| Actions motrices émises par Companion | **0** |
| Conséquences/rewards attribués à des actions | **0** |
| Objets/personnes mémorisés par cette voie | **0** |
| Appels au PC/Qwen | Aucun client PC configuré dans ce banc X2-C |
| Matériel physique certifié, sol réel sûr | **Non**, explicitement faux dans le JSON |

### Mesures sur le serveur hôte GitHub (pas RK3566)

| Mesure | Valeur |
| --- | ---: |
| Acquisition télémétrie, p50 sur 6 cycles | **67,023 ms** |
| Acquisition télémétrie, p95 sur 6 cycles | **78,650 ms** |
| Décision/journalisation, p50 sur 6 cycles | **1,462 ms** |
| Décision/journalisation, p95 sur 6 cycles | **1,791 ms** |
| Pic RSS du processus Python, session A | **19 016 Kio** |
| Pic RSS du processus Python, session B | **18 976 Kio** |
| Temps CPU du processus, session A | **7,865 ms** |
| Temps CPU du processus, session B | **6,383 ms** |
| Durée murale du run, session A | **1 347,908 ms** |
| Durée murale du run, session B | **1 417,511 ms** |

**Interprétation :** ce sont six mesures peu nombreuses, prises sur un exécuteur Ubuntu GitHub ; les p95 sont des maxima d'un échantillon minuscule, non des percentiles de production. RSS = maximum du processus Python lui-même, **pas** mémoire totale de `robotd`, MuJoCo ou des démons OEM, et **pas** surcharge incrémentale. Temps CPU limité au corps du cycle, non au démarrage de Python/imports. Stockage SQLite mesuré pour six lignes seulement ; la table historique P2b ne dispose toujours pas d'une rétention globale. La persistance et la comparaison de **statuts de batterie** ne sont pas l'apprentissage d'une cause ou d'une préférence. Les six `halt` sont des résultats prudents, **pas** une démonstration de comportement moteur ou exploratoire.

## Tests négatifs et sécurité

`tests/test_x2c_sim_acceptance.py` (huit tests sur fixtures) refuse notamment : session répétée, ancien journal réutilisé, compte de cycles incohérent, source changée en « robot », preuve de sol ou physique déclarée à tort, mouvement affirmé, qualité de capteur invalide, intention `explore`, lien mémoriel inventé, métriques latence/RSS incohérentes, base SQLite absente, et altération d'un plan persisted. Le vérificateur emploie `sqlite3` **en lecture seule** et n'ajoute aucune table. Les tests Python X1/X2-A/X2-B restent verts.

Les décisions `halt` et `idle` constituent des **propositions ou descriptions**, jamais un ordre aux moteurs ; `robotd` garde l'unique autorité des actionneurs. Un bon JSON n'authentifie ni un démon ni une carte physique ; l'attribution au simulateur OEM repose ici sur les **étapes et les SHA visibles en CI**, et pas sur le contenu d'un paquet.

## Reproduction et jalons restants

Dans un checkout GitHub complet sur Ubuntu avec les dépendances documentées par le workflow, placer les deux gitlinks OEM ci-dessus (ils sont épinglés dans la PR), puis déclencher le workflow `MuJoCo headless smoke test` sur la branche X2-C. Le `push` sur cette branche active `DUCK_SIM_X2C_ACCEPTANCE=YES` (les opt-in moteurs restent désactivés). L'artefact temporaire `mujoco-headless-diagnostics` contient `x2c-passive-session-a.json`, `x2c-passive-session-b.json`, `x2c-acceptance.json` et les logs utiles. Aucun média privé n'est requis.

**Validation obtenue :** contrats logiciels testés + intégration sur **vrais démons OEM dans MuJoCo** (observations, mémoire SQL, qualité, abstention, coût hôte). **Non obtenue :** reconnaissance visuelle Cat-A2b [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78), imitation des 16 animations OEM, comportement autonome motorisé, causalité d'une action effectivement exécutée [#80](https://github.com/Jean-Philippe56520/Microduck/issues/80), activation « Hé Kwipi ! » [#81](https://github.com/Jean-Philippe56520/Microduck/issues/81), contraintes mémoire/thermie RK3566 et robot réel [#82](https://github.com/Jean-Philippe56520/Microduck/issues/82). X2-C ne peut certifier ni sol sûr, ni navigation libre, ni autonomie en présence d'enfants/animaux.

**Prochaine décision :** conserver #79 comme base d'intégration fermée **uniquement après fusion de la PR X2-C**. Reprendre Cat-A2b si vraies prises autorisées disponibles ; sinon planifier EX4 [#80](https://github.com/Jean-Philippe56520/Microduck/issues/80) sur une source de preuves d'exécution sans perturber `robotd`.
