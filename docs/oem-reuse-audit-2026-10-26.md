# Audit de réutilisation OEM — autonomie et mémoire Microduck Companion

**Complément P-C (26/10/2026) :** vérification au commit OEM épinglé `942e58e3aa6dbb28e7037203fff11866122c7567` : `pet-detect/src/worker.rs` partage l'unique micro `arecord` pour la caresse et la sentinelle `SoundEvent::Noise/Voice`; `robotd/src/main.rs` consomme `PettingEvent::Start` et joue `coo` sous protections, alors que les sons ambiants sont seulement journalisés. `robotd/src/idle_head.rs` fournit déjà les mouvements d'inactivité et `sounds/src/personality.rs` des traits de voix stables. **Réutiliser** ces propriétaires ; **adapter uniquement** une lecture fictive P-A/B/F4 après décision via `oem_expression_hints.py`; **ne créer** ni second micro, synthé, commande, robotd, table SQL ou moteur M9. [Détails et limites](kwipi-oem-expressions-pc-2026-10-26.md). Aucune réaction réelle validée.


**Addendum P-B (26/10/2026) :** [réutilisation supplémentaire](kwipi-personality-continuity-pb-2026-10-26.md). F4-A `BehavioralMemory` (résultats P2a fictifs vérifiés, corrections et 14 jours/256 lignes) est **relue**, et non reproduite, pour fournir un faible biais facultatif à l'inspection cognitive F2 et une tendance descriptive dans P-A. Aucune table, nouvelle boucle/arbitrage moteur, copie OEM ou animation concurrente. `robotd` reste seul propriétaire de l'exécution ; M9 OEM et PR #381 non fusionnée ne sont pas traités comme des API. Aucun déploiement ni preuve matérielle.


**Complément P-A (26/10/2026) :** la [matrice de personnalité à 16 états historiques](kwipi-behavior-personality-16states-2026-10-26.md) confirme : **réutiliser** OEM IdleHead/sons et F2/F4/ExperienceMemory ; **adapter** uniquement la présentation `AutonomyBrain.describe_behavior` après une intention fictive ; **ne pas créer** de second scheduler, contrôleur, base ou boucle 50 Hz. Le code décrit 4 états sur fixtures et référence 12 états conditionnels. Les services M9 OEM non fusionnés et PR #381 restent des prérequis de compatibilité. Pas de changement de matériel ou licence, ni mesures RK3566.


**26 octobre 2026 — revue de sources, sans déploiement ni nouvelle capacité physique.**
Décision : conserver le constructeur comme **propriétaire exclusif des capteurs, des intentions motrices et des animations embarquées** ; conserver Companion comme **prototype de cognition/mémoire non motrice** tant qu'une interface OEM d'autonomie n'est pas définie. Ne pas créer un second contrôleur de mouvement ou un second système permanent de comportements à côté du futur cerveau M9.

## 1. Périmètre et sources faisant foi

- Dépôt de travail : [Jean-Philippe56520/Microduck](https://github.com/Jean-Philippe56520/Microduck). Le sous-module [upstream/microduck](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) est épinglé à **942e58e3aa6dbb28e7037203fff11866122c7567**. [upstream/microduck_rl](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3) est épinglé à **b02fdea4902c2b93b7d34a83a6f05da4ececb7d3**. Aucun sous-module n'est avancé dans cet audit.
- Revue du code Rust et du contrat officiel, notamment [robotd/idle_head](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/idle_head.rs), [robotd/control](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs), [duck-control/safety](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-control/src/safety.rs), [mediad/frame](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/frame.rs), [mediad/detect](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/detect.rs), [pet-detect/worker](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/pet-detect/src/worker.rs), [tof/main](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/tof/src/main.rs), [robotd/chorale](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/chorale.rs), [robotd/vetbook](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/vetbook.rs) et [protocole JSON-RPC](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs).
- La [roadmap OEM — M9](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/project/roadmap.md#L306-L338) et les [idées d'autonomie](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md) sont des **descriptions/intentions constructeur**, et **non** un moteur autonome M9 livré.
- Revue des modules Companion existants : [AutonomyBrain](../microduck_companion/autonomy.py), [PassiveRhythm](../microduck_companion/passive_rhythm.py), [ExperienceMemory](../microduck_companion/episodic_memory.py), [MultiviewPatternMemory](../microduck_companion/multiview_pattern_memory.py), [SelectivePCPolicy](../microduck_companion/selective_pc_policy.py), [mediad preflight](../microduck_companion/oem_frame_preflight.py), et [étude M1-B2](m1b2-host-embeddings-2026-10-26.md).
- Méthode : inspection statique des fichiers, inventaire de source, comparaison de responsabilités ; **pas** de build OEM, tests matériels, lancement d'une inférence sur Microduck, consultation Qwen réelle ou installation d'un service. Le dépôt constructeur peut évoluer ; recontrôler les révisions avant intégration.

### Niveaux de preuve

**OEM codé dans les sources** = source vérifiée à la révision épinglée, pas validation par nos soins sur robot. **OEM documenté/historique** = décrit, non disponible dans le système actuel à cette révision. **Companion testé sur fixtures/PC** = logiciel expérimental, ni fonctionnalité embarquée ni capteur validé. **Intégration sur robot** = entièrement ouverte pour Companion.

## 2. Capacités OEM à réutiliser, sans les dupliquer

| Capacité | Constat dans le code OEM épinglé | Conséquence pour Companion |
| --- | --- | --- |
| Sécurité, bus moteurs, boucle ~50 Hz, politiques ONNX, deadman | robotd et duck-control implémentent le contrôle et ses barrières | **Réutiliser exclusivement** ; jamais d'accès direct servo, de seconde boucle ou d'autorité moteur Companion |
| Skills, posture, mouvement, regard et commandes | robotd/control, intents et protocole JSON-RPC implémentent des intentions | Ne proposer plus tard qu'une **intention autorisée**, avec refus/expiration ; aucune action physique dans ce lot |
| Animation au repos | robotd/idle_head produit regards, mouvements subtils, bâillements ; le fichier précise « pas un regard ciblé sur un objet » | **Ne pas réimplémenter** un générateur de regards aléatoires ; conserver la distinction entre animation OEM et curiosité orientée par des souvenirs |
| Images et caméra | mediad/frame sert media.frame via socket local, entête JSON puis pixels bruts ; WebRTC possède sa propre voie | Ne pas créer un nouveau pilote/capture permanente ; futur client **lecture seule**, borné, avec authentification locale et filtrage de confidentialité |
| Détection visuelle sur NPU/CPU | mediad/detect et duck-detect reconnaissent **les autres Microducks seulement**, à cadence limitée ; NPU RKNN avec repli ONNX CPU | Reprendre l'infrastructure/format après vérification ; **ne pas** compter ce modèle comme détecteur chat, chien, personne ou peluche |
| ToF 8×8 | tof/main diffuse une matrice frontale ; pas de carte maison garantie | Lire les données fraîches quand elles sont autorisées ; aucune navigation libre ou certification d'escalier |
| Microphone, sons d'ambiance et caresses | pet-detect/worker acquiert l'audio avec une sentinelle ambiance/voix approximative et un classificateur de **caresses** | Réutiliser ces signaux ou un événement OEM permis ; **ne pas** reconstruire l'acquisition micro ni appeler ce modèle détecteur de chien/chat ou reconnaissance vocale |
| Présence de Microducks, chorale et voix | robotd/chorale, radio BLE et synthèse de sons préexistants | Préserver ces capacités OEM ; les idées de salutations et « amitié » entre Microducks ne sont pas une identification individuelle d'animaux ou d'enfants |
| Journal « vetbook » | robotd/vetbook conserve des faits et compteurs sur la vie du matériel | **Ne pas confondre** journal de santé/moteurs/caresses et mémoire sémantique/épisodique d'objets ; pas d'écriture Companion dans vetbook |

**Limite commune :** les éléments OEM sont présents dans les sources à la révision citée ; les services effectifs, capteurs montés et capacités en usage sur **notre futur appareil** restent inconnus.

## 3. Cerveau autonome M9 et ancien prototype : statut réel

Le document OEM [ideas/autonomous_behavior.md](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md) liste **16 états d'un ancien prototype** (notamment Chill, LookAround, Wander, BallPlay, Nap, Petted), une énergie/humeur, une grille de nouveauté, des réactions sonores et l'évitement ToF. Toutefois, il dit explicitement que le fichier **autonomous.rs ne figure pas dans le daemon courant**, ce que confirme l'arbre Git épinglé. La [roadmap constructeur M9](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/project/roadmap.md#L306-L338) le place encore dans les travaux à venir. **Ne pas déclarer les 16 états fonctionnels dans la version actuelle.**

La source historique exacte et sa licence/version à copier n'ont **pas** été auditées en dehors de ce snapshot. Il serait prématuré de copier cet algorithme, d'implémenter M9 nous-mêmes ou d'en affirmer les performances physiques. Le module OEM IdleHead est une **partie** de ce type de comportement, pas la boucle complète « curiosité → mémoire → action → apprentissage ».

Notre [AutonomyBrain](../microduck_companion/autonomy.py) et notre [PassiveRhythm](../microduck_companion/passive_rhythm.py) ont un **chevauchement conceptuel** (motivation, cadence, repos, évitement des répétitions) avec le futur M9, mais **aucun chevauchement d'autorité physique aujourd'hui** : ils ne sont pas branchés aux moteurs réels. **Conserver le prototype et ses tests**, sans créer un deuxième cerveau actif sur l'appareil. À l'arrivée de M9, comparer ses interfaces avant toute activation de logique comportementale Companion.

## 4. Nos apports complémentaires à conserver (état exact)

| Sujet | État Companion au 26 octobre 2026 | Décision |
| --- | --- | --- |
| Intention passive, motivations, repos simulé | Python F2-A/B/C/D, tests sur catégories et sockets fictifs | **Conserver comme banc d'expérimentation**, pas comme chef d'orchestre embarqué |
| Mémoire épisodique, sémantique, préférences et lieux incertains | SQLite locale sur stimuli fictifs ; corrections et rétentions définies | **Conserver**, réutiliser la même SQLite ; aucune mémoire OEM équivalente identifiée dans le snapshot |
| Mémoire multimodale d'empreintes et multi-vues | M1-A/B/B2 testés en hôte, rapprochement incertain ; embeddings ONNX non portés | **Continuer** avec jeux réels publics/autorisés comportant plusieurs prises de vue du *même objet* et des négatifs crédibles |
| Catégories chats/chiens/objets et sons | Bancs publics très petits, pas de modèle installé sur robot | **Développer et mesurer**, avec classe unknown ; ne pas confondre classe, instance et identité |
| Hypothèses facultatives Qwen | F5-A/B/C/D : contrats, client HTTP et tests serveur simulé, sans vrai Qwen | **Conserver en option** ; local autonome et repli sans réseau. Aucun Qwen ne valide une identité ni ne commande un moteur |
| Associations volontaires | F4-D : démonstrations de jetons fictifs révocables, sans biométrie | **Conserver comme contrat de confidentialité**, sans branchement à un enfant ni à un animal réel |

Le travail M1-B2 n'a **pas** choisi de modèle embarqué ; MobileNetV2 y utilise les **probabilités de classes ImageNet**, non un vecteur d'identité d'objet. Une même catégorie ne suffit pas pour conclure « même peluche ».

## 5. Frontières d'intégration à préserver

1. **Propriété des services :** robotd seul contrôle les moteurs ; mediad et son pipeline restent propriétaires de caméra/audio ; tofd est propriétaire des distances. Companion ne récupère que des observations **autorisées, datées et sourcées**, éventuellement en mode lecture seule.
2. **Pas de double arbitrage :** ne pas superposer un générateur de mouvements Companion à IdleHead ou à un futur M9. Les intentions cognitives (inspecter un souvenir, écouter, rester immobile) sont différentes des commandes et animations réelles. Toute capacité d'attention motrice future exige contrat d'arbitrage OEM, sécurité, disponibilité et mesure de latence.
3. **Pas de faux niveau de preuve :** une notification WebRTC n'est pas un événement authentifié sur socket Unix ; une vignette NPU d'autre Microduck n'est pas une catégorie chat/chien ; un mot « voix » de la sentinelle n'est pas une transcription ; un vetbook OEM n'est pas notre mémoire d'objet.
4. **Confidentialité avant capteur réel :** la catégorie unknown ne filtre pas les personnes/paroles. Aucun pipeline privé de photos/voix, aucune sauvegarde média brute et aucune transmission Qwen sans contrôles explicites adaptés.
5. **Ressources non extrapolables :** l'inférence constructeur a ses propres cadences/contraintes thermiques ; les mesures CI de notre mémoire ou de nos modèles sur PC ne garantissent aucune marge RAM, stockage, température ou boucle moteur RK3566.
6. **Respect de version et des licences :** aucun code OEM copié ou modifié dans cet audit ; pas d'avance silencieuse des sous-modules ni de modification d'unité systemd. À chaque mise à jour constructeur, revalider les interfaces et les hypothèses M9.

### Contrat d'ownership testable

L'inventaire [oem-reuse-inventory-2026-10-26.json](oem-reuse-inventory-2026-10-26.json) marque chaque responsabilité et le statut « implémenté OEM », « décrit mais non porté » ou « testé seulement dans Companion ». Les tests de schéma/offline contrôlent qu'on ne promeut pas M9 en fonctionnalité présente ni nos modules fictifs en capacités physiques. Ce sont des **tests d'inventaire**, **pas** une preuve de conformité du robot.

## 6. Nouvelle séquence recommandée, par étapes distinctes

**R0 — présent lot (audit seulement).** Matrice de réutilisation et non-duplication, tests d'inventaire, README/roadmap/plan/audit cohérents. Pas de changement de comportement.

**R1 — compatibilité lecture seule sur fixtures.** Réutiliser F1/F3 existants pour définir un contrat minimal d'observation (provenance, timestamp, taille, latence, disponibilité, redaction, unknown) à partir de formats OEM **rejoués**. Aucun appel physique mediad/tofd ni nouvelle commande robotd. L'interface future doit accepter l'absence totale des capteurs.

**R2 — vraie reconnaissance de souvenirs sur PC.** Plusieurs images indépendantes **du même objet autorisé**, plusieurs enregistrements indépendants d'un même son, des classes/instances ressemblantes comme négatifs. Mesurer rappels, **fausses fusions**, rejet unknown, CPU/RSS, conservation d'exemplaires et croissance réelle SQLite. Ne pas inférer une identité d'un seul détecteur de catégorie.

**R3 — harmonisation future avec M9.** Quand Pollen livre une API réelle de cerveau autonome, étudier les points d'extension pour fournir la nouveauté et les souvenirs, **sans deuxième décideur des mouvements**. En attendant, ne brancher aucune intention cognitive à robotd ; poursuivre les expériences F2 sur fixtures.

**R4 — PC facultatif M1-C.** Réutiliser F5-C (opt-in, quotas, timeout, circuit), et y intégrer plus tard des **hypothèses** multimodales sous consentement et sécurité d'accès au réseau vérifiés. L'échec du PC ne change pas l'intention locale ; jamais d'ordre moteur.

**R5 — validation sur appareil réel seulement après réception.** Mesurer RAM libre, espace et montage persistant, latences capteurs, p50/p95 CPU, RSS, température, charge de mediad/tofd et cadence robotd avec le protocole F6-D ; approbation et zone sûre pour toute étape impliquant un mouvement.

**Critère de sortie de cet audit :** le code constructeur n'est ni copié ni modifié ; la frontière de sécurité est écrite ; notre prototype F2 n'est pas présenté comme futur remplaçant direct de M9 ; les prochains essais portent sur l'**interopérabilité passive et la qualité de mémoire**, pas la locomotion.
