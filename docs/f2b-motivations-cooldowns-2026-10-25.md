# F2-B — Arbitrage des motivations, rythme et repos simulé

**Date : 25 octobre 2026. Statut : fusionné dans `main` via [PR #29](https://github.com/Jean-Philippe56520/Microduck/pull/29), testé en logiciel sur catégories fictives.** Aucun robot physique, servo, caméra/microphone ou API Qwen n'est intervenu dans les vérifications. [409 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40239148712) (378 existants + **31 nouveaux tests F2-B**).

## 1. Pourquoi cette étape

[F2-A](f2a-passive-cognitive-intentions-2026-10-25.md) proposait des intentions passives de façon isolée. **F2-B ajoute une courte mémoire de cadence en RAM**, pour que les propositions successives tiennent compte de la prudence, de l'intérêt d'une nouvelle catégorie, de la sociabilité, du jeu et de l'énergie motivationnelle fictive.

Ce n'est **pas** un deuxième cerveau : la nouvelle méthode `AutonomyBrain.propose_balanced_passive(...)` appartient au **même** `AutonomyBrain`. Le module `passive_rhythm.py` contient uniquement l'état déterministe `PassiveRhythm` et les métriques `PassiveRhythmMetrics`. Le journal de catégories reste `PassiveObservationJournal(ExperienceMemory)`, sans nouvelle table.

```
F1-B PassiveRead (fixture socket Unix, mock-only)
   -> F2-A provenance, TTL, statut et motifs invalides refusés
   -> F1-A catégories et contradictions conservatrices
   -> F1-C fréquence historique d'une *catégorie*, pas d'un individu
   -> AutonomyBrain.propose_balanced_passive()
      -> scores des cinq motivations + filtre cooldown + repos hystérétique
      -> PassiveIntent (non exécutée, motor_commands_issued=0)
   -> voie moteur/sécurité OEM inchangée
```

## 2. Algorithme et garde-fous

| Mécanisme | Règle codée | Signification et limites |
| --- | --- | --- |
| Cadence cognitive | **≥ 0,5 s** entre deux propositions prises en compte | Un nouveau tick trop rapide propose `idle` et **ne change pas** l'énergie simulée |
| Anti-répétition | **3 s** de cooldown pour une même paire *(intention, type, catégorie)* | La même `ball` fictive ne déclenche pas sans cesse `observe` ; une **autre catégorie** demeure éligible |
| Prudence | `caution` augmente l'attrait de `idle` et abaisse les scores actifs | Le système peut choisir de ne rien faire malgré une observation |
| Curiosité | `curiosity` augmente `observe` et `inspect` | Inspecter `unknown` est uniquement une proposition cognitive, sans caméra ni approche |
| Sociabilité | `sociability` augmente `listen` sur catégorie sonore fictive | Aucune capture microphone ni phrase produite |
| Jeu | `play` augmente seulement l'intérêt passif pour `ball` ou `toy` | **Aucun jeu ou contact physique exécuté** |
| Énergie simulée | `energy` atténue l'activité ; entrée en `rest` si ≤0,22, sortie après ≥0,34 | Hystérésis pour éviter une oscillation repos/activité ; **ce n'est pas un niveau de batterie** |
| Évolution interne | +0,04 par tick `rest` fictif, +0,005 par tick `idle` validé, −0,015 par proposition active validée, valeurs bornées à [0,1] | **Comptabilité cognitive synthétique**, pas une conséquence physique ni un apprentissage du modèle |
| Contradictions/pannes | Source `status != ok`, provenance falsifiée, TTL périmé, batch invalide, horloge réinitialisée, répétition de séquence → `idle` | Aucun ancien événement n'est promu en mesure présente, aucune recharge de l'énergie synthétique sur lecture en échec |

**Validité des données :** `PassiveRhythm.tick()` appelle lui-même le contrat **F2-A** pour valider les observations. Un appel externe ne peut pas contourner cette vérification en soumettant un prétendu événement « déjà validé ». Le lecteur en fonctionnement reste une fixture Unix `mock_fixture_unix` avec `source=mock` ; aucune source constructeur `mediad` n'est authentifiée en F2-B.

**État borné :** l'historique en RAM conserve les **32 dernières propositions**, les cooldowns uniquement sur les catégories autorisées et des compteurs de décisions. Le temps monotone sert au délai pendant le processus courant. Après redémarrage, les **cooldowns sont remis à zéro** ; seuls les anciens faits de *catégorie* dans SQLite restent disponibles. Les horodatages et catégories historiques ne deviennent pas des perceptions fraîches ni des identités individuelles.

**Indépendance de la sécurité :** `AutonomyBrain.choose_from_snapshot()` est inchangé ; pour les fixtures F1 privées de `safe_area`, `floor_clear`, ToF et batterie vérifiés, la voie de sécurité maintient `halt`. Un résultat F2-B `observe`, `listen`, `inspect`, `rest` ou `idle` **n'est pas une commande** `robotd`, un vrai arrêt moteur, un mouvement de tête, un message vocal ni une autorisation de déplacement.

## 3. Vérifications reproductibles

La suite `tests/test_passive_rhythm.py` contient **31 nouveaux tests**, avec données entièrement fictives.

- [x] Trois cycles présentant le même `ball` sans journalisation : **`observe` puis `idle`, `idle`**, **2 blocs de cooldown**, **0 répétition active**. Une catégorie différente ne reste pas artificiellement bloquée.
- [x] Scores de décision : prudence élevée → `idle` ; absence de curiosité/jeu → `idle` ; absence de sociabilité → `idle` ; catégorie `toy` favorisée par le jeu fictif ; `unknown`/conflit → `inspect`.
- [x] Démarrage avec énergie fictive 0,20 : **quatre propositions `rest` successives**, énergie portée à 0,36, puis retour vers une proposition `observe`. Perte de source pendant repos : aucune recharge supposée.
- [x] Gestion de cadence trop rapide, doublon de séquence, réinitialisation d'horloge, donnée périmée/future, faible confiance, provenance frauduleuse et faux `floor_clear`.
- [x] **Vrai socket Unix local avec faux serveur** pour cinq cycles ; F2-B propose `observe`, `idle`, `inspect`, `listen`, `idle`, tandis que la voie de sécurité distincte propose `halt` à chaque étape.
- [x] Reprise par un autre processus Python et la même SQLite : catégorie `ball` déjà présente, mais cadence et énergie synthétique repartant à l'état **du nouveau cerveau**, sans reconnaissance d'un objet individuel.
- [x] Mesures logicielles accessibles : `cycles`, décompte par intention, `cooldown_blocks`, `consecutive_active_repeats`, historique circulaire de **32 propositions max** et `simulated_motivation_energy`. **Ce ne sont ni des wattheures, ni des mesures CPU/RAM ou de taux de reconnaissance.**
- [x] [CI sur `main` réussie : 409 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40239148712), plus la CI habituelle du projet. Aucune commande motrice F2-B.

Commandes reproductibles en environnement Python compatible :

```bash
python -m unittest discover -s tests -p test_passive_rhythm.py -v
python -m unittest discover -s tests -v
```

Les récompenses, les préférences durables et la prise en compte de **conséquences observées et vérifiées** seront traitées **uniquement en F2-C**. Une baisse de `Motivations.energy` de 0,015 ne prouve pas une dépense énergétique, et le retour à 0,36 après repos ne démontre pas une recharge.

## 4. Frontière de validation et suite

**F2-B prouve seulement le rythme d'un cerveau Python sur des données synthétiques**, pas la cognition ou les capteurs d'un Microduck physique. F2-A demeure disponible sans mémoire de cadence ; F2-B est **opt-in** par `propose_balanced_passive`. Le robot peut donc sélectionner `idle` plutôt qu'une activité forcée, sans effets physiques.

**Prochaine PR : F2-C seulement**, conséquences sourcées (fictives clairement séparées des résultats MuJoCo instrumentés), corrections et évolution **lente** des préférences basée sur un résultat réellement constaté dans sa source. F2-D traitera ensuite pannes multi-sessions, budgets et délais. Le chantier de locomotion P0/P1 demeure **suspendu**. L'[audit matériel](hardware-feasibility-audit-2026-10-25.md) n'est pas modifié : aucune nouvelle mesure du Rockchip n'a été produite.
