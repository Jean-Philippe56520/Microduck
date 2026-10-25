# P0i — Comparaison contrôlée de politiques : paire alpha contre VelStand

**Date :** 25 octobre 2026. **État :** code P0i ajouté, **257 tests Python validés sur branche** ([CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221379918)). **Comparaison de locomotion MuJoCo constructeur en cours de contrôle** ([CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221380012)). Aucun test physique.

## Question expérimentale

Les essais J2e sous `duck-sim` ont demandé 0,12 m/s mais n'ont mesuré qu'environ 0,8 à 2,6 mm de translation nette. P0h a identifié que `duck-sim` force deux réseaux anciens (`alpha_walking`, `alpha_stand`), tandis que le mode marche constructeur ordinaire emploie `velstand` seul. **P0i examine ce seul facteur**, sans modifier les pilotes, la scène, la commande, le gain, les limites, les capteurs ou les sources OEM. Cette comparaison préliminaire en deux sessions ne prouve pas à elle seule la causalité.

## Procédure

Les deux sous-modules sont épinglés, propres et vérifiés (code constructeur `942e58e3aa6dbb28e7037203fff11866122c7567` ; simulateur RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`).

1. Démarrer `scripts/duck-sim up` sur l'environnement constructeur `SIT`, sans viewer ni caméra ; vérifier la scène plane et la nature du `body_server`.
2. **Bras A :** conserver `alpha_walking.onnx` et `alpha_stand.onnx`, configuration explicitement injectée par le lanceur officiel. Vérifier `robotd.toml`, les chemins lus en direct via `robotctl policy list --json`, le manifeste v8 et les SHA-256 exacts publiés dans [P0h](mujoco-p0h-policy-slot-lineage-2026-10-25.md).
3. Effectuer **une seule exécution** de la procédure `run_walk_trial` existante : pré-vol batterie, santé, zone plane sécurisée, horloge MuJoCo monotone et stabilité sans commande ; **24 notifications à 0,12 m/s** avec sondes à chaque tic, puis `robot.stop` confirmé et mesure de translation du tronc. Journal SQLite indépendant `p0i-alpha.sqlite3`.
4. Arrêter les services via `duck-sim down`, lancer **un nouveau `duck-sim up`**, avec une autre instance `body_server` (PID distinct), même scène, même posture initiale et mêmes paramètres.
5. **Bras B :** utiliser exclusivement **l'outil constructeur `robotctl policy load`** pour configurer `walk=velstand.onnx`, `stand=none`, puis recontrôler santé et configuration **en direct** de `robotd`. Ne pas modifier les sources/contrôles du fabricant.
6. Effectuer le même essai borné à 0,12 m/s, **une seule fois**, avec une nouvelle SQLite `p0i-velstand.sqlite3`. Stop et contrôle des données obligatoires.
7. Comparer seulement les mesures valides et conserver les rapports séparés `p0i-alpha.json`, `p0i-velstand.json` et `p0i-comparison.json`. Si la source, les états, la traçabilité, le stop, la progression de l'horloge ou les données sont incohérents, le programme **échoue au lieu de conclure**.

Le script ne démarre les deux essais **que sur la branche P0i**, avec `DUCK_SIM_POLICY_PAIR=YES` ; le module moteur exige en plus `MICRODUCK_SIM_P0I=YES` et `--enable-once`. Sur `main`, ces paramètres sont désactivés. `robotd` demeure l'unique autorité motrice ; les limites de vitesse, le `deadman` (500 ms) et le `robot.stop` officiel restent inchangés.

## Métriques et critères

- **Sécurité :** deux arrêts confirmés, 24 commandes par essai au maximum, pas de données constructeur modifiées ni d'essai hors de la scène plane épinglée.
- **Contrôle :** modèle ONNX effectivement chargé et chemin enregistré, `robotd` en mode marche, 24 échantillons `robot.state`, nombre d'échantillons `walk` et vitesse effectivement appliquée.
- **Translation :** déplacement net XY, déplacement avant X, dérive latérale Y, mouvement de référence sans commande, durée simulée et préférence/comportement enregistrés.
- **Seuil P1a indicatif :** 10 mm nets, seulement comme signal qu'une nouvelle vérification de locomotion serait justifiée ; **ce n'est pas une démonstration de démarche**.

La sortie porte toujours `causal_root_cause_proven=false` et `simulated_displacement_is_not_validated_gait=true`. Une amélioration isolée sur une seule exécution ne permet pas de conclure à une cause sans répétitions et contrôle de l'ordre des essais et du changement de réseau.

## Limites

La comparaison n'est pas parfaitement randomisée : `duck-sim` démarre sur la paire alpha, tandis que le bras VelStand nécessite **un changement de politique à chaud après le démarrage**. Les états du contrôleur et les transitoires après changement peuvent être des facteurs de confusion. Deux essais ne suffisent pas à quantifier la variance, la vitesse de marche soutenue, la stabilité réelle, les contacts pied-sol ou les forces articulaires exactes. Aucun portage physique ou augmentation de vitesse n'est autorisé par P0i.

**État à la sortie du jalon :** compléter les valeurs directement relevées dans la CI et arrêter le lot ; ne pas poursuivre automatiquement vers P1a.
