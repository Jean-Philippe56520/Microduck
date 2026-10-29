# E2E-1A — Ablation réelle du logiciel F2/MEM/F5-A, scènes entièrement fictives

**Porte 0 préenregistrée le 29 octobre 2026 avant modifications de code et avant résultats de la comparaison.** Base `main@14c64a8fdc50e7e8a475bceb71573239c37a86bf`. Autorité : `docs/plan-action.md`. **Ce n'est pas le jalon E2E-1 sur scènes physiques inédites.**

## Question concrète / manque prouvé

Les voies F2/DET-2/PER-1 (#176) et F5-A ont des tests isolés. **Écart de code :** `start_optional_pc_cycle()` appelle F2 sans permettre de lui transmettre les options d'objectif/détermination DET-2 ni l'engagement PER-1 ; une comparaison PC off/on peut ainsi changer par erreur le chemin de décision au lieu de seulement ajouter du conseil facultatif. Le banc C3-A préexistant compare des **étiquettes de prédiction déclarées**, sans exécuter mémoire, F2 ou PC ; ses gains ne prouvent rien sur la décision effective. MEM-2B-R #174 a prouvé **0/48** rappel correct d'instances sur images ABO réelles : E2E-1A ne peut pas supposer une continuité d'objet physique.

**Objectif mesurable de ce lot restreint :** faire réellement passer des **lectures fictives** dans le même F2 et le même F5-A, avec/sans entrée de la mémoire, détermination faible/forte, et avec/sans retour **émulé** du contrat PC ; vérifier que l'avis ne modifie pas la décision, que la mémoire peut l'infléchir uniquement dans les cas sourcés, et que stop/erreurs/absences ne créent ni faux effet, ni boucle ni commande. Les nouveaux cas construits dans la PR ne sont pas des captures inédites d'une caméra ; aucune annotation indépendante d'objet réel.

## Comparateurs et scénarios fixés

Combinaisons **2×2×2**, états indépendants mais entrées F1 de mêmes catégories/horloges : mémoire absente/présente (uniquement `ExperienceMemory` + `MockGoalMemory` réutilisés, pas un stockage supplémentaire), détermination `0`/`1`, PC off/on (le PC on signifie **uniquement un retour JSON fictif** conforme à F5-A, aucun vrai 9B, GPU, réseau, vision). Chaque lane repart d'une SQLite de fixtures isolée pour ne pas faire fuir le préchargement entre traitements ; jamais deux écrivains sur un même fichier.

1. **Deux catégories nouvellement présentes : `cat + toy`**. Avec objectif fictif actif cat sans tentative, mémoire on et détermination haute priorise `observe cat` ; sinon priorité F2 locale `observe toy`. Absence de mémoire ne peut favoriser arbitrairement cat. Le texte de l'avis PC n'ajoute pas d'instance et n'autorise rien.
2. **But `cat` déjà tenté**, seule la catégorie cat réapparaît dans une nouvelle lecture fictive ; mémoire off → F2 peut proposer `observe cat`, mémoire on+DET-2 → `idle` même si détermination haute. Ce cas est une détection de répétition cognitive, pas d'échec physique.
3. **Inconnu partiellement observé** : F2 propose `inspect unknown` ; PC off reçoit une absence d'avis, PC on reçoit des hypothèses **fictives non vérifiées**, notamment un faux `cat` très confiant. La décision, la SQLite et le statut d'identité doivent rester strictement identiques. Un JSON prétendant `person`, `motor_commands` ou faux `source` doit être rejeté.
4. **Observation non fiable/stale et repos simulé** : quels que soient les drapeaux, la seule issue cognitive est `idle` ou `rest` selon les règles F2 déjà codées ; jamais un appel PC, une identité, une récompense, un effet, ni une reprise d'action.

**Contrôle méthodologique :** mêmes lectures et horloges entre chaque combinaison, aucune paire avec deux données visuelles réellement nouvelles, aucun score d'identification. Mesurer plutôt le nombre de propositions `observe/inspect/idle/rest`, les différences d'intention, les faux crédits et les violations de garde de source. Ne pas valoriser `idle` systématique : il faut préserver l'attention sur un objectif non tenté et la réaction au contexte nouveau.

## Critères de passage / d'arrêt préfixés

- Les 8 combinaisons par scénario critique réalisent **exactement** les effets attendus des cas 1, 2, 3, 4 sur le **chemin F2 réel**, sans enrichissement à partir du texte PC. Comparer les **mêmes décisions** PC off/on et compter **0** décisions divergentes due au seul retour JSON fictif ; le nombre d'appels réels à Qwen doit être **0**.
- Pour cas 1 avec mémoire et détermination haute, 1 changement cible attendu vers cat ; pas de changement si mémoire absente ou détermination nulle. Pour cas 2, 0 répétition de la cible déjà tentée **lorsque garde DET-2 activé** ; le témoin sans mémoire doit conserver au moins une proposition sur la catégorie nouvellement vue.
- Cas inconnus avec avis faux/personne, hors délai, ou réponse contradictoire : zéro promotion en observation/identité/sens factuel. F5-A doit réutiliser **la décision F2 déjà effectuée**, sans deuxième cycle F2 ni second ordonnanceur.
- Budget et sûreté : aucun nouveau service, SQLite, table, moteur, speaker, replanification, Qwen, migration, image personnelle ; CI Python + N1 vertes, positif et négatif. Si la voie F5 manque la connexion ou le résultat ne se distingue pas du témoin, `insuffisant` ; n'ajouter aucune deuxième chaîne ad hoc.

## Revue réutiliser / adapter / créer et OEM

| Besoin | Décision | Preuve / risque |
| --- | --- | --- |
| F1-B, F2 (`AutonomyBrain.propose_balanced_passive`), DET-2/MEM-1/EX1 `ExperienceMemory` | **Réutiliser** | Chemin facultatif mock-only, pas d'intention d'action réalisée |
| F5-A `start_optional_pc_cycle`/ `finish_optional_pc_cycle` | **Adapter seulement la signature** | Propager `goals`, `guard_attempted_goals`, `personality_pacing` jusqu'au F2 existant ; F5-A ne ticke qu'une seule fois et aucun retour PC ne rentre dans F2 |
| C3-A `compare_mock_category_ablations` | **Ne pas dupliquer** | Ce banc mesure seulement des labels déclarés, pas F2/MEM/F5 ; objectifs différents |
| Nouvel orchestrateur/runtime/agent ou base | **Ne pas créer** | Un test d'intégration direct de F2/MEM/F5-A est suffisant ; zéro moteur/daemon |
| OEM épinglé `microduck@942e58e3` et RL `microduck_rl@b02fdea4` | **Lecture seule / inchangé** | `robotd` seul pilote à 50 Hz ; OEM main `a360b384` et RL main `bae39f59` diffèrent des pins ; #381/#414/#450 ouvertes, aucune n'est une fonctionnalité fusionnée |
| Registre C3 (QuackNav, microduck-brain, Quacksat, Twin, Smartulf) | **Référence seulement** | Pas de dépendance ni de code tiers requis |

## Portes de science restantes

E2E-1 **complet** nécessite des scénarios vraiment distincts **avec observation indépendante** et mesures de bénéfice sur des décisions utiles, plus une véritable comparaison PC/9B QW-1 en opt-in et sans données privées. Ici la branche PC ne reçoit que JSON artificiel ; `qwen_requests_real=0`. Cat-A2b manque toujours annotations indépendantes à hauteur 20–30 cm ; mémoire d'instance invalide sur ABO ; causalité robot toujours indéterminée. Aucun protocole de fiction ne peut débloquer `PHY-1` ou `AUT-1`.

## Résultats mesurés — intégration de logiciels réelle, scènes entièrement fictives

**Exécution :** [CI Python #40906041166](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40906041166), commit `c1091aa74346d22d313e29fdc89cd9da3a98f29c` : **1 791 tests, 6 ignorés, 0 échec**, dont les **six** nouveaux tests d'intégration E2E-1A. Les tests appellent réellement `start_optional_pc_cycle`, `AutonomyBrain.propose_balanced_passive`, F2/DET-1/DET-2, la même connexion `ExperienceMemory` et les contrats MEM-1/EX1/F5-A. Contrairement à C3-A, il ne s'agit pas de sorties de prédictions librement déclarées. Les **observations entrantes restent entièrement synthétiques**.

| Situation de fixture | Mémoire absente/présente × détermination 0/1 × réponse PC fictive off/on (8 lanes) | Observation contrôlée |
| --- | --- | --- |
| `cat` + `toy` observés simultanément | **2/8 `observe cat`** ; **6/8 `observe toy`** | Le changement de priorité n'existe qu'avec mémoire d'objectif actif et détermination forte ; retour PC n'influe jamais |
| But `cat` déjà lié à un EX1 antérieur | **4/4 `idle` avec mémoire**, **4/4 `observe cat` sans mémoire** | Le refus de re-proposer une attention déjà tentée est conditionné par MEM-1/DET-2 ; EX1 n'atteste pas un échec physique |
| Indice d'objet `unknown` partiel | **8/8 `inspect unknown`** | PC off : 4/4 `pc_unavailable` ; PC on : **4/4 JSON de conseil injectés localement**, statut `hypotheses_unverified` ; aucune identité promue |
| Lecture périmée (source non fraîche) | **8/8 `idle`** | Aucune requête de PC même si le drapeau on est activé |
| Énergie motivationnelle simulée basse | **8/8 `rest`** | Le repos F2 l'emporte sans supposer de batterie mesurée |

**Total : 40 exécutions de voies F2/F5-A sur 5 jeux de labels scriptés × 8 configurations**, plus tests négatifs de JSON prétendant `person`, ajoutant `motor_commands`, falsifiant la source ou l'identifiant de requête, réponse hors délai, connexion `ExperienceMemory` étrangère, lecture sous provenance `sensor` incompatible mock et mauvais booléen. Tous sont refusés sans action ni souvenir. Au moins le test du cas `cat+toy` constate **un seul cycle F2 par lane**, même avec F5 activé.

**Abstentions / effet indépendant :** aucune classification visuelle ni reconnaissance de chat, jouet ou personne n'a été exécutée ; il n'y a pas de capteur ni de mesure de pertinence dans une scène physique. Les objectifs et liens EX1 sont **pré-inscrits volontairement dans chaque lane de fixture** ; le contrôle `total_changes` constate **zéro nouvelle écriture pendant la consultation/décision**. Le retour PC déclaré « on » est **un JSON fabriqué dans le test**, non Ollama/Qwen. Il ne doit jamais être interprété comme une consultation sémantique réussie.

**Décision : `test_logiciel_seul` pour l'intégration des contrats ; `E2E-1 complet = bloque_source_externe`.** L'écart minimal F5-A/DET-2 est corrigé sans nouvelle boucle ni modification par défaut des anciens appels F5-A. **Aucun gain d'autonomie interscènes ni avantage du vrai Qwen3.5 9B n'est mesuré.** Le prochain essai utile sur le vrai E2E nécessite un nouveau corpus de scènes à faible hauteur **indépendamment annotées et autorisées** et un vrai 9B sur le PC, comparés en aveugle et enregistrés dès les premiers essais. Sans ces éléments, **STOP** : ne pas ajouter d'autres scénarios fictifs comme preuves d'une généralisation.

**Risques résiduels et retour arrière :** MEM-2B ne reconnaît pas les instances sur les photos ABO (#174 : 0/48), Cat-A2b sans vérité terrain externe et DET-2 ne garantit pas le quota de reprises après redémarrage (#176). Laisser le moteur OEM intact et les options DET-2/PER-1 désactivées par défaut ; si F5-A cause une régression, supprimer les 3 paramètres facultatifs (anciens appels restent inchangés). Aucun nouveau schéma/modèle/services, aucun média privé ni consommation RK3566/thermique/50 Hz mesurée.
