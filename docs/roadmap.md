# Feuille de route - Microduck Companion

## Objectif

Robot discret, curieux, explorateur et social. Ses motivations et ses
préférences évoluent selon les expériences qu'il a réellement faites.
L'IA conversationnelle n'est pas l'objectif principal.

## V0 - Prototype sur PC (en cours)

- Moteur local d'intentions : curiosité, sociabilité, jeu, énergie et prudence.
- Mémoire SQLite : objets, épisodes et préférences.
- Distinction explicite entre hypothèses du modèle et observations vérifiées.
- Demande d'analyse au PC pour un objet inconnu seulement si le PC est disponible.
- Tests automatiques des barrières de sécurité.
- Observations *fictives* : aucune caméra connectée, aucune commande motrice.

## V1 - Simulateur officiel

- Utiliser les sous-modules `upstream/microduck` et `upstream/microduck_rl`.
- Brancher les observations simulées sur le moteur de décisions.
- Développer un adaptateur JSON-RPC vers les intentions *autorisées* de robotd.
- Mesurer les collisions, le temps de réaction et la fréquence des décisions.
- Ne jamais autoriser un LLM à commander directement des servomoteurs.

## V2 - Qwen local sur PC (facultatif)

- Comparer un modèle multimodal 4B puis 9B en fonction de la vitesse réelle.
- Ajouter un serveur local simple, avec timeouts et limites de fréquence.
- Hypothèses vérifiables; pas d'action physique issue d'une seule hallucination.
- Ne pas stocker automatiquement les images ou conversations personnelles.

## V3 - Matériel réel

- Examiner la consommation RAM/CPU du robot.
- Valider les capteurs et vérifier les sécurités embarquées.
- Tests physiques graduels dans une zone sans chute.
- Consolider une mémoire sur le Microduck et une synchronisation optionnelle.

### Installation des sous-modules

```bash
git submodule update --init --recursive
```

### Limitations

Ce dépôt est un prototype de recherche. La sécurité matérielle reste
sous l'autorité du contrôleur officiel Pollen Robotics.
