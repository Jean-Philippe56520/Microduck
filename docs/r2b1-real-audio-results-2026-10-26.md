# R2-B+1 — Véritables opérations sonores, test négatif de M1-B

**26 octobre 2026. Statut : benchmark audio réel exécuté sur PC runner CI ; M1-B actuel NON RETENU comme reconnaissance fiable d'une source sonore.** Aucun test robot physique. R2-B+2 n'est pas lancé.

## 1. La question et la preuve réellement obtenue

Peut-on reconnaître la **même machine physique** sur une nouvelle prise de son, plutôt que seulement reconnaître une catégorie ou rapprocher deux transformations du même fichier ?

**Source officielle** : [DCASE 2020 Task 2 — Development Dataset, Zenodo DOI 10.5281/zenodo.3678171](https://zenodo.org/records/3678171), sous licence **CC BY-NC-SA 4.0** ; sous-ensembles ToyADMOS IND `ToyCar` et `ToyConveyor`. L'éditeur distingue explicitement **Machine Type** et **Machine ID**, et indique qu'un clip IND correspond à une opération enregistrée du début à la fin. **Il ne documente pas des dates de prise distinctes, changements de microphone ou scènes domestiques indépendantes.**

- [PR #60](https://github.com/Jean-Philippe56520/Microduck/pull/60) — lecteur ZIP à plages HTTP 206 bornées, extraction éphémère, préparation via [l'adaptateur déjà livré R2-B+1](../microduck_companion/r2b1_toyadmos_local.py) et évaluation via [`run_audio_manifest` existant](../microduck_companion/r2b_independent_capture_eval.py).
- [**Essai étendu réel : CI #40377345110**](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40377345110) **réussi (exécution)** ; [**tests Python : CI #40377345237**](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40377345237) : **993 exécutés, 1 ignoré, aucun échec**.
- Pas de fichier audio committé ni conservé après le job ; pas d'enregistrement de voix, d'enfant ou d'animal, pas de réseau vers le robot, pas de commande moteur ou Qwen, pas d'écriture SQLite. Le script se limite aux URLs Zenodo autorisées et refuse les réponses HTTP non `206`. Le ZIP vérifie le CRC de chaque fichier extrait. **Les MD5 de l'intégralité des archives (plusieurs Gio) n'ont pas été recalculés** : les sommes publiées par Zenodo sont indiquées comme référence, non comme résultat vérifié localement.
- `36` fichiers enregistrés originaux extraits **partiellement** depuis les deux archives, dont **34 extraits d'une seconde utilisés dans le benchmark** ; les deux fichiers restants complètent seulement le contrôle de provenance des machines inconnues.
- Six machines distinctes au total : validation sur deux `ToyCar` inscrites et une `ToyCar` inconnue ; test sur deux `ToyConveyor` inscrites et une `ToyConveyor` inconnue. **Une référence sonore de 1 s** et **cinq requêtes d'1 s issues de cinq opérations enregistrées** pour chaque machine inscrite ; cinq opérations pour chaque machine inconnue. Toutes les découpes sont la **seconde centrale fixe**, choisie avant score.

## 2. Résultats réellement mesurés — 16 octets M1-B

| Indicateur | Validation : ToyCar | Test indépendant : ToyConveyor |
| --- | ---: | ---: |
| Requêtes de machines connues | 10 | 10 |
| **Reconnaissances correctes** | **1 / 10 (10 %)** | **0 / 10 (0 %)** |
| Refus d'une machine connue | 9 / 10 | 9 / 10 |
| **Attribution à la mauvaise machine connue** | 0 | **1 / 10** |
| Requêtes de machine inconnue | 5 | 5 |
| Inconnues correctement rejetées | 5 / 5 | 5 / 5 |
| Inconnues faussement reconnues | 0 / 5 | 0 / 5 |
| Abstentions ambiguës (incluses dans les refus) | 1 | 0 |

Seuil de similarité **figé sur la validation uniquement** : **0,9681372549019608**. **Aucun réglage effectué sur le test** et aucune donnée de la même machine réutilisée dans les deux partitions.

**Lecture du résultat :** le seuil prudent rejette correctement les cinq requêtes d'une machine inconnue dans ce test réduit, **mais ne retrouve aucune des dix requêtes familières et commet une fausse fusion entre machines connues**. Ce n'est pas une méthode de reconnaissance fiable sur ce banc. Le `0/5` de faux inconnus ne démontre pas un taux d'erreur nul dans la réalité.

**Premier pilote réel**, [CI #40376862812](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40376862812) : seulement deux requêtes connues et une inconnue au test, **0/2 reconnues, 1/1 inconnue rejetée**. Cet effectif était insuffisant ; le pilote étendu précédent conserve les mêmes fonctions de score avec davantage de prises.

## 3. Coûts et limites de la preuve

Sur le runner Linux CI pour **34 extraits** : `host_wall_s_excludes_media_collection = 0,124 s` ; `host_cpu_user_s = 0,124 s` ; **pic RSS du processus entier = 52 700 Kio**. Ces nombres concernent le traitement *après* acquisition et préparation, **pas** le coût total des lectures réseau, du prétraitement ni le RK3566 du robot.

Les lectures des deux ZIP sous HTTP Range ont transféré **7 434 943 octets (ToyCar)** et **7 605 453 octets (ToyConveyor)**, sans télécharger les archives de 1,816 et 1,869 milliards d'octets. Les CRC individuels ZIP ont été vérifiés, mais **pas le MD5 global des ZIP**. Tout travail de publication sur ces données doit respecter la licence non commerciale.

**Restrictions méthodologiques :** 2 sources connues par jeu de test, 1 inconnue par type, une seule prise de référence par machine, test sur un **type de machine différent** de la validation. Les fichiers représentent des opérations distinctes, mais leurs **dates, acoustiques indépendantes, changements de salle ou de microphone ne sont pas établis**. Les résultats ne prouvent ni reconnaissance d'animaux, ni reconnaissance de bruits domestiques, ni généralisation à d'autres types de sons. **La meilleure preuve actuellement permise est un échec sur ce petit banc contrôlé**, pas un classement définitif de tous les descripteurs audio possibles.

**Non testé :** YAMNet ONNX et tout autre modèle, entraînement, bruit micro réel de Kwirou, voix `Hé Kwirou !`, acquisition OEM, matériel RK3566 et persistance de souvenirs physiques.

## 4. Réutiliser / adapter / créer, statut final du lot

- **Réutilisé** : validateur de prises WAV, SHA-256, seuil prudent de validation, rejet `unknown`, métriques et processeur M1-B/R2-B, ainsi que le préparateur R2-B+1 et les tests négatifs existants.
- **Créé/ajouté** : seul un lecteur ZIP HTTP Range **borné** et son jeu de tests simulés (sans média committé) ; aucune nouvelle mémoire, aucun modèle, aucun service constructeur.
- **Codé/testé en CI** : `993` tests sur fixtures et **un véritable benchmark audio sur fichiers DCASE**, avec succès d'exécution et **échec de reconnaissance**.
- **Décision : `RETESTER` une autre représentation audio ultérieurement, sans accepter M1-B comme modèle de source sonore robuste ni ajuster les seuils au test.** Pour la mémoire, conserver `unknown` et ne jamais convertir un rapprochement incertain en identité.
- **Arrêt demandé** : R2-B+2 et les autres étapes restent **non lancées** sans accord explicite de l'utilisateur.

**Référence canonique** : [plan d'action](plan-action.md) → [plan R2](r2-follow-up-execution-plan-2026-10-26.md) ; état initial du banc R2-B+1 dans [le rapport de préparation](r2b1-independent-audio-2026-10-26.md).
