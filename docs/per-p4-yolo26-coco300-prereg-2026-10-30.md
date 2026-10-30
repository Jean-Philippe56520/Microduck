# PER-P4 — sélection YOLO par 300 photographies publiques indépendantes du banc précédent (30/10/2026)

**Préenregistrement avant première inférence de ce lot.** Le point de comparaison est \`main@1e8d83d155a7ee19b03cc2fe188469ab4d429272\`. Les sous-modules OEM sont immuables. Ce lot ne modifie ni les modèles embarqués ni \`mediad\`, \`robotd\`, \`duck-detect\`, \`ExperienceMemory\` et Qwen.

## Question et manque

L'objectif est de choisir un candidat de **perception visuelle utile** et non d'obtenir une reconnaissance parfaite des fauteuils. Les précédents bancs (Cat-A/vis-att2 : 132 images COCO val2017, PER-S0/S1A : peu de scènes MuJoCo basses, PER-P3A/B : cinq scènes / treize photos publiques) sont trop petits pour extrapoler la qualité sur la variété d'environnements. L'échec d'un fauteuil isolé ne doit pas éliminer un modèle compétent sur les personnes, animaux, balles et régions inconnues. La séparation détection visuelle / sécurité ToF est obligatoire : voir un obstacle sur photo n'est pas une garantie de navigation.

## Comparaison bornée, qualité avant intégration

- **Trois candidats de même échelle nano** : \`yolo11n.pt\` (témoin), \`yolo26n.pt\` (détection) et \`yolo26n-seg.pt\` (détection + masques), exécutés par la **bibliothèque officielle Ultralytics sans copie de l'inférence ni retouche de poids**. Version exacte de bibliothèque fixée à ultralytics==8.4.60 par le workflow ; poids chargés depuis le fournisseur officiel, empreinte SHA256 et version effectives consignées avant toute analyse.
- **300 photographies distinctes** de COCO val2017 : 30 par catégorie cible (\`person\`, \`cat\`, \`dog\`, \`sports_ball\`, \`chair\`) plus 150 autres photos **sans annotation de ces cinq classes**, mais pas nécessairement des pièces vides ; photographies déclarées Flickr CC BY 2.0, annotation globale CC BY 4.0. Sources JPEG officielles, vérifiées en mémoire, supprimées après essai ; aucun JPEG, masque ou poids archivé/poussé.
- **Exclure les 132 IDs** des huit cohortes déjà publiées à l'aide du sélecteur \`eighth_disjoint\` et de l'annotation COCO exacte SHA256 vérifiée ; graine de sélection fixe \`per-p4-300-20261030\` ; une photo ne peut figurer qu'une fois. Différentes photos ≠ différentes scènes physiques ; hauteur optique et recul non connus.
- **Comparabilité** : même JPEG, même résolution d'entrée \`imgsz=640\`, \`conf=0.25\`, \`iou=0.50\`, CPU hôte, \`max_det=100\`, ordre de classes identique, zéro ajustement après observation ; une exécution par photo et modèle. Les masques COCO ne sont **pas** fournis à la prédiction, uniquement au score.
- **Résultats** : rappel d'instance avec **bonne classe** et IoU boîte ≥0,50 ; rappel de région **quelle que soit la classe** et IoU ≥0,50 ; ventilation par cinq catégories, personne/chat/chien/balle regroupés en **priorité cognitive** et chaise secondaire ; nombres de prédictions des cinq classes dans les 150 témoins sans annotations cibles (diagnostic, **non** faux positifs certains) ; pour \`yolo26n-seg\`, IoU des masques versus masques d'instance COCO indépendants et versus le rectangle prédit ; coût hôte médian/p95, RSS.
- **Fuites et refus** : image invalide, provenance COCO non authentifiée, licence absente, 132 anciens IDs, GT manquante, modèle ou bibliothèque incompatible → arrêt franc ; pas de score inventé ni substitution synthétique.

## Critères fixés avant essai

Cette étude est **un classement relatif**, pas une porte éliminatoire fondée sur le fauteuil seul.

1. Pour être recommandé à un essai complémentaire bas/caméra, un candidat doit présenter un rappel de **régions** sur l'ensemble des instances \`person/cat/dog/sports_ball\` ≥ 0,75 avec IoU50 ; une faiblesse documentée sur chaise ne bloque pas ce passage.
2. La meilleure option doit être comparée au témoin YOLO11n avec la **même cohorte** et les mêmes réglages. Si le rappel prioritaire est à moins de 0,05 du meilleur détecteur, préférer provisoirement \`-seg\` **seulement si** ses masques battent le rectangle sur **≥ 60 %** des instances effectivement appariées et mesurables. Sinon préférer la détection plus simple.
3. Même si l'étude passe, **aucune adoption ni promesse de 2 Hz sur RK3566** avant essais bas MuJoCo inédits, licences du code ET des poids acceptables, adaptation OEM à plusieurs sorties, mesure RAM/latence/RSS/thermique et validation robot supervisée. Toutes les observations restent PC/public.

**Tests positifs et négatifs logiciels** : 300 IDs uniques ; photo déjà examinée refusée ; licences erronées refusées ; rappel catégorie vs région dissocié sur une prédiction volontairement mal nommée ; appariement une cible ↔ une prédiction ; aucun GT sur témoin = zéro cible annotée, jamais « salle vide » ; un masque mauvais ne doit jamais gagner par inadvertance.

**Décision** : \`progres_demontre_PC_public\` si les trois analyses sur 300 vraies photos sont terminées avec provenance et scores ; \`insuffisant\` si les portes ci-dessus échouent ; \`bloque_source_externe\` si la récupération licite et vérifiable est impossible. Une CI logicielle verte ne constitue jamais une performance de détection. Pas de changement de modèles OEM, SQLite, permis moteur ou sous-module sans accord.

**Licence** : le code et les poids Ultralytics sont soumis aux conditions AGPL-3.0 / Enterprise et **ne sont évalués qu'à titre exploratoire sur hôte**. Ne pas redistribuer les poids ou intégrer ces modèles dans un produit sans examen approprié des droits. La licence de l'exemple Rockchip ne remplace pas ces obligations.
