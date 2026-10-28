# Cat-A2b-G — éditeur de contre-annotations locales en aveugle

28 octobre 2026. **Code fusionné dans main au commit e98295a9 via [PR #120 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/120), [CI finale #40713963667](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40713963667) réussie : 1 571 tests, 5 ignorés, zéro échec. Aucune contre-annotation réelle effectuée, aucune GUI WSLg validée.**

Ce lot fournit une interface manuelle pour générer les deux fichiers de revue attendus par le comparateur Cat-A2b-R #118. Il ne crée pas une vérité terrain indépendante. Les 29 photos privées, 50 boîtes V3 et 12 incertitudes déjà relevées restent des explorations : les revoir après avoir vu YOLOX ne serait pas une contre-annotation aveugle.

Références : [issue Cat-A2b #78](https://github.com/Jean-Philippe56520/Microduck/issues/78), [plan d'action](plan-action.md), [validateur des relectures](cata2b-blind-independent-annotation-gate-2026-10-28.md).

## Porte de preuve et retour arrière

**Observation :** le validateur existant cata2b_private_low.py vérifie JPEG, SHA, dimensions, hauteur de caméra déclarée et splits par site/séance/scène ; cata2b_blind_review.py compare strictement deux relectures de TEST, mais leur production manuelle était peu pratique.

**Hypothèse :** isoler dans la GUI uniquement identifiant opaque, empreinte et dimensions du jeu TEST, sans boîtes ni catégories préexistantes, réduit le risque de contaminer une nouvelle annotation avec V3. Le code **ne peut pas certifier** la bonne foi du relecteur, son indépendance, la réalité de la hauteur optique ou du site.

**Preuve visée :** boîte tracée en pixels originaux, catégorie parmi les cinq classes COCO cibles et visibilité full/partial, marqueur d'incertitude, négatif confirmé explicitement, relecture de chaque TEST, SHA recontrôlé à l'ouverture, export dans le schéma #118. Refuser classe invalide, rectangle hors image, images non confirmées, déclarations manquantes, lien symbolique, copie hors dossier privé, écrasement de fichier existant. Tests adversariaux sur fixtures seulement.

**Critères d'échec et risques :** ne jamais prétendre à des relecteurs distincts parce que les fichiers le disent ; éviter fausse identité de personne ou détection d'humain physiquement présent depuis une TV. Si données de même site seulement, les splits indépendants requis restent non prouvés. Sans fenêtre Tkinter ni validation, arrêter sans sauvegarder de résultat. L'éditeur ne sauvegarde pas de brouillons ; interruption avant export = session en mémoire perdue, sans média persistant nouveau. **Retour arrière :** supprimer le module, ses tests et cette documentation ; aucune SQLite, sous-module, caméra ou action OEM à restaurer.

## Réutiliser / adapter / créer

| Source relue | Décision | Limite |
| --- | --- | --- |
| OEM microduck@942e58e3 : duck-detect/src/lib.rs | Référence seulement | Le détecteur OEM RKNN reconnaît les autres Microducks, pas le corpus Cat-A général |
| mediad/src/main.rs, robotd OEM | Ne pas appeler | mediad possède caméra/son, robotd gère seuls moteurs/sûreté à 50 Hz |
| microduck_rl@b02fdea4 ; PR OEM #381/#414/#450 | Ne pas modifier | Les PR sont ouvertes à cette vérification ; aucun import, aucune action motrice |
| cata2b_private_low.py | **Réutiliser** | Chargement privé du manifeste, contrôles SHA/JPEG/splits, plafonds 25 TEST |
| cata2b_blind_review.py et Cat-A2a | **Réutiliser** | Format JSON, catégories, IoU50 et comparaison stricts déjà livrés |
| QuackNav, microduck-brain, Quacksat, Twin, GC/Smartulf | Ne pas importer | N'apportent pas une contre-annotation indépendante des JPEG locaux |
| cata2b_blind_editor.py | **Créer petit outil local** | Tkinter standard + Pillow déjà utilisé en Cat-A, aucun modèle, serveur ou daemon |

## Utilisation — Ubuntu/WSL sur le PC contenant les photos

Préconditions : corpus Cat-A2b réellement présent dans le dossier privé .local_visual_data/cat-a2b, droits/consentements contrôlés, manifeste et images vérifiés, Pillow installé, Tkinter fonctionnel dans WSLg. Ne rien installer sur le robot. Le programme n'a pas été validé sur Python Windows natif. **Un ancien lot mono-site invalide ne doit pas être déguisé artificiellement en trois sites pour passer les splits.**

Première nouvelle relecture par une personne qui n'a jamais vu les annotations V3 ni les prédictions :

    python -m microduck_companion.cata2b_blind_editor \
      --manifest .local_visual_data/cat-a2b/manifest.json \
      --role first \
      --approved-private-local-media

Deuxième relecture par **une autre personne indépendante**, sans accès au premier fichier :

    python -m microduck_companion.cata2b_blind_editor \
      --manifest .local_visual_data/cat-a2b/manifest.json \
      --role second \
      --approved-private-local-media

Sélectionner classe person/cat/dog/chair/sports_ball et visibilité full/partial, tracer au pointeur chaque boîte, confirmer explicitement chacune des images. Une image sans cible doit être déclarée négative ; une scène ambiguë reste incertaine. Aucune reconnaissance main/pied/chaussure n'est couverte par ce YOLOX. Une personne visible **sur écran** n'est pas une présence physique démontrée : signaler ce cas comme incertain jusqu'à annotation distincte du contexte réel/représenté.

Deux cases de déclaration sont nécessaires avant export : la relecture a été réalisée sans les prédictions/V3, et elle est réellement nouvelle et indépendante. Ces cases sont déclaratives, **non certifiées**. L'éditeur écrit seulement après la confirmation de toutes les images un fichier local reviews/r-<16 chiffres hex>.json, mode 0600, sans écraser d'autre revue. Le chemin est affiché localement pour que l'opérateur puisse utiliser le validateur existant :

    python -m microduck_companion.cata2b_blind_review \
      --manifest .local_visual_data/cat-a2b/manifest.json \
      --review-first .local_visual_data/cat-a2b/reviews/r-ID-OPAQUE-1.json \
      --review-second .local_visual_data/cat-a2b/reviews/r-ID-OPAQUE-2.json \
      --approved-private-local-media

Remplacer les deux noms illustratifs par les fichiers réels générés. Ne jamais placer photos, annotations individuelles, hashes privés, identités, visages, logs ou secrets dans GitHub ou les envoyer à Qwen. Le rapport comparatif produit uniquement des comptes agrégés, jamais un certificat de vérité terrain.

## Niveaux de preuve

- **Prévu :** deux vraies annotations indépendantes, résolution humaine des désaccords et nouvelles scènes sur sites distincts si nécessaire.
- **Codé :** affichage privé GUI des images TEST, boîtes, négatifs, incertitude, contrôles et export JSON compatible #118.
- **Tests PC-fixtures :** contrôles du modèle de session, données strictes, refus, absence de réseau/SQLite, pas d'essai de moteur. La CI ne montre pas une vraie fenêtre WSLg.
- **Simulé OEM / validé robot :** rien. Aucun nouveau modèle, Qwen, robotd, mediad, décision F2 ou mémoire C1 n'est branché.
- **Portage :** aucune mesure RK3566 RAM/RSS, CPU, NPU, disque/WAL, température, batterie ou timing 50 Hz. scripts/resource-audit.sh et inventaire OEM restent des préconditions physiques.

Vérification : [CI finale #40713963667](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40713963667) réussie après test de JPEG modifié, lien symbolique et refus d'écraser une revue existante. Les tests ne produisent ni vérité terrain indépendante ni essai sur un robot. Le gain cognitif C3-B reste bloqué tant que les relectures et sites réellement indépendants ne sont pas disponibles.
