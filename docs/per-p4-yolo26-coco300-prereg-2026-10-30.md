# PER-P4 — sélection YOLO par 300 photographies publiques indépendantes du banc précédent (30/10/2026)

**Préenregistrement avant première inférence de ce lot.** Ajustement de disponibilité des sources **avant toute première inférence** : la première CI a échoué **avant toute inférence** car la seule licence Flickr CC BY 2.0 laissait **1 nouveau chat disponible** après exclusion des 132 photos déjà vues. **Révision de provenance sans aucune sortie de modèle consultée :** la sélection reste à **40 par catégorie + 100 témoins**, mais elle accepte les **six licences Flickr Creative Commons 2.0** explicitement déclarées dans COCO et vérifiées par couple nom/URL/ID (BY, BY-SA, BY-ND, BY-NC, BY-NC-SA, BY-NC-ND), uniquement pour ce test **interne non commercial**, sans republication d'images et sans constituer un jeu de données d'entraînement. Les droits individuels ne sont pas revalidés et les conditions NC/ND interdisent certains usages ultérieurs. Tous les seuils de modèle et les exclusions restent inchangés. Le point de comparaison est `main@1e8d83d155a7ee19b03cc2fe188469ab4d429272`. Les sous-modules OEM sont immuables. Ce lot ne modifie ni les modèles embarqués ni `mediad`, `robotd`, `duck-detect`, `ExperienceMemory` et Qwen.

## Question et manque

L'objectif est de choisir un candidat de **perception visuelle utile** et non d'obtenir une reconnaissance parfaite des fauteuils. Les précédents bancs (Cat-A/vis-att2 : 132 images COCO val2017, PER-S0/S1A : peu de scènes MuJoCo basses, PER-P3A/B : cinq scènes / treize photos publiques) sont trop petits pour extrapoler la qualité sur la variété d'environnements. L'échec d'un fauteuil isolé ne doit pas éliminer un modèle compétent sur les personnes, animaux, balles et régions inconnues. La séparation détection visuelle / sécurité ToF est obligatoire : voir un obstacle sur photo n'est pas une garantie de navigation.

## Comparaison bornée, qualité avant intégration

- **Trois candidats de même échelle nano** : `yolo11n.pt` (témoin), `yolo26n.pt` (détection) et `yolo26n-seg.pt` (détection + masques), exécutés par la **bibliothèque officielle Ultralytics sans copie de l'inférence ni retouche de poids**. Version exacte de bibliothèque fixée à ultralytics==8.4.192 par le workflow ; poids chargés depuis le fournisseur officiel, empreinte SHA256 et version effectives consignées avant toute analyse.
- **300 photographies distinctes** de COCO val2017 : 40 par catégorie cible (`person`, `cat`, `dog`, `sports_ball`, `chair`) plus 100 autres photos **sans annotation de ces cinq classes**, mais pas nécessairement des pièces vides ; photographies aux licences Flickr Creative Commons 2.0 reconnues (IDs 1–6), métadonnées COCO non auditées image par image, annotation globale CC BY 4.0. Sources JPEG officielles, vérifiées en mémoire, supprimées après essai ; aucun JPEG, masque ou poids archivé/poussé.
- **Exclure les 132 IDs** des huit cohortes déjà publiées à l'aide du sélecteur `eighth_disjoint` et de l'annotation COCO exacte SHA256 vérifiée ; graine de sélection fixe `per-p4-300-20261030` ; une photo ne peut figurer qu'une fois. Différentes photos ≠ différentes scènes physiques ; hauteur optique et recul non connus.
- **Comparabilité** : même JPEG, même résolution d'entrée `imgsz=640`, `conf=0.25`, `iou=0.50`, CPU hôte, `max_det=100`, ordre de classes identique, zéro ajustement après observation ; une exécution par photo et modèle. Les masques COCO ne sont **pas** fournis à la prédiction, uniquement au score.
- **Résultats** : rappel d'instance avec **bonne classe** et IoU boîte ≥0,50 ; rappel de région **quelle que soit la classe** et IoU ≥0,50 ; ventilation par cinq catégories, personne/chat/chien/balle regroupés en **priorité cognitive** et chaise secondaire ; nombres de prédictions des cinq classes dans les 100 témoins sans annotations cibles (diagnostic, **non** faux positifs certains) ; pour `yolo26n-seg`, IoU des masques versus masques d'instance COCO indépendants et versus le rectangle prédit ; coût hôte médian/p95, RSS.
- **Fuites et refus** : image invalide, provenance COCO non authentifiée, licence absente ou non conforme au nom et à l'URL attendus, 132 anciens IDs, GT manquante, modèle ou bibliothèque incompatible → arrêt franc ; pas de score inventé ni substitution synthétique.

## Critères fixés avant essai

Cette étude est **un classement relatif**, pas une porte éliminatoire fondée sur le fauteuil seul.

1. Pour être recommandé à un essai complémentaire bas/caméra, un candidat doit présenter un rappel de **régions** sur l'ensemble des instances `person/cat/dog/sports_ball` ≥ 0,75 avec IoU50 ; une faiblesse documentée sur chaise ne bloque pas ce passage.
2. La meilleure option doit être comparée au témoin YOLO11n avec la **même cohorte** et les mêmes réglages. Si le rappel prioritaire est à moins de 0,05 du meilleur détecteur, préférer provisoirement `-seg` **seulement si** ses masques battent le rectangle sur **≥ 60 %** des instances effectivement appariées et mesurables. Sinon préférer la détection plus simple.
3. Même si l'étude passe, **aucune adoption ni promesse de 2 Hz sur RK3566** avant essais bas MuJoCo inédits, licences du code ET des poids acceptables, adaptation OEM à plusieurs sorties, mesure RAM/latence/RSS/thermique et validation robot supervisée. Toutes les observations restent PC/public.

**Tests positifs et négatifs logiciels** : 300 IDs uniques ; photo déjà examinée refusée ; licences erronées refusées ; rappel catégorie vs région dissocié sur une prédiction volontairement mal nommée ; appariement une cible ↔ une prédiction ; aucun GT sur témoin = zéro cible annotée, jamais « salle vide » ; un masque mauvais ne doit jamais gagner par inadvertance.

**Décision** : `progres_demontre_PC_public` si les trois analyses sur 300 vraies photos sont terminées avec provenance et scores ; `insuffisant` si les portes ci-dessus échouent ; `bloque_source_externe` si la récupération licite et vérifiable est impossible. Une CI logicielle verte ne constitue jamais une performance de détection. Pas de changement de modèles OEM, SQLite, permis moteur ou sous-module sans accord.

**Licence** : le code et les poids Ultralytics sont soumis aux conditions AGPL-3.0 / Enterprise et **ne sont évalués qu'à titre exploratoire sur hôte**. Ne pas redistribuer les poids ou intégrer ces modèles dans un produit sans examen approprié des droits. La licence de l'exemple Rockchip ne remplace pas ces obligations.


## Résultat POST-ESSAI, jamais utilisé pour définir les seuils — 30/10/2026

**Preuve effective :** [CI PER-P4 #41085096403](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41085096403) **verte** sur le commit `289a951edfd3e6c9ff5052275f2821d0643eab0c`. [CI Python #41085096349](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41085096349) verte sur le même SHA. **300 photos publiques COCO val2017 distinctes et inédites parmi les 132 IDs déjà vus ; 40 photos ciblées par catégorie + 100 contrôles sans annotation des cinq catégories ; 900 prédictions de modèles réellement effectuées sur CPU hôte.** Les cinq catégories totalisent **704 instances annotées** (personnes 421, chats 44, chiens 51, balles 57, chaises 131) ; 573 instances prioritaires hors chaises. Ces 300 JPEG sont distincts, mais leur indépendance physique et leur hauteur de caméra ne sont pas prouvées. Les droits individuels Flickr ne sont pas vérifiés en dehors des six métadonnées CC enregistrées. Aucune image privée ni poids publiés.

| Mesure (COCO hôte, même échantillon ; IoU boîte ≥0,50) | YOLO11n | YOLO26n | YOLO26n-seg |
| --- | ---: | ---: | ---: |
| Rappel de régions sans exiger bonne étiquette, 573 instances prioritaires | 0,7435 | 0,7435 | **0,7522** |
| Rappel avec catégorie correcte, 573 prioritaires | 0,7277 | 0,7295 | **0,7365** |
| Personne, rappel de région (421 instances) | 319/421 | 312/421 | 318/421 |
| Chat, rappel de région (44) | 35/44 | 37/44 | 36/44 |
| Chien, rappel de région (51) | 47/51 | 47/51 | 48/51 |
| Balle, rappel de région (57) | 25/57 | **30/57** | 29/57 |
| Chaise, rappel de région (131), non éliminatoire | 61/131 | **62/131** | 56/131 |
| Images témoins sans annotation cible | 100 | 100 | 100 |
| Prédictions portant l'une des 5 étiquettes sur ces témoins (diagnostic, pas FP prouvés) | 5 | 5 | 3 |
| Masque et rectangle comparés sur les propositions réelles | — | — | **487 instances** |
| IoU moyen masque / rectangle sur ces 487 instances | — | — | **0,7976 / 0,5119** |
| Fraction d'instances où masque > rectangle, parmi les 487 appariées | — | — | **98,36 %** |
| Médiane CPU hôte sur exécution verte #41085096403 | 48,09 ms | 44,24 ms | 68,05 ms |
| p95 CPU hôte sur exécution verte #41085096403 | 61,82 ms | 55,59 ms | 87,72 ms |
| Pic RSS de processus hôte (modèles successifs / mémoire cumulative) | 692 672 KiB | 703 040 KiB | 780 556 KiB |

**Interprétation sans extrapolation :** seul **YOLO26n-seg franchit** le rappel de régions prioritaires **≥0,75** préenregistré, de peu (0,7522). Il franchit le critère de masques **≥60 %** très largement (98,36 %), sur les **objets qu'il a déjà localisés** : une segmentation fine ne compense pas les objets jamais proposés. **Sélection : YOLO26n-seg comme candidat unique pour un nouveau banc de scènes basses OEM**, pas adoption de ses poids ou déploiement. Gain de rappel modeste versus YOLO26n/YOLO11n (0,87 point) mais important gain géométrique conditionnel ; YOLO26n seul est un **témoin léger/plus rapide** et récupère une balle de plus sur cette cohorte. Les 5 000 images de COCO val2017 ne sont PAS évaluées ; il ne s'agit pas d'un mAP COCO officiel ni d'une détection d'objet sans catégorie prouvée.

Les durées hôte varient entre exécutions du **même** jeu public : une exécution précédente sur le même script a donné 24,77 / 22,98 / 35,30 ms de médiane respectivement, la CI finale 48,09 / 44,24 / 68,05 ms. Aucune durée ni RSS ci-dessus ne démontre les 2 Hz du RK3566, le coût NPU, la latence du capteur, le respect de `robotd` 50 Hz ou les contraintes de 1 Go embarqué.

**Prochaine étape, sans ajouter d'infrastructure ni réentraîner :** comparer `yolo26n-seg` à son rectangle sur de nouvelles scènes MuJoCo **à hauteur basse**, positives et négatives (balle, chaussure/chaussette, animal/humain simulé, objet inconnu, écran/photo, occultation), vérités terrain indépendantes et validation de la propriété « physique » séparée des pixels. Avant toute adaptation constructeur : statut exact de licence AGPL des poids, format multi-sorties et ABI RKNN RK3566, conditions d'OEM `mediad/duck-detect`, CPU/RSS/thermique et intégrité du contrôle 50 Hz. Ne pas connecter automatiquement `ExperienceMemory` ni Qwen à une classe ou région incertaine. **Aucune action motrice ni sous-module OEM modifiés.**

## Résultat exécuté — après gel des seuils (CI GitHub 30/10/2026)

**Preuve réelle :** [GitHub Actions PER-P4 #41085096403](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41085096403) **réussie** avec 300 photos distinctes, 900 inférences PyTorch hôte sur 3 poids officiels vérifiés et rapport JSON numérique en artifact. [Suite Python du même SHA #41085096349](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41085096349) **réussie**. Les essais précédents (#41084965202, #41084897847) ont réellement produit les 900 inférences et les mêmes valeurs de précision, mais leur CI avait échoué **après inférence** sur une assertion de répartition `20+200` obsolète, alors que le préenregistrement et l'exécution retenue sont `40×5 + 100`. Le correctif a uniquement rétabli cette cohérence, **sans ajuster les poids, les seuils ou les scores**. Un ancien échec en amont était dû à trop peu d'images de chats admissibles en CC BY seul ; l'élargissement aux six licences CC 2.0 déclarées a précédé toute inférence du lot.

**Préparation figée :** COCO val2017, 40 photos par groupe person/cat/dog/sports_ball/chair plus 100 images sans ces cinq annotations, 132 anciens IDs exclus, licence individuelle selon métadonnées COCO seulement, même image pour les trois modèles, `imgsz=640`, `conf=0.25`, `iou=0.50`, `max_det=100`, GT indépendantes pour IoU boîte et masque ; aucune photo, poids, identité, média privé, Qwen, SQLite ou moteur publié/modifié.

| Modèle | Rappel région, toutes étiquettes, sur 573 instances prioritaires | Rappel bonne catégorie, mêmes 573 | p50 CPU PyTorch GitHub (ms) | p95 (ms) | Photos témoins et prédictions des 5 catégories |
| --- | ---: | ---: | ---: | ---: | ---: |
| YOLO11n | 74,35 % | 72,77 % | 48,09 | 61,82 | 100 ; 5 propositions |
| YOLO26n | 74,35 % | 72,95 % | 44,24 | 55,59 | 100 ; 5 propositions |
| **YOLO26n-seg** | **75,22 %** | **73,65 %** | 68,05 | 87,72 | 100 ; 3 propositions |

Temps issus **uniquement du run final réussi**, dépendants du partage du runner GitHub et des accès CPU ; lors d'une autre exécution réelle la médiane allait de 22,98 à 35,30 ms selon les modèles. Ce **n'est ni une mesure ONNX/RKNN ni une prédiction de coût robot**, et le pic RSS hôte 692 672 / 703 040 / 780 556 KiB comprend Python/PyTorch et ne se transpose pas au RK3566.

| Cible (instances GT) | YOLO11n rappel catégorie / région | YOLO26n catégorie / région | YOLO26n-seg catégorie / région |
| --- | ---: | ---: | ---: |
| Humain (421) | 318/421 · 319/421 | 312/421 · 312/421 | 317/421 · 318/421 |
| Chat (44) | 35/44 · 35/44 | 37/44 · 37/44 | 36/44 · 36/44 |
| Chien (51) | 39/51 · 47/51 | 40/51 · 47/51 | 41/51 · 48/51 |
| Balle (57) | 25/57 · 25/57 | 29/57 · 30/57 | 28/57 · 29/57 |
| Chaise (131) | 57/131 · 61/131 | 59/131 · 62/131 | 54/131 · 56/131 |

**Silhouettes, YOLO26n-seg :** 487 appariements spatiaux IoU≥0,50 où un masque était disponible, IoU moyenne de masque prédite/GT **0,7976**, IoU du *même rectangle prédit rempli* contre GT **0,5119**, masque meilleur sur **98,36 %** des instances appariées. Il s'agit de caractéristiques de **régions correctement retrouvées** et non d'un rappel de régions inconnues : aucun masque ne compense un objet totalement absent des propositions. Une mauvaise catégorie peut aider spatialement, mais ne devient jamais une signification certaine ou une justification d'action.

**Décision préenregistrée et limites :** la porte de rappel prioritaire `≥0,75` est franchie *seulement* par YOLO26n-seg (`0,7522`), soit un gain de **5 instances sur 573** comparé aux deux autres, trop faible pour déclarer une supériorité de détection généralisable. Le groupement pondéré est dominé par 421 humains ; la balle est encore localisée environ une fois sur deux et le fauteuil/chaises moins d'une fois sur deux. La porte masque 60 % est dépassée mais ne démontre pas une nouvelle détection d'objet totalement inconnu, ni la couleur/texture/mémoire ou distinction TV/réel. **YOLO26n-seg mérite un essai complémentaire à faible hauteur pour la silhouette**, YOLO26n reste un témoin plus léger pour détection, **aucun modèle validé pour Microduck**. Les 300 photos ne documentent pas l'angle bas robot, la diversité de *lieux physiques distincts*, ni les risques d'impact/chute. Le ToF frontal, la navigation et la sûreté 50 Hz restent des fonctions OEM séparées et non testées ici.

**Droits et arrêt :** les 6 variantes CC déclarées ne sont pas un droit commercial général ; NC/ND et droits des poids Ultralytics AGPL-3.0/Enterprise doivent être examinés avant diffusion, training ou intégration commerciale. Le modèle `mediad/duck-detect` OEM épinglé ne décode toujours qu'une classe et pas de masque. Aucun code robot/poids/SDK/branche OEM, aucune nouvelle caméra, SQLite, Qwen ou permission motrice introduit. Prochain essai seulement sur GT **basse et nouvelle**, balle/chaussette/objets inconnus, négatifs représentation 2D, coût NPU si et quand matériel disponible ; **pas de réglage sur les 300 photos**.
