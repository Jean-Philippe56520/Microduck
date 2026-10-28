# SIM-E2-B — diagnostic passif des cibles et positions `robotd`

**Date :** 28 octobre 2026. **Nature :** code opt-in et tests
sur fixtures hôte, **aucun essai moteur nouveau** ni validation robot.
Suivi : [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101).
Plan directeur : [plan-action](plan-action.md).

## 1. Observation, hypothèses, preuve et arrêt

Observations conservées de l'opérateur sous WSLg : trace `duck-sim
drive 0.08 0`, 32 états dont 31 `walk`, zéro limiteur, consigne appliquée
0,08 m/s, **3,500 mm** de déplacement XY net, jambes de faible amplitude.
Les SHA-256 locaux des trois ONNX correspondent **exactement** aux modèles
référencés P0h/v8, mais l'identité du fichier n'établit pas sa sortie
effective en boucle fermée.

Hypothèses **non prouvées** à départager par mesures futures :
amplitude des cibles de jambes faible ; cible variable mais position
mesurée peu mobile ; différence d'actionnement BAM vs position MJCF ;
contacts/glissement ; configuration de politique différente.
Une sélection `walk`, une consigne `applied`, un écart cible/mesure ou
une proximité temporelle ne démontrent **ni** une démarche, **ni** une cause.

Preuve recherchée d'abord **au repos** : lecture cohérente et horodatée
d'une paire `robot.state.joints/targets`, sans mouvement demandé.
Échec/arrêt : révisions ou processus non vérifiés, scène non épinglée,
nom alpha différent, réseau indisponible, horloge absente/périmée/non
croissante, trame non finie/mal dimensionnée, état `robotd` impossible.
Un refus reste un résultat, ne jamais abaisser une garde.
Risque principal : mauvaise attribution d'un écart à un ONNX.
Retour arrière : omettre `--joint-tracking` ; compatibilité par défaut
préservée ; aucune modification de configuration ni de modèle.

## 2. Inventaire OEM, sources épinglées

| Rôle | Source constructeur | Établi / limites |
| --- | --- | --- |
| Contrôle/politique | [microduck `942e58e3` / robotd-params](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd-params/src/lib.rs) ; [`robotd/src/control.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs) | `robotd` normal : `velstand`, sans `stand` ; `duck-sim` force duo alpha ; contrôle: ONNX, échelle, filtre, cibles |
| Protocole et contrôle moteur | [`duck-ipc-proto/src/lib.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs) ; [`robotd/src/main.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/main.rs) | `robot.state` comporte `joints[15]`, `targets[15]`, `t_ns`. `targets` est construit avant `safety.apply` et le traitement d'erreur d'écriture ; ne constitue pas un accusé du servo |
| Inspecteur existant | [`robotctl/src/monitor.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotctl/src/monitor.rs) | Affiche cibles/mesures sur la même trame ; `robotctl monitor --json` et `robot.subscribe` ont déjà cette source |
| Physique OEM | [microduck_rl `b02fdea4` / `body_server.py`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/sim/body_server.py) ; [`infer_policy.py`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/scripts/infer_policy.py) | `body_server.read` livre positions, temps simulateur et tronc, **pas** `data.ctrl` ni contacts ; `infer_policy` utilise par défaut BAM, ce n'est pas le même banc |

**Matrice de réutilisation :** réutiliser `ReadOnlyUnixRpc`, les tests
de provenance du `sim_flat_zone`, `sim_joint_trace`, P0h, `robotctl`
et la source OEM. **Adapter** `sim_joint_trace` avec option explicite,
validation stricte des trames et calcul de synthèse sans mémoire.
**Créer :** tests adversariaux et protocole de mesure ; **aucun**
pilote, service, IA, moteur, modèle, sous-module ou base supplémentaires.
Les PR OEM #381/#414 et les projets tiers du [registre C3](community-reference-registry-2026-10-26.md)
ne livrent pas à notre pin une preuve de contact ou de locomotion ; aucune
dépendance tierce importée.

## 3. Contrat de capture, sans contrôle moteur

Option `python3 -m microduck_companion.sim_joint_trace --joint-tracking`
(mode non activé par défaut), éventuellement avec `--verified-viewer`
si le viewer OEM est déjà démarré. **Un seul abonnement**
`robot.subscribe` à 1–10 Hz et **uniquement** `body_server hello/read`.
Traces bornées de 1 à 40 échantillons ; l'outil n'envoie jamais
`robot.move`, `robot.stop`, `policy load` ou cible articulaire.
La garde du processus/scene du simulateur épinglé reste obligatoire.

L'accusé `robot.subscribe` doit nommer `alpha_walking.onnx` et
`alpha_stand.onnx`, sans champ d'indisponibilité ; ce n'est **pas**
une empreinte du modèle exécuté à chaque tick. Pour chaque état,
validation stricte de `t_ns` (horloge MONOTONIC), 15 positions mesurées,
15 cibles finies dans l'ordre OEM, âge de trame, écart à la lecture
MuJoCo et progression des horloges. La ligne `mouth` non actionnée
n'entre pas dans les indicateurs des 10 joints de jambes.

**Mesures produites :** amplitudes des cibles et positions mesurées
par articulation des jambes, maximum de l'écart cible − mesure, qualité
de synchronisation et noms des politiques attestés par l'abonnement.
Ce sont des mesures du contrôleur `robotd`, **pas** la mesure indépendante
de `data.ctrl`, d'un contact ou de l'exécution d'une consigne. Le flux
`body_server` sert uniquement aux positions/tronc/horloges du simulateur,
sans prétention de simultanéité stricte avec le tick `robotd`.

Les JSON détaillés sont conservés sur le PC ; si `--output` est fourni,
seule la synthèse est affichée. Aucune image, voix, identité, image ONNX,
secret, média ou base SQLite dans le dépôt.

## 4. Séquence autorisée et critères de passage

1. **Fixtures et CI** : cas sain, identité de politique erronée,
   données absentes/mal formées/non finies, timestamp manquant,
   périmé/futur/répété, compétence inattendue, lecture hors scène,
   absence de commande motrice ; suite Python verte avant fusion.
2. **Contrôle passif au repos sur WSLg**, après mise à jour sûre de
   la copie locale, en réutilisant le simulateur déjà lancé.
   Procédure : [SIM-E2 trace graphique](sim-e2-manual-viewer-trace-2026-10-28.md).
   Une trame valide démontre seulement le bon fonctionnement de
   la collecte ; aucun nouveau `drive` à cette étape.
3. **Essai actif distinct, non autorisé par ce lot :** seulement après
   contrôle `robotctl health/version/policy list`, scène, contact,
   configuration et synchronisation ; comparer arrêt et mouvement de
   durée comparable, puis une seule commande OEM bornée avec propriétaire
   `robotd`, `robot.stop` confirmé, critères d'abandon sur état/horloge/
   équilibre/sécurité. Ne changer ni ONNX ni actionneur pour « obtenir
   une marche » avant mesure contrôlée.
4. Aucune récompense/mise à jour de préférence ou causalité d'objet
   sur les traces `robot.state` ou sur une translation sans preuve
   de démarche. Le robot réel reste absent ; Cat-A2b #78 et EX4-C2 #80
   ne sont pas débloqués.

**Résultat visé du lot :** un outil de diagnostic passif cohérent et
testé PC-fixtures, **pas** une locomotion MuJoCo validée.

## 5. Première capture WSLg réelle au repos — 28/10/2026

**Observation opérateur, pas fixture ni robot physique :** le serveur MuJoCo avait été arrêté (`body.pid` ancien, port 7801 absent) et a été redémarré par `scripts/duck-sim up` dans la configuration OEM épinglée, sans nouvelle consigne de marche. La nouvelle capture `--verified-viewer --joint-tracking` a alors réussi avec `--samples 8 --hz 4`, sauvegardée uniquement sur le PC dans `$HOME/kwipi-joints-idle.json` (fichier non joint au dépôt).

| Contrôle | Valeur rapportée |
| --- | --- |
| Posture | Debout, tronc 0,116 m, gravité Z −1 ; IMU prête |
| Politiques nommées par `robot.subscribe` | `alpha_walking.onnx` et `alpha_stand.onnx` (pas de SHA par tick) |
| Mesures et commandes | 8 échantillons de repos, **0 commande** émise par la sonde |
| Âge maximal du tick `robotd` à réception | 0,003134575 s |
| Écart temporel maximal tick `robotd` / lecture MuJoCo | 0,067031184 s |
| Pic absolu cible−mesure : hanche roll G / D | 0,216218607 / 0,207708166 rad |
| Pic absolu cible−mesure : genou G / D | 0,204887088 / 0,188733563 rad |

Les cibles et positions proviennent de la **même trame `robot.state`** ; le snapshot MuJoCo distinct n'est pas simultané. Les valeurs ci-dessus sont les **maxima absolus sur les huit trames**, pas des moyennes, pas des écarts permanents démontrés ni des preuves de panne. La littérature constructeur épinglée emploie un asservissement de position MJCF avec gain mis à l'échelle par `kp/200` et des limites de force ; il peut y avoir de l'écart à l'équilibre sous charge, mais **le rôle causal exact est inconnu**. De plus, `robot.state.targets` est publié avant `safety.apply` et ne certifie pas l'écriture vers `data.ctrl` ou les contacts de pieds.

**Statut :** l'option de diagnostic est **codée, testée CI sur fixtures et essayée avec succès en mode passif sur WSLg/MuJoCo OEM**. Aucun test de marche nouveau, aucune preuve de locomotion ou de sécurité robot réelle. [Journal de preuve #101](https://github.com/Jean-Philippe56520/Microduck/issues/101#issuecomment-6467541251).

**Suite avant nouvel essai actif :** lire uniquement le JSON détaillé **local** déjà acquis, en agrégeant la moyenne **signée** et l'étendue temporelle des écarts cible−mesure, les labels `policy` et `limited_by`. Ne pas poster le JSON intégral ni modifier le modèle, les gains ou le contrôleur. Comparer les résultats à la configuration `chosen_actuator` avant de formuler une expérience A/B contrôlée.

## 6. Analyse signée de la même capture au repos, sans nouvel essai

**Source :** calcul local de l'opérateur sur le JSON de huit trames déjà collectées à 4 Hz, le 28/10/2026 ([preuve dans #101](https://github.com/Jean-Philippe56520/Microduck/issues/101#issuecomment-6467856772)). Les huit labels sont `stand`, les huit listes de limitation contiennent `deadman`. L'absence de commande de marche explique l'état de repos et ne contredit pas l'ancien essai `walk` sans limitation.

| Articulation | Moyenne signée cible − mesure (°) | Min (°) | Max (°) | Étendue (°) |
| --- | ---: | ---: | ---: | ---: |
| `left_hip_roll` | −11,64 | −12,39 | −10,94 | 1,45 |
| `right_hip_roll` | +11,26 | +10,67 | +11,90 | 1,23 |
| `left_knee` | −10,83 | −11,74 | −10,37 | 1,37 |
| `right_knee` | +10,10 | +9,54 | +10,81 | 1,27 |

Les quatre écarts ont un **signe constant pendant ce bref relevé** (environ 1,75 s) et des signes opposés pour les jambes gauche et droite, dont la géométrie est en miroir. Ceci caractérise un offset quasi statique **sur cette courte fenêtre**, pas un biais à long terme, un défaut de conversion, une saturation ou une cause de marche démontrée.

**Relecture OEM épinglée (lecture seule) :** `robotd-params/src/lib.rs` définit par défaut `gain=200`, `standing_gain_ratio=0.8`, `standing_action_scale=1.0`; `robotd/src/control.rs` applique normalement un gain debout nominal de 160 si cette configuration est effectivement active. `microduck_rl/src/mjlab_microduck/sim/body_server.py` multiplie les gains de position MJCF par `kp/200`, et `robot_groundcontact.xml` donne à `chosen_actuator` un `kp` de 0.55 et une limite de force ±0.96. Ces mécanismes rendent possible un écart d'asservissement sous charge ; **le JSON stocké ne contient pas le gain actif** et ne relève ni `data.ctrl`, ni contacts, ni couple réel. Aucun correctif constructeur n'est donc justifié sur cette seule preuve.

**Réutiliser / adapter / créer :** réutiliser `sim_joint_trace`, `robotctl` et la configuration constructeur inchangés ; documenter seulement les statistiques locales, sans code ou second pilote. Le prochain essai potentiellement discriminant serait une paire témoin `stand` / commande `walk` à la même scène, au même intervalle et avec cibles + positions synchronisées, un seul départ OEM borné, contrôle des limites et `robot.stop` explicite confirmé. **Cet essai actif reste à autoriser distinctement après un protocole de sécurité complet** ; aucune nouvelle marche, installation, modification de policy, paramètre, moteur, mémoire ni sous-module par ce lot.

## 7. Confirmation OEM du gain `stand` et réutilisation des preuves de marche

Une lecture passive supplémentaire du `robot.state` sur le simulateur WSLg, **sans action motrice**, indique : `policy=stand`, `safety.gain=160`, `fallen=false`, `limp=false`, `limited_by=[deadman]`, avec les slots `alpha_walking.onnx` et `alpha_stand.onnx` annoncés. Le gain 160 correspond au réglage nominal `200 × standing_gain_ratio(0,8)` ; c'est la **valeur publiée par `robotd` à cet instant**, pas une mesure du couple ou du gain MJCF dynamique de cette session.

**Vérification de réutilisation réalisée avant nouvel essai moteur :** les rapports déjà intégrés [P0d](mujoco-p0d-live-solver-2026-10-25.md) (consignes `data.ctrl`, positions, contacts), [P0e](mujoco-p0e-actuator-gains-2026-10-25.md) (gain effectif et loi de force du modèle dans les fenêtres enregistrées : **0,44 debout sur 79/79 ; 0,55 en marche sur 123/127 et 0,44 sur 4/127 ; aucune saturation parmi 2 884 relevés**), [P0j](mujoco-p0j-load-transfer-2026-10-25.md) (**127/127** trames de marche à deux pieds chargés au seuil 0,1 N) et [P0i](mujoco-p0i-controlled-policy-pair-2026-10-25.md) (A/B alpha contre VelStand, sans locomotion validée) traitent déjà une large partie des questions initiales. Les gains sont ceux du **modèle MJCF sous CI headless**, pas un diagnostic matériel ni une mesure directement indépendante de cette session WSLg.

**Décision :** aucune nouvelle acquisition ou commande active uniquement pour répéter gain, cibles et contacts. Priorité à la lecture des données originales archivées, si toujours accessibles, et au [contrat P0f](mujoco-p0f-policy-contract-2026-10-25.md), notamment incertitude du transfert entraînement→`duck-sim` et absence de preuve de propulsion unipodale. N'entreprendre un essai moteur spécifique qu'après avoir formulé une hypothèse **non couverte**, un témoin approprié et un arrêt OEM vérifié. [Trace et interprétation #101](https://github.com/Jean-Philippe56520/Microduck/issues/101#issuecomment-6468070520).
