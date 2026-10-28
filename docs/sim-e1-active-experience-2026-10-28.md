# SIM-E1 — première expérience active bornée dans MuJoCo OEM

## Acceptation finale du lot — PR #100 fusionnée

**État réel au 28 octobre 2026 :** [PR #100 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/100), SHA merge `99faad230480502c321cb42db8d70509d3969409`. [CI MuJoCo constructeur du correctif #40652100659](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40652100659) **réussie** au SHA `72b051cc80651a1e7595bcb5c6de0299c26fae16`, **1 408 tests Python, 31 ignorés, 0 échec**. [CI Python après fusion sur `main` #40652673610](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40652673610) réussie.

L'[artefact de CI MuJoCo](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40652100659/artifacts/12799698587) contient : 24 consignes fixes J2e, 24 statuts `robotd` (23 `walk`, 1 `stand`), `robot.stop` confirmé, translation du tronc `0.0015535466 m` (≈ 1,554 mm) et dérive de référence `0.0000481123 m` (≈ 0,048 mm). Le rapport signale `limited_by=["deadman"]`, `outcome="inconclusive_control_limit"`, `reward=null`, préférence `0.0 → 0.0`, même décision `explore` avec/sans préférence, et `motor_commands_from_counterfactual=0`. L'épisode est conservé dans la SQLite de simulation, sans crédit positif ou négatif. La présence agrégée du flag ne prouve pas qu'il était actif pendant tous les ticks ; à détailler en SIM-E2.

**Validé :** refus d'apprentissage sur commande limitée, preuves liées à une simulation OEM épinglée, comparaison cognitive passive et absence de second contrôleur. **Non validé :** démarche efficace, navigation sûre, objet simulé, effet causal, généralisation, multimodal Qwen intégré, tests robot réel ou budget mémoire RK3566. Suivi [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101). Les limites et les premiers runs pré-correctif sont conservés ci-dessous pour audit.



## Résultat du premier run et correction anti-fausse récompense (28/10/2026)

La [première CI MuJoCo réelle #40651133574](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40651133574), sur SHA `099537f7...`, a réussi le banc headless et **1 405 tests Python, 31 ignorés**. Rapport archivé : **24** commandes `robot.move` à 0,12 m/s demandé, **24** états échantillonnés (23 `walk`, 1 `stand`), `robot.stop` accusé, déplacement du tronc **0,001858 m** contre dérive de base **0,000132 m**. Le résultat historique `no_progress_observed`, la récompense négative `-0.5` et la préférence `-0.075` ont été calculés **malgré `limited_by:["deadman"]` dans la télémétrie OEM**. L'intention restait `explore` avec et sans préférence. Cette pénalité **n'est donc pas une preuve d'échec d'apprentissage ou de commande librement exécutée**.

**Correction SIM-E1 :** dès qu'un échantillon OEM mentionne un limiteur `limited_by` non vide, la couche J2e mémorise l'épisode comme `inconclusive_control_limit` dans la SQLite **avec `reward=None` et sans changement de préférence**. La présence de limiteur est recoupée avec l'état et la récompense par le validateur SIM-E1 ; la commande, le stop, les sources et le rapport sont conservés. Aucun seuil OEM, vitesse, policy ou arbitrage modifiés. Tests de non-récompense, limites et falsification ajoutés. **Ne pas extrapoler à un robot réel ; ne pas inférer les causes mécaniques du déplacement insuffisant.** La CI du code corrigé doit être rattachée séparément à son dernier SHA avant fusion.



**28 octobre 2026 — candidat de laboratoire.** Code ajouté sur une branche dédiée.
Le présent document ne revendique **aucun test réel du robot**, aucune préhension,
aucun coup de pied sur une balle et aucun entraînement de réseau neuronal.
Avant résultat CI ciblé, distinguer **code publié**, **tests de fixtures**
et **exécution des démons officiels dans MuJoCo**. Les résultats CI, s'ils sont
disponibles, devront être rattachés au SHA précis.

## Objectif vérifiable

Après le succès passif [X2-C](x2c-mujoco-passive-acceptance-2026-10-27.md),
exécuter **une seule** expérience motrice déjà implémentée (J2e :
`sim_walk_trial.run_walk_trial`) dans le monde MuJoCo plat et vide, puis
comparer sur une observation simulée fraîche :

- une intention de `AutonomyBrain` avec la préférence `simulator/explore`
  venant de l'unique `ExperienceMemory` ;
- la même intention calculée avec préférence simulée neutralisée, sans action
  motrice ni nouvelle SQLite.

Mesurer explicitement `choice_changed`. Un seul essai peut modifier la
préférence **sans modifier la décision** ; ne jamais annoncer un apprentissage
de comportement autonome si les intentions restent identiques.

## Audit réutiliser / adapter / créer

| Bloc | Décision | Limite |
| --- | --- | --- |
| OEM épinglé `942e58e3`, `microduck_rl` `b02fdea` | **Réutiliser** `robotd` 50 Hz, `duck-sim`, `tofd` et policies sans modifier `upstream/` | Aucune garantie matérielle |
| J2e `sim_walk_trial.py`, `sim_flat_zone.py`, `sim_policy_trace.py` | **Réutiliser** le mouvement fixe `robot.move`, le `robot.stop` accusé et la lecture de position MuJoCo après commande | La translation n'atteste pas la démarche |
| `AutonomyBrain`, `ExperienceMemory`, `sim_motion_trials`, `intent_preferences` | **Réutiliser** la préférence simulée et la SQLite unique | Pas d'apprentissage causal physique |
| X2-C, EX4-A/B/C1, F5 v1/v2 en PR | **Conserver séparés** les contrats de provenance, l'attention et les hypothèses Qwen | Aucun retour Qwen ne devient récompense |
| `sim_e1_active_experience.py` | **Créer un vérificateur** et un contre-factuel en lecture seule, sans second pilote moteur | Pas de nouvelle primitive |
| `tests/test_sim_e1_active_experience.py` | **Créer des cas positifs et adversariaux** | Fixtures ≠ MuJoCo réel |
| `sim-smoke.sh`, workflow MuJoCo | **Adapter** par opt-in exclusif à la branche `feat/sim-e1-active-experience-20261028` | Une seule commande active J2e |

Références externes : OEM #381 (cerveau) et #414 (maploc/mapd),
QuackNav/microduck-brain, Quacksat, microduck-twin, quack-control et
microduck-lab/studio : veille uniquement. Aucune dépendance ni patch tiers
ajouté. Toute future navigation, objets et perceptions réelles nécessitent
un audit indépendant.

## Évidence de l'unique essai

La seule routine motrice utilisée est J2e. Dans le monde MuJoCo
**plat, vide et constructeur épinglé**, J2e confirme une base stable, vérifie
source/processus/simulation, limite la fenêtre temporelle, envoie une consigne
de vitesse fixe (`0,12 m/s`) sur au plus 24 ticks à période de 100 ms, lit
les états `robotd` et finit par `robot.stop`. Les `robot.state` ne sont
pas des reçus OEM de fin de skill; la position MuJoCo est l'observation
indépendante **de la translation du tronc dans la simulation**.

Le rapport SIM-E1 refuse : base SQLite déjà existante ou réutilisée,
compteur différent d'un essai, commande sans état OEM échantillonné,
arrêt non confirmé, état final dégradé, provenance modifiée,
dérive/effet inventé, double souvenir, contamination `robot`, métrique
non finie, sortie hors contrat ou post-observation périmée/à risque.

Une base SQLite fraîche du lot est ouverte par J2e puis **relue** par SIM-E1 :
aucune seconde table ou base, aucun second écrivain et aucun
`AutonomyBrain.feedback`. Les changements de préférence restent sur la
clé `simulator/explore`, jamais sur `robot/explore`. Le contre-factuel
n'émet aucune RPC; il neutralise seulement la préférence simulée et garde
le même contexte de perception et les motivations par défaut.

**En l'absence de progression :** le résultat négatif peut réduire un peu
la préférence simulée. Il ne démontre ni défaut de la policy ni
inaptitude à marcher. **En cas de mesure indéterminée :** zéro récompense.
**En présence d'un résultat après une seule séance :** ce n'est ni
une généralisation ni une preuve de cause sur objet.

## Tests et exécution

Tests PC/fixtures : `python3 -m unittest tests.test_sim_e1_active_experience -v`.
CI existante : `python3 -m unittest discover -s tests -v`.
Sur la branche spécifique, le workflow `mujoco-smoke.yml` exécute
`scripts/sim-smoke.sh run` avec `DUCK_SIM_SIM_E1=YES`.
La branche produit `sim-e1-report.json` si l'unique essai est complet.
La commande CLI directe exige **à la fois** `MICRODUCK_SIM_E1=YES` et
`--enable-once` ; le runner J2e effectue ensuite des vérifications
indépendantes de la provenance réelle des démons simulés. Aucune option
de bouclage, de répétition ou de nouvelle vitesse.

Mesurer dans le rapport les déplacements brut / dérive, les 24 états
échantillonnés de `robotd`, l'arrêt, le changement de préférence et
la décision `with_simulated_memory` comparée au contrôle.
Conserver le lien CI (sha, succès/échec) avant toute décision de fusion.
En cas d'erreur, le rapport de succès n'est pas émis; inspecter les
logs CI plutôt que fabriquer des résultats.

## Portes pour la suite

1. Réussite de la suite Python/fixtures sur la PR, puis vraie CI MuJoCo
   des démons épinglés. Signaler les échecs, sans les masquer.
2. Répéter plus tard **en essais séparés**, jamais dans la même commande,
   avec redémarrages et autres scènes *si* les contrôles constructeurs
   permettent de prouver leur provenance et leurs effets.
3. Ajouter un banc de généralisation avec/sans mémoire sur des contextes
   nouveaux, où la différence de décision est **effectivement mesurée**.
4. Ne pas importer de balle, animal, caméra ou perception inventée dans le
   monde plat. Priorité parallèle [Cat-A2b #78](https://github.com/Jean-Philippe56520/Microduck/issues/78).
5. Attendre le robot et [EX4-C2 #80](https://github.com/Jean-Philippe56520/Microduck/issues/80)
   pour attester fin de skill OEM et conséquences physiques.
   Les ressources RAM/RSS/NPU/température RK3566 restent inconnues;
   exécuter `scripts/resource-audit.sh` une fois le matériel disponible.

**Bilan provisoire :** SIM-E1 vérifie au plus la liaison *un mouvement
existant dans MuJoCo → sa mesure simulée → une préférence simulée →
une décision cognitive comparée*. Ni neurones supplémentaires,
ni autonomie motrice générale, ni transfert physique démontrés.
