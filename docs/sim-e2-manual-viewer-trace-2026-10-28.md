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

**État de validation (28/10/2026) :** [PR #103 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/103), [CI #40658582383 réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40658582383) (1 410 tests, 31 ignorés). **WSLg utilisateur :** 8 lectures passives au repos puis **32 lectures pendant une commande OEM** de ~8 s à 0,08 m/s, 31 `walk`, aucune limitation, déplacement du tronc net **3,500 mm**. La collecte est validée sur hôte, **pas la locomotion** ; la cause reste inconnue, aucun essai physique. [Dossier de reprise](reprise-microduck-oem-sim-e2-2026-10-28.md).
Suivi : [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101).

## SIM-E2-B — mesure optionnelle du suivi articulaire OEM (nouveau lot)

L'OEM épinglé expose `joints` et `targets` dans la **même trame**
`robot.state` avec l'horloge `t_ns`. À la différence de `body_server.read`,
ce sont les positions mesurées par `robotd` et les **cibles proposées
avant `safety.apply`**, et non une confirmation d'écriture/actionnement.
`sim_joint_trace --joint-tracking` lit cette trame sans toucher au moteur.

Premier contrôle : **au repos seulement, sur le simulateur OEM déjà lancé**
et sa configuration alpha existante, sans aucun `drive` ou `policy load`.
Depuis un terminal WSL Ubuntu contenant le checkout validé :

```bash
cd ~/Microduck
export DUCK_SIM_RL="$PWD/upstream/microduck_rl"
export DUCK_SIM_STATE="$HOME/.cache/kwipi-visual"
export PYTHONPATH="$PWD:$DUCK_SIM_RL/src"
python3 -m microduck_companion.sim_joint_trace \
  --verified-viewer --joint-tracking \
  --state-dir "$DUCK_SIM_STATE" --rl-root "$DUCK_SIM_RL" \
  --port 7801 --samples 8 --hz 4 \
  --output "$HOME/kwipi-joints-idle.json"
```

**Condition préalable :** après vérification GitHub/CI, récupérer le code
sur un répertoire Git propre ; ne pas effectuer de `git pull` automatique
sur un environnement modifié. Le simulateur doit déjà être lancé avec la
scène/processus constructeur exact ; la sonde **ne le lance pas**. Une
erreur d'identité, horloge ou forme de donnée doit arrêter le relevé ;
ne jamais supprimer une vérification pour le faire passer.

Le fichier JSON complet reste **local sur PC** ; seule la synthèse
cibles/mesures est imprimée. Les 8 échantillons au repos servent à
vérifier le protocole, **pas** à conclure sur la marche. Un éventuel
nouvel essai actif exige un plan distinct, un témoin de même durée,
des états synchronisés, le `robot.stop` OEM garanti, et des critères
d'arrêt et de non-crédit. Voir le
[protocole SIM-E2-B](sim-e2b-robotd-joint-target-trace-2026-10-28.md).
