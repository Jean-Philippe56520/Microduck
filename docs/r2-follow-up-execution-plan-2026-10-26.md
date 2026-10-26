# Plan d’exécution après R2-B — reconnaissance et mémoire Microduck

**R2-B+1, point d'étape réel (26/10/2026) :** [PR #60](https://github.com/Jean-Philippe56520/Microduck/pull/60) et [rapport](r2b1-real-audio-results-2026-10-26.md). La provenance ToyADMOS IND décrit des opérations d'une même machine enregistrées séparément, mais pas les dates ou microphones. **Le banc a été réellement exécuté** (34 extraits de 6 machines), avec **0/10 connues reconnues**, **1 fausse fusion entre machines connues**, **5/5 inconnues rejetées** sur TEST. **M1-B n'est pas promue** ; l'échec de rappel exige une autre évaluation audio ultérieure, sans adapter les seuils au TEST. Les 993 tests du code réussissent (1 ignoré) ; R2-B+2 **pas entamé sans nouveau Go**.

**Actualisation R2-B+1 (26/10/2026) :** [PR #59](https://github.com/Jean-Philippe56520/Microduck/pull/59) ajoute une voie locale préparatoire fondée sur [DCASE2020/ToyADMOS IND](r2b1-independent-audio-2026-10-26.md), en conservant l'évaluateur R2-B. Les modèles, la mémoire et le robot sont inchangés. **Aucun échantillon audio physique réel exécuté dans ce lot** ; le taux de reconnaissance reste inconnu et le passage à R2-C n'est pas autorisé. **R2-B+2 ne doit pas commencer sans nouveau go explicite.**

**26 octobre 2026 — plan de travail, pas livraison de nouvelles fonctions.** Ce document détaille l’ordre des prochains lots du [plan opérationnel](plan-action.md). Il repose sur [R2-A](r2a-single-memory-selection-2026-10-26.md), [R2-B](r2b-independent-capture-evaluation-2026-10-26.md), l’[audit rétroactif R1.5](r15-retrospective-reuse-audit-2026-10-26.md) et la règle [« réutiliser avant de créer »](development-reuse-protocol.md).

## 1. Référence et problème à résoudre

- **Acquis visuel, sur PC uniquement :** benchmark ABO CC BY 4.0 sur 72 images issues de 12 séquences d’objets. Sur le **jeu de test réduit**, M1-B obtient **10/16** vues connues rapprochées et MobileNetV2 ImageNet **15/16** ; les deux rejettent **8/8** vues de séquences non inscrites. Ces vues sont **corrélées au sein des séquences** ; elles ne constituent **ni** 16 exemplaires indépendants **ni** une preuve d’identification d’un objet dans une maison. MobileNetV2 produit des **scores de catégories ImageNet**, pas un embedding fiable d’identité.
- **Acquis audio :** M1-B et YAMNet testés sur quelques fichiers publics et transformations artificielles, et un banc local de WAV avec manifeste. **Aucun résultat** sur plusieurs enregistrements physiques indépendants d’une même source de bruit ; aucun modèle audio retenu.
- **Acquis mémoire :** `MultiviewPatternMemory` M1-B est candidat à la **seule écriture de signatures** pour l’expérimentation, en mode `r2a_single_writer=True`. Les extracteurs M1-A restent des références **sans seconde écriture** ; les associations explicites multi-vues actuelles ne certifient que des **fixtures synthétiques**. L’écriture d’une association à un objet physique réel nécessite donc une **revue dédiée du contrat de provenance**, pas un contournement silencieux.
- **Sécurité OEM inchangée :** `robotd` seul moteur ; `mediad` caméra/audio ; `tofd` profondeur. L’ancien cerveau autonome M9 est encore non porté dans la révision de sous-module auditée. Aucun accès aux capteurs réels, locomotion, surveillance permanente, enregistrement privé dans GitHub ni consultation Qwen automatique.

**Ordre obligatoire :** R2-B+1 audio réel → R2-B+2 robustesse visuelle → R2-C décision comparée → R2-D mémoire expérimentale sur vraies prises → M1-C/R4 analyse PC facultative → R3/R5 compatibilité OEM et mesures sur robot (ordre affiné au moment des prérequis). **Une PR ciblée par lot.**

## 2. R2-B+1 — Épreuve audio sur enregistrements physiquement distincts

**But :** tester si un son est retrouvé malgré une nouvelle prise, un changement de volume/distance et des bruits de fond, sans confondre des sources ressemblantes.

- **D’abord chercher un corpus existant** qui documente la licence, la source physique ou événement répétable, et des prises indépendantes ; inspecter les ensembles déjà utilisés par M1-B2. Si sa provenance n’est pas démontrable ou si les droits sont ambigus, **ne pas le présenter comme une preuve**. L’alternative est un petit corpus local enregistré volontairement par un adulte, sans conversations ni voix d’enfants, stocké **uniquement hors dépôt**.
- Pour un **pilote mesurable**, viser **au moins 2 sources connues en validation, 1 inconnue en validation, 2 connues en test et 1 inconnue en test**, conformément au manifeste R2-B, avec **au moins une prise de référence et une nouvelle prise de requête par source connue** ; obtenir ensuite plus de sources et plusieurs sessions avant toute décision robuste. Les labels « même source » doivent désigner clairement **le même objet/bruiteur physique** ou **le même type d’événement** : ce ne sont pas des équivalences interchangeables.
- Convertir les prises autorisées au format du banc existant : **WAV PCM16 mono 16 kHz, 1 seconde**, SHA-256, `source_id`, `session_id`, `take_id`, partition, rôle et base juridique documentée. Séparer les sources physiques entre validation et test ; prévenir fuite de segments d’un même enregistrement ou de variantes modifiées artificiellement.
- **Réutiliser** `r2b_independent_capture_eval`, `_audio_baseline`, `_audio_learned`, `conservative_threshold`, `_metrics` et contrôles SHA, sans refaire les parseurs ni créer une nouvelle mémoire. Comparer M1-B (16 octets) et, seulement si la licence et les poids sont vérifiés, YAMNet ONNX CPU sur PC.
- Relever par **source/session** : vrais rapprochements, faux rattachements entre sources, inconnu correctement rejeté, refus à tort de sons familiers, latence, CPU et pic RSS hôte. Le seuil est fixé **sur validation**, puis gelé avant test ; publier les échecs et les cas ambigus.

**Livrable :** PR dédiée contenant protocole, tests d’échec, mesures réelles **si des enregistrements autorisés et indépendants ont été exécutés**, plus décision « données suffisantes ou non ». **Blocage :** pas de médias valides → banc prêt mais **aucun résultat de reconnaissance audio réelle**, pas de passage automatique à une sélection audio.

## 3. R2-B+2 — Robustesse visuelle et objets semblables

**But :** distinguer un objet familier de plusieurs objets proches, et non seulement deux séquences de plateau tournant.

- **Réutiliser** l’évaluateur ABO, les manifestes PNG et le scoreur R2-B ; choisir plusieurs groupes d’objets ressemblants et davantage d’objets inscrits/inconnus avec provenance et licence. Inclure angles, éclairage, échelle, arrière-plan et **séances de capture réellement séparées lorsqu’elles sont disponibles**. N’appeler « multi-session » que les données qui le démontrent.
- Faire un **pilote sur plus de sources physiques** que les 4 connues + 2 inconnues testées dans ABO. Ne pas optimiser le modèle ni le seuil sur le jeu de test existant : utiliser une nouvelle partition indépendante et conserver la séparation au niveau objet/source.
- Comparer M1-B classique et MobileNetV2 avec **leurs limites propres** ; privilégier le rejet `unknown` aux rapprochements plausibles mais incertains. Donner les effectifs **en nombre d’objets** et **en nombre de vues**, ainsi que les pires confusions sur objets visuellement proches.
- Ne pas ajouter d’emblée un troisième modèle ou un nouvel extracteur : ce choix attend le rapport de R2-C et une justification « l’existant a échoué à tel critère ».

**Livrable :** PR de comparaisons et rapport de généralisation. **Blocage :** seulement des séquences corrélées ou peu d’objets → conclusion limitée à ces séquences, pas d’identification individuelle démontrée.

## 4. R2-C — Analyse comparative et décision d'abstention

**Prérequis :** les deux rapports précédents, **ou** mention explicite et visible des modalités qui restent sans preuve.

**Protocole de décision :** produire un tableau par modalité et **par source** avec rappel des familiers, erreurs de fusion, rejet des inconnus, abstentions et intervalles d’incertitude quand l’effectif le permet. Ajouter coût du descripteur, poids, latence complète incluant prétraitement et recherche, CPU/RSS du processus sur **PC**, et perspectives de stockage SQLite. Conserver les seuils figés ; ne pas calibrer sur le test.

**Principes :** éviter une fausse reconnaissance avant de maximiser le rappel ; un modèle sémantique ne suffit pas à établir « même objet physique ». Si aucune solution ne satisfait le compromis faux rapprochements / rappels / ressources, **retenir `unknown` et ne sélectionner aucun modèle**. La décision peut être **différente en vision et en audio**.

**Livrable :** PR documentaire/analytique avec décision explicite `retenir`, `retester` ou `rejeter` pour chaque modèle **en tant que candidat sur PC** ; aucun modèle réputé « validé sur Microduck ».

## 5. R2-D — Démonstration de mémoire sur PC, sans double stockage

**But :** retrouver un souvenir lors d’une **nouvelle rencontre**, compter les observations et ne conserver que les variantes utiles, sur une seule SQLite.

- **Réutiliser d’abord** `ExperienceMemory`, `MultiviewPatternMemory` et le mode R2-A à écrivain unique. **Ne pas créer une troisième mémoire** ni une nouvelle table sans lacune vérifiée et essai de compatibilité/migration.
- Le contrat courant de regroupement explicitement déclaré n’accepte que des **affirmations de même source synthétique**. Toute preuve réelle d’association d’objets exige **une décision et des tests distincts** de provenance, séparation entre observations vérifiées et hypothèses, correction/révocation et absence de biométrie personnelle. Ne pas forcer `synthetic_same_source_claim` pour des photographies réelles.
- Scénario mesurable : inscrire un objet avec peu d’exemplaires, le revoir sous différentes conditions **à plusieurs sessions**, présenter un semblable différent et une source inconnue ; reprendre le processus avec la **même base**, contrôler nombre de rencontres, groupes, exemplaires, corrections et absence de doublon M1-A.
- Mesurer la taille **réelle** du fichier SQLite et, selon mode de journal, index/WAL/pages, temps de recherche, CPU et RSS. Les petits vecteurs de 16/64 octets **ne déterminent pas** la taille réelle des ressources. Ne pas stocker les photos/sons bruts continuellement.

**Livrable :** une PR de démonstration et mesures sur PC, avec arrêt/retour en arrière si fausses fusions ou croissances anormales. **Aucune intégration au robot**.

## 6. Après R2-D — PC facultatif, constructeur et matériel

- **M1-C / R4 :** retrouver les contrats F5 déjà codés ; ajouter seulement la pièce manquante permettant de **demander volontairement une hypothèse Qwen** pour une nouveauté non résolue. Opt-in, quota, délais, anonymisation ; Qwen n’écrit pas des identités certifiées et ne commande jamais les moteurs. En absence de PC, conserver `unknown` et continuer localement.
- **R3 :** surveiller la livraison réelle du cerveau OEM M9 et ses interfaces, sans dupliquer `IdleHead` ni les services capteurs. Si M9 n’est pas porté, préserver le prototype passif.
- **R5/F7 après réception du robot :** `scripts/resource-audit.sh` sur appareil, RAM libre réelle, stockage persistant libre, RSS, latence du pipeline complet, cadence moteur 50 Hz, thermie et batteries ; **jamais** d’hypothèse de marge RK3566 déduite des runners CI. Avant mouvement, simulation et zone sécurisée sous supervision.

## 7. Règles de pilotage de chaque lot

1. Inspecter l’**état GitHub actuel** et les sous-modules OEM épinglés, puis remplir la mini-matrice **réutiliser / adapter / créer** du [protocole permanent](development-reuse-protocol.md). Les scripts de laboratoire et les modèles d’étude ne deviennent pas des services embarqués par défaut.
2. **Une PR, une responsabilité**, tests positifs/négatifs, refus `unknown`, absence de moteur/PC automatique, contrôle de confidentialité, source, droits et SHA des éventuels modèles.
3. Exécuter la CI, rapporter le **SHA réel**, nombre de tests et mesures authentiques ; distinguer code, tests synthétiques, vraies captures sur PC, simulation MuJoCo et validation physique. Un workflow réussi sans média réel ne prouve aucune reconnaissance.
4. Mettre à jour la documentation opérationnelle sans ajouter un autre « plan directeur ». **Ce document décline le [plan-action.md](plan-action.md), qui reste la seule source de priorités.** Les compteurs historiques dans le README/roadmap correspondent à leur commit et ne sont pas des scores actuels globaux.
5. **Arrêt explicite à chaque fin de lot**, revue des preuves et décision de poursuivre/ajuster/arrêter avant la PR suivante.

### Ordre et statut à date

| Lot | État au 26/10/2026 | Porte pour le suivant |
| --- | --- | --- |
| R2-A, R2-B (socle et premier ABO) | **Fusionnés**, benchmark visuel hôte seulement | Ne pas transformer les résultats ABO en validation d’identité |
| **R2-B+1 — audio indépendant** | **Prévu, premier lot à ouvrir** | Données authentiquement distinctes, droits et mesures ; sinon diagnostic « preuve manquante » |
| R2-B+2 — robustesse visuelle | Prévu | Diversité de sources et négatifs proches, absence de fuite |
| R2-C — comparaison et décision | Prévu | Faux rapprochements, inconnus, coût ressources et décision par modalité |
| R2-D — mémoire sur PC | Prévu | Une seule SQLite, provenance contrôlée, revue des sessions et croissance |
| M1-C/R4, R3, R5/F7 | Prévus et conditionnels | Hors ligne préservé, OEM respecté, mesure physique avant déploiement |

**Première action recommandée :** exécuter **R2-B+1**, sans toucher à M1-B/robotd, et ne lancer R2-B+2 qu’après revue du rapport sonore ou constat documenté d’insuffisance de corpus.
