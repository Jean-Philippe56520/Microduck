# F4-C — Interactions sociales courtes, silencieuses et non exécutables

**26 octobre 2026 — branche `feat/f4c-social-cues-mock-only-20261026`, à revoir et non fusionnée.** Cette phase suit [F4-B fusionnée par PR #38](https://github.com/Jean-Philippe56520/Microduck/pull/38) avec [662 tests Python sur les fixtures spatiales](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40247570297). **Aucun robot physique disponible, aucun son ni mouvement émis.**

## 1. Une couche sociale, pas un second cerveau

`microduck_companion/mock_social_cues.py` enveloppe le **même** `AutonomyBrain.propose_balanced_passive` (F2-B), son `PassiveObservationJournal` (F1-C), ses motivations et sa **SQLite `ExperienceMemory`**. La sortie `MockSocialPlan` décrit une intention fictive et comporte des garde-fous explicites : `executed=False`, `real_consent_verified=False`, `real_sensor_authenticated=False`, `identity_verified=False`, `physical_execution_authorized=False`, et **zéro commande vers les moteurs, le regard ou le haut-parleur**.

Aucun client `mediad`, `robotd`, `tofd`, moteur audio, moteur de regard, reconnaissance de voix ou connexion PC/Qwen n'est créé. Le code n'a accès qu'à une `PassiveRead` provenant de la voie de fixtures `mock_fixture_unix` et ne considère jamais la simple chaîne `source=mock` comme la preuve d'un vrai capteur.

## 2. Arbitrage social, avec silence par défaut

| Situation sur *fixture* | Proposition fictive | Autorité |
| --- | --- | --- |
| Absence d'opt-in explicite, de supervision ou de vérification privée déclarée | **`silence`** | Aucun mouvement ni son, pas de trace de proposition active |
| Aucun signal actuel, source perdue, catégorie inconnue, ambiguïté, faible confiance | **`silence`** | Aucun souvenir ancien utilisé comme perception en temps réel |
| Mode calme déclaré | **`silence`** pour regards/sons/jeu | L'option silencieuse prime sur les propositions actives |
| Énergie **motivationnelle fictive** basse et observation fictive valide | **`rest`** | Repos théorique, pas d'état moteur ni de recharge physique |
| Catégorie visuelle fictive `toy/ball/cat/dog` et conditions réunies | **`glance`**, *durée proposée* 250 ms | Aucune cible spatiale, orientation ou mouvement de tête exécuté |
| Jouet/balle fictifs, autorisation spéciale de jeu et motivation `play ≥ 0,70` | **`play_cue`**, *durée proposée* 300 ms | Invitation abstraite, sans geste ni moteur |
| Catégorie sonore fictive `bark/meow`, opt-in **audio séparé** | **`chirp`**, *durée proposée* 180 ms | **Aucun fichier audio, aucune onde ni commande haut-parleur** |

Les durées ci-dessus sont **des durées nominales proposées**, jamais mesurées. Les catégories `person`, `unknown`, `speech`, les mots-clés `stop`/`viens`/`Microduck`, les noms non reconnus et tout mélange de catégories incompatibles **ne produisent aucune interaction sociale**. Le mot-clé `stop` de ces fixtures **n'est pas** un véritable arrêt d'urgence ; la sécurité reste exclusivement chez le constructeur.

`MockSocialContext` exige des **déclarations booléennes explicites** pour l'opt-in, la supervision, la confidentialité, le mode calme, l'audio bref et le jeu. **Ces déclarations ne vérifient ni un opérateur, ni un consentement d'enfant, ni un micro/haut-parleur authentique**. Elles ne seront pas réutilisées comme autorisation matérielle ; une future intégration physique devra disposer de contrôles supplémentaires, notamment parentaux.

## 3. Fréquence, silence et reprise sans réseau

La table `f4c_mock_social_proposals` conserve seulement **kind** (type générique), **category** (catégorie générique parmi six choix), date Unix et provenance `mock_social_proposal_only`. **Aucune identité, nom, ID de suivi, transcription, audio, photo, position, preuve de consentement ou action exécutée n'est enregistrée.**

- **Intervalle global minimal : 10 s** entre deux propositions actives ; **60 s** pour une même combinaison de type et catégorie.
- **Au plus deux propositions de son en dix minutes**, sur une fenêtre temporelle glissante. Le même mécanisme est conservé **entre deux processus Python** grâce à la SQLite locale.
- Historique des propositions plafonné à **128 entrées** avec **7 jours de rétention** ; refus en cas de recul de l'horloge murale par rapport à la dernière proposition.
- Un échec SQLite, une donnée incohérente ou un plafond de fréquence ramène à **`silence`**. Les décisions F2-B peuvent encore modifier l'**énergie motivationnelle simulée** de leur propre modèle lors d'un cycle d'attention, même si le rendu social est ensuite supprimé ; ce n'est pas de l'énergie physique ou une preuve d'exécution.
- Les budgets sont ceux des **propositions**, pas des sons réellement émis. Le système est pensé pour ne rien faire souvent, plutôt que parler ou bouger par réflexe.

Le classement `cat` ou `dog` n'identifie **jamais** un individu : les bancs F3-D n'ont reconnu correctement que **8/16 photos d'animaux**, et F3-E n'a **pas** réalisé les contre-annotations humaines des 48 sources publiques. Aucun avis du LLM ni souvenir F4-A/B ne peut se faire passer pour une perception sociale actuelle.

## 4. Tests et démonstration

`tests/test_mock_social_cues.py` ajoute **27 tests** : consentement revendiqué et révocation par refus, silence, repos, faible motivation, option jeu, audio sous opt-in distinct, catégories sensibles, collisions, catégories contradictoires, données non fiables/périmées, plafonds de fréquence et de sons, persistance entre processus, refus des champs exécutables, arrêt moteur et erreurs SQLite.

[CI Linux : **689 tests Python réussis**, compilation et validation de la démonstration F4-C dans deux processus distincts](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248330199).

La démonstration du premier processus produit **une proposition fictive de `chirp` de 180 ms, avec zéro appel au haut-parleur**, après opt-in **déclaré uniquement dans le scénario** ; le deuxième processus relit la même SQLite et répond **`silence`**, à cause du délai global entre propositions. Il n'y a ni enregistrement, ni lecture de vrais capteurs, ni son, ni moteur :

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.f4c_social_demo --database /tmp/f4c-mock.sqlite3 --session first
python -m microduck_companion.f4c_social_demo --database /tmp/f4c-mock.sqlite3 --session second
```

## 5. Reste à valider

Ce travail ne démontre **aucune précision réelle de reconnaissance sociale, aucune réaction d'un animal, aucune autonomie énergétique, aucun comportement sonore ou visuel réel, aucune mesure RAM/thermique sur RK3566, aucune conformité de fonctionnement sur matériel Microduck**. Les mécanismes OEM `robotd`/`mediad`/`tofd` ne sont pas modifiés.

Le prochain lot **F4-D**, après revue et fusion éventuelle de F4-C, concernera l'**association volontaire et révocable d'identités locales** sur données privées et avec contrôle parental, sans biométrie permanente. Les tests publics utiliseront uniquement des identités fictives. Les médias et informations personnelles resteront hors GitHub. Le chantier de locomotion P0/P1 reste suspendu.
