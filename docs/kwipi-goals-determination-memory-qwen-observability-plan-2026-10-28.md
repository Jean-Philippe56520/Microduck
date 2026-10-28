# Kwipi — feuille de route des objectifs, de la détermination, du rappel Qwen et de l'observabilité

**QW-GOAL-0 — 28/10/2026, correction du rôle de Qwen, DOCUMENTATION SEULE :** [objectif motivé → question utile → conseil 9B PC facultatif](qw-goal0-motivation-driven-qwen-policy-2026-10-28.md). Le besoin d'information, l'objectif inachevé, la détermination, la curiosité, le jeu, la sociabilité, la prudence et l'exploration peuvent rendre une consultation utile ; **ne pas instaurer une rareté arbitraire**. Une question véritablement différente peut justifier une reconsultation sans nouvelle image. Les quotas actuels F5-C restent dans le code tant que QW-2 ne les a pas adaptés et mesurés ; protections techniques et OEM inchangées.


**MEM-2A — premier sous-lot (28/10/2026, [PR #147](https://github.com/Jean-Philippe56520/Microduck/pull/147) fusionnée (`67d6db4b`), [CI Python #40780346663](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40780346663) et [N1/N5/N6 #40780346693](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40780346693) réussies) :** [lecture seule bornée C1/C2 + MEM-1](mem2a-readonly-context-recall-2026-10-28.md) avec compteur F0 séparé des catégories fictives et sans identité d'instance prouvée. L'étape complète MEM-2 (continuité multi-vues indépendante), DET-2 et QW-1/QW-2 restent à développer. Aucune seconde SQLite, Qwen ni commande moteur.


**Date :** 28 octobre 2026. **Statut :** plan d'intégration, DOCUMENTATION UNIQUEMENT ; aucune fonction autonome nouvelle, moteur, consultation PC ou migration SQLite livrée par ce document.
**Autorité :** [plan directeur](plan-action.md). Cette feuille ajoute des jalons aux chantiers F2/F4/F5/PD/EX/N3/N4 ; elle ne remplace ni leurs critères de preuve ni la priorité Cat-A2b/C3-B, B/C et l'audit robot.
**Référence auditée :** Companion `cdce37c52260b9036f212656dadae0f8013bbc08`, OEM `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, RL `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Vérifier à nouveau ces révisions avant le moindre code ou essai.
**Évolutions OEM non livrées :** [cerveau #381](https://github.com/pollen-robotics/microduck/pull/381) et [cartographie #414](https://github.com/pollen-robotics/microduck/pull/414) ouvertes à l'audit ; elles ne sont ni le cerveau actif ni une sûreté anti-escalier.

## 1. Observation, hypothèses, preuve recherchée, échec, risque et retour arrière

**Observations :**
- `AutonomyBrain` F2 possède cinq motivations (curiosité, sociabilité, jeu, énergie *simulée*, prudence) ; `passive_rhythm` propose seulement des intentions passives sur fixtures. `behavior_personality` et PD2 décrivent des états *après* la décision, sans ordonnancement moteur. Pas de détermination persistante/objectif durable et validé sur robot.
- `ExperienceMemory` est l'unique SQLite commune ; N3 recense 22 tables dans 121 modules au moment de son audit, avec un site d'ouverture écrivable, et les lecteurs RO existants. `experience_ledger`/`experience_effects`/`experience_expectations` sont mock-only. N4 ne mesure que des fixtures hôte ; les quotas 14 j/256 ne sont pas dimensionnés sur RK3566.
- F5 v2 Qwen3.5 9B multimodal fonctionne comme pilote **manuel PC**, image autorisée, sorties non vérifiées, sans accès à la SQLite ; F5 v3 filtre des propositions **fictives**, sans autorité sur la perception ou le moteur. Qwen #97–99 sont fusionnées ; les tests existants ne prouvent pas une boucle robot autonome.
- OEM `robotctl monitor --json` lit des états `robot.state` décimés, `robotctl logs` lit journald, `robotctl health` et `policy list` décrivent l'état technique. `robot.do accepted` est une mise en file, **pas** un reçu de début/fin d'exécution ; les états moteurs ne sont pas des preuves indépendantes de l'effet. Le journal OEM `/var/log` sur zram n'est pas durable lors d'une coupure électrique.

**Hypothèses de conception à tester :** (H1) un journal de décision rend F2 explicable sans nouvelle boucle ; (H2) une persistance d'objectifs change les décisions sans répétition compulsive ; (H3) les souvenirs filtrés améliorent l'utilité des conseils du 9B ; (H4) l'humeur/engagement apportent de la continuité sans compter deux fois les mêmes motivations.

**Preuves recherchées :** reconstitution d'un épisode ; A/B mêmes scènes avec/sans mémoire, détermination et PC ; reprises après redémarrage ; corrections non ressuscitées ; zéro faux crédit moteur/causal ; stockage, temps et charge mesurés sur hôte avant toute validation robot.

**Échecs bloquants :** deuxième écrivain ou base, permission motrice implicite, « accepted = executed », réessai sans information nouvelle, humeur instable, données privées transmises automatiquement, latence bloquant `robotd`, fausse revendication de perception/locomotion ou taux de réussite sans contre-annotation.

**Risque et retour arrière :** commencer en lecture seule et fixtures, fonctions optionnelles désactivées par défaut, PR petites et réversibles ; en cas de dérive, retirer l'adaptateur et revenir aux décisions F2 actuelles sans toucher aux sous-modules, poids, unités OEM ni souvenirs corrigés.

## 2. Invariants d'architecture

**Une seule boucle décisionnelle** : perception sourcée → rappel mémoire → motivations/état/objectif/risque → Qwen facultatif si besoin réel et consentement → proposition de F2 ou inaction → autorisation **exclusivement OEM robotd** pour tout mouvement → attestation indépendante action/effet lorsqu'elle existe → correction prudente → mémoire/journal.

- **Local sans PC :** observation, rappel, repos, objectifs passifs et arbitrage essentiels doivent continuer sans Ollama ni réseau. Qwen3.5 9B reste sur PC Ryzen, jamais requis sur RK3566.
- **OEM propriétaire unique :** `robotd` conserve la sécurité, la boucle à 50 Hz, les skills effectivement chargés, le deadman et le stop. Aucun geste non supporté, contrôleur concurrent, contournement ou navigation libre présumée ; ToF frontal 8×8 ≠ cartographie complète ni preuve de sol.
- **Mémoire unique :** `ExperienceMemory`, même connexion mono-écrivain pour les nouveaux enregistrements si nécessaires, réutilisation des tables existantes d'abord. Lecteur SQLite `mode=ro`/`query_only` existant : pas de SQL libre donné à Qwen, ni copie de SQLite entière ou de journal moteur brut sur le PC.
- **Séparation des niveaux :** `hypothesis_unverified`, `intention_proposed`, `oem_accepted`, `execution_attested`, `effect_observed`, `causal_evidence`, `indeterminate` et `retracted` ne sont jamais équivalents. Les trois derniers nécessitent des preuves adaptées.
- **Vie privée :** médias éphémères, aucun flux permanent ni identité/biométrie, souvenirs expurgés et minimisés, consentement explicite et quotas/auth/chiffrement pour échanges PC ; export diagnostique local, volontaire et borné.
- **Ressources :** budget RAM/CPU/SQLite/WAL/journaux à mesurer sur robot ; ne pas modifier les réglages OEM journald/zram et ne pas produire un journal de chaque tick dans la mémoire cognitive.

## 3. Réutiliser / adapter / créer

| Besoin | Réutiliser | Adapter / à créer avec justification |
| --- | --- | --- |
| Choix de l'intention | `autonomy.py`, `passive_rhythm.py`, F2 | Adapter **le même F2** ; jamais un second arbitre |
| Humeur/continuité | `behavior_personality.py`, `behavior_continuity.py`, F2 | Adapter les états descriptifs, puis l'engagement pré-décision ; ne pas faire d'une humeur un moteur |
| Souvenirs/stratégies | `episodic_memory.py`, F4/C1/C2, EX1–EX4, N3/N4 | Adapter rappel et éventuel contrat d'objectif ; migration seulement si prouvée indispensable |
| Qwen facultatif | F5-A/B/C/D, F5 v2 et v3, PD3 | Adapter l'entrée **filtrée et autorisée** de souvenirs et la validation des sorties ; aucun SQL libre |
| Journal consultable | `kwipi_journal.py` RO, `robotctl monitor`/`logs`/`health`/`policy list`, EX4 | Créer le **seul contrat manquant** de corrélation diagnostique, non un démon de télémétrie concurrent |
| Navigation/manipulation | `robotd` et catalogue OEM réellement chargé | Auditer les primitives et preuves avant chaque capacité ; ne pas créer une compétence « transport de chaussette » imaginaire |

Comparaisons tierces : registre C3 (`QuackNav/microduck-brain`, Quacksat, Twin, GC/Smartulf, quack-control, lab/studio), uniquement pour les composants pertinents ; licences et ressource à contrôler, aucune intégration implicite.

## 4. Sémantique : détermination, objectifs et réessais

**Trait de détermination** relativement stable (candidat F2), distinct de curiosité (chercher des nouveautés), jeu (valeur contextuelle), prudence (risque), énergie (disposition cognitive *non égale à batterie*) et humeur (état descriptif transitoire). La détermination agit sur la conservation/reprise d'un objectif, **jamais** sur la possibilité de franchir une barrière de sûreté.

**Objectif local :** `candidate` / `active` / `suspended` / `completed_verified` / `abandoned` ; avec catégorie pouvant être `unknown`, stratégie, incertitude, contexte, coût estimé, conditions de reprise, provenance, dernière décision et historique de tentatives. `completed_verified` ne peut jamais venir d'un récit Qwen ou d'un simple `robot.do accepted`.

**Une nouvelle tentative exige à la fois** (1) contexte sûr et compétence admissible, (2) budget/temps/ressource suffisants, (3) hypothèse falsifiable ou information/stratégie réellement nouvelle. Sinon suspendre, observer ou abandonner, **même si détermination forte**. Le nombre d'essais autorisés n'est pas une « intensité d'humeur » ; les seuils se règlent après tests négatifs et mesures.

**Échec utile** = objectif encore pertinent mais stratégie inadéquate ou observation manquante. Un refus OEM et un résultat indéterminé ne sont pas « échecs physiques ». Un nouvel environnement peut légitimer la réévaluation des anciennes hypothèses, sans résurrection automatique d'une rétraction.

**Exemple exclusivement hypothétique :** « chaussette → prise au bec → transport → panier ». Qwen peut suggérer textile souple et contenant comme concepts à examiner ; `ground_pick` ne prouve ni prise d'une chaussette, ni maintien, ni déplacement, ni dépôt. Ces quatre preuves physiques sont séparées et la locomotion SIM-E2 #101 reste non résolue.

## 5. Contrat cible de journal et corrélation

En OBS-1, un **lecteur dérivé** non intrusif doit produire un enregistrement par événement diagnostique, avec :
- `schema_version`, `episode_id`, `attempt_id` optionnel, `sequence`, `source`, `evidence_level`, `event_type`, `timestamp_wall`, `session_monotonic_ns`/référence boot si réellement disponibles ; conserver `unknown` si une provenance manque.
- `scene_category` générique/`unknown`, `objective_state`, `motivation_profile`/humeur descriptive si sourcée, `memory_refs` corrigibles, `qwen_status`, `decision`, `reason_code`, `alternative_reason_codes` et `risk_gate` ; valeurs fermées, pas de texte privé.
- `oem_request_id` et `accepted/refused` si vérifiés, `execution_status` **indeterminate par défaut**, `effect_status` **indeterminate par défaut**, `causality_status` **unproven par défaut** ; jamais inventer une corrélation entre `robot.state` et un geste.
- `clock_source`, version OEM/API/modèle/policy lorsque attestés, événements manquants/lacunes, invalidation, rétraction et références de preuves.

Le **journal de décision** durable, dimensionné et sélectif reste dans l'unique SQLite si la persistance est justifiée ; la **télémétrie technique brute** reste un flux OEM séparé, décimé et borné, jamais une ligne par tick moteur en SQLite. Le lecteur `kwipi_journal.py` fournit déjà des sorties JSONL/CSV de fixtures : le réutiliser, ne pas lui attribuer le suivi réel qu'il n'a pas.

La consultation différée devrait proposer un **export manuel local**, expurgé, avec manifeste SHA/versions, événements, compteurs, éventuels extraits OEM, index des inconnus et marqueurs de corrections. Une future vue directe doit être opt-in et locale. Aucun agent distant autonome de collecte tant que consentement, stockage, partition `data`, sécurité réseau et coût embarqué ne sont pas validés.

## 6. Lots, dépendances et acceptation

| Ordre | Lot | Livrable/test vérifiable | État au lancement |
| --- | --- | --- | --- |
| 0 | **Cadrage présent** | Docs/plan-action, README et roadmap synchronisés ; aucun code/moteur | documenté, [PR #140](https://github.com/Jean-Philippe56520/Microduck/pull/140) fusionnée |
| 1 | **OBS-1** | Diagnostic JSONL fictif borné et lecture seule sur EX1/EX2 ; aucune vraie télémétrie robot | codé/testé PC-fixtures ; [PR #141](https://github.com/Jean-Philippe56520/Microduck/pull/141) fusionnée |
| 2 | **MEM-1** | États d'objectifs fictifs persistants et liens vers EX1, sans duplication d'épisodes ; tests réouverture/correction | codé/testé PC-fixtures ; [PR #142](https://github.com/Jean-Philippe56520/Microduck/pull/142) fusionnée |
| 3a | **DET-1** | Biais de détermination optionnel sur candidats F2 déjà sûrs, uniquement pour objectif fictif non tenté ; tests A/B | codé/testé PC-fixtures ; [PR #143](https://github.com/Jean-Philippe56520/Microduck/pull/143) fusionnée |
| 3b | **MEM-2** | MEM-2A lecteur en lecture seule livré ; MEM-2B continuité et nouveauté multi-vues encore non prouvées | MEM-2A #147 fusionnée/testée PC-fixtures ; MEM-2B prévu |
| 4a | **QW-1** | Qwen3.5 9B PC reçoit un rappel expurgé et **une question utile à un objectif motivé** ; JSON strict, consentement, contrôle de charge F5-C actuel, timeout, aucune écriture ; A/B vrai 9B avec/sans mémoire | prévu |
| 4a+ | **QW-2** | Reconsultation fondée sur valeur informationnelle et stratégies/questions nouvelles **même sans nouvelle image**, adaptation des bornes arbitraires F5-C uniquement après mesure PC, anti-boucle, consentement et repli | prévu (aucune limite changée) |
| 4b | **PER-1** | Humeur descriptive avec inertie, coût d'engagement, repos ; aucun double score/ordonnanceur | prévu |
| 4c | **OBS-2** | Diagnostic direct optionnel + export différé, OEM read-only, événements incomplets signalés ; charge mesurée | prévu |
| 5 | **EXP-1** | Provenance vraie action début/fin/effet, sinon `indeterminate` ; aucun crédit moteur non prouvé | prévu, bloqué sur capacité de preuve OEM/robot |
| 6 | **E2E-1** | Scènes tenues à part et ablation avec/sans mémoire/PC, détermination faible/forte ; tests contradictoires | prévu PC-fixtures |
| parallèle | **Cat-A2b/C3-B** | Vision basse réaliste, contre-annotations indépendantes, confusion/`unknown`, scènes disjointes | priorité existante maintenue |
| après robot | **PHY-1** | Audit robot en lecture seule puis gestes OEM graduels sous supervision, ressources/stop/capteurs frais mesurés | bloqué : robot absent |
| dernier | **AUT-1** | Expériences physiques autonomes seulement pour classes d'actions réellement validées et sûres | bloqué : PHY-1 |

**Critères E2E minimaux :** comparer `mémoire off/on × Qwen off/on` sur les mêmes situations inédites, puis `determination` différente à mémoire/perception identiques ; ablation sans robot. Mesurer pertinence de la décision, non-répétition, abstention, fausse attribution, nombre de corrections et cohérence sur plusieurs sessions. Aucune réussite de fixture ou de CI ne sera dénommée autonomie robot.

**Tests négatifs obligatoires :** second écrivain, Qwen absent ou malformé, fausse preuve d'action, hors quota, image/contenu privé, capteur périmé, vivant représenté/réel, zone/sol inconnu, état « pris » sans preuve, récipient non reconnu, erreur d'horloge, fichier de télémétrie tronqué, journal dupliqué, ancienne rétraction réapparue, échec sans stratégie alternative.

## 7. Métriques, seuils et passage sur matériel

Suivre objectifs (`created/active/suspended/verified/abandoned`), tentatives par stratégie, pauses et reprises, répétitions sans information nouvelle, contradictions, ratio `indeterminate`, dérive d'humeur, effets des ablations, consultations Qwen pertinentes/hallucinées, omissions du journal et motifs de refus. Mesurer sur PC séparément temps CPU, RSS, SQLite/WAL, taille export, latence du vrai Qwen, puis **sur robot** uniquement après audit version/configuration/caméra/policy, partition persistante, température, batterie et cadence 50 Hz.

Les quotas initiaux et les seuils de fixtures ne sont ni une performance physique ni un budget d'autonomie. La décision stop/repli s'applique avant tout score de curiosité ou de détermination.

## 8. Protocole de livraison et première action

Chaque lot suit [AGENTS](../AGENTS.md), [protocole de réutilisation](development-reuse-protocol.md), [registre C3](community-reference-registry-2026-10-26.md), [audit matériel](hardware-feasibility-audit-2026-10-25.md) et [plan EX](kwipi-experiential-learning-plan-2026-10-26.md) : lire source OEM **épinglée**, version/configuration réellement actives, inspecter tiers pertinents, poser observation/hypothèse/preuve/critère d'échec/risque/retour arrière, tests positifs et négatifs, mesures, PR séparée, CI verte puis revue/fusion. Aucune modification des sous-modules sans accord.

**État actualisé après la PR #143 :** OBS-1 (#141), MEM-1 (#142) et DET-1 (#143) sont fusionnés et leurs CI de PR sont vertes, **exclusivement sur fixtures PC**. Les lots MEM-2/QW-1/PER-1/OBS-2/EXP/E2E/PHY/AUT restent à traiter avec leurs propres preuves et critères OEM. La corrélation OEM entre action et effet indépendant n'est pas encore fournie ; **aucune validation robot ni autonomie motrice n'est démontrée**.
