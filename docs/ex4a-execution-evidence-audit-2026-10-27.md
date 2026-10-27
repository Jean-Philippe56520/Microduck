# EX4-A — Audit de provenance des conséquences, sans fausse preuve motrice

**27 octobre 2026 — [PR #88](https://github.com/Jean-Philippe56520/Microduck/pull/88), [issue #80](https://github.com/Jean-Philippe56520/Microduck/issues/80).** Cette tranche est un **audit hôte en lecture seule**. Elle ne livre **ni la mémoire de conséquences physiques vérifiées, ni une cause certifiée** : aucun robot Microduck n'est disponible. Cat-A2b [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78) reste prioritaire pour la perception, bloqué par l'absence de vraies prises basses privées.

## Réutiliser / adapter / créer — audit préalable

| Source vérifiée | Choix pour EX4-A | Limite |
| --- | --- | --- |
| OEM épinglé microduck **942e58e3**, microduck_rl **b02fdea4** ; robotd seul maître des moteurs | **Réutiliser comme référence** ; aucun changement OEM, politique, pilote, démon ou commande | Aucune attestation authentifiée du robot physique fournie à Companion |
| [PR OEM #381](https://github.com/pollen-robotics/microduck/pull/381) cerveau et [#414](https://github.com/pollen-robotics/microduck/pull/414) carte | **Veille** ; ouvertes et non fusionnées au 27/10 | M9 et mapd ne sont pas des APIs livrées dans la version épinglée |
| ExperienceMemory.conn, tables experiences et intent_preferences, fermeture du feedback historique X1 | **Réutiliser la même SQLite**, en lecture seule | Les lignes historiques record_action ne contiennent pas de reçu |
| EX1, EX2, EX3 | **Relire et recroiser** sessions, événements, corrections et analyse des indices EX2 | « mock_executed » et « temporal_only » ne sont ni une action physique ni une cause |
| P2a et F4-A | **Relire** retour fictif et rétractation F4-A sans autre écriture | Préférences mock ≠ préférences apprises sur robot |
| sim_motion_trials et sim_passive_cycles P2b/X2-C | **Relire** états simulés, cohérence, attestation et refus | Une pose MuJoCo ou une télémétrie cohérente ≠ mouvement réel |
| Registre C3 (QuackNav/Brain, Quacksat, Twin, GC, Smartulf, Lab, Studio) | **Référence**, aucun import de code, poids ni licence | Aucun tiers ne certifie ici une conséquence physique de Kwipi |
| Développement ciblé | **Créer** le filtre ex4_evidence_audit.py et ses tests de refus | Aucun nouvel écrivain, table, modèle, processus ni commande motrice |

**Nomenclature :** le plan ancien EX0 nomme « EX4 » la recherche Qwen/affordances. L'issue actuelle #80 utilise « EX4 » pour la provenance d'exécution. Ici, **EX4-A désigne uniquement le premier sous-lot de l'issue #80**. Qwen reste un chantier séparé sans droit d'établir un fait.

## Interface et classification des cinq sources

ExecutionEvidenceAudit(memory) exige une **instance de l'ExperienceMemory déjà ouverte** et ne fait que des SELECT ciblés. Elle ne recrée ni EX1, ni EX2, ni P2a, ni F4-A. Absence de table/ligne : verdict « missing » ; identifiant invalide : ValueError.

| Méthode | Verdicts représentatifs | Information non obtenue |
| --- | --- | --- |
| review_ex1(session, sequence) | proposed, refused, interrupted, mock_resolution_only, mock_temporal_only, mock_confounded, mock_unchanged, mock_indeterminate, withdrawn, withdrawn_effect, invalid_provenance | Autorisation et exécution robotd ; causalité |
| review_p2a(session, sequence) | mock_feedback_only, withdrawn_mock_followup, no_verified_execution, invalid_provenance | Apprentissage vécu sur Kwipi |
| review_sim_motion(trial_id) | simulated_effect_only, simulated_inconclusive, invalid_provenance | Exécution ou déplacement du robot physique |
| review_sim_passive(session, sequence) | no_action_executed, invalid_provenance | Acte moteur à partir d'une télémétrie seule |
| review_legacy_action(action_id) | legacy_unverifiable | Authentification impossible depuis les anciennes lignes experiences |

Les données EX2 sont revalidées avec la comparaison _assess existante et sa chronologie, les résultats de sim_motion_trials avec le calcul simulateur existant et les corrections EX1/EX2/F4-A sont relues à chaque requête. Aucune réécriture des souvenirs, aucun score reconstitué en cache, aucune récompense appliquée.

**Invariants pour tous les résultats :** authorized = not_attested, verified_on_robot = false, causality_established = false, physical_learning_allowed = false. Les états « scripted_mock_only » et « simulator_only » décrivent des provenances, **jamais** une confirmation matérielle. Une déclaration JSON, un simple paquet prétendant venir de robotd, un épisode MuJoCo ou une hypothèse Qwen ne peut pas être promu en preuve.

## Tests et critères de refus

Test cible : tests/test_ex4_evidence_audit.py. Reproduction locale sur un checkout du projet :

    python -m unittest discover -s tests -p 'test_ex4_evidence_audit.py' -v
    python -m unittest discover -s tests -v
    python -m compileall -q microduck_companion tests

Les tests examinent : intention proposée/refusée/interrompue ; résolution fictive seule ; changement temporel sans causalité ; événement concurrent ; scène différente ; scène inchangée ; retrait EX1/EX2/F4-A ; reprise de la même SQLite ; donnée altérée ou non numérique ; objet inconnu ; récompense de simulation séparée de la robotique ; absence de modification SQL, d'autorisation et de commande motrice. La CI GitHub sur fixtures prouve uniquement le logiciel, **pas** les résultats vécus ni l'authenticité d'un démon.

**Limites :** aucune nouvelle campagne MuJoCo dédiée à EX4-A ; les expériences X2-C demeurent des lectures passives en simulation. Aucune validation sur un RK3566, capteur, NPU, mécanique, caméra basse, enfant ou animal réel.

## Mémoire, coût et confidentialité

**Zéro nouveau schéma SQL, seconde base, autre écrivain, fichier image, audio, export automatique ni démon.** Le filtrage se fait à la demande, avec une lecture par clé ; il n'ajoute aucune purge aux historiques existants, ni ne répare leurs éventuelles rétentions non bornées. Les corrections sont représentées par les marqueurs actifs/retirés des tables sources, pas par suppression automatique.

Les chiffres hôte X2-C (40 960 octets SQLite pour six cycles et RSS Python ~18,5 Mio) ne mesurent **ni la surcharge EX4-A, ni la RAM libre 1 Go, ni le coût sur le robot**. Avant tout portage : exécuter scripts/resource-audit.sh sur le vrai matériel et vérifier RAM/CPU/stockage/WAL, température, sécurité et timings robotd 50 Hz.

Aucune donnée privée ou identité, son, image, secret, appel réseau ou Qwen ne figure dans EX4-A. Aucun pilote, flux capteur, actionneur ou système de sécurité n'est modifié.

## Suite conditionnelle, sans promesse de preuve anticipée

**EX4-B :** inventorier sur l'OEM effectivement épinglé les vraies interfaces de commande, autorisation, fin d'action et mécanismes de refus. Définir une chaîne typée, idempotente, horodatée et corrigible avant tout droit de mutation. Ni une PR ouverte ni une métadonnée de simulation ne l'authentifie.

**EX4-C :** après réception du robot et tests de sécurité graduels, qualifier des mesures indépendantes avant/après, l'absence d'événements concurrents, l'incertitude, les corrections et l'unicité de l'écrivain SQLite/M1-B. Seulement un résultat réellement attribuable peut **candidater** à une adaptation lente, sans jamais contourner robotd.

**Critère de sortie EX4-A :** empêcher la promotion d'une source fictive ou simulée en preuve d'une conséquence physique. **La mémoire causale vécue reste à développer et à valider.**
