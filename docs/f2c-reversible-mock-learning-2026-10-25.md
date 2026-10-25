# F2-C — Conséquences passives fictives, corrections et préférences graduelles

**25 octobre 2026 — Lot logiciel F2-C, branche dédiée.**
**Portée :** observations de catégories **fictives** déjà présentes dans la SQLite F1-C, sans capteur ni action réellement exécutée.

## Objectif et distinction des preuves

Le cerveau disposait déjà de scores de motivations (F2-B) et de catégories historiques (F1-C). Ce lot mémorise **ce que prouve une nouvelle ligne d'observation fictive** : première catégorie, répétition, doublon de même trame, catégorie indéterminée, annotation inutilisable. Il ne déduit **jamais** qu'une proposition `observe`, `listen`, `inspect` ou `idle` a été exécutée ni qu'elle a provoqué l'observation suivante. Les sorties `mock` ne deviennent pas des observations réelles. La boucle « conséquence *d'une action physique* → préférence » reste hors périmètre.

Aucune attribution à un chien/individu, aucune reconnaissance vocale, aucune vidéo/voix stockée, aucune commande `robotd` ou `mediad`, aucun réseau ni Qwen.

## Implantation

- Nouveau module `microduck_companion/passive_learning.py` : `PassiveLearning(ExperienceMemory)`, dans **la même SQLite** que F1-C et le cerveau existant. Une conséquence prend uniquement comme preuve une ligne **déjà journalisée** par `PassiveObservationJournal.append`, provenant du canal Unix fictif `mock_fixture_unix`. Elle n'est évaluée que dans la session courante et au plus **2 secondes** après son enregistrement.
- Table `passive_learning_events` indexée par l'identifiant historique F1-C : enregistrement **idempotent**, résultat calculé et correction par motif fermé (`fixture_annotation_error` / `source_retracted`). Une correction marque la contribution inactive et **recalcule** les contributions restantes dans l'ordre du journal sans effacer l'archive F1-C.
- Table `passive_attention_preferences` pour `observe` et `listen` seulement : ajout de **+0,020** pour la première catégorie distincte, **−0,005** pour une répétition, bornes **[−0,120, +0,120]**. Dans une trame, plusieurs pistes de même catégorie ne comptent qu'une fois. Les catégories `unknown`, conflictuelles ou sous le seuil ne modifient rien.
- `AutonomyBrain.propose_balanced_passive(..., learning=instance)` peut **facultativement** ajouter cette petite valeur aux scores de F2-B. Sans cet argument, les règles F2-B restent strictement identiques. La mémoire d'une **catégorie** ne devient pas un événement courant, la priorité ne devient pas une exécution.
- Les préférences de mouvement `intent_preferences(environment='simulator', action='explore')` restent **séparées** : ni les essais MuJoCo ni les hypothèses de LLM n'entrent dans les calculs F2-C.
- En cas de source absente, catégorie non validée ou table des préférences indisponible, la voie cognitive choisit une intention `idle` ou n'apprend rien. La voie de sécurité motorisée reste inchangée et sans sol vérifié propose `halt`.

## Vérifications logicielles

Suite `tests/test_passive_learning.py` : scénarios de découverte puis répétition et persistance après réouverture de SQLite avec nouvelle origine monotone ; reprise idempotente d'une même séquence ; doublons de catégories au sein d'une trame ; son et objet indépendants ; provenance fictive obligatoirement conservée ; refus des données futures/périmées, contradictoires ou sous-confiantes ; corrections multiples avec recomposition ; bornes mathématiques ; changement d'arbitrage **uniquement** avec `learning` explicite ; absence de moteur et conservation du `halt` de sûreté.

Reproduction dans un checkout du dépôt :

```bash
python -m unittest discover -s tests -p test_passive_learning.py -v
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
```

L'environnement de preuve est **Python et SQLite sur fixtures fictives**, pas un simulateur MuJoCo de perception, ni le RK3566.

## Limites et décision de suite

La préférence F2-C reflète la **nouveauté/répétition constatée dans le journal fictif**, non un succès ou un échec d'action du robot. Une correction ne supprime pas les données de F1-C ni leur comptage historique par le chemin F2-B ; elle corrige exclusivement les contributions et le biais de F2-C. Cette distinction reste visible et exigera une décision spécifique avant des corrections de faits réels.

L'énergie motivationnelle demeure fictive. Les chiffres de CPU, RAM, latence et consommation ne sont pas transposables à la carte physique. Aucun mouvement, caméra/microphone ou NPU vérifié. La locomotion P0/P1 reste en attente.

**Suite, dans une PR séparée après validation : F2-D**, reprise et pannes multi-sessions, budgets et latences réelles de l'environnement logiciel ; ne pas ouvrir F3 ou de tests moteurs dans F2-C.
