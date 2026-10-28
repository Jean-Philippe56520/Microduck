# N5 — Véritable wheel candidat hôte avec allowlist stricte (non déployable)

**Date :** 2026-10-28. **Autorité :** [`plan-action.md`](plan-action.md). **Statut initial :** preuve de conditionnement PC/CI en PR, mesures d'archive et tests à confirmer ; **ni installation, ni adaptation de robot**, ni réduction du wheel normal. Point de départ : `main@f9961feea13713c5b80e95a6d9ea00a1283fa682` ([N4 #132 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/132), [CI post-fusion verte](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40749873643)).

## 1. Porte préalable et question précise

**Observation vérifiée :** [N1 #128](https://github.com/Jean-Philippe56520/Microduck/pull/128) a compté **121 fichiers `.py`** dans le **vrai wheel normal**, dont 54 candidats laboratoire heuristiques ; [N1b #129](https://github.com/Jean-Philippe56520/Microduck/pull/129) a sélectionné **19 `.py`** de clôture statique à partir de `microduck_companion.__init__`, dans un ZIP **qui n'était pas un wheel**. [N2 #130](https://github.com/Jean-Philippe56520/Microduck/pull/130) a décalé les imports de `mock_cycles` et `mock_social_cues` hors du chemin passif ordinaire, mais leurs fonctionnalités historiques peuvent encore les charger sur demande. [N3 #131](https://github.com/Jean-Philippe56520/Microduck/pull/131) et [N4 #132](https://github.com/Jean-Philippe56520/Microduck/pull/132) ont préservé la seule `ExperienceMemory` et mesuré le WAL sur fixtures.

**Hypothèse falsifiable :** en reprenant strictement les mêmes **19 sources**, on peut construire un **wheel Python normal**, distinct du wheel habituel, dont le contenu, les octets et les métadonnées sont vérifiables, puis faire `pip install --no-index --no-deps --target` **dans un dossier temporaire de CI** et tester la voie de décision fictive sans import de banc moteur ou de Qwen. **Ce wheel est une sonde de dépendances, pas une sélection des fonctions à installer sur le RK3566.**

**Arrêt/refus de fusion :** le jeu d'import se modifie sans revue de l'allowlist ; import dynamique ou marqueur de commande moteur dans la clôture ; fichier source/symlink non régulier ; ajout d'un fichier `sim_`, d'un `*_demo` ou d'un poids ; contenu du wheel différent des sources ; RECORD/sha256, METADATA, ou tag de wheel incorrect ; import isolé impossible ; comportement normal fictif divergent ; CI rouge. Ne pas masquer un échec en installant des bibliothèques de robot ou en modifiant un modèle OEM.

**Retour arrière :** arrêter/abandonner la PR ; le script de packaging normal `pyproject.toml`, les modules `microduck_companion/`, SQLite réelle, firmware, ONNX, socket, sous-modules et moteur ne sont **pas modifiés**.

## 2. OEM, tiers, et matrice réutiliser / adapter / créer

- OEM **épinglé inchangé** : `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Sources consultées : [architecture robotd](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/architecture.md), [roadmap constructeur](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/project/roadmap.md), [idées M9](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md), [console robotctl](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md). `robotd` seul moteur/sûreté à 50 Hz, `mediad` et `tofd` lecteurs/sources OEM. M9 absent du daemon épinglé ; PR OEM [#381](https://github.com/pollen-robotics/microduck/pull/381) et [#450](https://github.com/pollen-robotics/microduck/pull/450) **ouvertes et non fusionnées** au contrôle. Inconnus : version, santé, politique, chemins et RSS **du robot physique absent**.
- Communauté : [registre C3](community-reference-registry-2026-10-26.md), QuackNav et autres projets tiers ; aucun paquet concurrent ni bibliothèque de navigation ajoutée, car la question N5 est **le conditionnement du cœur Python existant**, pas le contrôle robot.
- **Réutiliser :** `scripts/n1_inventory.py`, `scripts/n1_public_slice.py`, `pyproject.toml` normal **inchangé**, `setuptools` et `wheel` déjà utilisés en CI N1, `AutonomyBrain` et `ExperienceMemory` actuels, CI N1 existante.
- **Adapter :** étendre seulement le workflow N1 **sans créer de nouveau workflow** : comparer le wheel officiel inchangé et le wheel dérivé, installer ce dernier dans une cible temporaire sans Internet.
- **Créer :** `scripts/n5_host_wheel.py` (staging stricte + vérification des octets/METADATA/RECORD d'un véritable wheel), `tests/test_n5_host_wheel.py` (cas positifs/négatifs), ce rapport.

## 3. Frontière explicite : wheel laboratoire ≠ paquet robot

L'[allowlist de N5](../scripts/n5_host_wheel.py) est la liste **figée et examinée** des 19 fichiers de l'API publique depuis N1b. Aucun ajout nouveau n'est admis sur le seul critère d'un nom ; si les imports changent, la PR s'arrête. **Deux exceptions conservées** : `mock_cycles.py` (P2a) et `mock_social_cues.py` (F4-C), car des branches de code historiques les importent à la demande ; les supprimer rendrait certaines méthodes incompatibles. N5 ne prétend **pas** à un binaire robot « débarrassé de toute simulation ».

Le wheel candidat s'appelle **`microduck-companion-n5-host-probe` version `0.0.0`** : son nom de distribution distinct rend son statut expérimental explicite, **mais il fournit toujours l'import `microduck_companion`** et **ne doit surtout pas être installé dans un environnement contenant le paquet normal**. CI le crée dans `$RUNNER_TEMP` ; il n'est pas publié sur PyPI, dans un firmware Yocto ou sur le Microduck.

**Provenance/limitations :** `select_public_closure` est AST statique (imports dynamiques signalés, imports locaux ou `TYPE_CHECKING` inclus dans la fermeture) ; vérifier la liste de modules d'un wheel, sa signature RECORD et son import **n'est pas un audit d'effets d'import complet, de licences tierces, de chemins d'import indirects ni de sécurité moteur**. Le wheel n'inclut ni outils `robotctl`, ni policies ONNX, ni interface OEM authentifiée, ni Qwen 9B, et ne saurait fonctionner comme cerveau embarqué complet.

## 4. Procédure de vérification (PC/CI seulement)

Le workflow [N1 existant](../.github/workflows/n1-wheel-inventory.yml) effectue, à partir de deux builds distincts :

```sh
python -m unittest discover -s tests -p 'test_n5_host_wheel.py' -v
python -m scripts.n5_host_wheel stage --stage-dir /tmp/n5-stage --report /tmp/n5-stage.json
python -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/n5-wheels /tmp/n5-stage
python -m scripts.n5_host_wheel inspect --wheel /tmp/n5-wheels/CANDIDAT.whl --normal-wheel /tmp/n1-wheel/NORMAL.whl --report /tmp/n5-inspection.json
```

*Les noms des wheel doivent être déterminés sur le disque ; les chemins ci-dessus sont des exemples documentaires, pas des liens ni des fichiers générés dans le dépôt.* La CI installe la wheel **seulement avec `--target` temporaire**, puis lance `python -I -B` : source chargée dans cette cible isolée, pas dans le checkout ; `AutonomyBrain.propose_balanced_passive` renvoie `idle` sur fixture de perception indisponible, `describe_behavior` décrit `Chill`, zéro action ; aucun module `mock_*` importé sur cette voie ; un `MockSocialPlan` explicite demeure disponible mais son `executed=True` est refusé. Les modules `sim_motion`, `sim_walk_trial`, `mock_cycle_demo`, `qwen9b_advisor_v2` et `visual_photo_baseline` doivent être **absents** de la distribution isolée.

Les 8 tests sur fixtures comprennent les refus **allowlist étendue sans revue**, import dynamique, littéral `robot.do`, source symlink, staging dans le checkout ou non vide, contenu de wheel altéré. Rapport JSON et wheel sont déposés sous l'artefact **`n5-host-only-wheel-NOT-FOR-ROBOT`**. Aucun média privé, souvenir, voix, jeton, fichier `.sqlite3`, ONNX ou donnée constructeur n'est inclus.

## 5. Critères de sortie et suite

Consigner après CI : comptage de modules **des deux vraies roues**, tailles réelles, identité sha256 du wheel, éventuels échecs et statut de fusion. Une CI verte **prouve la faisabilité du conditionnement hôte**, pas la possibilité de déployer un cerveau sur 1 Go RAM / 32 Go de stockage. Le prochain chantier d'intégration exigera une **interface OEM active** (version, robotctl health/policy, origine/horloge des observations), un audit de RAM/RSS, disque/WAL, chaleur et deadman, la garantie d'une seule SQLite, et une décision de réduire/retirer explicitement les composants `mock_*` sans perdre les preuves de laboratoire. En attendant, garder `docs/plan-action.md` et Cat-A2b/C3-B comme priorités, et ne pas reprendre les essais moteurs SIM-E2.
