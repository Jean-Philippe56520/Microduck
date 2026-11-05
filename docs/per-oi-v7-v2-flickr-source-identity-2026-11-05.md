# PER-OI-V7-V2-ID-1 — alias Flickr et MD5 sur le roster V2 inchangé

**05/11/2026 — protocole préenregistré [sur l'issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6651993891) AVANT modifications de code et toute nouvelle CI.** Base `main@b42b92feab7417d9227ca9f2b7d1644840f2943a`, [#315](https://github.com/Jean-Philippe56520/Microduck/pull/315) fusionnée après **10/10 CI** au SHA final ; modèle S/M [#310](https://github.com/Jean-Philippe56520/Microduck/pull/310) confirmé PC noir synthétique seulement. [Plan d'action](plan-action.md) autoritaire.

## Manque démontré et unique gain utile

Le roster **V2** reste exactement `282d67af8f97975b55149f4b104eaef79bcef1e94beb9522b207ff8a7193c28c` (42 images, 7 × 6, **aucun pixel/inférence**). Les 288 anciennes photos Open Images réellement inférées sont exclues par leur **ImageID** et les collisions **Flickr COCO 5 000** par identité de photo. Cependant deux ImageID Open Images différents peuvent, en principe, référencer **une même photo Flickr** ou partager `OriginalMD5` malgré des labels distincts. Le code #315 ne prouvait pas l'absence d'une telle collision entre les 42 et les 288 **en comparant les identités des photographies originales**.

Ce lot **n'effectue aucun nouveau tirage** et ne modifie pas les 42 choix, le seuil, la graine, la taxonomie, les modèles ou le protocole des scores. Il réutilise la lecture des **mêmes 41 620 métadonnées de validation Open Images V7** et les mêmes cinq SHA épinglés (#315). Il compare pour les 42 et les 288 les identifiants Flickr extraits indépendamment des champs `OriginalURL` et `OriginalLandingURL`, ainsi que les MD5 source, sans téléchargement d'image ni requête Flickr. Les 5 000 Flickr IDs COCO val demeurent l'autre comparateur.

## Positifs/négatifs, PASS/STOP définis avant lecture

**PASS source-only :** 42/42 sources V2 lisibles avec les **deux URLs concordantes** et un MD5 admissible, 288/288 sources historiques idem, **42 photos Flickr distinctes et 42 MD5 distincts**, zéro collision des 42 en ID Flickr ou MD5 avec les 288, zéro collision Flickr avec les 5 000 COCO val, et SHA du roster **strictement inchangé**. Ces éléments sont des **métadonnées déclarées**, pas une preuve d'égalité ou d'inégalité des pixels.

**Négatifs obligatoires sur fixtures avant CSV officiels :** même Flickr avec des ImageID différents dans V2, ancien ID Flickr sous nouveau ImageID, MD5 historique réutilisé avec une autre URL, URL origine / landing contradictoires, métadonnée historique manquante, photo Flickr source COCO déjà présente, double ligne, SHA/roster modifié. Un défaut produit `STOP_V2_FLICKR_IDENTITY_NOT_QUALIFIED` **sans remplacer aucune image** ; une CI peut passer techniquement en rapportant un STOP scientifique.

Le résultat ne contient **que des compteurs, drapeaux et les SHA déjà épinglés** : ni URL, photo ID, auteur, identifiant Open Images, image, autre média, poids ou secret. **0 JPEG / ONNX / modèle / moteur / SQLite**. L'ancien essai V1 (PR #312/#314 fermées sans fusion, quatre réemplois) reste archivé et non rejoué.

## Limites non levées

Un PASS de noms de fichiers Flickr/MD5 n'établit **ni l'absence de doublons perceptuels**, ni la disponibilité de la photographie, ni les droits individuels du photographe, l'authenticité d'un sujet physique, une hauteur de caméra, la qualité du détecteur ou les performances RK3566/NPU. [Open Images V7](https://storage.googleapis.com/openimages/web/factsfigures_v7.html) demande explicitement de vérifier la licence de chaque image ; [la méthode Flickr pour l'historique de licence](https://m.flickr.com/services/api/flickr.photos.licenses.getLicenseHistory.html) exige une clé d'API même sans authentification et les [termes d'utilisation](https://www.flickr.com/help/terms/api) imposent leur propre cadre. **Aucune clé n'est disponible/approuvée ici ; aucune page n'est scrapée**. Les droits et l'absence de doublons perceptuels restent un STOP **avant toute inférence naturelle Nano/S/M**.

Retour arrière : fermer le lot sans fusion si la source échoue, garder le SHA V2 et les résultats tels quels. Sous-modules OEM, `mediad` propriétaire caméra, `robotd` moteur/sûreté 50 Hz, Yocto, unique SQLite, Qwen PC facultatif et confidentialité inchangés.
