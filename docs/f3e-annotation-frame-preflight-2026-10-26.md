# F3-E — Revue de données et précontrôle d'acquisition locale

**26 octobre 2026.** [PR #36](https://github.com/Jean-Philippe56520/Microduck/pull/36), non fusionnée. Portée : **contrats logiciels sur métadonnées, sans robot, sans image acquise et sans commande motrice**. Après F3-D ([PR #35 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/35)). Cette étape ne constitue ni une validation des droits d'auteur ni une preuve de fonctionnement du capteur.

## 1. Pourquoi F3-E est nécessaire

[F3-D](f3d-open-set-resource-benchmark-2026-10-26.md) a testé 28 nouvelles photos déclarées CC0 avec le seuil MobileNetV2 figé depuis F3-B : **20/28 réponses correctes**, mais **8/16 animaux connus** reconnus. Un total d'exactitude favorable ne suffit pas pour des interactions autonomes fiables. Les **48 photos publiques** des catalogues F3-B (20) et F3-D (28) ont des étiquettes issues des descriptions de fichiers Commons et des droits déclarés par leurs auteurs. Il n'existe **aucune contre-annotation indépendante de ces photos** ni preuve juridique produite par notre logiciel.

Cette phase sépare **deux problèmes** : l'examen humain des étiquettes et licences, puis la préparation technique d'une future requête de capture locale.

## 2. Registre de déclarations de revue (pas une certification)

`microduck_companion/visual_annotation_review.py` dérive **48 identifiants opaques** des pages publiques cataloguées, sans noms privés, images ou chemins de média. Il reçoit des déclarations JSON strictement structurées : identifiant d'échantillon, identifiant **opaque** de relecteur, catégorie `cat`/`dog`/`unknown`, case « image examinée », « page indiquant CC0 consultée » et « déclaration Own work consultée ».

- Deux déclarations distinctes et concordantes peuvent donner le statut `attestation_consensus_only`. **Elles ne prouvent pas que deux personnes réelles et indépendantes ont effectué l'examen, ni que la licence est juridiquement authentique.**
- Une déclaration seule reste `needs_second_attestation` ; une divergence entre relecteurs ou avec la légende publique devient `label_disagreement` ; une déclaration incomplète devient `rights_claim_incomplete`.
- Le registre n'accepte aucun champ libre, URL, fichier, voix, identité ou commentaire de foyer. Il refuse JSON ambigu, doublons d'identifiants, catégories non prévues et déclarations excédant les plafonds.
- **Aucun enregistrement n'accorde une permission d'entraînement ou de collecte : `training_authorizations_granted = 0` par construction.** Les droits, le consentement et la vraie indépendance des annotations requièrent des vérifications humaines hors GitHub.

Au démarrage réel du registre, **48/48 échantillons restent `missing` et zéro revue humaine n'a été conduite par le logiciel**. Les revues fictives des tests servent seulement à éprouver les statuts.

## 3. Contrat constructeur `media.frame` et garde-fous avant acquisition

Le code constructeur inspecté à la révision épinglée `942e58e3aa6dbb28e7037203fff11866122c7567` expose [`mediad/src/frame.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/frame.rs) et [`MediaFrameHeader`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs) : le socket Unix local `/run/mediad/media.sock` accepte `hello`, puis une requête `media.frame` renvoyant **un en-tête de réponse JSON-RPC suivi d'octets UYVY bruts**, et **pas** des notifications `media.detections`. Le socket est prévu avec permissions de groupe `0660` (groupe `robot`). L'accès technique au socket doit être ajouté, authentifié et limité séparément : **ce code F3-E ne s'y connecte pas**.

`microduck_companion/oem_frame_preflight.py` implémente uniquement un **validateur de format sur fixtures** :

- Enveloppe JSON-RPC `2.0`, identifiant de requête attendu, champs du constructeur exacts : `width`, `height`, `format=UYVY`, `bytes`, `captured_at_unix_us`, `rotate`.
- Largeur paire, rotation 0/90/180/270, **`bytes = width × height × 2`** ; **4 Mio maximum** pour une image dans ce prototype (inférieur à la limite OEM de 16 Mio), en-tête de 2 Kio maximum.
- Horodatage déclaré vieux de deux secondes au plus ou futur de 100 ms au plus par rapport à l'horloge extérieure fournie. Un horodatage JSON **n'authentifie pas une capture réelle**.
- Tests avec un contenu binaire **fictif** de longueur exacte ; aucune écriture de pixels sur disque.
- `CaptureChecklist` : consentement ponctuel, vérification privée, identité du pair Unix, révision constructeur, robot immobile et supervisé, audit des ressources **sur le vrai robot**, et intervalle planifié de cinq secondes. Même lorsque toutes les cases sont affirmées vraies, la sortie reste `declared_checks_only_no_capture_authorized` : les cases sont **des affirmations non vérifiées automatiquement**, pas une autorisation d'activer la caméra.

**Cette PR ne crée volontairement aucun client `media.frame`, aucune connexion Unix, aucun appel à `robotd`, aucune collecte automatique ni contrôle moteur.** Une future capture locale nécessitera un programme séparé, l'identification du vrai pair et la preuve d'une permission opérateur, une lecture bornée avec délai total, une politique d'effacement ainsi qu'une vérification de RAM, température et cadence moteur sur le RK3566.

## 4. Tests et niveaux de validation

`tests/test_visual_annotation_review.py`, `tests/test_oem_frame_header.py` et `tests/test_oem_capture_checklist.py` couvrent les avis concordants/conflictuels, l'absence de preuve de droits, les champs interdits, les en-têtes UYVY et les refus des demandes non autorisées. La démonstration `python -m microduck_companion.f3e_demo` lit seulement **un registre vide**, sans images. Le dépôt dispose de **598 tests Python réussis** (28 nouveaux tests F3-E) sur [GitHub Actions](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40245623218) avant les mises à jour documentaires.

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.f3e_demo
```

| Fonction | État |
| --- | --- |
| Vérification du format et de la confidentialité des métadonnées | **Codé, testé sur données fictives** |
| Deux annotations indépendantes sur les 48 photographies | **Non réalisées** |
| Authentification et vérification juridique des droits d'image | **Non réalisées** |
| Contrôle de forme de réponse `media.frame` | **Codé, testé sur fixtures** |
| Connexion au vrai `mediad`, capture d'image, KWS audio | **Non réalisés** |
| Mesures RK3566/RAM/thermique et sécurité locomotrice | **Non réalisées** |

## 5. Condition pour la suite

Avant une prétention de reconnaissance d'un animal du foyer ou l'utilisation d'une caméra en direct, réaliser une **contre-annotation indépendante réelle** avec droits/consentements conservés hors dépôt ; constituer des jeux d'évaluation plus diversifiés sans contamination du test ; puis seulement, avec le robot disponible, vérifier l'UID du processus `mediad`, la révision API et le chemin local, la RAM/température/cadence via `scripts/resource-audit.sh` et les autorisations explicites. Les enfants et animaux doivent rester sous supervision. **Aucune identité personnelle, voix ou photo privée ne doit être versée dans GitHub.**

Prochain lot distinct après revue : priorité à une **voie d'acquisition non motrice et authentifiée**, vérifiable sur fixtures Unix d'abord, puis sur robot physique. Rien dans F3-E ne change `robotd` ou les mécanismes de sécurité du constructeur.
