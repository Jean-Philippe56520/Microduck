# SIM-E2-A — trace manuelle graphique, lecture seule

Le diagnostic `sim_joint_trace` précédemment validé uniquement en CI headless
refusait à juste titre le processus OEM graphique (`--headless` absent).

Cette adaptation **n'ouvre aucune autorisation motrice**. Le défaut reste
headless strict ; l'option `--verified-viewer` accepte uniquement le second
argv constructeur exact (même module Python, mêmes port/1 duck/SIT, sans
`--headless`), sous les mêmes vérifications : processus/propriétaire,
gitlink RL épinglé propre, hash de scène plane. `robot.subscribe` et
`hello/read` sont les seules opérations émises par cette trace. L'autre
contrat de sécurité `read_verified_flat_ground` reste headless par défaut.
Aucune modification `upstream/`, moteur, policy, SQLite ou attribution causale.

## Utilisation sur Ubuntu / WSLg

```bash
cd ~/Microduck
export DUCK_SIM_RL="$PWD/upstream/microduck_rl"
export DUCK_SIM_STATE="$HOME/.cache/kwipi-visual"
export PYTHONPATH="$PWD:$DUCK_SIM_RL/src"

python3 -m microduck_companion.sim_joint_trace \
  --verified-viewer \
  --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
  --port 7801 --samples 8 --hz 4 \
  --output "$HOME/kwipi-idle-check.json"
```

Vérifier d'abord ce **test passif**. En cas de refus, transmettre l'erreur
sans supprimer la vérification de processus. La fenêtre et l'environnement
graphique ne constituent pas une preuve de locomotion. La télémétrie
`deadman` au repos est attendue et ne prouve pas une inhibition en marche.
Un futur essai actif manuel doit séparer les fenêtres temporelles
avant / pendant / après et ne pas convertir la trace en récompense.

**État de validation :** code et tests de fixtures publiés sur branche ;
CI sur le SHA final à vérifier avant fusion. Aucun essai physique.
Suivi : [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101).
