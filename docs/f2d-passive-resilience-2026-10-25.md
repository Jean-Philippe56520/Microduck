# F2-D — Reprise après interruption, quotas et mesures hôte

**25 octobre 2026 — [PR #31](https://github.com/Jean-Philippe56520/Microduck/pull/31), branche en revue.** Aucun Microduck physique, capteur réel, pilote moteur ou modèle IA n'intervient dans les expériences. La [CI Python F2-D](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240749032) a réussi : **450 tests Python** (425 préexistants + **25 nouveaux F2-D**) ainsi que la compilation et les démonstrations.

## 1. Architecture et périmètre

Le superviseur `PassiveCycleSupervisor` ne crée **aucun nouveau cerveau** : il utilise `FixtureUnixReader` (F1-B), le même `AutonomyBrain.propose_balanced_passive()` (F2-B), `PassiveObservationJournal` (F1-C), `PassiveLearning` (F2-C) et **une SQLite existante**. Il n'appelle ni `robotd`, ni `mediad`, ni `tofd`, ni réseau/PC/Qwen, et n'exécute aucune intention.

Chaîne :

1. Refuser toute exécution au-delà des quotas de session ou si SQLite est indisponible.
2. Recevoir **une lecture fictive** Unix via l'adaptateur F1-B, en mesurant sa durée sur l'hôte.
3. Sur source absente, retardée ou falsifiée : produire uniquement un rapport `idle`, sans relire un ancien souvenir comme une perception actuelle.
4. Sur lecture admissible : demander **une proposition non exécutée** à F2-B/F2-C. Les refus de F2-B (horloge, source, séquence, fraîcheur, intervalle minimal) empêchent la journalisation.
5. En cas de cycle toujours admissible : journaliser la catégorie fictive via F1-C, puis qualifier la nouveauté/répétition via F2-C.
6. Rapporter source, stockage, propositions, durées, CPU et mémoire du **processus hôte**. Un dépassement constaté après SQLite n'annule pas l'écriture déjà achevée.

**Le superviseur ne peut pas garantir une transaction atomique** entre `journal.append` et `learning.record` : une interruption entre ces deux appels peut laisser une observation historique non évaluée. Elle n'est jamais récompensée ni rejouée automatiquement comme une mesure fraîche. L'état des cooldowns F2-B reste en RAM et repart à zéro entre processus ; les préférences de catégories F2-C sont relues depuis SQLite.

## 2. Budgets codés

| Limite | Valeur par défaut | Effet |
| --- | ---: | --- |
| Tentatives de cycles par superviseur | 16 (1–512 configurable) | Au-delà : `quota_cycles`, sans lecture socket |
| Événements reçus sur la session | 128 (1–8192 configurable) | Au-delà : `quota_events`, sans cognition ni sauvegarde supplémentaires |
| Durée acquisition de fixture | 1 000 ms (max 3 000 ms) | Dépassement : `late_source`, **avant** décision/mémoire |
| Durée complète du cycle | 1 500 ms (max 5 000 ms) | Après décision : `late_before_commit` sans écriture ; après écriture : `late_after_commit` signalé mais commit non annulé |
| Fenêtre de mesures | 64 cycles | Historique RAM borné, compteurs d'événements conservés pour cette instance |

Ces valeurs sont des **limites de démonstration sur processus Python**, non un temps de réponse garanti par un ordonnanceur temps réel, ni des allocations matérielles validées. Le lecteur F1-B conserve ses propres limites strictes (trame 8192 octets, au plus 64 événements, TTL/fraîcheur et socket Unix local).

## 3. Expérience mesurée en CI

[Exécution GitHub Actions #40240749032](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240749032) : Ubuntu Linux hébergé, Python **3.11.17**, deux **processus distincts**, chaque processus lance un faux serveur socket Unix et partage uniquement le fichier SQLite. Les origines monotones et dates des observations sont **synthétiques** ; les durées de cycle, temps CPU et `ru_maxrss` proviennent **du vrai processus Linux du runner**.

| Mesure | Premier processus | Deuxième processus |
| --- | ---: | ---: |
| Cycles proposés | 6 | 4 |
| Cycles F1-C journalisés | 5 | 3 |
| Conséquences de catégories fictives F2-C | 5 | 3 |
| Déconnexions socket fictives | 1 | 1 |
| Latence totale p50 (horloge réelle hôte) | **2,521846 ms** | **2,851877 ms** |
| Latence totale p95, rang le plus proche | **4,096983 ms** | **5,638041 ms** |
| Temps CPU moyen du processus par cycle | **1,572542 ms** | **2,088481 ms** |
| Pic RSS *du processus* (maximum historique Linux) | **18 424 Kio** | **18 348 Kio** |
| Commandes motrices, exécutions | **0, 0** | **0, 0** |

Les deux exécutions ont conservé et relu la préférence F2-C : `observe` passe de **+0,035** à **+0,050** après nouvelle répétition et catégorie; `listen` de **+0,020** à **+0,040**. Ce sont des **biais cognitifs fictifs**, pas des résultats d'actions. Le p95 sur seulement 6 ou 4 cycles correspond au maximum (rang le plus proche) ; **il n'est pas une estimation statistique robuste**. Le CPU couvre le processus et ses threads, dont le faux serveur, et `ru_maxrss` est un pic historique de processus, **pas la consommation propre d'un module**.

Aucune fréquence de capteur réel, charge robotd, batterie, chaleur, RAM libre embarquée ou NPU n'a été mesurée. Il serait incorrect d'extrapoler ces chiffres au RK3566.

Reproduction avec deux commandes distinctes dans un checkout Python 3.10+ sur système Unix :

```bash
python -m unittest discover -s tests -p test_passive_resilience.py -v
python -m unittest discover -s tests -v
python -m microduck_companion.passive_resilience_demo --database /tmp/microduck-f2d.sqlite3 --session first
python -m microduck_companion.passive_resilience_demo --database /tmp/microduck-f2d.sqlite3 --session second
```

## 4. Scénarios de robustesse effectivement testés

- Source absente, exception lecteur, type/canal/source erroné, contradiction, confiance faible, événement passé/futur, séquence répétée : aucune perception dangereuse produite, aucune commande.
- Quotas de cycles et d'événements : refus **avant** de traiter davantage ; aucune promotion d'anciens événements.
- Dépassements temporels instrumentés avec horloge de test contrôlée : source trop lente, décision lente avant écriture, écriture terminée mais cycle tardif (commit honnêtement conservé). Ce sont **des contrôles post-hoc**, non des interruptions de calcul.
- SQLite fermée, incohérence de bases et échec du journal des apprentissages après sauvegarde F1-C : rapport `idle`, sans prétendre qu'un résultat F2-C a été commis.
- Deux processus Linux distincts en CI : fermeture/reprise de SQLite, horloge monotone réinitialisée, souvenirs de catégorie disponibles sans réutilisation comme événements vivants.
- Mesures p50/p95, temps CPU, RSS Linux et fenêtre mémoire métrique bornée. Le décompte de cooldown et des répétitions reprend directement F2-B.

## 5. Statut et suite

**Codé et testé en logiciel :** reprise, isolement des pannes, quotas et diagnostics hôte. **Non testé :** système constructeur, caméra, microphone, capteur ToF, NPU, robot physique, limites temps réel, consommation énergétique, mobilité et reconnaissance individuelle. Le chantier locomoteur reste suspendu.

Le lot F2-D clôt **la phase F2 logicielle sur fixtures fictives uniquement**, sous réserve de revue et de fusion de la PR #31. La suite indépendante sera **F3-A**, constitution et protocole d'évaluation de catégories, avec séparation données annotées/évaluation et respect de la confidentialité. Aucune exploration mobile ou identification d'individu n'est revendiquée.
