# F5-D — Résistance aux réponses PC malveillantes et aux pannes

**26 octobre 2026 — [PR #44](https://github.com/Jean-Philippe56520/Microduck/pull/44) fusionnée après revue ; code et tests logiciels, aucun modèle Ollama exécuté.** F5-A, F5-B et F5-C sont sur `main` avant cette PR. Les exemples sont des catégories fictives anonymes ; aucune personne, voix, image, identité, moteur ou caméra réel n'est utilisé.

## Menaces vérifiées dans les fixtures

Les tests `tests/test_f5d_adversarial.py` fabriquent directement des réponses JSON prétendument produites par un PC, un serveur HTTP hostile limité à **127.0.0.1** et un worker facultatif compromis. Ils couvrent :

- Fausse autorité du PC : `motor_command`, `speaker`, `safe_floor`, `identity_verified`, promesse de reconnaître un chien ou une personne, confiance prétendue sans preuve, type `floor_safe` ⇒ **aucune action, aucune reconnaissance et refus de la réponse**.
- Rejeu d'identifiant aléatoire, identifiant de requête contradictoire, usurpation du champ de source, doublons de clés JSON, sortie non JSON, texte injonctif, réponses incomplètes ou UTF-8 invalide ⇒ **annotation `response_rejected`**, avec la même intention locale.
- Corps HTTP transmis **octet par octet**, réponse `Transfer-Encoding: chunked` ou sans `Content-Length` ⇒ rejet ou `pc_unavailable`, sans attendre indéfiniment la fin du corps.
- Retour d'un worker fabriquant une `OptionalPCAdvisory` avec catégorie `dog`, confiance artificiellement forte, horodatages hors de l'échéance, ou `PCRequest` dupliquée à contenu identique mais sans provenance d'objet ⇒ rejet **à la jonction F5-C**, même si le modèle ou un composant amont est fautif.
- Arrêt de l'exécuteur avant la soumission HTTP ⇒ **aucune consultation fantôme**, aucune tâche en attente ni commande moteur.

Le test initial, avant correctifs, a démontré **six échecs attendus** (dépassement par flux lent, absence de longueur, chunked, réponses de worker forgées et copies de requête). Après correctifs ciblés, l'ensemble des tests peut être vérifié par la CI. Une réussite de tests sur fixtures **ne prouve pas une sécurité face à tous les attaquants**.

## Correctifs ciblés

**`ollama_local_client.py` :** le corps HTTP d'une réponse non streaming est désormais limité par une **échéance monotone totale** : un client ne peut plus redémarrer le budget à chaque octet reçu. Une taille `Content-Length` numérique, unique et bornée (1 à 16 384 octets) est exigée. Les réponses chunked/compressées, trop longues, absentes ou tronquées sont refusées, et la ressource de réponse est fermée. La sortie modèle reste limitée à 4 096 octets et passe **encore** le contrat strict F5-A/B. La voie réseau n'est jamais appelée depuis `robotd`.

**`selective_pc_policy.py` :** le résultat d'un worker doit se rapporter aux **objets de requête et d'intention originaux**, et toute annotation de type `hypotheses_unverified` reste bornée aux seules catégories `unknown` de confiance déclarée 0, avec un temps de réception/expiration localement cohérent. Même un retour de worker forgé ne peut fournir la catégorie `dog` ou un fait/sécurité à F5-C. L'échec est compté comme `response_rejected` sans mettre à jour la mémoire des observations.

**`OptionalOllamaWorker` :** l'échec de `ThreadPoolExecutor.submit` sur exécuteur fermé n'abandonne plus un faux cycle `pending`. Il renvoie un refus local. La boucle cognitive continue, et la politique F5-C conserve quotas, temps d'attente et circuit de panne.

**Démonstration `f5d_adversarial_demo.py` :** quatre faux avis dangereux et un PC absent, uniquement en mémoire. Le programme exige que la décision locale `inspect` reste inchangée, que les ordres soient rejetés, qu'aucune expérience ne soit écrite et que les commandes moteur/haut-parleur restent à zéro.

## Limites de sécurité non résolues

- **Authentification réelle absente.** Le champ `source=pc_qwen_unverified` et l'identifiant de requête sont des assertions dans le JSON, **pas une signature, un certificat TLS ou une identité cryptographique du serveur**. Un faux service loopback, un PC ou un lien LAN intercepté peut encore fournir des réponses fausses **mais non vérifiées**. Préférer un tunnel SSH authentifié testé et une configuration protégée, non présents dans cette PR.
- Le délai monotone couvre **le corps HTTP** une fois les en-têtes reçus. `http.client` peut toujours être retenu par un pair malveillant qui transmet les **en-têtes** très lentement ; l'isolation hors boucle motrice et le refus tardif par le worker limitent l'impact sur la cognition, mais ne sont **pas une garantie d'interruption d'un socket ou de terminaison du processus**. Avant déploiement, un processus externe isolé ou une couche de transport à échéance stricte serait à évaluer.
- L'exigence de `Content-Length` refuse volontairement les réponses `chunked` : sa compatibilité effective avec des versions réelles d'Ollama reste **à vérifier sur le PC**, car F5-D n'installe ni ne contacte Ollama.
- Aucun Qwen 4B/9B testé sur le PC utilisateur : qualité, latence réelle, RSS, puissance et accélération restent inconnues. Aucun modèle n'est chargé sur RK3566 ; caméra, ToF, sécurité des escaliers et navigation libre sont **non validés**.
- Les tests sur une machine GitHub Actions n'établissent aucune preuve de latence déterministe de SQLite, d'autonomie énergétique, de refroidissement, d'authentification d'un service OEM ou de sécurité physique. Le contrôle moteur et ses protections restent du ressort du constructeur.

## Tests reproductibles

```bash
python -m unittest discover -s tests -v
python -m microduck_companion.f5d_adversarial_demo
```

**Validation logicielle :** [808 tests Python, compilation et démonstration F5-D fictive réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40253911518), après revue puis [fusion de PR #44](https://github.com/Jean-Philippe56520/Microduck/pull/44). La validation Ollama/Qwen et robot physique reste ouverte. Aucune instruction de mouvement n'est exécutée.

**Étape suivante : F6-A**, préparation des interfaces embarquées et inventaire des services OEM, **sans portage ni déploiement réel**. La comparaison des modèles 4B puis 9B sur le PC constitue un essai distinct qui reste nécessaire avant de prétendre valider l'assistance du PC.
