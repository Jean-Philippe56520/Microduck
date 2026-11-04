# QUAL-R0 — contrat d'évaluation COCO/Sama avec les vrais types du lecteur

**04 novembre 2026.** Autorité [plan d'action](plan-action.md). [Objectif, manque, témoin, tests et STOP préenregistrés avant code dans l'issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6639358263).

## Contexte vérifié et manque réel

Point de départ GitHub `main@fec98d46de5787651ff1ba379887278b7edbe741` : #302 (IDs COCO/YOLOX) et #303 (cohorte GT-only) fusionnées. Les PR #301 et #304 sont **fermées sans fusion** : chacune a consommé **42 JPEG COCO** puis échoué à donner un rappel valide, respectivement à cause des indices de catégorie confondus et du rejet d'un `collections.defaultdict(list)` par un scoreur attendant strictement `type(x) is dict`. Total historique **1 316 IDs COCO consommés**. Les sorties du modèle et métriques invalides ne sont pas des preuves de performance ou de taux d'erreur. **Aucune de ces images ne doit être réexécutée comme holdout inédit.**

Le manque n'est donc pas un nouveau modèle, une autre caméra ou encore 42 photos : **il manque un préflight de bout en bout, sur le type de données réellement renvoyé par le lecteur source, AVANT le chargement d'un modèle**.

## Évolution minimale, réutilisation obligatoire

- Le lecteur `experiments.per_qual1_sama_gt_gate._index_boxes` est appelé **directement** dans les tests et produit des `defaultdict(list)`, exactement le type ayant bloqué #304. Aucune conversion cachée en dictionnaire ordinaire.
- `validate_dual_class_map` et `COCO80_ID_ORDER` conservent les deux domaines : annotations indexées par `coco_category_id`, prédictions `Proposal.class_idx` indexées par `yolox_head_idx`. Exemples : personne 1/0, chat 17/15, chien 18/16, balle 37/32, bouteille 44/39, chaise 62/56, livre 84/73.
- `validate_paired_contract` contrôle 42 cas (7 × 6), unicité, les deux GT, les boîtes, les catégories officielles, et refuse tout déficit de GT pour une image assignée, **sans modèle, inférence ni photographie**. Les vues sans boîtes hors sous-ensemble positif sont **inconnues**, non des négatifs physiques vérifiés.
- `score_paired_contract` reprend ce préflight, accepte les tuples `Proposal` synthétiques ou décodés, et mesure les correspondances maximales un-à-un IoU50 via `_paired_iou50` déjà présent. Les propositions non appariées ne sont jamais appelées « faux positifs physiques ». Aucun seuil modèle modifié, aucun calcul n'est intégré au contrôleur du robot.

**Porte obligatoire avant futur essai** : tout futur runner hôte devra appeler `validate_paired_contract` sur les GT **réelles** avant le téléchargement des JPEG/poids et vérifier les empreintes de cohorte. Un test de fixture seul n'autorise pas automatiquement une nouvelle série de 42 images : d'abord démontrer l'intérêt d'une nouvelle évaluation par rapport aux jalons cognitifs et à VIS-FOCUS.

## Tests positifs / négatifs et portée des preuves

**13/13 tests sur fixtures locales** exécutés sur hôte de développement avec les fonctions du lecteur déjà disponibles. Le workflow `qual-r0-scoring-contract-offline.yml` exécute ces mêmes tests sur le vrai checkout GitHub, sans dépendance externe de photographies ni ONNX ; son résultat et les CI générales **doivent être contrôlés au SHA final de la PR avant fusion**.

Tests positifs : `defaultdict(list)` authentique et accepté sans mutation sur `.get`, sept catégories COCO/YOLOX correctes avec rappels synthétiques de 100 %, modifications de GT Sama seules, appariement cardinal maximal, absence de faux positif physique présumé. Tests négatifs : inversions des espaces, altérations des GT et boîtes non finies, déficits sur l'un des annotateurs, nombre ou identité des cas erronés, propositions hors 80 classes, confiance non finie, classe booléenne et structures inattendues.

**PASS_R0 :** CI ciblée et générale vertes au SHA final, 13 tests vérifiés dans le checkout complet, zéro image/poids/ONNX, interfaces et pin OEM inchangés. **STOP_R0 :** erreur de fixture, incompatibilité effective du lecteur, CI rouge ou en attente : non fusion, pas de nouvelle inférence. Retour arrière : revert des seuls fichiers `QUAL-R0` et des en-têtes de documentation.

**Limites irréductibles :** ce lot **ne vérifie pas le score réel YOLOX**, la profondeur d'une scène, le suivi, les modèles concurrents, les caractéristiques RK3566/NPU, la thermique, la sécurité des moteurs ou un Microduck physique. Ni la réussite des fixtures ni la fusion d'une PR ne permettent de lever `STOP_PROMOTION`.

## Suite planifiée après validation

**VIS-FOCUS-A0 : audit de réutilisation**, sans création automatique d'un tracker. Kwipi peut observer plusieurs objets dans la même image si le détecteur le permet, mais ne conserve **qu'une cible d'attention principale choisie selon contexte, intérêts, motivations et unique ExperienceMemory**. Les autres observations restent disponibles et peuvent interrompre le focus pour raison de sécurité ; aucun objet mémorisé n'autorise à avancer sur une position périmée.

**VIS-FOCUS-A1 uniquement en cas de manque prouvé :** séquences indépendantes comparant témoin F1/F2 et continuité hypothétique, erreurs d'échange de cibles, réacquisition, abstention et représentations TV/photos. Mesurer par taille apparente, points de vue et distance/angles physiques si leurs vérités terrain existent. Caméra à hauteur non chiffrée admise sur PC ; ToF frontal 8×8 OEM ne fournit pas automatiquement une distance à chacun des trois objets.

**Cadence :** 2 Hz initialement pour analyser les observations, évaluer 1,5 Hz puis 1 Hz sur mêmes séquences **si** le coût/qualité d'un modèle différent le justifie, sans implémenter de cadence adaptative sans mesures. Cela reste indépendant de la commande motrice `robotd` 50 Hz. **Aucun** second pilote, base SQLite, poids, Qwen, changement OEM, Yocto/B11, gitlink ni photo privée dans ce lot.
