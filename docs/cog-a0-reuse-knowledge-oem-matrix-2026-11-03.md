# COG-A0 — Audit cognition locale, compétences OEM et lacunes

**03/11/2026 — lecture seule.** Autorité : [plan d'action](plan-action.md), section COG-BASE-0 de la [PR #285](https://github.com/Jean-Philippe56520/Microduck/pull/285). État d'entrée vérifié : Companion main 1042e8785105429ca4ee5524e8477d97282a130e, #285 corrigée au commit 0e88d91305871991190c0f75dfa4a755ff602943 (CI de ce commit encore à vérifier). Gitlinks épinglés inchangés : microduck 942e58e3aa6dbb28e7037203fff11866122c7567, microduck_rl b02fdea4902c2b93b7d34a83a6f05da4ececb7d3. Référence Yocto B11 : 1ee58387810cebb67ae0d634c351d95024483bce. L'OEM main d13be2c1a2f4b1e0b0e499b08b92f870518b1384 est différent du pin : aucune mise à jour ni équivalence présumée. PR constructeur #381/#414 ouvertes non fusionnées ; #450 fermée sans fusion ; Qwen Companion #97–99 fusionnées, #237 ouverte. Robot absent.

## Comparaison minimale des interfaces OEM épinglées et amont

**Vérification de sources, pas portage :** dans l'OEM épinglé, `duck-ipc-proto/src/lib.rs` définit **API_VERSION = 44** (blob f64c7e1b3a4b090f5a167d88e98974f303c7d97c) ; `main@d13be2c1` définit **API_VERSION = 47** (blob 6c9d2f31f7bf9c56950eda38c5421200b6583b79). Les notes de protocole v45 traitent de l'option de galerie Vetbook, v46 des opérations de mise à jour A/B, v47 des réglages de télémétrie anonyme. **Aucun de ces ajouts ne démontre un accusé de fin OEM par commande** : EX4-C2 reste bloqué pour la version épinglée. Les blobs `robotd/src/control.rs`, `mediad/src/detect.rs` et `pet-detect/src/worker.rs` examinés sont identiques entre pin et main ; `robotd/src/idle_head.rs` et la cheatsheet ont changé et leur équivalence complète n'a pas été établie. **Ne pas mettre à niveau les gitlinks ni mélanger v47 et v44 sans accord/audit ABI.**

**Reprise GitHub (03/11/2026) :** #285 fusionnée sur `main@7a34d9a22648c2710918043601a4c7a837e4fda3` avec 9/9 workflows réussis. Ce document conserve explicitement ses SHAs d'audit antérieurs ; ils ne sont pas des SHAs de production. #286 ne change ni code ni OEM.

## Objectif, hypothèse, risques et critère d'arrêt

**Question :** qu'est-ce que Kwipi pourra mieux choisir ou vérifier *sans Qwen ni PC* grâce à une connaissance générale sourcée, par rapport à F2, F4 et EX déjà codés ? Hypothèse à vérifier : une liaison entre propriétés/usages conditionnels d'objets, observations, intentions F2 et compétences OEM disponibles manque ; ni la motivation ni la SQLite ne sont absentes.

**Risque :** promotion d'une connaissance générique au rang d'observation, d'une empreinte au rang d'identité, d'un skill documenté au rang d'action disponible, ou d'un accusé OEM au rang d'effet. **STOP :** si une composante équivalente existe déjà, la réutiliser sans code ; si preuve de capteur ou d'effet manque, EN ATTENTE. Aucun matériel, modèle, SQLite, sous-module, service ou politique motrice modifié ; repli = aucun changement fonctionnel.

## Inventaire réutilisable réellement inspecté

| Domaine | Sources inspectées et exemples de tests | État constaté |
| --- | --- | --- |
| Intentions/motivations | autonomy.py, passive_intentions.py, passive_rhythm.py ; test_det1_goal_determination.py (20 cas) | AutonomyBrain, curiosité/sociabilité/jeu/énergie/prudence/détermination ; F2 propose observe/inspect/listen/idle/rest **uniquement en fixtures mock**, avec fraîcheur et temporisations. Ne commande aucun moteur. |
| Inspection active de categorie (a reutiliser) | category_inspection.py, tests/test_category_inspection.py | **Deja code/teste sur fixtures** : des indices partiels (main, patte, contour rond, pied de meuble...) proposent jusqu'a deux suites de recherche visuelle sous l'intention F2 `inspect unknown` **deja choisie**. Les classes candidates `chair`/`shoe` ne deviennent pas des classes F1 ni des objets identifies. Aucune capture, mouvement, SQLite, Qwen ni preuve de continuite visuelle reelle. **Ne pas recréer de second inspecteur pour A2.** |
| Source/observation | perception.py, passive_observations.py, passive_memory.py | Vocabulaire F1 ball, toy, person, cat, dog, microduck, other_object, unknown ; catégorie/TTL/conflits et journal uniquement mock_fixture_unix. Le libellé sensor n'authentifie pas mediad. |
| SQLite/semantique | episodic_memory.py, category_semantics.py, behavioral_memory.py, memory_recall.py ; test_category_semantics.py (23), test_mem2_memory_recall.py (11) | **Une ExperienceMemory.conn** : objets/épisodes/essais simulés, F1-C/F4-A, correction et retrait. F4-A connaît les champs texture/movement/affordance mais uniquement des hypothèses fictives, non une connaissance de référence générale approuvée. |
| Consolidation | memory_consolidation.py, experience_expectations.py ; test_memory_consolidation.py (11) | C1 et EX3 sont **en lecture seule**, avec jointures de provenance et corrections ; EX3 produit un biais d'attention mock, pas un écrivain de relations ni des liens causaux. |
| Ressemblance | compact_multimodal_memory.py, multiview_pattern_memory.py ; test_multiview_pattern_memory.py (20), test_r2a_memory_selection.py (9) | Signatures 64 octets image et 16 octets audio, candidats multivues, sélection M1-B sans double écriture ; pas de reconnaissance d'instance physique. |
| Expériences | experience_ledger.py, experience_effects.py, experience_expectations.py, ex4_evidence_audit.py, ex4b_oem_wire_audit.py, ex4c_mock_causal_preflight.py ; tests EX1/EX4-B | EX1–EX3 sont **mock** et non causaux ; EX4 vérifie des reçus fictifs. robot.do accepted = mise en file, jamais preuve de fin ou d'effet. |
| Personnalité | behavior_personality.py, behavior_continuity.py, oem_expression_hints.py ; tests behavior_personality et pd1_oem_expression_capabilities | 16 noms historiques, 4 descriptions fictives et 4 correspondances OEM **partielles** (Chill/LookAround/Nap/Petted) ; aucune série de 16 commandes M9 disponibles. |
| Qwen | qwen9b_production_role_v2.py, qwen9b_action_guard.py, PR #97–99 et #237 | Conseil PC facultatif. P1 rapporté deux abstentions unverified ; nouveaux essais suspendus, pas de rôle de pilote ni de writer. |

**Provenance d'essai :** méthodes et tests inspectés dans GitHub, **pas exécutés à nouveau par cet audit**. Résultats acquis et gelés : MEM-2B-WA 0/36 vues familières, MEM-2B-R 0/48, PER-P4L1 0/3 sur cibles basses, SIM-S1 sans gain d'attention. Aucune extrapolation au robot.

## Matrice capacité constructeur / connaissance / preuve / intention / effet

[OEM épinglé : cheatsheet](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md), robotd/src/main.rs (PolicyNames, robot.policies), robotd/src/control.rs (arbitrage skills/postures), robotd/src/idle_head.rs, mediad/src/detect.rs, pet-detect/src/worker.rs. **Présence dans les sources ≠ skill chargé sur notre robot**. Lorsque le robot sera présent : robotctl version, health, policy list et monitor en lecture seule, paramètres/poids/empreintes et journaux d'abord.

| Concept/situation hypothétique | Capacité OEM réellement documentée | Observation et intention disponibles aujourd'hui | Effet et manque exact |
| --- | --- | --- | --- |
| Objet inconnu : inspecter ses propriétés | mediad, robot.look, idle_head (pas de suivi visuel) | F1/F2 inspect/observe/idle **mock** ; pas de perception physique validée | Nouvelle vue indépendante non prouvée, aucune permission de mouvement |
| Balle : peut rouler selon sol/contexte | kick_left/kick_right, **si skills présents/chargés** | Label ball fictif, personnalité joueuse descriptive ; aucun kick F2 autorisé | Contact, trajectoire et mouvement indépendant de balle **non vérifiés** |
| Tissu/objet au sol : certains objets se laissent saisir | ground_pick OEM, sans preuve de transport | Pas de classe cloth F1 ni forme/matériau/localisation fiables ; inspect/idle | Préhension/transport/pose non attestés |
| Chaise : peut supporter un humain | sit_toggle concerne la posture **du robot**, pas sa montée sur une chaise | Chaise hors vocabulaire F1 ; ni cible ni sol sûr | Aucune compétence de « s'asseoir sur chaise » exposée |
| Humain / photo / écran | robot.look et sons conditionnels, pas un jeu autonome | Pas de source réelle prouvant présence, participation ou consentement | Ne jamais assimiler photo/TV à une personne présente |
| Chat/chien | pet-detect reconnaît **caresse du robot**, pas présence d'animal ; coo conditionnel robotd | Cat/dog F1 fixtures, absence de détection réelle fiable | Pas de contact/trajectoire vers vivant sur simple catégorie ; pas d'interdit global vivant/kick |
| Bruit / voix | Micro partagé, SoundEvent Noise/Voice heuristiques | F2 listen fictif ; pas d'ASR « Hé Kwipi », « stop » validé | Compréhension vocale et effet **inconnus** |
| Repos / regard / posture | sit_toggle, idle_head, stand, sons | Repos/idle F2, énergie **motivation simulée** | Batterie, compétence active, effet réel de repos inconnus |
| Exploration / marche | walk, robot.move, safety et deadman robotd, ToF frontal | Prototype explore, pas de navigation sûre ; SIM-E2 non résolu | Déplacement net et sécurité terrain non prouvés |
| Action et conséquence | robot.do, robot.state, robot.policies | EX4-A/B/C1 vérifient seulement des formes de trames | **EX4-C2** attend fin authentifiée par action et effet indépendant avant apprentissage causal |

## Écarts prouvés et décision réutiliser / adapter / créer

**G1 (P0, A1) — Absence de savoir général local versionné dans le choix.** F4-A stocke des hypothèses *mock* et non des relations générales sources/propriétés/usages/conditions. **Adapter** avec un très petit référentiel révisé, **seulement si la comparaison A1 démontre un gain**. Pas de souvenirs vécus fictifs, pas de SQLite de référence séparée.

**G2 (P0, A2) — Composition conditionnelle non établie.** L'inspecteur existant `category_inspection.suggest_category_inspection` fournit deja des suites d'indices en MOCK sous une decision F2 ; **le manque ne porte pas sur la production d'un deuxieme indice visuel**. F2 sait déjà proposer l'attention et s'abstenir, PD1 lit un catalogue statique ; aucune liaison vérifiée entre contexte frais, usage candidat et présence réelle du skill OEM. **Réutiliser/adapter F2 et les guards existants**, non créer un moteur d'actions ou de permissions.

**G3 (P0, bloqué par données/matériel) — Perception réelle insuffisante.** Les résultats visuels bas et multivues ne justifient pas la reconnaissance d'un objet précis ; RKNN multiclasses 2 Hz, source authentifiée et budgets robot restent **EN ATTENTE**.

**G4 (P0, bloqué OEM/robot) — Exécution et effet.** API OEM épinglée : ack admis ≠ fin, robot.state ne fournit pas un reçu final corrélé par action ; aucune mémoire motrice causale avant EX4-C2. **Réutiliser EX4**, ne pas inventer récompense, fin ni écrivain.

**G5 (P1, A3) — Consolidation physique non acquise.** C1/EX3 et mono-écrivain existent ; l'intégration à des épisodes réels corrigibles demandera provenance, effet et ressources mesurées. **Ne pas développer par anticipation.**

**G6 (P2, Qwen) — Bénéfice non démontré.** P1 avec deux abstentions, aucun besoin justifiant de nouveaux essais, ni de génération autonome de code. **Suspendre**.

## COG-A1 — socle initial candidat à relire, pas de faits vécus

Propositions **conditionnelles** et génériques, non des observations ni des capacités activées :

| Concept | Relation / usage possible | Conditions et contre-exemple | Lien OEM non autorisant |
| --- | --- | --- | --- |
| ball | Peut rouler, parfois servir à jouer | Surface, taille, cible et contact incertains ; écran/absent/vivant proche ≠ permission | kick_left/right **si réellement chargés** |
| toy | Certains jouets permettent le jeu | Ne rien supposer de leur innocuité ou solidité | Aucun automatiquement |
| cloth (future classe) | Certains tissus sont déformables ou saisissables | Cloth n'est pas une catégorie F1 ; taille/prise inconnues | ground_pick ≠ transport |
| chair (future classe) | Peut être utilisée pour l'assise humaine | Chair n'est pas une catégorie F1 ; jamais associer sit_toggle | Aucun |
| person | Peut participer volontairement à l'interaction | Photo/TV, personne non participante, cible imprécise | Regard/son seulement selon API et contexte |
| unknown | Caractéristiques/usage inconnus : observer ou attendre | Similarité ou LLM n'établissent pas l'identité | Aucun |

**Structure minimale envisagée, NON CODÉE :** références en lecture seule versionnées, champs concept, type de relation (property/use/condition), énoncé conditionnel, source/date/licence/relecture, statut general_reference/candidate/withdrawn, contre-exemples, skill OEM seulement comme **nom de référence**. Séparer strictement (1) connaissances générales révisables, (2) hypothèses F4-A, (3) observations authentifiées, (4) fin OEM et (5) effets mesurés. Aucune nouvelle SQLite, entraînement à partir de milliers d'épisodes inventés, personnalité pilotant la sûreté ou export de médias privés. Pas d'extension factice des catégories F1 pour satisfaire le tableau.

## Tests positifs/négatifs pré-enregistrés avant tout code A1/A2

**Témoin apparié :** mêmes fixtures indépendantes et même état initial de la seule ExperienceMemory, F2 actuel sans nouvelles références vs F2 avec références. Qwen/PC absents des deux bras ; aucune requête réelle robotd/mediad, aucune reprise des cohortes précédentes.

- **4 positifs prévus :** P1 balle fixture + usage conditionnel → intention **non motrice** pertinente ; P2 second contexte inconnu → proposer d'observer une autre propriété plutôt que certifier ; P3 savoir rétracté/corrigé → choix révisé hors PC ; P4 motivation+objectif réutilisant une relation générale dans un contexte inédit sans répétition arbitraire.
- **8 négatifs prévus :** N1 humain seulement à l'écran ; N2 cible vivante sur trajectoire/contact non sûr ; N3 capteur absent/périmé/non authentifié ; N4 classe future chair/cloth absente de F1 ; N5 skill OEM non chargé/désactivé ; N6 savoir retiré/contradictoire ; N7 signature similaire non identitaire ; N8 robot.do accepted sans fin ni effet.
- **PASS préfixé, non atteint :** 4/4 positifs produisent une différence utile et expliquée vs témoin, 8/8 négatifs restent prudents, 0 ordre moteur, 0 nouvelle affirmation de fait/effet physique, 0 appel Qwen, 0 nouvelle DB/double écriture, corrections et source préservées ; coûts CPU/RSS/latence bornés lors des futurs essais.
- **STOP :** absence de gain mesurable sur l'attention vs F2 seul ; faux fait, faux accès à une compétence, réactivation d'un retrait, répétition risquée, taux mesurés sur jeu déjà optimisé ou budget de ressources non maîtrisé. Données indépendantes indisponibles = **EN ATTENTE**, jamais score inventé.

**Décision A0 :** audit et matrice suffisants pour cadrer un *petit essai A1* ; **aucun code A1, comportement combiné A2 ou apprentissage réel livré par cette note**. Fusion documentaire = décision de pilotage, pas autonomie. Revue des preuves avant toute future PR fonctionnelle.

Sources complémentaires : [protocole de réutilisation](development-reuse-protocol.md), [OEM audit](oem-reuse-audit-2026-10-26.md), [PD1](pd1-oem-expression-capabilities-2026-10-27.md), [EX](kwipi-experiential-learning-plan-2026-10-26.md), [perception](perception-oem-rknn-2hz-plan-2026-10-29.md), [C3](community-reference-registry-2026-10-26.md), [matériel](hardware-feasibility-audit-2026-10-25.md), [README](../README.md).
