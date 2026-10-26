# PD3 — Besoin sémantique de Kwipi, avant toute consultation Qwen

**27 octobre 2026 — [PR #76](https://github.com/Jean-Philippe56520/Microduck/pull/76) et [CI hôte #40422474003](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40422474003) : 1 221 tests exécutés, 19 ignorés, zéro échec, dont 22 scénarios PD3. Code sur fixtures fictives ; aucun appel PC/Qwen et aucune validation sur Microduck physique.** [PD0](pd0-behavior-states-selective-qwen-2026-10-27.md) fixe la politique ; [PD1](pd1-oem-expression-capabilities-2026-10-27.md) le catalogue historique des 16 états ; [PD2](pd2-coherent-mock-behavior-continuity-2026-10-27.md) une continuité **descriptive**, non motrice. [Cat-A2b et le plan directeur](plan-action.md) conservent la priorité des prises visuelles réelles basses.

## 1. Choix architectural : deux décisions distinctes

**Intérêt d'apprendre ≠ permission d'envoyer à Qwen.**

Une éventuelle consultation doit d'abord répondre à deux questions indépendantes :

1. **La situation pose-t-elle une question nouvelle, pertinente et persistante ?** PD3 calcule une **opportunité fictive** à partir du résultat F2/F5-A déjà établi, du portrait P-A/P-B, de l'état descriptif PD2, des motivations et de deux observations F1-B de laboratoire. Ni un état `LookAround` ni une humeur curieuse ne suffisent.
2. **Disposons-nous de données utiles à transmettre à Qwen, avec consentement et quotas ?** **Non dans le contrat actuel F5-A/B.** La requête transmet uniquement `object_label=unknown`, statut `unknown` ou `conflict` et une confiance **déclarée**. Aucun pixel ni caractéristique discriminante n'est transmis, et le prompt de laboratoire Ollama impose une réponse `unknown`. Dépenser une consultation n'apporterait donc **aucune information nouvelle crédible**.

Le module [`semantic_pc_opportunity.py`](../microduck_companion/semantic_pc_opportunity.py) exporte `assess_mock_pc_opportunity(...)` et `MockPCOpportunity` : il décrit l'intérêt, le motif de refus et la provenance, mais **force toujours** `eligible_for_transport=False`, `request_transmitted=False`, `pc_requests_issued=0`, `real_scene_verified=False`. Il ne crée **ni** `PCRequest`, **ni** transmission, **ni** réservation F5-C. Ces invariants sont validés par le type de sortie.

Le sélecteur **F2 choisit une seule fois** via le mécanisme déjà livré `start_optional_pc_cycle` de **F5-A**. PD3 consomme la réponse `OptionalPCAdvisory` **existante** : jamais une seconde boucle, ni un second `AutonomyBrain`. PD3 n'intercepte pas les autres appels F5 existants ; pour une future politique de production, le coordinateur devra exiger PD3 **avant** de soumettre à `SelectivePCBridge`. Ce branchement de transport est **hors périmètre de PD3**, précisément parce que les données utiles ne sont pas encore disponibles.

## 2. Audit de réutilisation avant création

| Déjà existant et vérifié | Réutiliser / adapter / créer |
| --- | --- |
| OEM épinglé [`942e58e3`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) : `robotd`, `mediad`, `tofd`, `pet-detect`, JSON-RPC | **Réutiliser ultérieurement** ses capteurs ; aucun démon, flux, moteur, son ni pilote constructeur n'est touché par PD3. `robotd` garde seul les moteurs. |
| [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) et [#414](https://github.com/pollen-robotics/microduck/pull/414) | Toujours **ouvertes/non fusionnées** au contrôle du 27/10/2026. Une proposition de cerveau ou de carte ne constitue ni un capteur réel authentifié ni une capacité de déplacement. |
| [Registre C3](community-reference-registry-2026-10-26.md) : Quacksat, QuackNav/microduck-brain, GC-RENCAO/Smartulf123, microduck-twin, quack-control, lab/studio | **Veille seulement**, aucun modèle, moteur, méthode de consultation ou licence tierce ajouté. Les cerveaux qui autorisent des actions depuis Qwen ne sont pas retenus. |
| F1-B [`PassiveRead`](../microduck_companion/passive_sources.py), F1-A [`summarize_passive`](../microduck_companion/passive_observations.py) | **Réutiliser sans capteur inventé**, vérifier provenance `mock_fixture_unix`, statut, catégorie `unknown/conflict`, ordre, fraîcheur, deux séquences fictives distinctes et continuité d'empreinte de suivi **éphémère**. Aucun visage, voix, photo, piste nominative ni audio. |
| F2 [`AutonomyBrain`](../microduck_companion/autonomy.py), P-A/P-B `BehaviorPortrait`, PD2 `MockBehaviorDisposition` | **Lire une décision déjà produite** ; motivations et prudence sont des valeurs **simulées**, pas une batterie mesurée. `BallPlay` est descriptif, pas un mouvement. |
| F5-A [`OptionalPCAdvisory`](../microduck_companion/pc_hypothesis_contract.py), F5-B [Ollama](../microduck_companion/ollama_local_client.py), F5-C [`SelectivePCPolicy`](../microduck_companion/selective_pc_policy.py), F5-D | **Réutiliser les contrats et ne pas copier les quotas**. Le bilan F5-A produit déjà une requête fictive si une catégorie est incertaine, mais cette requête **n'est pas utile sémantiquement** aujourd'hui. Aucune modification F5 ni HTTP dans ce lot. |
| SQLite [`ExperienceMemory`](../microduck_companion/episodic_memory.py), `BehavioralMemory`, EX1/2/3 | **Ne pas écrire** de nouvelle table, `MoodMemory` ou copie du journal. Un `inspection_reserved` déjà soutenu par les souvenirs F4-A inhibe la candidature ; une correction/relecture peut faire disparaître ce frein. |

**Créer uniquement** la fonction de triage pure et ses tests. Aucun poids, entraînement, seconde base, calendrier, récupération d'audio, démon réseau ni worker supplémentaire.

## 3. États historiques et opportunités Qwen

| État / situation | Intérêt PD3 aujourd'hui | Transport aujourd'hui |
| --- | --- | --- |
| **LookAround** avec deux lectures d'une catégorie de fixture `unknown` ou `conflict`, séparation temporelle valide et intention F2 `inspect` | **Candidat**, si curiosité et énergie suffisantes, prudence acceptable, source non privée | **Non**, seules les étiquettes fictives seraient envoyées |
| **TurnInPlace** / **Wander** | **Candidat fictif** seulement si le portrait F2 antérieur est `LookAround/curious`, le contexte PD2 concorde et un objet reste incertain. **Pas de vraie rotation ni exploration.** | **Non** |
| **GroundPick** | État historique possible dans PD2, mais **pas d'appel utile dans l'état F5 actuel** ; l'objet réellement au sol n'est ni localisé ni saisi et la familiarité nécessaire ne provient pas d'une lecture `unknown` seule | **Non** |
| **BallPlay** | Un jeu connu ou une invitation ne constituent pas une question d'identification. Une surprise sémantique pendant le jeu est **future** et nécessitera d'abord une observation distincte `inspect`, une provenance et un contrat adapté | **Non** |
| **Startle**, bruit inhabituel | Le sursaut n'atteste pas une catégorie sonore ni une demande sémantique. Une analyse d'un son inconnu répétée est **future** après un classifieur éprouvé, sans parole privée | **Non** |
| **Chill, Nap, Zoomies, Stretch, Ruffle, Preen, Sneeze, Dance, Petted, Held** | **Aucun appel** sur le seul libellé ou son bruit/affect supposé | **Non** |

Les trois états de type `Wander/TurnInPlace/GroundPick` sont **de simples libellés de scène fictive** (PD2) et ne donnent jamais une permission motrice. PD3 exige aussi un contexte concordant et frais : une mention `Wander` sans `new_space` ou `TurnInPlace` sans `viewpoint_ambiguity` est écartée.

## 4. Contrat précis et filtres

`assess_mock_pc_opportunity` reçoit un **`OptionalPCAdvisory` F5-A déjà calculé**, un portrait P-A/B déjà obtenu, une disposition PD2, une situation PD2, deux lectures F1-B, les cinq motivations existantes, l'horloge monotone de fixture et `pc_opt_in`.

- Seule une **intention locale `inspect`** déjà choisie et une demande F5-A **`pending_transport`** non expirée peuvent devenir une opportunité. Le motif et la confiance doivent correspondre à la **lecture actuelle**. Aucune consultation nouvelle n'est fabriquée.
- Deux **acquisitions fictives** avec séquences strictement croissantes, entre **0,5 et 30 secondes fictives** d'écart, observation courante de moins de **1 seconde**, même trace de test éphémère et un seul objet incertain `unknown` ou `conflict`. Ce critère démontre la **cohérence des fixtures**, **pas l'indépendance ou la robustesse de vrais capteurs**.
- Tous les événements doivent être `mock` et du type `object_label`, catégorie connue par la liste de sécurité ou `unknown`. **Refus complet** si catégorie `person`, voix/parole, plusieurs entités, texte libre (ex. nom d'une personne), événement non fiable, statut incohérent, époque incorrecte, horloge reculée ou indice périmé.
- L'état de base est `LookAround/curious` provenant d'un portrait d'attention F2. `Nap`, `Startle`, `Petted`, `BallPlay`, les scènes `stop/fallen/busy` et tout contexte PD2 sans pertinence sémantique sont refusés.
- Motivation `curiosity >= 0.55`, énergie **simulée** `>= 0.35`, prudence `<= 0.70`, et absence d'`inspection_reserved` ou d'historique indisponible. Valeurs **de laboratoire uniquement**, non calibrées sur robot.
- Un candidat retourne `interesting=True`, `trigger=unknown/conflict`, `fixture_samples=2`, mais **jamais `eligible_for_transport`**. Même avec `pc_opt_in=True`, la raison est `f5_has_no_discriminating_input`. Sans opt-in : `pc_opt_in_missing`. En refus : `interesting=False` et raison explicite.

**L'option `pc_opt_in=True` ne constitue ici ni un consentement vérifié à transférer des photos/voix, ni une activation du réseau.** Toute extension multimodale devra obtenir un consentement spécifique, démontrer l'utilité de ce qui est envoyé et appliquer **les quotas F5-C existants** : intervalle 60 s, 2/600 s, 8/24 h, une demande en vol, backoff. Aucun nouveau quota d'humeur PD3.

## 5. Tests et preuves

[`tests/test_pd3_semantic_pc_opportunity.py`](../tests/test_pd3_semantic_pc_opportunity.py) couvre le cycle F5-A réel **sur fixtures** (sans double tick F2), l'inconnu et le conflit répétés, l'effet de `LookAround/Wander/TurnInPlace`, le refus des catégories connues, noms/voix/personnes, timestamps, ordre et présence de séquences, track éphémère cohérent, énergie/prudence, STOP/chute/activité, mémoire rétractable et P-A/B, demande F5 malformée ou périmée, tentative de fausse disponibilité d'action/réseau et **absence de modification SQLite, de consommation de quota ou d'envoi**.

Les tests sont soumis à la CI globale GitHub ; seule une réussite CI autorisera la fusion. **Aucun vrai Ollama/Qwen 4B ou 9B, photo, voix, interaction moteur, chronométrage RK3566, Yocto ou robot physique n'est validé.**

## 6. Suite

1. **Cat-A2b** : capturer des scènes réellement basses et indépendantes, mesurer fausses reconnaissances, pertes de vue et inconnus, avant de présenter de vraies questions sémantiques.
2. **PD4 conditionnel** : étudier un contrat PC **multimodal privé** et utile, éphémère, borné en octets et en fréquence ; consentement par session et PC facultatif. Comparer **Qwen 4B puis 9B** sur vrais jeux autorisés, pas en prétendant un accélérateur disponible sans mesure.
3. Quand des indices réels sont disponibles, réutiliser l'arbitrage local F2 et les limites F5-C, ajouter le branchage sécurisé **sans jamais permettre à Qwen de décider un mouvement**, ni de déclarer une identité, une causalité ou un sol sûr.
4. **PD5–PD7** : ports OEM vérifiés, simulation puis mesures réelles ; les états historiques ne valent jamais preuve d'un geste joué.

**Statut réel :** PD3 sait décrire des **occasions fictives d'apprendre**. Il ne sait pas encore rendre une demande à Qwen réellement utile, et **ne déclenche aucun appel**. C'est un garde-fou intentionnel pour préserver le caractère autonome, sobre et principalement silencieux de Kwipi.
