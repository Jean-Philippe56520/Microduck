# EX3 — Tendances d'attention réversibles sur expériences fictives

**26 octobre 2026 — [PR #72](https://github.com/Jean-Philippe56520/Microduck/pull/72) : CI hôte [#40415274293](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40415274293) réussie (1 175 tests exécutés, 19 ignorés, zéro échec dont 36 tests EX3), sur fixtures uniquement.** Le robot physique reste absent, et aucune expérience EX1/EX2 n'est une exécution `robotd` authentifiée. Ce lot démontre seulement que **la mémoire peut modifier légèrement une future proposition cognitive F2**, sans transformer une corrélation en cause, ni une réaction sociale en récompense.

## Objectif et niveaux de preuve

Après [EX1](ex1-mock-experience-ledger-2026-10-26.md) (proposition → statut fictif) et [EX2](ex2-mock-effects-kwipi-journal-2026-10-26.md) (indice avant/après et association temporelle), EX3 réutilise la **même** base SQLite `ExperienceMemory` pour une préférence d'attention **déduite à la demande**. Aucune mémoire supplémentaire, nouvelle écriture, pondération entraînée ou second contrôleur ne sont créés.

**La règle fondamentale :** `changed + temporal_only` ne prouve pas une causalité. EX3 ne peut donc pas apprendre « j'ai fait X, cela a provoqué Y, alors X est bon ». Il peut seulement apprendre une **tendance descriptive synthétique** : « dans plusieurs scénarios distincts, une observation de cette catégorie a été suivie d'un changement », ce qui motive parfois un peu plus d'attention passive. C'est une étape de validation architecturale, pas encore l'apprentissage social/physique de Kwipi.

États des preuves :
- **Codé :** calcul conservateur de tendances et branchement facultatif dans F2 ; consultation `--trend` dans le Journal de Kwipi.
- **À tester :** sessions fictives indépendantes, cas contradictoires, rétractions et redémarrages, préservation du comportement par défaut, CPU/SQLite hôte.
- **Non validé :** perception par caméra, micro, gestes, conséquences vécues, moteur, Qwen, apprentissage causal, RAM 1 Go / stockage 32 Go, batterie et température.

## Audit réutiliser / adapter / créer

| Existant / état vérifié | Choix EX3 |
| --- | --- |
| OEM épinglé `942e58e3` : `robotd` à 50 Hz, `mediad`, `tofd`, `pet-detect`, `robotctl` | **Ne pas modifier, ni lire ni piloter** dans EX3. Aucun nouveau service, boucle, contrôle moteur ou enregistrement média. |
| [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) cerveau et [#414](https://github.com/pollen-robotics/microduck/pull/414) cartographie | **Veille** : encore ouvertes/non fusionnées à la revue. Le design M9 proposé et mapd ne sont pas des API livrées sur notre OEM épinglé. |
| [Registre C3](community-reference-registry-2026-10-26.md) : QuackNav, microduck-brain, Quacksat, microduck-twin/lab/studio, GC-RENCAO, Smartulf123, quack-control | **Références seulement** : pas de modèle, code, média ou licence supplémentaire importée. Un algorithme de lecture SQL suffit ici. |
| `ExperienceMemory`, [EX1](../microduck_companion/experience_ledger.py), [EX2](../microduck_companion/experience_effects.py) | **Réutiliser** : provenance des sessions et des effets conservée ; scores recalculés par `SELECT` sur tables existantes. Zéro table `ex3_*`, zéro double écriture M1-B/F4-A/P2a. |
| [F2 AutonomyBrain](../microduck_companion/autonomy.py), [PassiveRhythm](../microduck_companion/passive_rhythm.py) et motivations | **Adapter minimalement** via un paramètre **optionnel** `expectations`. Sans l'option, règles, cadence, sécurité et sélections F2 restent inchangées. Le hint affecte au plus une proposition `observe` ou `listen` fictive, jamais une action OEM. |
| [Journal de Kwipi](../microduck_companion/kwipi_journal.py) | **Réutiliser** en ajoutant `--trend` en lecture seule. N'ajoute ni dashboard permanent ni collecte de télémétrie. |

## Règles de calcul EX3

`MockAttentionTrends(MockEffectJournal).summary(intention, category, now_wall_epoch_s)` effectue une lecture bornée de la SQLite existante, sans modifier `experiences`, `intent_preferences`, les résultats F4-A ou les fichiers média.

Une contribution doit satisfaire **toutes** les conditions :
- EX1 actif, `status=mock_executed`, source strictement fictive, intention `observe` ou `listen`, catégorie publique connue, session fictive explicite ;
- EX2 actif, source fictive, modalité cohérente et valeurs avant/après explicites, fraîcheur/chronologie cohérentes, confiance fictive d'au moins `0.75`, même scène, **aucun événement concurrent**, association `temporal_only` (si changé) ou `none` (si inchangé) ;
- **aucune** réponse sociale positive/négative, son hors modalité, observation `unknown`, retour interrompu/refusé, preuve retirée, affirmation Qwen ou simulation physique non liée ;
- **sessions distinctes** : au plus un indice par session et contexte, avec sélection du plus récent ; le nombre d'événements d'une seule session ne simule pas un apprentissage répété.

Les paramètres `3 sessions indépendantes`, `0.01` de biais par différence `changed - unchanged`, plafond `±0.04`, `32` sessions utiles maximum, lecture de `256` paires en fenêtre de `14 jours` restent **strictement des paramètres de laboratoire**. Ils ne sont pas des estimations de causalité ou des seuils capteur validés.

Une contradiction peut annuler la tendance, une rétractation ou l'expiration la remet à zéro, le redémarrage conserve les épisodes utiles mais ne sauvegarde pas un second score. Aucune adaptation automatique des motivations, de l'énergie/batterie, des commandes OEM, des limites de sécurité ou des préférences personnelles.

## Impact sur F2, opt-in et réversible

```python
# Dans le même processus et la même ExperienceMemory déjà ouverte :
ex1 = MockExperienceLedger(memory)
ex2 = MockEffectJournal(ex1)
trends = MockAttentionTrends(ex2)

proposal = brain.propose_balanced_passive(
    reading,
    journal=passive_journal,
    now_monotonic_s=100.1,
    now_wall_epoch_s=1770000150.0,
    expectations=trends,   # option EX3 explicite ; sinon comportement F2 intact
)
```

Seuls les candidats *déjà autorisés par la validation F2-A* reçoivent le biais. Une catégorie familière n'est re-proposée pour une simple observation que lorsque sa tendance fictive strictement positive a été répétée dans au moins trois sessions différentes. Le cooldown, la fatigue motivée, l'inaction, le refus de source, le statut `unknown` et la limite de cadence F2 demeurent prioritaires. Le résultat est un **PassiveIntent non exécuté** (`motor_commands_issued=0`), jamais un ordre.

**Raison vérifiable :** `repeated_temporal_mock_attention` distingue une proposition motivée par cette répétition d'une nouveauté de catégorie. Cela ne signifie pas « expérience bénéfique » et ne doit pas servir d'indicateur de bien-être.

## Journal de Kwipi sur PC, lecture seule

Pour une **base de test EX1/EX2 persistante déjà existante**, uniquement sur le PC :

```bash
python -m microduck_companion.kwipi_journal /chemin/vers/experiences.sqlite3 \
  --trend observe --category ball --at 1770000150
```

ou sortie CSV explicite :

```bash
python -m microduck_companion.kwipi_journal /chemin/vers/experiences.sqlite3 \
  --trend observe --category ball --at 1770000150 --format csv > tendance-kwipi-privee.csv
```

Pour une catégorie sonore, `--trend listen --category bark`. La consultation ne produit **aucun journal supplémentaire** sur le robot, n'active aucun service réseau, n'écrit rien en SQLite et conserve les drapeaux `causality_established=false`, `verified_on_robot=false` et `motor_commands_issued=0`. Les exports incluent uniquement de petites statistiques et la provenance `mock_fixture_only`, pas de noms individuels, audio, vidéo, reconnaissance humaine ou souvenirs personnels.

## Tests et suite

`tests/test_ex3_mock_attention_trends.py` couvre absence/single session, minimum de sessions indépendantes, doublons, contradictions, retrait EX1/EX2, signaux sociaux exclus, confusion/horloge, catégories et sons séparés, plafonnement, reprise SQLite, refus de bases incompatibles, absence d'écritures ou d'actes moteurs, F2 avec/sans `expectations` et lecture CLI depuis un second processus.

Ce lot doit **échouer fermé** lorsque sa mémoire ou provenance sont défaillantes. La CI hôte est une preuve logicielle, **pas une validation physique ou une démonstration de causalité**. La priorité demeure les vrais médias Cat-A2b et la résolution indépendante du chantier L avant tout déplacement. Une future expérience d'actions réelles exigera des accusés `robotd`, observations capteur authentifiées, crédit causal correctement qualifié et vérification des protections, sans second writer dans `ExperienceMemory`.
