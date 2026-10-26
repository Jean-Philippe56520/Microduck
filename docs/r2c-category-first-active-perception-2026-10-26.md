# R2-C — Clôture de l'identification d'instances et pivot vers la perception par catégories

**Suite autorisée et exécutée, Cat-A pilote :** [résultats réels de catégories](cata-category-detection-pilot-2026-10-26.md) et [PR #63](https://github.com/Jean-Philippe56520/Microduck/pull/63). Le nouveau détecteur hôte ne reconnaît correctement que **4/6** images CC0 TEST entières et **3/6** moitiés inférieures ; sur 12 chaises, **8/12** entières, **0/12** recadrées. Le recadrage est une occultation artificielle, **pas une vue à 25 cm**, donc cet essai n'autorise ni déploiement ni mouvement et ne modifie pas la décision d'arrêter les identités d'instances. Prochaine étude Cat-A2 à autoriser ; Cat-B/C/D restent prévues.


**26 octobre 2026 — décision d'architecture validée par l'utilisateur, analyse rétrospective documentaire et prototype de suggestion `inspect` sur fixtures.**

**Statut :** résultats précédents relus ; **aucun modèle d'identité sélectionné**, aucune nouvelle inférence réelle relancée pour cette décision. Le [prototype de vérification des indices partiels](../microduck_companion/category_inspection.py) est uniquement une proposition cognitive sur **données fictives**, sans caméra, regard physique, réseau Qwen ou écriture mémoire.

## 1. Comparaison des preuves existantes (R2-C)

Les prérequis sont [R2-B+1 audio réel](r2b1-real-audio-results-2026-10-26.md), [R2-B+2 objets ressemblants](r2b2-confusable-objects-2026-10-26.md), [R2-B initial](r2b-independent-capture-evaluation-2026-10-26.md), [plan initial R2](r2-follow-up-execution-plan-2026-10-26.md) et [protocole de réutilisation](development-reuse-protocol.md).

| Problème d'**identité de source** (pas de catégorie) | Test tenu à part | Reconnaissance correcte d'une source connue | Faux rapprochements | Inconnus rejetés | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| M1-B audio, empreinte 16 octets | 2 machines connues × 5 nouvelles opérations ToyConveyor | **0/10** | **1/10** vers une autre source connue | **5/5** | **Ne pas retenir** en reconnaissance fiable de même objet sonore |
| M1-B visuel, empreinte 64 octets | 12 objets catalogue « CHAIR », 4 vues interrogées × 12 | **10/48** | **2/24** vues d'inconnus prises pour des connus | **22/24** | **Ne pas retenir** pour l'identité d'instance |
| MobileNetV2 ImageNet, 1000 scores de classes | mêmes 12 objets « CHAIR » et 4 vues interrogées × 12 | **4/48** | **0/24** vus dans ce petit test | **24/24** | **Ne pas retenir** pour l'identité d'instance ; scores de **classes**, pas embeddings individuels |
| YAMNet ONNX audio | pas de nouvel essai sur les prises ToyADMOS réelles | **Non mesuré** | **Non mesuré** | **Non mesuré** | **Non évalué** sur ce nouveau protocole : ne rien conclure sur sa généralisation |

Les seuils **0,968137** (audio M1-B), **0,876838** (vision M1-B) et **0,999730** (MobileNetV2) ont été fixés uniquement à partir de données de validation. Ils proviennent d'espaces de scores différents : **ne pas les comparer directement, ni les réajuster à partir des jeux de test**. Les faibles effectifs ne permettent pas de conclure à un taux d'erreur intrinsèque nul.

**Les vues d'une séquence ABO restent corrélées** ; plusieurs `item_id` ne prouvent pas plusieurs objets physiques authentifiés. Les opérations ToyADMOS sont distinctes mais leurs dates et microphones ne sont pas établis. Il manque la preuve de fiabilité d'une identité sous scènes naturelles, distances, éclairages, sons et matériels différents.

**Ressources mesurées sur PC, non comparables au RK3566 :** vision MobileNetV2 sur hôte Linux, **médiane ONNX 8,959 ms / pic RSS processus 143 224 Kio** sur 180 vues, durée 56,452 s incluant téléchargement ; audio M1-B sur hôte, **0,124 s de traitement hors collecte / pic RSS processus 52 700 Kio** pour 34 segments. Ces chiffres ne mesurent pas un pipeline complet RKNN, le stockage effectif SQLite, l'autonomie énergétique ni la température du robot.

**Décision R2-C :** **mettre en pause l'identification des exemplaires et des personnes**, sans supprimer M1-A/M1-B ni leurs résultats de recherche. Garder les essais publiés en historique ; ils ne deviennent pas des modèles embarqués ni des critères de vérification d'une identité. **Le refus `unknown` est obligatoire** lorsque la catégorie elle-même n'est pas établie.

## 2. Objectif prioritaire validé : catégories et perception active

Kwipi, environ 25 cm, verra parfois une **partie** d'objet ou de corps plutôt qu'un objet entier. L'objectif est une boucle **observer → hypothèses de catégories → rechercher un indice de continuité utile → observer à nouveau, si sûr → classer ou rester inconnu → intention/expérience → apprentissage progressif**.

**Catégories prioritaires futures :** `person`, `cat`, `dog`, `chair`, `shoe`, `ball`, avec `unknown` et `other_object`. `hand`, `forearm`, `foot`, `leg`, `paw`, `fur`, `furniture_leg`, `seat` ou `round_edge` sont des **indices partiels**, pas des catégories de personnes identifiées. Les chaussettes/chaussures isolées ne prouvent pas qu'un humain est présent. Une patte ou des poils ne prouvent pas « chat » plutôt que « chien ». Deux indices ne décrivent pas automatiquement **le même** objet ; il faut une continuité spatiale/visuelle supplémentaire.

**Classification de catégorie ≠ identité d'instance ≠ biométrie.** Aucun nom d'humain, de Malo, Kitty ou Nessquick, ni archive de visage, voix ou trace personnelle dans les expériences publiées. Une catégorie peut devenir un souvenir si un détecteur local fiable et une provenance sensorielle authentifiée le justifient ; une hypothèse de Qwen demeure une hypothèse et ne devient pas une vérité mémorisée sans observation indépendante.

## 3. Réutiliser / adapter / créer avant portage

| Fonction | Existe déjà ; à conserver | Adaptation minimale envisagée et limite |
| --- | --- | --- |
| Observations de catégories | `PerceptionEvent`, `summarize_passive`, provenance/fraîcheur/threshold F1, `PassiveRead` ; catégories `person/cat/dog/ball` déjà prévues en fixtures | Pour `chair/shoe`, **ne pas** changer les catégories de capteur en prétendant qu'un détecteur existe. Étudier un détecteur **réel de catégories**, ses classes, son rejet de l'inconnu et les licences avant adaptation F1 |
| Choix d'attention | `AutonomyBrain.propose_passive`, `PassiveIntent(inspect)`, `PassiveRhythm`, repos et cooldowns F2 | [`category_inspection.py`](../microduck_companion/category_inspection.py) reçoit **une intention F2 déjà produite**, des indices fictifs allowlistés ; suggère le *type d'indice* utile à rechercher, **jamais** un angle de tête ni une commande |
| Regard et capteurs | OEM épinglé `mediad`, `tofd`, `IdleHead`, cinématique caméra | `IdleHead` regarde spontanément, **ne suit aucune cible observée** ; tout suivi/mouvement futur doit passer par une interface officielle auditée et `robotd`. Ni second moteur ni changement des protections |
| Mémoire locale et apprentissage | `ExperienceMemory`, journal F1-C, F2-C, mémoire F4-A/F4-B, signature M1-B expérimentale, voie R2-A unique | Garder **une seule SQLite**, les sources, dates, corrections, rétentions, quotas et conséquences réellement constatées ; ne pas apprendre une identité d'un rapprochement ambigu, ni archiver médias en continu |
| Hypothèses PC | Contrats F5, `SelectivePCPolicy`, Ollama/Qwen facultatif | Après observations locales épuisées, un **candidat de revue** sans aucune requête ; passage éventuel au vrai F5 avec opt-in, quota, timeout, réseau privé et contenus anonymisés. Les indices concernant une personne ne déclenchent **aucun transfert** via ce prototype |
| Détection et calcul | OEM NPU/RKNN pour **autres Microducks** ; banc hôte MobileNetV2, modèles F3-A/D ; tierces études Smartulf/GC | **Comparer avant d'intégrer** les détecteurs génériques de catégories existants, en séparant classification d'image entière, détection localisée et estimation de pose partielle. Une sortie de classes ImageNet n'est pas un détecteur de main/pied. Les catégories `shoe` et parties ne sont pas toutes garanties par COCO standard |

**Pas de nouvelle table SQLite, modèle, service d'acquisition ou LLM embarqué créé** dans cette décision. Le prototype de proposition est déconnecté des commandes physiques. Les projets communautaires demeurent dans le [registre C3](community-reference-registry-2026-10-26.md) ; aucune dépendance tierce intégrée.

## 4. Prototype de vérification : preuves et interdits

Le seul nouveau composant logiciel de ce lot est une **fonction pure et opt-in de suggestion** : `suggest_category_inspection`. Elle exige une intention F2 `inspect` issue de la voie actuelle (le type seul n'authentifie pas son origine), des indices `mock` bornés et frais, et un compteur d'observations. Exemples :

- `hand` → hypothèse non vérifiée `person`, rechercher `forearm`, **pas** un humain identifié ;
- `shoe` → `shoe`, rechercher `sole` ; **ne conclut pas** à un humain ;
- `furniture_leg` → `chair`, rechercher `seat`, **pas** une chaise certifiée ;
- `fur` → `cat` **ou** `dog`, rechercher `head_outline` ; un autre indice aide seulement avec preuve de continuité ;
- deux parties incompatibles déclarées liées → **rester `unknown`** ;
- après **2 suggestions autorisées** : rester `unknown`, ou signaler « revue PC envisageable » pour une catégorie non personnelle avec accord, sans **aucune** requête réelle. L'ancien gate F5 reste seul compétent pour un éventuel appel.

**Ce prototype n'a ni coordonnées, ni suivi, ni image, ni authentification de caméra :** il ne bouge pas la tête, ne déplace pas le robot, ne lit pas un capteur, ne crée pas une identité, n'écrit aucun souvenir et n'envoie rien à Qwen. Les associations d'indices sont des exemples **fictifs**, pas des règles physiques validées. Les catégories suggérées ne sont **jamais des observations confirmées**.

## 5. Ordre révisé des prochains chantiers (aucun portage automatique)

1. **Cognition catégorie-first (lot actuel)** : clore R2-C par l'analyse ci-dessus, coder/tester une *suggestion* limitée de perception active sur fixtures sans moteurs, et figer la séparation faits/hypothèses.
2. **F3 / Cat-A — banc de reconnaissance de catégories sur PC, séparé** : identifier les modèles et données publiques autorisées, catégories `person/cat/dog/chair/ball` puis `shoe` si couverture prouvée ; photographies à différents cadrages, notamment caméra basse et objets partiels. Mesurer matrice de confusion, rejets/erreurs sur inconnus, précision, coût complet, mémoire, robustesse vues proches. Vérifier explicitement les licences poids/données et les classes supportées. **Pas de module de détection déclaré livré** avant tests.
3. **Cat-B — seconde observation / continuité réelle** : après le classifieur, évaluer si une deuxième image améliore réellement les catégories sur des paires de prises distinctes et **liées par preuve de continuité**, en conservant des cas négatifs. Les indices de main/pied sont optionnels et nécessitent des jeux dédiés ; pas de reconnaissance faciale.
4. **Cat-C / mémoire** : adapter **une seule** `ExperienceMemory` pour les catégories/souvenirs/résultats corrigibles ; conserver les signatures M1-B en laboratoire tant qu'elles ne sont pas fiables. R2-D (ancien objectif d'identité mono-écrivain) est **suspendu/reformulé**, sans migration SQLite automatique.
5. **Cat-D / Qwen facultatif** : après épuisement des indices locaux et seulement avec consentement, comparer le bénéfice d'hypothèses non confirmées via F5, sans autorité motrice ni apprentissage automatique à partir de texte LLM.
6. **Simulation OEM puis mesures du robot physique** : avant orientation réelle de tête ou mouvement, audit API `robotd`, cinématique, risques, vitesse/zone/sécurité, simulation et `scripts/resource-audit.sh` sur matériel livré ; pas de chiffres ARM extrapolés.

**Décision d'arrêt :** ce lot ne lance ni Cat-A, ni R2-D, ni la connexion caméra réelle/Qwen, ni entraînement ou portage RKNN. Tout nouveau chantier requiert une demande distincte et les mêmes tests indépendants. Maintenir les anciens rapports R2 comme archives scientifiques, pas comme priorités contradictoires.
