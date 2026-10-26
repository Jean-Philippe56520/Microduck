# Programme d'expérimentation après R2-B — Mémoire visuelle et acoustique

**Décision du 26 octobre 2026 — plan opérationnel, non exécution de R2-C.**
**Référence principale :** [plan directeur](plan-action.md), [R2-A](r2a-single-memory-selection-2026-10-26.md), [R2-B](r2b-independent-capture-evaluation-2026-10-26.md), [audit rétroactif R1.5](r15-retrospective-reuse-audit-2026-10-26.md) et [protocole réutiliser avant de créer](development-reuse-protocol.md).
Ce document organise uniquement les prochaines preuves manquantes. Les anciens rapports sont conservés, sans nouvelle version concurrente du plan directeur. Une PR par sous-lot, et **arrêt pour décision** après chaque PR.

## Point de départ vérifié — ce qui fonctionne et ce qui manque

- **R2-A fusionné :** voie de mémoire M1-B/SQLite choisie pour les futurs essais ; M1-A n'est plus qu'un témoin analytique. Le garde `r2a_single_writer=True` refuse des lignes M1-A anciennes et certaines réouvertures destructives dans le chemin R2-A, mais n'est **pas** une exclusion globale des autres processus.
- **R2-B fusionné — benchmark hôte réel ABO :** 72 vues originales de **12 séquences de rotation**. Sur seulement 4 séquences connues test (16 vues) et 2 séquences non inscrites (8 vues), M1-B retrouve **10/16** vues connues, MobileNetV2 **15/16** ; les deux refusent **8/8** vues des séquences inconnues. Les observations d'une séquence sont corrélées et les images ne couvrent **ni plusieurs séances indépendantes ni une maison**. Les 1 000 probabilités de classes ImageNet ne constituent **pas** une signature d'identité d'instance.
- **Audio :** le validateur de manifeste WAV 16 kHz/PCM16/1 seconde et le scoreur comparatif M1-B/YAMNet existent ; les tests actuels utilisent surtout des sinusoïdes fictives. **Aucun résultat de vrais sons réenregistrés indépendamment**.
- **Robot :** aucune mesure sur RK3566, RAM libre, stockage utile, thermique, batterie, stabilité mediad/tofd ou latence motrice. Les chiffres d'inférence et de RSS CI sont des chiffres **hôte uniquement**.
- **M1-B ne stocke pas d'empreintes apprises réelles :** ses associations vérifiées par fixtures ne permettent pas de prétendre à une identité physique certifiée, et son format n'accepte pas automatiquement des embeddings 4 Kio. **Ne pas contourner cette garde**.

## Séquence et jalons de décision

| Ordre | Lot / une PR ciblée | Livrable et contrôle de sortie | Statut |
| --- | --- | --- | --- |
| 1 | **R2-B+1 — enregistrements sonores réellement distincts** | Manifeste et sources autorisées revus ; rapport M1-B / YAMNet : rappel, confusions, refus inconnus, bruit, CPU/RSS ; **aucune performance revendiquée sans données réelles** | **Prochaine PR** |
| 2 | **R2-B+2 — vision élargie et négatifs proches** | Plusieurs séances de prises pour un même objet, autres objets similaires, séparations validation/test par objet ; rapport avec taux *par objet* et abstentions | Planifié, après bilan B+1 |
| 3 | **R2-C — arbitrage de reconnaissance et des ressources** | Tableau commun des deux modalités, seuils gelés, risques, taille réelle des vecteurs ; décision *conserver méthode*, *réessayer* ou *étudier un autre descripteur* | Bloqué par preuves B+1/B+2 |
| 4 | **R2-D — mémoire fonctionnelle sur PC** | Démonstration complète observer → reconnaître/unknown → consolider M1-B → réouvrir SQLite → retrouver souvenir ; quota et taille SQLite réelle, aucune double écriture | Bloqué par choix R2-C |
| 5 | **M1-C / R4 — PC Qwen facultatif** | Réutiliser F5 : consultation uniquement lorsque incertain/intéressant **et autorisé**, délai, quota, preuve d'échec réseau et repli autonome ; Qwen renvoie hypothèses, pas ordres moteur | Après contrat mémoire/perception fiable |
| 6 | **R3 — compatibilité du futur cerveau OEM M9** | Réinspecter la version OEM **seulement lorsqu'une API M9 existe** ; aucune duplication de motivation/mouvement | Conditionnel, pas un bloqueur de R2 |
| 7 | **R5 / F7 — validations physiques** | `scripts/resource-audit.sh` sur vrai appareil ; RAM libre, CPU, RSS, espace libre et partitions, chauffe, cadence robotd, batterie, vision, sûreté ; tests supervisés en zone protégée | En attente de réception du robot |

### Lot 1 — R2-B+1 : son réel

**Objet exact :** vérifier si un bruit familier enregistré **à des moments distincts** est reconnu et si un bruit ressemblant mais provenant d'une **autre source** est correctement refusé.

1. **Avant tout nouveau code**, inspecter le lecteur local `r2b_independent_capture_eval.py`, ses `_audio_manifest`, `_read_wav_take`, `_audio_baseline`, `_audio_learned`, la version de YAMNet déjà testée, les licences et les fixtures. Réutiliser ces outils ; **ne pas créer de nouveau pipeline audio**.
2. Construire **un petit pilote non privé** : deux ou trois sources matérielles différentes pour chaque classe de situation lorsque faisable (par exemple plusieurs clochettes, objets mécaniques ou bruits d'impact différents), chacune enregistrée séparément plusieurs fois, avec distances/niveaux/bruit modifiés. Ne pas enregistrer de voix ou de personnes, et ne pas envoyer d'audio du domicile à GitHub.
3. **Respecter le schéma existant** : WAV 16 kHz mono, PCM16, exactement 1 seconde ; noms locaux opaques ; SHA-256, `source_id`, `session_id`, `take_id`, `split` et droits/consentement vérifiés. Les sessions doivent désigner des **prises physiques différentes**, pas des transformations numériques d'un même fichier. Les labels sont revus manuellement ; le manifeste seul ne garantit pas leur vérité.
4. Séparer **validation**, **validation_unknown**, **test_known**, **test_unknown** par source physique : une source d'entraînement/validation ne réapparaît pas dans le test. Les sources inconnues ne doivent jamais être inscrites comme références. Définir le seuil **sur validation seulement**, le figer avant test.
5. Produire un rapport de **rappel des sources connues, mauvaise association entre sources, inconnues acceptées, inconnues correctement rejetées, abstentions, sensibilité au bruit**, répartis par source et séance. Chiffrer poids, taille du descripteur, médiane/p95 d'inférence, CPU et **RSS du processus hôte**. Aucun score n'est inventé ; si les données ne sont pas disponibles ou les droits non confirmés, laisser **« non évalué »**.
6. **Porte d'arrêt :** rapport et tests positifs/négatifs, absence de fuite de sessions et de droits, aucune capture privée dans le dépôt. Une réussite de quelques sons ne suffit **pas** à calibrer une fiabilité domestique.

**Principe d'effort :** commencer avec le pilote minimal autorisé par le validateur (10 prises et sources séparées), puis élargir uniquement si les premières erreurs le justifient. Ce nombre est un **seuil de fonctionnement du protocole**, pas un échantillon statistique suffisant. Si aucun jeu réel sûr et licite n'est disponible, consigner l'absence de résultat et **ne pas débloquer R2-C comme si l'audio était validé**.

### Lot 2 — R2-B+2 : vision hors séance unique

1. Réutiliser le benchmark ABO et son évaluateur de PNG locaux. Conserver ABO comme **baseline reproductible**, et distinguer expressément ses photos de plateau tournant d'une **deuxième séance de prise réelle**.
2. Constituer un pilote avec des objets physiques autorisés, photographiés en au moins **deux séances distinctes** (autre position, arrière-plan, luminosité et angle), avec des objets très ressemblants comme **négatifs difficiles**. Sans accès à un vrai jeu répondant aux droits et labels, déclarer que ce sous-objectif n'est pas encore mesuré.
3. Conserver les groupes physiques exclusivement dans **validation** ou **test**. Pour chaque objet connu, référence et requêtes proviennent de séances différentes ; inclure d'autres objets jamais présentés et si possible deux exemplaires différents visuellement semblables. Ne pas confondre catégorie (« peluche ») et identité d'exemplaire.
4. Rapporter par objet et par prise : association correcte, fausse fusion, abstention et inconnus rejetés. Conserver les scores sans réadapter les seuils à partir des résultats finaux. Examiner les confusions par type (objet similaire, lumière, distance, occultation). Garder les sources et images privées hors GitHub.

**Porte d'arrêt :** le rapport distingue clairement vues d'une même session, sessions réellement différentes, objet physique connu, autre objet semblable et source inconnue. En cas d'ambiguïté de provenance, le résultat ne valide pas la reconnaissance d'instance.

### Lot 3 — R2-C : arbitrage, pas sélection automatique du meilleur chiffre

- Comparer sur des **ensembles suffisamment différents pour évaluer les erreurs** : M1-B (64/16 octets) et MobileNetV2/YAMNet existants, si disponibles, **sans introduire automatiquement un autre modèle**.
- Les décisions portent sur la **mauvaise identification**, l'abstention et la généralisation d'une séance à l'autre, et non seulement le pourcentage de reconnaissances ou une moyenne des vues corrélées.
- Donner le nombre de **sources physiques indépendantes** pour toutes les métriques. Un résultat « 0 erreur » sur quelques sources donne une information limitée et **ne prouve pas un taux d'erreur nul**.
- Consigner **CPU, latences de bout en bout**, RSS hôte, coût exact des signatures, poids ONNX et compatibilité du format. **Aucun budget embarqué définitif** sans mesures du robot.
- Décider, avec preuve : **(a)** méthodes existantes suffisantes pour un pilote prudent, **(b)** données insuffisantes → ajouter des exemples, **(c)** méthode inadéquate → justifier la comparaison d'un modèle *d'instance* léger. Les scores ImageNet ne sont pas des embeddings d'identité certifiés.
- Aucun critère chiffré arbitraire de « succès garanti ». **Bloquer toute reconnaissance affirmative** lorsqu'une fausse fusion critique ou des données trop faibles rendent le seuil incertain. `unknown` est un résultat valide.

### Lot 4 — R2-D : la première démonstration d'une mémoire qui fonctionne

1. **Inspecter avant coder** : `ExperienceMemory`, `MultiviewPatternMemory`, quotas M1-B et garde R2-A. Ne pas créer une autre base ou une seconde voie de signatures. Une modification de format/feature nécessite **version, migration explicite, sauvegarde et tests de compatibilité** ; ne jamais insérer silencieusement 1 000 scores dans les blobs de 64 octets de l'ancienne méthode.
2. Dérouler sur PC avec des données autorisées : observation initiale → entrée compacte → nouvelle vue/prise → proposition de familiarité ou `unknown` → vérification des conséquences → incrément de rencontres → ajout **sélectif** d'exemplaires utiles → fermeture et réouverture de SQLite → reconnaissance/retrait ultérieur.
3. Mesurer : **taille réellement allouée du fichier SQLite, index, pages libres/WAL le cas échéant**, évolution par observation, mémoire RSS, CPU, temps d'association, taux de fausses fusions, retenue/expiration, corruption et récupération, quotas globaux et par objet. Ne pas déduire le stockage total de la seule longueur des empreintes.
4. Ne conserver ni images ni audio bruts sans justification et consentement, ne rien publier de privé, ne pas connecter un capteur constructeur ou un moteur, conserver la correction des souvenirs et les sources d'hypothèses.
5. **Porte d'arrêt :** démonstration reproduite sur PC avec deux séances indépendantes et réouverture de SQLite ; aucune confusion non traitée promue en identité certaine. Sinon maintenir la fonction comme prototype.

## Contraintes transversales à chaque PR

1. **Réutiliser avant de créer** : sources et révisions OEM/Companion inspectées, matrice « composant existant → lacune → changement minimal », sans second pilote, deuxième cerveau, deuxième SQLite ou pipeline d'acquisition ; préserver les licences.
2. **Une PR par jalon**, tests ciblés puis suite générale CI, résultats liés au SHA ; aucune fusion de résultats fictifs et réels. Actualiser `README.md`, `docs/plan-action.md`, `docs/roadmap.md` et l'audit matériel si le statut évolue, sans recopier le rapport dans chaque document.
3. **Vie privée et autorisations** : aucune voix ni photo personnelle, enfant, animal identifié ou secret dans GitHub ; datasets publics ou explicitement autorisés, données de séance et résultats potentiellement sensibles stockés en privé local.
4. **Sécurité** : aucune connexion aux moteurs/robotd, aucune autorisation de sol par vision/ToF, aucune action Qwen automatique, aucun portage de modèle sur RK3566 avant audit matériel. L'absence du PC ne doit pas empêcher l'autonomie locale.
5. **Statuts explicites** : *prévu* ≠ *codé* ≠ *testé sur fixtures* ≠ *testé sur données réelles sur PC* ≠ *simulé* ≠ *validé sur robot*.

**Décision immédiate :** commencer exclusivement **R2-B+1**, en réutilisant le validateur audio existant et en examinant un corpus sûr de prises indépendantes. S'arrêter après ce lot pour choisir entre enrichissement de données, correction ou R2-B+2. **R2-C ne sélectionne pas de modèle sans preuves auditives et visuelles suffisantes.**
