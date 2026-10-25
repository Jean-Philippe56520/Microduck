# P0g — Contacts compilés des trois variantes MuJoCo (25 octobre 2026)

**Preuve :** [MuJoCo officiel épinglé réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208635206), [214 tests Python sur branche P0g](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208638362). Trois variantes OEM sont compilées séparément depuis des copies temporaires de la scène plane vérifiée. Seul l'include XML est changé. La pose active STAND est restaurée et **un seul mj_forward par variante** est appelé, sans mj_step, sans robot.move et sans modification des sous-modules.

## Résultats numériques à la pose commune STAND

| Variante | Géométries compilées, sol compris | Éligibles aux masques du sol | Contacts statiques candidats |
| --- | ---: | ---: | ---: |
| robot_walk.xml (tâche vitesse) | **76** | **2** | **0** |
| robot_groundcontact.xml (scène headless) | **82** | **10** | **0** |
| robot_allcollisions.xml (VelStand) | **141** | **69** | **0** |

Dans les trois modèles, **21 coordonnées de pose STAND identiques**, tronc XYZ (0, 0, 0,12 m), quaternion (1,0,0,0), 16 corps, 20 degrés de liberté, 14 actuateurs, masse de modèle identique **0,73724318 kg**. Les masques de collision sol et semelles sont identiques (**contype=1 / conaffinity=1**, condim=3). Les paramètres compilés de contact des semelles et du sol sont identiques : **friction [1, 0.005, 0.0001] ; solref [0.02, 1] ; solimp [0.9, 0.95, 0.001, 0.5, 2]**. La priorité de contact vaut 0 dans les trois cas.

Les comptes ci-dessus sont des **géométries compilées** (différentes du nombre de balises XML du rapport P0f), et les masques ne modélisent pas toutes les exclusions. Le calcul statique ne comporte **aucun pas d'intégration ni relaxation sous pesanteur**. Les zéros candidats à cet instant initial ne prouvent pas que les pieds n'appuient pas en mouvement : P0d/P0e ont bien observé les deux pieds chargés sur les trames dynamiques. Aucune comparaison de forces ni aucune marche n'a été effectuée en P0g.

## Provenance et sûreté

- microduck_rl épinglé à b02fdea4902c2b93b7d34a83a6f05da4ececb7d3, arbre suivi intact ; blob de scene.xml a3848be52113a50138d54921748733f09488d496. Les répertoires temporaires réutilisent les assets officiels en lecture seule.
- L'ancienne clé STAND présente dans un commentaire du fichier constructeur a d'abord causé un refus diagnostique ; correction : lire les éléments XML actifs plutôt que compter les chaînes, avec test de régression.
- Les tests d'absence de mj_step, de modification des variantes ou de commande moteur passent. Les [diagnostics JSON archivés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208635206) contiennent les paramètres exacts, les masques et les états.

## Interprétation et suites

**La différence entre variantes compilées est confirmée, mais aucune cause de l'absence de marche n'est établie.** Les friction/solref/solimp sol/semelles ne présentent pas de différence dans cette comparaison ; les géométries des autres parties sont différentes et leur influence dynamique n'a pas été étudiée.

**Piste complémentaire P0h à confirmer :** la [documentation OEM épinglée des politiques](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/policy-channel-design.md) indique que velstand.onnx est devenu le slot de marche par défaut depuis le jeu v5, tandis que duck-sim épinglé charge alpha_walking.onnx au sein d'un jeu déclaré v8. Il faut vérifier la provenance des poids, la sélection réelle des slots et la compatibilité de ces versions avant tout essai. **Ne pas modifier une politique, un gain ou un garde-fou constructeur sans validation.**

**P1a reste bloqué :** dernier essai moteur P0e à **2,295 mm** avec stop confirmé, bien sous le seuil de 10 mm. **P2a** (autonomie fictive persistante) est intégré indépendamment ; **P2b** (plusieurs cycles passifs sur télémétries du simulateur) peut avancer sans locomotion. Aucun robot physique n'a été testé.
