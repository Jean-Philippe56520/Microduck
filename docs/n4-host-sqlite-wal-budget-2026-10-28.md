# N4 — Taille SQLite/WAL sur fixtures et rétention après réouverture

**Date :** 28 octobre 2026. **Statut initial :** protocole et outil PC/CI candidat ; valeurs numériques à reporter depuis le **JSON du dernier workflow vert**. Aucune mesure sur le RK3566 ni aucun effacement de la SQLite personnelle de Kwipi. Autorité : [`plan-action.md`](plan-action.md). Suite de [N3 #131](https://github.com/Jean-Philippe56520/Microduck/pull/131) fusionnée au commit `241acde368d5abc5d456ebbe3d725656735934fa` ; les 22 tables relevées en N3 représentent **le code entier**, pas les tables actives du profil N4.

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

## 4. Contrôles et décision de nettoyage

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
