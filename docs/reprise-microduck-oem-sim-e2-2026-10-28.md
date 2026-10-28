# Point de reprise — Microduck Companion / Kwipi — 28 octobre 2026

**Document de continuité après réinitialisation de conversation.** Vérifier GitHub, le SHA de main, les PR et les fichiers effectivement installés **avant** toute affirmation ou modification. Priorité au [plan d'action](plan-action.md), aux [instructions permanentes](microduck-companion-instructions-permanentes-2026-10-28.md) et au [protocole de réutilisation](development-reuse-protocol.md).

## 1. État GitHub vérifié lors de cette reprise

- PR [#103 SIM-E2-A](https://github.com/Jean-Philippe56520/Microduck/pull/103) **fusionnée** en `main` (squash `079e6fc088327f69776ad5db17030438b746ffbd`) ; [CI #40658582383](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40658582383) **1 410 tests, 31 ignorés, aucun échec**. La trace passive graphique `--verified-viewer` est intégrée.
- [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101) **ouverte** : locomotion du simulateur non résolue ; les mesures manuelles anonymisées sont enregistrées dans l'issue.
- [Cat-A2b #78](https://github.com/Jean-Philippe56520/Microduck/issues/78) **ouverte** : vérité terrain indépendante et reconnaissance basse encore à démontrer.
- PR [#97](https://github.com/Jean-Philippe56520/Microduck/pull/97) (stratégie Qwen 9B), [#98](https://github.com/Jean-Philippe56520/Microduck/pull/98) (F5 v2) et [#99](https://github.com/Jean-Philippe56520/Microduck/pull/99) (F5 v3) **ouvertes, non fusionnées** lors du contrôle. `docs/kwipi-oem-qwen9b-realistic-plan-2026-10-27.md` est dans la branche de la PR #97, **absent de main** ; ne jamais le présenter comme livré.
- OEM épinglé : `upstream/microduck` `942e58e3aa6dbb28e7037203fff11866122c7567`; RL `upstream/microduck_rl` `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Ne pas modifier les sous-modules sans accord.

## 2. État des essais WSL2 / MuJoCo déclarés par l'opérateur

- Windows 11, Ubuntu WSL2/WSLg : fenêtre MuJoCo OEM affichée ; boucle `robotd` **50,0/50,0 Hz, 0 tick manqué**, bus OK, IMU prête, robot debout (tronc ~0,116 m) ; simulation à **1,00×** en temps réel. Pas de robot physique.
- `DUCK_SIM_RL=$HOME/Microduck/upstream/microduck_rl` ; `DUCK_SIM_STATE=$HOME/.cache/kwipi-visual` lors de ces essais ; variables à réexporter dans un nouveau shell Ubuntu. `python3` système 3.14.4, simulateur utilise son venv Python distinct. Ne pas confondre PowerShell Windows et Bash Ubuntu.
- Premier essai `duck-sim drive 0.05 0` : commande envoyée, pas de déplacement visible ; sans trace active exploitable.
- Trace passive graphique au repos : 8 échantillons (1,74 s), **8 `stand`, 8 `deadman`**, vitesse appliquée nulle, déplacement net XY **0,595 mm**. `deadman` au repos n'explique pas la marche.
- **Essai actif instrumenté** : `duck-sim drive 0.08 0`, ~8 s ; 32 échantillons pendant les consignes, **31 `walk`, 1 `stand`, zéro limitation de sécurité**, vitesse de consigne appliquée montée à **0,08 m/s**. **Déplacement net XY 3,500 mm**, trajectoire cumulée 4,575 mm. Consigne appliquée ≠ vitesse physique. Locomotion **non démontrée**.
- Amplitudes en marche, max-min de positions mesurées : hanche yaw G/D 1,36°/2,03° ; roll 0,48°/0,45° ; pitch 2,61°/2,16° ; genou 0,69°/1,28° ; cheville 3,71°/0,64°. Peu de mouvement des jambes ; ne pas conclure que le réseau ONNX est fautif.
- Capture `robotctl monitor` **au repos** : `stand`, `deadman`, ONNX `alpha_walking/alpha_stand`, 50 Hz, ToF simulé 15 Hz ; écarts commande/mesure visibles, p. ex. hanche gauche roll -0,336 / -0,088 rad et genou gauche -0,181 / +0,024 rad. Valeurs ponctuelles **au repos**, pas preuves pendant la marche.
- L'opérateur a confirmé trois fichiers `velstand.onnx`, `alpha_walking.onnx`, `alpha_stand.onnx`, chacun ~776 Kio dans `$DUCK_SIM_STATE/policies/current`. Le **28/10/2026, leurs trois SHA-256 locaux ont été reçus et comparés avec succès à P0h/v8** (tableau en section 4).

## 3. Comparaison OEM impérative avant tout nouvel essai

L'[audit P0h déjà fusionné](mujoco-p0h-policy-slot-lineage-2026-10-25.md) établit une différence : configuration `robotd` ordinaire OEM **`velstand.onnx` sans `stand` séparé** ; le script officiel `scripts/duck-sim` sélectionne explicitement **`alpha_walking.onnx` + `alpha_stand.onnx`**. Réutiliser les trois fichiers OEM et `robotctl monitor`; ne pas déclarer qu'un seul est défectueux.

Le RL officiel `scripts/infer_policy.py` utilise par défaut `bam.mujoco.MujocoController` (actuateur XL330 BAM) ; `sim/body_server.py` de `duck-sim` écrit des cibles dans les actionneurs MJCF et règle leurs gains. Les scènes de vitesse et contact ne sont pas interchangeables. Ce sont des **différences à auditer**, pas des causes établies. La trace passive actuelle **n'expose ni contacts des pieds ni cibles articulaires** ; `robotctl monitor` montre les cibles OEM dans le flux d'état.

## 4. Vérification ONNX locale réalisée et diagnostic OEM restant

**Preuve rapportée par l'opérateur, 28/10/2026 :** `sha256sum` en lecture seule sur les trois fichiers existants dans `$HOME/.cache/kwipi-visual/policies/current/`. Aucun moteur, politique, service, paramètre ou sous-module modifié.

| Fichier | SHA-256 local reçu | Comparaison [P0h/v8](mujoco-p0h-policy-slot-lineage-2026-10-25.md) |
| --- | --- | --- |
| `velstand.onnx` | `2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492` | Identique |
| `alpha_walking.onnx` | `e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c` | Identique |
| `alpha_stand.onnx` | `1569268713e40deea795dd2922dba50d3621e15a872855408b6b1b125b1c094b` | Identique |

**Portée de la preuve :** les fichiers locaux sont bit à bit identiques à ceux déjà audités par P0h dans le bundle déclaré v8 ; une corruption ou divergence de contenu de ces trois fichiers par rapport à cette référence n'est pas observée. La source/manifeste v8 ne constitue pas une signature du checkpoint d'entraînement. Cette comparaison ne prouve ni le chemin effectivement chargé par `robotd` à chaque tick, ni la justesse des entrées/sorties ONNX en boucle fermée, ni la démarche.

**Lecture des sources constructeur épinglées, sans moteur :**
- [`robotd-params/src/lib.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd-params/src/lib.rs) : par défaut `walk=velstand.onnx`, pas de `stand` distinct ; [`scripts/duck-sim`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/scripts/duck-sim) : paire alpha explicitement configurée. La trace opérateur active annonce `walk` mais pas un SHA de session à chaque tick.
- [`robotd/src/control.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/control.rs) : observation, inférence, conversion des 14 actions en cibles de position, échelle et filtres ; l'étape seule ne prouve pas le suivi des cibles par la physique.
- [`mjlab_microduck.sim.body_server`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/src/mjlab_microduck/sim/body_server.py) : `set_targets` écrit dans `data.ctrl` des actionneurs MJCF, `read` renvoie positions/vitesses/tronc mais pas cibles ni contacts. [`infer_policy.py`](https://github.com/pollen-robotics/microduck_rl/blob/b02fdea4902c2b93b7d34a83a6f05da4ececb7d3/scripts/infer_policy.py) emploie par défaut le contrôleur BAM, non interchangeable avec `duck-sim` sans mesure.
- `robotctl monitor` sait afficher les angles commandés/mesurés par `robotd` ; la seule capture antérieure communiquée était **au repos**. Les 32 observations de `sim_joint_trace` pendant la commande ne comportent **ni cibles ni contacts**. On ne peut donc pas départager sorties ONNX trop faibles, filtres/échelles, suivi des actionneurs ou glissement/contact.

**Décision / étape suivante :** réutiliser P0h, `robotctl monitor`, `sim_joint_trace` et les journaux OEM existants. Examiner les configurations et traces disponibles **en lecture seule**. Si la capture des cibles pendant mouvement exige un nouveau run, concevoir d'abord un protocole séparé avec hypothèses, témoin de durée comparable, critères de stop, synchronisation et contrôle de versions ; ne pas lancer un `drive`, modifier `policy load`, réentraîner, toucher aux moteurs ou attribuer une récompense maintenant. Aucun correctif OEM ni nouveau pilote n'est justifié à ce stade.

Le `robotctl version` local peut afficher `rev unknown` (build non CI), et `installed daemon none` (absence de release installée sur ce PC) : ces chaînes **ne prouvent pas** un défaut des démons vivants ; consulter `health` et l'environnement réel.

## 5. Règle opérationnelle de reprise

**Ne pas repartir d'une hypothèse d'assistant** : état GitHub + docs autoritaires + configuration réellement chargée → audit réutiliser/adapter/créer → mesure passive → essai borné si justifié → conclusion mesurée → PR ciblée avec CI → documentation. Ne pas publier médias privés, identité, journaux bruts de l'opérateur ou données de foyer. Résultat de simulation ≠ autonomie physique.
