# PER-P3B — Vérification bornée des catégories et exécution locale privée (30/10/2026)

**Préenregistré avant toute inférence de P3B.** Base `main@72d092f43af20f94ff268f7ae796834152252f6c` ; OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` **inchangés**. Autorités : `docs/plan-action.md`, `docs/development-reuse-protocol.md`, `docs/perception-oem-rknn-2hz-plan-2026-10-29.md`, P3A/#207. Aucun modèle, seuil ou nouveau média entraîné, retouché ou ajouté à GitHub.

## Question et manque prouvé

P3A [CI #41058705033](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41058705033) a identifié 2/2 balles sur des vues OEM simulées mais **0/1 fauteuil** et aucune région inconnue ; **le critère P3A a échoué**. PP-YOLOE-s n'a jamais été testé dans P3A sur chat, chien, humain. Les 13 photos publiques **déjà présentes** dans `tests/assets/public_vision_smoke` contiennent 4 chats, 2 chiens, 1 personne, 1 chaise, 3 balles, 2 scènes sans les cinq classes ciblées. YOLOX-Nano a déjà été évalué sur ces mêmes photos (3/4 chats, 2/2 chiens, 1/1 personne, 1/1 chaise, 0/3 balles, 2/2 négatifs sans cible dans `yolox_baseline_results.json`). **Ces images ne sont ni inédites pour YOLOX, ni des prises à hauteur de Microduck ; PP-YOLOE ne les a pas utilisées pour un ajustement connu de ce projet.**

But du lot : **combler une lacune d'observation restreinte** en exécutant **une fois** les deux détecteurs inchangés sur exactement les mêmes treize octets publiquement indexés. Pas de nouvelle collecte COCO, détection « open world », nouvelle caméra ni décodeur OEM. Par ailleurs permettre aux **deux JPEG privés déjà fournis** d'être diagnostiqués par **le même programme** sur le PC de l'opérateur sans les confier à GitHub. En l'absence de poids ONNX accessibles dans l'environnement local d'assistance, le mode privé restera `preflight_only` et **aucune inférence privée ne sera revendiquée**.

## Réemploi et critères figés avant essai

Réutiliser `cata_yolox_categories.prepare_image/validate_model_file`, `cata2_bbox_eval.decode_boxes`, `per_p3a_rockchip_low_oem_visual.verify_model/load_vendor/check_heads`, le `ppyoloe.py` + `COCO_test_helper` **officiels Rockchip** épinglés `837db8e992815ff8647eadb709f07067f4bc3a71`. PP-YOLOE ONNX SHA256 `af72d05b33723f6d18f9784f6bba8e593a5554f465f1800d7ad1ba1e33e38b8a`, 31 734 323 octets ; YOLOX SHA256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`. Seuils immuables 0,25 chacun, NMS Rockchip 0,45 ; conserver les 80 classes du fournisseur, rapporter **uniquement les cinq catégories opérationnelles** et les propositions par image. Ne pas modifier après le résultat.

**Positifs de protocole** : exactement 13 entrées SHA Git vérifiées, chaque image décodable, prétraitement identique à l'intérieur de chaque modèle, neuf sorties PP-YOLOE vérifiées `[1,68/80/1,20/40/80,20/40/80]`, YOLOX tête `[1,3549,85]`, une inférence de chaque modèle par image, nombres finis, rapport numérique sans image ni poids ni nom de personne.

**Négatifs** : refuser fichier ajouté ou altéré, manifest incohérent, image symlink, source privée en CI, modèle SHA/poids incorrects, score/catégorie/coordonnées invalides, absence de modèle, rapport préexistant. Si une image échoue, **pas de réparation/retouche de seuil ou sélection alternative d'image**. Compter les propositions parasites sur les deux images `unknown` comme *candidats erronés par rapport aux cinq classes déclarées*, et non comme faux positifs avec GT exhaustive. Interdire IoU/TP/FP/FN/AP50 **sans boîtes de GT indépendante**. Toute image peut présenter plusieurs objets ; `expected_category_proposed` ne mesure qu'une présence d'étiquette.

**Lecture des résultats** : sur **4 chats, 2 chiens, 1 humain**, décrire nombre de propositions attendues pour PP-YOLOE et YOLOX. Décrire aussi chaise, balles, inconnu, les principales confusions et écarts par image, même si aucun modèle ne gagne. **Ce lot n'a pas de porte d'adoption du modèle** ; si les images sont toutes traitées et l'origine des valeurs vérifiée, `test_logiciel_seul` ; sinon `insuffisant`/`bloque_source_externe`. **Dans tous les cas** PP-YOLOE reste non choisi après le 0/1 fauteuil simulé de P3A et licence des poids binaires non prouvée. Aucun décodeur RKNN/mediad, Qwen, système moteur, capteur, SQLite ou NPU installé.

## Les photos privées : pas de métrique de reconnaissance avant inférence et référence

Les deux images sont des vues du **même objet/scène**, non deux cas indépendants ; la trottinette n'a pas de catégorie COCO dédiée. Hauteur optique non mesurée, aucune boîte figée. Mode `--source private --preflight-only` valide localement le manifeste, empreintes, dimensions et absence d'EXIF **sans modèle et sans photo sauvegardée**. Un diagnostic ultérieur, **explicitement privé**, peut comparer les deux modèles **sur le PC** avec leurs modèles SHA vérifiés ; ses seules sorties sont des hypothèses de détection, **aucune preuve de « trottinette reconnue », « obstacle sûr », de couleur fiable ou de score IoU**. Refus du mode privé en GitHub Actions ; aucun JPEG ni archive privée dans la branche/CI/artifact. Ne pas rapatrier les prédictions privées dans le dépôt sans revue et consentement spécifiques.

## Capteur obstacle et sécurité : hors du périmètre du banc

`tofd` délivre 64 mesures de distance frontal, `kinematics/src/tof.rs` permet une reprojection `Floor/Hit/TooClose/Empty`. Dans l'OEM épinglé, `robotd` ne souscrit aux distances pour le thérémine que si activé ; `duck-control/src/safety.rs` n'implémente pas un arrêt collision ToF. **Il ne faut ni inventer un freinage constructeur, ni confondre une catégorie absente avec l'impossibilité de voir un obstacle à distance**. Une navigation sûre / anti-escaliers / contournement n'est **pas livrée** et nécessite un chantier OEM séparé, autorisé et mesuré, pas une nouvelle sécurité motrice dans ce lot.

## Risque, stop et retour arrière

Droits des binaires PP-YOLOE non établis, poids récupérés temporairement sur CI publique uniquement sur échantillons **publics existants** ; pas de redistribution ni déploiement, aucun test RK3566/NPU 2 Hz. Réinstallation inutile sur robot. Si une source, SHA, format, droit ou CI échoue, arrêter uniquement P3B ; ne pas modifier P3A. Retour arrière : revert du lot de comparaison, sans modification OEM/sous-modules/poids/médias.

## Résultat exécuté

**En attente de CI** — ne pas écrire de score PP-YOLOE avant la première exécution réelle.
