# PER-OI-V7-COHORT-1 — cohorte GT-only de 42 scènes pour YOLOX-S/M

**Date :** 04/11/2026. **État de ce document :** candidat source-only ; **les résultats réels et les CI du dernier SHA sont à constater**. [Porte fixée AVANT code](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6643789216). Base `main@e4909805644adfe9dbedd9870033a9b016aa7fb5` après [#311](https://github.com/Jean-Philippe56520/Microduck/pull/311) fusionnée 4/4 CI. #310, qualification de vrais ONNX Rockchip S/M sur noir synthétique, encore distincte et non déployée. L'autorité reste [le plan d'action](plan-action.md).

## Manque et objectif borné

La preuve publique [#311 / CI #41924855594](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41924855594) a contrôlé **seulement** trois vrais CSV Open Images V7 : 41 620 métadonnées validation, 35 826 images correspondant aux filtres de licence déclarée CC BY 2.0/MD5/rotation/URL, et suffisamment de classes candidates (9 `Tennis ball`, 41 `Book`, 151 `Bottle`, 201 `Chair`, 292 `Cat`, 1 363 `Dog`, 4 473 `Person`). **Ces nombres ne sont pas des détecteurs réussis et n'établissent ni les droits individuels ni la non-contamination des images COCO consommées.**

La cohorte de comparaison entre YOLOX-Nano/S/M ne peut être tirée **après avoir vu leurs sorties** : il faut d'abord fixer un échantillon de GT et son empreinte. Le lecteur [`experiments/per_oi_v7_source_inventory.py`](../experiments/per_oi_v7_source_inventory.py) sert de garde source et n'est pas dupliqué.

## Sources et statut des licences

Les trois SHA-256 officiels vérifiés en CI #311 sont figés dans le code de cohorte :
- Classes : `1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9`.
- Métadonnées d'images validation : `ed93a0e121fe345effdfc7359b848dbc64a1ff6778c8c73563157cb500b33a17`.
- Boîtes validation : `d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2`.

**Sept libellés source retenus** : `Tennis ball`, `Book`, `Bottle`, `Chair`, `Cat`, `Dog`, `Person`, six images **distinctes** par libellé. `Football` n'est pas interchangeable par défaut. `Tennis ball` n'est qu'un **candidat sous-type** de `sports_ball` COCO : cette hypothèse doit être vérifiée avant de compter des TP de balle. Les six autres libellés correspondent en nom, **pas encore en exactitude des scènes**, à des catégories COCO. Les MIDs Open Images ne sont pas des indices de tête YOLOX.

**Licence :** sélectionner exclusivement la licence Flickr **déclarée** CC BY 2.0 par image et les métadonnées validation (URL HTTPS d'origine, MD5 valide unique, rotation 0). Le producteur ne garantit **pas** juridiquement la provenance et les droits de chaque photographie. Aucune photo n'est publiée, revendue, utilisée pour entraîner, ou introduite dans l'image Yocto.

## Réutiliser, adapter, créer

**Réutiliser** le lecteur, filtre et inventaire OI V7 (#311), le vrai jeu GT externe et sa version, le contrôleur de droits/empreintes, le protocole de QUAL-R0 `COCO category_id` ≠ `YOLOX head_idx`, et seulement ensuite les modèles S/M officialisés dans #310. **Créer** un sélecteur autonome `experiments/per_oi_v7_frozen_cohort.py`, les 13 tests source-only, une seule CI et ce rapport. Aucun nouveau modèle, entraîneur, service caméra/moteur, base SQLite, pilote, modèle ONNX/RKNN distribué, modification d'OEM ou de sous-module.

Sélection : prendre uniquement les rectangles humains valides, non `IsGroupOf` / `IsDepiction` / `IsInside`, source `xclick/activemil` avec confiance 1 ; choisir les labels du **plus rare au plus fréquent**, puis trier chaque pool au SHA-256 de `kwipi-per-oi-v7-20261104-v1/Label/ImageID`. Conserver six identifiants non réutilisés par catégorie, sans doublon de MD5 ; compter les boîtes petites/moyennes/grandes uniquement en **métadonnées**. Stocker une seule empreinte du roster (ordre + label + ID), **jamais** les IDs individuels dans un artefact.

## Tests, succès, arrêt et retour arrière préfixés

**Positifs (P1/P2) :** exactitude des trois SHA officiels, schéma/GT compatible, exactement 42 images et 6 par libellé disjointes, choix déterministe sans prédiction, tailles de boîtes et flags sous forme d'agrégats, aucun média/model chargé. Positifs des lecteurs #311 et du plan OEM conservés.

**Négatifs (N1–N5) :** drift de fichier, MID ou image dupliqués, MD5 partagé, licence non admissible, mauvaise rotation/URL, bbox nonfinie/inversée, annotations dessin/groupe/inside, classe supprimée, moins de six tennisballs, image reprise dans plusieurs classes. Rejeter par STOP documenté, sans changer le seuil/la source après constat. Les photos Open Images peuvent aussi exister dans COCO même avec des IDs distincts : **disjonction cross-dataset de contenu inconnue** ; les 1 316 JPEG COCO précédents ne sont **jamais** rechargés ici.

**PASS source uniquement** : 13 tests + préflight des vrais CSV avec 42 images et SHA + **toutes les CI du HEAD final vertes**. **STOP** : aucun lot de précision tant qu'au moins un des contrôles échoue ; aucun renouvellement arbitraire d'échantillon sur le même GT. **Retour arrière** : laisser la PR non fusionnée, sans modification des archives 19+5+4 ni des gitlinks.

**Étape suivante séparée** : qualifier sans fuite les droits/identités/similarité cross-dataset, vérifier sémantique des sous-classes et sortie du décodeur S/M sur images autorisées ; puis un benchmark Nano/S/M du **même roster** avec seuils figés, IoU50, détections manquées et propositions non appariées (qui ne sont **pas** automatiquement FP), latence/RSS hôte. **Pas** de revendication de portée/angles physiques, 2 Hz RK3566, suivi temporel, sécurité motrice ou autonomie. A2 focus/EX4-C2 restent bloqués dans leur périmètre respectif.

**Responsabilités** : `mediad` seul capteur/vision OEM ; `robotd` seul moteur/sûreté à 50 Hz. Les modèles Rockchip restent hors robot et hors distribution, `ExperienceMemory` SQLite unique, Qwen PC facultatif.
