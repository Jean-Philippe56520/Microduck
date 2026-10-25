# P0j — Transfert de charge pied gauche/droit, relecture hors ligne du solveur MuJoCo

**Date : 25 octobre 2026.** **État : codé, testé logiciellement et reproduit sur l'archive P0e.** Aucune commande motrice, aucun redémarrage du simulateur et aucun test matériel dans ce lot.

- **Source de mesure :** [GitHub Actions P0e #40193139617](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617), archive `mujoco-headless-diagnostics`. L'essai source P0e avait 24 notifications de `robot.move` à 0,12 m/s et un `robot.stop` confirmé ; **P0j n'en émet aucune**.
- **Nouvelle vérification P0j :** [GitHub Actions #40229765655](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655) : **269 tests Python réussis** et replay du fichier JSONL original sur Ubuntu 24.04, **sans checkout des sous-modules ni démarrage de `robotd`/MuJoCo**. Rapport `p0j-load-transfer.json` archivé.
- **Révisions sources P0e :** `microduck_rl` `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, scène Git blob `a3848be52113a50138d54921748733f09488d496`.
- **Module :** `microduck_companion/sim_p0j_load_transfer.py` ; tests `tests/test_sim_p0j_load_transfer.py` ; workflow `.github/workflows/p0j-offline.yml`.

## Protocole et limites de validité

La sonde **P0e**, déjà exécutée auparavant, a enregistré un échantillon sur quatre appels d'origine `mj_step` (pas MuJoCo de 5 ms, soit **50 Hz** environ), sans modifier l'actionnement constructeur. P0j recalcule exclusivement sur l'archive immuable P0e :

1. Trois SHA-256 connus sont exigés avant analyse, avec un manifeste de source, `888` trames contiguës et la présence d'un arrêt confirmé dans la comparaison P0b. Toute troncature, mutation, mauvaise scène, valeur non finie ou séquence temporelle incohérente entraîne un **refus**.
2. Les fenêtres `stand` et `walk` proviennent du journal **P0b à 10 Hz**. Ce sont des intervalles temporels, **pas des étiquettes de la politique interne pour chaque pas du solveur à 50 Hz**.
3. Sur chaque instant, la charge gauche/droite est la somme des **forces normales d'origine du solveur MuJoCo** par pied. Le pied est « chargé » si sa force normale est **strictement supérieure à 0,1 N**, seuil purement diagnostique. La part relative gauche est `F_gauche / (F_gauche + F_droite)`.
4. Les déplacements calculés à partir des positions `foot_sites_solver_cache_xyz_m` sont des **trajectoires de sites mises en cache** ; ils ne mesurent **pas le glissement physique réel d'une zone de contact**. Les normes de forces tangentielles ne possèdent ni signe ni projection XY monde : **on ne peut pas en déduire une impulsion de propulsion orientée**.

Le module ne charge aucune politique ONNX, n'utilise pas de socket et n'envoie aucun mouvement. Il ne prétend pas résoudre la question de l'absence de locomotion.

### SHA-256 des données originales (P0e)

| Fichier de l'archive | Empreinte SHA-256 |
| --- | --- |
| `solver-tap.jsonl` | `7606cf8f06a944d7905b29b2a4b144eed304a05bbbf7bbb30d022f61965f8e39` |
| `solver-analysis.json` | `1be478752366e295f23ce37e970bb3ea994dcfbb5589985681d6399ef7013929` |
| `walk-comparison.json` | `e5dfc4a86039002e9cf75f62b0bbb9fb22cbde597df5dd2c2f1d849b3c56bb5a` |

Le fichier diagnostique archivé par Actions est soumis à la **rétention GitHub** ; ses données ne sont pas archivées durablement dans notre dépôt. Après expiration de l'artefact initial, les tests unitaires restent exécutables, mais une relecture complète nécessite une copie authentique des données P0e ou une nouvelle collecte indépendante explicitement autorisée. Ne pas substituer une source ressemblante sans réviser les contrôles de provenance.

## Résultats mesurés, même essai P0e

| Indicateur | Fenêtre `stand` | Fenêtre `walk` |
| --- | ---: | ---: |
| Relevés du solveur 50 Hz | **79** | **127** |
| Deux pieds chargés (> 0,1 N chacun) | **79/79** | **127/127** |
| Un seul pied chargé | **0/79** | **0/127** |
| Force normale moyenne gauche | 3,765 N | 3,220 N |
| Force normale moyenne droite | 3,470 N | 4,016 N |
| Part moyenne de la charge à gauche | **52,03 %** | **44,54 %** |
| Part minimale / maximale gauche | 46,81 / 56,33 % | 32,92 / 53,59 % |
| Franchissements de la part gauche de 50 % | 18 | 15 |
| Site pied gauche, trajet XY monde | 0,459 mm | 2,057 mm |
| Site pied droit, trajet XY monde | 0,602 mm | 2,216 mm |
| Tronc, longueur du chemin XY dans la fenêtre | 1,357 mm | 9,331 mm |
| Tronc, translation XY nette dans la fenêtre | 1,186 mm | 5,062 mm |

**Différence de répartition : −7,48 points de pourcentage de charge gauche** entre les deux fenêtres. La marche simulée observée est principalement en **double appui**, avec une charge moyenne plus élevée à droite. Les 15 franchissements du rapport gauche/droit ne constituent **pas** un appui unipodal : chaque pied conserve plus de 0,1 N dans tous les relevés.

Les valeurs de **5,062 mm** (déplacement net du tronc entre premier et dernier échantillons du seul intervalle de marche du solveur) et de **2,295 mm** (distance J2e finale relevée à un autre instant, après commande et arrêt dans P0e) portent sur **des bornes temporelles différentes** ; il serait incorrect de les confondre ou d'en conclure une progression réelle de 5 cm.

Les sites de pieds et la trajectoire du tronc n'indiquent ni le signe de la force de propulsion, ni l'adhérence effective du contact. Une « amélioration » de marche ne peut être déduite de ces valeurs seules.

## Vérification et décision

**Contrôles de reproductibilité :** les 3 SHA-256 exacts, 888 frames contiguës, 79/127 trames dans les fenêtres d'analyse, 2/2 charges en marche, absence de valeurs non finies, cohérence des comptages avec P0e, présence du stop et refus des fichiers modifiés. **12 tests nouveaux** sur données fictives ont été ajoutés ; **269 tests Python** et le replay de l'archive P0e ont réussi en CI.

**Conclusion :** les mesures rendent visible le changement de répartition d'appui entre repos et marche, mais **la cause du manque de propulsion reste inconnue**. Pas d'argument permettant d'ajuster le gain, le modèle ONNX, la vitesse ou les règles constructeur. **P1a reste bloqué** et aucun robot physique n'a été testé. Le prochain diagnostic éventuel serait une analyse *distincte* des composantes signées des forces de contact et de la cinématique pieds-sol sur un protocole OEM inchangé, sans modifier le pilotage ; sinon poursuivre la perception et la cognition sans déplacement.

### Relecture locale sans moteurs (si l'artefact P0e est disponible)

Après extraction de l'archive du run source dans un répertoire de travail :

```bash
python3 -m microduck_companion.sim_p0j_load_transfer \
  --solver-tap original/tmp/duck-sim-companion/solver-tap.jsonl \
  --solver-analysis original/tmp/duck-sim-companion/solver-analysis.json \
  --walk-comparison original/tmp/duck-sim-companion/walk-comparison.json \
  --output p0j-load-transfer.json
```

La relecture seule réussit uniquement sur les **octets originaux correspondants** ; cela évite d'attribuer à P0e des mesures provenant d'une autre exécution.
