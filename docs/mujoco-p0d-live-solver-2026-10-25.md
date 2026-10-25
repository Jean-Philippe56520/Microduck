# P0d — Contacts et consignes originaux du solveur MuJoCo (25 octobre 2026)

**Nature de la preuve : simulation épinglée, pas robot physique.** La [PR #14](https://github.com/Jean-Philippe56520/Microduck/pull/14) ajoute une sonde **facultative au sein du processus** `body_server` officiel, sans changement des fichiers sous-modules. Elle intercepte l'appel `mujoco.mj_step` en conservant exactement son appel original et copie **après** ce pas les données `MjData.contact`, `mj_contactForce`, `data.ctrl` et angles. `robotd` reste seul maître des moteurs ; la seule marche est l'essai J2e existant, 24 commandes à 0,12 m/s et arrêt confirmé.

## Sources, déroulement et cadence

- Révision `microduck_rl` `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, fichier de scène `scene.xml` blob `a3848be52113a50138d54921748733f09488d496`, sources constructeur suivies **inchangées**.
- `sitecustomize.py` n'attache l'instrumentation qu'au processus exact : Python du `.venv`, `-m mjlab_microduck.sim.body_server --port 17801 --ducks 1 --keyframe SIT --headless`. Le chemin et les paramètres sont vérifiés. Les autres processus Python n'activent rien.
- Le serveur OEM règle `model.opt.timestep=0,005 s`; la sonde échantillonne **un pas sur quatre**, environ 50 Hz, depuis le même `MjData` utilisé par `robotd` via le serveur. Aucune reconstruction statique P0c ni aucun `mj_step` additionnel.
- Un écrivain asynchrone conserve au maximum 512 relevés en file ; la sonde ne bloque pas sur une écriture disque. Une erreur de capture désactive le diagnostic et **n'interrompt jamais le pas OEM**. Un échantillon perdu, des timestamps non continus, une provenance ou une validation P0b absente font rejeter le résultat hors ligne.
- [Premier essai officiel P0d réussi #40190232870](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190232870) sous la version initiale de la sonde : 189 tests logiciels, fichier `solver-tap.jsonl` archivé, **888 trames validées au moment du rapport**. Le fichier final archivé peut comporter quelques trames de plus, le simulateur continuant après l'analyse.
- **Durcissement ajouté ensuite :** capture d'exceptions imprévues sans impact sur `mj_step`, résumé de double appui et estimation de l'écart consigne/angle ; [190 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697176). Les métriques ci-dessous sont celles du **premier essai mesuré** et restent distinctes d'une répétition ultérieure.

## Premier essai : mesures du solveur original (GitHub Actions #40190232870)

| Grandeur | Repos `stand` | Fenêtre de marche |
| --- | ---: | ---: |
| Trames natives (~50 Hz) | 79 | 126 |
| Pied gauche avec contact et force normale > 0,1 N | 79/79 | **126/126** |
| Pied droit avec contact et force normale > 0,1 N | 79/79 | **126/126** |
| Force normale moyenne gauche | 3,651 N | 3,207 N |
| Force normale moyenne droite | 3,578 N | 4,030 N |
| Force normale maximale gauche | 3,725 N | 3,818 N |
| Force normale maximale droite | 3,891 N | 5,252 N |
| Somme des normes tangentielles maximale gauche | 0,260 N | 0,587 N |
| Somme des normes tangentielles maximale droite | 0,307 N | 1,685 N |

**L'observation importante :** au seuil diagnostic de 0,1 N, **les deux pieds sont chargés sur chacune des 126 trames échantillonnées pendant la période de marche**. Aucune phase de transfert d'appui avec un seul pied chargé n'a été observée à 50 Hz. Cela **n'exclut pas** un allègement bref entre trames ni des changements de la surface de contact ; cela ne prouve pas à lui seul la cause du défaut de locomotion.

### Commande positionnelle comparée aux angles simulés (fenêtre de marche)

| Articulation | Excursion de la consigne `data.ctrl` | Excursion de l'angle `qpos` | RMS approximatif consigne − angle |
| --- | ---: | ---: | ---: |
| Hanche gauche, roulis | 0,15679 rad | 0,01124 rad | 0,11021 rad |
| Hanche droite, roulis | 0,16747 rad | 0,00569 rad | 0,07997 rad |
| Genou gauche | 0,08412 rad | 0,01858 rad | 0,13664 rad |
| Genou droit | 0,03723 rad | 0,02410 rad | 0,18559 rad |

Ces valeurs sont issues des **consignes de position réellement présentes dans les actuateurs MuJoCo** et des angles post-intégration. Le RMS mesure un **écart de suivi apparent, incluant les offsets de posture** et le léger décalage de phase interne au pas physique. Ce n'est pas une erreur normalisée de moteur réel ni une preuve directe de saturation. Les amplitudes de roulis commandées mais peu reproduites et les deux pieds continuellement chargés justifient un diagnostic causal des gains/efforts et de l'intégration du contrôleur, **sans changement arbitraire**.

### Résultat moteur et surcoût de la mesure

- Essai J2e à **0,12 m/s**, `walk` rapporté **23/24** échantillons, **2,222 mm** de déplacement final XY (X monde +2,180 mm ; Y monde +0,429 mm), baseline propre à J2e **0,050 mm**, `robot.stop` confirmé, `no_progress_observed` écrit dans la SQLite éphémère. Seuil de progression de 10 mm **non atteint**.
- Sur **888 trames validées**, coût déclaré de la capture synchrone : moyenne **139 µs**, maximum **452 µs** par relevé (un relevé toutes les ~20 ms) ; ce n'est pas le coût système total du thread écrivain ni une mesure énergétique. Le workflow a passé les contrôles de santé et cadence du simulateur, mais **l'instrumentation change la charge CPU** et les essais sans instrumentation ne sont pas strictement appariés statistiquement.

## Séparation explicite des informations

- **Mesuré dans le solveur original :** paires de contacts semelle/sol, forces normales et tangentielles MuJoCo, cibles de position (`data.ctrl`), angles, efforts simulés, pose du tronc et temps simulé.
- **Nuance temporelle :** les forces et caches de contact proviennent du solveur du dernier pas ; les `qpos` sont post-intégration. Un léger décalage intra-pas peut exister. Les phases `stand`/`walk` sont bornées à partir des notifications P0b à 10 Hz, **pas** étiquetées au même tick moteur.
- **Non mesuré ou non validé :** glissement réel du patch de contact, interaction du pied avec le sol entre échantillons, cause racine de l'échec de marche, marge de sécurité matérielle, courant des vrais servos ou température de robot.
- **Hypothèses à éprouver :** limitation des actuateurs simulés, écart de contrôle de position, stratégie ONNX ne déchargeant pas les pieds, conditions de contact/sol et déphasage entraînement/simulation. Ne conclure ni que le constructeur est défectueux ni qu'un réglage précis résoudrait la marche.

## Prochain jalon P0e et barrière P1a

Analyser le **suivi par articulation et la charge moteur** en comparaison avec les paramètres actuels OEM, lire les gains, limites d'effort et l'état du contrôle sans aucune écriture, puis établir une expérience comparative contrôlée en simulation isolée. Une modification ne sera proposée qu'après identification vérifiable de l'origine (notre intégration, différence OEM simulation/entraînement ou autre). P1a exige encore **trois** traductions indépendantes d'au moins 10 mm, puis une démarche contrôlée d'au moins 5 cm, sans contournement constructeur.

**Artefacts :** [GitHub Actions #40190232870](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190232870), `solver-tap.jsonl`, `solver-analysis.json`, `walk-comparison.json`, logs de `robotd`. Aucune donnée personnelle ou robot physique impliqué.

