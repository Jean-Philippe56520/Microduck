# P0h — Provenance et sélection des politiques ONNX (25 octobre 2026)

**État : codé et vérifié sur le simulateur constructeur épinglé.** [243 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219234669) et [CI MuJoCo officielle réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997). Aucun nouvel essai moteur depuis P0h.

PR : https://github.com/Jean-Philippe56520/Microduck/pull/20

## Découverte vérifiée dans les sources constructeur épinglées

Dans la révision constructeur `942e58e3aa6dbb28e7037203fff11866122c7567`, `robotd-params/src/lib.rs` (`PolicyParams::resolved_with`) détermine pour `Mode::Walk` :
- **`walk = velstand.onnx`** par défaut ;
- **`stand = None`** : `velstand` est utilisé même à vitesse nulle ; il sait marcher et se maintenir debout sans deuxième réseau.

À l'inverse, `scripts/duck-sim` écrit explicitement `robotd.toml` avec :
- `walk = alpha_walking.onnx` ;
- `stand = alpha_stand.onnx`.

Dans `duck-control/src/policy.rs`, `DEFAULT_STANDING_THRESHOLD=0.05` et `will_stand` exige un modèle `stand` présent, non désactivé, et une norme de vitesse au plus égale à ce seuil. `robotd/src/control.rs` choisit `Net::Stand` ou `Net::Walk` à partir de cette sélection. Dans la posture `Up`, sans commande de pose du corps ni autre compétence, les sélections théoriques sont :

| Commande avant, sans autre vitesse | `robotd` ordinaire par défaut | `duck-sim` actuel |
|---|---|---|
| 0 m/s | `velstand.onnx` | `alpha_stand.onnx` |
| 0,05 m/s | `velstand.onnx` | `alpha_stand.onnx` |
| 0,06 m/s | `velstand.onnx` | `alpha_walking.onnx` |
| 0,12 m/s | `velstand.onnx` | `alpha_walking.onnx` |

Ces lignes décrivent **l'intention du code en régime ordinaire**, pas une trace interne du modèle effectivement utilisé à chaque tic du contrôle.

## Provenance documentée, non cryptographique

Le script constructeur `scripts/seed-policies.sh` installe par défaut le bundle Hugging Face `pollen-robotics/microduck-policies` tag `v8`. Cette valeur est un minimum de version pour l'installation initiale, pas une garantie que toutes les cartes physiques exécutent encore exactement `v8`.

La documentation RL épinglée, `docs/velstand_policy.md`, attribue :
- `alpha_walking.onnx` à l'enseignant W&B `441tzs6d` / `model_3750.pt` ;
- `alpha_stand.onnx` à l'enseignant `69u48n8l` / `model_9750.pt` ;
- `velstand.onnx` v8 à `0045i2si` / `model_2749.pt`.

Ce sont des **déclarations de traçabilité dans les sources officielles**, pas des signatures permettant de rattacher les poids ONNX au checkpoint. Le fichier local `.source` et le `manifest.json` du bundle ne sont pas des attestations cryptographiques.

## Implémentation du diagnostic en lecture seule

`microduck_companion/sim_policy_lineage.py` :

1. Vérifie les révisions exactes de `microduck` et `microduck_rl`, l'absence de modification suivie et, en CI constructeur, le processus MuJoCo attendu.
2. Compare explicitement les règles de sélection de `robotd`, les chemins forcés dans `duck-sim`, le seuil et les lignes de provenance documentées.
3. Exige un bundle local `v8` cohérent : trois fichiers du même dossier, `robotd.toml`, `.source` et manifeste ; refuse toute pièce manquante, mélangée ou inattendue.
4. Calcule la taille et SHA-256 des **trois fichiers ONNX réellement installés**. Ouvre chaque modèle dans sa propre session CPU ONNX Runtime et vérifie le contrat `obs[1,61]` → `actions[1,14]`, avec état récurrent optionnel.
5. Calcule deux distances L2 entre sorties brutes sur observations **synthétiques indépendantes à historique nul** : `velstand` contre `alpha_stand` à vitesse nulle, puis `velstand` contre `alpha_walking` à 0,12 m/s.

**Précaution :** ces distances comparent des sorties sur une entrée artificielle. Les normalisations, états internes, amortissements et comportements en boucle fermée ne sont pas identiques ; une différence ne signifie pas que le modèle est meilleur, compatible ou responsable du défaut locomoteur.

## Vérifications

- [x] 243 tests Python sur branche (234 précédents et 9 nouveaux), y compris refus de sources/configurations modifiées, incohérences manifestes, présence des trois fichiers, sorties non finies, contrôle de priorité et absence de preuve de démarche.
- [x] [MuJoCo constructeur et ONNX installés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) réussis, **sans commande `robot.move` ni modification constructeur** ; archive `mujoco-headless-diagnostics`, fichier `policy-lineage.json`.

## Mesures réellement obtenues en MuJoCo

L'audit a lu les modèles du même bundle local `pollen-robotics/microduck-policies` `v8`, dont le manifeste comprend **10 entrées**. Les trois modèles sont **non récurrents**, avec entrée `obs [1,61]` et sortie `actions [1,14]` en float32.

| Fichier ONNX | Taille (octets) | SHA-256 |
|---|---:|---|
| `velstand.onnx` | 793 705 | `2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492` |
| `alpha_walking.onnx` | 793 705 | `e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c` |
| `alpha_stand.onnx` | 793 705 | `1569268713e40deea795dd2922dba50d3621e15a872855408b6b1b125b1c094b` |

Pour les entrées synthétiques sans historique, distances euclidiennes (L2) entre les **14 sorties brutes** :

- **0,2295563983** : `velstand` contre `alpha_stand` à `vx=0` ;
- **0,1524270678** : `velstand` contre `alpha_walking` à `vx=0,12`.

Ces écarts ne sont **ni des erreurs de marche, ni des écarts de consignes articulaires dans `robotd`**, puisque les filtres, l'historique, les observations réelles et les évolutions temporelles ne sont pas mesurés. Il n'existe toujours **aucune preuve causale** associant cette divergence à la translation insuffisante. Le rapport JSON complet, les logs de `robotd` et la vérification d'arrêt des services sont disponibles dans l'[archive Actions #40219277997](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997).

## Décision à l'issue de P0h

Ce travail établit une divergence **réelle de sélection de politique entre la configuration normale de `robotd` et celle forcée par `duck-sim`**. Cela en fait une piste à examiner, mais **la cause des 2,295 mm observés en P0e reste non démontrée**. La prochaine étape, si souhaitée, sera de définir un essai comparatif moteur séparé avec ses critères de sûreté, puis de demander son exécution dans un nouveau lot. **P0h ne réalise pas cet essai.**

Aucun résultat n'est extrapolable au robot physique : pas de mesure RAM, chaleur, autonomie ou comportement réel.
