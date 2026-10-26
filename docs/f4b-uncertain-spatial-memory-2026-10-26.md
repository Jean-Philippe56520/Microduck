# F4-B — Repères spatiaux fictifs avec incertitude explicite

**26 octobre 2026 — branche `feat/f4b-uncertain-spatial-memory-20261026`, à revoir, non fusionnée.**

Cette étape intervient après [F4-A fusionnée via PR #37](https://github.com/Jean-Philippe56520/Microduck/pull/37), et ne modifie aucune commande, pilote, politique de marche ou mécanisme de sécurité du constructeur. **Le robot physique est toujours indisponible.**

## 1. Portée réelle

`microduck_companion/uncertain_spatial_memory.py` crée une table `f4b_mock_spatial_observations` **dans le même fichier SQLite `ExperienceMemory`** que les mémoires épisodique, sémantique et comportementale. Le code reçoit des points **fictifs prédéfinis par des tests**, ni par la caméra, ni par un ToF 8×8, ni par un système de localisation.

Un point de fixture est une déclaration `MockSpatialObservation` : repère de catégorie générique parmi `toy`, `ball`, `table`, `door`, `wall`, coordonnées `x_m`/`y_m`, rayon d'incertitude **déclaré** en mètres, confiance **déclarée**, horodatages monotone et Unix, numéro de séquence, `source='mock'`, canal `mock_spatial_fixture` et `environment='mock'`. Les deux cadres `mock_zone_a` et `mock_zone_b` ne sont **que des conventions inventées** ; aucune conversion d'un repère vers l'autre ou vers le corps du robot n'existe. Ils ne correspondent à **aucune pièce, porte réelle, carte du domicile ou position géographique**.

Il n'existe pas d'adaptateur physique qui atteste ces champs ; la création d'une fixture par du code Python n'est pas une authentification matérielle. Ce module **ne sait pas mesurer** l'erreur réelle d'une position, ni attribuer une identité individuelle à un animal, un enfant ou un objet.

## 2. Contrat prudent et absence de navigation

| Contrôle | Implémentation F4-B | Ce qu'il ne prouve pas |
| --- | --- | --- |
| Vocabulaire des lieux | 5 catégories génériques et 2 cadres fictifs, sans nom de pièce, personne ou animal individuel | Aucun repérage automatique de porte ou d'objet réel |
| Positions des fixtures | Axe local `x,y` dans **[-10, +10] m** ; rayon annoncé **0,05–2,00 m** ; confiance bornée **[0,1]** | Aucun étalonnage caméra/IMU/ToF, rayon non certifié |
| Fraîcheur **à l'ingestion** | Différence monotone **0–1 s**, différence d'heure Unix **0–2 s** ; aucun horodatage futur accepté | Aucun capteur réel fiable ni cohérence garantie entre horloges physiques |
| Journal et répétitions | Session aléatoire locale, séquences croissantes, doublons exacts sans nouvel enregistrement, rejeu divergent et ordre inversé refusés | Pas de preuve cryptographique, pas de suivi individuel fiable |
| Rappel **historique** | `SpatialRecall.historical_only=True`, `real_sensor_authenticated=False`, `real_reference_frame_verified=False` | **Jamais une observation fraîche**, une localisation du robot ou une destination autorisée |
| Contradictions | Deux disques de rayon annoncé disjoints donnent `conflicting_mock_landmarks` sans coordonnées ; une confiance inférieure à **0,70** bloque aussi la restitution des coordonnées | Le seuil 0,70 est une barrière logicielle **arbitraire, non calibrée** |
| Incertitude | En cas de disques compatibles, conserve **le centre du dernier échantillon** et un rayon **au moins assez grand pour englober tous les disques déclarés**. Jamais de gain de précision par moyenne. Si rayon requis dépasse 2 m, statut `uncertainty_too_large`, sans coordonnées | La cohérence géométrique de points inventés n'est pas un vrai filtre de localisation |
| Mémoire et correction | Conservation maximale configurée **14 jours**, **256 lignes**, requêtes de 50 IDs maximum ; retrait `fixture_annotation_error`/`source_retracted`, relecture excluant les données retirées | Ni empreinte de vraie carte ni marge eMMC/RAM mesurée |
| Autorité sécurité | `floor_clearance_verified=False`, `navigation_authorized=False`, `motor_commands_issued=0` dans **tous** les résultats, y compris en cas de confiance annoncée 1,00 | Le ToF n'est pas un LiDAR 360°, aucun escalier/animal mobile détecté ni évité |

**Si le modèle fictif contient deux positions incompatibles, le rapport supprime le centre et le rayon au lieu d'inventer un emplacement moyen.** Même en présence de points compatibles, le résultat est un **souvenir historique non actionnable**. Deux frames ne sont jamais fusionnées. La disparition de la fixture nouvelle n'est pas comblée par une ancienne observation prétendument actuelle.

Le test d'intégration envoie un repère fictif de « porte » à confiance 1,00 dans la mémoire puis sollicite `AutonomyBrain.choose_from_snapshot` avec les mesures de sécurité absentes : le cerveau **reste en `halt`**, car le souvenir spatial ne peut pas fournir les éléments de sol sûr, de batterie ni d'obstacles.

## 3. Architecture et tests exécutables

- `microduck_companion/uncertain_spatial_memory.py` : validation stricte de la fixture, SQLite du `ExperienceMemory` déjà utilisé, correction de provenance, rappels conservateurs sans commande.
- `tests/test_uncertain_spatial_memory.py` : stockage et relecture, deux cadres indépendants, incertitudes compatibles/incompatibles, confiance insuffisante, suppressions, duplication, séquences, horloges, catégories privées interdites, erreurs SQLite, limite de capacité, invariants moteurs et vérification du `halt`.
- `microduck_companion/f4b_spatial_demo.py` : **deux processus indépendants**, une base SQLite ; un repère de jouet fictif se retrouve avec un rayon **qui ne diminue pas artificiellement** après la seconde observation. Le deuxième cadre reste inconnu.
- `.github/workflows/python-tests.yml` : exécute la suite Python, `compileall` et les deux démonstrations F4-B successives dans la CI Linux.

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.f4b_spatial_demo --database /tmp/microduck-f4b-fixture.sqlite3 --session first
python -m microduck_companion.f4b_spatial_demo --database /tmp/microduck-f4b-fixture.sqlite3 --session second
```

Les tests sur GitHub Actions portent sur les fonctions Python et la persistance du même fichier SQLite. **Ils ne simulent pas la physique MuJoCo, ne valident aucun flux OEM, ne mesurent pas la RAM disponible sur le RK3566 et ne construisent pas de carte.** Le module ne requiert ni PC local, ni LLM, ni API payante, ni réseau.

## 4. Reste à faire et limite de phase

Le développement réel d'une mémoire spatiale utilisable pour l'exploration exigerait, sur une version matérielle identifiée et contrôlée, un capteur de localisation/odométrie exploitable, la gestion rigoureuse de sa dérive et de l'incertitude, une vérification du sol, des obstacles et des animaux en mouvement, des cas d'échec, un cadre de calibration, la supervision humaine, des délais bornés et l'exclusivité motrice de `robotd`. Rien de cela n'est établi par F4-B.

Le lot suivant **F4-C** peut travailler en logiciel fictif sur les propositions d'interactions brèves, silencieuses et annulables **sans** faire exécuter le regard, les sons ou les moteurs. F4-D traitera ultérieurement les associations volontaires et locales d'identités, sans biométrie permanente. **Une position remémorée n'est jamais une autorisation de marcher**, y compris après une validation logicielle réussie.
