# F4-C — Interactions sociales courtes et discrètes, propositions fictives

**26 octobre 2026 — nouvelle étape après [F4-B fusionnée (PR #38)](https://github.com/Jean-Philippe56520/Microduck/pull/38).** Ce lot doit être revu dans sa propre PR, sans fusion automatique et **sans commande d'actionneur**.

## 1. Contexte : ne pas fabriquer un robot bavard

Microduck Companion doit rester autonome, curieux et social, mais **peu bavard**. Les mécanismes précédents savent déjà proposer des attentions passives via `AutonomyBrain.propose_balanced_passive` (F2-A/F2-B), journaliser des catégories fictives, appliquer une cadence et retenir des expériences simulées. F4-C ajoute **une couche de présentation sociale non exécutable sur le cerveau existant**, pas un deuxième contrôleur autonome ni un entraînement de modèle.

`microduck_companion/mock_social_cues.py` ne consomme que `PassiveRead`, via `mock_fixture_unix`, avec snapshot `environment='mock'` et événements `source='mock'`. Un JSON qui dit « robot », une reconnaissance individuelle, une phrase de Qwen ou une hypothèse de classe ne deviennent **jamais** un interlocuteur autorisé. La couche existante F2-B conserve son rythme et ses règles de provenance. Les choix F4-C ne pilotent ni `robotd`, ni `mediad`, ni `tofd`.

## 2. Catalogue de propositions et garde-fous

| Choix F4-C | Condition minimale dans une fixture | Durée déclarée | Action réelle |
| --- | --- | ---: | --- |
| `silence` | **Par défaut** : opt-in absent, source absente, condition incertaine, mode calme, répétition ou budget épuisé | 0 ms | Aucune |
| `rest` | Le **cerveau existant** propose le repos en raison de la variable de motivation-énergie *simulée* ; aucun événement réel n'est déduit | 0 ms | Aucune |
| `glance` | Catégorie fictive unique `cat`/`dog`/`ball`/`toy`, fraîche et acceptée par le cerveau, consentement déclaré et mode calme désactivé | 250 ms | **Aucun mouvement de regard**, durée indicative |
| `chirp` | Signal sonore fictif catégoriel `bark`/`meow`, autorisation de **bref son** distincte et cerveau proposant `listen` | 180 ms | **Aucun son diffusé**, aucun micro lu |
| `play_cue` | Catégorie générique fictive `ball`/`toy`, **invitation au jeu explicitement déclarée** et motivation `play` ≥ 0,70 | 300 ms | **Aucun jeu ou mouvement exécuté** |

**Consentement :** `MockSocialContext` requiert trois affirmations de scénario (`operator_opt_in`, `supervised`, `privacy_reviewed`) et `quiet_mode=True` **par défaut**. Le son bref et l'invitation au jeu ont chacun leur autorisation **séparée**. Ces booléens sont de **simples déclarations de test** : ils ne vérifient pas l'identité, la tutelle, la présence réelle ni une permission matérielle. Même tous vrais, `MockSocialPlan` garde **`executed=False`, `physical_execution_authorized=False`, `real_consent_verified=False`, `identity_verified=False`, `speaker_commands_issued=0`, `gaze_motor_commands_issued=0` et `motor_commands_issued=0`**.

**Confidentialité et sécurité :** une entrée `person`, `unknown`, `speech`, `keyword_stop`, `keyword_microduck`, `keyword_viens`, une catégorie ambiguë, un signal de sécurité (`floor_clear`) ou un flux `sensor` sans authentification est rejeté comme une proposition de silence. Les sorties n'incluent **aucun nom de membre du foyer, identité individuelle, piste de suivi, transcript, photo ou voix**, et les sons « stop » fictifs ne constituent **pas** un véritable arrêt d'urgence. Les mouvements ne peuvent toujours être commandés que par le contrôleur officiel sur le vrai robot, non par ces plans.

## 3. Limites de répétition persistantes et silence contrôlé

Les **propositions**, non des événements effectivement joués, utilisent une petite table `f4c_mock_social_proposals` dans la **SQLite `ExperienceMemory` existante**, avec seulement `kind`, `category`, `recorded_epoch_s`, `source` (plus un identifiant auto-incrémenté).

- Intervalle global entre deux propositions sociales enregistrées : **10 secondes** minimum.
- Intervalle entre deux propositions de **même type et catégorie** : **60 secondes** minimum.
- Au plus **2 propositions `chirp` sur une fenêtre glissante de 600 secondes**. Ce sont deux propositions théoriques, **zéro émission sonore**.
- Rétention configurée **7 jours** et **128 lignes maximum**. Sélection et écriture des propositions dans une transaction SQLite pour éviter qu'un redémarrage court-circuite l'anti-répétition ; les horloges murales régressives bloquent aussi la proposition. La faible taille de table n'est **pas** une mesure de ressources du robot.
- Aucune préférence comportementale, récompense ou « émotion réelle » ne provient d'un simple plan. Le compteur de propositions ne compte **jamais des actions accomplies**.

Le mode silence/absence d'autorisation ne stocke aucune proposition. Les plafonds ne remplacent **pas** une politique audio réelle, de sûreté motrice ou de consentement parentale, qui reste à définir lors de l'intégration physique.

## 4. Preuves vérifiées sur GitHub Actions

Le prototype inclut :

- `microduck_companion/mock_social_cues.py` : contrôle d'origine, coordination avec **le cerveau existant** et génération de cinq catégories de plans **non exécutables**.
- `tests/test_mock_social_cues.py` : **27 tests nouveaux** sur consentement fictif, silence, priorité au repos, courtes propositions, catégories privées et paroles interdites, échecs de sources, budgets, séquences, absence de sortie audio/motrice, persistance de cooldown après ouverture de SQLite par un second processus et maintien du `halt` existant.
- `microduck_companion/f4c_social_demo.py` : démonstration en **deux processus Python indépendants**, avec le même fichier SQLite. Le premier observe un **`bark` fictif** : mode par défaut silencieux, puis une proposition `chirp` **non exécutée** après opt-in de scénario. Le deuxième reçoit exactement la même fixture dans un nouveau processus : **`silence`** par limite anti-répétition persistée.
- `.github/workflows/python-tests.yml` : exécute la compilation, les tests et les deux sessions de démonstration.

**[CI du 26 octobre 2026, commit `d3639e8d7c`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248330199)** : **689 tests Python réussis**, compilation réussie, deux sessions F4-C réussies, **1 proposition mémorisée**, **0 haut-parleur**, **0 commande motrice**, **0 média enregistré**.

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.f4c_social_demo --database /tmp/f4c-social.sqlite3 --session first
python -m microduck_companion.f4c_social_demo --database /tmp/f4c-social.sqlite3 --session second
```

## 5. Reste à faire

**Non livré :** mouvements réels de tête, yeux ou regard ; son diffusé, détection effective de mots-clés, identification individuelle, traitement de voix/microphone, liaison OEM matérielle, interaction non surveillée avec enfants et animaux, mesures de charge sur RK3566, chauffe et batterie. Un mot « stop » **n'est pas détecté réellement** par F4-C.

**F4-D**, lot séparé après revue de F4-C, étudiera des **associations locales, volontaires, révocables et consenties**, sans biométrie permanente. Les données réelles de l'entourage resteront hors GitHub. L'ensemble des fonctions vitales doit continuer sans PC ni Internet ; aucun résultat ici ne valide l'utilisation autonome du robot physique.
