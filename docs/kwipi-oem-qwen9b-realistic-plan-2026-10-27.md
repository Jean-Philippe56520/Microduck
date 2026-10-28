# Kwipi — plan révisé selon le Microduck réel et Qwen 9B

**Décision d'architecture du 27 octobre 2026 — DOCUMENTATION UNIQUEMENT.** Le présent document ajuste la priorisation du [plan directeur](plan-action.md) et des plans [EX0](kwipi-experiential-learning-plan-2026-10-26.md), [PD0](pd0-behavior-states-selective-qwen-2026-10-27.md) et [F5](f5b-ollama-local-transport-2026-10-26.md). Il ne livre aucun modèle, appareil, flux vidéo, compétence nouvelle, entraînement ni commande motrice. Le Microduck physique n'est pas disponible : **rien n'est validé sur robot**. Les résultats existants sur PC/fixtures et MuJoCo conservent leur niveau de preuve.

## 1. Décision principale

**Objectif :** Kwipi perçoit, rappelle les souvenirs utiles, évalue nouveauté/incertitude/motivations/risques, formule ou consulte des hypothèses, choisit une intention sûre (ou l'inaction), observe un résultat réellement corroboré, corrige ses attentes et généralise à de nouvelles scènes.

- **Robot autonome sans PC** : une seule boucle cognitive légère (réutiliser `AutonomyBrain` et les contrats F1/F2 comme références de prototype), mémoire locale SQLite `ExperienceMemory`, motivations (curiosité, sociabilité, jeu, énergie, prudence), catégories/indices et refus si inconnu. Pas de LLM embarqué obligatoire ; portage Rust envisagé **après** mesures et audit d'API.
- **PC facultatif : Qwen3.5 9B multimodal choisi par le propriétaire.** Il propose des hypothèses sur la catégorie, l'usage, les relations, les propriétés incertaines, les conséquences possibles et des **observations/expériences à évaluer**. Il ne décrète ni vérité, ni intention, ni permission motrice. Comparaison 4B non requise pour décider du modèle cible ; mesurer en revanche le **vrai 9B**, sa qualité, ses erreurs, sa latence et son coût sur le PC. Aucun véritable Qwen/Ollama n'est validé par la CI actuelle.
- **Un seul propriétaire des moteurs** : `robotd`, politiques ONNX et sûretés OEM à 50 Hz. Qwen, mémoire, vision, audio, motivations ne peuvent pas appeler directement les servos ni certifier le sol. Refus / abstention sûrs en l'absence de capteur, de preuve d'action ou de PC.
- **Ne pas préentraîner chaque scène** : reconnaître des catégories avec des modèles adaptés ; conserver des propriétés/relations/hypothèses et des résultats sourcés plutôt que chaque image ; affiner un réseau uniquement si une limite mesurée le justifie, sans auto-entraînement des politiques motrices.

## 2. Audit de compatibilité et de réutilisation (OEM épinglé)

Source : [OEM `942e58e3aa6dbb28e7037203fff11866122c7567`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567), [simulation `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3), [README OEM](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/README.md), [cheatsheet des skills](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md), [policy-channel-design](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/policy-channel-design.md), [configuration robotd](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/deploy/robotd.toml). **Un skill documenté n'implique pas que son modèle soit effectivement chargé sur le futur robot : inspecter `robotctl policy list` et l'état réel.**

| Capacité | État exact | Décision |
| --- | --- | --- |
| Équilibre, marche, posture, arrêt, deadman, arbitrage | OEM `robotd` / `duck-control`, politiques motrices | **Réutiliser**, ne jamais créer de contrôleur moteur concurrent |
| Ramassage au bec | Bec articulé et **`ground_pick` disponible dans le catalogue OEM** ; séquence physique non testée par Companion | **Réutiliser**. Une chaussette précise, une prise maintenue, le transport et la restitution **ne sont pas prouvés** |
| Coup de pied | `kick_left` / `kick_right` dans l'inventaire des politiques OEM | **Réutiliser** le geste, **ne pas** déclarer détection automatique d'une balle, alignement, jeu autonome, état `BallPlay` ou réussite physique |
| Regard, animation au repos, sons, caresses | `robotd/idle_head`, sons OEM, `pet-detect` | **Réutiliser** ; les 16 anciens comportements ne sont pas 16 routines autonomes actives |
| Caméra et média | `mediad`, `media.frame` sur socket local ; WebRTC distinct | **Adapter** un lecteur passif et autorisé, sans second pilote ni captation permanente |
| ToF frontal 8 × 8, IMU | `tofd`/OEM | **Réutiliser** les lectures ; **incompatible avec une garantie de sol, anti-escalier 360° ou navigation domestique sûre** |
| Vision chat/chien/personne/chaise/balle | Détecteur OEM surtout dédié aux autres Microducks ; YOLOX-Nano Companion étudié sur PC, sans portage validé | **Conditionnel** : Cat-A2b, erreurs/unknown/caméra basse puis mesures NPU/CPU sur l'appareil |
| Mem. épisodique/sémantique/comportementale | `ExperienceMemory`, F4, EX1–4, M1-B expérimental | **Réutiliser/adapter**, une seule SQLite et un seul chemin actif de signatures, aucune identité induite d'une empreinte |
| Qwen3.5 9B vision | Fonction multimodale côté **PC**, tests réels non exécutés | **Prévu**, jamais sur le RK3566 1 Go, ni dans la boucle moteur |

**Matériel et ressources :** RK3566, environ 1 Go de RAM annoncé, stockage 32 Go annoncé (variante bêta eMMC 64 Go), NPU INT8 limité. Le choix final Zero 3W / IMX219 ou carte bêta Seeed / GC2093, les partitions montées, RAM libre, RSS combiné, performances et thermique restent à vérifier sur l'unité livrée. Les chiffres YOLO/SQLite mesurés sur PC sont **non transposables** ; `scripts/resource-audit.sh` est obligatoire avant tout portage. Le ToF annoncé « LiDAR » par le marketing reste ici une matrice frontale 8 × 8, pas une couverture omnidirectionnelle.

**Évolutions non livrées à ne pas présumer** : [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) (conception du cerveau, ouverte) et [#414](https://github.com/pollen-robotics/microduck/pull/414) (`maploc/mapd` et API v45, ouverte), vérifiées le 27/10/2026. Recontrôler à chaque chantier. Le [registre C3](community-reference-registry-2026-10-26.md) cite QuackNav/microduck-brain, Quacksat, microduck-twin, GC-RENCAO/Smartulf123, quack-control, lab/studio : **veille**, sans import, poids, licence ni compatibilité présumée.

### Trois niveaux de compétence, à distinguer dans chaque PR

1. **Primitive constructeur** : `ground_pick`, `kick_left`, `robot.look`… disponible dans le contrat OEM, disponibilité effective et état de chargement à vérifier.
2. **Perception et situation** : détecter un objet, estimer pose/distance/continuité/risque ; ceci n'est pas fourni par la seule primitive motrice.
3. **Comportement autonome sûr** : choisir la bonne primitive, vérifier l'environnement et l'exécution/résultat, décider de l'expérience suivante. **Non livré** pour le ramassage de chaussette, la balle et la navigation libre.

## 3. Architecture Qwen 9B : contrat v2 projeté, pas un branchement actif

**Réutiliser** `pc_hypothesis_contract.py` (F5-A), `ollama_local_client.py` (F5-B), `selective_pc_policy.py` (F5-C), filtres F5-D et PD3. Leur **v1 actuelle** transmet seulement des étiquettes fictives `unknown`, sans pixels, et refuse les classifications non vérifiées. Ne pas prétendre que le multimodal est déjà branché et ne pas assouplir silencieusement v1. Créer **un contrat versionné distinct** uniquement après tests ciblés.

- **Déclenchement** : nouveauté/contradiction ou stratégie locale insuffisante, besoin réellement transmissible, consentement de la session, quota et cooldown, PC accessible. Aucune consultation répétée pour une scène déjà expliquée par la mémoire ; `unknown` reste permis.
- **Entrée autorisée** : **au plus une image utile pour le pilote** (recadrage/miniature, et vue d'ensemble seulement si besoin justifié et budget évalué), catégorie et incertitude locales, propriétés observées, quelques souvenirs génériques expurgés, capacités OEM **inventoriées** et question ciblée. Ne pas transmettre SQLite entière, noms privés, données d'enfants, flux vidéo/audio continu ni scènes sensibles. Filtrer la TV/écrans : une représentation de personne à l'écran n'est pas une personne présente. **Une photo n'est envoyée que si la politique de confidentialité l'autorise explicitement.**
- **Transport** : API image Ollama `POST /api/chat` (images encodées en base64, taille totale strictement plafonnée), PC local sur lien **authentifié et chiffré** ; ne pas exposer Ollama en HTTP brut sur le LAN comme production. Worker hors boucle 50 Hz, une requête à la fois, gestion d'expiration et de réponse tardive. La fenêtre v1 de deux secondes n'est pas une garantie réaliste pour du 9B multimodal : faire évoluer **uniquement** le contrat de conseil différé avec une validité de scène explicitement contrôlée, sans ralentir les fonctions locales.
- **Réponse stricte** : schéma JSON versionné, taille/énumérations bornées ; `hypotheses` (catégorie/fonction/relation), `properties`, `possible_outcomes`, `suggested_observations`, `risks`, `unknowns`, sources et incertitudes. Enlever tout vocabulaire libre susceptible d'être interprété comme ordre moteur. Valider et traiter en **hypothèses non vérifiées**, jamais comme fait, sol sûr, permission ou récompense. Réponse absente/invalide → repli local, aucun effet physique.
- **PC cible** : `qwen3.5:9b` préféré. Mesurer sur le PC réel les performances, l'abstention, les hallucinations, la latence de chargement/inférence, le RSS, le réseau, les données transmises et la qualité sur scènes indépendantes. Aucune performance Ryzen AI, GPU/NPU ni mémoire Ollama n'est encore mesurée.

**Exemples de test** : balle nouvelle, objet textile/chaussette, couffin vide, couffin avec chien, objet indéterminé, photo de personne affichée sur TV. Le couffin « appartenant au chien », la douceur d'un tissu et la capacité à saisir une chaussette sont **des hypothèses**, non observables directement par une image unique. Chien présent → pas d'approche/contact pour une expérience ; une réponse Qwen contraire est rejetée par la politique locale.

## 4. Mémoire : compacte, explicable, corrigible

Réutiliser la **même** `ExperienceMemory` (F4-A/B, EX1–4) et, si nécessaire après évaluation, M1-B comme **unique** voie d'écriture de signatures ; pas de deuxième SQLite, pas de double écriture M1-A/M1-B. Les empreintes M1-A/M1-B existantes de 64 octets (image) et 16 octets (audio) sont des **indices grossiers d'apparence**, pas une preuve d'identité, une catégorie ni un substitut à la perception. Les embeddings neuronaux et leur coût embarqué ne sont pas encore validés.

Politique cible :
1. **RAM courte durée** : images/sons analysés en mémoire transitoire ; aucune archive continue.
2. **Épisodes utiles seulement** : observation sourcée, catégorie `unknown` possible, contexte minimal, intention, exécution distincte du simple accusé OEM, effet/indéterminé, correction et timestamp.
3. **Connaissance généralisable** : propriétés, relations, usages/affordances et conséquences contextualisées (ex. « certains objets sphériques roulent »), séparant `qwen_unverified`, `locally_observed`, `causal_evidence` et `retracted`. Pas de promotion automatique d'une réponse Qwen ni de deux empreintes similaires en identité.
4. **Consolidation prudente** : doublons rapprochés, agrégats de tendances et indices de provenance conservés, affaiblissement/expiration des hypothèses non confirmées, corrections non effacées, conservation sélective de connaissances utiles. Tests de récupération après redémarrage, saturation, WAL, panne électrique et préservation des preuves.
5. **Budgets mesurés** : les 14 jours / 256 souvenirs F4-A et autres quotas sont des **paramètres de prototype**, ni réglages définitifs ni estimation de place libre. Définir des limites RAM/RSS, taille réelle SQLite + WAL/index, CPU, latence I/O et rétention à partir des relevés sur l'appareil.

**Point de vérité :** Kwipi ne parle pas naturellement le français dans SQLite. Le cerveau local applique un petit vocabulaire structuré de catégories/propriétés/relations/effets. Qwen interprète éventuellement le langage libre sur PC, puis les validateurs produisent des annotations bornées. Les images sont parfois utiles mais ne doivent pas être stockées par défaut.

## 5. Nouveau séquencement : optimiser l'apprentissage, pas le nombre de tests

| Lot prioritaire | Livrable réel et réutilisation | Critère de passage / blocage |
| --- | --- | --- |
| **A — alignement OEM** (ce document) | Inventaire à trois niveaux `skill/perception/autonomie` pour `ground_pick`, kicks, idle, audio et capteurs ; aucune modification OEM | Documents alignés, pas de capacité inventée |
| **B — Qwen 9B Advisor v2 sur PC** | Contrat d'hypothèses multimodales versionné, filtrage images, consentement, schéma, transport sûr ; garder F5 v1 intact | Démonstration réelle Ollama 9B avec images **autorisées**, sorties structurées, cas hostiles/indéterminés, performances PC rapportées. En absence du PC : fixtures seulement |
| **C — mémoire utile et stratégie de rappel** | Adaptation de la **même** SQLite pour hypothèses sourcées/relations/affordances, consolidation, corrections et rappel sans Qwen ; réutiliser F4/EX/M1-B | Tests multi-sessions, scénarios tenus à part, croissance SQLite/WAL et absence de double écrivain ; pas d'« apprentissage physique » sans preuve |
| **D — perception de catégories et continuité** | Terminer Cat-A2b #78 avec annotations indépendantes, négatifs, angles bas, TV et `unknown` ; comparer seconde observation si bénéfice mesuré | Rapport honnête confusion/rejet ; ne pas multiplier des campagnes équivalentes sans nouvelle question. **Prérequis pour la perception physique**, parallélisable avec B/C |
| **E — boucle intégrée sans action dangereuse** | Scénario inédit « percevoir → rappeler → hypothèse → intention passive → résultat observable → correction », avec/ sans mémoire et avec/sans PC ; réutiliser MuJoCo X2-C et EX | Démontrer un transfert à une catégorie/scène tenue à part, sans commande motrice inventée ; MuJoCo ne certifie ni NPU ni caméra réelle |
| **F — audit de l'unité physique** | Vérifier version de carte, caméra, montage des partitions, `robotctl policy list`, `media.frame`, ToF/IMU/micro, ressources par `scripts/resource-audit.sh` au repos et sous charge supervisée | RAM libre/RSS total, stockage/WAL, CPU, thermie, fréquence 50 Hz, latences et stop mesurés ; si insuffisance, réduire cadence/scope ou refuser portage |
| **G — actions OEM supervisées** | Première intention vers primitive OEM autorisée **après** sécurité/observation et preuve d'exécution ; contact éventuel avec **objet inerte de test**, pas avec animal/personne | Reçu d'exécution de bout en bout ou évidence indépendante ; `robot.do accepted` ne suffit pas. Validation physique en zone plane et arrêts contrôlés. Ramassage de chaussette **non présumé** |
| **H — autonomie graduelle** | Décisions autonomes locales, expériences sûres et connaissances durables sans PC | Conditions F/G remplies ; navigation libre/anti-escalier, animal mobile, enfants, téléprésence audio et « Hé Kwipi ! » sont **chantiers spécifiques non validés** |

**Arbitrage pratique :** en attendant la disponibilité de Kwipi et des annotations Cat-A2b indépendantes, donner la priorité aux lots **B et C** sur PC, puis **E** pour prouver que la mémoire change effectivement une décision sur un scénario nouveau. Ne pas retarder B/C par de nouveaux tests visuels redondants ; ne pas court-circuiter D/F/G pour déployer des comportements physiques.

## 6. Mesures d'acceptation et interdits

- **Mesurer l'apprentissage** : décisions avec/sans mémoire, généralisation sur scènes nouvelles, corrections, oublis injustifiés, répétitions, fausses causalités et proportion de résultats `indeterminate`.
- **Mesurer Qwen 9B** : schéma valide, coût de chaque conseil, latence p50/p95 sur **PC réel**, hallucinations d'objets, refus corrects, fuite de données, appel utile plutôt que systématique, cas de panne/timeout.
- **Mesurer l'embarqué sur robot** : RSS cumulé et RAM libre, CPU/thermie, taille SQLite réelle + WAL, délais d'acquisition et d'intention, cadence moteur, alimentation et sûreté ; pas de seuil fictif issu d'un runner x86.
- **Interdire** : 9B sur RK3566 comme dépendance, envoi privé non consenti, écriture permanente des images/voix, prétendu « apprentissage neuronal continu » des gestes, actions moteurs directement pilotées par Qwen, récompense d'une intention non exécutée, traitement d'un animal comme objet d'expérience, sûreté conditionnée au LLM.
- **Changements logiciels ultérieurs** : une PR par responsabilité avec audit `réutiliser/adapter/créer`, tests nominaux/négatifs et docs; vérifier statut des PR OEM et licence de tout poids ou média utilisé. Aucun sous-module, firmware, protecteur ou servo changé ici.

**Statut de cette révision : prévu/documenté.** Le choix 9B et les nouveaux jalons ne valent ni intégration, ni test, ni autorisation de déploiement.
