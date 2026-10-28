# SIM-E2H — appuis natifs des pieds pendant la translation OEM MuJoCo

**28 octobre 2026. [PR #125](https://github.com/Jean-Philippe56520/Microduck/pull/125), [run OEM #40734782145](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40734782145) (**CI rouge, refus conservateur du contrôle confondu**), [réanalyse OFFLINE verte #40736104413](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40736104413), [artefact dérivé](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40736104413/artifacts/12836983145).** Le robot physique est absent. Pas de nouvelle marche validée, ni de cause motrice prouvée. L'issue [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101) demeure ouverte.

## Pourquoi ce seul essai et quelle question précise ?

**Observation (SIM-E2G, [PR #124](https://github.com/Jean-Philippe56520/Microduck/pull/124)) :** une commande OEM à 0,30 m/s pendant 12 notifications avait déplacé le tronc de 109,771 mm. Cependant son `joint-trace.json` archivé ne contient que huit trames `stand` **avant** l'essai ; **aucun contact au sol pendant la translation n'avait été relevé**.

**Hypothèse falsifiable :** les forces de contact originales du solveur `mj_contactForce` (et non la pose du tronc) peuvent montrer que les charges d'appui gauche et droit varient dans la fenêtre de translation. L'hypothèse d'une simple translation sans transfert de charge serait affaiblie si **les deux pieds étaient chargés unilatéralement à des instants distincts**. Ce critère est descriptif, non équivalent à une démarche autonome ou stable.

**Choix réutiliser / adapter / créer :** réutiliser le tap externe **P0d** (`sim_live_solver_tap.py`, `scripts/solver-tap/sitecustomize.py`) dans le vrai `mj_step` OEM et son parseur strict (`_read_solver_trace`), le seuil 0,1 N **P0j**, E2G et `robotd` seul pilote. Adapter E2G pour reporter les bornes de temps MuJoCo pré-commande et après arrêt, sans changer la politique, les moteurs, la scène ou les protections. Créer un **petit analyseur hors ligne** `sim_e2h_contact_audit.py`, sans SQL ni socket. Les projets tiers restent des références non intégrées, en particulier le signalement vitesse lente de [microduck_rl #59](https://github.com/pollen-robotics/microduck_rl/issues/59) (politiques v5 ≠ v8). La PR constructeur [#450](https://github.com/pollen-robotics/microduck/pull/450) n'était pas fusionnée au moment de l'audit et **n'est pas utilisée**.

## Configuration, risque, arrêt et preuve du banc

- Gitlinks conservés : `pollen-robotics/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Scène `src/mjlab_microduck/robot/microduck/scene.xml` (Git blob `a3848be52113a50138d54921748733f09488d496`).
- Politique réellement chargée `alpha_walking.onnx` et `alpha_stand.onnx`, ONNX v8 authentifiés par P0i. Pas de changement de réseau, gain, frottement, deadman, balise, capteur ou zone de sécurité.
- **Une répétition bornée** `vx=0,30 m/s`, 12 commandes à 10 Hz maximum dans `run_walk_trial`, avec relecture sol, batterie/santé, horloge, position, limitation et `robot.stop` acquitté. Pas d'activation de P0b ni de deuxième ordonnanceur. Mémoire d'essai SQLite jetable hors produit ; aucun crédit causal.
- P0d capture une trame native tous les quatre `mj_step` (pas MuJoCo 5 ms, sorties **50 Hz**), sur le vrai serveur constructeur identifié par argv, avec file d'écriture bornée non bloquante. Surcoût potentiel CPU/GIL : p95 et maximum du **temps de copie/encodage**, pas des délais système à 50 Hz ni d'une comparaison simulée non instrumentée.
- **Retour arrière/stop :** le tap n'envoie aucun ordre et les erreurs de collecte ou d'horloge invalident la preuve. Le premier pipeline CI a **refusé à juste titre de conclure** parce que `deadman` apparaît parmi les limites agrégées ; ce n'est **pas** une panne de contact. Aucun autre essai moteur lancé après cet échec ; le déclenchement automatique MuJoCo sur la branche a été retiré. Le rapport est ensuite recalculé **sur la même archive immuable**, par workflow GitHub **offline** sans moteur.

## Évidence brute de la seule session constructeur

**Run OEM [#40734782145](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40734782145), artefact `mujoco-headless-diagnostics` ID `12837680134` (retention GitHub limitée) :**

| Mesure vérifiée | Résultat |
| --- | ---: |
| Fichier original `solver-tap.jsonl` | **764 trames continues**, zéro trame d'erreur |
| Source et horloge | `mj_step` natif épinglé, **0,020 s** entre échantillons |
| Fenêtre `sim_baseline_time_s` → `sim_after_stop_time_s` | 12,980 → 14,440 s (1,460 s) |
| Trames de contact dans cette fenêtre | **74** |
| Pied gauche seul chargé, >0,1 N | **24** |
| Pied droit seul chargé, >0,1 N | **28** |
| Deux pieds chargés, >0,1 N chacun | **22** |
| Aucun pied chargé | **0** |
| Transitions directes gauche seul ↔ droit seul | **3** |
| Force normale max pied gauche | **13,116 N** |
| Force normale max pied droit | **16,411 N** |
| Trajet XY monde du site pied gauche en cache | **159,113 mm** |
| Trajet XY monde du site pied droit en cache | **145,890 mm** |
| Déplacement XY du tronc par le solveur | **126,466 mm** |
| Déplacement XY du tronc par E2G, séparé | **126,466 mm** |
| Translation avant X / latérale Y | **+116,751 mm / −48,611 mm** |
| P95 du temps local de capture | **111,655 µs** (max. 114,891 µs) |
| Politique signalée | 11 `walk` / 1 `stand`, 12 mesures |
| Vitesse « applied » max | 0,300 m/s |
| Limitation observée dans au moins un échantillon | **`deadman`** |
| `robot.stop` | **confirmé** |

**SHA-256 des originaux :** `solver-tap.jsonl` = `a6cf5effde780eac953caaa18508e28e9c17453b1381e7cadaa5664b5e4aa563` ; `sim-e2g-report.json` = `1e49a67325688fca2d0dd41abc0c3b36b954a15656bf3a2b0717406a5ed1a090`.

**CI de réanalyse réelle :** [#40736104413](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40736104413) **verte** : télécharge exclusivement l'artefact OEM précédent, vérifie **les deux SHA-256**, rejoue `sim_e2h_contact_audit.py`, produit `sim-e2h-contact-report.json` et ne démarre **aucun simulateur, modèle, agent ou moteur**. Tests adversariaux hors moteur : source/empreinte/horloge manquante, déconnexion, stop non confirmé, NaN, faux contact, déplacement contradictoire, surcharge. Les résultats positifs des tests synthétiques ne sont pas confondus avec l'évidence constructeur.

## Interprétation rigoureuse

**Démontré :** les forces normales issues du **solveur original** montrent une alternance descriptive d'appuis unilatéraux du pied gauche et droit, avec des épisodes de double appui, au cours d'une fenêtre MuJoCo où une translation XY indépendante est mesurée. Cela apporte une preuve de **transfert de charge observé dans la simulation** qui manquait à SIM-E2G. Les 74 trames sont continues et alignées à la même horloge de simulation que le rapport E2G.

**Non démontré / inconnu :**
- `deadman` dans la liste de limites E2G : **moment exact et effet sur chaque commande inconnus**. La sortie du premier pipeline `control_inconclusive` est conservée. Le nouvel analyseur peut **décrire des contacts** indépendamment, mais il inscrit `e2g_control_eligible=false` et **`motor_command_caused_displacement_proven=false`**. Aucune préférence ou récompense n'est déduite du rapport.
- La fenêtre commence à la lecture de la baseline et se termine **après le stop** : **ce n'est pas une synchronisation à chaque tick de commande**. Certains contacts sont transitoires et ne peuvent pas être imputés avec certitude à une commande précise.
- `mj_contactForce` donne des forces normales et **la norme** des composantes tangentielles en repère de contact, pas le sens de la traction au sol. Les trajectoires des **sites de pieds en cache** ne mesurent **ni le point de contact réel ni le glissement sur le plancher**.
- 1,46 s et une seule scène, pas de répétabilité ni vitesse soutenue, coût du tap seulement micro-temps de capture et non absence d'impact système, aucun essai matériel RK3566 ou Microduck. **Une démarche stable, navigable, autonome ou transférable au robot n'est pas validée.**

**Décision :** arrêter les essais moteurs de ce lot ; statut **SIM-E2H = transférer/alterner les charges en simulation observé, locomotion globale SIM-E2 #101 non résolue**. Pour conclure ensuite à une démarche stable, il faudrait un protocole différent évaluant contacts véritables, stabilité sur plusieurs cycles, éventuel glissement et capacité OEM à rendre `obs[61]` / `raw_actions[14]` sans changer la commande 50 Hz, avec validation et ressources. Pas de correction moteur/gain ni de déploiement.

**Ressources :** valeurs du PC/runner, pas de budget RAM/RSS, CPU, thermie, batterie, disque, latence/fiabilité 50 Hz sur RK3566. `scripts/resource-audit.sh` obligatoire avant tout portage. Les archives GitHub expirent ; cette page conserve les SHAs et les résultats agrégés, pas les médias privés ni une seconde SQLite.
