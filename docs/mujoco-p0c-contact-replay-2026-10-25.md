# P0c — Reconstruction géométrique hors ligne des pieds (25 octobre 2026)

**Statut : testé avec le MuJoCo officiel épinglé, pas de locomotion validée.** Ce rapport décrit l'essai [GitHub Actions #40188553954](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954), inclus dans la [PR #13](https://github.com/Jean-Philippe56520/Microduck/pull/13). Le workflow a réussi techniquement, y compris les **179 tests Python**. Il ne démontre pas de marche ni de comportement sur un robot physique.

## Objectif et méthode

Le protocole constructeur `body_server.op=read` fournit la pose du tronc et ses angles articulaires, mais **pas les contacts dynamiques, impulsions, efforts normaux/tangentiels ni les consignes articulaires**. L'outil P0c ne modifie **aucun** fichier OEM, politique, seuil ou garde-fou. Il enregistre désormais le quaternion WXYZ OEM complet (`imu.quat`) à côté des 15 positions articulaires du relevé P0b.

Après la fin de l'**unique** essai moteur J2e existant et la confirmation de `robot.stop`, la commande **hors ligne** `microduck_companion.sim_contact_replay` :

1. Rejette les anciennes traces sans quaternion, les états incomplets, modifiés, invalides ou non issus du MuJoCo épinglé.
2. Vérifie la révision Git `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` et le blob de la scène plane `a3848be52113a50138d54921748733f09488d496`.
3. Charge `scene.xml` dans un **nouveau** `MjModel/MjData` local, reconstitue chaque `qpos` de tronc et articulations, et exécute seulement `mujoco.mj_forward` (**jamais** `mj_step`). Les vitesses inconnues du tronc sont mises à zéro **uniquement pour la reconstruction**, sans prétendre rétablir l'état dynamique d'origine.
4. Identifie explicitement les paires géométriques `floor`/`left_foot_collision` et `floor`/`right_foot_collision`, leur distance signée et les positions reconstruites des sites de pieds. Aucun accès réseau au robot, aucune commande, aucune lecture de mémoire du processus constructeur.

**Attention :** les paires créées par `mj_forward` sont des **candidats de contact dans un état reconstruit**. Ce ne sont pas les enregistrements du solveur pendant la trajectoire originale. La géométrie statique ne prouve ni force, ni friction, ni glissement, ni alternance réelle d'appuis. La scène compilée utilise son pas par défaut ; le `body_server` peut configurer un pas différent. Cela n'affecte pas l'objectif de recherche de proximité géométrique mais interdit de déduire des forces dynamiques.

## Résultats observés lors de l'essai P0c

| Observation issue de la reconstruction | Repos `stand` | Essai borné `walk` |
| --- | ---: | ---: |
| Échantillons à 10 Hz | 16 | 24 (23 `walk`, 1 `stand`) |
| Les deux semelles montrent un chevauchement géométrique avec le sol | **16/16** | **24/24** |
| Aucun chevauchement des deux semelles dans le relevé | 0/16 | 0/24 |
| Distance signée minimale pied gauche / sol, étendue | −0,429 à −0,368 mm | −0,390 à −0,289 mm |
| Distance signée minimale pied droit / sol, étendue | −0,413 à −0,381 mm | −0,534 à −0,354 mm |
| Nombre maximal de candidats par relevé (deux pieds) | 5 | 6 |

**Interprétation stricte :** les géométries des deux semelles restent en légère intersection avec le plan à **chacun** des 40 instants relevés. Les distances négatives de quelques dixièmes de millimètre sont compatibles avec des contacts souples de MuJoCo et ne doivent pas être interprétées comme une pénétration dangereuse, un pied plaqué par un blocage ou une preuve de traction. À 10 Hz, un décollage entre deux trames peut rester invisible. Les sites `left_foot`/`right_foot` sont des points géométriques, pas des capteurs de force ni des mesures directes de distance entre semelle et sol.

### Résultat de l'essai moteur lié (nouvel essai P0c, distinct de P0b)

- **24 commandes** à 0,12 m/s, `robotd` rapporte `walk` sur **23/24** notifications et une vitesse appliquée maximale ~0,12 m/s.
- **Déplacement net final XY : 1,997 mm**, dont **X monde +1,776 mm** et **Y monde +0,913 mm** ; dérive de la baseline propre à cet essai : **0,063 mm**.
- `robot.stop` explicitement confirmé, mémoire SQLite : `no_progress_observed` ; seuil proposé de 10 mm **non atteint**.
- Ce **nouvel essai** ne remplace ni le résultat historique P0b de **1,338 mm**, ni les quatre essais antérieurs J2e (0,820–2,574 mm).

## Niveaux de preuve et conclusion

- **Codé :** enregistrement du quaternion officiel, lecture de traces P0b complètes, reconstruction et classification géométrique indépendantes.
- **Testé :** 179 tests Python sur GitHub Actions ; essai [MuJoCo headless réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954) ; JSON `contact-replay.json` dans l'artefact `mujoco-headless-diagnostics` avec `walk-comparison.json` et logs.
- **Observé dans la reconstruction :** proximité/intersection géométrique des deux semelles au sol à 40 instants échantillonnés.
- **Toujours inconnu :** contacts originaux du solveur `MjData.contact` au moment du contrôle, forces et impulsions de pied, coefficient de friction effectivement sollicité, action ONNX et cibles par articulation, éventuel glissement, cause de l'absence de marche.
- **Non validé :** démarche stable, translation au-dessus de 10 mm, sécurité et locomotion physiques.

## Suite — P0d proposé, sous protection constructeur

Étudier une **instrumentation facultative en lecture seule du solveur** dans un processus MuJoCo de diagnostic indépendant, sans modifier les sous-modules suivis, puis documenter explicitement son impact sur la reproductibilité. Elle devra capter `data.contact`, les forces calculées et les valeurs de cibles effectivement appliquées **au même tick**, avec une provenance et une cadence vérifiées, sans ralentir ni piloter `robotd`. Comparer ensuite contrôle/moteurs/contacts/translation. **Ne pas** modifier aveuglément les gains, la vitesse, le deadman, les politiques ou le modèle officiel pour atteindre artificiellement 10 mm.

**Reproduction manuelle après collecte P0b (Python de la `.venv` MuJoCo officielle, exécution locale seulement) :**

```sh
upstream/microduck_rl/.venv/bin/python -m microduck_companion.sim_contact_replay \
  --rl-root upstream/microduck_rl \
  --input /tmp/duck-sim-companion/walk-comparison.json \
  --output /tmp/duck-sim-companion/contact-replay.json
```

Cette commande est **hors ligne** et peut être exécutée uniquement sur une trace P0b récente avec quaternion complet et arrêt confirmé ; les précédentes archives P0b sans quaternion sont intentionnellement rejetées.

