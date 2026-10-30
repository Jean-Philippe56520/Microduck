# VIS-ATT-2 — huitième cohorte COCO, catégories vs régions top3

**Préenregistrement du 30 octobre 2026 AVANT toute inférence de cette étude.**

## Porte 0 : question de Kwipi et preuve manquante

**Question :** le même YOLOX-Nano sait-il proposer, dans une scène jusque-là non évaluée, une région intéressante **sans connaître correctement la catégorie de son contenu**, ou ne fait-il que reproduire ses détections COCO correctement classées ? Pour Kwipi, la première possibilité peut permettre une observation prudente \`unknown\`, jamais une identification ou un mouvement.

État source de vérité : \`main@ead50d566077516216fc15798d7138c889d1c5fc\`. Les sept cohortes COCO antérieures totalisent **24+24+18+12+12+12+12 = 114 images** (IDs définis par le sélecteur SHA, septième cohorte gelée dans \`tests/assets/public_vision_smoke/region_appearance_seventh_coco_results.json\`). VIS-ATT-1 a déjà montré 8/10 cibles en top3 sur sa sixième cohorte, VIS-APP-1 n'a pas validé les couleurs sur la septième. Les trois vues SIM-VIS-C du même appartement ne prouvaient aucune généralisation ; SIM-VIS-D (nouveau monde OEM) a manqué un pilier visible. Le test géométrique SIM-VIS-F a justement refusé son propre négatif : **aucune nouvelle preuve multiobjet** sur MuJoCo. Ne pas réutiliser ses images.

**Manque spécifique** : aucune comparaison *sur les mêmes sorties ONNX et images nouvelles* entre (a) la boîte YOLOX avec **bonne classe COCO** et IoU≥0,50 ; (b) une des régions **top1/top3/top5 quelle que soit sa classe** avec IoU≥0,50 ; (c) le nombre de régions haute confiance qui déclencheraient F2 en **mock** \`unknown\`, sans appeler F2 ni contourner sa provenance.

## Jeu et méthode fixés avant mesure

Source : COCO 2017 \`val\` **annotations officielles vérifiées SHA-256** \`e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f\` ; images en HTTPS depuis le domaine officiel \`images.cocodataset.org\`, licences CC BY 2.0 *déclarées* dans les métadonnées. Exact modèle Megvii Apache-2.0 \`YOLOX Nano ONNX\` SHA-256 \`c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d\`, score brut **0,25**, NMS **0,50**, bbox IoU **0,50**, image 416×416 avec le même letterbox Cat-A. Pas de nouvelle dépendance et **aucune modification** de décodeur, de poids ou de seuil après résultat.

La sélection est indépendante de toutes les prédictions. Rejouer l'ordre SHA historique du \`select_coco_cases\` **exactement** sur les cohortes (4,4), (4,4), (3,3), (2,2), (2,2), (2,2), (2,2). **Porte de provenance** : les 12 IDs de la 7e doivent correspondre *exactement* aux 12 IDs publiés dans son rapport ; sinon STOP. Exclure les **114 IDs** avant de choisir la huitième cohorte (3 personnes, 3 chats, 3 chiens, 3 chaises, 3 balles, 3 images sans aucune annotation de ces cinq classes = **18 images**). Un « négatif » n'est pas dépourvu de tout objet : il peut contenir les 75 autres catégories COCO, et des omissions de GT.

Évaluer une seule fois chaque image, **un seul passage ONNX par JPEG**, exactement les mêmes sorties brutes pour les deux décodeurs existants \`cata2_bbox_eval.decode_boxes\` et \`yolox_attention_candidates.decode_candidates\`. Les **classes** sont utilisées pour mesurer le témoin et le GT, jamais pour promouvoir une région top3 en fait. Les annotations toutes catégories COCO servent seulement au ratio « sans correspondance GT », pas à déclarer de vrais faux positifs. Aucun JPEG/visage n'est conservé ni publié ; seulement IDs, nombres et métriques. Couleur, forme réelle, distance, capture à 20–30 cm, présence vs photo/TV **non évaluées**.

## Critères fixés avant résultats, sans adaptation ultérieure

- **Porte d'intégrité** : 18 IDs distincts, aucune répétition avec les sept cohortes (114 images), 3+3+3+3+3 cibles avec annotations officielles valides et 3 témoins sans les cinq classes ; SHA et licences vérifiés.
- **Porte de valeur cognitive (généralisation partielle)** : au moins **8/15 cibles** localisées top3 par IoU≥0,50, dont **5/12 non-ballons** ; au moins **une cible non-ballon localisée par top3 alors que le décodeur classé correctement l'a manquée**, car c'est le gain particulier recherché (et pas une simple répétition d'un détecteur de balles).
- **Porte de risque/temps** : fraction de régions top3 **non appariées aux 80 classes GT ≤70 %**, interprétée avec ses limites (GT manquantes ≠ fausses régions) ; décodage top3 p95 hôte ≤15 ms sur 18 images ; relever le nombre de négatifs avec région >= score F2 **0,80** mais ne pas les appeler de faux objets.
- **Si une porte échoue : \`insuffisant\`**, pas de tuning sur cette huitième cohorte, pas de relance opportuniste ni de classe forcée. **Si elle réussit :** preuve bornée « localisation d'une région inconnue pertinente » sur COCO hôte, pas détection générale, perception OEM authentifiée ou décision déployée.

## Réutiliser / adapter / créer

**Réutiliser** \`experiments/yolox_candidate_regions_sixth_coco.py\` (sélection disjointe, mappage toutes GT, mesures), \`cata2_bbox_eval.select_coco_cases\` / \`decode_boxes\` / \`_official_jpeg\`, \`decode_candidates\`, les URLs et SHAs du workflow \`.github/workflows/yolox-candidate-regions-sixth-coco.yml\` ; adapter *seulement* un banc hôte de comparaison A/B et son appel GitHub Actions ; créer des tests qui refusent fuite entre cohortes, absence de bonne catégorie, incohérence des appariements et négatif mal interprété.

Ne pas coder d'intégration \`mediad\`, SDK caméra, service, arbitrage, apprentissage, SQLite nouvelle, Qwen ou moteur. OEM pins \`microduck@942e58e3\` et \`microduck_rl@b02fdea4\` inchangés. CI hôte ≠ RNKK/NPU, robotd 50 Hz ou scènes réelles nouvelles.

**Décision de fin obligatoire** : reporter les 5 classes, appariements classés vs régions top1/3/5, gain top3 non-ballon, témoins, coût hôte et limites dans ce document puis dans README et plan d'action si la CI du code est verte. Une PR n'est fusionnable qu'après CI complètes vertes, même si la porte de valeur du détecteur échoue (elle peut être fusionnée comme mesure négative utile, sans revendiquer une nouvelle fonction).

## Résultat mesuré après préenregistrement et correction de métrique

**Preuve exécutée sur le code corrigé :** [GitHub Actions #41040239645](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41040239645) **verte**, SHA `6256ba47e9d2e6afef41170cb23721395572e0ad`. Les 18 IDs sont nouveaux et exclusifs des 114 images des sept cohortes précédentes ; le 7e roster correspond exactement au témoin historique. Aucune image JPEG n'est publiée. Un seul passage ONNX par image, mêmes sorties pour les deux décodeurs.

| Catégorie cible (3 images chacune) | Localisée avec bonne catégorie | Localisée par région top3 | Récupérée par top3 après échec classé |
|---|---:|---:|---:|
| Personne | 3 | 3 | 0 |
| Chat | 1 | 2 | **1** |
| Chien | 2 | 3 | **1** |
| Balle | 2 | 1 | 0 |
| Chaise | 3 | 1 | 0 |
| **Total** | **11/15** | **10/15** | **2** |

**Mesures complémentaires :** top1 **3/15**, top5 **11/15** ; régions top3 sur cibles non-ballons **9/12** (personne/chat/chien/chaise, sports_ball explicitement exclu), **2/12 cibles non-ballons récupérées** malgré l'échec du comparateur classé. Parmi 41 régions top3 sur les 18 images, **34** se superposent à une annotation de l'une des 80 classes COCO (IoU≥0,50), **7** n'ont pas de correspondance, soit **17,07 %**. Ces sept régions **ne sont pas démontrées fausses** à cause des lacunes d'annotation. Parmi les trois images *sans annotation des cinq classes cibles*, **3/3** ont au moins une région et **2/3** une région à score ≥0,80 : un rappel critique contre une confiance excessive et contre le déclenchement automatique de F2.

Mesures PC GitHub Actions : inférence ONNX médiane **24,251 ms/image**, décodage **combiné des deux méthodes** p95 **3,720 ms/image**, pic RSS de tout le processus hôte **360 576 KiB** incluant Python, annotations et modèle (ni NPU/robot, ni coût par frame embarqué). Le test du suivi de catégories a révélé **avant fusion** que l'ordre COCO situe `sports_ball` avant `chair` : une agrégation initiale par position comptait la mauvaise tranche de 12 images. L'agrégation est maintenant fondée sur le nom de catégorie, testée pour exclure la balle et inclure la chaise ; les seuils **préannoncés** et les sorties ONNX sont inchangés. Il ne s'agit pas de retuning du détecteur.

**Toutes les portes d'étude préenregistrées sont franchies**, mais **décision d'architecture limitée** : les propositions top3 peuvent compléter une attention **spatiale `unknown`** dans le *banc PC*, surtout chat/chien, **sans remplacer** le détecteur COCO classé (11/15 vs 10/15), sans promouvoir une région en catégorie, objet physique réel ou action. Aucun gain de comportement sur l'OEM réel et aucune perception RKNN/2 Hz validée. Ne pas répéter d'autres cohortes COCO pour gagner artificiellement un point : la prochaine preuve utile concerne les sources et budgets du flux OEM `mediad → duck-detect → RKNN`, puis des scènes basses indépendantes avant déploiement.
