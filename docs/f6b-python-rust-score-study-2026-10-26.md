# F6-B — Étude Python / Rust : calcul cognitif pur et décision de portage

**26 octobre 2026 — [PR #46](https://github.com/Jean-Philippe56520/Microduck/pull/46), étude expérimentale hors robot et hors PC Qwen.** Le projet reste un prototype Python sur données fictives ; F6-A a inventorié les interfaces OEM sans aucun déploiement. Cette phase ne crée **pas** de service Rust embarqué et ne modifie pas `AutonomyBrain`, `PassiveRhythm`, les bases SQLite ni les services officiels.

## Question étudiée

« Un noyau Rust apporte-t-il une justification technique de remplacer du Python sur Microduck ? »

Réponse actuelle : **indécidable sans ressources mesurées sur le robot**. Un microbenchmark de fonction ne démontre ni une réduction de la RAM *de l’application complète*, ni une baisse d’énergie, ni le maintien de `robotd` à 50 Hz. Le bénéfice doit être mesuré avec le même traitement d'événements, une SQLite persistante réellement disponible et des interfaces OEM. Un prototype Rust n'est pertinent que **s'il résout une contrainte observée**.

### Frontière vérifiée dans le code existant

| Élément actuel | Rôle et dépendances | Position F6-B |
| --- | --- | --- |
| `AutonomyBrain` + `PassiveRhythm` (Python) | Motivations, cadence 0,5 s, cooldown 3 s, repos à hystérésis, décisions `observe/inspect/listen/idle/rest` sur fixtures | **Conserver tel quel** ; aucune réécriture du cerveau |
| `PassiveObservationJournal` + `ExperienceMemory` (SQLite) | Catégories, observations et conséquences **fictives** persistables, sans enregistrement média permanent | **Conserver tel quel** ; ne pas substituer un magasin Rust avant audit des volumes et de la partition de données |
| `FixtureUnixReader` (Python) | Source fictive bornée, horloges/fraîcheur et anti-rejeu ; aucune provenance constructeur réelle | **Conserver l'interface actuelle**, vérifier plus tard un vrai flux sous supervision |
| `OptionalOllamaWorker` (Python, PC facultatif) | Hypothèses rejetables ; aucune autorité sur les moteurs | **Hors noyau embarqué critique**, pas de LLM requis sur le RK3566 |
| `robotd`/ONNX (Rust constructeur) | Boucle motrice et sécurité OEM 50 Hz | **Ne jamais modifier ou concurrencer** ; seul chemin d'autorité moteur constructeur |

## Expérience isolée codée (aucun portage fonctionnel)

`experiments/f6b/passive_score.rs` est **un programme d'essai compilable avec le seul `rustc`**, sans dépendance Cargo, crate téléchargée, NPU, caméra, bus, Wifi ni SQLite. Il reprend uniquement l'expression pure de **`PassiveRhythm._score`** : trois intentions non motrices (`observe`, `inspect`, `listen`), cinq variables de motivation déclarées dans `[0, 1]` et des catégories fictives bornées. Les actions physiques, noms, identifiants de suivi, requêtes réseau et valeurs non finies sont rejetés dans le programme Rust.

`microduck_companion/f6b_score_probe.py` utilise **la fonction Python réellement présente** dans `PassiveRhythm`, et non une seconde implémentation de référence. Les **1 500 cas synthétiques déterministes** couvrent états extrêmes, seuils conventionnels et valeurs intermédiaires. La vérification inter-langages compare les résultats `f64` à une tolérance absolue **1 × 10⁻¹²**, sans prétendre à l'équivalence de la décision complète. Le score ne connaît pas la fraîcheur d'une caméra, le stockage, le cooldown, les conséquences ni les obstacles ; seuls les composants Python d'origine portent ces garanties.

`tests/test_f6b_score_probe.py` vérifie les fixtures Python, la parité Rust lorsqu'un `rustc` est présent, les entrées corrompues, les dépassements de taille/du nombre de lignes et la cohérence du calcul du checksum des benchmarks. `rustc --test` exécute **quatre** tests unitaires Rust indépendants. La CI impose explicitement `rustc` dans une étape dédiée, même si un utilisateur Windows ne possède pas le compilateur et que les tests Python inter-langages sont alors ignorés.

## Protocole de mesure sur hôte (non équivalent à une mesure embarquée)

La CI Ubuntu compile le programme Rust de test puis le binaire **optimisé `rustc -O`**. Elle vérifie la parité avant toute mesure. Elle chronomètre ensuite **120 000 appels au calcul de score** dans le programme Python existant et dans l'expérience Rust, avec identiques intentions/catégories/motivations fictives et somme des scores (checksum). Les chronomètres internes `time.perf_counter()` et `std::time::Instant` sont des **mesures du runner GitHub Actions**, non des mesures du RK3566. La commande `/usr/bin/time` mesure séparément le RSS **du processus hôte** et le temps écoulé, dans **deux exécutables très différemment emballés**.

**La comparaison mémoire brute n'est pas équitable :** le processus Python charge l'interpréteur et les modules de Companion, tandis que l'exécutable Rust ne contient que la fonction pure, sans SQLite, imports, framework ni moteurs. Ce n'est **ni un comparatif de cerveaux de même périmètre, ni une preuve de performance sur le robot**. Les effets des optimisations du compilateur, de la charge variable du runner, des démarrages de processus et de l'absence de perception dans le score empêchent d'utiliser les ratios comme décision de portage.

### Résultats réellement obtenus en CI hôte (26 octobre 2026)

La [CI expérimentale #40256023791](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40256023791) a réussi avec **841 tests Python**, **4 tests Rust**, **1 500 cas de parité** (**erreur absolue maximale 0,0**) et **120 000 appels par benchmark**. Environnement : runner Ubuntu GitHub Actions, `rustc 1.99.0` ; programme Rust optimisé (`-O`). Le checksum des deux langages est exactement `61592.00000002356` dans cet essai.

| Mesure *sur le runner* | Python `PassiveRhythm._score` | Rust expérimental (`score`) |
| --- | ---: | ---: |
| Temps interne de boucle, appel combiné `--benchmark` (120 000 scores) | **38,031 ms** | **3,503 ms** |
| Temps interne de boucle, processus indépendant (120 000 scores) | **32,587 ms** | **2,060 ms** |
| RSS maximum **du processus indépendant complet**, Linux `/usr/bin/time` | **17 068 Kio** | **2 132 Kio** |
| Latence globale de lancement indépendant, `/usr/bin/time` (précision 0,01 s seulement) | **0,10 s** | **0,00 s** |

**Interprétation correcte :** Rust est plus rapide pour **cette seule fonction** dans ce banc et son exécutable minimal utilise moins de mémoire de processus. Le binaire Rust n'intègre **aucun module équivalent** à Python (SQLite, supervision, réseau facultatif, capteurs, exceptions), les entrées sont déjà validées et les fréquences du robot ne sont pas reproduites. Le rapport d'usage mémoire compare des **processus de périmètre différent**. Ces chiffres ne justifient **pas** un portage ni ne prédisent une économie d'énergie sur le RK3566. Les calculs ont été effectués sur hôte x86-64 de CI, sans Microduck.

### Vérification reproductible

```bash
python -m unittest discover -s tests -v
rustc --edition=2021 --test experiments/f6b/passive_score.rs -o /tmp/f6b-rust-tests
/tmp/f6b-rust-tests
rustc --edition=2021 -O experiments/f6b/passive_score.rs -o /tmp/f6b-score
python -m microduck_companion.f6b_score_probe --rust-bin /tmp/f6b-score --benchmark
/usr/bin/time -f 'python_host_elapsed_s=%e python_host_peak_rss_kib=%M' python -m microduck_companion.f6b_score_probe --python-only-bench
/usr/bin/time -f 'rust_host_elapsed_s=%e rust_host_peak_rss_kib=%M' /tmp/f6b-score --bench
```

Ces commandes ne sont pas une procédure d'installation sur le Microduck. Elles supposent le compilateur Rust disponible sur le PC Linux ; `/usr/bin/time -f` n'est pas portable sur Windows. Aucun média ni donnée personnelle ne sont requis.

## Décision F6-B et critère de réouverture

**Décision par défaut : conserver le cerveau Python tant que la preuve n'exige pas un portage.** Le programme Rust F6-B reste dans `experiments/`, **non relié à l'exécution de Companion** et sans accès aux moteurs. Un portage du noyau cognitif embarqué ne serait envisagé qu'après audit réel :

1. Mesurer la RAM **libre** sur le robot au repos, la consommation RSS du **processus complet**, le CPU, la fréquence réelle de `robotd`, la température et l'espace disque réellement monté ; répéter au repos, en vision et pendant une session de mouvement **seulement si le chantier locomotion est résolu et les conditions sûres**.
2. Identifier une fonction *réellement* limitée (temps CPU, RAM ou risque d'interruption) que Rust isolerait plus simplement, sans ajouter de voie de commande moteur. Comparer la même entrée, les mêmes vérifications et les mêmes résultats Python et Rust sur un processeur équivalent.
3. Vérifier la parité **de décisions et de dégradations**, pas seulement de trois formules ; conserver un repli sûr, la provenance, les catégories `unknown`, les quotas, la SQLite et les politiques constructeur.
4. Mesurer **sur l'unité physique** la variation de RSS, CPU, cadence motrice, chaleur et énergie. N'intégrer le portage que si le gain mesuré dépasse sa complexité, son coût de maintenance et les risques de sécurité.

**Prochaine étape du plan : F6-C**, budgets de débit, stockage et événements du cœur *sans PC*, sur fixtures et instrumentation hôte d'abord ; aucune validation RK3566, Ollama/Qwen réel ni installation systemd n'est prétendue.
