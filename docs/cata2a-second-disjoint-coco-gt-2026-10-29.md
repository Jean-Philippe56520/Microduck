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

## Résultats

Non mesurés au dépôt initial ; attendre un run de l'action Cat-A2a avec `disjoint_followup` exécuté sur le vrai dataset public. Ne pas transformer des fixtures en précision/rappel.

