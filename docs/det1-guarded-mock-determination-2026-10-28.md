# DET-1 — Détermination bornée au sein de F2

**Date :** 28 octobre 2026. **Statut :** [PR #143 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/143) dans `main@deed1858`, code et tests **PC-fixtures** uniquement ; [Python 1 694 tests dont 5 ignorés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40777508447), [N5/N6](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40777508714), [CI post-fusion](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40777728509) **réussies**. Aucun robot réel validé. Le [plan directeur](plan-action.md) reste l'autorité. Voir [plan global](kwipi-goals-determination-memory-qwen-observability-plan-2026-10-28.md) et [MEM-1](mem1-mock-persistent-goals-2026-10-28.md).

## 1. Porte OEM-first et hypothèse falsifiable

**Observation.** Sur `main@12dc426b2756ec75ea1d418781054ed504fa6866`, `AutonomyBrain` délègue ses intentions passives à **son** `PassiveRhythm` F2-B ; F2-A vérifie provenance fictive, fraîcheur, séquences et catégorie. Le rythme F2-B applique déjà repos avec hystérésis, cadence et cooldown. MEM-1 dans l'**unique SQLite** `ExperienceMemory` possède les états d'objectifs, liens avec EX1, rétractions et quotas. EX1/EX2 restent des fixtures, jamais des exécutions OEM.

**OEM épinglé vérifié.** `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Lecture : `robotd/src/intents.rs` (commandes horodatées et deadman), `duck-ipc-proto/src/lib.rs`, `robotctl/src/monitor.rs`, `robotd-params/src/lib.rs`, `docs/design/robotd-design.md`, `docs/robot/cheatsheet.md`. `robotd` seul contrôle les moteurs ; `robot.do accepted` ne prouve ni fin de mouvement ni effet. OEM #381 (cerveau) et #414 (cartographie) restent ouvertes/non livrées. Le robot est absent : politique ONNX, scène/collisions, `robotctl health/policy list/monitor` et version installée sont **inconnus**. SIM-E2 #101 locomotion non résolue.

**Hypothèse H-DET-1.** Une détermination graduelle change le choix **entre intentions passives déjà admissibles** pour un objectif actif encore non essayé, sans créer de candidat, franchir la prudence, attribuer une récompense ou déplacer le robot.

**Preuves visées.** Ablation appariée : à mémoire et perception fictive identiques, détermination 0 vs 1, puis mémoire optionnelle absente. Tests négatifs : cooldown, énergie/repos, prudence, source périmée/forgée, catégorie absente/déjà connue, objectif suspendu/rétracté/expiré, tentative EX1 liée, erreur SQLite et valeur NaN. Suite Python et N3/N5/N6 restent obligatoires.

**Échecs bloquants.** Nouveau décideur, second writer ou stockage, priorité motorisée, répétition sans élément nouveau, saut de cooldown, résurrection de correction, interprétation de `mock_executed` comme action réelle, CI rouge. **Retour arrière :** omettre `goals` (défaut), ce qui restaure strictement l'arbitrage F2 antérieur ; retirer le biais sans toucher aux souvenirs MEM-1.

## 2. Réutiliser / adapter / créer

| Composant | Décision | Justification |
| --- | --- | --- |
| `AutonomyBrain`, `Motivations`, `PassiveRhythm` | **Adapter F2 existant** | Aucun second arbitre ni daemon |
| `MockGoalMemory`/EX1/`ExperienceMemory.conn` | **Réutiliser ; ajouter une lecture SQL bornée** | Pas de nouvelle table ou copie d'expérience |
| F1-B/F2-A/`PassiveObservationJournal` | **Réutiliser inchangé** | Fraîcheur, provenance, catégories et danger ne dépendent jamais d'un souvenir |
| `robotd` et OEM JSON-RPC | **Ne pas appeler** | Propriétaire exclusif du moteur ; aucune action réelle dans le lot |
| Qwen 9B/PD2/EX4 | **Ne pas brancher** | Conseil, humeur et effet physique nécessitent leurs propres preuves |
| QuackNav/microduck-brain, Quacksat, Twin, GC/Smartulf, lab/studio | **Références C3 uniquement** | Pas de dépendance nécessaire pour le score |
| Tests DET-1 et ce dossier | **Créer** | Prouver une modification de choix plutôt que de supposer un gain |

## 3. Contrat du lot

- Nouvelle motivation `determination` dans `Motivations`, en dernière position (compatibilité des cinq anciens paramètres), défaut **0,55**, valeurs finies dans [0,1].
- Entrée facultative `goals: MockGoalMemory | None = None` dans `AutonomyBrain.propose_balanced_passive` et `PassiveRhythm.tick`. Vérifier que les deux partagent **la même SQLite** ; pas d'instanciation autonome.
- `MockGoalMemory.attention_focus` lit au plus 33 lignes, uniquement des objectifs **actifs, non rétractés, âgés au plus de 14 jours fictifs et sans lien EX1**, y compris EX1 ensuite purgé, refusé ou rétracté : un lien persistant neutralise le biais, jamais une preuve de « nouvelle stratégie ». Les types/catégories sont à vocabulaire fermé.
- F2 doit **d'abord** valider source, horloge, séquence, repos, absence de danger observable, candidats et cooldown. Il peut ensuite ajouter au classement au plus `0,18 × determination` pour une paire intention/catégorie **déjà admise** et correspondante. Il ne transforme pas un objectif en candidat.
- La raison `det1_mock_goal_focus` est un code de provenance fictive. La sortie reste `source=mock`, `executed=False`, `motor_commands_issued=0`, `request_pc_analysis=False`. Les scores n'écrivent aucun succès et ne changent pas les préférences réelles.
- Une erreur de lecture de l'objectif (si le mode optionnel est actif) produit `idle / det1_goal_memory_unavailable`, sans consommer l'énergie simulée.
- **Limite voulue :** aucune reprise des objectifs **déjà tentés**, même si la transition d'état MEM-1 indique `new_view`. Les étiquettes de contexte ne prouvent pas une nouvelle observation indépendante. Cette porte est pour DET-2/MEM-2, après preuve de nouveauté et de causalité.

## 4. Évaluation et limites

**Expérience positive attendue :** dans une scène fictive montrant chien et balle, F2 préfère initialement la balle ; si un objectif fictif actif « observer chien » n'a aucune tentative liée, détermination forte peut classer le chien devant. Détermination nulle ou `goals=None` conserve le témoin. Le cas des objets `unknown` est testé séparément, sans reconnaissance prétendue.

**Commandes effectivement exécutées dans la CI (fixtures et tests hôte uniquement) :**
`python -m unittest discover -s tests -p test_det1_goal_determination.py -v`
`python -m unittest discover -s tests -v`
`python -m scripts.n3_sqlite_audit --output /tmp/n3-det1.json`
La CI valide également N5/N6, présence des exclusions host-only et analyses non motrices. Les différences de score ne constituent **ni apprentissage autonome, ni action, ni effet causal**.

**Ressources et arrêt :** aucun nouveau schéma, modèle, réseau, média, socket, boucle, seconde SQLite ou journal à 50 Hz. Lecture bornée et optionnelle : coût CPU/temps non encore mesuré sur RK3566. Les quotas MEM-1/EX1 sont des prototypes non dimensionnés. Robot absent = aucune validation physique.

**Suite :** MEM-2 rappel avec provenance et preuves de nouveauté, PER-1 humeurs cohérentes, QW-1 conseiller Qwen PC et ablations E2E. Aucune action sur vivant ou manipulation autonome n'est autorisée par DET-1.
