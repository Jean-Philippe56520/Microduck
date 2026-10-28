# MEM-1 — Objectifs fictifs persistants, sans duplication d'EX1

**Date :** 28 octobre 2026. **Portée :** première implémentation **PC/fixtures** de MEM-1, [PR #142](https://github.com/Jean-Philippe56520/Microduck/pull/142) fusionnée au commit `12dc426b` avec [CI post-fusion #40775879843](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40775879843) réussie ; aucun matériel, servomoteur, capteur, LLM, boucle autonome, retour d'effet réel ou stockage sur robot validés. Le [plan directeur](plan-action.md) est l'autorité, et le [plan objectifs/détermination/Qwen/observabilité](kwipi-goals-determination-memory-qwen-observability-plan-2026-10-28.md) reste la feuille d'intégration.

## 1. Porte d'entrée : observation → hypothèse → preuve → arrêt / repli

**Observation.** Au `main@f07f22f01df3d466a431971c482788ba7ae53d37`, l'unique `ExperienceMemory` crée déjà la SQLite utilisée par F1/F2/F4/C1/C2/M1/EX/F5-C. `MockExperienceLedger` EX1 y conserve **les intentions et leurs résolutions fictives**. `AutonomyBrain` F2 est l'arbitre unique, mais ni objectif durable ni détermination persistante ne sont intégrés. OBS-1 #141 a introduit un diagnostic sur EX1/EX2 seulement. Le scanner N3 établit le site d'ouverture écrivable existant ; N4 mesure SQLite/WAL **sur fixtures hôte**, non sur RK3566.

**OEM d'abord.** Gitlink OEM `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, simulation `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Les fichiers officiels `robotd/src/intents.rs`, `duck-ipc-proto/src/lib.rs`, `robotctl/src/monitor.rs`, `docs/design/robotd-design.md` et `robotd-params/src/lib.rs` conservent la propriété exclusive du moteur à `robotd`. `robot.do accepted` est un accusé de mise en file, **pas** un reçu de fin d'action. Les PR Pollen [#381](https://github.com/pollen-robotics/microduck/pull/381) (cerveau) et [#414](https://github.com/pollen-robotics/microduck/pull/414) (navigation) restent **ouvertes/non fusionnées** à cette revue. Le robot physique manque : versions réellement installées, politique active, ONNX, caméra et partition de données ne sont pas vérifiables sur l'appareil.

**Hypothèse technique.** Une petite fiche d'objectif persistante et des *références vers les épisodes EX1 existants* suffisent à rendre vérifiables les phases `candidate/active/suspended`, les conditions de reprise et les corrections, **sans créer de seconde mémoire des tentatives**.

**Preuves visées.** Tests de création/idempotence, transitions conditionnelles, redémarrage, lecture depuis second processus, lien strict avec EX1, relecture des sources rétractées ou supprimées par rétention, quotas, refus de données privées et faux accomplissement moteur ; scan statique N3 et CI complète.

**Échec bloquant.** Second `sqlite3.connect` écrivable, nouvelle base, duplication ou réécriture d'EX1, `completed_verified` abusif, réactivation de correction, réessai identique, création de moteur/agent, fuite de texte libre, statut de cause physique induit depuis `mock_executed`, CI rouge.

**Risque et retour arrière.** L'activation est *à la demande* sur un `ExperienceMemory` explicitement passé, pas un nouveau processus ni branchement F2. Les deux tables additionnelles sont préfixées `mem1_mock_` ; une réversion du module/PR laisse les données historiques intactes. Ne jamais exécuter `DROP` sur les souvenirs de l'utilisateur ou les tables F4/EX. La capacité atteinte est un refus explicite, non une purge de corrections.

## 2. Réutiliser / adapter / créer

| Responsabilité | Choix | Justification |
| --- | --- | --- |
| SQLite et transactions | **Réutiliser** `ExperienceMemory.conn` | **Une** base et **un** site d'ouverture écrivable, N3 comme garde |
| Tentatives | **Réutiliser** EX1 `ex1_mock_experiences` | Aucune copie de statut ou de résultat : `mem1_mock_goal_links.ex1_row_id` est une référence |
| Décisions | **Ne pas modifier** `AutonomyBrain` F2 ni `passive_rhythm` | MEM-1 stocke ; DET-1 devra tester l'influence sur F2 séparément |
| Provenance/causalité | **Réutiliser** EX4-A/B/C et OBS-1 | Aucune déduction de succès depuis acceptation OEM ou fixture |
| Rappel Qwen | **Pas de connexion** F5 v2/v3 | MEM-2 puis QW-1 seulement avec sélection et confidentialité |
| Nouveau code | **Créer** `mock_goal_memory.py`, **deux tables** et tests MEM-1 | Ce contrat d'objectifs n'existe pas dans les 22 tables recensées par N3 |
| Tiers | **Référencer** QuackNav/microduck-brain, Quacksat, Twin, GC/Smartulf, lab/studio ; ne rien importer | Leur navigation/architecture ne remplace pas le journal EX1 ou ne valide pas les gestes |

## 3. Contrat de persistance

**Tables dans la même SQLite :**
- `mem1_mock_goals` : identifiant opaque `g-` + 16 hex, type et catégorie d'objectif passif, état, condition de reprise, horodatages, révision optimiste, `active`, `correction_reason` et source `mock_fixture_only`.
- `mem1_mock_goal_links` : clé vers la fiche MEM-1, `ex1_row_id` vers la ligne EX1 existante, stratégie d'observation passive, contexte déclaré, date et source ; **pas de colonnes de copie** du résultat, de texte libre, d'image, d'identité, ni d'appel moteur.

**États fermés :** `candidate`, `active`, `suspended`, `mock_closed`, `abandoned`. Il n'existe **aucun** `completed_verified` en MEM-1. `mock_closed` signifie uniquement *dossier de fixture clos après un EX1 scripté encore actif*, jamais résultat physique prouvé. Reprise `suspended → active` uniquement lorsque le motif de transition correspond exactement à la condition consignée (`new_view`, `new_context`, `new_evidence` ou `operator_review`) ; ces motifs restent **déclaratifs**, sans preuve qu'une caméra a réellement vu quelque chose.

**Stratégies :** `observe_from_distance` et `observe_over_time` correspondent à l'intention fictive EX1 `observe` ; `inspect_other_view` et `compare_memory` à `inspect`. Aucune de ces chaînes n'autorise un mouvement des yeux ou des pattes. La paire `stratégie + contexte` n'est pas réutilisable sur un même objectif ; un contexte textuellement différent ne démontre **pas** une expérience véritablement nouvelle. EX1 doit être créé **après activation de l'objectif** et le lien doit respecter une fenêtre de laboratoire bornée. Un épisode EX1 ne peut appartenir qu'à un objectif dans ce prototype.

**Corrections :** les rétractions `fixture_annotation_error` et `source_retracted` produisent un marqueur durable (`active=0`) qui ne peut être recréé avec le même identifiant. Les références à des épisodes EX1 supprimés par leur propre rétention ou rétractés apparaissent comme `missing_ex1` / `retracted_or_untrusted_ex1` et `unavailable`, **pas comme succès ou échec moteur**. Aucun effacement silencieux des marqueurs ni transformation d'une hypothèse Qwen en fait.

## 4. Budget de prototype et preuves de ressources

Plafonds conservateurs **à tester sur hôte** : au plus **32 fiches d'objectifs**, **8 références EX1 par objectif** et **128 références au total**, marqueurs corrigés inclus dans les 32. Ces bornes ne sont **pas** une recommandation de rétention RK3566 ; un quota plein renvoie une erreur explicite. Les enregistrements EX1 conservent indépendamment leur prototype 14 jours/256 ; leur disparition ne rend pas un objectif « achevé ».

La CI vérifie les tests MEM-1 et la suite Python existante, le scanner N3 doit continuer à détecter **un seul site** d'ouverture écrivable ; le nombre de tables passe de 22 à 24 *si aucune autre déclaration n'a changé*. Mesurer taille SQLite + WAL et RSS/CPU sur vraies fixtures ensuite, puis sur appareil seulement avec `scripts/resource-audit.sh`, une fois disponible. Ne pas extrapoler les chiffres de N4 (WAL artificiel sans auto-checkpoint) à la flash robot.

## 5. Suite et limites

MEM-1 **n'arbitre aucune intention par lui-même** et ne se branche ni à l'humeur, au conseiller Qwen, ni à `robotctl`. **DET-1**, intégré séparément par [PR #143](https://github.com/Jean-Philippe56520/Microduck/pull/143), donne à F2 une consultation **optionnelle** des objectifs fictifs non encore tentés, sous toutes les protections F2 existantes. Cela ne démontre pas la reprise après un échec ou un mouvement réel. MEM-2/QW-1 fourniront ensuite un rappel local sélectionné et expurgé, seulement après contrat consentement/quotas. La vérification d'exécution/effet EX4-C2 et les gestes physiques restent bloqués tant que le robot et un signal OEM indépendant ne permettent pas de conclure.

**Exécuter en laboratoire (fixtures non privées uniquement) :** `python -m unittest discover -s tests -p test_mem1_mock_goal_memory.py -v` et `python -m scripts.n3_sqlite_audit --output /tmp/n3-mem1.json`, puis la CI de la PR. Pas de moteur, capteur ni modèle dans ces commandes.

Sources : [EX1](ex1-mock-experience-ledger-2026-10-26.md), [N3](n3-sqlite-writer-retention-audit-2026-10-28.md), [N4](n4-host-sqlite-wal-budget-2026-10-28.md), [plan EX](kwipi-experiential-learning-plan-2026-10-26.md), [registre communautaire C3](community-reference-registry-2026-10-26.md), [protocole de réutilisation](development-reuse-protocol.md).
