# QW-1A — Conseil d'objectif et rappel MEM-2A vers le vrai Qwen3.5 9B PC

**Porte 0, préenregistrée avant code et sorties modèle : 29 octobre 2026.** Base `main@6d6764dc080f308692524b26a103f50c0dfb1b1f`. Priorité du [plan directeur](plan-action.md) : QW-1, non QW-QUAL-2A historique. Aucun robot présent ; Qwen sur PC Ryzen/Ollama **facultatif, non déployé**.

## Objectif concret et manque prouvé

Aujourd'hui F5-B/Ollama refuse de deviner le sens d'une image absente et force `unknown` ; F5-A/G a relié F2, DET-2, MEM-1 et F5-A, mais **ne transmet pas une question d'objectif avec un rappel au vrai 9B**. Le rôle PC v2 exige une image et reste gelé après les quatre anciens cas QW-QUAL-1F ; QW-PERF-1 envoie un simple contexte fictif dans un test de couleurs, **pas les vrais lecteurs MEM-1/MEM-2A de la SQLite**. Il manque donc un **seul essai réel A/B** qui constate si une proposition de stratégie évite une répétition après consultation du rappel, sans fabriquer d'image, d'identité ou d'effet.

**Question préfixée :** Kwipi a un objectif de **catégorie fictive** `ball` dont l'observation à distance a déjà été **proposée** (EX1), pas prouvée exécutée. Sans rappel (A), le même objectif abstrait est fourni. Avec rappel (B), seule la stratégie `observe_from_distance` provenant de MEM-1/EX1 et la provenance `mock_fixture_only` sont ajoutées. Que propose le **même Qwen3.5 9B réel** comme observation nouvelle **sans contact**, ou choisit-il l'abstention ? Aucun capteur/objet/sol réel fourni ; catégorie et contexte restent des **déclarations de fixture**.

## Décisions de réemploi

| Entrée | Réutiliser / adapter / créer | Raison et frontière |
| --- | --- | --- |
| `ExperienceMemory` unique, `MockExperienceLedger`, `MockGoalMemory` et MEM-2A `recall_memory` | **Réutiliser en lecture seule pendant la consultation** | Conserver les corrections, statut fictif et absence de clé d'identité ; transmettre **seulement** des enums `goal_kind/category/state/need/previous_strategies` et provenance, jamais sqlite brut, SQL, noms, horodatages, UUID, images |
| `OllamaEndpoint` F5-B, `_strict_json`, `_envelope_diagnostic` du pilote PC existant | **Adapter un unique appel PC opt-in**, pas de nouveau daemon | Local loopback `127.0.0.1` obligatoire ; modèle `qwen3.5:9b`, une requête, réponse JSON stricte, timeout/budget, aucune installation ni retour robot |
| Rôle v2 visuel gelé et `screen_preview_text` | **Ne pas modifier**, conserver comme témoin distinct | Un conseil de sens textuel n'est pas une interprétation indépendante d'image, et un garde lexical ne suffit pas pour valider une stratégie |
| F5-C/F2/DET-2/PD3 | **Ne pas reconfigurer** | Le test PC **manuel** ne réserve aucune capacité F5-C, ne décide pas d'envoyer la requête en production et ne peut pas influer sur F2 |
| OEM `microduck@942e58e3` `robotd` seul à 50 Hz, RL `b02fdea4` | **Inchangés** | Amonts OEM main `a360b384`, RL main `bae39f59` différents, OEM PR #381/#414/#450 ouvertes et non livrées |
| QuackNav, microduck-brain, Twin, Quacksat et autres tiers du registre C3 | **Références seulement** | Aucun gain vérifié à ajouter un runtime/LLM tiers ici |

## Essai A/B et porte de sortie (définis AVANT les sorties du vrai 9B)

- **PC opérateur, opt-in explicite et local :** exactement deux requêtes séquentielles (sans rappel et avec rappel), même objectif et besoin `find_strategy`, `think=false`, température 0, structure JSON contrainte, timeout **120 s chacune**, aucun retry automatique ; la deuxième requête ne part pas si la première n'est pas sûre/protocolairement valide. Le contexte ne contient que des catégories publiques et une proposition EX1 *fictionnelle*, jamais un événement moteur ou une photo.
- **Mesures à extraire** : statut/régime Ollama `stop`, statut JSON, stratégie proposée, rappel évité ou pas (dans B), abstention, durée murale, tokens et métriques serveur si présents, `motor_commands=0`, `memory_writes=0` **par construction**. Les raisonnements textuels restent **humain-seulement** et ne sont jamais interprétés en ordre, effet, identité ou souvenir ; affichage facultatif explicite sur la console locale, pas de fichier.
- **Passage technique QW-1A** : les deux vrais appels terminent (ni `length`, timeout, HTTP invalide ni JSON malformé), le client lie `request_id`, refuse champs inconnus/commande moteur ; la proposition avec mémoire **n'est pas la stratégie déjà proposée** `observe_from_distance` (une nouvelle observation passive ou `abstain` admise) ; aucune fausse revendication de vérification. Sinon statut `insuffisant` et STOP, sans augmenter aveuglément les tokens ni créer d'autres bancs.
- **Passage qualitatif QW-1 complet :** exige en plus au moins quelques **nouveaux scénarios autorisés** et une **revue indépendante** jugeant pertinence, valeurs sémantiques, erreurs de prudence, inaction, amélioration mémoire, latence/RSS du vrai 9B. **Les deux réponses d'une fixture ne suffisent jamais** à affirmer un bénéfice sémantique autonome. Un gain de structure n'est ni causalité ni reconnaissance.
- **Négatifs sur code en CI sans Qwen** : objectif expiré, rétracté, but étranger à l'instance SQLite, faux lien EX1, tentative à `mock_executed` jamais présentée comme action vraie, corruption, entrée libre/SQL, session/ID privé, demande non autorisée, réponse avec commande/action, champ excédentaire, doublons JSON, retard, erreur réseau, modèle différent ou troncature, plan de fuite de texte. Absence de réseau par défaut, pas de second écrivain, pas de PC inaccessible imposé.

## Retour arrière et statut matériel

Tout chemin nouvellement créé **opt-in PC seulement** et déconnecté de F2 et robotd ; aucune création de schéma, aucune modification OEM, aucune image. Si 9B indisponible, le choix F2 local reste intact. Ne pas fusionner sans CI Python et N1 vertes ; **CI verte prouve le contrat PC fixturé, pas que les deux vraies requêtes ont été exécutées sur la machine utilisateur**. L'adaptateur peut être fusionné comme outil facultatif seulement en statut `test_logiciel_seul` tant que les sorties PC véritables ne sont pas reçues.

## Résultats

**Prévu, non mesuré au moment de l'enregistrement de cette porte.** Aucun chiffre réel Qwen n'est inféré des anciens cas QW-QUAL ni des tests de GitHub.
