# P0i — Comparaison contrôlée de politiques : paire alpha contre VelStand

**Date :** 25 octobre 2026. **État : fusionné dans `main` ([PR #21](https://github.com/Jean-Philippe56520/Microduck/pull/21)), codé et testé sous MuJoCo constructeur.** [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915) et [comparaison A/B officielle réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528), avec deux arrêts confirmés et **aucune translation supérieure à 10 mm**. Aucun robot physique testé. **Cause de non-marche inconnue.**

## Question expérimentale

Les essais J2e sous `duck-sim` ont demandé 0,12 m/s mais n'ont mesuré qu'environ 0,8 à 2,6 mm de translation nette. P0h a identifié que `duck-sim` force deux réseaux anciens (`alpha_walking`, `alpha_stand`), tandis que le mode marche constructeur ordinaire emploie `velstand` seul. **P0i examine ce seul facteur**, sans modifier les pilotes, la scène, la commande, le gain, les limites, les capteurs ou les sources OEM. Cette comparaison préliminaire en deux sessions ne prouve pas à elle seule la causalité.

## Procédure

Les deux sous-modules sont épinglés, propres et vérifiés (code constructeur `942e58e3aa6dbb28e7037203fff11866122c7567` ; simulateur RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`).

1. Démarrer `scripts/duck-sim up` sur l'environnement constructeur `SIT`, sans viewer ni caméra ; vérifier la scène plane et la nature du `body_server`.
2. **Bras A :** conserver `alpha_walking.onnx` et `alpha_stand.onnx`, configuration explicitement injectée par le lanceur officiel. Vérifier le **fichier actif `robotd-duck-a.toml`** (`robotd.toml` n'est que le modèle de génération), les chemins lus en direct via `robotctl policy list --json`, le manifeste v8 et les SHA-256 exacts publiés dans [P0h](mujoco-p0h-policy-slot-lineage-2026-10-25.md).
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

## Résultats vérifiés du protocole A/B

[Workflow MuJoCo officiel #40221935528](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) : **succès de la procédure**, et non succès de locomotion. Les fichiers `p0i-alpha.json`, `p0i-velstand.json`, `p0i-comparison.json` et les logs sont archivés.

| Variable mesurée | A : alpha | B : VelStand |
|---|---:|---:|
| Net XY du tronc | **1,443665 mm** | **1,967688 mm** |
| Avance X | 0,674686 mm | 1,885973 mm |
| Dérive Y | 1,276310 mm | 0,561162 mm |
| Dérive de référence sans mouvement | 0,032997 mm | 0,345584 mm |
| Durée simulée de l'essai | 2,80 s | 3,32 s |
| `robot.state.policy=walk` | 23/24 | 24/24 |
| Maximum vitesse appliquée | 0,120 m/s | 0,120 m/s |
| `robot.stop` | Confirmé | Confirmé |
| Déplacement ≥ 10 mm | Non | Non |
| Résultat SQLite indépendant | `no_progress_observed` | `no_progress_observed` |

Deux PID distincts ont été vérifiés pour le `body_server` (**13556** et **15317**) ; chaque journal SQLite est neuf (une expérience par base), la récompense `-0.5` est explicitement relative **à ces résultats simulés** et la préférence d'exploration passe de 0 à `-0.075` dans chaque base, sans prétendre à un entraînement de réseau.

**Écart observé VelStand − alpha : +0,524023 mm de distance XY**, très inférieur au seuil de 10 mm ; il ne permet pas de départager les politiques en matière de propulsion. Les deux séquences ont été bornées à 24 notifications, soit **48 au total sur l'exécution réussie**. Le protocole a contrôlé les chemins ONNX réellement signalés par `robotctl policy list --json` ; `walk=velstand` et `stand=none` ont été confirmés pour B.

### Première tentative refusée et correction

La [première CI MuJoCo #40221380012](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221380012) a mesuré **1,567156 mm** sur le bras alpha (24 notifications, `robot.stop` confirmé), puis a **refusé le bras B sans commande motrice** : le contrôle utilisait `$STATE/robotd.toml`, qui est **un gabarit OEM**, et non `$STATE/robotd-duck-a.toml`, véritable paramètre du daemon (`--params`). La correction a aligné `robotctl policy load` et la validation en lecture seule sur le fichier actif, avec un test de non-confusion des deux chemins. Aucune condition de sécurité n'a été désactivée. La mesure A du premier essai reste historisée ; le tableau ci-dessus est exclusivement celui des deux bras d'une même exécution CI finale réussie.

## Limites

La comparaison n'est pas parfaitement randomisée : `duck-sim` démarre sur la paire alpha, tandis que le bras VelStand nécessite **un changement de politique à chaud après le démarrage**. Les états du contrôleur et les transitoires après changement peuvent être des facteurs de confusion. Deux essais ne suffisent pas à quantifier la variance, la vitesse de marche soutenue, la stabilité réelle, les contacts pied-sol ou les forces articulaires exactes. Aucun portage physique ou augmentation de vitesse n'est autorisé par P0i.

**Décision : P0i valide le bon fonctionnement du banc de comparaison, pas une marche.** Les deux politiques ne dépassent pas le seuil de 10 mm ; **P1a reste bloqué**. Un diagnostic ultérieur, séparé, devra examiner le manque de propulsion dynamique (contacts, interaction commande/sol, temps de simulation, capteurs/états internes) sans contourner `robotd`, ou poursuivre indépendamment la perception et la cognition immobiles. Ne pas lancer automatiquement de nouveau test moteur.
