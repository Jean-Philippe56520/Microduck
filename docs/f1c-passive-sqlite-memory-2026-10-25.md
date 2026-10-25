# F1-C — Mémoire persistante des observations passives

**Date : 25 octobre 2026. État : logiciel développé sur branche F1-C ; tests avec catégories entièrement fictives.** La phase F1 reste **incomplète** tant que F1-D (démonstration de bout en bout) n'est pas effectuée. Aucun accès au vrai Microduck, aucune caméra, aucun micro, aucune commande moteur et aucun modèle de reconnaissance n'entrent dans F1-C.

**Références :** [plan directeur](plan-action.md), [F1-A — contrat de catégories](f1a-passive-observation-contract-2026-10-25.md), [F1-B — source fictive bornée](f1b-passive-source-2026-10-25.md).

## 1. Architecture : réutilisation de la même SQLite

Le module `microduck_companion/passive_memory.py` ajoute un **journal distinct dans la connexion SQLite de `ExperienceMemory` déjà existante**, et non un second service ou une seconde base de souvenirs.

```
FixtureUnixReader (F1-B : mock obligatoire)
    -> PassiveRead(status, snapshot, sequence)
    -> summarize_passive (F1-A : confiance, conflits, TTL)
    -> PassiveObservationJournal(ExperienceMemory)
    -> table passive_observation_log (SQLite persistante)
    -> recent() / category_count() après redémarrage
```

- **Conditions d'entrée :** le message doit être un `PassiveRead` avec `status="ok"`, `channel="mock_fixture_unix"`, un `PerceptionSnapshot(environment="mock")` et uniquement des événements `source="mock"` de type `object_label` ou `sound_label`. Tout message `sensor` ou `robot` est refusé. Un échec F1-B (timeout, perte de connexion, débit, doublon) n'ajoute **aucune** ligne. Cette validation logiciel ne prouve évidemment pas l'authenticité cryptographique d'un faux socket ; elle empêche qu'une fixture soit promue au statut de vrai capteur.
- **Projection contrôlée :** on journalise le résultat de `summarize_passive` et **jamais les libellés originaux libres**. Un nom privé ou une catégorie arbitraire devient `unknown`, un désaccord devient `conflict` avec catégorie `unknown`, un faible score devient `low_confidence`, une ancienne mesure `stale`. Une catégorie incertaine ne peut pas remplacer une ancienne catégorie fiable en mémoire : **l'historique les conserve toutes deux avec leur statut**, sans réécrire un « fait ».
- **Champs enregistrés :** `session_id` aléatoire (pour isoler deux exécutions), `sequence` et `ordinal` de réception, date civile `recorded_epoch_s` (secondes Unix), horodatage monotone d'origine **historique seulement**, `kind`, `category`, `status`, `source=mock`, `confidence`, `channel=mock_fixture_unix`. **Pas de track_id, nom, photo, voix brute, transcription, coordonnées, biométrie ou ordre moteur** dans cette table.
- **Reprise :** un nouveau processus ouvre la **même base** via `ExperienceMemory(path)`, crée son propre `PassiveObservationJournal(memory)` et retrouve les catégories dans `recent()` et `category_count()`. La requête `category_count` compte des observations `identified` de **catégorie**, **jamais la réapparition d'un individu**. Un `track_id` éphémère d'une session ne devient pas une identité permanente.
- **Aucune reconfiance temporelle :** le temps `time.monotonic()` sert exclusivement à valider la fraîcheur **dans la session courante** ; après redémarrage, l'ancienne valeur est un champ historique et **ne peut pas rendre une perception à nouveau fraîche**. Le temps civil Unix sert uniquement aux filtres et à la purge. Le journal n'a pas d'interface pour produire une `PerceptionSnapshot` utilisable par les moteurs.
- **Idempotence transactionnelle :** un couple `session_id, sequence` déjà vu ne peut pas être réinjecté avec des catégories modifiées ; l'enregistrement des catégories d'une lecture se fait en une transaction. Les deux processus d'essai possèdent des identifiants de session différents.

## 2. Volume et confidentialité

- **14 jours maximum de rétention logique**, avec suppression physique sur `append()` ou `prune()`, et filtrage temporel sur toutes les requêtes. La purge refuse également les anciennes dates **plus de 60 secondes dans le futur** relativement à l'horloge de nettoyage, pour éviter d'éterniser des données après un saut d'horloge.
- **512 observations maximum** sur cette table ; le plus ancien contenu est supprimé dans la même transaction après insertion. Les requêtes `recent()` sont plafonnées à **100 lignes**.
- **Ce n'est pas une garantie de destruction forensique** des pages SQLite/WAL, des sauvegardes ou du stockage physique : pour des données identifiantes, prévoir un mécanisme d'effacement adapté et des contrôles utilisateurs dans un lot futur. F1-C interdit déjà l'ingestion de données identifiantes.
- `ExperienceMemory` conserve ses tables historiques `objects`, `experiences`, `sim_motion_trials` et `intent_preferences` sans modification de leurs API. Les entrées fictives F1-C ne modifient aucune préférence, récompense ou identité existante. **Il s'agit d'un journal de catégories, pas d'un entraînement de réseau.**
- La base SQLite de production devra rester privée, hors GitHub, et son emplacement sur le matériel doit attendre l'audit de ressources et de stockage réel. Les tests utilisent exclusivement un chemin temporaire.

## 3. Tests de validation

`tests/test_passive_memory.py` couvre sur **fixtures fictives** :

- catégorie identifiée et `unknown`, source `mock` conservée, son et objet distincts ;
- contradiction entre deux labels sur la même observation (journalisée `unknown` + `conflict`) ; incertitude sans promotion ni effacement d'un historique ancien ;
- seuil de confiance, TTL expiré, observation future et refus de messages `sensor`/source moteur ;
- échecs de lecture sans réutilisation de vieux événements, séquence répétée ou altérée, données non finies et mauvaise horloge ;
- colonnes SQLite sans image, track, transcription ni nom libre ; absence de modification des préférences et des objets existants ;
- purge à 14 jours, borne de 512 lignes et consultation de 100 entrées maximum ;
- **deux processus Python indépendants** rouvrant la même SQLite, avec **réinitialisation simulée du compteur monotone** et nouveau `session_id`. Le nombre de catégories vues passe de **1 à 2** sans interprétation d'identité.

Ce test de reprise est une validation **logicielle de persistance**, non une simulation de caméra ou de robot physique. La CI GitHub Actions est la source de vérité pour le décompte final des tests.

## 4. Suite

**F1-C ne réalise pas F1-D.** Le prochain lot devra composer F1-A + F1-B + F1-C dans une démonstration passive intégrée « découverte → rappel → inconnu ou contradiction → perte de la source → reprise », sans mouvement ni modèle ML. Après F1-D et vérification des critères de sortie F1 seulement, commencer F2-A (intentions cognitives passives). La locomotion P0/P1 reste suspendue.
