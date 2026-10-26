# PD0 — 16 comportements, personnalité cohérente et consultations Qwen contextuelles

**Date : 27 octobre 2026. Statut : PLAN D'INTÉGRATION UNIQUEMENT.** Aucun nouveau mouvement, modèle, état actif, consultation Qwen, micro/caméra, appel réseau ni apprentissage causal n'est livré par ce document. Microduck physique absent : **aucune validation embarquée**. Le [plan directeur](plan-action.md) fait foi ; **Cat-A2b, la perception sur vraies prises réellement basses, conserve sa priorité**. PD0 prépare les lots logiciels sans promettre le portage des 16 états.

## 1. Finalité et vocabulaire

**Ne pas confondre :**
- **Motivations** : cinq variables existantes F2 (`curiosity`, `sociability`, `play`, `energy`, `caution`) qui évoluent selon les événements autorisés, le rythme et les souvenirs. `energy` est actuellement une variable **simulée**, pas la batterie mesurée.
- **Tonalité affective simulée** : huit qualificatifs descriptifs P-A (`quiet`, `calm`, `curious`, `attentive`, `playful`, `sociable`, `resting`, `watchful`). Ce ne sont ni une conscience ni des émotions ressenties.
- **Comportement** : un des seize **noms historiques de l'OEM** ; certains peuvent décrire une intention actuelle, très peu correspondent à une fonctionnalité effectivement disponible dans le `robotd` épinglé.
- **Expression** : mouvement, posture, bec ou son réellement fourni par une primitive/animation **OEM vérifiée**, pas le simple libellé d'un état.
- **Demande à Qwen** : besoin **sémantique lié à une observation et à une incertitude persistante**, jamais synonyme d'humeur, de réaction émotionnelle, d'ordre d'action ou d'obligation de connexion au PC.

**Principe :** un seul arbitre F2, un portrait P-A/P-B **après** choix, et plus tard un adaptateur qui propose à `robotd` uniquement des primitives OEM autorisées. **Aucun second cerveau, ordonnanceur moteur, démon audio, magasin SQLite ou boucle parallèle à 50 Hz.** Kwipi peut ne rien faire, observer ou se reposer ; un refus de Qwen ne doit pas engendrer des tentatives répétées.

## 2. Vérification et décision réutiliser / adapter / créer

| Vérifié le 27/10/2026 | Décision |
| --- | --- |
| [OEM épinglé `942e58e3`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567), [idées de portage autonome](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md), `robotd/src/idle_head.rs`, `robotd/src/main.rs` | **Réutiliser** le regard/respiration/bâillement idle et le son `coo` déclenché par caresse OEM ; inventorier chaque autre geste réellement disponible avant usage. Le document OEM explique que la machine historique 16 états n'est **pas encore portée** dans le démon. Ne pas la déclarer livrée. |
| [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) cerveau et [#414](https://github.com/pollen-robotics/microduck/pull/414) maploc/mapd | **Veille** : ouvertes et non fusionnées à la vérification. #381 est une **proposition documentaire**, #414 n'autorise ni navigation ni anti-escalier dans notre révision épinglée. Recontrôler à chaque chantier physique. |
| [F2 `AutonomyBrain`](../microduck_companion/autonomy.py), rythme et [`ExperienceMemory`](../microduck_companion/episodic_memory.py) | **Réutiliser et adapter** l'arbitre unique et la mémoire actuelle ; ne pas introduire une seconde mémoire des humeurs. Préférences persistantes/conséquences sont aujourd'hui uniquement fictives. |
| [P-A catalogue 16](../microduck_companion/behavior_personality.py), [P-B continuité](kwipi-personality-continuity-pb-2026-10-26.md), [P-C expressions](../microduck_companion/oem_expression_hints.py) | **Réutiliser** l'API `BehaviorPortrait` après F2/F4 : seulement quatre états **descriptifs fictifs** (`Chill`, `LookAround`, `Nap`, `BallPlay`). P-C donne `Petted` comme effet déjà détenu par OEM, `Startle` seulement hypothèse sur bruit fictif. Aucune preuve d'exécution depuis Companion. |
| [EX1](ex1-mock-experience-ledger-2026-10-26.md) → [EX2](ex2-mock-effects-kwipi-journal-2026-10-26.md) → [EX3](ex3-reversible-mock-attention-2026-10-26.md) | **Lire sans recopier** les preuves et corrections dans **la même SQLite**. EX3 ajuste un intérêt passif sur des répétitions temporelles **fictives**, pas des actions causées. Pas d'apprentissage social positif/négatif réel sans provenance. |
| [F5-A contrat PC](../microduck_companion/pc_hypothesis_contract.py), [F5-B Ollama](../microduck_companion/ollama_local_client.py), [F5-C quotas](../microduck_companion/selective_pc_policy.py), F5-D adversarial | **Réutiliser sans détourner** : décisions locales d'abord, réponse Qwen non vérifiée, worker facultatif, quotas, consentement et retour hors ligne. Les requêtes actuelles n'emportent **aucun média** et le prompt Ollama de laboratoire force une **réponse `unknown`** ; pas d'identification réelle d'objets. |
| [Registre C3](community-reference-registry-2026-10-26.md) : Quacksat, QuackNav/microduck-brain, GC-RENCAO/Smartulf123, microduck-twin, quack-control, lab/studio | **Comparer sans intégrer** : ni API OEM identique, ni preuve de modèle, licence des poids/médias, sûreté ou RAM sur notre robot. Pas de copier-coller d'un autre cerveau, d'un assistant donnant des commandes, ou d'un système audio concurrent. |

**Créations envisagées, par PR ciblée seulement :** (a) une matrice typée des états `supported/descriptive/planned/unavailable` adossée à P-A, sans second sélecteur ; (b) une fonction **pure** de détection d'opportunité sémantique `should_ask_qwen`, qui prépare un *candidat* pour F5 mais **ne réserve ni ne transmet** elle-même ; (c) ultérieurement un adaptateur OEM après audit de l'API. Ne pas créer de nouveaux contrôleurs, caméras, SQLite ou mémoire émotionnelle.

## 3. Les seize états : signification, expression et opportunité Qwen

**Les états ne déclenchent jamais automatiquement Qwen.** `possible` veut dire « un **fait d'observation indépendant**, pertinent et incertain *pendant ce comportement* peut proposer une consultation F5 ».

| État OEM historique | Intention / contexte local | Statut OEM / Companion actuel | Qwen candidat ? |
| --- | --- | --- | --- |
| **Chill** | Détente, calme, observation facultative | P-A décrit `idle`, OEM anime les gestes idle | **Non** ; économiser énergie et réseau |
| **LookAround** | Curiosité, regarder ou écouter | P-A décrit ; OEM idle_head bouge la tête mais **ne cible pas** réellement un objet | **Oui**, nouvel objet inconnu/contradictoire *après* essais locaux |
| **Wander** | Explorer des lieux nouveaux | Historique non porté, navigation et sol non validés | **Conditionnel plus tard**, observation inconnue durant une pause sûre ; aucune destination Qwen |
| **TurnInPlace** | Chercher un angle supplémentaire | Historique non porté ; ne pas commander de rotation | **Conditionnel plus tard**, ambiguïté persistante après multi-vues déjà validées |
| **Zoomies** | Activité ludique brève | Historique non porté, pas d'enveloppe de vitesse vérifiée | **Non** ; éviter boucle bavarde ou impulsive |
| **Startle** | Réaction brève à un signal inattendu | P-C bruit = **hypothèse** ; OEM journalise les bruits sans lancer Startle autonome | **Pas sur le sursaut** ; **éventuellement plus tard**, bruit inhabituel répété, identifié comme non privé et sans danger immédiat |
| **Stretch** | Étirement éventuel après repos | Animation/mécanique à auditer | **Non** |
| **Ruffle** | Petit geste expressif | Animation à auditer | **Non** |
| **Preen** | Toilette / soin de soi | Animation à auditer | **Non** |
| **Sneeze** | Micro-expression sonore/gestuelle | Animation/son à auditer | **Non** |
| **Dance** | Jeu rythmique / sociabilité | OEM musique/gestes potentiels à inventorier ; état autonome non porté | **Non** ; jamais analyser la musique/voix par défaut |
| **GroundPick** | Examiner un objet au sol | Contact/préhension non validés ; pas de primitive de saisie présumée | **Oui**, question sur catégorie/usage *avant tout contact*, sans transformer la réponse en permission |
| **Nap** | Repos, économie de sollicitations | P-A décrit `rest` ; OEM idle peut s'assoupir, pas preuve de sommeil/économie matérielle | **Non** ; aucune sollicitation PC |
| **BallPlay** | Jeu, intérêt pour objet mobile | P-A décrit un `play_cue`, **aucun kick/jeu physique exécuté** | **Parfois**, objet de jeu **inconnu** ou effet contredisant des attentes après observation ; jamais Qwen pour chaque balle familière |
| **Petted** | Retour à une caresse détectée | OEM peut jouer `coo` si conditions remplies ; P-C l'indique sans l'émettre | **Non** ; pas de transfert d'interactions personnelles |
| **Held** | Réaction à une prise en main | Détecteur historique de soulèvement déprécié, pas d'événement fiable livré pour EX | **Non** ; stabilité et sécurité d'abord |

**Bilan initial :** trois circonstances prioritaires pour étudier un candidat Qwen (`LookAround`, `GroundPick`, `BallPlay`) ; deux potentielles plus tard (`Wander`, `TurnInPlace`), un cas sonore très conditionnel **après** `Startle`. Les autres n'ont aucun intérêt sémantique à eux seuls. Les quinze autres états ne doivent pas être « forcés » pour remplir un catalogue ; le numéro 16 n'est pas une cible de fréquence.

## 4. Politique contextuelle de consultation Qwen, sans humeur déclenchante

La décision locale produit un **besoin d'information**, non une directive « la curiosité est à 80 %, donc interroger Qwen ». Schéma de priorité :

1. **Observation locale autorisée :** catégorie `unknown`, contradiction entre observations indépendantes, nouvel effet non expliqué ou hypothèse sémantique à confirmer. Le capteur et sa provenance doivent être valides ; une étiquette seule ne certifie pas l'existence de l'objet.
2. **Essayer de comprendre localement :** relire la catégorie, des propriétés génériques et les souvenirs `ExperienceMemory` ; tenter une autre observation **passive autorisée** et temporisée, sans imposer de mouvement non vérifié. Ne pas répéter si rien n'a changé.
3. **Intérêt informationnel :** nouveauté significative ou incertitude persistante, pertinence pour curiosité/jeu/exploration, attente de gain d'information supérieur au coût batterie/temps/ressources et au risque pour la confidentialité. Les motivations **pondèrent la priorité**, elles ne forcent jamais une requête.
4. **Vérifier l'état global :** ne pas solliciter le PC si `Nap`, `Chill`, chute, `Held` incertain, `Startle` actif, STOP, mouvement critique, capteur périmé, attention insuffisante ou activité déjà engagée. Si doute, **aucune requête**.
5. **Vérifier un consentement préalable borné** à la session pour le transfert éventuellement utile, réseau local authentifié/chiffré, pas de données personnelles, voix ou images d'enfants, ni identité d'animaux/personnes. Aucun appel externe sans autorisation. Préférer **métadonnées anonymes** ; une image serait une extension distincte, opt-in explicite et sans stockage continu.
6. **Passer par F5-C, sans deuxième quota :** quotas de laboratoire actuels 60 s entre demandes, 2/600 s, 8/24 h, une requête simultanée, backoff après échecs ; *ne pas inventer* une vitesse de service sur robot. Le même `SelectivePCPolicy` décide et réserve de façon atomique. Échec du PC, refus ou temps expiré ⇒ retour local immédiat, pas de commande moteur et pas de nouvelle tentative compulsive.
7. **Réponse Qwen = hypothèse, jamais preuve :** garder type, source `pc_qwen_unverified`, date et expiration. Vérifier par nouveaux indices locaux ; pas de conversion directe en identité, objet sûr, engagement social, causalité, sol praticable ou permission `robotd`.

**Limitation actuelle substantielle :** F5-A/B n'envoient ni photographies ni caractéristiques discriminantes ; leur prompt de laboratoire impose `unknown`. Il ne faut donc pas annoncer « Kwipi consulte Qwen et sait ce qu'est la trottinette ». Pour aboutir à une **identification multimodale**, il faudra un contrat distinct, revue des droits/consentements, évaluation hors ligne sur vraies scènes, limites de taille/latence, puis essai PC **4B avant 9B** sans extrapolation GPU/NPU. L'analyse du contenu ne doit pas devenir une décision motrice. À défaut de média autorisé, mieux vaut **ne pas envoyer** une requête qui ne peut apporter d'information nouvelle.

## 5. Boucle émotionnelle et comportementale envisagée

```text
Perception locale (source, heure, confiance, "unknown" autorisé)
            |
Souvenirs et conséquences OBSERVÉS (pas intentions non exécutées)
            |
5 motivations, fatigue simulée, prudence, nouveauté, rythme F2
            |
Intention unique : agir plus tard / regarder / écouter / repos / inaction
            |
Portrait P-A/B + candidat parmi les 16 noms historiques
            |                         \
            |                          besoin sémantique persistant ?
            |                              | oui
            |                           F5-C (consentement, quota, PC dispo)
            |                              |
            |                         Qwen (avis non vérifié, hors moteur)
            |
Adapter OEM autorisé plus tard (si primitive réellement disponible)
            |
Accusé d'exécution → conséquence constatée → EX1/2/3 réels futurs
            |
Correction / préférence lentement recalculée, mêmes données SQLite
```

- Un seul contrôleur moteur `robotd`, interruption prioritaire, sans blocage de sa boucle 50 Hz.
- Ne pas créer une transition arbitraire `Chill → Dance → Startle` à chaque cycle : utiliser **durée minimale, inertie, cooldown, préemption du danger, fluctuations faibles** ; conserver la possibilité de rester neutre ou immobile.
- Aucune `emotion.sqlite`, table duplicate `MoodMemory` ou échantillonnage multimédia permanent. Les souvenirs doivent distinguer observation, hypothèse PC, simulation, action exécutée et correction. Les traits se renforcent lentement sur **des répétitions corroborées**.
- P-A/P-B décrit actuellement quatre comportements sur **fixtures**. Le document ne suppose aucune exécution robot, ni de persistance attestée des cinq motivations après redémarrage. La continuité des motivations reste une question de conception distincte si elle se révèle nécessaire.

## 6. Priorités et livrables proposés : une PR par responsabilité

| Lot | Type | Livrable à réaliser | Critères de sortie |
| --- | --- | --- | --- |
| **PD0 (ce document)** | Plan | Matrice de 16 états, limites OEM, politique de demande Qwen, scénario des portes techniques | **Documentation seule**, pas de capacité ni de dépense embarquée |
| **PD1 — contrat des expressions (PC/fixtures)** | Code | Étendre **P-A**, sans seconde machine d'états, par catalogue des capacités vérifiées, motifs, indisponibilités, garde de source et contexte ; tester `Chill`/regard/`Petted` sans doubler OEM | Tous les 16 classés honnêtement `descriptive/available/pending/unsupported`, zéro moteur, zéro son, zéro Qwen |
| **PD2 — continuité des motivations et humeur (PC/fixtures)** | Code | Adapter **F2/P-B** : inertie, interruptions légitimes, repos, répétition, rétractions et motivations au long de scénarios, sans nouvelle SQLite | Comparaison avec/sans historique ; changements graduels, pas de sursaut ou mouvement aléatoire ; stabilité et corrections |
| **PD3 — opportunité de consultation PC (PC/fixtures)** | Code | Une fonction pure de besoin informationnel entre perception/mémoire et **F5 existant**, candidates `LookAround`/`GroundPick`/`BallPlay` selon contexte, non état seul | Zéro demande pour `Nap/Chill/Startle` immédiat, données privées, connu ou ambigu non pertinent ; refus d'entrée périmée ; compatibilité F5-C quota/backoff ; déduplication ; aucune commande moteur |
| **PD4 — hypothèses multimodales facultatives (PC réel autorisé)** | Code + banc | **Étendre explicitement F5** seulement après justification de la nécessité des images ; protocole privé et éphémère, schema court, versionnage, correction, simulation de réseau ; comparaison Qwen 4B puis 9B | Mesurer qualité de `unknown`, fausses propositions, latence, confidentialité, quotas et PC absent ; jamais écrire une identité comme fait |
| **PD5 — catalogue OEM et simulation** | Code + simulation | Vérifier `robotd` version épinglée, PR #381, états historiques, gestes réellement commandables (idle, regard, voix, autres si supportés), protections ; liaison de seules intentions autorisées | Simulation `microduck_rl` séparée, limites, timeout, STOP, absence de deuxième décideur moteur. Le simulateur ne prouve ni capteur NPU ni force réelle |
| **PD6 — audit et validation robot** | Mesures | `scripts/resource-audit.sh` au repos/vision/son, audit eMMC/RSS/température, commandes OEM sous supervision, catalogue état→expression réellement jouée | Compte rendu **sur robot physique** ; pas de marche, contact, animaux ou enfants en autonomie avant preuve de sol et sûreté |
| **PD7 — cohérence long terme** | Évaluation | Journal de Kwipi : source d'observation, motivation, portrait, état demandé, capacité OEM, mouvement *confirmé ou refusé*, éventuel motif d'appel Qwen, conséquence et correction | Comparer décisions avec/sans mémoire, répétitions, taux d'abstention, faux appels PC, transitions d'états, ressources ; n'archiver ni voix ni images en continu |

**Ordonnancement :** Cat-A2b (prises réelles basses) reste **le prochain jalon de perception**. PD1–PD3 peuvent être construits sur fixtures **sans déclarer les seize animations opérationnelles** et sans déployer Qwen ; PD4 ne sert que si la perception/les droits et la sécurité du PC sont prêts. PD5–PD7 dépendent des mesures constructeur, de la simulation puis du robot physique.

## 7. Scénarios de validation indispensables

| Scénario | Résultat exigé |
| --- | --- |
| Trois objets déjà connus, état `LookAround` | Observation locale, **zéro requête Qwen automatique** |
| Objet vraiment inconnu sous deux points de vue indépendants, curiosité haute, consentement préalable et PC disponible | **Candidat** F5 selon quota ; réponse non vérifiée ; pas d'ordre moteur |
| Objet inconnu, mais aucun indice discriminant transmissible via le contrat F5 actuel | **Abstention** plutôt qu'un appel inutile qui renverrait `unknown` |
| `BallPlay` et balle connue ou invitation sociale | Jeu décrit, **zéro Qwen** sans question sémantique |
| `GroundPick` et objet inconnu | Hypothèse d'usage possible, **aucune autorisation de ramasser** |
| Bruit bref, `Startle`, danger ou STOP | **Aucun Qwen immédiat** ; inaction/STOP local ; bruit de son propre moteur filtré |
| Bruit anormal répété, hors parole, correctement sourcé | **Éventuel candidat ultérieur**, seulement si classifieur fiable, consentement et pertinence |
| `Petted`, `Held`, enfant, voix ou identité personnelle | Pas d'envoi automatique de média ou de souvenir social au PC |
| Qwen répond `safe_floor=true`, `kick`, `recognize_Malo`, ou un plan moteur | Ignorer/refuser, conserver l'intention locale et les barrières OEM |
| Quota dépassé, PC éteint, réseau coupé, horloge incohérente | Aucun appel, retour local sans blocage ni file infinie |
| Contradiction de souvenirs, épisode EX2 rétracté | Réduire la priorité cognitive, ne pas conserver de récompense artificielle |
| Redémarrage du robot et 1 Go RAM / 32 Go nominaux | État connu et provenance seulement après mesures **réelles** ; aucune consommation ni persistance présumée |

**Indicateurs :** transitions par heure, durée moyenne par état, répétitions évitées, intentions effectivement suivies d'une expression OEM et refus, appels F5/24 h, appels inutiles, `unknown` correctement conservé, débit/quota, latence PC/absence PC, taux d'erreurs de catégorie, taille SQLite/WAL, RSS, CPU, température, retards `robotd`, arrêts. Aucun seuil matériel n'est affirmé dans PD0.

## 8. Décisions hors périmètre

- Pas de machine autonome complète à 16 animations tant que les primitives OEM ne sont pas **réellement livrées et mesurées** ; ne pas créer de faux état actif pour atteindre `16/16`.
- Pas de `mood-triggered Qwen` généralisé ; la **situation, l'incertitude et le besoin d'information** déterminent les candidats.
- Pas de Qwen exécutant `Wander`, `GroundPick`, `BallPlay` ou déduisant un sol sûr ; il peut décrire des usages **à confirmer**, pas autoriser l'action.
- Pas de deuxième conducteur des moteurs, démon audio, capture micro, stockage de conversations, photos d'enfants, empreintes identitaires ni telemetry continue.
- Pas de prétention d'intégration embarquée, d'autonomie domestique, de reconnaissance de « Hé Kwipi ! », d'émotions véritables ou de budget RAM/thermique validé.

**Étape de code conseillée après le plan :** PD1, audit de disponibilité état→primitive OEM, puis PD3 pour les opportunités de Qwen non motrices ; PD2 reste utile pour la cohérence émotionnelle, mais ne doit pas retarder la preuve Cat-A2b. Recontrôler les PR OEM et le registre au moment de chaque implementation.
