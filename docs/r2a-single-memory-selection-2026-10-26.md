# R2-A — Sélection d'une mémoire unique pour le futur banc R2

**26 octobre 2026 — étude sur PC/fixtures seulement ; pas de robot, de média réel ni de migration.** Décision issue de [l'audit rétroactif R1.5](r15-retrospective-reuse-audit-2026-10-26.md) et du [protocole « réutiliser avant de créer »](development-reuse-protocol.md).

## Choix motivé par l'existant

| Responsabilité | Source réutilisée | Décision R2-A |
| --- | --- | --- |
| Connexion et historique SQLite | `ExperienceMemory` (`episodic_memory.py`) | **Conserver la même connexion et le même fichier** |
| Extraction visuelle (64 octets) / audio (16 octets) | `image_fingerprint`, `audio_fingerprint` dans `compact_multimodal_memory.py` (M1-A) | **Réutiliser les fonctions pures** ; aucun nouveau modèle |
| Première mémoire compacte | `CompactPatternMemory` (M1-A) et sa table `m1a_compact_patterns` | **Référence de laboratoire seulement** ; ne pas appeler `observe_*` sur la base R2 |
| Groupes et exemplaires multi-vues | `MultiviewPatternMemory` (M1-B) et tables `m1b_groups`, `m1b_signatures` | **Seul écrivain de signatures choisi pour R2** |
| Benchmark de reconnaissance | M1-B2 et F3 déjà présents | Réutiliser pour R2-B, sans le connecter à SQLite ni sélectionner un modèle |
| Moteurs, capteurs, PC | Services OEM et contrats F1/F5 existants | **Aucun raccordement** ni service nouveau |

Il n'existe **aucune troisième mémoire, aucune nouvelle table, aucun moteur de reconnaissance ajouté, aucune copie de parseur, aucune conversion de données** dans R2-A.

## Décision codée : option stricte, non activée par défaut

Le module **existant** `microduck_companion/multiview_pattern_memory.py` reçoit uniquement l'option facultative `r2a_single_writer=True` :

```python
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.multiview_pattern_memory import MultiviewPatternMemory

db = ExperienceMemory(":memory:")  # ou une base dédiée à des fixtures autorisées
try:
    memory = MultiviewPatternMemory(db, r2a_single_writer=True)
    # À R2-B seulement : appeler observe_image / observe_audio sur des fixtures
    # et jamais CompactPatternMemory.observe_* dans la même base.
finally:
    db.close()
```

Le mode strict vérifie **avant toute création de table M1-B** qu'aucune ligne héritée M1-A n'est présente. Une table M1-A **vide** est tolérée ; une table non vide provoque un refus, **sans migrer ni supprimer les anciens souvenirs**. Il refuse aussi un schéma M1-B partiel, des exemplaires sans groupe/cohérence de modalité et des limites nouvellement configurées qui provoqueraient une **éviction silencieuse au redémarrage**.

À chaque observation et chaque `prune()` R2-A, le contrôle est refait **dans la transaction SQLite `BEGIN IMMEDIATE`** du chemin M1-B. Si quelqu'un a écrit des lignes M1-A entre-temps, la prochaine opération R2-A est refusée sans écrire de signature M1-B supplémentaire. Si la mémoire existante est valide et dans ses budgets, le mode strict la rouvre sans déplacer ses données.

**Limitation explicite :** cela garantit une sélection contrôlée **pour les opérations passant par cette API R2-A**. Un ancien programme qui ouvre directement `CompactPatternMemory` peut toujours écrire sur sa propre table, avant que R2-A ne le détecte. Il ne s'agit **pas** d'un verrou global du fichier, d'une interception des autres processus ou d'une migration de schéma. L'absence de mélange requiert que l'expérience R2 utilise exclusivement le chemin sélectionné.

Les anciennes démonstrations M1-A et les tests historiques de M1-B restent inchangés : le mode `r2a_single_writer=False` par défaut conserve leur comportement. Aucun portage automatique ni aucune suppression de table ne sont réalisés.

## Vérifications hors ligne

Les tests `tests/test_r2a_memory_selection.py` couvrent : base vierge, répétitions d'une image, photo et audio dans les **mêmes** tables M1-B, réouverture sans perte, ancien schéma M1-A vide, données M1-A présentes avant ouverture, écriture héritée **après** ouverture depuis la même connexion et depuis une seconde connexion, refus de `prune`, quotas trop stricts et schéma partiel. Les fonctions pures M1-A restent disponibles pour comparer les empreintes sans ouvrir son écrivain persistant.

Contrat attendu :
- `m1b_groups` et `m1b_signatures` seulement pour les **signatures R2** (dans `ExperienceMemory` existant).
- Aucun `m1a_compact_patterns` créé par R2-A et aucune double écriture par R2-A.
- Aucun enregistrement de pixels, d'ondes, de voix ou d'images brutes ; groupes/labels toujours **non vérifiés**.
- Aucune requête Qwen, aucune commande moteur ni aucun accès à `mediad`, `tofd` ou `robotd`.
- La taille de signatures stockées ne représente ni la taille physique de SQLite ni le RSS sur RK3566.

**Preuve réellement observée sur la PR #55 :** [GitHub Actions #40319206601](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40319206601), **970 tests Python réussis**, dont 9 nouveaux tests ciblés R2-A, sur le commit `76859b80aa36e3582870158d9a76977dde233ce0`. Ces tests valident les contrats logiciels et les anciennes suites M1-A/B ; ils ne certifient ni une identité physique, ni la reconnaissance d'angles naturels, ni l'usage sur RK3566. La CI d'un éventuel commit documentaire ultérieur doit être revérifiée.

## Critère de sortie R2-A et passage à R2-B

**Décision prise :** une seule voie M1-B active pour le banc R2, M1-A gardée pour les comparaisons **sans écriture** et sans migration implicite. En R2-B, reprendre les mêmes validations et acquérir/identifier **plusieurs prises distinctes d'un même objet ou événement sonore** avec des négatifs ressemblants. Si des modèles d'embedding sont envisagés, vérifier au préalable leur licence, la compatibilité `feature_version`, les limites de SQLite et le coût CPU/RSS. Aucun nouveau module de persistance ne doit être créé sans lacune mesurée et décision de migration.

**Interdit à cette étape :** branchement physique, identification personnelle, usage de photos privées sur GitHub, décision motrice ou consultation automatique du PC. Le choix M1-B est **provisoire pour l'expérience R2**, pas une validation pour le RK3566.
