# EX2 — Effets fictifs, causalité incertaine et Journal de Kwipi à la demande

**26 octobre 2026 — [PR #71](https://github.com/Jean-Philippe56520/Microduck/pull/71) et [CI hôte #40413719554](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40413719554) : 1 139 tests exécutés, 19 ignorés, zéro échec (dont 28 tests EX2), fixtures uniquement.** Ce lot réutilise [EX1](ex1-mock-experience-ledger-2026-10-26.md) et la **même** `ExperienceMemory.conn`. Il n'exécute aucun mouvement, ne capture aucune image ni voix, n'utilise ni Qwen ni un service OEM et ne valide rien sur le Microduck physique. La priorité [Cat-A2b](cata2b-private-low-camera-protocol-2026-10-26.md) demeure inchangée.

## 1. Objet exact : consulter les souvenirs, ne pas surveiller en permanence

La demande utilisateur est de **consulter, à la demande et localement**, le journal cognitif des expériences et le résultat de leur comparaison, sans recopier le monitoring constructeur et sans créer de collecteur de télémétrie permanente.

`microduck_companion.experience_effects` rapproche **deux indices de fixture** (avant/après) uniquement si leur session, séquence et chronologie correspondent à un cycle EX1 `mock_executed`. Le résultat se limite aux statuts :
- `changed` / `unchanged` / `indeterminate` : variation **déclarée dans une fiction**, non validée par caméra, audio, ToF ou actionneur ;
- `temporal_only` : variation après la résolution fictive, **pas un lien causal établi** ;
- `confounded` : variation malgré un autre événement concurrent ;
- `indeterminate` : source insuffisante, catégorie inconnue, faible confiance ou rupture de scène ;
- `none` : aucune variation visible dans l'indice synthétique.

**Aucun score de récompense et aucune préférence ne sont modifiés.** La causalité et l'effet sur le comportement ne sont pas prouvés. En particulier, même un indice `friendly_signal` après une inspection ne signifie pas « l'inspection a provoqué la caresse ». L'évaluation d'un résultat réellement exécuté par `robotd` reste une phase ultérieure, sous matériel.

`microduck_companion.kwipi_journal` lit **EX1 et EX2 ensemble**, à partir d'une SQLite existante, sans écrire, sans créer le fichier s'il manque, sans démarrer de service, sans streaming, ni connexion réseau. Les champs exportés restent strictement bornés ; l'export est privé et volontaire.

## 2. Audit réutiliser / adapter / créer

| Source vérifiée | Décision |
| --- | --- |
| OEM épinglé [`942e58e3`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) : `robotd`, `mediad`, `tofd`, `pet-detect`, `robotctl health/monitor/logs/vetbook` | **Réutiliser les outils OEM pour le diagnostic physique futur**, pas ajouter de boucle de monitoring. La branche EX2 n'appelle aucune interface OEM et ne modifie ni la sécurité ni les politiques motrices. |
| [PR constructeur #381](https://github.com/pollen-robotics/microduck/pull/381) et [#414](https://github.com/pollen-robotics/microduck/pull/414) | **Veille** : ouvertes, non fusionnées au contrôle du chantier ; #381 design cerveau, #414 carte. Rien à importer pour un lecteur SQL local. |
| Références tierces [registre C3](community-reference-registry-2026-10-26.md) : QuackNav, microduck-brain, Quacksat, microduck-twin, GC-RENCAO, Smartulf123, quack-control et microduck-lab/studio | **Ne rien copier** : les besoins EX2 sont des filtres SQL et deux signaux synthétiques typés, sans modèle tiers, audio, simulateur ni coût de licence supplémentaire. |
| [F2 `PassiveIntent`](../microduck_companion/passive_intentions.py) → [EX1 `MockExperienceLedger`](../microduck_companion/experience_ledger.py) | **Réutiliser**, en conservant `mock_executed` comme un marqueur fictif et `refused/interrupted` comme sans résultat causal. |
| [`ExperienceMemory`](../microduck_companion/episodic_memory.py) | **Adapter avec une unique table EX2 dans la même connexion SQLite**, jamais seconde base ni migration de M1. EX2 écrit uniquement des paires d'indices de fixture ; EX1 n'est pas réécrit. |
| [P2a](../microduck_companion/mock_cycles.py), [F4-A](../microduck_companion/behavioral_memory.py), [M1-B](../microduck_companion/multiview_pattern_memory.py) | **Ne pas fusionner** des souvenirs hétérogènes ni créer de double écriture. Aucun résultat P2a/F4-A ou empreinte M1-B n'est promu en preuve EX2. |
| [F6-D `resource-audit.sh`](f6d-hardware-audit-protocol-2026-10-26.md) | Outil ponctuel de diagnostic matériel, inchangé. Aucun budget RAM/CPU/stockage réel prétendu. |

## 3. Contrat d'observation EX2

- `MockCue(kind,value,observed_at_epoch_s,confidence,source='mock_fixture_only')` : valeurs **fermées**, sans texte libre, noms de personne, IDs d'objets/animaux, médias ou transcriptions ; `motion`, `distance`, `social`, `sound`.
- `MockEffectPair(session,sequence,before,after,same_scene,competing_event)` : uniquement les jetons de session synthétiques EX1, temps monotones **de fixture exprimés ici en epoch synthétique**, même modalité, deux indices strictement ordonnés.
- `MockEffectJournal(ledger).record(pair)` : refuse un EX1 absent, rétracté, refusé, interrompu, non résolu, inactif, sans cible, d'une autre modalité ou hors fenêtre d'essai. Une même preuve identique est idempotente ; une autre preuve pour le même EX1 est rejetée. Le seul résultat automatique admissible est **descriptif** (`temporal_only`, `confounded`, etc.), jamais une causalité positive.
- `retract()` : invalide l'effet ; la rétractation du parent EX1 masque aussi l'effet en lecture. Réactivation interdite ; aucune préférence produite.
- `history()` : bornée, inclut source et indicateurs constants `causality_established=False`, `verified_on_robot=False`, `motor_commands_issued=0`.

Les seuils **sur fixtures** sont ici : 2 s avant la proposition, 2 s après la résolution fictive, confiance déclarée minimale 0,75, 256 traces stockées, 14 jours de rétention, 50 résultats au maximum. Aucun de ces chiffres n'est un seuil de capteur ou budget matériel calibré.

**Précision importante :** `temporal_only` n'est pas une probabilité de causalité. La succession d'une réaction sociale et d'un geste ne justifie pas « positif » ou « négatif ». La détection d'une voix n'implique pas que « bravo » ou « non » aient été compris. L'apprentissage progressif à partir de véritables conséquences reste **EX3 et l'intégration matérielle**.

## 4. Lecture du Journal de Kwipi, sur PC uniquement

Pour une **base de test persistante déjà existante** et située localement sur le PC (ne pas utiliser un chemin fictif tel qu'un chemin robot non monté) :

```bash
python -m microduck_companion.kwipi_journal /chemin/vers/experiences.sqlite3 --limit 20
```

Export CSV volontaire des seules lignes existantes :

```bash
python -m microduck_companion.kwipi_journal /chemin/vers/experiences.sqlite3 --format csv --category ball > journal-prive.csv
```

Pour les essais avec dates fictives, `--at 1770000002`. `--status refused`, `--include-withdrawn` et `--limit 1..50` sont disponibles. Le programme ne crée **aucun** dossier ou fichier SQLite ; `> journal-prive.csv` est une action explicite de l'opérateur **sur son PC**, et les lignes retournées sont issues de tables **fictives uniquement**. Les exports n'incluent ni captures, ni voix, ni noms, ni texte libre, ni adresses réseau ; les sessions sont des jetons opaques de test.

Pour les diagnostics matériels OEM réels, conserver distinctement les commandes constructeur `robotctl health --json`, `robotctl monitor`, `robotctl logs`, `robotctl vetbook --json`. **EX2 ne lit pas ces journaux**, et ne prétend pas produire une analyse complète des données OEM. En production, une future exportation privée autorisée pourra rapprocher les deux chronologies **sans créer de faux liens de causalité**.

## 5. Tests et preuves visées

`tests/test_ex2_effects_journal.py` couvre le cycle nominal, les replays, les refus, absences de résolution, valeurs malformées, catégories inconnues, faibles confiances, événements concurrents, scène rompue, absence de variation, son et signal social, horodatages divergents, rétractions parent/enfant, réouverture en second processus, lecture EX1 seule sans table EX2, filtres, export JSONL/CSV, absence de fichier, bases étrangères, absence de modification de la SQLite.

**Seule la CI hôte peut valider les tests de cette PR.** Aucun test n'utilise caméra, micro, PC Qwen, NPU, `robotd` réel, moteur, déplacement, stockage Yocto ou RK3566. Une réussite CI atteste uniquement une règle de provenance logicielle sur fixtures.

## 6. Limites et étape suivante

- EX2 : lien **temporel et descriptif**, pas une causalité apprise ni une habitude effective.
- Lecteur : EX1 + EX2 seulement dans cette première livraison. Les autres mémoires `ExperienceMemory`, `F4-A`, `M1-B` et les journaux OEM restent distincts. « Tout ce que Kwipi sait » nécessitera une lecture structurée de chaque famille de preuve, sans fusion arbitraire, dans un lot ultérieur.
- Le futur déploiement en dur exige de confirmer partition `/var/lib/robot`, permissions, taille physique SQLite + WAL/index, ressources disponibles, révisions de carte, mémoire, CPU/thermie, sûreté OEM, et consentement aux exports privés. **Aucune écriture persistante sur robot n'est autorisée par EX2.**
- EX3 pourra adapter très progressivement les choix F2 après **preuves indépendantes d'effets réellement observés et attribution causale vérifiable** ; aucun score ne découle de ce lot.
