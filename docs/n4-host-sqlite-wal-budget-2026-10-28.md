# N4 — Taille SQLite/WAL sur fixtures et rétention après réouverture

**Date :** 28 octobre 2026. **Statut :** outil et mesures PC/fixtures [CI N4 #40749269400 réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40749269400), sur la [PR #132](https://github.com/Jean-Philippe56520/Microduck/pull/132), commit de code `e2552ecf72c45d527783e46082aeedd2ad16b21b`. Dernier commit documentaire et nouvelle CI à vérifier avant fusion. Aucune mesure sur le RK3566 ni aucun effacement de la SQLite personnelle de Kwipi. Autorité : [`plan-action.md`](plan-action.md). Suite de [N3 #131](https://github.com/Jean-Philippe56520/Microduck/pull/131) fusionnée au commit `241acde368d5abc5d456ebbe3d725656735934fa` ; les 22 tables relevées en N3 représentent **le code entier**, pas les tables actives du profil N4.

## 1. Porte préalable, hypothèses et échec

**Observation :** les tests existants [C2](../tests/test_c2_correction_retention.py) vérifient déjà la persistance des 54 clés fermées et leur non-réintroduction après plusieurs TTL ; [R2-A](../tests/test_r2a_memory_selection.py) vérifie l'écrivain sélectionné M1-B et le refus des lignes M1-A avant écriture. Les **80 octets** de deux empreintes tests ne mesurent pas le disque SQLite ni le journal WAL. N3 a recensé un seul site d'ouverture SQLite écrivable, 3 lecteurs RO et 4 SQL dynamiques à revoir.

**Question bornée :** dans **un seul fichier SQLite temporaire** généré par nos APIs, combien d'octets prennent le fichier et les fichiers `-wal`/`-shm` avant et après les écritures, puis après réouverture, purge d'une hypothèse active et checkpoint ? Un marqueur de correction reste-t-il bloquant après réouverture ? Les signatures M1-B sont-elles intactes et M1-A non activé ?

**Hypothèse de travail :** la rétention C2 garde les retraits sans empêcher l'expiration normale des hypothèses actives, et M1-B stocke ses deux signatures sans M1-A, pendant que le WAL peut temporairement dépasser le poids de données logiques. **Un résultat contraire ou une CI rouge bloque la fusion** : il ne faut pas masquer un test avec `VACUUM` ou une modification du schéma pour obtenir une petite taille.

**Risques :** les octets réels dépendent de SQLite, de son paramétrage, de l'OS, du checkpoint et de la charge. La fermeture de la dernière connexion peut checkpoint/tronquer/supprimer le WAL. `combined_bytes` inclut le fichier `-shm`, qui n'est **pas** un volume de souvenirs durables. Les quotas de BLOB et le nombre de tables ne constituent pas un budget flash/RAM sur robot.

## 2. OEM d'abord, réemploi et séparation de responsabilités

- Constructeur épinglé **inchangé** : [architecture `robotd` seul pilote](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/design/architecture.md), [roadmap M9](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/project/roadmap.md), [historique autonomie](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md) ; gitlinks `microduck@942e58e3`, `microduck_rl@b02fdea4`. M9 historique non livré au commit épinglé ; PR OEM #381 et #450 **ouvertes/non fusionnées** à l'audit. `robotctl version/health/monitor` requis **sur robot seulement** avant portage, robot absent ici.
- Communauté [registre C3](community-reference-registry-2026-10-26.md) : QuackNav et autres références n'apportent pas de stockage cognitif validé à intégrer en N4. Aucun nouveau paquet, modèle ou code externe.
- **Réutiliser :** `ExperienceMemory`, `CategorySemantics`/C2, `MultiviewPatternMemory(r2a_single_writer=True)`/R2-A, générateurs **synthétiques existants** `_synthetic_pixels` et `_synthetic_audio`, `unittest`, `sqlite3`, workflow Python actuel.
- **Adapter :** ajouter un petit profil de test dans `scripts/` et l'exécuter dans la CI actuelle. **Ne pas créer :** deuxième SQLite opérationnelle, nouveau writer, schéma, modèle, pilote, robotctl alternatif, démo de motricité, politique WAL sur robot.

## 3. Scénario mesuré, sans média personnel

`python -m scripts.n4_sqlite_fixture_budget --output /tmp/n4-sqlite-budget.json`

L'outil **n'accepte aucun argument de chemin vers une base SQLite**. Il utilise exclusivement `TemporaryDirectory`, puis supprime la base expérimentale. `--output` désigne **seulement un rapport JSON agrégé** et non les souvenirs ni les octets BLOB. Il ne contacte pas Ollama, `mediad`, `tofd`, `robotd`, MuJoCo ou Internet.

1. Créer `ExperienceMemory` dans un dossier temporaire ; activer **WAL uniquement sur cette fixture** et désactiver son auto-checkpoint pour pouvoir mesurer le WAL avant fermeture.
2. Initialiser la sémantique F4-A et **M1-B strict** ; enregistrer les octets `db`, `-wal`, `-shm`, `page_size`, `page_count` et `freelist_count`.
3. Parcourir les **54** clés fermées F4-A, rétracter **53** hypothèses fictives avec `fixture_annotation_error`, garder **une** hypothèse active ; inscrire deux empreintes **synthétiques** M1-B (image 64 o, audio 16 o, groupes distincts).
4. Mesurer sans fermer le writer pour capter le WAL non checkpointé ; fermer/réouvrir via la **même classe** `ExperienceMemory`, vérifier `PRAGMA quick_check`, les 53 rétractions, l'hypothèse active et les 80 octets M1-B, sans table M1-A.
5. Avancer l'**horloge de fixture** de **5 × 14 jours** (pas l'horloge réelle), appeler `CategorySemantics.prune`, vérifier que **53 rétractions restent**, **1 active expire**, et que la même clé rétractée ne peut revenir ; vérifier zéro expérience non vérifiée ou mouvement.
6. Checkpoint `PRAGMA wal_checkpoint(TRUNCATE)` sur **cette base temporaire seulement**, mesurer à nouveau les tailles, fermer et vérifier la destruction du dossier temporaire.

Le profil n'instancie que les **8 tables pertinentes** (F0:4, F4-A:2, M1-B:2), contrairement au registre statique de 22 tables N3. Les tables F1/F2/EX/F5 et les écritures historiques sont exclues de cette mesure. La **durée de vie des 53 rétractions** est une politique C2 du prototype fermé, non une assurance d'oubli approprié d'un savoir réel.

## 4. Mesures réelles Linux CI et provenance de l'artefact

**Source :** workflow Python compagnon [#40749269400](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40749269400), artefact `n4-host-sqlite-wal-fixture` ID `12843466574`, SHA-256 de l'archive `2b74769018e0b8591258a6cf1c8e76372131a1ac31914e2175baf52d1e038a75` (**vérifiée sur les octets téléchargés**). Runtime : Linux, SQLite **3.45.1**, `page_size=4096`. Le JSON a été lu et ses invariants (total DB+WAL+SHM, 53 corrections, retrait d'une hypothèse active, nettoyage temporaire) contrôlés hors moteur.

| Étape de l'échantillon 8 tables | DB (octets) | WAL (octets) | SHM (octets) | Total transitoire |
| --- | ---: | ---: | ---: | ---: |
| Initialisation de F0/F4-A/M1-B et activation WAL | 32 768 | 57 712 | 32 768 | 123 248 |
| 54 propositions, 53 rétractions, 2 signatures synthétiques, **avant fermeture** | 32 768 | **1 013 552** | 32 768 | **1 079 088** |
| Réouverture, prune à 70 jours fictifs, corrections contrôlées | 86 016 | 12 392 | 32 768 | 131 176 |
| `wal_checkpoint(TRUNCATE)` sur la **fixture uniquement** | **86 016** | **0** | 32 768 | 118 784 |
| Dernière connexion fermée | **86 016** | Fichiers temporaires gérés par SQLite | — | DB persistante **86 016 octets** |

**Rétention mesurée :** avant fermeture : **53 marqueurs corrigés + 1 hypothèse active** ; après réouverture : idem ; après `5 × 14 jours` simulés et purge : **53 corrections + 0 active**. Une tentative d'insérer à nouveau la clé fictive rétractée a retourné `None`. **Deux signatures M1-B pour 80 octets de BLOBs**, deux groupes, aucune table M1-A et aucune ligne d'expérience/mouvement ; `PRAGMA quick_check = ok`. Dossier temporaire supprimé après exécution.

**Interprétation critique :** le pic WAL ~**990 Kio** provient notamment des nombreuses petites transactions et du **`wal_autocheckpoint=0` volontaire**. Il ne décrit pas la politique WAL de la version OEM ou l'écriture continue d'un service réel. En WAL actif, `page_count × page_size` peut décrire des pages logiques **déjà présentes dans le WAL** sans être toutes dans le fichier DB : ne pas assimiler `db_bytes` intermédiaires au volume total. Le fichier SHM, utilisé pour la coordination WAL, n'est pas une archive durable de souvenirs. L'écart **80 octets de BLOBs vs 86 016 octets DB** reflète surtout le schéma, les index, les pages SQLite et l'expérience synthétique, **pas le coût par souvenir à l'échelle**.

**Conclusion limitée :** N4 démontre des coûts hôte **sur 8 tables activées** et la conservation de corrections fictives, ni les **22 tables** disponibles dans le code entier ni les budgets flash/RAM/thermie/batterie du RK3566. Aucun réglage de `journal_mode`, `wal_autocheckpoint` ou `wal_checkpoint` n'est proposé sur le robot. Ces chiffres ne prouvent pas de mémoire autonome ni de généralisation Cat-A2b/C3.

## 5. Contrôles et décision de nettoyage

Les tests `tests/test_n4_sqlite_fixture_budget.py` valident la réouverture, l'oubli de l'actif, l'absence de résurrection des corrections, les 80 octets M1-B sans M1-A ni effet physique, le WAL tronqué sur la fixture et le refus d'argument `--database`. Les anciennes suites C2/R2-A/EX restent exécutées dans `python-tests.yml`. La CI publie le **JSON agrégé**, pas le fichier SQLite, le WAL, un BLOB, une image, un son ou un secret.

| Voie / statut après N3 | Choix N4 |
| --- | --- |
| `ExperienceMemory` (unique SQLite et gestion des transactions) | **Conserver** comme point d'entrée ; pas de deuxième base |
| `f4a_property_hypotheses` / rétractions C2 | **Conserver les corrections** ; pas de suppression ni migration silencieuse |
| M1-B strict `m1b_groups`/`m1b_signatures` | **Candidat R2 à conserver**, empreintes factuelles **non garanties**, pas de modèle moteur |
| M1-A `CompactPatternMemory` | **Laboratoire historique** ; seulement extracteurs purs partagés, pas d'écrivain M1-A dans une base R2 |
| `mock_cycles`, `f4a_mock_behavior_outcomes`, `ex1_mock_experiences`, `ex2_mock_effects`, `sim_motion_trials` | **Laboratoire / simulation**, pas de conséquence robot ni de causalité démontrée |
| `SelectivePCPolicy` / F5-C | **Conserver séparément** le consentement/quota PC, ne pas transformer l'analyse du 9B en fait mémorisé |
| `kwipi_journal`, vérificateur X2-C | **Lecteurs de diagnostic**, aucun écrivain cognitif |

**Sortie N4 :** publier les **octets hôte observés**, leur périmètre et les limites dans ce rapport après CI ; ne pas promettre un gain de stockage sur le robot et ne pas retirer de table en N4. L'étape suivante éventuelle N5 est une **sélection d'un paquet embarquable minimal**, conditionnée à une allowlist et une fermeture des imports sur le vrai wheel, puis au budget matériel OEM mesuré par `scripts/resource-audit.sh`.
