# Cat-A2c — deuxième mesure visuelle : Open Images V7 à labels humains

**28 octobre 2026 — expérience réellement exécutée sur JPEG publics en CPU GitHub Actions, non sur caméra basse ni robot.** [PR #123](https://github.com/Jean-Philippe56520/Microduck/pull/123) ; [première CI de mesure réussie #40722697441](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40722697441), puis contrôles SHA ajoutés avant la fusion. Le plan directeur reste docs/plan-action.md ; les conclusions Cat-A2b #78 et SIM-E2 #101 restent inchangées.

## 1. Pourquoi cette mesure, plutôt qu'une nouvelle préparation

L'expérience Cat-A2a sur **24 images COCO2017 validation** avait produit 31 TP, 9 FP, 18 FN / 49 instances, avec 1/7 chaises et 1/4 sports_ball à IoU50. Elle **existait déjà** et ne devait pas être répétée. Cat-A2b-R/G/G2 sont des outils prêts, mais les 29 images privées historiques n'ont pas de vérité indépendante ni de séparation de lieux démontrée. Les nouveaux outils autour de ce blocage n'ajouteraient pas de preuve. Il fallait une nouvelle source **réelle**, hors de COCO.

**Hypothèse à tester :** sans changer le modèle YOLOX Nano, le seuil ni la politique OEM, les erreurs de reconnaissance sur un autre corpus annoté par des humains seront mesurables, en particulier la sensibilité aux chaises et les fausses présences d'animaux.

**Critères de réussite de l'essai :** nouvelle distribution de photographies réelles, labels positifs **et négatifs** vérifiés humainement avant inférence, sélection déterministe sans fuite d'ID, modèle ONNX et contrat d'inférence inchangés, métriques par classe, compteurs/dénominateurs explicites, fichiers officiels et cohorte SHA-256 figés, fichiers photo transitoires jamais committés.

**Critères d'échec/arrêt :** source machine utilisée comme vérité, catégorie non équivalente, label manquant traité comme négatif, faux droit d'image, fichier source modifié, modèle/poids/threshold changés, téléchargement de photo privée, cohorte sélectionnée selon le score, échec CI ou inférence. Aucun ajout de moteur/robot/companion daemon.

## 2. Réutiliser / adapter / ne pas créer

| Source examinée | Décision | Preuve et limite |
| --- | --- | --- |
| Projet Cat-A2a, `cata_yolox_categories.py`, `cata2_bbox_eval.py` | **Réutiliser** | YOLOX Nano ONNX identique, SHA-256 fixé, `prepare_image`, `decode_boxes`, seuil 0,25, CPU uniquement |
| Google <https://storage.googleapis.com/openimages/web/download_v7.html> | **Réutiliser** | Métadonnées officielles Open Images V7 : étiquettes humaines `verification` / `crowdsource-verification` avec présence=1, absence=0 ; 4 noms exactement équivalents |
| Métadonnées de droits Open Images | **Filtrer** | N'accepter que photos déclarées CC BY 2.0, ensemble validation, orientation 0, taille bornée, sans republier les JPEG. Google précise qu'il ne garantit **pas** la licence réelle de chaque photo |
| `sports_ball` COCO vs `Ball` Open Images | **Exclure** | Les concepts ne sont pas exactement équivalents : pas de faux score balle |
| OEM épinglé microduck@942e58e3, RL@b02fdea4, `robotd`/`mediad` | **Inchangés** | Pilote/sûreté et capture OEM hors périmètre : aucune instruction motrice, aucun modèle OEM ni gitlink |
| QuackNav, microduck-brain, Quacksat, Twin, GC/Smartulf | **Ne pas importer** | Aucun tiers nécessaire pour ce test de perception hôte ; aucune dépendance ou licence nouvelle |
| `cata2c_openimages_human_labels.py` | **Créer petit évaluateur public** | Réutilise le modèle/décodeur existant et mesure uniquement le binaire présence/absence humainement vérifié, sans base de données, entraînement ou appareil |

## 3. Première mesure réelle — run #40722697441

**48 photographies Open Images V7 validation**, sélectionnées avant l'inférence : 6 étiquettes humaines positives et 6 négatives pour chacune des quatre catégories `person`, `cat`, `dog`, `chair`. Chaque fichier a un ID distinct ; l'indépendance de leurs lieux/captures **n'est pas attestée**. Seule la catégorie vérifiée est évaluée par image ; les quatre autres classes ne sont pas supposées négatives.

| Catégorie | TP | FN | TN | FP | Sensibilité | Spécificité |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Chat | 6 | 0 | 4 | 2 | 6/6 = 100 % | 4/6 = 66,7 % |
| Chien | 6 | 0 | 3 | 3 | 6/6 = 100 % | 3/6 = 50 % |
| Humain | 5 | 1 | 5 | 1 | 5/6 = 83,3 % | 5/6 = 83,3 % |
| Chaise | 3 | 3 | 6 | 0 | 3/6 = 50 % | 6/6 = 100 % |

**Fait mesuré, pas théorie :** sur cette petite sélection, le modèle manque 3/6 chaises ; il accepte à tort un chat sur 2/6 absences, un chien sur 3/6 absences et un humain sur 1/6 absences **déclarées** par la source. Les résultats sont instables statistiquement avec 6 cas par modalité ; ne pas annoncer une précision « générale » de Kwipi ni affirmer que la cause des fausses présences est connue. Le corpus ne garantit pas l'absence de recouvrement entre certaines photos Flickr et l'entraînement YOLOX COCO.

- Modèle : SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` ; seuil **0,25 inchangé**.
- Sources officielles gelées après la première réussite : noms `1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9`, métadonnées `ed93a0e121fe345effdfc7359b848dbc64a1ff6778c8c73563157cb500b33a17`, labels humains `92ddbdfceb3626e044df5e89100b24f6c22a79c1888a4bddd00a6f231d86d56a`.
- Roster (ID+classe+présence, non publié) : SHA-256 `608aa803df32cff206267fdc40c926a0c64783889dc79861cd0a92625d23627b`. Un digest agrégé des octets JPEG est également calculé par le banc de répétition ; aucune photo ni empreinte individuelle ne sort.
- Ressources **runner PC** : médiane inférence **23,07 ms** ; pic RSS processus **219 892 Kio (~215 Mio)** ; durée totale de l'essai **23,646 s** (téléchargement des 48 JPEG compris, pas les outils/poids), ni énergie ni latence robot.

## 4. Ce que cette expérience démontre et ce qu'elle ne démontre pas

**Démontré :** des vrais pixels publics ont été inférés par le vrai modèle ONNX et confrontés à 48 étiquettes binaires humaines officielles. Ce n'est pas un résultat de fixtures. Les faux positifs sur animaux et faux négatifs sur chaise sont mesurés dans ce cadre.

**Non démontré :** vérité terrain de **boîtes** et mAP50, vision à 100–300 mm du sol, qualité multi-angle, animal réel versus représentation TV, continuité d'objet, identité, robustesse `unknown`, indépendance physique des scènes, absence totale de recouvrement d'entraînement, généralisation C3 mémoire avec/sans Qwen, validation RKNN/NPU/mediad, mouvements et effet causal. Ne jamais comparer directement ce score présence/absence à l'IoU50 de Cat-A2a : **les métriques et distributions diffèrent**.

**Verdict : RESTER PRUDENT / pas de déploiement.** Pour la perception Cat-A2b, les tests de basse hauteur et annotations véritablement indépendantes restent prioritaires. Ne pas réentraîner ou ajuster le seuil à partir de ces 48 images TEST ; pour étudier la cause d'une fausse présence, revoir une source indépendante et son contexte (TV/affiche versus monde réel) hors du jeu TEST et sans promouvoir une hypothèse Qwen comme fait.

## 5. Retour arrière, quotas et sécurité

Les poids et les fichiers CSV sont téléchargés seulement dans RUNNER_TEMP, images JPEG téléchargées en mémoire et jamais enregistrées/committées. Source/roster SHA gelés, échec si source officielle change. Le code ne journalise ni IDs image, ni auteurs, ni URL privée ou médias. Les seuls scores sont agrégés. En cas de problème de droits, d'accès réseau, de consentement ou de résultat, désactiver **l'étape CI publique** et supprimer le petit module Cat-A2c ; aucune base, sous-module, moteur, politique ou souvenir à restaurer. Avant toute mise en production robot, scripts/resource-audit.sh et mesure RK3566 (RSS, chaleur, CPU/NPU, stockage, autonomie, 50 Hz) obligatoires.

## 6. Plan d'action suivant, sur critères de passage

1. **Arrêt des PR préparatoires Cat-A2b.** L'éditeur, son comparateur et son smoke GUI sont suffisamment prêts. Le blocage est matériel/annotation humaine, non un manque de code.
2. Vérifier si une source **publique réellement basse avec 4–5 catégories** fournit hauteurs optiques, droits et scènes disjointes ; le corpus OCID (deux hauteurs, balles et objets, mais classes/hauteur exactes non prouvées) reste candidat à auditer, pas un score Cat-A2b déclaré.
3. À défaut, deux nouvelles annotations humaines aveugles et un TEST effectivement indépendant sur le PC, puis mesure basse seulement. Ne pas créer de fausses séances.
4. En parallèle, SIM-E2 #101 : attendre/contrôler OEM #450 et mesurer la vraie translation comparativement, sans changer les moteurs à l'aveugle.
