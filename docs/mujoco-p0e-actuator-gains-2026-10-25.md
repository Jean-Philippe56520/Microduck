# P0e — Vérification des gains actifs et de la loi d'effort des actionneurs (25 octobre 2026)

**Verdict :** [CI Python et MuJoCo réussie #40193139617](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617), **199 tests Python**. Le gain effectif et les forces calculées suivent **exactement la loi d'actionnement du modèle épinglé** sur les relevés vérifiés. **Aucune saturation d'actionneur n'est observée** dans les phases comparées. Malgré cela, la translation finale n'est que **2,295 mm** (seuil 10 mm **non atteint**). La démarche n'est pas validée et la **cause racine du manque de progression demeure inconnue**.

## Périmètre, méthode, traçabilité

- Révisions OEM inchangées : [`microduck_rl` `b02fdea...`](https://github.com/pollen-robotics/microduck_rl/tree/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3) et [`microduck` `942e58e...`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567). Scène plane `scene.xml` identifiée par blob Git `a3848be52113a50138d54921748733f09488d496`.
- Le protocole **ne change aucun fichier du constructeur** ni aucune commande, politique, gain ou contrôle moteur. Un processus `body_server` officiel épinglé est instrumenté par le crochet facultatif P0d. `robotd` reste seule autorité motrice.
- Nouvelle collecte P0e **avant l'appel original** de chaque quatrième `mujoco.mj_step` (pas de 5 ms, échantillonnage ~50 Hz), sous le verrou du monde OEM : consignes `ctrl`, positions et vitesses des articulations, `model.actuator_gainprm`, `model.actuator_biasprm`, gear, `forcerange` et activation de cette limite, amortissement et frottement interne. **Après** ce seul pas OEM, la sonde relève les forces calculées `data.actuator_force`, contacts, angle post-intégration et position du tronc.
- L'analyse hors ligne refuse les anciennes traces P0d sans captures pré-pas, les trames perdues, la mauvaise révision ou scène, les paramètres manquants/non finis, les valeurs gear et limites de force non attendues, les horodatages impossibles et toute absence de `robot.stop` confirmé. Elle ne touche ni aux moteurs ni à MuJoCo et ne reconstitue pas artificiellement des valeurs manquantes.
- Le lien entre phases `stand` et `walk` reste une **fenêtre horodatée** par l'observateur P0b à 10 Hz ; elle ne certifie pas que la politique n'a pas changé entre ses échantillons. Les quatre relevés à gain debout dans la fenêtre marche sont consignés comme tels, sans réinterprétation.

### Relation vérifiée

Pour les **14 actionneurs positionnels nommés**, et seulement dans ce modèle épinglé où le rapport d'engrenage est `gear=1`, la force d'actionnement scalaire avant écrêtage est :

`F = gain_p_actif × consigne + bias_position_actif × angle_avant_pas + bias_vitesse_actif × vitesse_avant_pas`.

Pour le modèle OEM, `bias_position_actif = −gain_p_actif` et `bias_vitesse_actif = 0`. La sortie est bornée par le `forcerange` actif du modèle : **−0,96 à +0,96 N·m**. Cette vérification utilise la **pose avant intégration**, et non l'angle après intégration utilisé approximativement par P0d.

Sources constructeur : [classe `chosen_actuator`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/robot/microduck/joints_properties.xml), [`Body._apply_torque` du serveur](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/sim/body_server.py) et [valeurs par défaut du contrôle `robotd`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs). Le gain nominal `0,55` est multiplié par `gain_registre / 200` et par le ratio de station debout `0,8` lorsque le constructeur l'impose ; cette lecture de code ne doit pas être confondue avec une nouvelle commande de gain.

## Mesures vérifiées — essai P0e #40193139617

| Indicateur | Fenêtre `stand` | Fenêtre `walk` |
| --- | ---: | ---: |
| Relevés solveur (~50 Hz) | **79** | **127** |
| Relevés × 14 actionneurs contrôlés | **1 106** | **1 778** |
| Gain actif (`chosen_actuator`, actions jambes) | **0,44 N·m/rad sur 79/79** | **0,55 N·m/rad sur 123/127** ; **0,44 sur 4/127** |
| Écart maximal force prédit/force solveur | **0 N·m** | **0 N·m** |
| Échantillons d'effort écrêtés par le modèle | **0/1 106** | **0/1 778** |
| Échantillons d'effort observés près de ±0,96 N·m | **0/1 106** | **0/1 778** |
| Deux pieds avec force normale > 0,1 N | **79/79** | **127/127** |

**Au total, 2 884 valeurs d'effort des 14 actionneurs** correspondent exactement au modèle **pour ces fenêtres échantillonnées**. Le résultat `0 N·m` est la valeur numérique retournée par le comparateur sur les trames de cette exécution, **pas** une preuve de précision de servo physique ni de représentativité universelle. Les quatre relevés de la fenêtre de marche à gain `0,44` sont compatibles avec un changement de sélection de politique à la frontière de la fenêtre, mais cette explication n'est **pas prouvée tick par tick**.

### Amplitude des commandes comparée aux articulations

| Articulation (fenêtre de marche) | Excursion de consigne avant pas | Excursion d'angle avant pas |
| --- | ---: | ---: |
| Hanche gauche, roulis | **0,1060 rad** (~6,07°) | **0,0173 rad** (~0,99°) |
| Hanche droite, roulis | **0,1056 rad** (~6,05°) | **0,0035 rad** (~0,20°) |
| Genou gauche | **0,0548 rad** (~3,14°) | **0,0228 rad** (~1,31°) |
| Genou droit | **0,0526 rad** (~3,01°) | **0,0263 rad** (~1,51°) |

Ces amplitudes descriptives dépendent de la posture et de la charge au sol ; une amplitude d'angle inférieure à l'excursion de consigne **ne démontre pas** une panne, une saturation ou un gain inadéquat. Il faut mesurer l'effet de la politique ONNX et des contraintes dynamiques ensemble.

### Résultat de déplacement, arrêt et coût de la sonde

- Essai **J2e existant** : **24 commandes de 0,12 m/s**, politique `walk` sur **23/24** notifications, vitesse appliquée maximale déclarée proche de 0,12 m/s ; une indication `deadman` figure dans les limitations échantillonnées et ne doit pas être masquée.
- Translation nette XY finale **0,002294842733 m (2,295 mm)** ; mémoire éphémère : `no_progress_observed`. **`robot.stop` confirmé**, critère de 10 mm **non atteint**. Ce nouvel essai ne modifie pas les valeurs des précédents essais P0b, P0c et P0d.
- La CI **199 tests Python** et l'exécution MuJoCo sont réussies. L'artefact `mujoco-headless-diagnostics` conserve `actuator-gain-audit.json`, `solver-tap.jsonl`, `solver-analysis.json`, `walk-comparison.json` et les logs sans donnée personnelle.
- Le chronométrage `capture_us` ancien P0d (~60 µs moyens ici) **n'inclut pas la nouvelle capture avant le pas physique**. Le coût CPU total de P0e et son éventuel effet sur la phase du contrôleur ne sont donc **pas quantifiés** ; ne pas utiliser cette CI pour promettre une latence réelle.

## Interprétation et prochaine investigation P0f

1. **Écart de conversion gain/force identifié : non.** Le ratio station debout 0,8 et le gain de marche 0,55 sont présents dans les valeurs effectives ; aucune saturation à la limite ±0,96 N·m n'est vue sur les 2 884 échantillons étudiés.
2. **Absence d'alternance de charge parmi les instants enregistrés : oui.** Les deux pieds sont chargés sur les 127 échantillons de marche ; ce n'est pas une mesure continue ni une preuve d'immobilité absolue.
3. **Origine du faible suivi et de la faible propulsion : inconnue.** P0e vérifie une *loi d'actionnement*, non l'adéquation de ses paramètres ni la qualité de la politique de marche.
4. **P0f proposé, non réalisé :** comparer en lecture seule les entrées/sorties ONNX, mises à l'échelle et états de référence de `robotd` avec l'inférence et le simulateur d'entraînement officiel à modèle épinglé. Examiner la cohérence des phases de marche, sans modifier gains, réseaux ou contrôle constructeur. Si la cause ne peut pas être isolée, avancer en parallèle sur P2 (autonomie multi-cycles sans locomotion).

**Niveau de preuve :** 199 tests Python réussis, MuJoCo constructeur avec sonde Python facultative ; **aucune validation matérielle** (robot physique indisponible). La simulation n'établit ni navigation intérieure ni sécurité d'une pièce habitée.

