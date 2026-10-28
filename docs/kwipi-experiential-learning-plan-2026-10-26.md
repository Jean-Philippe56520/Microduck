# Kwipi — plan d'apprentissage autonome par l'expérience (EX)

**C1 — mémoire de sens vs expérience réelle (28/10/2026) :** le rappel agrégé de F4-A à partir de F1-C/F2-C conserve uniquement des observations *mock* historiques et des hypothèses séparées ; **aucun gain causal, aucune connaissance du monde réel et aucun effet autonome**. Une catégorie répétée dans plusieurs sessions de fixture ne constitue pas plusieurs scènes indépendantes. Réutiliser EX1/EX2/EX3 sans changer les états ; EX4-C2 nécessite preuve de fin d'acte OEM et effet observé indépendamment, non satisfaits. [Dossier C1](c1-conservative-category-recall-2026-10-28.md).

**F5 v2 — Qwen 9B sur PC : conseiller, pas lexique ni contrôleur (28/10/2026) :** une scène autorisée peut produire des hypothèses de catégorie, propriétés, relations, conséquences possibles et **observation future pertinente** ; le pilote est manuel, sans souvenir ni moteur. Une sortie réelle a proposé à tort `ground_pick` vers un chat ; aucune proposition Qwen ne doit devenir une commande sans vérification indépendante des êtres vivants, zone/sol, skills chargés et effet observable. **Aucune mémoire causale** avant acte OEM achevé et effet indépendant confirmé. [Rôle](kwipi-qwen9b-role-contract-v2-2026-10-28.md).

**Addendum SIM-E1 du 28/10/2026 :** une première expérimentation motrice **en simulateur OEM uniquement** est codée sur branche dédiée ; elle réutilise l'unique essai J2e déjà borné et l'unique mémoire SQLite, puis compare l'effet de la préférence `simulator/explore` sur une décision F2, avec contrôle sans préférence. **Pas** d'objets ou d'animaux modélisés, ni causalité physique, ni apprentissage de réseau, ni autonomie validée. Voir [SIM-E1](sim-e1-active-experience-2026-10-28.md) ; priorité Cat-A2b et garde EX4-C2 inchangées.

**Date : 26 octobre 2026. Statut : PLAN PROPOSÉ, DOCUMENTATION UNIQUEMENT.**
Aucun modèle, actionneur, service, schéma SQLite ou branchement Qwen n'est livré par ce document. Aucune validation sur le robot physique. Le [plan directeur](plan-action.md) reste l'unique référence pour les priorités et les critères de passage ; **Cat-A2b et la perception par catégories passent avant un déploiement EX**.

## 1. Finalité et principe de liberté

Kwipi est un explorateur curieux, social, peu bavard et capable de ne rien faire. Il **n'exige pas qu'un humain préprogramme chaque objet, animal ou situation**. Il utilise la perception locale, les souvenirs, des motivations stables et, exceptionnellement, des hypothèses Qwen sur un PC autorisé pour décider ce qui mérite attention, puis parfois une expérience physique.

Boucle cible : **percevoir → rappeler → évaluer nouveauté/intérêt/risque → imaginer des effets possibles → choisir une intention → exécuter une primitive OEM autorisée (ou s'abstenir) → mesurer la différence avant/après → estimer le lien causal → enregistrer ou rejeter le résultat → adapter lentement les préférences.**

- **Autonomie locale sans PC :** découvrir, reconnaître des catégories générales, comparer, choisir l'attention, se reposer et utiliser la mémoire ne nécessitent ni Qwen ni réseau.
- **Pas de réaction par objet :** connaissances généralisables sur des propriétés et effets (mobile, léger, roule, ne bouge pas, réaction sociale observée), sans dictionnaire manuel « trottinette = telle action ».
- **Personnalité, pas hasard permanent :** curiosité, sociabilité, jeu, énergie, prudence, nouveauté, mémoire, cadence et repos influencent la sélection ; une expérience isolée n'impose pas une habitude durable.
- **Liberté proportionnée :** pas d'approbation humaine pour chaque observation ou action inoffensive *déjà validée*. Quelques invariants physiques restent indépendants de l'apprentissage : arrêt prioritaire, état du robot, limites des commandes OEM, sol/obstacles, aucune expérimentation par coups sur personnes/animaux.
- **Une hypothèse n'est pas un fait ; une intention n'est pas une action ; une action exécutée n'est pas une conséquence prouvée.** Ce sont trois frontières distinctes.

## 2. Réalité du dépôt au 26 octobre 2026

| Composant | Vérifié / décision EX | Ce qui n'existe pas encore |
| --- | --- | --- |
| OEM épinglé [microduck 942e58e3](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) : robotd, mediad, tofd, pet-detect, IdleHead | **Réutiliser**, ne pas créer de commande motrice, capture ni pilote concurrents. robotd conserve sa boucle à 50 Hz. | Bibliothèque vérifiée de contacts légers avec objets, mesures de force, navigation libre et anti-escalier validés |
| [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) | **Veille** : document de design du cerveau, ouverte/non fusionnée à la revue ; pas une implémentation livrée. Recontrôler avant EX4/EX6. | M9 exécutable sur notre révision OEM |
| [PR OEM #414](https://github.com/pollen-robotics/microduck/pull/414) | **Veille navigation** : maploc v2/mapd ouvert/non fusionné, non importé. Le consulter avant toute navigation, puis QuackNav et microduck-brain. | Certificat de sol sûr / cartographie embarquée validée dans notre système |
| F1/F2 : [perception](../microduck_companion/perception.py), [AutonomyBrain](../microduck_companion/autonomy.py), rythme, apprentissage passif | **Réutiliser/adapter** l'arbitre des cinq motivations et les intentions passives. | Expérience physique autonome et observations caméra authentifiées |
| F4-A / P-B : [mémoire de résultats](../microduck_companion/behavioral_memory.py), [sémantique](../microduck_companion/category_semantics.py), [une SQLite ExperienceMemory](../microduck_companion/episodic_memory.py) | **Adapter** les contrats de provenance et correction, sans second magasin ; le biais actuel est testé uniquement sur résultats fictifs. | Attribution causale et préférences fondées sur de vrais effets |
| [Cat-A2b](cata2b-private-low-camera-protocol-2026-10-26.md) | **Priorité immédiate conservée** : protocole de prises à hauteur basse, sans corpus réel bas livré ni modèle embarqué validé. | Détection fiable en situation réelle, continuité multi-vues, objets inconnus robustement rejetés |
| F5 : contrats [Qwen](f5a-pc-hypotheses-2026-10-26.md), [transport](f5b-ollama-local-transport-2026-10-26.md), [quotas](f5c-sparse-consultations-2026-10-26.md) | **Réutiliser** les contrats et le circuit non bloquant avec opt-in, quota, timeout et repli. | Appels Qwen multimodaux sur scènes réelles, reconnaissance automatique du langage ou autorisation d'envoyer des images |
| Communauté : [registre C3](community-reference-registry-2026-10-26.md), GC-RENCAO/Smartulf123, Quacksat, microduck-twin/lab/studio, quack-control | **Références à auditer par lot** (API, licence, ressources, sûreté), pas des dépendances approuvées. | Preuve indépendante d'intégration sur le robot |

**Décision de réutilisation :** conserver une seule boucle cognitive F2, une seule connexion/base SQLite ExperienceMemory, un seul propriétaire moteur robotd et les capteurs OEM. Créer seulement les contrats et adaptateurs qui manquent. M1-B reste **expérimental pour des signatures d'instances** et ne sert pas de preuve d'identité ; ne pas réactiver les doubles écritures M1-A/M1-B ni bâtir une seconde mémoire d'épisodes.

## 3. Données et souvenirs utiles

La future **trace d'expérience** doit représenter un fait minimal, avec des champs typés, sourcés et bornés :

| Élément | Contenu proposé | Précaution |
| --- | --- | --- |
| Situation et contexte | Catégorie ou `unknown`, propriétés visibles, proximité approximative si autorisée, nouveauté, sources et dates | Pas de nom d'enfant, personne, animal individuel, ni localisation privée précise |
| Intention | Observer, inspecter, jouer, explorer ; objectif et effet attendu, avec identifiant éphémère | Une intention seule ne produit jamais de retour d'apprentissage |
| Exécution | Primitive OEM nommée, accusé et résultat d'exécution robotd, durée bornée, interruptions et arrêt | Un accusé de commande ne garantit pas la réussite du mouvement |
| Résultat | Changements constatés par capteurs après l'action : mouvement de l'objet, immobilité, perte d'équilibre, contact détecté, réaction sociale vérifiée | Absence de mesure = résultat **indéterminé**, pas échec ni succès inventé |
| Attribution | Fenêtre temporelle, continuité de scène, action concurrente, confiance du lien action→effet, contradictions | Succession temporelle seule ≠ causalité |
| Apprentissage | Bilan positif/neutre/négatif/inconnu, contexte et preuves d'origine, correction/rétraction, rétention | Mise à jour faible, réversible et seulement sur événements exécutés et crédibles |

Conserver un **journal borné d'épisodes utiles** et des **résumés de tendances** (types d'actions × contextes génériques × effets). Éviter enregistrements continus audio/vidéo, noms ou biométrie. Les nouveaux contrats doivent exploiter les tables F4-A / la connexion ExperienceMemory, prévoir migration/versionnement explicites si nécessaire, empêcher les doubles écritures et ne pas effacer silencieusement les souvenirs actuels. La limite F4-A actuelle de 14 jours/256 résultats est un **paramètre de prototype**, pas une mémoire durable validée ; dimensionner rétention/quota après mesures du robot, sans déduire la taille SQLite des seules empreintes.

## 4. Comment Kwipi apprend une conséquence

1. **Avant :** description sensorielle de la scène, incertitude, contexte, intention et effet attendu, sans supposer qu'un objet possède les propriétés décrites par Qwen.
2. **Pendant :** une primitive admise par robotd est réellement exécutée, ou l'action est refusée/abandonnée. Un refus ou une intention non exécutée ne produit aucun « essai réussi/raté ».
3. **Après :** mesurer les effets visibles et les éventuels retours sociaux **détectés par une voie autorisée**, en distinguant le son d'une voix de la compréhension de mots.
4. **Lien causal :** utiliser la continuité de l'objet/scène, le délai et l'absence d'actions concurrentes ; garder « cause inconnue » si ambigu, différé ou capteur absent.
5. **Préférence :** mettre à jour lentement une attente située (ex. « pousser doucement les objets légers et sphériques peut les faire rouler »), et non une règle universelle ou une identité individuelle. Réévaluer selon preuves répétées et corrections.
6. **Relecture :** à une découverte ultérieure, la mémoire influence la proposition F2 sans remplacer la prudence, l'inaction ou la priorité robotd.

Le retour humain peut être utile : « bravo », « doucement », « non » ou caresse. **Actuellement pet-detect détecte des caresses et des événements Noise/Voice, pas les mots prononcés.** Une future reconnaissance locale des mots/phrases et de la personne ayant consenti devra être testée séparément ; pas de transcription inventée et pas d'enregistrement permanent. Le signal « stop » fiable et prioritaire demeure hors apprentissage.

**Exemples de fixtures, pas des faits de robot :**

- Balle : poussée **réellement exécutée** → déplacement détecté → « rouler après contact » probable. Une caresse plusieurs secondes plus tard n'est pas automatiquement imputée au geste.
- Chat : plusieurs observations « j'avance / le chat part » et « je reste / il reste » → ajuster la propension à approcher, en restant sur la catégorie `cat` et sans déclarer une émotion ou une identité.
- Humain : une réprimande ou un geste négatif est un retour social possible, mais le robot **ne doit pas donner des coups ni se faire pousser pour apprendre**. Une perte d'équilibre est un événement de stabilité, pas une preuve certaine que l'action l'a causée.
- Trottinette : Qwen propose « objet à roues servant à se déplacer » → hypothèse ; observation ultérieure du roulement → propriété corroborée, sans présumer qu'un contact moteur est possible ou sûr.

## 5. Affordances générales, sans programmation par objet

Introduire seulement après tests un **vocabulaire compact de propriétés/effets transversaux** (mobile/immobile, roule/glisse, léger/lourd incertain, souple/rigide incertain, mouvement provoqué/absent, interaction sociale favorable/défavorable/inconnue). Ne pas prétendre estimer poids, fragilité ou force sans capteur/épreuve. La sortie `unknown` reste légitime.

Qwen sur PC peut proposer catégorie, usage probable et expériences **à examiner**, mais uniquement sur consentement et contenu expurgé, après le contrat F5 et sans trafic systématique. Tester d'abord Qwen 4B, puis 9B si la comparaison qualité/latence/ressources est utile sur le PC disponible. Les images ne sont pas transmises par le pipeline F5 existant : il faudrait une extension multimodale explicite, revue sur confidentialité. **Ni Qwen ni sa description ne produisent une action OEM ou un fait certifié.** Hors PC, la boucle continue avec observation et mémoire locale.

## 6. Contrôle moteur proportionné

**Ne pas demander une permission à l'utilisateur pour chaque petite expérience**, après validation d'une classe de mouvements et de son enveloppe d'emploi. En revanche, l'IA ne peut inventer une primitive ni changer une limite matérielle. Séparer :

- **Primitives cognitives immédiatement testables sur PC** : observer, inspecter, écouter, ne rien faire, proposer une hypothèse, relire un souvenir.
- **Primitives physiques à inventorier dans l'OEM réellement épinglé** : orientation du regard, pas/rotation et éventuelle interaction ballon. Les états historiques OEM `BallPlay`, `GroundPick`, `Wander` et les 16 comportements documentés **ne prouvent pas que les actions correspondantes sont portées**. Le bec ne devient pas un manipulateur par hypothèse ; éviter de promettre pousser, saisir ou donner un coup de pied avant examen mécanique/API/force.
- **Contact léger avec objet inerte** : candidat futur seulement si une primitive OEM existe, si la force/trajectoire ont été mesurées, sur zone plane connue et objet de test prévu à cette fin. Aucune frappe autonome sur personnes/animaux ; pas de poursuite d'un animal pour obtenir un résultat social.
- **Sécurité permanente** : robotd seul autorise les moteurs et peut interrompre ; capteur critique périmé, sol non établi, chute, batterie ou température hors enveloppe → arrêt/inaction. Le ToF frontal 8×8 n'est pas une validation anti-escalier 360°.

Ces invariants limitent les conséquences graves, **pas la curiosité ni la variété des questions et essais non dangereux**.

## 7. Phases EX proposées, une PR par responsabilité

| Lot | Livrable vérifiable | Critères de sortie et dépendances |
| --- | --- | --- |
| **EX0 — cadrage (ce document)** | Architecture, états de preuve, matrice réutiliser/adapter/créer, jalons et scénarios | Documentation uniquement. Aucune capacité nouvelle déclarée |
| **EX1 — contrat d'épisode et provenance (PC, fixtures)** | Relier F2 intention et F4/ExperienceMemory à des épisodes typés `proposé/exécuté/refusé/interrompu`, sans nouvelle base ni moteur | Tests refus d'origine, horodatage, doublons, redémarrage, corrections, zéro résultat d'une intention non exécutée ; ne pas remplacer Cat-A2b |
| **EX2 — attribution prudente des effets (PC, fixtures)** | Comparateur avant/après, source d'effet, incertitude, statut `indéterminé`, résultats et preuve liés à une exécution | Tests causalité plausible vs simple succession, événement concurrent, retour retardé, observation absente, contradictions ; métriques de fausses attributions |
| **EX3 — apprentissage lent et généralisable (PC, fixtures)** | Résumés par action/contextes génériques, biais bornés, oubli/correction ; branchement optionnel à F2/P-B après arbitrage | Tests multi-sessions/reprise, généralisation sur objets non inscrits, absence de répétition compulsive, aucun résultat issu de Qwen |
| **EX4 — langage, affordances et PC facultatif (PC réel autorisé)** | Hypothèses Qwen sur catégories/usages possibles ; extension multimodale uniquement si justifiée et consentie ; mots sociaux locaux dans un lot séparé | Évaluation 4B puis 9B si utile, taux d'hallucination/abstention, latence, quota, PC absent, refus données personnelles ; pas de commande |
| **EX5 — inventaire de gestes OEM et simulateur** | Catalogue des seules primitives **réellement supportées** (API, état, fin d'action), adaptateur d'intention avec permission robotd | Comparaison OEM épinglé, PR #381 et tiers ; tests stop/timeout/fausses autorisations, simulation MuJoCo sans prétendre valider une caméra/NPU/force réelle |
| **EX6 — validation robot, progression graduelle** | Audit ressources au repos, mémoire/vision réelles, observation immobile, puis gestes et contacts doux sur objets de test sous supervision | `scripts/resource-audit.sh`, capteurs et moteur mesurés, arrêts vérifiés, essais indépendants avec échecs documentés ; aucune extrapolation PC |
| **EX7 — autonomie domestique progressive** | Exploration spontanée à cadence maîtrisée, préférences adaptées par résultats réellement observés, consultations PC rares | Seule après EX6, sol et déplacements validés ; comparer avec/sans mémoire, observer les dérives, supervision renforcée avant tout contexte avec enfants/animaux |

**Prérequis transverse :** la priorité en cours est Cat-A2b (corpus de **vraies** prises basses, droits, vérité terrain indépendante, `unknown`, tests de confusion et de localisation), puis Cat-B continuité, Cat-C mémoire de catégories et Cat-D revue PC quand leurs preuves le permettent. EX1–EX3 peuvent être conçus sur fixtures sans robot, mais **EX4–EX7 ne prétendent pas qu'une perception fiable ou une navigation validée sont acquises**. Le chantier L locomotion reste séparé et non résolu.

### Les trois premières PR d'implémentation EX (après arbitrage avec Cat-A2b)

1. **EX1 : contrat d'épisodes sur fixtures, sans nouveau moteur ni second écrivain.** Tester `intention ≠ exécution`, refus et correction ; vérifier les tables F4 existantes avant toute migration.
2. **EX2 : attribution de conséquences et statut inconnu.** Tester de faux retours positifs et négatifs, et les erreurs de crédit causal ; aucune récompense sans provenance.
3. **EX3 : préférences réversibles et relecture multi-sessions.** Démontrer que l'histoire change réellement une décision F2, de façon faible mais mesurable, sans apprentissage d'une interaction non exécutée.

Chaque PR a ses propres fixtures **fictives**, tests ciblés et de régression, rapport de limites, audit de réutilisation, et seulement ensuite une décision de poursuite. N'enchaîner aucune implantation motrice par effet de bord.

## 8. Matrice minimale de tests

| Cas | Résultat attendu |
| --- | --- |
| Objet nouveau, catégorie incertaine | `unknown`, observation possible ; aucune catégorie forcée |
| Consultation Qwen indisponible ou « trottinette » non vérifiée | Hypothèse refusée ou conservée comme telle ; aucune action commandée |
| Intention de pousser, action non exécutée / refusée | Zéro souvenir de conséquence comportementale |
| Balle déplacée après une exécution réellement traçable | Épisode positif *si* déplacement lié de manière plausible ; sinon `indéterminé` |
| Caresse ou bruit arrivant sans lien certain avec la dernière action | Événement distinct, pas récompense automatique |
| Animal qui part après approche, mais aussi parfois spontanément | Pas de causalité inventée ; tendance seulement après observations comparables répétées |
| Retour verbal non reconnu ou ambigu | Aucun sentiment de récompense inventé ; pas de transcription prétendue |
| Source périmée, redémarrage, horloge incohérente, preuves retirées | Refus/abstention, correction propagée, biais recalculé, pas de double écriture |
| Action contraire à une protection OEM / PC tentant un ordre moteur | Refus, stop et robotd prioritaires, aucune commande autonome |
| Même catégorie sous contexte nouveau ou objet jamais inscrit | Réutilisation prudente des **propriétés** apprises, avec doute ; pas de fausse identité |

## 9. Indicateurs à mesurer, sans seuil inventé

- **Apprentissage :** proportion d'expériences avec exécution effectivement corroborée ; taux de résultats `indéterminé` ; fausses associations effet/action ; correction et persistance après reprise.
- **Adaptation :** comparer décisions **avec et sans relecture mémoire**, sur scénarios tenus à part, sans surapprentissage d'une seule caresse/réprimande ; fréquence de répétition et d'inaction choisie.
- **Perception :** précision/rappel par catégorie et `unknown`, sous angles bas indépendants, fausses fusions et continuité.
- **Autonomie :** pourcentage de cycles hors PC, nombre d'appels Qwen, abstentions, latences et retours après coupure.
- **Embarqué :** RSS/RAM libre, taille physique de la SQLite (WAL/index compris), CPU, température, batterie, interruptions, délai robotd, stabilité et arrêts réels. Les seuils devront être définis à partir des mesures **sur l'unité exacte**, sans importer les chiffres CI PC.

## 10. Décisions de non-réalisation dans EX0

- **Pas** de second cerveau, ordonnanceur, pilote, commande moteur concurrente, deuxième SQLite ou réactivation de l'identité d'instance M1-B.
- **Pas** de captures/audio permanents ni de données de mineur, humain, animal nommé ou identité personnelle dans GitHub.
- **Pas** de perte d'équilibre provoquée volontairement, ni de coup sur un humain/animal pour apprendre une « mauvaise expérience ». Les réactions sociales peuvent être apprises via les retours autorisés, sans reproduire le comportement dangereux.
- **Pas** de Qwen multimodal/ASR déclaré fonctionnel sur robot, de budget matériel supposé, de preuve de locomotion déduite de MuJoCo.
- **Pas** de changement aux sous-modules OEM ni aux protections robotd dans une PR documentaire.

**Prochaine action concrète selon le plan directeur :** recueillir et évaluer des prises de vue *réellement basses*, indépendantes et autorisées (Cat-A2b), tout en gardant EX1 comme **premier lot cognitif futur**, entièrement testable sur PC/fixtures. Réévaluer l'OEM épinglé, #381, #414 et le registre communautaire avant les chantiers d'action.
