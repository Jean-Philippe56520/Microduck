# SIM-1B — Première chaîne caméra OEM MuJoCo → YOLOX PC → F2 mock (05/11/2026)

**Statut : candidat logiciel, PR #322, non qualifié en MuJoCo vivant.**
Source de vérité : `docs/plan-action.md`. Réutilise strictement `sim_media_frame.py` (PR #321), `sim_bridge.py`, `cata_yolox_categories.py`, `yolox_attention_candidates.py` et `sim_vis_d_new_scenes_f2_fixture.mock_f2_from_regions`.

## Le changement réel

Le programme `python3 -m microduck_companion.sim_vis_oem_cycle` relit la télémétrie du `robotd/tofd` simulé et exige sa cohérence (≥45 Hz, fraîcheur ≤2 s, sûreté de base). Il demande UNE trame UYVY brute à **`mediad` OEM** par `media.frame` sur socket Unix. Il convertit les pixels en JPEG temporaire en mémoire, respecte l'angle `rotate`, charge **uniquement** le Nano ONNX SHA `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` sur CPU PC, extrait 0–3 régions à seuils et NMS inchangés, puis réutilise **le F2 actuel dans sa voie `mock`**. L'impression JSON permet de voir la décision, les régions et les refus. **Aucun média n'est enregistré**, pas de commande moteur, d'effet, de récompense ou d'apprentissage.

Le signal d'image est bien destiné au socket `mediad`, mais ni l'identité du processus serveur ni la correspondance au **même pas MuJoCo** que `robotd/tofd` ne sont authentifiées. L'heure de capture vient du champ OEM `captured_at_unix_us` ; sa projection en monotone local est approximative et explicitement non synchronisée. Le détecteur renvoie des **hypothèses COCO, pas des catégories observées** ; le F2 reçoit `unknown` en `mock` et ne peut que choisir une attention non motrice. Aucune identification de balle/personne n'est prouvée.

## Porte et essais fixés avant première campagne OEM

| Cas | Attendu | Arrêt |
| --- | --- | --- |
| P1 — capture OEM valide, télémétrie 50 Hz cohérente et région score ≥0,80 | possible `inspect unknown`, jamais d'action | mauvaise provenance, trame invalide, objet invisible |
| N1 — score 0,25–0,79 ou aucune région | `idle` | `inspect` injustifié |
| N2 — `robotd/tofd` manquants, lents ou périmés | `STOP`, aucune inférence si porte initiale manquante | décision visuelle affirmée |
| N3 — UYVY tronqué, angle illégal, en-tête invalide ou capture périmée | `STOP`, aucun média sauvé | flux accepté |
| N4 — classe COCO `person` hypothétique | cible F2 `unknown`, source `mock` | personne vérifiée/identité |
| C0 — comparateurs historiques SIM-VIS-D, X2-C | pas de prétention à nouveauté de leurs capacités propres | CI fixtures comptée comme test OEM |

**Succès de la qualification logiciel** : tests positifs/négatifs Python et CI complète verte. **Succès MuJoCo non encore acquis** : processus `mediad` et `robotd/tofd` réellement lancés, trame valide + logs du même scénario, sortie JSON mesurée, absence de moteurs envoyés par Companion. Si une porte manque, garder **`STOP / inconnu`** ; ne pas modifier seuils, scène, modèle, constructeur ni inventer une détection.

## Lancer manuellement sur WSL2 *après validation de la PR*

Ce bloc ne s'exécute pas depuis ChatGPT : il nécessite un checkout local, les politiques OEM, le simulateur et l'ONNX déjà installés. **Ne pas lancer sur un robot physique.** Le `mediad` officiel peut ouvrir une console Web sur le réseau local non authentifiée ; travailler sur un poste/réseau de confiance, sans compte distant ni ouverture de port.

Dans le checkout du projet :

```sh
git submodule status
export DUCK_SIM_RL="$PWD/upstream/microduck_rl"
export DUCK_SIM_STATE="$HOME/.cache/duck-sim-companion-vision"
export DUCK_SIM_PORT=17801
export DUCK_SIM_FRAME_PORT=17901
export DUCK_SIM_DUCKS=1
export DUCK_SIM_VIEWER=0
export DUCK_SIM_CAMERAS=a
export DUCK_SIM_SCENE=ball
# Chemin réel de VOTRE checkpoint vérifié, à renseigner localement.
export YOLOX_NANO_ONNX="/chemin/absolu/yolox_nano.onnx"
test -f "$YOLOX_NANO_ONNX" || { echo "STOP_NO_MODEL"; exit 1; }
# Lancer les services OFFICIELS OEM et MuJoCo dans cet environnement de test.
"$PWD/upstream/microduck/scripts/duck-sim" up
"$PWD/upstream/microduck/scripts/duck-sim" status
"$PWD/upstream/microduck/scripts/duck-sim" ctl health
python3 -m microduck_companion.sim_vis_oem_cycle \
  --state-dir "$DUCK_SIM_STATE" --model "$YOLOX_NANO_ONNX"
# À la fin de la séance contrôlée :
"$PWD/upstream/microduck/scripts/duck-sim" down
```

La console vidéo officielle, si `mediad` fonctionne, est `http://127.0.0.1:8080/`. **Ce n'est pas** la trace décisionnelle : celle-ci est imprimée dans le terminal. La scène constructeur `ball` contient une balle, mais **sa visibilité caméra à l'instant de capture n'est pas présupposée**. Le script OEM `duck-sim` peut initialiser sa posture de station debout ; ce mouvement constructeur ne vient pas de Companion.

Si le lancement constructeur, `mediad`, son pipeline GStreamer, les politiques ou les droits des sockets échouent, **ne pas forcer une simulation factice** ; rapporter le STOP exact.

## Risque, preuve, retour arrière

- **Faits déjà distincts** : SIM-VIS-D a exploité des images/GT MuJoCo *statiques* sans `mediad` ; X2-C a réellement lu `robotd/tofd` mais sans caméra. Le nouveau raccordement n'a pas encore démontré l'association sur les services vivants.
- **Mémoire** : réutilisation par F2 d'une seule `ExperienceMemory(":memory:")` éphémère **sans écritures**, pas de mémoire long terme, d'ablation mémoire on/off ni d'apprentissage. SIM-S1 a mesuré 0/6 changement d'attention grâce à la mémoire.
- **Action et effets** : zéro `robot.move`, `robot.do`, `robot.stop`, causalité, translation ou interaction ; SIM-E2/#101 et EX4-C2 restent bloquants pour SIM-3.
- **Périmètre temporel** : un seul cycle et une trame ; aucune réussite 2 Hz soutenue ni 95 % représentatif mesurée.
- **Repli** : supprimer uniquement `sim_vis_oem_cycle.py`, le test et la dépendance NumPy de CI si aucune autre preuve n'en a besoin ; le constructeur et tous les modules réutilisés restent inchangés.
