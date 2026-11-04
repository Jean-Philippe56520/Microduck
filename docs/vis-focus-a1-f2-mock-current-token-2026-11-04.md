# VIS-FOCUS-A1 — comparateur hôte d'un seul focus fictif F1/F2, sans modification OEM

**Date :** 04/11/2026. **État :** CANDIDAT PC-FIXTURES, ni déployé ni validé sur robot. Autorité : [plan d'action](plan-action.md). **Porte préenregistrée AVANT code :** [issue #78, A0](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6639783194) puis [A1](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6640438838), [amendement B10/B11](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6640611915).

## Référence GitHub et témoin

- Base exacte avant lot : `main@432c2e7e3628b2defdabd7fa9024f7f18af8b44a`, après fusion de [#305 QUAL-R0](https://github.com/Jean-Philippe56520/Microduck/pull/305) et 10/10 CI vertes. Branche : `feat/vis-focus-a1-ephemeral-f2-focus-20261104`.
- Les sources existantes F1 `perception.py`, `passive_observations.py`, `passive_sources.py` savent présenter des observations multiples, chacune avec `track_id` **éphémère**, catégorie, confiance et TTL. `PerceptionSnapshot.to_scene()` en réduit historiquement la vue à un seul objet.
- `AutonomyBrain.propose_balanced_passive()` et `PassiveRhythm.tick()` arbitrent déjà les **catégories** selon motivations, jeu, familiarité F1-C et options DET-1/2 / EX3 dans l'unique `ExperienceMemory`, sans commande motrice. Le résultat `PassiveIntent` ne désigne **aucune piste parmi deux objets de même catégorie**. Ce manque est une limite de contrat démontrable par inspection et les fixtures nouvelles, pas un défaut de détecteur démontré.
- `yolox_attention_candidates.py` sait décrire jusqu'à trois boîtes COCO **sur PC**, sans identité, suivi ou flux OEM. `mediad`/ `duck-detect` OEM épinglés ne publient pas encore de catégorie multi-objets ni d'identifiant de suivi utilisable dans F1. Aucune adaptation OEM approuvée par ce lot.

## Arrêt confirmé et adaptation du protocole sans toucher B10/B11

L'essai initial dans `microduck_companion/autonomy.py` (PR #307, HEAD temporaire `6d662eb59b8d0e067adf97708218153167706d69`) a fait réagir **cinq gardes CI** d'intégrité B10/B11 : `Refused: the historical 19+5 B10 sources changed` et empreinte P14B différente. **Il s'agit d'un STOP légitime**, non d'un défaut à masquer en modifiant les SHA historiques. Le fichier `autonomy.py` a ensuite été **restauré octet pour octet** à la version `main@432c2e7e...` (blob `476051625738c8102918c91fd0293c629620bce1`). Les essais ont été déplacés hors de `microduck_companion` vers `experiments/vis_focus_a1_host.py` ; les tests importent désormais ce comparateur hôte. La même hypothèse et les 4 P/8 N demeurent, sans prétendre livrer une fonction embarquée. Voir [amendement de porte #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6640611915).

Ce lot ne doit ni mettre à jour le manifeste d'archives B10/B11, ni modifier les licences, recettes, sous-modules, poids ou SHA de référence pour faire passer la CI. Un futur raccordement productif exigerait un lot de distribution distinct, avec accord et qualification du matériel.

## Candidat limité au banc PC : réutiliser F1/F2, pas de tracker

Un **comparateur expérimental PC uniquement**, `experiments/vis_focus_a1_host.py:HostFocusComparator.describe_mock_visual_focus(...)`, et une sortie non motrice `MockFocusHint`. **L'AutonomyBrain de production demeure byte-identique à main** ; cette étude ne modifie pas son API :

1. Vérifient uniquement les fixtures F1-B `mock_fixture_unix`, la séquence et le temps monotone ; refusent lecture absente, source étrangère, trame périmée, future, réordonnée, contradictoire ou faible confiance.
2. Réutilisent **l'intention F2 déjà sélectionnée**. Si F2 a choisi `observe ball`, distinguent une piste courante parmi les `ball` observées, préférant le **même jeton toujours présent et frais**, sinon la confiance puis l'horodatage. Un `idle` dû au cooldown peut conserver **l'intérêt descriptif** seulement si cette même piste est **à nouveau visible et fraîche** dans la fixture.
3. Sur perte de piste, effacent immédiatement `current_track_id` ; un autre ID de la même catégorie reste **un nouvel intérêt**, jamais une ré-identification. Aucun cache de localisation, flux d'images, correspondance IoU, prédiction de trajectoire ou tentative de déplacement.
4. Conservent l'état de cet intérêt **uniquement dans la RAM du comparateur PC extérieur à Companion**, jamais dans l'AutonomyBrain livré ni dans SQLite ; les conditions `physical_identity_verified=False`, `location_verified=False`, `motor_commands_issued=0` sont obligatoires dans le résultat. Les préférences/motivations et l'intention F2 ne sont pas modifiées par la description.

**Ce qui n'est PAS réalisé :** détecteur multicatégorie embarqué, suivi physique fiable, persistance d'identité d'un visage/animal/objet, focus moteur, poursuite, temps réel, distinction TV/photo/personne réelle, estimation de distance, anti-escalier, nouvelle autorisation OEM, apprentissage causal. Le `track_id` reste une **valeur fictive fournie par la source**, pas une preuve géométrique. Une sortie `continued` signifie seulement « même jeton frais déclaré », pas « même objet physique confirmé ».

## Porte A1 et critères fixés avant tests

**Comparateur** : F1/F2-B/SQLite existants sur les mêmes séquences et motifs (sortie de catégorie uniquement). **Candidat hôte seulement** : ces **mêmes décisions F2**, lues par le comparateur expérimental extérieur, suivies par la description facultative d'une **seule piste courante**, sans nouveau modèle, image ou politique. **Gain minimal attendu** : désambiguïsation descriptive de deux balles simultanées que `PassiveIntent` ne peut pas distinguer, sans transformer cette désambiguïsation en identité ou coordonnées.

- **P1–P4** : au moins trois objets (dont deux balles) → un seul indice frais ; continuité du même jeton explicite pendant un cooldown F2 ; nouvelle cible sélectionnée par F2 sur observation courante ; perte puis nouveau jeton = **nouvel** intérêt.
- **N1–N8** : source perdue ou non fiable ; TTL dépassé ; temps futur/séquence rejouée/reset ; conflit d'étiquettes ; confiance faible ; échange de jetons de même catégorie ; écran/photo/peluche ne prouvant aucune présence physique ; absence de sûreté sol/ToF/opérateur n'autorisant aucun moteur.
- Tests supplémentaires : familiarité de catégorie dans la **même SQLite**, objet inconnu et rejet des entrées non passives / invalides.
- **PASS logiciel conditionnel** = 4/4 P + 8/8 N, suite générale CI au dernier HEAD entièrement verte, aucun changement d'intention F2, zéro écriture SQLite *par description*, zéro nouvelle commande/action et gitlinks inchangés. **STOP** si un garde négatif échoue, si CI est rouge/en attente, ou si le témoin couvre déjà le même besoin sans candidat. Retour arrière = revert ciblé du complément et des tests.

## Cadence, perspective et distance

Cette preuve porte uniquement sur des événements synthétiques F1-F2, **pas des pixels** : elle ne mesure aucun taux de reconnaissance, FPS matériel, coût NPU, angle ou distance. `2 Hz` reste la référence de **l'analyse visuelle prévue** ; `1,5 / 1 Hz` devront être comparés sur les **mêmes séquences horodatées indépendantes** en étudiant pertes/réacquisitions, latence et coût mesuré, sans coder de cadence adaptative. En absence de GT métrique, indiquer `viewpoint_height=unknown` et `distance=unknown`, sans transformer une taille apparente en portée réelle. Aucun cliché privé nécessaire.

## Frontières et niveaux de preuve

- F1-B `mock_fixture_unix` ne constitue pas une source caméra OEM authentifiée. Les observations, catégories et jetons des tests sont **fictifs**. **Aucun robot physique présent.**
- `robotd` seul propriétaire des moteurs, sûreté et ONNX à 50 Hz ; `mediad` seul propriétaire caméra. Les pin `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` ne doivent pas changer.
- Qwen3.5 9B PC facultatif et suspendu, une unique SQLite `ExperienceMemory`, Yocto/recettes B11 et modèles/poids inchangés. Aucune donnée individuelle, image, empreinte ou secret publié.

**À vérifier avant fusion :** 15 tests ciblés ajoutés sous `tests/test_vis_focus_a1.py` et tous les tests généraux en CI, ainsi que les empreintes figées des sources de distribution. **Une CI verte qualifie uniquement la logique des fixtures PC**, pas le focus autonome du robot.
