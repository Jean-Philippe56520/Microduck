# MEM-C-TIME — intégrité temporelle du rappel F4-A (préenregistrement du 03/11/2026)

**Ce document est créé avant toute modification des sources/tests de ce lot.** Base `main@318c8fb01f00ba55e2facafb4d7958bce4eb3e87` au début du chantier, après P17-S17/#279 ; la PR PER-P4L1/#280 est distincte, en vérification finale, et ne modifie pas le code de la mémoire.

## Objectif / manque prouvé dans le code

Kwipi ne doit pas réutiliser une catégorie historique comme souvenir récent si le champ `recorded_epoch_s` de sa projection F4-A diverge de la date dans son journal F1-C source. **Observation de source :** `microduck_companion/category_semantics.py::CategorySemantics.recall` compare les catégories, les types, les confiances et les activités F1-C/F2-C, puis filtre **uniquement** la date de la projection `s.recorded_epoch_s`. Il manque `AND s.recorded_epoch_s=j.recorded_epoch_s`. Au contraire, `microduck_companion/memory_consolidation.py::recall_category` comporte déjà cette égalité. Une projection obsolète, incohérente ou malencontreusement rajeunie pourrait donc être retournée par F4-A bien que son observation source ait expiré. Cela n'établit pas qu'une corruption s'est produite sur un robot ; c'est un **écart de contrat démontré statiquement** entre deux lecteurs du même stockage.

**Risque :** présenter une observation `mock_fixture_unix` périmée comme fraîche, puis faire croire à une continuité/habitude sans preuve ; la voie F4-A est historique et pas une identité physique. L'objectif ici est uniquement de maintenir l'accord des preuves entre F1-C et F4-A en lecture seule.

## Réutiliser / adapter / ne pas créer

- **Réutiliser** l'unique `ExperienceMemory` SQLite, le journal `PassiveObservationJournal` F1-C, le suivi `PassiveLearning` F2-C, `CategorySemantics` F4-A et l'oracle conservateur `memory_consolidation.recall_category` C1. Ne changer aucune table, colonne, migration, API, horloge F2, modèle, seuil de reconnaissance ou souvenir d'objet.
- **Adapter** uniquement la jointure SQL de `CategorySemantics.recall` pour exiger **l'égalité stricte des dates originales et projetées**, comme C1 ; ajouter deux tests adversariaux ciblés au fichier `tests/test_category_semantics.py` existant, sans créer de module de tests.
- **Ne pas créer** de deuxième SQLite, nouvelle mémoire, moteur, fonction Qwen, daemon, pilote, donnée privée ou dépendance. Les projets tiers du registre C3 n'apportent rien à ce contrôle local. Sous-modules conservés : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. OEM main distant différent, non adopté. Qwen #97–99 fusionnées, hors champ.

## Positifs / négatifs et critères fixés **avant** essai

1. **Témoin positif :** une observation fictive `cat` enregistrée/validée via F1-C → F2-C → F4-A est relue exactement une fois par `CategorySemantics.recall` ; en l'absence de corruption, C1 retourne la même présence historique. Aucune identité ou présence physique vérifiée.
2. **Négatif A — rajeunissement de la projection :** la ligne source conserve `WALL`, alors que la projection F4-A est forcée à `WALL + RETENTION_S + 0,5` ; à `WALL + RETENTION_S + 1` le lecteur F4-A doit rendre **zéro** observation, tout comme C1. Sans égalité de dates, l'ancienne implémentation retournerait à tort une entrée récente.
3. **Négatif B — réécriture de la date source :** une ligne F1-C validée reçoit après coup un horodatage différent et F4-A garde l'ancien ; même avec les deux dates dans la fenêtre autorisée, F4-A et C1 doivent **tous deux** retourner zéro observation.
4. **Retour positif / relecture :** quand la date cohérente et la provenance actives sont rétablies, F4-A renvoie l'entrée ; un redémarrage via une deuxième connexion **séquentielle** au même fichier SQLite doit garder le résultat correct. La correction F2-C existante doit ensuite retirer le souvenir.
5. **Lecture seule / refus :** `conn.total_changes` doit rester identique avant et après les requêtes ; zéro commande moteur, Qwen, identité ou récompense. Deux négatifs doivent rester invisibles, un positif visible, sans modifier les autres tests.

**Succès** : deux négatifs rejetés + témoin positif/rétablissement + pas d'écriture + tests ciblés et CI Python de la PR verts. **Arrêt** : si un négatif reste visible, si un rappel intact disparaît, si une ancienne table doit être migrée, si les suites régressent ou si un nouveau composant apparaît, conserver l'échec et **ne pas fusionner**. Pas de réglage sur des photographies ni de test sur robot. Les tests demeurent **PC/fixtures inventées**, sans bénéfice cognitif interscènes attesté.

**Retour arrière :** retirer une condition SQL et les tests associés ; aucune conversion, base nouvelle, service, image B11 ou sous-module OEM à restaurer. Ce lot ne prétend pas débloquer M1-B/MEM-2B (0/48 sur ABO), la reconnaissance réelle, l'apprentissage causal ou la V1 shipping.
