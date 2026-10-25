# F1-D — Démonstration passive intégrée : découverte, souvenir et repli sûr

**Date : 25 octobre 2026. Statut : fusionné dans `main` ([PR #27](https://github.com/Jean-Philippe56520/Microduck/pull/27)), [351 tests Python + deux processus CLI réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40235779649). Démonstration sur données FICTIVES, sans moteur.** Cette étape réunit [F1-A](f1a-passive-observation-contract-2026-10-25.md), [F1-B](f1b-passive-source-2026-10-25.md) et [F1-C](f1c-passive-sqlite-memory-2026-10-25.md) sans ajouter de modèle d'IA, de commande motrice ou de service parallèle.

## Objectif et protocole réel des tests

Deux **processus Python indépendants** lancent le module `microduck_companion.passive_demo` avec les arguments `--session first` et `--session second`, chacun démarrant temporairement **son propre faux serveur de catégories sur un socket Unix local**. Ils partagent **exactement le même fichier SQLite** via `ExperienceMemory` / `PassiveObservationJournal`.

Les trames JSON fictives sont ingérées par le **véritable lecteur F1-B** `FixtureUnixReader`, classées par le **véritable projecteur F1-A** `summarize_passive` (également appelé à l'insertion F1-C), puis conservées par la **véritable SQLite F1-C**. Le cerveau Python existant `AutonomyBrain.choose_from_snapshot` propose **`halt` à chaque cycle** car les catégories d'objet et de son ne prouvent **ni la sécurité du sol, ni la distance obstacle, ni l'état du robot**. Aucune intention n'est envoyée à `robotd` : `halt` est une décision logicielle journalisée, **pas un arrêt moteur réellement exécuté**.

La démonstration utilise une **horloge monotone fictive** (origine différente pour chaque session) et des horodatages Unix fictifs séparés pour le journal. Le programme vérifie les séquences et refuse **avant toute insertion** de lancer la seconde session sans les cinq lignes attendues de la première, ou de répéter la première session sur une base non vide.

## Parcours attendu (10 cycles, 8 lignes de catégories)

| Session | Cycle | Signal transmis sur le faux socket | Décision sur la catégorie | SQLite |
| --- | ---: | --- | --- | --- |
| A | 1 | `ball`, confiance 0,96 | **`new_category`** : premier libellé « balle » fictif | +1 |
| A | 2 | `ball`, nouveau relevé | **`previously_seen_category`** | +1 |
| A | 3 | `ball` **et** `toy` avec même suivi éphémère | **`conflict`, `unknown`**, pas de vote arbitraire | +1 |
| A | 4 | `unknown` | **`unknown`**, aucune identification inventée | +1 |
| A | 5 | Socket coupé avant réponse | **`unavailable_or_invalid`**, aucune ancienne catégorie réutilisée | +0 |
| A | 6 | Son fictif `knock` (sans microphone) | **`new_category`** | +1 |
| B | 1 | `ball`, compteur monotone reparti de zéro | **`previously_seen_category`** après réouverture de SQLite | +1 |
| B | 2 | `dog` (catégorie, **pas un individu**) | **`new_category`** | +1 |
| B | 3 | Nouvelle coupure de la source | **AUCUN événement**, `halt` conservateur | +0 |
| B | 4 | Nouvelle observation `ball` | **`previously_seen_category`** sans redonner vie au relevé précédent | +1 |

**Bilan attendu et contrôlé par la CLI :** **6 + 4 cycles**, **5 + 3 = 8 observations journalisées**, **4 occurrences fictives de la catégorie `ball`**, **2 déconnexions**, **10 intentions `halt`**, **0 commande moteur**, **0 identité reconnue**, **0 image ou voix enregistrée**. Les deux processus créent deux `session_id` différents. Le compte de « balle déjà vue » signifie seulement qu'une **catégorie a été notée auparavant** : il ne prouve pas le retour d'un même objet.

Les contrôles `no_raw_media`, `motor_commands_issued`, `oem_sensor_connected` et `physical_robot_validated` sont des propriétés du scénario codé ; **ils ne sont pas des mesures instrumentées sur un robot physique**.

## Exécuter la démo hors robot

Sur Linux, dans le dépôt, **dans deux processus successifs** et sur un répertoire privé hors Git :

```bash
python -m microduck_companion.passive_demo --database /tmp/f1d-demo.sqlite3 --session first
python -m microduck_companion.passive_demo --database /tmp/f1d-demo.sqlite3 --session second
```

La seconde commande échoue si le premier historique manque ou ne correspond pas ; la première échoue si la base comporte déjà des observations F1-D. Pour recommencer proprement, **utiliser un nouveau fichier de test vide**, et ne jamais écraser une véritable base utilisateur. Chaque invocation imprime **seulement des catégories publiques fictives et des statuts** en JSON ; aucune image/voix, `track_id`, nom privé ou ordre moteur. La base SQLite est un artefact temporaire local, **non publié dans GitHub**.

La CI Python exécute :
- des tests unitaires et d'intégration de la démo sur **deux vrais sous-processus**, mêmes SQLite et faux sockets Unix, plus les tests F1-A/B/C ;
- **les deux commandes CLI indépendantes** ci-dessus avec `$RUNNER_TEMP/f1d-memory.sqlite3` ;
- la vérification de syntaxe Python sans sous-modules OEM ni MuJoCo.

## Ce qui est démontré et ce qui ne l'est pas

**Démontré en logiciel :** composition du lecteur fictif F1-B, projection conservatrice F1-A, mémoire persistante F1-C et décision conservatrice du cerveau ; refus des observations contradictoires, des faux faits de sécurité et de la perte de source ; historique préservé après un redémarrage du processus.

**Non démontré :** vision réelle, reconnaissance d'objets par `mediad`, animaux identifiés, mots-clés réels, intégration RKNN/NPU, sécurité des escaliers, sortie sonore ou mouvements, performances RAM/température sur Rockchip, autonomie batterie. `media.frame` et `media.detections` du fabricant ne sont **pas appelés** par F1-D. L'IA Qwen et le robot physique restent hors du périmètre.

**Décision :** les critères de **F1 logiciel sur fixtures** sont couverts ; cela **ne valide pas les capteurs physiques**. La prochaine PR sera uniquement **F2-A**, intentions cognitives passives (`observe`, `listen`, `idle`, `rest`) **sans exécution de mouvement** et sans prétendre que les récompenses fictives prouvent un apprentissage sur robot. Le chantier locomoteur reste suspendu.
