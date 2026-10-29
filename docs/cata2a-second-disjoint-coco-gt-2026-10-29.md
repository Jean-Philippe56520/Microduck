# Cat-A2a-S2 — deuxième cohorte COCO avec boîtes annotées, disjointe du pilote initial

**Porte 0 préenregistrée le 29 octobre 2026 — avant tout résultat sur le nouveau jeu.** Candidat PC-hôte, aucun effet moteur. Ce protocole ne démontre pas une prise à la hauteur du robot.

## Problème et preuve visée

Les 29 JPEG privés pris à hauteur **déclarée** 20–30 cm ont 66 propositions YOLOX mais aucune contre-annotation indépendante des résultats ; les 50 boîtes ajustées V3 et les légendes Cat-A2c ne sont pas une vérité terrain aveugle. Cat-A2b/C3-B réel reste **bloqué** par cette condition. Une base d'évaluation indépendante du modèle existe déjà : l'étude [Cat-A2a COCO 2017 val](../microduck_companion/cata2_bbox_eval.py), 24 photos sous licence CC BY 2.0 déclarée dans les métadonnées, annotations COCO Consortium CC BY 4.0 : 31 TP / 9 FP / 18 FN sur 49 objets à IoU50 ; hauteur caméra **inconnue**.

**Hypothèse testable :** sur 24 **autres** photos portant des boîtes officielles et disjointes par `image_id` des 24 premières, mesurer si le même YOLOX Nano ONNX offre encore des propositions correctes pour `person/cat/dog/chair/sports_ball` tout en refusant des vues **sans annotations de ces cinq classes**. La nouvelle cohorte est définie comme la **suite de l'ordre SHA déjà fixé dans Cat-A2a**, après exclusion des 24 premiers IDs, et ne sera pas choisie après visualisation des scores.

## Revue réutiliser / adapter / créer

- **Réutiliser** le sélecteur sécurisé et l'évaluateur de boîtes [Cat-A2a](../microduck_companion/cata2_bbox_eval.py), les annotations officielles épinglées par SHA-256 et leur droit CC BY 4.0, les photos COCO métadonnées CC BY 2.0 déclarées, les poids Megvii YOLOX Apache-2.0 inchangés, le score 0,25, l'IoU50, les cinq classes, les 4 scènes avec GT par classe et 4 sans GT cible, les tests et le workflow existant. Les droits photographiques individuels ne sont pas certifiés hors métadonnées COCO.
- **Adapter** la fonction de sélection via `excluded_image_ids: frozenset[int]` borné à 25, option `--cohort disjoint_followup` ; sans cette option, la première cohorte et les APIs continuent **identiques**. Garder les deux cohortes d'images **distinctes**, pas une garantie de sites/séances/objets différents.
- **Créer** seulement trois tests supplémentaires de disjonction, exclusion malformée, négatif COCO avec fausse proposition. Réutiliser le workflow Cat-A2a au lieu d'un nouveau collecteur, et les mêmes poids/annotations temporaires.
- **OEM et communauté** : robotd épinglé `microduck@942e58e3` seul moteur 50 Hz, `mediad` seul propriétaire caméra, `duck-detect` mono-classe Microduck RKNN ; RL `microduck_rl@b02fdea4`. Les main amont `microduck@a360b384` et `microduck_rl@bae39f59` diffèrent des pins, **mise à niveau non sollicitée** ; PR #381/#414/#450 ouvertes. QuackNav, microduck-brain, Quacksat, Twin et Smartulf restent des références, aucun import.
- **Ne pas créer** nouveau détecteur/modèle, mémoire SQLite, writer, consentement fictif, Qwen, interface caméra, pilote ou routine motrice.

## Contrôle/témoin, critères de passage ou arrêt

Le pilote Cat-A2a original sur COCO val2017 (24 photos) est le **témoin historique**, pas une paire expérimentale. Les images de suivi proviennent du même corpus mais sont exclues des 24 premières ; le seuil est figé à **0,25** et aucune photo n'est choisie en fonction de ses prédictions.

**Passage purement exploratoire fixé avant résultats** : (1) 24 nouvelles images disjointes par ID + annotations vérifiées ; (2) au moins **un TP IoU50 pour chacune des cinq classes** ; (3) **précision et rappel micro ≥ 50 %** ; (4) au moins **3 des 4 photos sans GT des cinq classes** sans aucune proposition des cinq classes. Si un seul critère échoue, le cas unique n'est pas suffisamment fiable pour guider des choix catégoriels sans incertitude ; **STOP**, ne pas retoucher le seuil sur TEST. Même si la porte passe, elle ouvre seulement la **recherche d'une vraie validation Cat-A2b** avec vues à 100–300 mm et annotations indépendantes ; elle **n'autorise pas** l'intégration F2/Qwen/robot.

## Ce qui n'est pas une preuve

- COCO val2017 n'indique ni hauteur optique à 25 cm, ni deux séances disjointes sur un même objet, ni présence physique d'une personne/chat/chien à proximité du robot.
- L'annotation officielle est une vérité terrain externe à notre modèle, **mais les cinq classes peuvent ne pas être annotées de manière parfaitement exhaustive**. Une image COCO sans GT des cinq classes n'est pas nécessairement une pièce réellement sans ces objets.
- Rien ne démontre que le préentraînement de YOLOX n'a aucun recouvrement avec les photos sélectionnées.
- Ni catégorie, ni empreinte MEM-2B n'autorise une action OEM ; les photos sont téléchargées seulement sur runner opt-in sans archivage Git ou SQLite.
- La comparaison n'est ni une ablation cognitive C3-B avec/sans mémoire/PC, ni une mesure RK3566/Yocto, température, batterie, NPU ou loop 50 Hz.

**Risques et retour arrière :** erreur de catégorie induisant une fausse présence ou une décision dangereuse, licence d'image mal déclarée, provenance sous-spécifiée, téléchargement indisponible. Refuser les empreintes/licences/sources inattendues ; abandonner l'évaluation plutôt que de relabelliser une image ; `--cohort baseline` revient à l'API historique inchangée. Une CI verte ne suffit pas pour conclure ; seul le rapport de boîtes réellement annotées compte.

## Résultats réels et décision (29 octobre 2026)

**Exécution publique vérifiée :** [COCO-bbox #40898003424](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40898003424), sous PR #175 ; suite [Python #40898003451](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40898003451) **réussie** (1 775 tests, **6 ignorés**, dont le test NumPy hors dépendances facultatives) ; [N1 #40898003388](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40898003388) **réussie**. Le test du bornage flottant **a réellement tourné et réussi dans le workflow COCO** qui installe NumPy (17 tests ciblés). Tous ces chiffres concernent un runner PC, pas RK3566.

**Cohorte et témoin réels** : sélection de 24 nouvelles images CC BY 2.0 déclarée à partir du même COCO val2017 sous annotations COCO CC BY 4.0 épinglées ; **0 image_id commun** avec les 24 premières. Le pilote d'origine relancé dans le même workflow donne toujours **31 TP / 9 FP / 18 FN** pour **49** instances (macro AP50 0,485555). Le second jeu a **70 instances** annotées, pas les mêmes scènes/images : ce n'est ni une paire contrôlée ni une démonstration d'amélioration du modèle. Le ratio de négatifs se rapporte seulement aux **4 images sans GT des cinq classes**.

| Mesure indépendante du score du détecteur, IoU50 | Second lot COCO |
| --- | ---: |
| Images nouvelles / partage d'IDs avec la première cohorte | **24 / 0** |
| Boîtes GT des cinq classes | **70** |
| Propositions YOLOX à seuil fixe 0,25 | **50** |
| TP / FP / FN | **38 / 12 / 32** |
| Précision / rappel micro | **0,760 / 0,542857** |
| Macro AP50 (5 classes présentes) | **0,542611** |
| Sans GT cible : sans proposition / avec proposition | **4/4 / 0/4** |

**Par classe (TP / GT) :** personne **23/30 (76,7 %)**, chat **3/4 (75 %)**, chien **7/7 (100 %)**, chaise **4/24 (16,7 %)**, balle sportive **1/5 (20 %)**. Ces effectifs dépendent de leur présence dans les 24 images et **ne sont pas des performances par espèce ou objet en conditions réelles de Kwipi**. Le nombre de faux positifs total 12 comprend les images avec GT cible ; aucun n'a été rapporté dans les quatre images sans GT cible.

**Porte exploratoire : franchie** (24 image_id différents, les cinq classes ont au moins un TP, précision/rappel micro ≥50 %, 4/4 négatifs annotés sans détection). Ce passage ne transforme pas YOLOX en classifieur sûr : en particulier **les faibles rappels chaise et balle ne permettent pas de guider un comportement sans refus unknown**. Aucune précision validée sur scènes basses du foyer ; zéro vérité terrain nouvelle sur les 29 clichés privés ; aucune preuve C3-B, continuité d'objet, identification/présence physique, mouvement autonome ou robot.

**Défaut constaté et corrigé avant mesure réussie :** la première exécution de la nouvelle cohorte a échoué avec `invalid detector results or bbox coordinates` : multiplication flottante après le clipping sur la grille 416 peut dépasser la largeur entière d'un ULP (`416*(417/416) > 417`). Une seconde borne `np.clip(..., 0, width/height)` après reprojection corrige ce cas **sans toucher score, NMS, poids, seuil ou COCO**. Un test régressif sur format 417×32 passe avec NumPy dans le workflow. L'ancien premier échantillon produit exactement ses comptes historiques.

**Mesure hôte du second lot (non robot)** : inférence ONNX médiane **24,180 ms**, p95 **26,582 ms** sur 24 images ; pic RSS **192 732 Kio du processus hôte**, comprenant bibliothèque/ONNX/Python ; aucun budget énergétique, thermique ou deadline `robotd` de RK3566 mesuré.

**Décision et retour arrière :** arrêter la répétition des petites évaluations COCO et maintenir les seuils/poids fixes. La condition véritable pour Cat-A2b reste la **contre-annotation indépendante** et la **hauteur du centre optique vérifiée** sur photos consenties et scènes disjointes ; C3-B nécessite ensuite des décisions réelles avec/sans mémoire sur le **même test tenu à part**, pas de simples sorties YOLOX. Faute de telles données, le lot perceptif est **en attente** : pivoter vers un axe indépendant (objectifs/détermination/abstention sur fixtures) plutôt que fabriquer de nouvelles annotations, modèles ou outils. La nouvelle option est facultative : `--cohort baseline` conserve l'étude d'origine, aucune migration.

