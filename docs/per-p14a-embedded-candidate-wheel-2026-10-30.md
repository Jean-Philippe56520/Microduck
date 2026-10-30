# PER-P14A — paquet Python réduit candidat embarqué (30 octobre 2026)

## Objectif, manque prouvé et preuve avant code

Base `main@9ede20893ac1a21dae4dda737753bd870ee91bdd`, gitlinks OEM `942e58e3aa6dbb28e7037203fff11866122c7567`, RL `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` et Yocto `1ee58387810cebb67ae0d634c351d95024483bce`. PR #225/P11 et #226/P12 fusionnées. P13A #227 ouverte, parse BitBake en cours, non autorisé comme preuve. Qwen #97-99 fusionnées ; P8/#218 fermée sans parité.

**Manque :** le wheel standard `microduck-companion==0.2.0` embarque tous les laboratoires, et le wheel **N6 strict 18 sources** reste expressément hôte, dépourvu de la couche de lecture `robot.health` OEM. Aucun service Kwipi arm64 ni packaging Yocto/Python n'est aujourd'hui testé. Réutiliser `scripts/n5_host_wheel.py`, `scripts/n6_no_mock_wheel.py`, `microduck_companion/sim_ipc.py` (transport Unix officieux en lecture seule), `ExperienceMemory` unique, `AutonomyBrain` sans moteurs, tests OEM; pas de nouveau processus/scheduler moteur ni base.

**Gain mesurable P14A :** un vrai `wheel` candidat **19 modules Python** (les 18 N6 plus **exactement** le transport `sim_ipc.py`, inchangé), une identité de distribution distincte, `RECORD` vérifié et installation `pip --no-index --no-deps --target` dans un venv hôte isolé. Prouver **l'absence** de modules `mock_*`, de commandes `robot.move/do/stop` dans le transport, et la compatibilité du cycle cognition passive `idle` sur source absente. Les observations du socket peuvent être falsifiées : ce n'est **pas** une authentification d'un robot.

## Matrice réutiliser / adapter / créer

- **Réutiliser** : N5/N6, fichiers et test suites existants ; `read_health` / `ReadOnlyUnixRpc` et leurs restrictions de méthodes, `ExperienceMemory` en mémoire uniquement, `AutonomyBrain.propose_balanced_passive`. Le montage persistant Yocto devra être validé avant écriture sur disque.
- **Adapter** : N6 staging en copie externe pour ajouter un fichier pur `sim_ipc.py` dont l'AST et l'allowlist sont contrôlés ; changer uniquement la distribution/version de ce wheel distinct (pas le `pyproject.toml` principal).
- **Créer** : script de staging, audit du wheel et CI, tests d'octets et négatifs. Aucun service ni adaptation robotd ; seul `robotd` a les moteurs.

## Positifs et négatifs préenregistrés

Positifs : 19 chemins exacts ; 0 `mock_*`/modèle/SDK/service ; vrai wheel `py3-none-any` ; contenu et `RECORD` SHA-256 identiques aux sources ; installation sans Internet ; imports d'une instance de `AutonomyBrain`, `ExperienceMemory(":memory:")`, `PassiveObservationJournal` et `ReadOnlyUnixRpc` ; réponse `idle, executed=False, motor_commands_issued=0` sur capteur manquant ; refus explicite d'une demande `robot.move` sur fausse socket sans émettre de trame.

Négatifs : fichier non autorisé, import caché/dynamique, nouveau pilote ou source `mock`/moteur, source symlink, wheel avec fichiers/RECORD altérés, doublons, identité de distribution erronée, installation mêlée à un autre `microduck_companion`, commandes moteur, absence de DB `ExperienceMemory` unique, permission physique affirmée.

**Arrêt/retour arrière :** si la fermeture N6 change ou la garde source est incompatible, STOP et revue, ne pas supprimer les laboratoires du dépôt ni forcer la sélection. Si tests hôte échouent ou CI final rouge : ne pas fusionner. Supprimer seulement la branche ou le staging. La réussite du wheel ne valide **pas** Python/SQLite sur Yocto RK3566, les sockets réels, la thermique, NPU, la cognition autonome, la locomotion ou les mises à jour.

## Suites, sans dérive

P14B ultérieur : intégration dans vraie recette Yocto, dépendances CPython/sqlite en image, chemin de stockage persistant validé, processus d'observation read-only en P15 **sans piloter les moteurs**. Ne pas confondre les services simulés P14A avec un daemon robot livré. Qwen reste sur PC seulement ; les licences YOLO26 et parité P8 ne sont pas résolues.

## Résultats

À compléter après une CI sur le dernier SHA.

## Vérification sur vrai wheel hôte — P14A

[CI P14A #41137030593](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41137030593) réussie au SHA `42ecb707161cb93dbd5fed74c87e34112808a2a3` : 8 tests P14A, 8 tests N6 et 22 tests de transport `sim_ipc` (38/38), soit vraie roue `microduck_companion_embedded_candidate-0.2.0a1-py3-none-any.whl` (**66 701 octets dans ce run**, SHA256 de cette roue `9da4834427dba5543d78a36e602ac93fc95415bc1d39ed136c0c48f5854f3b90`). Source bytes et hashes `RECORD` vérifiés, `METADATA` et `top_level.txt` exacts, 19 modules, aucun `mock_cycles`, `mock_social_cues`, `sim_bridge` ni `qwen9b_advisor_v2`. Installation offline à l'extérieur du checkout et `-I -B` hôte réussies, (a) `ExperienceMemory(":memory:")`, (b) `AutonomyBrain.propose_balanced_passive` renvoie `idle, executed=False, motor_commands_issued=0` sur capteur absent, (c) 5 méthodes `robot.move/stop/do`, `media.frame` et `tof.stream` mal ciblé refusées avant toute connexion. Artifact hôte de revue uploadé pour 7 jours. Les tests P14A initiaux ont refusé le wheel jusqu'à l'acceptation **précise et testée** du fichier `top_level.txt` automatiquement fourni par `setuptools`.

**Ne pas inférer** une politique d'action, un état de santé authentifié, un vrai visage/caméra, une perception, un suivi, un robot autonome, des moteurs pilotés, une livraison `microduck-image` ou un comportement physique. Une roue hôte `py3-none-any` ne prouve ni CPython/SQLite Yocto ni environnement réel ARM64. CI générale et fusion à vérifier au dernier SHA documentaire. Le chemin `sim_ipc.py` est nommé historiquement ; la source et les données de ses sockets simulés ne deviennent pas authentifiées par ce packaging.
