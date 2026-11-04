# PER-OI-V7-OVERLAP-1 — qualification exacte d'une cohorte GT, 288 anciennes Open Images

**Date :** 04/11/2026. **Statut :** PR empilée en laboratoire **source-only**, non fusionnable tant que [#312](https://github.com/Jean-Philippe56520/Microduck/pull/312) n'a pas passé **toutes** ses CI et rejoint `main`. [Porte originale avant code](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6644168616) ; [correction avant code des anciennes cohortes](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6644204260). `docs/plan-action.md` reste la source d'autorité. Aucun achat, flash, droit moteur ni nouveau modèle.

## Question, manque prouvé et gain limité

Le SHA de [#312](https://github.com/Jean-Philippe56520/Microduck/pull/312) fixe prospectivement **42 scènes** à partir de GT boîtes, mais ne vérifie ni qu'elles sont **humainement positives** pour le libellé alloué, ni qu'elles n'ont pas été utilisées en Open Images dans les essais antérieurs. [#313](https://github.com/Jean-Philippe56520/Microduck/pull/313), fusionnée `main@d0170757bbbb7abee389f6d39007bef37f7b1f56`, a contrôlé les **4 CSV officiels**, 618 184 labels humains et les sept comptes de catégories, mais **uniquement des agrégats**.

**Gain testable :** reconstituer exactement les **42 couples ImageID/label** du SHA figé `1026cb395a8b817c43d8e03fbafa695aabc0b9c927464cf9f81d39e686703bc3`, les 288 anciens IDs déjà inférés, puis calculer les **intersections et 42 votes humains attribués** sans publier les identifiants, URL, auteurs, rectangles, JPEG, modèles ou souvenirs.

## Réemploi exact (pas une quatrième sélection)

- [#312](https://github.com/Jean-Philippe56520/Microduck/pull/312) : `_taxonomy`, `_eligible_images`, `_valid_boxes`, `select_frozen_roster` ; aucune nouvelle graine ou retouche de cohorte.
- [Cat-A2c #123](https://github.com/Jean-Philippe56520/Microduck/pull/123) : `select_human_verified_cases` ⇒ 48 anciennes scènes.
- [Cat-A2d #295](https://github.com/Jean-Philippe56520/Microduck/pull/295) : `_load_sources` ⇒ 192 scènes, après exclusion de Cat-A2c.
- [PER-OI-W1 #298](https://github.com/Jean-Philippe56520/Microduck/pull/298) : `choose_cases` avec les 240 anciennes exclues ⇒ **48 autres scènes** et SHA historique `6954c9a0136d262a01eeba44b1da35319cf5323d270c73bc306cfd7f5f33179a`.
- [#311](https://github.com/Jean-Philippe56520/Microduck/pull/311)/[#313](https://github.com/Jean-Philippe56520/Microduck/pull/313) : quatre CSV validation officiels, SHA fixés, source de labels humains `92ddbdfceb3626e044df5e89100b24f6c22a79c1888a4bddd00a6f231d86d56a`. Pour la validation des votes du roster uniquement, parseur décimal exact 0/1, aucune valeur fractionnaire arrondie.

## Critères préfixés positifs, négatifs et STOP

**P1 :** 42 images, 7 labels × 6, 42 IDs uniques et SHA identique au roster #312. **P2 :** chacun a un vote positif explicitement vérifié humainement pour le label attribué, sans vote négatif contradictoire. **P3 :** exactement 288 IDs antérieurement inférés retrouvés via les sélecteurs officiels, avec SHA W1 inchangé et **intersection nulle** avec les 42 ; aucune des 288 ne fait l'objet d'une nouvelle inférence. **P4 :** URL source d'origine HTTPS pour chaque sélectionnée. **P5 :** tests fixtures positifs/négatifs avant accès externe, quatre SHA officiels validés et sortie uniquement numérique sans média.

**Négatifs :** roster modifié/incomplet/dupliqué, SHA drift, 7×6 faux, ancien ID collisionné (Cat-A2c/Cat-A2d/W1), ancien historique non reproduit, vote manquant/négatif/contradictoire, source non humaine, score de vote fractionnaire, landing URL absent, fichier symlink, CI non verte ⇒ `STOP`. Pas de sélection de remplacement après analyse : garder la cohorte #312 figée comme donnée d'expérience.

**Si aucun blocage détecté :** `OI_42_DISJOINT_FROM_288_WITH_HUMAN_GT_METADATA_ONLY`, **exclusivement pour les réemplois Open Images connus**. Si l'un des 42 chevauche une ancienne image, n'a pas de vote humain positif ou de landing HTTPS : `STOP_FROZEN_42_SOURCE_NOT_QUALIFIED`. Un STOP **scientifique** peut coexister avec une CI technique réussie : ne pas prétendre à un PASS de cohorte.

## Limites et suites bloquées

**Non vérifiés :** identité Flickr/URL/MD5 entre Open Images et les 5 000 COCO val / 1 316 consommées, doublons JPEG/perceptuels intercorpus, droits actuels de chaque auteur Flickr, images physiquement basses, équivalence sémantique de `Tennis ball` à tous les `sports_ball`, annotations exhaustives, segmentation ou distinction image d'écran/présence réelle. Une licence déclarative dans le CSV n'est **pas une permission individuelle prouvée**. Ainsi même en cas de P1–P5, **aucune inférence Nano/S/M sur les JPEG et aucun calcul de précision n'est permis par ce lot seul**.

Réutiliser l'OEM uniquement après mesures sur robot réel, absent : `mediad` caméra propriétaire, `robotd` seul pilote et garde 50 Hz, NPU RK3566 et 2 Hz multicatégories non validés. Les archives B10/B11 19+5+4, l'unique SQLite, Qwen PC facultatif, Yocto et les gitlinks épinglés restent inchangés.

**Rollback :** fermer le candidat sans fusion si les 42 échouent, si la base #312 diverge, si CI en attente/rouge ou si fuite de médias. Cette PR empilée doit être rebasée/auditée après fusion de #312 puis soumise à toutes les CI finales avant une éventuelle fusion sur `main`.
