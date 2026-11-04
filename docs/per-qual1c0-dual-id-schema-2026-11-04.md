# PER-QUAL-1C0 — contrat explicite entre identifiants COCO et indices YOLOX

**04/11/2026 — Porte de correction avant modification :** [issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6638239391). Retour sur l'essai [#301](https://github.com/Jean-Philippe56520/Microduck/pull/301), **ferme sans fusion**, apres 42 vraies inférences COCO mais **resultat de rappel non valable**.

## Pourquoi STOP de #301 malgre CI specialisee verte

- Contrat des annotations : dictionnaires des boites `(ImageID, COCO category_id)`. Exemples : `person=1`, `cat=17`, `dog=18`, `sports_ball=37`, `bottle=44`, `chair=62`, `book=84`.
- Contrat du decodeur 80 têtes YOLOX : `(class_idx 0..79, box)`. Exemples correspondants : `person=0`, `cat=15`, `dog=16`, `sports_ball=32`, `bottle=39`, `chair=56`, `book=73`.
- Dans #301, le script cherchait les GT avec le **second espace** au lieu du **premier**. Les fixtures faisaient cette meme confusion, d'ou une CI de fonctionnement techniquement verte mais des mesures physiques fausses. Les GT non trouvees ne sont pas des negatifs humains et les taux imprimes par #301 **ne doivent pas etre utilises**.

**Preuves conservees de #301 :** le modele ONNX et les sources SHA256 etaient conformes et 42 photos inedites ont fait 42/42 inférences. Images et poids non publies. **Le calcul GT/decodeur de #301 est invalide ; 42 IDs consommes et aucun rerun autorise en tant que nouvel holdout.** Aucun score valide de sensibilite aux deux GTs ne peut etre reconstruit sans les boites individuelles et les predictions, volontairement non conservees.

## Correction minimale C0

**Reutiliser :** le COCO80_ID_ORDER du decodeur PER-80, la liste de noms COCO issue de `_cohort_from_pinned_source()`, le tableau `targets` deja determine par Sama-COCO. **Adapter :** le seul source gate existant `experiments/per_qual1_sama_gt_gate.py` : construire un dictionnaire `class_id_domains` par classe avec `coco_category_id` et `yolox_head_idx` distincts ; verifier `COCO80_ID_ORDER[yolox_head_idx] == coco_category_id`. **Sans nouvelle DB, inférence, lib, modele, licence ou service OEM.**

**Tests fixes avant code :** P1 les sept ancres officielles correctes, P2 conservation du gate 42 images et 7x6 boites GT validées. N1 inversions et indices zero-based refuses, N2 categorie absente/80 têtes en double ou mauvaises rejetees, N3 source modifiee, absence de rerun de photos ou ONNX. SUCCESS = tests de fixtures + source-only CI et suite generale verts sur dernier SHA ; STOP_SCHEMA ou CI en echec = pas de fusion. Retour arriere : revert uniquement des changements de ce lot. **CI PC source seulement, pas de demonstration de vision Kwipi.**

## Suite future, non executee dans ce lot

Pour une nouvelle mesure sur modeles **apres passage de C0** : selection prospective sur de nouvelles images GT **en excluant 1 274 IDs deja consommes** (1232 historiques + 42 de #301) ; tests sur espaces d'IDs representatifs de COCO et YOLOX, mapping des boites et sorties avant tout modele ; figer nouvelle cohorte/hash avant inference. Aucune reutilisation des 42, aucun tuning. Pas de robot physique, NPU, F1/mediad, SQLite, Qwen, sous-module, Yocto ou moteur `robotd` modifie.
