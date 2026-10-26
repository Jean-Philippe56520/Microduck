# Microduck Companion

**R2-B+1 (audio indépendant) — adaptation du banc hôte, sans preuve de reconnaissance réelle :** [rapport et protocole](docs/r2b1-independent-audio-2026-10-26.md), [PR #59](https://github.com/Jean-Philippe56520/Microduck/pull/59). Le préparateur local sélectionne 6 machines ToyADMOS IND (10 prises originales), contrôle droits/format/SHA/source et réutilise M1-B avec rejet des inconnus et diagnostics anonymes. **Les archives réelles n'ont pas été téléchargées ni évaluées : pas de taux de reconnaissance audio mesuré.** CI sur WAV purement synthétiques ; aucun service OEM, modèle, SQLite ou moteur modifié. **Ne pas démarrer R2-B+2 avant le prochain accord explicite.**

**C1–C3 — références comparées chantier par chantier (sans intégration) :** [audit de six projets publics](docs/community-reuse-audit-2026-10-26.md) et [registre de sélection actuel](docs/community-reference-registry-2026-10-26.md), étendu aux projets de voix, simulation et interface. Pour la cartographie, vérifier **d'abord la PR OEM #414 maploc v2/mapd** (ouverte, non livrée), puis QuackNav et microduck-brain ; pour l'autonomie, surveiller **la PR OEM #381** (proposition de design, non portée). Les références ne sont **pas des dépendances validées**. Aucun code extérieur n'est intégré ; R2-B+1 et l'autorité motrice de `robotd` restent inchangés.

**Prochaines étapes (plan seulement) :** [plan d'exécution après R2-B](docs/r2-follow-up-execution-plan-2026-10-26.md). D'abord **des sons réellement réenregistrés**, puis **davantage d'objets visuellement ressemblants**, ensuite analyse des confusions et démonstration de la **mémoire unique M1-B sur PC**. Chaque lot réutilise l'existant et se clôt sur des tests et un bilan avant le suivant. Aucun modèle ni comportement robot supplémentaire n'est livré par cette planification.

**R2-B — premier benchmark sur vraies vues multi-angles effectué :** [rapport et mesures ABO](docs/r2b-independent-capture-evaluation-2026-10-26.md), [CI réelle #40322898625](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40322898625). Sur 72 photographies originales de **12 séquences** de produits (ABO CC BY 4.0), avec seuil appris exclusivement sur validation, le test de **4 séquences connues** (16 vues) donne **10/16** reconnaissances M1-B (64 octets) contre **15/16** MobileNetV2 (scores ImageNet, **pas embedding d'instance**) ; **8/8 vues de séquences non inscrites rejetées** dans les deux cas. Cohortes **très réduites**, vues corrélées d'une même session tournante, sans preuve d'identité physique entre séquences ni résultats acoustiques indépendants. Le bench réutilise M1-A/M1-B2, ne crée aucune nouvelle mémoire, et ne branche ni robot, Qwen, moteurs ni capteurs. RAM/CPU publiés **hôte uniquement**.


**R2-A — mémoire unique pour les prochaines expériences, sans déploiement :** [choix et limites documentés](docs/r2a-single-memory-selection-2026-10-26.md). Le **module M1-B existant** dispose d'une option explicite `r2a_single_writer=True` : elle refuse les anciennes lignes M1-A, les schémas partiels et une réouverture susceptible de supprimer des exemplaires ; ses transactions revérifient la sélection. M1-A reste une baseline via ses extracteurs **purs**, sans double persistance dans le chemin R2-A. **Ce garde-fou n'empêche pas globalement un ancien programme d'écrire dans M1-A** : une telle écriture provoque le refus de l'opération R2-A suivante. Aucun troisième stockage, modèle, Qwen, moteur ou capteur réel.


**M1-B2 — pilote CPU hôte réussi en CI, sans déploiement :** 934 tests Python réussis sur la branche et [banc comparatif CC0 ONNX](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40309136430) exécuté. Sur six photos de TEST, MobileNetV2 retrouve 6/6 rotations et recadrages dérivés du même fichier (contre 0/6 M1-B), mais rapproche aussi 1/15 paires de fichiers différents ; YAMNet retrouve 2/2 décalages mais 0/2 sons avec bruit numérique. **Aucune identification de même objet sur de vrais angles naturels, ni reconnaissance audio robuste démontrée.** [Rapport M1-B2](docs/m1b2-host-embeddings-2026-10-26.md). Aucun poids, média, PC connecté au robot, ni intégration SQLite/OEM.

Projet de robot autonome, curieux, explorateur et social.

**Audit rétroactif R1.5 (avant R2) :** [verdict sur les développements précédents](docs/r15-retrospective-reuse-audit-2026-10-26.md). La plupart des modules ont une utilité de **prototype/tests**, mais leurs variantes ne doivent pas toutes être embarquées : R2 doit utiliser **une seule mémoire active** (M1-B candidate, M1-A témoin sans double écriture), garder F1/F2/F5 existants et exclure les diagnostics moteurs du robot. Revue statique et tests de cohérence, aucune modification moteur, ni modèle sélectionné ou validation RK3566.

**Méthode permanente : réutiliser avant de créer.** [Protocole de développement](docs/development-reuse-protocol.md), [consignes pour agents](AGENTS.md) et [checklist de PR](.github/pull_request_template.md) imposent l'inspection du constructeur épinglé et de nos modules avant tout nouveau code, avec justification vérifiable en cas de lacune. **R1**, [contrat de perception passive sur fixtures](docs/r1-oem-passive-fixture-contract-2026-10-26.md), réutilise les parseurs F3-C/F3-E et `sim_ipc` au lieu de créer d'autres lecteurs de caméra, audio ou ToF. Aucune caméra, aucun micro, aucun capteur physique, aucun mouvement, Qwen ou mémoire réelle n'est raccordé.


**Audit de réutilisation OEM — 26 octobre 2026 :** la [revue du cerveau officiel et des fonctions existantes](docs/oem-reuse-audit-2026-10-26.md) distingue les fonctions réellement codées (moteurs/sécurité `robotd`, animation `IdleHead`, capture `mediad`, ToF et signaux sonores) du **futur cerveau autonome M9, non encore porté**. `AutonomyBrain` reste un **banc cognitif sans moteurs** et ne doit pas doubler l'arbitrage OEM ; l'apport Companion à conserver est la mémoire locale, les reconnaissances mesurées et les hypothèses PC facultatives. [Inventaire vérifiable](docs/oem-reuse-inventory-2026-10-26.json) et tests hors ligne, aucun capteur physique branché.

**Objectif :** développer un cerveau comportemental qui observe, conserve une mémoire locale, apprend des conséquences de ses actions et interroge facultativement un modèle Qwen sur un PC du réseau local. Le dialogue est secondaire.

## Les deux sources officielles

- [Pollen Robotics / microduck](https://github.com/pollen-robotics/microduck) : contrôle du robot, capteurs, sécurité et interfaces.
- [Pollen Robotics / microduck_rl](https://github.com/pollen-robotics/microduck_rl) : simulation MuJoCo et entraînement des politiques motrices.

Ces deux sources sont intégrées comme **sous-modules Git**, épinglés sur des révisions précises pour préserver la reproductibilité.

```bash
git clone --recurse-submodules https://github.com/Jean-Philippe56520/Microduck.git
cd Microduck
python -m unittest discover -s tests -v
python -m microduck_companion.autonomy_demo
```

Sur Windows, le prototype Python peut être exécuté normalement. La simulation officielle s'exécute sur Linux ou WSL2 correctement configuré ; son démarrage headless a déjà été validé sur Ubuntu dans GitHub Actions.

## Architecture cible

1. **Embarqué (Microduck)** : sécurité, mouvements, motivations, choix d'activités simples et mémoire essentielle.
2. **PC local (facultatif)** : Qwen pour interpréter des images, suggérer des hypothèses et analyser les nouveautés.
3. **GitHub** : conserver le code et les versions ; GitHub n'exécute pas l'IA.

Le module `microduck_companion` est actuellement un **prototype autonome testé avec les services officiels simulés**, y compris une impulsion `robot.move` suivie de `robot.stop`. Il n'est pas un contrôleur moteur ni une solution de navigation autonome validée. Aucune action ne doit être envoyée au robot réel sans un adaptateur validé et ses protections.

## Confidentialité et sécurité

Le dépôt ne doit contenir ni souvenirs personnels, ni enregistrements audio/vidéo, ni clés d'API, ni données privées. Les bases SQLite locales sont ignorées par Git. Le dépôt est actuellement privé. Les données personnelles doivent rester hors du dépôt, même privé.

## Plan de développement

**Chantier M1 :** M1-A a démontré une déduplication sur données synthétiques ; **M1-B** corrige le quota global, regroupe plusieurs variantes et évalue un très petit jeu public CC0. L'objectif de modèles d'empreintes plus invariants reste ouvert ; M1-C étudiera le PC sous consentement strict et contraintes matérielles.

Le **[plan directeur par phases](docs/plan-action.md)** est la **référence unique pour les priorités, critères de sortie et trois prochaines PR**. Il distingue F0–F8 et le chantier indépendant L (locomotion). La [roadmap](docs/roadmap.md) conserve l'historique des six phases initiales et des jalons P0a–P0j ; le [précédent plan P0–P8](docs/plan-action-historique-2026-10-25.md) est archivé sans supprimer les preuves. Le [plan MuJoCo](docs/mujoco-integration-plan.md) décrit les protocoles J1b–J2e ; l'[audit matériel](docs/hardware-feasibility-audit-2026-10-25.md) conserve les limites vérifiées.

**F1 — perceptions passives et mémoire sur données fictives : terminée en logiciel.** Les [PR #24–27](https://github.com/Jean-Philippe56520/Microduck/pull/27) ont mis en place un lecteur de faux événements Unix, la validation des catégories, une SQLite persistante et un scénario de **10 cycles** sur deux processus : **8 observations journalisées**, **2 déconnexions**, **10 décisions de sécurité `halt`**, **aucune commande motrice**. [Rapport F1-D](docs/f1d-integrated-passive-demo-2026-10-25.md). **Aucun capteur constructeur ni détecteur d'animal/personne réel n'est raccordé.**

**F2 — autonomie cognitive immobile : F2-A/B/C/D fusionnées et testées en logiciel fictif.** F2-A ([PR #28 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/28), [378 tests Python sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40237211717)) propose `observe`, `inspect`, `listen`, `idle` ou `rest` à partir des catégories fictives et de la SQLite, sans les exécuter. **F2-B est fusionnée dans `main` et testée via [PR #29](https://github.com/Jean-Philippe56520/Microduck/pull/29)** : [409 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40239148712), dont **31 nouveaux**. `AutonomyBrain.propose_balanced_passive()` ajoute un arbitrage utilisant les **cinq motivations**, un **cooldown de 3 s par catégorie**, une cadence minimale de **0,5 s**, le choix `idle` et un repos à hystérésis (`energy` fictive ≤0,22 jusqu'à ≥0,34). L'état de rythme est **en RAM**, le journal SQLite et les voies F2-A/`robotd` demeurent séparés ; les métriques comptent des propositions, non des actions réalisées. **Aucun moteur, caméra/microphone réel, Qwen, récompense ou mesure de batterie physique.** [Rapport F2-B](docs/f2b-motivations-cooldowns-2026-10-25.md), [plan directeur](docs/plan-action.md). **F2-C [fusionnée dans `main` via PR #30](https://github.com/Jean-Philippe56520/Microduck/pull/30) ([425 tests Python validés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240204045)) :** nouveau `PassiveLearning` sur la SQLite F1-C, classement de nouveautés/répétitions **fictives**, corrections réversibles et petits biais d'attention (`observe` / `listen`), opt-in uniquement. Ce ne sont ni des conséquences d'actions exécutées, ni un entraînement de modèle ; les expériences MuJoCo restent séparées. [Rapport F2-C](docs/f2c-reversible-mock-learning-2026-10-25.md). La locomotion P0/P1 reste suspendue.

**F2-D [fusionnée dans `main` via PR #31](https://github.com/Jean-Philippe56520/Microduck/pull/31) :** `PassiveCycleSupervisor` impose des quotas de cycles/événements et vérifie les pertes de source, le redémarrage SQLite et les budgets temporels **souples**. [450 tests Python réussis, dont 25 nouveaux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240749032), avec **deux processus Unix fictifs** et mesures hôte de latence p50/p95, CPU et pic RSS. Les chiffres de GitHub Actions **ne mesurent pas** le Microduck RK3566 ; les propositions ne sont jamais exécutées. [Rapport F2-D](docs/f2d-passive-resilience-2026-10-25.md). **F3-A [fusionnée dans `main` via PR #32](https://github.com/Jean-Philippe56520/Microduck/pull/32) :** `visual_dataset.py` définit un manifeste de catégories strictement borné (chien, chat, personne, objets, `unknown`), partition `train/validation/test` sans fuite de groupe ni doublon exact, déclaration de droits, et un évaluateur de **prédictions fictives uniquement**. [482 tests Python réussis sur la branche (32 nouveaux F3-A)](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40241592517), démonstration de **28 exemples de métadonnées imaginaires sans image** et aucune caméra/microphone réelle. [Rapport F3-A](docs/f3a-visual-dataset-protocol-2026-10-25.md). **F3-B [fusionnée dans `main` via PR #33](https://github.com/Jean-Philippe56520/Microduck/pull/33) :** première comparaison **sur des pixels de 20 photographies publiques déclarées CC0** (8 train, 6 validation, 6 test), sans images ajoutées à GitHub. Le petit kNN artisanal refuse presque tout (2/6 corrects grâce aux deux `unknown` seulement). Un MobileNetV2 ONNX ImageNet sous licence Apache-2.0, sans réentraînement, obtient **5/6 sur le test** (2 chats, 1 chien et 2 `unknown`; 1 chien rejeté). Ce résultat sur **six photos** ne prouve aucune précision utilisable en situation réelle. [Banc CPU GitHub Actions](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40242876466), [rapport avec sources CC0 et limites](docs/f3b-real-cc0-photo-baseline-2026-10-25.md). **Aucune caméra Microduck, NPU, détection avec boîtes, identité individuelle ou mouvement n'a été validé.** F3-C est [fusionnée via PR #34](https://github.com/Jean-Philippe56520/Microduck/pull/34) : **contrat OEM seulement sur données fictives**, pas une connexion `mediad` réelle.

**M1-B [fusionnée via PR #50](https://github.com/Jean-Philippe56520/Microduck/pull/50), mémoires multi-vues expérimentales :** correction de M1-A (les **256 signatures image et audio réunies**, jamais 257). Nouveau `MultiviewPatternMemory` : **groupes de souvenirs avec jusqu'à 6 variantes de fixture**, limites configurables **1 024 groupes, 4 096 signatures, 256 Kio de BLOBs**, quotas de comparaison et éviction/rétention. Ces budgets ne limitent **pas** la taille totale SQLite et ne sont pas mesurés sur RK3566. [CI hôte : 925 tests Python et 4 Rust réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40303522130) ; 512 motifs synthétiques traités et agrégés. [Évaluation facultative sur 6 photographies + 2 sons CC0](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40302657292) : **6/6** photos rapprochées après changement de luminosité, mais **0/6 après rotation de 12° et 0/6 après recadrage** ; son, **2/2** après changement de volume mais **1/2** après 16 ms de décalage. **La limite réelle est la robustesse des signatures, pas seulement leur nombre.** Aucune reconnaissance du même animal/objet sous vues naturelles ni capture réelle. [Rapport M1-B](docs/m1b-multiview-memory-2026-10-26.md).

**M1-A [fusionnée via PR #49](https://github.com/Jean-Philippe56520/Microduck/pull/49), première mémoire multimodale compacte :** `compact_multimodal_memory.py` extrait **de véritables caractéristiques** sur des pixels gris 32 × 32 et de l'audio PCM16 **synthétiques**, puis rapproche les empreintes et regroupe les rencontres dans la **SQLite existante** : **64 octets image + 16 octets son**, 256 empreintes actives maximum, 180 jours de rétention. Un nouveau motif intéressant peut produire une **suggestion de revue PC sans le contacter** ; une rencontre répétée incrémente son compteur sans sauvegarder de photos ou sons bruts. Refus des empreintes étiquetées `person` et `speech` dans les fixtures. [CI initiale : 898 tests Python et 4 tests Rust réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40297726482) ; deux processus démontrent **2 motifs et 10 rencontres par motif**, 80 octets de *seules empreintes*. **Ce n'est pas un modèle de reconnaissance d'objets/animaux ou de voix, et aucun capteur/PC réel n'est raccordé.** [Rapport M1-A](docs/m1a-compact-multimodal-memory-2026-10-26.md).

**F6-D [fusionnée via PR #48](https://github.com/Jean-Philippe56520/Microduck/pull/48), audit matériel préparé, non effectué :** `scripts/resource-audit.sh` possède un `--plan` **sans collecte**, et deux relevés **stationnaires sous accès développeur autorisé** (`--phase idle` ou `--phase vision` après revue du repos). La phase **mouvement est toujours refusée**, même avec tous les drapeaux. Le script limite les sorties aux ressources nécessaires, vérifie prudemment l'architecture ARM64/RK3566, distingue `df` du montage de la partition `data` et marque délais moteurs, batterie et latence capteur **non mesurés**. Un modèle de checklist `hardware_audit_policy.py` interdit qu'une déclaration de fixture devienne autorisation physique. [878 tests Python et démonstration purement fictive réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40289135442) ; **aucun robot physique connecté**. [Protocole et critères d'arrêt F6-D](docs/f6d-hardware-audit-protocol-2026-10-26.md).

**F6-C [fusionnée via PR #47](https://github.com/Jean-Philippe56520/Microduck/pull/47), quotas locaux facultatifs :** `offline_resource_budget.py` ajoute des quotas glissants de sollicitations et d'événements **avant** le traitement du cerveau F2-D et la persistance SQLite, ainsi qu'un repli après surcharge CPU/temps ou relevé RSS anormal, avec **seuils de test non calibrés sur RK3566**. Les refus retournent `idle` et n'envoient aucune commande. Le scénario hors PC en faux socket Unix a [réussi en CI avec **861 tests Python**](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40257113819) : **3 cycles fictifs acceptés, 3 refusés, 3 observations fictives journalisées**, zéro commande motrice. Le CPU/RSS sont ceux de l'hôte GitHub, pas les mesures de disponibilité du robot. [Rapport F6-C](docs/f6c-offline-resource-envelope-2026-10-26.md).

**F6-B [fusionnée via PR #46](https://github.com/Jean-Philippe56520/Microduck/pull/46), comparaison exploratoire Python/Rust :** l'expression **non motrice** de scoring `PassiveRhythm._score` est reproduite dans un programme Rust autonome sous `experiments/f6b/`, **sans branchement au cerveau ni portage embarqué**. [La CI hôte](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40256023791) valide **841 tests Python, 4 tests Rust, 1 500 cas de parité exacts**, puis mesure 120 000 scores par langage. Le programme Rust minimal est plus rapide et a un RSS de processus inférieur sur ce banc, mais **il n'intègre ni perception, SQLite ni contrôle constructeur** : ce n'est pas une mesure du RK3566 ni une preuve de marge RAM/énergie. **Décision : garder Python en production du prototype et suspendre tout portage Rust jusqu'à audit matériel.** [Rapport et chiffres F6-B](docs/f6b-python-rust-score-study-2026-10-26.md).

**F6-A [fusionnée via PR #45](https://github.com/Jean-Philippe56520/Microduck/pull/45), préparation documentaire et logicielle hors réseau :** `embedded_readiness.py` inventorie sans connexion les interfaces Unix officielles `robotd` / `mediad` / `tofd`, la révision constructeur épinglée et les fonctions actuellement simulées qui pourront rester autonomes sans PC. Il distingue les cartes Zero 3W et beta par **déclarations de fixtures**, et contrôle prudemment la possibilité d'un stockage persistant Yocto. **`/var/lib/robot` peut exister sans partition `data` montée** : le contrôle ne valide qu'un *candidat*, et utilise toujours `:memory:` au lieu d'écrire sur l'image système. Zéro installation systemd, capteur OEM connecté, PC, mouvement ou identification réelle. [830 tests Python et démonstration de faux montage réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40254981871). [Contrat F6-A](docs/f6a-embedded-readiness-2026-10-26.md).

**F5-D [fusionnée via PR #44](https://github.com/Jean-Philippe56520/Microduck/pull/44), tests adversariaux sur fixtures :** `test_f5d_adversarial.py` reproduit les attaques JSON (faux ordres moteurs, identités et sol sûrs), les réponses HTTP trop lentes, sans taille déclarée ou chunked, ainsi que les retours de worker forgés ou rejoués. Les correctifs durcissent la lecture HTTP non streaming (taille explicite et échéance monotone totale pour **le corps**), revalident la requête et les annotations avant F5-C, et empêchent un état pending fantôme après arrêt du worker. [808 tests Python, compilation et démonstration hors réseau réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40253911518). **Aucune authentification réseau réelle, aucun modèle Qwen, moteur ou capteur validé** ; le flux d'en-têtes HTTP malveillant et les essais sur PC restent des limites. [Rapport F5-D](docs/f5d-adversarial-pc-contract-2026-10-26.md).

**F5-C [fusionnée via PR #43](https://github.com/Jean-Philippe56520/Microduck/pull/43), tests logiciels sur données fictives :** `selective_pc_policy.py` ajoute une **consultation du PC uniquement sur autorisation explicite**, après le choix d'intention locale F5-A. L'inconnu/contradictoire **fictif** est éligible, mais une requête n'est jamais nécessaire au fonctionnement autonome. Quotas persistants dans la SQLite `ExperienceMemory` : **60 s minimum, 2/10 min, 8/24 h**, une consultation en cours, circuit fermé pendant 5 minutes après deux pannes successives ; refus si horloge recule, SQLite est occupée ou PC absent. L'historique ne conserve que l'empreinte d'un ID aléatoire, une issue et une date, sans média, identité ni réponse Qwen. `SelectivePCBridge` utilise le worker F5-B sans bloquer l'intention. [798 tests Python réussis sur la branche et démonstration multi-processus](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40252645890), **sans vrai PC Ollama, robot physique ni moteur**. [Rapport F5-C](docs/f5c-sparse-consultations-2026-10-26.md).

**F5-B [fusionnée via PR #42](https://github.com/Jean-Philippe56520/Microduck/pull/42), prototype logiciel testé sur serveur HTTP simulé :** `ollama_local_client.py` ajoute un transport HTTP Ollama **facultatif**, limité à une adresse IP loopback par défaut et à des catégories d'objets strictement fictives de F5-A. Un worker non bloquant conserve l'intention locale sans PC et rejette les réponses tardives, malformées, contenant un ordre, ou prétendant identifier un animal sans image. `f5b_benchmark.py` prépare une comparaison locale `qwen3.5:4b` puis `qwen3.5:9b`, mais **ne lance aucun modèle ni réseau sans option explicite**. La [CI Python : 781 tests réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40251807307) utilise uniquement un serveur HTTP simulé sur `127.0.0.1` ; **aucune performance réelle du PC, multimodalité, RAM/thermie RK3566, ni communication avec le robot n'est validée**. [Contrat et procédures F5-B](docs/f5b-ollama-local-transport-2026-10-26.md).

**F5-A [fusionnée via PR #41](https://github.com/Jean-Philippe56520/Microduck/pull/41) :** contrat Python pour des **hypothèses PC facultatives**, après la décision locale du cerveau F2-B. Une catégorie d'objet **strictement fictive** inconnue/contradictoire peut être proposée à un futur Qwen avec un JSON borné ; sans PC, le robot conserve son intention locale. Réponse manquante, tardive, malformée, non sourcée ou contenant une commande => hypothèses écartées. Toute suggestion reste **non vérifiée**, sans accès au contrôle moteur, sans écriture de connaissance ou d'identité dans SQLite. **Aucun appel Ollama/Qwen réel, aucun réseau, caméra, haut-parleur ou robot physique** dans F5-A. [757 tests Python réussis en CI, dont 34 F5-A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40250745954) et démonstration fictive sans réseau. [Contrat et limites](docs/f5a-pc-hypotheses-2026-10-26.md).

**F4-D [fusionnée via PR #40](https://github.com/Jean-Philippe56520/Microduck/pull/40) :** `revocable_mock_identity.py` introduit des **associations fictives et volontaires**, **sans biométrie**, dans la même `ExperienceMemory` SQLite : un jeton de fixture de 32 octets est converti en **empreinte HMAC-SHA256** avec une clé fournie au programme, non persistée ; seules référence opaque, classe générique `pet_cat`/`pet_dog`/`child`/`adult`, HMAC et dates/séquences sont stockés. **Aucun nom, photo, voix, jeton brut ou clé privée enregistré.** Toutes les autorisations sont **des déclarations de test non authentifiées**, avec contrôle parental et assentiment déclarés pour `child` à **chaque présentation**. Expiration (7 j par défaut, 30 j maximum), 24 associations max, refus de rejeu, révocation ciblée et `forget_all`. [723 tests Python réussis (34 nouveaux) et démonstration en deux processus avec révocation](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40249168929). [Rapport F4-D](docs/f4d-revocable-optin-contract-2026-10-26.md). **Aucun lecteur de badge, consentement parental réel, reconnaissance individuelle ni action motrice ou audio validés** ; la suppression SQL n'est pas une garantie d'effacement des sauvegardes.

**F4-C [fusionnée via PR #39](https://github.com/Jean-Philippe56520/Microduck/pull/39) :** `mock_social_cues.py` ajoute à l'existant `AutonomyBrain.propose_balanced_passive` des propositions **strictement fictives et silencieuses par défaut** : attention visuelle courte (250 ms annoncées), invitation au jeu (300 ms), son bref non verbal (180 ms) et repos motivationnel, **sans émission sonore ni mouvement réel**. Opt-in/supervision/confidentialité sont **des déclarations de fixtures, pas un consentement authentifié** ; aucun son sans opt-in audio distinct. Catégories sensibles/ambiguës, mots-clés vocaux et capteur incertain ⇒ silence. Historique local ne gardant que catégorie générique, type et horodatage ; intervalle global 10 s, même indice 60 s, au maximum deux propositions sonores par 10 min, persistées dans la SQLite existante. [689 tests Python réussis (27 nouveaux), démonstration en deux processus](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248330199), [rapport F4-C](docs/f4c-social-cue-contract-2026-10-26.md). **Aucune commande au haut-parleur, tête ou moteur, aucune reconnaissance individuelle ni interaction physique validée.**

**F4-B [fusionnée via PR #38](https://github.com/Jean-Philippe56520/Microduck/pull/38) :** `uncertain_spatial_memory.py` introduit des **repères exclusivement fictifs et historiques** dans la SQLite `ExperienceMemory` : cinq catégories génériques, deux cadres artificiels indépendants, coordonnées locales et rayons d'erreur **déclarés mais non mesurés**, contrôle de fraîcheur, rejets des coordonnées contradictoires et conservation bornée. Le rappel **n'accorde jamais le statut de sol sûr ni le droit de navigation** ; même un repère prétendument très fiable laisse `AutonomyBrain` choisir `halt` si les données de sécurité manquent. [662 tests Python réussis, 27 nouveaux F4-B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40247354468), avec démonstration dans deux processus SQLite indépendants. [Rapport F4-B](docs/f4b-uncertain-spatial-memory-2026-10-26.md). **Ni carte de maison, ni localisation physique, ni capteur OEM authentifié, ni robot ni commande motrice validés.**

**F4-A [fusionnée via PR #37](https://github.com/Jean-Philippe56520/Microduck/pull/37) :** ajout de deux tables de connaissances dans la SQLite `ExperienceMemory`, **sans second cerveau** : `category_semantics.py` conserve des catégories **historiques fictives**, seulement si la preuve F1-C et F2-C est présente, active et récente ; les hypothèses de propriétés restent **non confirmées et séparées**. `behavioral_memory.py` reprend uniquement les **conséquences explicitement fictives** des cycles P2a, calculant un biais descriptif de **0,04 par réussite/échec**, plafonné à **±0,12** et non connecté à `robotd`. Retraits, durée de conservation 14 jours, quotas et tests de redémarrage. [635 tests Python réussis (37 nouveaux), démonstration SQLite dans deux processus](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40246670514). [Rapport F4-A](docs/f4a-semantic-behavior-memory-2026-10-26.md). Aucune reconnaissance individuelle, capteur réel, commande motrice ou apprentissage de modèle.

**F3-E [fusionnée via PR #36](https://github.com/Jean-Philippe56520/Microduck/pull/36) :** revue déclarative de **48 sources publiques** (aucune contre-annotation humaine réellement enregistrée) et vérification hors connexion des réponses `media.frame` (UYVY) sur fixtures. Deux avis concordants restent des **déclarations**, jamais une preuve de licence ou une autorisation d'entraînement. Le précontrôle de caméra **n'ouvre aucun socket, ne stocke aucun pixel et n'accorde aucun droit moteur**. [598 tests Python réussis, 28 nouveaux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40245623218), [rapport F3-E](docs/f3e-annotation-frame-preflight-2026-10-26.md). Aucune validation sur robot.

**F3-D [fusionnée via PR #35](https://github.com/Jean-Philippe56520/Microduck/pull/35) :** ajout de **28 photos publiques déclarées CC0** (8 chats, 8 chiens, 12 exemples hors catégorie) dont les auteurs et fichiers sont distincts de toutes les partitions F3-B. Le seuil MobileNetV2 ONNX reste **figé sur la validation F3-B**, sans réentraînement. Sur le nouveau jeu : **20/28 exactes**, mais seulement **3/8 chats et 5/8 chiens correctement reconnus** ; 12/12 images hors catégorie rejetées (**0/12 faux positifs, échantillon trop petit pour garantir un taux nul**). Le banc Linux CI a mesuré **9,036 ms d'inférence CPU médiane** et **108 148 Kio de pic RSS du processus entier (~105,6 Mio)**, pas du seul modèle ni du Rockchip. [570 tests Python réussis (19 nouveaux)](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671272), [banc réel et ressources](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671367), [rapport et sources](docs/f3d-open-set-resource-benchmark-2026-10-26.md). **Ni précision domestique, ni capacité de détecter visuellement un animal individuel, ni sécurité motrice ne sont établies**. **F3-E fusionnée via PR #36**, uniquement sur métadonnées et fixtures, sans capture réelle.

**F3-C [fusionnée dans `main` via PR #34](https://github.com/Jean-Philippe56520/Microduck/pull/34) :** lecture des formats `media.video` et `media.detections` du constructeur dans la **révision épinglée**, avec contrôle des champs, tailles, géométrie, boîtes et origine **non authentifiée**. Le socket local `media.frame` ne fournit pas ces notifications : aucune session WebRTC ni capture de pixels n'est ouverte. Le détecteur OEM voit les autres **Microducks** ; `pet-detect` perçoit des **sons de caresses**, et ne reconnaît ni animaux ni mots-clés vocaux. Les faux signaux `Microduck`/`stop`/`viens` restent **des hypothèses de fixtures**, sans action motrice. [551 tests Python réussis sur la branche, dont 31 nouveaux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40243859433). [Rapport F3-C](docs/f3c-oem-media-notifications-2026-10-26.md). **F3-D fusionnée via PR #35**, évaluation sur images CC0 publiques sans capteur physique ; **F3-E fusionnée dans `main` via PR #36**.

**État vérifié au 25 octobre 2026 :** P0j [fusionné dans `main` (PR #22)](https://github.com/Jean-Philippe56520/Microduck/pull/22) a [recalculé hors ligne les charges de pieds de l'archive P0e](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655) : **79 échantillons repos, 127 marche, 0 appui unipodal échantillonné**, et part moyenne de charge du pied gauche **52,03 % → 44,54 %**. **[269 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946) et [replay P0e réussi en CI P0j](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655)**, zéro commande motrice nouvelle, aucune cause démontrée ni validation physique. [Rapport P0j](docs/mujoco-p0j-load-transfer-2026-10-25.md). P0i [fusionné dans `main` (PR #21)](https://github.com/Jean-Philippe56520/Microduck/pull/21) a réussi sa [comparaison instrumentée MuJoCo](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) avec **1,444 mm alpha contre 1,968 mm VelStand** (2 arrêts confirmés, 48 notifications au total) et [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915). Les deux configurations sont **sous le seuil expérimental de 10 mm**, sans preuve de gait ni cause démontrée, P1a reste bloqué et aucun robot physique testé. P0h **fusionné dans `main`** ([PR #20](https://github.com/Jean-Philippe56520/Microduck/pull/20)) a validé [243 tests Python sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219827102) et un [audit MuJoCo/ONNX officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) : `duck-sim` force la paire alpha alors que `robotd` utilise normalement `velstand`, trois modèles présents et différents, aucune causalité de non-marche prouvée. P2b a été **fusionné dans `main`** ([PR #19](https://github.com/Jean-Philippe56520/Microduck/pull/19)) : **[234 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216649169)** et [MuJoCo officiel validé pour six cycles cognitifs passifs](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) (3 puis 6 entrées SQLite, six intentions `halt`, zéro commande motrice et aucune récompense). P2a a démontré la mémoire fictive persistante ; P0g a comparé les variantes de contacts. La marche reste non validée (dernier essai moteur P0e : **2,295 mm**, arrêt confirmé), P1a bloqué et aucun robot physique testé.

**Cognition sans mouvement (P2a) :** [217 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40207932413) et **deux sessions fictives successives** sur une même SQLite. Journal de 8 cycles, préférence fictive persistée, tout mouvement non exécuté. Cela ne résout pas le blocage locomoteur P1a.

**Historique des jalons ci-dessous :** les mentions « prochaine étude » de ces rapports décrivent les décisions de leur époque et **ne remplacent pas la priorité courante du plan directeur (M1-B fusionnée via PR #50, regroupement multi-signatures et évaluation CC0 très limitée ; aucune mesure physique RK3566, ni Qwen 4B/9B réellement exécuté)**.

### P0j — Relecture hors ligne des forces d'appui P0e (PR #22)

Sans nouveau mouvement, le module `sim_p0j_load_transfer.py` vérifie les SHA-256 exacts des anciens diagnostics du solveur MuJoCo P0e et calcule le transfert de charge gauche/droite. La [CI P0j](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655) a réussi : **269 tests Python**, replay du traceur original à 50 Hz, **127/127 relevés de marche avec deux pieds en charge**, 0 relevé sur un seul pied, part de charge gauche passant de **52,03 % au repos** à **44,54 % en marche**. Le changement de charge n'est ni un changement d'appui unipodal, ni une preuve de traction ou de marche. [Rapport détaillé](docs/mujoco-p0j-load-transfer-2026-10-25.md) ; **cause inconnue et P1a bloqué**. Les [269 tests passent aussi sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946).

### P0i — Essai comparatif alpha / VelStand en MuJoCo (PR #21)

La [PR #21](https://github.com/Jean-Philippe56520/Microduck/pull/21), fusionnée, teste les politiques v8 du constructeur, à **0,12 m/s, 24 notifications par essai**, sur deux démarrages indépendants et deux SQLite séparées ; `robotd` seul pilote les moteurs. La [CI MuJoCo officielle](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) a vérifié les configurations réellement chargées, les deux arrêts, **1,444 mm XY pour alpha** et **1,968 mm pour VelStand**, donc **aucune translation de 10 mm**. Le premier lancement a refusé le bras B, car il inspectait le gabarit `robotd.toml` plutôt que le paramètre actif `robotd-duck-a.toml` ; cette différence OEM a été corrigée, sans supprimer les garde-fous. [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915). **Un essai par configuration dans l'exécution finale ne démontre pas une causalité ni une démarche.** Voir [rapport P0i](docs/mujoco-p0i-controlled-policy-pair-2026-10-25.md) ; P1a reste bloqué.

### P0h — Auditer les politiques constructeur sans commande moteur (PR #20)

La [PR #20](https://github.com/Jean-Philippe56520/Microduck/pull/20), fusionnée, identifie une **différence réelle de sélection ONNX** : `robotd` charge normalement `velstand.onnx` sans second modèle debout, tandis que le lancement `duck-sim` force `alpha_walking.onnx` et `alpha_stand.onnx` (seuil vitesse `0,05`). L'audit vérifie les sources épinglées, les déclarations de filiation W&B et les fichiers du bundle v8, puis compare des sorties ONNX CPU **sur données synthétiques**, sans aucune commande de mouvement. [243 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219234669) ; [validation sur les trois ONNX installés et le MuJoCo officiel réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) (bundle v8, 10 entrées de manifeste, trois modèles 61→14, empreintes SHA-256, distances brutes L2 0,2296 et 0,1524, zéro commande motrice). **La cause de l'échec locomoteur n'est pas démontrée.** Voir [rapport P0h](docs/mujoco-p0h-policy-slot-lineage-2026-10-25.md).

### P2b — Cycles passifs sur les services simulés (PR #19, testé MuJoCo)

La [PR #19](https://github.com/Jean-Philippe56520/Microduck/pull/19), désormais fusionnée, ajoute une collecte répétée des télémétries `robotd`/`tofd` du simulateur, des choix cognitifs passifs et un journal SQLite réouvert entre deux sessions. Les données périmées, non progressives ou incohérentes conduisent à `halt`. Les intentions ne deviennent jamais des commandes, récompenses ou résultats de déplacement. **234 tests Python réussis** sur branche ; l'[exécution MuJoCo officielle](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) a réussi **3 + 3 cycles cohérents, avec 3 puis 6 entrées SQLite**, zéro ordre moteur et zéro récompense. Les six décisions ont été `halt` faute de sol certifié. Voir [rapport P2b](docs/p2b-passive-mujoco-cycles-2026-10-25.md). Aucune validation robot physique.

### P0g — Comparaison des géométries compilées (PR #18)

La [PR #18](https://github.com/Jean-Philippe56520/Microduck/pull/18) compare des copies temporaires des trois variantes constructeur à une posture STAND identique, sous MuJoCo épinglé, par **mj_forward seulement**, sans commande moteur ou modification OEM. La [CI officielle a réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208635206) : **76 / 82 / 141 géométries compilées** pour Walk / Groundcontact / AllCollisions et **2 / 10 / 69** éligibles aux masques du sol. Les semelles et le plan ont mêmes friction, solref et solimp dans les trois modèles. Aucun contact candidat à l'état STAND brut sans relaxation dynamique ; ce zéro ne contredit pas les forces sous charge mesurées P0d. **Cause locomotrice inconnue, P1a bloqué.** [Rapport P0g](docs/mujoco-p0g-compiled-contacts-2026-10-25.md). P0h vérifie ensuite les politiques velstand/alpha_walking et leur provenance, sans encore lancer de comparaison motrice. P2b a été fusionné.

### P2a — Cycles autonomes fictifs et mémoire durable (PR #17)

La [PR #17](https://github.com/Jean-Philippe56520/Microduck/pull/17) ajoute **quatre cycles de décision consécutifs par session fictive**, avec journal SQLite de chaque intention, décision ultérieure sensible aux préférences mémorisées, et réouverture effective de la même base lors d'une seconde session. [217 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40207932413) ; démonstration de CI : **4 puis 8 cycles persistés**, préférence fictive pour un jouet **0,06 maintenue après redémarrage**.

Le système **ne commande jamais un moteur** : `explore` et `play_with_object` sont journalisées comme **non exécutées** ; un retour positif ou négatif n'est pris en compte que s'il est **explicitement fictif**, daté, attaché à une inspection `mock` ciblée et corroboré par une seconde observation fictive fraîche. Sans cette confirmation, aucune préférence n'est modifiée. Une perte de preuves de sûreté produit `halt`, même après un précédent résultat positif.

Commande de reproduction purement locale :

```bash
python -m microduck_companion.mock_cycle_demo --database /tmp/p2a-local.sqlite3 --session first
python -m microduck_companion.mock_cycle_demo --database /tmp/p2a-local.sqlite3 --session second
```

Ce jalon **n'est pas** une boucle de navigation autonome validée dans MuJoCo ni sur un robot physique. Prochain P2b : exécuter plusieurs cycles **sans déplacement** avec les observations datées `robotd` et `tofd` de MuJoCo, sans transformer une intention de marche en commande physique. Voir le [rapport P2a](docs/p2a-mock-cycles-2026-10-25.md).

### P0f — Politiques ONNX et variantes de simulation (PR #16)

La [PR #16](https://github.com/Jean-Philippe56520/Microduck/pull/16) ajoute un audit **sans commande motrice** des deux ONNX nommés par `duck-sim` (`alpha_walking` et `alpha_stand`, jeu v8 déclaré) et du contrat de `robotd`. [207 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419766) et [smoke MuJoCo headless](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419709) réussis : chaque ONNX répond à **61 observations / 14 actions float32**, **non récurrent**, et les constantes HOME présentent **0 rad d'écart** entre contrôle et entraînement. Une entrée **synthétique** vx 0 → 0,12 m/s fait varier la sortie brute du modèle de marche de **0,147 L2**.

Les sources comparent des variantes différentes : `robot_walk.xml` (tâche vitesse, 2 balises géométriques de collision explicites), `robot_allcollisions.xml` (tâche VelStand, 69) et `robot_groundcontact.xml` (headless `duck-sim`, 10). **Ce sont des comptes de balises XML, pas des contacts simulés mesurés** et la provenance d'entraînement exacte des poids v8 n'est pas démontrée. Le filtrage des actions et la différence d'échelle 1,0 / 0,9 exigent également un contrôle de version avant conclusion.

Voir le [rapport P0f](docs/mujoco-p0f-policy-contract-2026-10-25.md). **Les entrées 61D et sorties brutes 14D réellement utilisées dans la boucle `robotd` n'ont pas été capturées** ; aucune cause racine de l'absence de marche n'est démontrée, et P1a reste bloqué. Prochaine recherche P0g : confronter les paramètres géométriques et contacts compilés des trois variantes en MuJoCo indépendant et sans modification des sources constructeur ; poursuivre P2 en parallèle.

### P0e — Gains actifs et cohérence de la loi d'actionnement (PR #15)

La [PR #15](https://github.com/Jean-Philippe56520/Microduck/pull/15) ajoute une capture **avant** le pas MuJoCo et un audit **hors ligne** : gain réellement actif, biais, limites de force, consigne, position et vitesse, comparés à l'effort observé après le pas original. La sonde reste facultative, n'écrit dans aucune commande ou paramètre constructeur, et exige l'essai J2e borné avec `robot.stop` confirmé.

Dans le [scénario MuJoCo officiel réussi #40193139617](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617), **199 tests Python réussis** : gains de **0,44 N·m/rad** au repos (79/79 relevés) et **0,55 N·m/rad** sur 123/127 relevés de marche (quatre à 0,44). **2 884 efforts** correspondent exactement à la loi du modèle et aucun écrêtage à ±0,96 N·m n'a été observé. Pourtant, **127/127 trames montrent les deux pieds chargés**, et le déplacement final est seulement **2,295 mm**. Voir le [rapport P0e](docs/mujoco-p0e-actuator-gains-2026-10-25.md) pour la provenance, la cadence, les exceptions et les limites.

**Ce résultat exclut un défaut évident de conversion gain/effort pour les échantillons mesurés, mais ne démontre ni une marche valide ni une cause de l'absence de propulsion.** Prochaine étude P0f : comparer les commandes/références de la politique ONNX et les conditions de simulation/entraînement sans changer arbitrairement les gains ou les garde-fous.

### P0d — Contacts et consignes originaux du solveur (PR #14)

La [PR #14](https://github.com/Jean-Philippe56520/Microduck/pull/14) ajoute un tap optionnel **dans le processus headless officiel MuJoCo épinglé**, sans changer les fichiers constructeur ni émettre de commandes motrices. Il prélève les **contacts/forces réels de MuJoCo** (`MjData.contact`, `mj_contactForce`) et les **consignes de position articulaires** (`data.ctrl`) à environ 50 Hz, avec file non bloquante et contrôle de provenance.

Le [premier essai P0d officiel réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190232870) a montré les **deux pieds sous force normale > 0,1 N sur 126/126 relevés de marche**, des écarts entre les variations de commande et d'angle (roulis hanches gauche/droite particulièrement), ainsi que **2,222 mm** de déplacement net final malgré 23/24 politiques `walk` et `robot.stop` confirmé. Ce sont des **mesures de physique simulée**, pas du robot physique ; le diagnostic peut lui-même ajouter du temps CPU. La [suite logicielle durcie compte 190 tests réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697176).

La [seconde exécution P0d avec sonde durcie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697090) confirme **les deux pieds chargés sur 132/132 trames de marche**, un déplacement de **1,597 mm**, et des écarts consigne/angle pour le roulis des hanches et les genoux. L'effort simulé est cohérent avec un gain positionnel d'environ 0,55 N·m/rad déclaré par le constructeur, mais ce rapprochement **n'explique pas encore pourquoi la démarche ne progresse pas**.

Voir le [rapport de preuve P0d](docs/mujoco-p0d-live-solver-2026-10-25.md). **La cause racine est toujours inconnue, et P1a reste bloqué** ; la prochaine étude doit isoler l'écart de suivi des consignes et son rôle causal, sans retoucher les moteurs au hasard.

### P0c — Contacts géométriques reconstruits hors ligne (PR #13)

La [PR #13](https://github.com/Jean-Philippe56520/Microduck/pull/13) conserve le **quaternion WXYZ OEM** et reconstruit hors ligne, via `mj_forward` sur un `MjData` indépendant, les candidats de contact entre la semelle gauche/droite et le sol. Le [scénario officiel MuJoCo](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954) a réussi : **179 tests Python**, 16 relevés `stand` et 24 relevés pendant **un** essai J2e (23 `walk`), les **deux semelles en léger chevauchement géométrique dans 40/40 trames**, déplacement final **1,997 mm**, `robot.stop` confirmé.

Ces contacts sont **reconstitués** à 10 Hz, pas capturés par le solveur pendant l'essai : aucune force de contact, aucun glissement ni preuve de marche. Le [rapport P0c](docs/mujoco-p0c-contact-replay-2026-10-25.md) distingue précisément la proximité des pieds de l'appui dynamique réel ; les précédents relevés P0b dépourvus de quaternion sont rejetés. Aucun code constructeur ni mécanisme moteur n'a été modifié.

### P0b — Comparaison articulations / repos / marche (PR #12)

La [PR #12](https://github.com/Jean-Philippe56520/Microduck/pull/12) ajoute un comparatif **sur le même simulateur OEM épinglé**, avec **16** relevés passifs `stand` puis **24** relevés pendant **un seul essai J2e** existant à 0,12 m/s, strictement protégé par `robotd`. La commande n'est lancée que sur activation explicite (variable `MICRODUCK_SIM_WALK_COMPARE=YES` **et** option `--enable-once`) et après une baseline stable.

Dans le [workflow MuJoCo réussi #40187514292](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514292), la politique a été `walk` sur 23/24 relevés et les genoux ont bougé (gauche ~1,28°, droit ~0,46° d'excursion). **Le déplacement net final de J2e est seulement 1,338 mm**, surtout sur Y du monde ; `robot.stop` est confirmé et la mémoire constate `no_progress_observed`. La comparaison ne révèle **pas** une cause certaine de l'absence de marche.

Voir le [rapport mesuré P0b](docs/mujoco-p0b-stand-walk-comparison-2026-10-25.md) pour les résultats complets et la distinction des fenêtres d'échantillonnage. Les contacts dynamiques et cibles articulaires ne sont toujours pas exposés dans l'API `op=read` ; ils ne sont ni simulés par notre logiciel ni présentés comme mesurés.

### Diagnostic passif P0a (PR #11)

La [PR #11](https://github.com/Jean-Philippe56520/Microduck/pull/11) ajoute
`microduck_companion/sim_joint_trace.py`. Après démarrage du simulateur officiel
épinglé, cet outil échantillonne **sans commande motrice** `body_server` (uniquement
`hello` puis `read`) et les notifications `robot.state` via `robot.subscribe` :

```sh
python3 -m microduck_companion.sim_joint_trace \
  --state-dir "$HOME/.cache/duck-sim-companion" \
  --rl-root "$PWD/upstream/microduck_rl" --port 17801 \
  --samples 8 --hz 5 --output /tmp/microduck-joint-trace.json
```

Le JSON conserve les positions et vitesses des 15 entrées articulaires,
les courants **simulés non calibrés** (proxy de force, pas des ampères réels),
la pose du tronc, les horodatages, et les politiques/vitesses déclarées par
`robotd`. La provenance du simulateur, l'intégrité de la scène et le processus
`body_server` sont vérifiés. Toute donnée invalide ou périmée fait échouer la sonde.

**Limite documentée :** le protocole officiel épinglé ne fournit ni les
**contacts dynamiques des pieds** ni les **consignes articulaires** ; ces champs
restent `null`. La télémétrie passive ne prouve pas une marche. Le workflow
MuJoCo a effectivement archivé `joint-trace.json` dans le [workflow P0a réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580637) : **8 échantillons à 5 Hz**, 1,4 s simulée, `stand` sur 8/8 échantillons, **0 commande motrice**, **0,991 mm de variation nette du tronc au repos**. Il s'agit d'une référence de dérive au repos, pas d'une preuve de translation en marche. Les essais J2e antérieurs
restent des résultats négatifs inchangés. Aucun pilote réel n'a été interrogé.

### Étapes principales

- [x] Récupérer les deux bases officielles sous forme de sous-modules.
- [x] Tester un premier moteur d'autonomie et une mémoire locale.
- [x] Brancher les observations aux démons officiels du simulateur MuJoCo (lecture seule).
- [x] Vérifier la zone plane épinglée, les intentions bornées et l'arrêt via `robotd` en **simulation**, sans preuve de marche effective.
- [ ] Diagnostiquer la locomotion et démontrer une progression mesurée de plus de 10 mm en simulation (critère proposé, pas atteint).
- [ ] Répéter la boucle perception → action → observation → mémoire sur plusieurs cycles et sessions.
- [ ] Développer une perception mesurée d'objets/animaux et les interactions sociales prudentes.
- [ ] Tester Qwen sur le PC en mode **facultatif**, avec repli autonome hors connexion.
- [ ] Vérifier les ressources, la vitesse et la sécurité sur le matériel réel.

**Le robot physique n'est pas encore disponible.** Les étapes P0–P5 peuvent être étudiées en simulation, avec des jeux de test ou sur le PC, sans présenter ces travaux comme une validation matérielle.

## Contrat de perception (prototype V0)

Le module `microduck_companion/perception.py` fournit `PerceptionEvent` et `PerceptionSnapshot` (schéma v1). Chaque événement déclare sa provenance (`mock`, `simulator`, `sensor`, `robotd`, etc.), sa confiance, une heure monotone et une durée de validité limitée. Le moteur utilise `AutonomyBrain.choose_from_snapshot(snapshot)` pour obtenir une `Scene` conservatrice :

- absence ou expiration du signal de sol, de zone, d'obstacle ou de batterie : intention `halt` (ou `rest` si la batterie faible est confirmée) ;
- contradiction ou manque de confiance dans une mesure de sécurité : pas d'autorisation de déplacement ;
- les affirmations de Qwen n'attestent jamais la sécurité et ne sont jamais promues en observation de capteur ;
- étiquettes `mock`, `simulator` et `sensor` conservées distinctement en SQLite ; un souvenir fictif ne prouve pas une reconnaissance réelle.

L'ancienne méthode `choose(Scene(...))` est maintenue pour les essais synthétiques et **ne doit pas devenir un adaptateur de commande motrice**. Les sources ne sont pas encore authentifiées par un pilote, et aucun vrai capteur n'alimente ces événements : ce sont des protections de prototype, pas une homologation matérielle. `robotd` demeure seul responsable des moteurs et de la sécurité.

Exécuter `python -m unittest discover -s tests -v` pour les tests de sécurité. La **connexion en lecture seule à MuJoCo a été vérifiée** sur un exécuteur GitHub Actions ; une première démonstration de déplacement autonome sûr reste à construire.

## Sonde de télémétrie JSON-RPC (J2a, lecture seule)

Le module `microduck_companion/sim_ipc.py` sait lire `robot.health`, souscrire à `robot.subscribe` (`robot.state`) et `tof.stream` (`tof.frame`) sur les sockets Unix des démons officiels. Il limite la taille des trames, la cadence demandée et les délais de réception ; les données malformées ou manquantes sont rejetées. Les 64 mesures ToF sont conservées avec leurs statuts bruts : **elles ne prouvent pas que le sol est sûr**.

Avec `duck-sim` démarré sur Linux/WSL2, exécuter depuis la racine du dépôt :

```sh
python -m microduck_companion.sim_probe --state-dir "$HOME/.cache/duck-sim"
```

La commande affiche l'état et des échantillons de télémétrie, sans envoyer aucune intention motrice. Elle renvoie un code non nul si `robotd` est malade ou si le flux est inaccessible. Le client possède des tests avec **faux services Unix** et a également été **exécuté avec les véritables services `robotd`/`tofd` en simulation MuJoCo**, lors de l'essai GitHub Actions du 25 octobre 2026. Il ne construit pas encore les événements `floor_clear` ou `safe_area` nécessaires pour autoriser une exploration.

### J2b — Observation conservatrice, sans commande motrice

Le module `microduck_companion/sim_bridge.py` transforme les lectures reçues de `robotd` et `tofd` en un `PerceptionSnapshot` versionné. Il vérifie la fraîcheur, la santé des démons, l'état de chute, la cadence de contrôle et, quand disponible, la cohérence des horloges. Il ne certifie **jamais** le sol ou la zone à partir du ToF, et ne fabrique ni `safe_area`, ni `floor_clear`, ni distance d'obstacle fiable. La décision normale est donc `halt` (ou `rest` lorsque la batterie basse est confirmée sur une télémétrie cohérente).

Pour afficher cette décision quand un simulateur fonctionne déjà :

```sh
python -m microduck_companion.sim_observer --state-dir "$HOME/.cache/duck-sim"
```

Depuis un clone Git sur Linux/WSL2, le script suivant vérifie les prérequis puis démarre un environnement isolé sans caméra, avec arrêt en fin d'essai :

```sh
sh scripts/sim-smoke.sh check
DUCK_SIM_DEP_MODE=runtime sh scripts/sim-smoke.sh run
```

Le mode `run` initialise les sous-modules épinglés puis utilise `duck-sim`, `sim_probe` et `sim_observer`. `DUCK_SIM_DEP_MODE=runtime` installe sur Python 3.12 un ensemble minimal **épinglé** et vérifié pour le simulateur sans caméra (MuJoCo 3.10.0, NumPy 2.5.4 et ONNX Runtime 1.28.0), afin d'éviter les lourdes dépendances d'entraînement. Sans cette variable, `uv sync --frozen` utilise l'environnement RL officiel complet. Les politiques motrices officielles sont toujours téléchargées par `duck-sim` ; elles ne sont pas remplacées par le compagnon.

**Premier essai officiel réussi** : [GitHub Actions #40145369078](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078) a exécuté les 81 tests et lancé MuJoCo en mode headless sur Ubuntu 24.04. `robotd` a rapporté ~50 Hz (0 échéance manquée dans la fenêtre observée), `duck-sim realtime` **1,00×**, deux trames ToF simulées de **64 cellules** et une décision du cerveau `halt` sans commandes motrices. Cette mesure concerne uniquement ce test sur une machine CI Linux, **pas** les ressources ni la sûreté sur le Microduck physique.

Le script constructeur peut lever **son robot virtuel** pendant l'initialisation ; notre cerveau ne commande pas de mouvement. L'intégration validée est **lecture seule** : elle n'établit ni un sol sûr, ni une navigation autonome, ni une reconnaissance d'objets.

## Audit matériel et mémoire

- [Audit de faisabilité du matériel, de la vision, de la RAM et du stockage](docs/hardware-feasibility-audit-2026-10-25.md)
- [Script de mesures en lecture seule pour une unité réelle](scripts/resource-audit.sh)
- Troisième source officielle : [microduck_yocto — OS, partitions et carte beta](https://github.com/pollen-robotics/microduck_yocto).

L'image OS décrite en octobre 2026 prévoit une partition persistante de 8 Gio ; la RAM réellement disponible et l'espace libre ne sont pas encore mesurés sur l'unité commerciale.


## J2c — Contrôle d'une zone plane dans MuJoCo (simulation uniquement)

Le module expérimental `microduck_companion/sim_flat_zone.py` **ne transforme pas les distances ToF en preuve de sol sûr**. Il consulte directement le serveur du corps simulé (`op=read`) et vérifie au préalable le dépôt `microduck_rl` épinglé, son absence de modifications suivies, le hash Git exact de la scène `scene.xml`, le processus Linux `body_server` et ses paramètres (un seul robot, scène par défaut, sans caméra). Toute autre scène ou version est refusée.

Sur la scène officielle plane et vide, la pose `trunk`, la hauteur et la gravité projetée permettent de tester une petite zone virtuelle radiale de **0,90 m**, avec marge de **0,16 m** autour du robot et interdiction d'approcher à moins de **0,35 m** de la limite. Ce sont des **paramètres expérimentaux du simulateur**, pas des distances d'obstacles mesurées sur robot réel.

Pour tester sans commandes motrices, après démarrage du simulateur officiel :

```sh
python -m microduck_companion.sim_zone_probe \
    --state-dir "$HOME/.cache/duck-sim-companion" \
    --rl-root "$PWD/upstream/microduck_rl" --port 17801
```

Une pose incertaine, un processus inconnu, une source périmée ou une scène modifiée donnent `halt`. Le script `scripts/sim-smoke.sh` exécute désormais cette sonde après les vérifications initiales. **Ce jalon ne délivre aucune commande `robot.move`.** La [validation officielle MuJoCo #40173323079](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173323079) a **réussi** : scène certifiée, zone sûre, tronc à (0,0257 ; 0,0069 ; 0,1155) m, réserve de 0,7134 m, décision du cerveau `explore` et aucune commande motrice. Les **103 tests Python** sont également réussis. Prochaine étape : une seule impulsion de mouvement, limitée en vitesse et en durée et envoyée uniquement à `robotd`.


## J2d — Impulsion limitée via robotd (expérience MuJoCo)

`microduck_companion/sim_motion.py` contient une **unique** démonstration de mouvement, non réutilisable sur robot physique. Après autorisation par le cerveau et preuve de la zone MuJoCo plane officielle, il adresse des notifications `robot.move` à `robotd` avec une vitesse avant **fixe de 0,05 m/s**, quatre impulsions séparées de 0,1 s ; ni rotation ni déplacement latéral. Le client revérifie la scène, la position, la réserve de zone, la batterie et la cadence `robotd` avant **chaque** notification. Toute perte de preuve arrête les nouvelles notifications, et un appel `robot.stop` est envoyé et vérifié. Le deadman constructeur (~500 ms) demeure actif en dernier recours.

**Aucun mouvement n'est envoyé par défaut**, y compris dans les workflows manuels habituels. Pour un essai unique sur la machine Linux où le simulateur officiel est déjà en fonctionnement :

```sh
MICRODUCK_SIM_MOTION_TEST=YES python -m microduck_companion.sim_motion_demo \
  --enable-once --state-dir "$HOME/.cache/duck-sim-companion" \
  --rl-root "$PWD/upstream/microduck_rl" --port 17801
```

Le script `sim-smoke.sh` ne lance cette démonstration que si `DUCK_SIM_SHORT_MOVE=YES` est explicitement présent. Le workflow GitHub Actions ne définit cette variable que pour la branche expérimentale `feat/one-bounded-sim-intent-20261025` ; sur `main`, il reste en lecture seule.

**Essai MuJoCo effectué et réussi :** [GitHub Actions #40173809463](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173809463), 115 tests Python verts, `robotd` sain à ~50 Hz, 1,00× temps réel, **4 notifications `robot.move`**, `robot.stop` confirmé. Évolution observée du tronc : **0,0001848 m (0,185 mm)** en ~0,36 s de temps simulé. Cette très faible variation ne prouve **pas** une marche ; elle peut provenir de la stabilisation en posture. Aucune navigation autonome, aucun évitement d'objets mobiles et aucune validation physique.


## J2e — Mesurer une translation et conserver l'expérience (MuJoCo seulement)

Le code constructeur choisit la politique de station debout lorsque la norme de la vitesse demandée est au plus égale à **0,05 m/s**. C'est probablement pour cela que le premier essai, à exactement 0,05 m/s, n'a produit qu'une variation de **0,185 mm** (hypothèse à vérifier). Le nouveau module expérimental `sim_walk_trial.py` demande une seule séquence à **0,12 m/s**, donc au-dessus de ce seuil, sans rotation ni déplacement latéral. Il effectue jusqu'à **24 notifications espacées de 0,1 s** sous réserve d'une zone sûre : soit environ 2,4 s de commandes, avec un budget d'exécution maximal de 4,0 s et `robot.stop` obligatoire.

Le contrôleur vérifie systématiquement le simulateur épinglé, sa scène sans obstacles, la santé `robotd`, la cadence, la position et la marge à la zone. Une **dérive du tronc sans mouvement commandé** est mesurée d'abord. Si la dérive dépasse 5 mm, si une source est douteuse ou si le cerveau ne choisit pas `explore`, **aucun mouvement n'est envoyé**. Aucune adaptation constructeur n'est modifiée.

Après l'accusé de réception de `robot.stop`, une nouvelle position et la santé de `robotd` sont contrôlées. Le module `episodic_memory.py` conserve une table SQLite distincte des souvenirs d'objets (`sim_motion_trials`), avec provenance, déplacement horizontal, dérive de référence, état de sécurité et résultat. Les catégories sont `translation_observed`, `no_progress_observed`, `inconclusive_drift` et `unverified`. Une préférence d'exploration évolue **lentement** uniquement sur une conséquence fiable : cette mise à jour de mémoire n'est **pas un entraînement du modèle**.

Exemple, uniquement sur Linux avec la simulation officielle déjà lancée :

```sh
MICRODUCK_SIM_WALK_TEST=YES python3 -m microduck_companion.sim_walk_demo \
  --enable-once --state-dir "$HOME/.cache/duck-sim-companion" \
  --rl-root "$PWD/upstream/microduck_rl" \
  --memory "$HOME/.local/share/microduck-companion/sim-motion.sqlite" \
  --port 17801
```

En CI, `DUCK_SIM_WALK_TRIAL=YES` est volontairement activé **seulement** sur `feat/measured-sim-walk-learning-v1`. Sur la branche principale, aucun nouveau mouvement n'est autorisé par défaut. Le CLI renvoie **3 si la translation mesurée reste sous le seuil**, ce qui n'est ni un plantage du protocole, ni une validation de marche. Le script CI classe explicitement ce cas `WALK_TRANSLATION_ACCEPTANCE=NOT_MET` et n'accepte aucun échec de communication ou de `robot.stop`.

### Mesures MuJoCo officielles — résultats négatifs

| Essai | Vitesse demandée | Commandes | Politique / vitesse appliquée | Déplacement du tronc | Dérive avant commande | Résultat |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| [J2e-A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175133570) | 0,12 m/s | 12 | non instrumentée | 1,242 mm | 0,105 mm | pas de progression validée |
| [J2e-B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175696383) | 0,12 m/s | 12 | `walk` 11/12 ; 0,12 m/s appliqué | 0,820 mm | 0,037 mm | pas de progression validée |
| [J2e-C](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176018018) | 0,12 m/s | 24 | `walk` 23/24 ; 0,12 m/s appliqué | 1,399 mm | 0,273 mm | pas de progression validée |
| [J2e-D](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) | 0,12 m/s | 24 | `walk` 23/24 ; 0,12 m/s appliqué | **2,574 mm** | 0,192 mm | pas de progression validée |

Dans les quatre essais, `robot.stop` a été accusé, les mesures ont été obtenues du véritable serveur MuJoCo épinglé et la mémoire a consigné `no_progress_observed`, récompense `-0,5`, variation de préférence d'exploration **0 → −0,075**. Ces bases de CI sont **éphémères** ; la persistance entre essais est testée avec SQLite par les tests automatisés, mais les essais CI ne réutilisent pas la même base. Un échantillon de J2e-C/J2e-D mentionne `deadman` parmi les limitations, tout en rapportant une vitesse appliquée nominale lors d'autres échantillons.

**Conclusion : la chaîne décision → commande → stop → observation → mémoire fonctionne en simulation ; aucune marche effective n'est encore validée.** Le fait que `robotd` choisisse `walk` ne prouve pas la translation. Les prochains essais devront analyser les contacts des pieds, la cinématique et le comportement du modèle OEM, sans modifier ni affaiblir ses mécanismes de sécurité.


**Résultat de l'intégration technique :** [GitHub Actions #40176410817](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) a réussi avec **142 tests Python** et le statut explicite `WALK_TRANSLATION_ACCEPTANCE=NOT_MET`. Il atteste la bonne gestion des essais sans progression et non pas une marche fonctionnelle. `robot.stop` exige dorénavant `accepted=true` dans la réponse JSON-RPC.
