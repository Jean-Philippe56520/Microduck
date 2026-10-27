# Feuille de route — Microduck Companion

**B / F5 v2 — essai A/B sur Qwen 9B PC réalisé (27/10/2026) :** deux sorties structurées acceptées sur photographie de couchage pour animal : `simple=unknown/unknown/clear` (11,172 s), `balanced=other_object/photograph/clear` (11,953 s), classe plausible attendue `dog_bed`. Effet du prompt observé sur cette scène, **pas de classification exacte ni généralisation validée**. Étape suivante : protocole d'évaluation figé sur nouvelles photos annotées indépendamment ; compter erreurs de catégorie, abstentions, type photographie/dessin/écran et coût PC. Prévoir un audit séparé des libellés de taxonomie : des objets voulus, notamment `shoe`, ne figurent pas dans les 11 catégories actuelles, donc `other_object` ne suffit pas à mesurer toute la perception souhaitée. Ne pas changer les critères après lecture des réponses. [F5 v2](f5v2-qwen9b-pc-multimodal-pilot-2026-10-27.md).


**B / F5 v2 — diagnostic de vision avant exploration des usages (27/10/2026) :** deux images réelles/dessin auparavant produisaient surtout `unknown` ; photo d'un couchage pour animal testée sur PC (9,703 s) : `category=unknown` et `depiction=unknown`, insuffisant. Prochaine porte : autotest sans données privées pour distinguer le rouge du bleu avec le Qwen3.5 9B sur le même chemin JPEG/Ollama. `VERIFIER_VISION_KWIPI.cmd` génère 2 images temporaires **en RAM**, utilise le client F5 v2 existant, refuse réponse structurée incorrecte et ferme le serveur qu'il a ouvert. Test succès = seulement indice que les pixels atteignent le modèle, **pas reconnaissance d'objet**. Ensuite évaluer sur photos indépendamment annotées et contre un cas sans image / sans PC avant d'enrichir l'Advisor. [Détails](f5v2-qwen9b-pc-multimodal-pilot-2026-10-27.md).


**F5 v2 — essai réel du mode `simple` et auto-démarrage Windows (27/10/2026) :** image réellement choisie = capture d'écran d'Explorateur Windows (confirmée par l'opérateur) ; serveur Ollama temporaire, réponse du vrai Qwen 9B en 10,078 s, `unverified`, `unknown/unknown/clear`. Le protocole fonctionne, **pas de reconnaissance de photo d'objet** ; `depiction=screen` souhaité mais non obtenu. Étape suivante : petit protocole d'évaluation sur **photographies** d'objets inanimés variés (balle, chaussure, chaussette, chaise, objet partiellement visible et inconnu) avec vérités indépendantes et consentement. Aucune image privée versionnée, aucun effet sur les moteurs/mémoire du robot. [Détails](f5v2-qwen9b-pc-multimodal-pilot-2026-10-27.md).


**B / F5 v2 — reproductibilité Windows 27/10/2026 :** rendre `TESTER_KWIPI.cmd` autonome face à l'absence d'Ollama sur le port dédié `11435`, sans démarrer le modèle avant choix et consentement pour une image. Réutiliser `ollama serve`, l'installation Windows et le modèle `qwen3.5:9b` existants ; options GPU Vulkan/iGPU héritées, aucun changement permanent de service. Tests statiques et Python sur faux serveur, test syntaxique PowerShell dans la CI, test réel Windows et placement GPU encore requis. [Compte rendu](f5v2-qwen9b-pc-multimodal-pilot-2026-10-27.md).


**B / F5 v2 — simplification pour mesurer la vision Qwen 9B (27/10/2026) :** conserver `qwen3.5:9b` PC ; tester d'abord une sortie de perception a 4 champs via `--mode simple` et `TESTER_KWIPI.cmd`, puis evaluer photos autorisees, erreurs, rejets, incertitude, latences et RSS avant d'ajouter usages/relations/effets. Le schéma strict reste disponible comme reference mais pas requis pour les premiers essais. Aucun nouveau reseau neuronal, poids ni service embarque ; pas d'autonomie acquise. Code et 25 tests locaux sur fausses reponses ; CI complète et essais Qwen reel du mode simple a confirmer. [Protocole](f5v2-qwen9b-pc-multimodal-pilot-2026-10-27.md).


**F5 v2 - diagnostic Qwen 9B sur PC, 27/10/2026 :** ajout de motifs de refus fixes sans texte modele (`diagnostic_reason`) et contrainte explicite de l'UUID attendu dans le schema Ollama. Reutiliser F5-B, conserver tous les refus, aucun stockage media/souvenir, aucun moteur ni F5 v1 modifie. 18 tests locaux sur transport mock (pas Qwen reel) ; CI a verifier. Prochain test operateur : une requete autorisee et son code de rejet, puis evaluation sur nouvelles photos sans entrainement et sans affaiblissement des gardes. [Dossier](f5v2-qwen9b-pc-multimodal-pilot-2026-10-27.md).


**F5 v2 pilote Qwen 9B multimodal PC (27/10/2026, logiciel en PR) :** [nouveau pilote manuel](f5v2-qwen9b-pc-multimodal-pilot-2026-10-27.md) : préparation image contrôlée, transport localhost seulement et réponses JSON de catégories/usages/risques/observations non vérifiées, sans commande motrice. F5 v1 intact. Les tests mock HTTP n'établissent pas la qualité de Qwen ; les performances Ryzen AI, les photographies autorisées et l'intégration à la mémoire restent à tester. Étapes suivantes : essai réel 9B PC, bouclage mémoire et généralisation avec/sans PC, Cat-A2b puis audit robot.


**Cat-A2b — étape d'observation privée sur PC franchie ; benchmark représentatif non validé (27/10/2026, [compte rendu agrégé](cata2b-private-host-ort-exploratory-2026-10-27.md)) :** [issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78) **toujours ouverte**. Sur **29 JPEG réels** à hauteur basse déclarée **20–30 cm**, ONNX Runtime CPU Windows 11 a produit **66 propositions**, appariées **66/66** avec OpenCV DNN (même modèle YOLOX, même seuil 0,25), p50 **13,109 ms**, p95 **13,622 ms**, RSS maximal de processus **107 808 Kio** ; données privées hors GitHub. Un brouillon **non indépendant** de 50 boîtes annotées V3 donne **26 TP / 40 FP / 24 FN** et un AP50 macro *illustratif* ≈ **0,503**, non valide pour annoncer une reconnaissance fiable. **Prochain travail Cat-A2b :** revue humaine indépendante à l'aveugle, négatifs, droits, mesure instrumentée du centre optique, nouveaux lieux/séances et splits sans fuite avant score formel ; pas de portage robot/NPU sans audit. Les représentations TV doivent rester distinctes d'une présence physique ([#95](https://github.com/Jean-Philippe56520/Microduck/issues/95), idée seulement). Aucun modèle, déploiement, contrôle moteur ni apprentissage ajouté par ce rapport.

**Cat-A2c — traitement de 25 JPEG publics F3-D avec YOLOX inchangé (27/10/2026) :** [dossier de preuve](cata2c-positive-public-captions-2026-10-27.md). Cohorte exploratoire à légendes déclarées, 22 sujets positifs `cat/dog/chair/sports_ball` et trois scènes hors-catégorie possibles, jamais une base de boîte de vérité terrain. Aucune mesure de hauteur, aucune catégorie `person` positive. Réutilisation de F3-D/Cat-A/A2a, sans nouveau modèle ou moteur. Distinguer « proposition concordante » de « reconnaissance certifiée » et conserver Cat-A2b #78 ouvert. [Résultat réel en CI #40531455983](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40531455983) : 25 JPEG, concordances aux légendes chat **7/8**, chien **7/8**, chaise **1/4**, balle **0/2** ; médiane CPU hôte **23,238 ms**, maximum RSS Python **99 756 Kio**. Aucune mesure de précision/rappel ; les études CPU GitHub sont indépendantes du budget RK3566.

**Cat-A2b — essai exploratoire avec prises publiques d'un robot à hauteur annoncée ~12 cm (27/10/2026) :** [audit et protocole](cata2b-public-12cm-smoke-2026-10-27.md). Trois aperçus UMD PNG à SHA source épinglé, inférence YOLOX CPU hôte **vérifiée en [CI #40522854949](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40522854949) : 3 PNG, 0 proposition** sans vérité terrain (8 tests spécifiques verts, 16,453 ms médiane, 105 872 Kio de RSS Python), sans sous-échantillonnage mal déclaré ni transfert d'images. Aucun annotation indépendante `person/cat/dog/chair/sports_ball` ni preuve de hauteur individuelle ; le nombre de propositions ne mesure pas leur exactitude. Aucun déploiement, NPU, voix, animation/moteur ou bilan ressources robot ; suite : données basse hauteur à droits validés et annotations indépendantes pour [#78](https://github.com/Jean-Philippe56520/Microduck/issues/78).

**Cat-A2b — état de couverture du corpus à hauteur basse (27/10/2026 ; fixtures) :** même validateur de JPEG privés, ajout d'un compte rendu de présence des cinq catégories par split (boîtes partielles/entières, négatifs et diversité de séances/sites auto-déclarée). Signaler les classes absentes dans TEST sans inventer un score global représentatif. Aucun modèle, moteur ni mémoire ajouté dans **ce lot historique sur fixtures** ; aucune image basse réelle évaluée **à cette date**. [Protocole](cata2b-private-low-camera-protocol-2026-10-26.md) ; [issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78).

**EX4-C1 — garde-fou temporel des conséquences fictives (27/10/2026 ; [PR #90](https://github.com/Jean-Philippe56520/Microduck/pull/90) fusionnée après #89 et #88 ; [CI #40504225917 réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40504225917) : 1 376 tests, 19 ignorés) :** [rapport et contrat](ex4c1-mock-causal-preflight-2026-10-27.md). Correlation test-only d'une intention OEM fictive et d'événements scénarisés avec l'historique EX1/EX2, refus/retrait/desordre/événement concurrent, horloges distinctes et sortie sans cause certifiée. Zéro journalisation d'intention comme acte, récompense, nouvel écrivain M1-B, sous-module OEM modifié ou moteur parallèle. Validation PC/fixtures uniquement ; EX4-C2 nécessitera une identité d'action OEM de bout en bout, un capteur indépendant et un audit matériel. Cat-A2b #78 manque toujours de photographies privées basses.

**EX4-B — séparation des accusés OEM v44 et d'une preuve de conséquence (27/10/2026 ; [PR #89](https://github.com/Jean-Philippe56520/Microduck/pull/89) fusionnée après EX4-A #88, [CI #40498153294 réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40498153294)) :** [audit API, tests et refus](ex4b-oem-receipt-capability-2026-10-27.md). Un validateur de réponses robot.do/robot.look/robot.stop et notifications robot.move/head/state constate seulement une prise en charge IPC ou des états non liés à l'ordre ; les champs de sortie refusent toute autorisation physique, action terminée, causalité ou apprentissage. Révisions OEM #381/#414 ouvertes, aucun changement de firmware, pilote, boucle, RPC émis, SQLite, Qwen ni données privées. **EX4-C** : besoin d'une preuve d'action univoque fournie/vérifiée par l'OEM, puis tests robot en zone sûre ; Cat-A2b garde la priorité des vrais médias bas.

**EX4-A — première tranche de l'issue de conséquences [#80](https://github.com/Jean-Philippe56520/Microduck/issues/80) (27/10/2026 ; [PR #88](https://github.com/Jean-Philippe56520/Microduck/pull/88) fusionnée) :** [contrat](ex4a-execution-evidence-audit-2026-10-27.md). Filtre de provenance en lecture seule sur une seule `ExperienceMemory`, avec refus des faux reçus, contradictions, récompenses simulées et corrections retirées. `authorized=not_attested`, `verified_on_robot=false`, `causality_established=false` et `physical_learning_allowed=false` pour chaque verdict. La CI des tests hôte est réussie sur `main` ; pas de nouvel apprentissage causal, service, action motrice, Qwen ou pilote. EX4-B a recensé les accusés OEM v44 sans reçu authentifiable de fin d'action ; Cat-A2b manque de photos basses.

**X2-C — acceptation réelle des démons constructeur dans MuJoCo (27/10/2026 ; [PR #87](https://github.com/Jean-Philippe56520/Microduck/pull/87), [CI #40472442011 réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40472442011)) :** [rapport](x2c-mujoco-passive-acceptance-2026-10-27.md). P2b/X2-A/X2-B conservés ; 6 cycles cohérents sur deux processus, même SQLite, 5 références historiques vérifiées dont 1 traversant la session ; aucun acte moteur, Qwen, apprentissage causé ou impression de robot validé. `halt` et `idle` pour les 6 cycles. Les 8 tests négatifs X2-C sont verts dans la [suite Python #40472441954](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40472441954) : 1 260 tests, 19 ignorés. Mesures CPU, RSS, acquisition et décision **sur PC CI uniquement**. Suite : vraies captures basses Cat-A2b et source causale pour EX4, sans contrôleur concurrent ; audit RK3566 après réception du robot.

**X2-B — mémoire P2b de transitions énergétiques *simulées*, non motrices (27/10/2026 ; [PR #85 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/85), [CI finale #40470345439](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40470345439) réussie : 1 252 tests, 19 ignorés) :** [contrat et essais](x2b-simulator-passive-memory-2026-10-27.md). Une seule SQLite avec les lignes anciennes conservées, trois colonnes migrées, dernière lecture antérieure sur 60 s maximum, rejet des séquences et horloges réinitialisées, refus des interruptions et données inconnues. Les états `idle/rest/observe_status/abstain` sont des descriptions cognitives, pas des animations OEM ni des actes ; aucune récompense, Qwen ou nouveau capteur. Les modules P2b/X2-A sont réutilisés et seize tests X2-B ont réussi en CI finale, avec PR #85 fusionnée. MuJoCo X2-C distinct et robot physique toujours absent.

**X2-A — contrat de télémétrie MuJoCo en lecture seule (27/10/2026 ; [PR #84](https://github.com/Jean-Philippe56520/Microduck/pull/84), [CI hôte #40428500259](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40428500259) réussie : 1 236 tests, 19 ignorés) :** [audit et critères](x2a-simulated-observation-contract-2026-10-27.md). Pas de second pont ou pilote : `ReadOnlyUnixRpc` vérifie localement le rôle `robotd/tofd`, `SimulatorTelemetry.assess()` qualifie les échecs avec une source revendiquée `simulator_ipc_unverified`. Source absente, chute, retard, cadence dégradée ou incohérence → pas d'observation utilisable, **zéro droit moteur**. Les six cycles P2b sur démons MuJoCo sont antérieurs ; X2-A est vérifié par neuf tests supplémentaires en CI hôte, sans ajouter d'expérience réelle, d'apprentissage ni de reconnaissance. X2-B/C prévus [#79](https://github.com/Jean-Philippe56520/Microduck/issues/79).

**X1 — étape d'intégration hôte de la chaîne cognitive (27/10/2026 ; [PR #77 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/77), [CI finale #40425919775](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40425919775) réussie : 1 227 tests, 19 ignorés, zéro échec) :** [cahier de vérification et portes de sortie](kwipi-execution-acceptance-2026-10-27.md). Vérifier F1 → F2 → mémoire/journal EX1/EX2/EX3 → descriptions PD2 et abstention Qwen PD3 dans des scénarios factices. `feedback` historique est mis en quarantaine sans preuve d'exécution, et `choose()` ne persiste plus ses choix comme des expériences exécutées. **Pas de robot, de simulateur OEM fermé, d'audio de microphone, de caméra basse, ni de mesure RK3566.** Cat-A2b reste première priorité de perception réelle ; les étapes simulées et physiques ne doivent pas être annoncées comme livrées.

**PD3 — arbitrage de la curiosité et abstention Qwen (27/10/2026 ; [PR #76](https://github.com/Jean-Philippe56520/Microduck/pull/76), [CI hôte 1 221 tests, 19 ignorés, 0 échec](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40422474003)) :** [matrice et critères](pd3-semantic-pc-opportunity-2026-10-27.md). Un filtre pur consomme l'avis F5-A déjà produit, les descriptions P-A/B/PD2 et deux lectures fictives non privées. Les noms de comportement ne suffisent pas ; l'inconnu doit persister, les indicateurs STOP/repos prévalent, et toute demande demeure **non transmissible** faute d'indices visuels discriminants dans F5 actuel. Pas d'ajout de quotas, de worker, de SQLite, de flux audio/image, de moteur ou de Qwen exécuté. PD4 multimodal et Cat-A2b sont des phases distinctes.


**PD2 — continuité descriptive et prudente des 16 états (27/10/2026 ; [PR #75](https://github.com/Jean-Philippe56520/Microduck/pull/75), [CI hôte : 1 199 tests, 19 ignorés, 0 échec](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40420772999)) :** [matrice et critères](pd2-coherent-mock-behavior-continuity-2026-10-27.md). Après la décision F2/F4, petit adaptateur dans le cerveau existant : dix signaux explicitement synthétiques + quatre portraits P-A + deux indices P-C, seuils provisoires, courtes fenêtres de maintien, refus et corrections F4-A. Aucun état moteur historique disponible, aucune exécution, aucun Qwen, aucune voix/image, aucune nouvelle base ; humeur process-local non persistée. Cat-A2b prioritaire, PD3 ensuite.


**PD1 — catalogue non exécutable des seize comportements OEM (27/10/2026 ; [PR #74](https://github.com/Jean-Philippe56520/Microduck/pull/74), [CI hôte 1 176 tests, 19 ignorés, zéro échec](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40418679064)) :** [audit source, interface et tests](pd1-oem-expression-capabilities-2026-10-27.md). Dans P-A, `BehaviorExpressionCapability` inventorie 4 indices **partiels** déjà présents dans les sources constructeur (Chill/LookAround/Nap/Petted), douze états sans indice partiel confirmé, et **zéro compétence complète à 16 états dispatchable**. Liaison descriptive optionnelle P-C, aucune création d'ordonnanceur, geste, son, mémoire ou consultation Qwen. La preuve est un test logiciel sur fixtures, pas un essai robot. PD2 cohérence puis PD3 besoin d'information non moteur ; Cat-A2b prioritaire.


**PD0 — 16 états historiques et consultation Qwen parcimonieuse (27/10/2026 ; documentation seule) :** [plan par état et jalons PD1–PD7](pd0-behavior-states-selective-qwen-2026-10-27.md). Objectif : humeur descriptive cohérente + sélection F2 déjà existante → expression OEM uniquement si supportée ; candidats Qwen fondés sur l'inconnu/contradiction réelle, jamais sur le seul nom de l'état. Réutiliser F5-C quotas, F5-B repli, EX1/2/3 mémoire corrigible ; aucun accès multimodal ni état moteur nouveau. PD1/PD2/PD3 testables sur fixtures seulement ; PD4–PD7 conditionnés par perception et matériel. Cat-A2b reste prioritaire.


**EX3 — tendances d'attention fictives réversibles ([PR #72](https://github.com/Jean-Philippe56520/Microduck/pull/72), [CI hôte 1 159 tests, 19 ignorés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40415345335)) :** [code, tests, limitations](ex3-reversible-mock-attention-2026-10-26.md). Un `SELECT` EX1/EX2 déduit un biais d'attention F2 borné, optionnel, annulable par correction ; sessions distinctes requises, aucune récompense/causalité/acte physique. `kwipi_journal --trend` permet de consulter les statistiques sans autre service. Cat-A2b et validation physique restent inchangées.


**EX2 — Journal de Kwipi consultable à la demande ([PR #71](https://github.com/Jean-Philippe56520/Microduck/pull/71), [CI hôte 1 139 tests, 19 ignorés, zéro échec](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40413719554)) :** [contrat et tests](ex2-mock-effects-kwipi-journal-2026-10-26.md). Comparaison d'effets artificiels avant/après sur EX1 uniquement et interprétation conservatrice : changement observé en fixture ≠ preuve de cause. Lecteur JSONL/CSV ouvrant une SQLite existante en mode lecture seule ; aucun capteur, moteur, récompense ou télémétrie continue. Priorité Cat-A2b conservée, EX3 et robot physique non validés.


**EX1 — journal de cycle d'intention fictif ([PR #70](https://github.com/Jean-Philippe56520/Microduck/pull/70), [CI 1 111 tests, 19 ignorés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40410788233)) :** [contrat et limites](ex1-mock-experience-ledger-2026-10-26.md). Adaptateur F2 `PassiveIntent` → journal `proposed/mock_executed/refused/interrupted` dans la même `ExperienceMemory` SQLite, sans causalité ni récompense, sans commande ou conséquence réelle. EX2 reste prévu, Cat-A2b demeure prioritaire.


**EX0 — nouvelle orientation cognitive documentée, aucun code livré :** [plan d'apprentissage par l'expérience](kwipi-experiential-learning-plan-2026-10-26.md). Un événement doit être distingué d'une intention et d'une action confirmée ; une conséquence observée n'est pas automatiquement causée par la dernière action. EX1 contrat d'épisodes, EX2 attribution prudente, EX3 préférences réversibles sur fixtures, puis Qwen/affordances, gestes OEM et validation réelle sous conditions. **Cat-A2b reste la prochaine preuve de perception attendue**, aucun apprentissage sensorimoteur ou langage réel validé.


**Cat-A2b — vérification des captures vraiment basses, sans corpus personnel dans Git :** [protocole/limites](cata2b-private-low-camera-protocol-2026-10-26.md), [validateur local/évaluateur](../microduck_companion/cata2b_private_low.py), [tests sur JPEG fabriqués](../tests/test_cata2b_private_low.py). Le contrôleur vérifie les hauteurs du **centre optique déclarées** (100–300 mm, preuve photographique privée avec SHA contrôlé mais **pas de hauteur indépendamment certifiée**), droits/consentement, boîtes `full/partial`, vrais négatifs, séparations séance/site/scène, empreintes de JPEG et modèle YOLOX Cat-A2a identique sans réglage sur TEST. **Pas de prise basse réelle mesurée ni de taux de reconnaissance dans ce lot, pas de matériel ni RKNN.** Étape suivante : obtenir un corpus réel fiable et indépendamment annoté avant décision de modèle ; ne pas supprimer la catégorie `unknown`.


**Cat-A2a (lot de localisation, sans hypothèse d'angle bas) :** [méthode et matrice](cata2-coco-bbox-host-2026-10-26.md), [évaluateur de boîtes](../microduck_companion/cata2_bbox_eval.py), [tests](../tests/test_cata2_bbox_eval.py), [CI COCO](../.github/workflows/cat-a2-coco-bbox.yml). Réutilise Cat-A YOLOX Nano ONNX/CPU et ses poids vérifiés ; 24 photos réelles COCO2017 VAL à licence déclarée CC BY, IoU50/matching/AP50 partiel, aucun affinage sur test, pas de poids/media dans GitHub. **[CI réelle #40400991178](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40400991178) : 31 TP / 49 annotations, 9 FP et 18 FN, précision 77,5 %, rappel 63,3 %, AP50 macro 0,485555 ; balles/chaises défaillantes, RETESTER.** **Non réalisé :** captures véritablement basses/caméra à hauteur de Kwipi (~25 cm à confirmer), vues répétées indépendantes, classes `shoe/hand/foot`, portage RKNN/robot, capteurs/autorité motrice. La CI hôte ne peut pas lever ces portes. **Cat-A2b** = images basse hauteur horodatées + boîtes et droits vérifiés ; Cat-B suit seulement après résultat concluant.


**P-C — rattachement descriptif des réactions OEM à la personnalité :** [contrat et audit](kwipi-oem-expressions-pc-2026-10-26.md), [adaptateur P-C](../microduck_companion/oem_expression_hints.py). `PettingEvent::Start` → candidat historique `Petted` **déjà pris en charge par `robotd`**, `SoundEvent::Noise` → hypothèse `Startle` **non vérifiée**, `SoundEvent::Voice` → voix remarquée, **aucune transcription ni activation**. Les portraits P-A/P-B sont réutilisés, sans modifier leurs quatre états descriptifs, leur mémoire ni le rythme F2/F4. Tout est `mock`, aucune sortie physique ni consommation RK3566 mesurée. **P-C2 et réactions sur robot non codées ; Cat-A2 reste prioritaire.**


**P-B — habitudes et personnalité cohérente, étape expérimentale :** [contrat mémoire/émotion simulée](kwipi-personality-continuity-pb-2026-10-26.md), [test de continuité](../tests/test_personality_continuity.py). À la vue P-A ajoutent lecture seule de `BehavioralMemory` (résultats fictifs vérifiés), persistance après redémarrage via la même SQLite, correction/expiration, seuil de deux retours pour exposer une tendance, et biais F2 `inspect` limité et **opt-in**. Aucune mémoire du caractère distincte, aucun moteur ni émotion vécue, aucune preuve d'apprentissage physique ; la priorité Cat-A2 reste inchangée. **Vérification logicielle P-B réussie : 1 056 tests Python exécutés, 4 ignorés, zéro échec** ([CI GitHub Actions #40394372640](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40394372640)) ; aucune validation sur robot. Étape suivante P-C : sources réelles et garde-fous avant expressions OEM, puis P-D/M9 si fonctions livrées.


**P-A — personnalité évolutive, première tranche strictement descriptive :** [contrat/évaluation](kwipi-behavior-personality-16states-2026-10-26.md), [vue `BehaviorPortrait`](../microduck_companion/behavior_personality.py) et [tests ciblés](../tests/test_behavior_personality.py). Liste les seize comportements OEM historiques mais ne relie **que quatre états de description fictive** aux intentions F2/F4 déjà retenues, aux motivations et à la familiarité des catégories F1/F2 sur la **même SQLite**. Ni seconde machine d'états exécutrice, ni animation moteur, ni capteur physique, ni Qwen. Étapes futures : preuve de conséquences, cohérence multi-sessions, interface M9, puis validation robot. **Cat-A2 conserve sa priorité.**


**Cat-A, essai de catégories effectué sur PC (26/10/2026) :** [rapport](cata-category-detection-pilot-2026-10-26.md), [PR #63](https://github.com/Jean-Philippe56520/Microduck/pull/63). Détecteur YOLOX-Nano Apache-2.0 416 px, seuil 0,25 prédéfini. Cat/dog/unknown CC0 : **4/6 images TEST entières correctes** contre **3/6 recadrages inférieurs** ; 12 chaises ABO : **8/12 entières**, **0/12 recadrées**. Vision basse simulée par coupe d'image, **pas** capteur physique à 25 cm. **État RETESTER** : données réelles de proximité, personne et balle annotées, classes chaussures/parties non couvertes, localisation et vrais rejets à vérifier. Cat-B/C/D ne sont pas lancés ; l'identité d'instance reste suspendue.


**Nom officiel : Kwipi.** Détecteur hors ligne « Hé Kwipi ! » à concevoir et mesurer ultérieurement, sans toucher aux moteurs ni détourner Cat-A.

**Nouvel ordre de priorités validé (R2-C, 26/10/2026) :** [clôture de l'identification précise et plan catégorie-first](r2c-category-first-active-perception-2026-10-26.md). **Réalisé :** bilan R2-C sans recalibrage des scores, prototype de suggestions de recherche de parties d'objet uniquement sur fixtures, réutilisant F2. **À ouvrir ensuite par chantier indépendant :** Cat-A classifieur/détecteur de catégories sur PC et données caméra basse ; Cat-B épreuve de continuité visuelle par observations supplémentaires ; Cat-C mémoire catégorie/expérience **dans la même SQLite** ; Cat-D revue PC/Qwen facultative sans certifier les hypothèses ; simulation OEM puis mesures matérielles. **Identification individuelle/instance et ancien R2-D suspendus**, modèles M1-B/MobileNetV2 non déployés ; aucun mouvement, robot, capteur ou Qwen réel validé.

**Historique R2-B+2 — comparaison d'objets de même catégorie réellement évaluée (26/10/2026) :** [PR #61](https://github.com/Jean-Philippe56520/Microduck/pull/61), [rapport et mesures](r2b2-confusable-objects-2026-10-26.md), [CI visuelle #40380437787](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40380437787). **30 références de chaises `item_id` distinctes, 180 photos ABO** ; test 12 connues+6 inconnues, 48 vues familières+24 inconnues. M1-B **10/48** reconnues, **2/24** fausses acceptations d'inconnus ; MobileNetV2 **4/48** reconnues, 0 fausse acceptation. Seuils congelés sur validation, aucune photo conservée, ni identité physique assurée ni mesures robot. **M1-B et MobileNetV2 non retenus comme identité ; R2-C a depuis établi la priorité catégorie-first.**

**Historique R2-B+1 — essai sur enregistrements réels réalisé (échec de reconnaissance, non déploiement) :** [rapport complet](r2b1-real-audio-results-2026-10-26.md) et [CI #40377345110](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40377345110). Sur **10 requêtes connues TEST**, M1-B retrouve **0**, refuse 9, en attribue **1 à la mauvaise machine** ; **5/5 inconnues rejetées**. 34 extraits ToyADMOS IND de 6 machines physiques ; validation sur ToyCar, test sur ToyConveyor, seulement 2 connues/1 inconnue par type. Un enregistrement distinct ≠ nouvelle date/enceinte/micro attestée. Pas de modèle retenu, aucune modification de SQLite/OEM/robot. **R2-B+2 a ensuite été exécuté ; voir son statut en tête de roadmap.**

**Historique R2-B+1, préparation [PR #59](https://github.com/Jean-Philippe56520/Microduck/pull/59) :** [contrôles et tests sur fixtures](r2b1-independent-audio-2026-10-26.md). Cette première étape, sans données réelles, a été complétée par l'essai audio de la PR #60 ci-dessus. **Le code est validé sur PC, mais M1-B échoue comme reconnaissance fiable** ; ni le modèle ni la mémoire ne sont promus. Le bilan R2-C a depuis reformulé les prochaines étapes.

**C1–C3 (26/10/2026) — comparaison par chantier et sélection de références :** [audit initial de six dépôts](community-reuse-audit-2026-10-26.md), puis [registre de références avec décisions et statuts](community-reference-registry-2026-10-26.md). Veille OEM prioritaire : [PR #414 maploc v2/mapd](https://github.com/pollen-robotics/microduck/pull/414) (ouverte, non fusionnée) avant QuackNav, et [PR #381 cerveau autonome](https://github.com/pollen-robotics/microduck/pull/381) (document de proposition seulement). Quacksat, microduck-twin, GC-RENCAO et autres sont des **pistes ciblées**, sans aucune dépendance intégrée ni test robot. **Ordre historique ; R2-C a depuis suspendu R2-D d'identité au profit de catégories.**

**Plan R2 initial archivé (voir le nouvel ordre ci-dessus) :** [R2-B+1 audio réel → R2-B+2 visuel élargi → R2-C décision prudente → R2-D démonstration mémoire mono-écrivain](r2-follow-up-execution-plan-2026-10-26.md). La seule source des priorités reste [plan-action.md](plan-action.md). Chaque étape impose « réutiliser avant de créer », séparation stricte validation/test, gestion de `unknown`, aucune nouvelle autorité moteur ni activation automatique Qwen. R3/R4/R5 restent conditionnels.

**R2-B — comparaison sur images multi-angles réelles (test hôte, non robot) :** [rapport](r2b-independent-capture-evaluation-2026-10-26.md) et [CI #40322898625](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40322898625). Sources ABO CC BY 4.0 : **72 clichés de 12 séquences** ; test sur quatre séquences inscrites et deux inconnues : **15/16** vues reconnues avec les 1 000 scores de classe MobileNetV2 contre **10/16** M1-B, et **8/8** inconnues rejetées par les deux, sans changement de seuil après validation. Étude trop petite et trop contrôlée pour établir une capacité réelle du robot ; images corrélées dans la même séance, aucune source audio physiquement réenregistrée évaluée. Aucun modèle ni mécanisme d'identification d'instance retenu pour RK3566. Réutilisation M1-A/M1-B2 ; **pas d'écriture dans SQLite R2-A**.


**R2-A — décision de mémoire expérimentale :** [rapport de sélection](r2a-single-memory-selection-2026-10-26.md). M1-B est le **seul écrivain utilisé par le chemin R2-A** via une option strictement facultative, avec tests de non-écriture M1-A, réouverture sans éviction, détection des anciennes lignes et nouvelle validation avant chaque opération. M1-A reste la référence pure et historique. La sélection n'est pas une migration des anciennes lignes, un verrou global interprocessus ou une validation embarquée ; R2-B doit d'abord mesurer une vraie reconnaissance multi-vues/son indépendant et les confusions.


**M1-B2 — pilote comparatif hôte mesuré sur PR #51 :** [934 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40309129962) et [banc ONNX public terminé](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40309136430) ; sur 6 photos test, 6/6 rotations et recadrages de fichier retrouvés par le descripteur sémantique MobileNetV2, contre 0/6 M1-B, mais 1/15 rapprochements inter-fichiers suspects. Audio YAMNet : 2/2 décalages 16 ms, 0/2 avec bruit numérique ; M1-B : 1/2 et 2/2. Ce ne sont ni de vraies vues indépendantes du même objet ni une mesure de reconnaissance sonore généralisable. [Rapport M1-B2](m1b2-host-embeddings-2026-10-26.md). La sélection définitive d'un embedding et M1-C restent distincts.

**Audit OEM R0 (26 octobre 2026) :** [rapport de non-duplication](oem-reuse-audit-2026-10-26.md) + [inventaire](oem-reuse-inventory-2026-10-26.json), fondés sur les sous-modules épinglés. Les animations de repos, la perception audio de caresses/bruits, la détection **d'autres Microducks uniquement**, la caméra, le ToF et les contrôles moteurs existent dans les sources constructeur. Les **16 états historiques ne sont pas dans le daemon actuel** ; M9 est encore un jalon non porté. Conserver F2 comme expérimentation non motrice, renforcer la mémoire et la perception en **réutilisant les services OEM**. Suivant : R1 observation en lecture seule sur trames fictives, aucun mouvement ni robot physique.

**R1.5 — audit rétrospectif des développements avant R2 :** [rapport de conformité au protocole de réutilisation](r15-retrospective-reuse-audit-2026-10-26.md). Conclusion **nuancée** : prototypes mémoire/cognition/vision/son/PC justifiés comme bancs d'essai ; chevauchements des tables M1-A/M1-B et préférences F0/F2/F4 à unifier **avant tout portage**, pas par suppression aveugle. Une seule voie de signatures est à sélectionner pour R2 (M1-B candidate, M1-A témoin sans double écriture), scripts historiques MuJoCo exclus d'une future installation robot. État : revue statique, non un test matériel ni une refonte exécutée.

**R1 — contrat passif de métadonnées OEM sur fixtures :** [rapport technique](r1-oem-passive-fixture-contract-2026-10-26.md) et [règle permanente de non-duplication](development-reuse-protocol.md). Ne réimplémente ni acquisition, ni modèle, ni transport, ni mémoire : réutilise F3-C, F3-E, `sim_ipc` et F1/F2 pour examiner quatre formes d'observations fictives. Toutes les catégories restent **unknown**, sans source physique vérifiée, Qwen, commande moteur ou SQLite réelle. R2 devra obtenir plusieurs vues/enregistrements indépendants d'une même source et vérifier les fausses fusions.

Mise à jour : 2026-10-26. **La [nouvelle organisation opérationnelle F0–F8](plan-action.md) définit seule les priorités, critères de sortie et prochaines PR.** Ce fichier conserve l'historique technique des **six phases précédentes** et des diagnostics P0a–P0j. L'[ancien plan P0–P8](plan-action-historique-2026-10-25.md) est archivé. Une case cochée indique la preuve explicitement mentionnée (code, tests logiciels, MuJoCo), **jamais** une validation physique par défaut. Les mentions « priorité P0 » ou « prochaine étude » plus bas appartiennent à **l'historique**, pas au backlog actuel.

**Ordre actuel :** F1-A/B/C/D **fusionnées et testées sur fixtures fictives** ([PR #24 à #27](https://github.com/Jean-Philippe56520/Microduck/pull/27)) ; F2-A **fusionnée/testée** ([PR #28](https://github.com/Jean-Philippe56520/Microduck/pull/28)). **F2-B fusionnée/testée sur `main` via [PR #29](https://github.com/Jean-Philippe56520/Microduck/pull/29)** : [409 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40239148712), dont 31 nouveaux. Le même cerveau propose les intentions passives selon les **cinq motivations**, cadence 0,5 s, cooldown **3 s par catégorie**, `idle` possible, repos simulé avec hystérésis. **Aucun moteur, media réel, capteur OEM, récompense ni Qwen.** **F2-C fusionnée sur `main` via [PR #30](https://github.com/Jean-Philippe56520/Microduck/pull/30)** : catégories fictives et préférences corrigibles ; **F2-D [fusionnée sur `main` via PR #31](https://github.com/Jean-Philippe56520/Microduck/pull/31)** : quotas, pannes, mesures hôte ; **F3-A [fusionnée via PR #32](https://github.com/Jean-Philippe56520/Microduck/pull/32)** : contrôle des annotations et métriques fictives ; **F3-B [fusionnée via PR #33](https://github.com/Jean-Philippe56520/Microduck/pull/33)** : comparaison CPU sur 20 photos publiques CC0 déclarées (6 de test seulement) ; **F3-C [fusionnée via PR #34](https://github.com/Jean-Philippe56520/Microduck/pull/34)**, parseur OEM sur fixtures sans flux live ; **F3-D [fusionnée via PR #35](https://github.com/Jean-Philippe56520/Microduck/pull/35)** : 28 photos CC0 supplémentaires et mesures CPU/RAM hôte ; **F3-E [fusionnée via PR #36](https://github.com/Jean-Philippe56520/Microduck/pull/36)** : registre d'annotations déclaratif et précontrôle UYVY sur fixtures ; **F4-A [fusionnée via PR #37](https://github.com/Jean-Philippe56520/Microduck/pull/37)** : mémoire de catégories et conséquences fictives ; **F4-B [fusionnée via PR #38](https://github.com/Jean-Philippe56520/Microduck/pull/38)** : repères fictifs incertains, pas de navigation ; **F4-C [fusionnée via PR #39](https://github.com/Jean-Philippe56520/Microduck/pull/39)** : propositions sociales fictives et discrètes ; **F4-D [fusionnée via PR #40](https://github.com/Jean-Philippe56520/Microduck/pull/40)** : associations volontaires fictives et révocables → **F5-A [PR #41 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/41)** → **F5-B [PR #42 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/42)** → **F5-C [PR #43 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/43)** → **F5-D [PR #44 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/44)** → **F6-A [PR #45 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/45)** → **F6-B [PR #46 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/46)** → **F6-C [PR #47 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/47)** → **F6-D [PR #48 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/48)** → **M1-A [PR #49 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/49)**, mémoire visuelle+sonore compacte sur fixtures → **M1-B [PR #50 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/50)**, quotas/variantes + petit test CC0 → M1-C étude embeddings/PC facultatif → F7 validation physique après réception → F8 options. **Chantier L/P1a locomotion suspendu.** [Critères](plan-action.md).

**État courant :** P0j [fusionné dans `main` (PR #22)](https://github.com/Jean-Philippe56520/Microduck/pull/22), [replay sans moteurs de P0e](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655) réussi : **[269 tests Python sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946)**, 79 relevés `stand` et 127 `walk` à 50 Hz, **127/127 appuis bilatéraux**, charge gauche moyenne **52,03 % → 44,54 %**, mais aucun appui unipodal observé ; aucune cause ni démarche validées. P0i [fusionné dans `main` (PR #21)](https://github.com/Jean-Philippe56520/Microduck/pull/21) et testé sur [MuJoCo officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) : alpha **1,444 mm** vs VelStand **1,968 mm**, 24 commandes par configuration, deux arrêts confirmés et deux modèles choisis par `robotd` vérifiés ; [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915). Seuil indicatif 10 mm **non atteint**, aucune causalité ni gait validées, P1a bloqué. P0h fusionné ([PR #20](https://github.com/Jean-Philippe56520/Microduck/pull/20)) : [243 tests Python sur main](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219827102) et [audit MuJoCo OEM / ONNX réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997). Le simulateur force `alpha_walking`/`alpha_stand` tandis que `robotd` utilise normalement `velstand`. Trois modèles v8 conformes et comparés sur observations synthétiques, **cause de non-marche toujours inconnue**. P2b [fusionné dans `main` (PR #19)](https://github.com/Jean-Philippe56520/Microduck/pull/19), avec **[234 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216649169)** et [six cycles cognitifs passifs testés sous MuJoCo officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) (3 puis 6 lignes persistées en SQLite, six `halt`, zéro moteur). P2a avait démontré huit cycles fictifs persistés. P0g : modèles compilés 76/82/141 géométries, 2/10/69 éligibles aux masques du sol ; la cause de non-marche demeure inconnue. Dernier essai moteur P0e 2,295 mm ; P1a bloqué, aucun robot physique testé.

## M1-B — Groupes multi-vues, plafonds configurables et banc public CC0 ([PR #50](https://github.com/Jean-Philippe56520/Microduck/pull/50), fusionnée en logiciel)

- [x] Corrige M1-A : insertion de son après **256 images** conserve **256 empreintes totales**, pas 257. `MultiviewPatternMemory` crée des groupes de signatures sous **la même SQLite**, sans migration automatique, avec empreintes 64/16 octets et associations multi-vues **déclarées uniquement par fixtures**.
- [x] Budgets de **test** configurables : **1 024 groupes, 4 096 variantes au total, jusqu'à 6 par groupe, 256 Kio de BLOBs, 4 096 comparaisons** ; refus `search_budget_exhausted` plutôt qu'une décision sur corpus partiel ; rétention 180 jours, éviction et collisions ambiguës. Ni l'espace libre, ni RAM, ni la taille totale du fichier SQLite ne sont déduits de ces seuils.
- [x] [CI hôte : 925 tests Python + 4 Rust réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40303522130) ; parcours de **512 signatures synthétiques** (médiane hôte Python+SQLite **1,727 ms** et pic **4,876 ms**, sans RK3566).
- [x] [Banc public CC0 facultatif](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40302657292) : **6/6** luminosité, **0/6** rotation et **0/6** recadrage pour les photos ; **2/2** volume et **1/2** décalage 16 ms pour les sons. Aucun vrai « même objet sous autre angle » établi ; méthodes artisanales insuffisantes. [Rapport M1-B](m1b-multiview-memory-2026-10-26.md).
- [x] [PR #50 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/50) et [925 tests Python + 4 Rust réussis sur main](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40304109080). **Étape suivante : comparer de petits embeddings appris** et un corpus indépendant, en conservant les restrictions de confidentialité et de CPU/RAM. Aucune validation Microduck physique, Qwen, reconnaissance individuelle ni capteur réel.

## M1-A — Empreintes d'image et de son sans fichiers médias ([PR #49](https://github.com/Jean-Philippe56520/Microduck/pull/49), fusionnée en logiciel)

- [x] `compact_multimodal_memory.py` : extraction **réelle mais rudimentaire** de 64 caractéristiques sur 32×32 pixels gris synthétiques et 16 caractéristiques sur 8 kHz PCM synthétique. Ce ne sont **pas** des embeddings appris ni des classes `cat/dog/person` reconnues.
- [x] Une seule SQLite `ExperienceMemory` ; regroupement des rencontres comparables, refus des ambiguïtés et des catégories conflictuelles, **256 signatures au total / 180 jours**. Un champ de signature occupe 64 ou 16 octets ; la **taille du fichier SQLite** (index, pages, WAL, autres tables) n'est **pas** limitée à ce volume.
- [x] Refus des signatures étiquetées `person` / `speech` sur fixtures (un média inconnu n'est **pas** dépersonnalisé automatiquement) ; aucune voix enregistrée, photo conservée, identifiant réel, commande ou consultation réseau.
- [x] Une nouveauté intéressante peut seulement **suggérer** une consultation PC, avec opt-in déclaré ; pas de transfert multimodal ni d'appel au vrai Ollama. [898 tests Python, 4 Rust et démonstration sur deux processus réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40297726482) : 2 lignes SQLite, 10 rencontres par ligne, 80 octets de champs d'empreintes, 0 média brut. [Rapport M1-A](m1a-compact-multimodal-memory-2026-10-26.md).
- [ ] Revue et fusion. La capacité de reconnaître **un vrai objet ou un vrai son** malgré angle, lumière, distance, bruit, réverbération n'est **pas validée** ; aucun modèle, caméra, microphone, PC réel ni mesure RK3566.

## F6-D — Audit matériel préparatoire, étapes stationnaires et critères d'arrêt ([PR #48](https://github.com/Jean-Philippe56520/Microduck/pull/48), fusionnée en logiciel)

- [x] `scripts/resource-audit.sh` révisé : `--plan` **sans aucune lecture machine** ; l'accès ponctuel au relevé de repos exige une déclaration explicite d'opérateur sur **ARM64 avec entrée device-tree RK3566**. La vision stationnaire exige aussi une **déclaration de revue des données de repos** et une activation des fonctions OEM **déjà effectuée indépendamment**.
- [x] **Mouvement refusé sans exception** (`--phase movement`), pas de service `systemd` démarré/arrêté, aucune vidéo/voix, aucun socket OEM ni ordre moteur. Un drapeau opérateur **ne constitue pas une authentification**.
- [x] Rapport réduit : RAM disponible, RSS/CPU des processus OEM, état `systemd`, températures, fréquences, `df` et présence exacte du montage `/var/lib/robot`. `df` seul n'atteste pas la persistance. La cadence moteur 50 Hz, les latences des capteurs, la batterie et la thermie dynamique sont indiquées **non mesurées**.
- [x] `hardware_audit_policy.py` : checklist statique à catégories de risque strictes ; même avec toutes les déclarations favorables, elle **ne peut** confirmer ni de capteur, ni un robot physique, ni un mouvement. [878 tests Python, démonstration hors réseau et tests de refus shell réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40289135442). [Rapport F6-D](f6d-hardware-audit-protocol-2026-10-26.md).
- [x] [PR #48 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/48) après revue et CI complète. L'audit réel RK3566 reste **impossible tant que le robot n'est pas disponible** ; aucun seuil thermique/RAM/énergie fiable sans mesures constructeur et relevés supervisés.

## F6-C — Garde optionnel de ressources et quotas glissants hors PC ([PR #47](https://github.com/Jean-Philippe56520/Microduck/pull/47), fusionnée en logiciel)

- [x] `OfflineResourceGate` complète le **superviseur F2-D existant** : admission des cycles avant lecture, quota d'événements avant cognition et SQLite, un seul cycle local en cours, refus `idle`, trame entière rejetée sans file d'attente ni rejeu.
- [x] Seuils de test **non calibrés pour le robot** : 0,5 s entre admissions, 8 cycles/10 s, 32 événements/10 s ; pause 5 s après dépassement de délai ou CPU configuré, verrouillage en cas de RSS hors plafond configuré ou d'horloge invalide. Les seuils CPU et RSS sont **désactivés par défaut** et n'agissent qu'après la mesure du processus hôte.
- [x] [CI F6-C : 861 tests Python réussis et démonstration sur six sollicitations fictives](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40257113819) ; trois acceptées, trois refusées, trois observations fictives conservées. Temps p50 hôte 0,196 ms, p95 1,887 ms sur seulement six rapports, RSS du processus hôte 18 324 Kio — **aucune extrapolation RK3566**. [Rapport F6-C](f6c-offline-resource-envelope-2026-10-26.md).
- [x] [PR #47 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/47) après [861 tests Python et démonstration F6-C réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40257453473). Aucune mesure matérielle, ordonnanceur temps réel, consommation batterie ou capteur réel validé. F6-D reste la préparation de l'audit physique.

## F6-B — Étude Python/Rust de la seule fonction de scoring ([PR #46](https://github.com/Jean-Philippe56520/Microduck/pull/46), fusionnée en logiciel)

- [x] Sous-ensemble isolé et **non exécutable comme cerveau autonome** : `PassiveRhythm._score` (trois intentions passives, cinq motivations) reproduit dans `experiments/f6b/passive_score.rs`, sans Cargo externe, action, SQLite, capteur, installation systemd ni réseau.
- [x] `f6b_score_probe.py` compare **la fonction Python originale** et Rust sur **1 500 cas fictifs** (écart absolu maximal **0,0**, tolérance **1e-12**) ; `tests/test_f6b_score_probe.py` teste les vecteurs invalides, les actions interdites et les données malformées ; tests `rustc --test` indépendants.
- [x] [841 tests Python et 4 tests Rust réussis, banc hôte 120 000 scores](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40256023791). Deux mesures internes hôte : Python **38,031 puis 32,587 ms**, Rust minimal **3,503 puis 2,060 ms** ; RSS du **processus entier** ~**17 068 Kio Python** contre **2 132 Kio Rust minimal**. Ces charges n'ont **pas le même périmètre applicatif**, donc aucun gain embarqué n'est prouvé. [Rapport F6-B](f6b-python-rust-score-study-2026-10-26.md).
- [x] **Décision prudente : conserver Python** ; aucune intégration du prototype Rust dans le cerveau avant mesures réelles des ressources et de la cadence moteur du robot.
- [x] [PR #46 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/46) après deux CI vertes et [841 tests Python + 4 Rust sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40256318076). Aucun Rust embarqué, aucune RAM/CPU/thermie RK3566 ni batterie mesurés ; les performances Qwen 4B/9B sur PC restent inconnues.

## F6-A — Préparation OEM et autonomie sans PC ([PR #45](https://github.com/Jean-Philippe56520/Microduck/pull/45), fusionnée en logiciel)

- [x] Inventaire **strictement statique** des trois sockets/lectures documentées dans la révision constructeur épinglée : `robotd` (health/state), `mediad` (hello seulement implémenté), `tofd` (stream documenté), sans établissement d'une connexion, déplacement ou perception authentifiée.
- [x] `embedded_readiness.py` : registre des fonctions locales sur **fixtures uniquement**, séparation de l'option PC, inspection **déclarative** des familles Zero 3W/Seeed beta, et étude de l'unité `var-lib-robot.mount` de Yocto.
- [x] Un `/var/lib/robot` existant **ne prouve pas** un montage persisté. Le parseur reçoit des chaînes `mountinfo` *fictives*, refuse montage absent/mauvais device/ro/ambigü ; même favorable, le résultat est un **candidat** et la SQLite choisie reste `:memory:`. Aucun dossier, service ou BD physique créé.
- [x] Tests sur données fictives et démonstration `f6a_preflight_demo` ajoutée à la CI. [Rapport F6-A](f6a-embedded-readiness-2026-10-26.md).
- [x] [830 tests Python, compilation et démonstration F6-A hors réseau réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40254981871) ; [PR #45 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/45) après revue. **Aucune mémoire libre, eMMC libre, RAM/CPU/thermie, authentification d'un vrai service, installation systemd, robot physique ni Qwen sur PC mesuré.**

## F5-D — Résilience adversariale du PC optionnel ([PR #44](https://github.com/Jean-Philippe56520/Microduck/pull/44), fusionnée en logiciel)

- [x] Tests avec **réponses PC trompeuses fictives** : commandes, identité et sol prétendument sûrs, faux `dog`, requête mal corrélée/rejouée, clé JSON dupliquée, texte injonctif, octets malformés ; repli vers la **même intention locale**, zéro moteur, son ou expérience ajoutée.
- [x] Serveur HTTP hostile **sur loopback uniquement** : corps envoyé octet par octet, réponses sans `Content-Length` ou `chunked`. `OllamaLocalClient` impose une taille non streaming bornée et une **échéance totale du corps de réponse** ; aucun contrôle de temps réel sur les en-têtes malveillants n'est revendiqué.
- [x] `SelectivePCBridge` recontrôle identité originale de la requête/intention, catégorie `unknown` à confiance 0, temps de réception et expiration ; le worker fermé ne peut plus laisser un faux cycle en attente.
- [x] [808 tests Python, compilation et scénario `f5d_adversarial_demo` réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40253911518), [PR #44 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/44) après revue. [Rapport F5-D](f5d-adversarial-pc-contract-2026-10-26.md).
- [x] CI sur dernier code et revue conformes ; **aucun véritable Qwen/Ollama, PC authentifié, modèle multimodal, capteur ou robot physique testé**. L'interopérabilité `Content-Length` avec un vrai Ollama, la lenteur d'en-têtes, le RSS et la consommation sur PC restent à vérifier.

## F5-C — Politique de consultation facultative et parcimonieuse ([PR #43](https://github.com/Jean-Philippe56520/Microduck/pull/43), fusionnée en logiciel)

- [x] `SelectivePCPolicy` réserve les consultations uniquement **sur autorisation explicite** `pc_opt_in=True`, et seulement pour une requête F5-A fictive `inspect` sur une classe `unknown/conflict`. Ce n'est ni une nouveauté réelle démontrée ni une identité individuelle. Intention F2-B déjà choisie **avant** toute décision de consulter.
- [x] Quotas atomiques **dans la même SQLite `ExperienceMemory`** : 60 s par tentative, **2/10 min**, **8/24 h**, un seul appel en attente même après redémarrage ; seuils prudents non calibrés. Deux pannes consécutives ⇒ circuit ouvert pendant **300 s** ; reprise contrôlée de toute requête fictive abandonnée depuis plus de **3 s** ; retour local après erreur/horloge incohérente.
- [x] `SelectivePCBridge` réutilise le worker HTTP non bloquant F5-B : consentement et réservation **avant** la soumission, `poll()` non bloquant ; erreur de persistance ou de réseau ⇒ annotation `pc_unavailable` sans écriture d'observation ni action physique.
- [x] Historique minimal : **empreinte SHA-256 d'un nonce aléatoire**, date, état et origine `unknown/conflict` ; aucune photo, voix, personne, identifiant de suivi, invite Qwen ou résultat contenu. Tests SQLite entre connexions indépendantes, verrouillage, anti-rejeu, quotas, circuit, panne de PC fictive, compteurs anonymes et travailleur simulé. [798 tests Python réussis en CI initiale](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40252645890), plus démonstration en deux processus frais.
- [x] [798 tests Python réussis, compilation et deux sessions SQLite sur processus frais](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40252645890), [PR #43 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/43) après revue. Aucun **vrai Ollama/Qwen 4B/9B**, vrai LAN sécurisé, capteur, moteur ou robot testé ; cette validation sur PC et RK3566 reste distincte. [Rapport F5-C](f5c-sparse-consultations-2026-10-26.md).

## F5-B — Client HTTP Ollama optionnel et banc PC ([PR #42](https://github.com/Jean-Philippe56520/Microduck/pull/42), fusionnée en logiciel)

- [x] `ollama_local_client.py` : POST `/api/chat` sur adresse IP explicite, **127.0.0.1 par défaut**, sans DNS, redirections, proxies ou cloud. IPv4 de LAN privé uniquement sur opt-in **de laboratoire non chiffré** ; recommande un tunnel authentifié si déployé. Limites d'enveloppe et de délai, modèle `qwen3.5:4b` ou `qwen3.5:9b`, JSON structurel et parseur strict F5-A.
- [x] `OptionalOllamaWorker` : une consultation au maximum, `poll` non bloquant, résultat périmé écarté et **intention cognitive locale inchangée**. Aucun moteur, haut-parleur, perception certifiée, identité ou écriture d'expérience ; même une classification chien/chat est refusée par F5-B puisque **zéro image** est fourni.
- [x] Tests HTTP locaux par **serveur simulé**, refus des sorties dangereuses et cas dégradés, `f5b_transport_demo` sur loopback ; banc `f5b_benchmark` **dry run par défaut** et exécution réelle uniquement sous `--run-live`.
- [ ] Les **mesures réelles sur le PC** (4B puis 9B, latence, conformité, RSS/CPU et consommation énergétique si instrumentée) restent à réaliser ; aucun Ollama/Qwen réel n'est exécuté par notre CI. Une réponse réseau réelle ne prouve aucune qualité de vision sur des photos et une bibliothèque de modèles présente ne garantit pas l'accélération.
- [x] [PR #42](https://github.com/Jean-Philippe56520/Microduck/pull/42) fusionnée après revue logicielle : [781 tests Python, compilation et deux commandes F5-B réussies en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40251807307). **Aucune performance Qwen réelle mesurée : cette validation PC reste ouverte.** [Rapport F5-B](f5b-ollama-local-transport-2026-10-26.md). **F5-C** apportera déclenchement parcimonieux, quotas et politique de déconnexion.

## F5-A — Hypothèses facultatives PC/Qwen, contrat hors réseau ([PR #41](https://github.com/Jean-Philippe56520/Microduck/pull/41), fusionnée)

- [x] Réutilise **AutonomyBrain** F2-B et la même mémoire SQLite : l'intention passive est décidée localement **avant** toute possibilité de requête à un PC. Aucun second cerveau et aucune commande `robotd`.
- [x] `pc_hypothesis_contract.py` construit seulement des requêtes de catégories anonymes **sur fixtures F1-B** ; exclut personnes, sons sensibles, track ID, noms, images, paroles, ordres et certificats de sécurité. Réponse de schéma strict, au plus 4 096 octets / 4 hypothèses, corrélation par requête, source non authentifiée, délai logique local de 2 s et rejet des entrées anormales.
- [x] L'annotation `pc_qwen_unverified` reste distincte des observations et préférences. Sans PC ou avec réponse rejetée, l'intention locale reste inchangée ; ni attribution d'identité ni commande audio/moteur, aucune écriture de résultat en SQLite.
- [x] **757 tests Python réussis en CI** (dont 34 nouveaux F5-A), compilation et démonstration `f5a_contract_demo` réussies : [exécution validée](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40250745954). **[PR #41](https://github.com/Jean-Philippe56520/Microduck/pull/41) fusionnée après revue**. Aucun Qwen/Ollama, transport LAN ou matériel exécuté ; ces essais relèvent de F5-B/F5-C. [Rapport F5-A](f5a-pc-hypotheses-2026-10-26.md).

## F4-D — Contrat d'association volontaire et révocable ([PR #40](https://github.com/Jean-Philippe56520/Microduck/pull/40), fusionnée)

- [x] `revocable_mock_identity.py` : **aucune biométrie ni nom privé**. Seul un jeton *fictif de fixture* de 32 octets présenté explicitement peut être associé à une classe générique `pet_cat`/`pet_dog`/`child`/`adult`, avec référence opaque et empreinte **HMAC-SHA256** ; jeton brut et clé non stockés par le module. La SQLite `ExperienceMemory` reste unique.
- [x] Consentement/supervision/confidentialité déclarés **et non authentifiés**, tous désactivés par défaut ; pour `child`, approbation parentale et assentiment déclarés exigés **à l'inscription et à chaque présentation**. Le résultat demeure `real_identity_verified=False` et `physical_actions_authorized=False`, sans moteur, son ni perception OEM.
- [x] **24 associations max**, durée 7 jours par défaut et 30 jours au plus, présentation de 2 s maximum, séquences anti-rejeu, séparation par clé HMAC, révocation ciblée par référence + jeton et purge générale. Les suppressions SQL n'assurent pas l'effacement forensique des sauvegardes.
- [x] [723 tests Python, dont 34 F4-D](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40249168929), compilation et démonstration en deux processus : inscription volontaire fictive, restitution sous même clé, révocation et résultat `unknown`. [Rapport F4-D](f4d-revocable-optin-contract-2026-10-26.md).
- [x] **[PR #40](https://github.com/Jean-Philippe56520/Microduck/pull/40) fusionnée après revue et CI verte**. Avant toute identité réelle : matériel de présentation volontaire, contrôle parental vérifiable, gestion privée des clés, suppression des sauvegardes et mesures du robot restent à développer et valider.
- [x] **F5-A fusionnée via [PR #41](https://github.com/Jean-Philippe56520/Microduck/pull/41)** : contrat hors réseau, réponses strictement non vérifiées, [757 tests Python et démonstration réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40250745954).

## F4-C — Interactions sociales discrètes et non exécutées ([PR #39](https://github.com/Jean-Philippe56520/Microduck/pull/39), fusionnée)

- [x] `MockSocialComposer` appelle **le même cerveau F2-B** et le journal F1-C. Pas de second contrôleur ou LLM, pas de position du regard, ni d'actuateur. Sorties `silence` (défaut), `rest` (énergie motivationnelle fictive), `glance` (250 ms annoncées), `play_cue` (300 ms) ou `chirp` (180 ms), **toutes non exécutables**.
- [x] **Opt-in, supervision, revue de confidentialité déclarés**, et opt-in **audio séparé**. Aucun élément ne prouve un vrai consentement ; les objets et sons sont seulement des étiquettes de fixtures, pas des individus authentifiés. Signaux sensibles (`person`, `speech`, `keyword_stop`, `unknown`, noms libres), ambiguïtés, sources non fiables et mode calme ⇒ silence.
- [x] Cooldowns SQLite existante : **10 s global**, **60 s même proposition**, au plus **2 propositions audio par 10 min**, 7 jours et 128 entrées maximum de *métadonnées génériques*. Aucune photo, voix, identité, piste ou action réelle enregistrée. Les seuils ne sont pas calibrés sur du matériel.
- [x] [689 tests Python réussis, dont 27 nouveaux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248330199), compilation et simulation dans **deux processus** confirmant le silence après redémarrage. [Rapport F4-C](f4c-social-cue-contract-2026-10-26.md).
- [x] [PR #39 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/39) après [689 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248575737). F4-D fusionnée via PR #40 : contrats volontaires fictifs de jetons et révocation ; aucune identité réelle ou commande moteur.

## F4-B — Repères fictifs incertains ([PR #38](https://github.com/Jean-Philippe56520/Microduck/pull/38), fusionnée)

- [x] `uncertain_spatial_memory.py` : table de la **SQLite existante** contenant **5 catégories génériques et 2 cadres inventés** ; positions dans ±10 m et rayons d'erreur déclarés, jamais mesurés par un capteur. Source `mock_spatial_fixture`, pas de personne, GPS, carte ni localisation du robot.
- [x] Ingestion : horodatage monotone ≤1 s et mural ≤2 s, séquences croissantes idempotentes, rayon 0,05–2 m, confiance plancher **0,70 non calibré**. Contradictions, confiance insuffisante, ou rayon trop large ⇒ **pas de position consolidée**. Pas de fusion entre cadres ni amélioration de précision inventée.
- [x] Correction/retrait de la preuve, expiration **14 jours**, au plus **256 lignes** et **50 IDs** par liste. Sorties exclusivement historiques, jamais `floor_clearance_verified` ni `navigation_authorized` ; aucune commande motrice.
- [x] [662 tests Python, dont 27 F4-B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40247354468) avec compilation et démonstration SQLite en deux processus. Le cerveau retourne `halt` lorsque les capteurs de sécurité manquent malgré un repère fictif à confiance 1. [Rapport F4-B](f4b-uncertain-spatial-memory-2026-10-26.md).
- [x] [PR #38 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/38) après [662 tests Python, compilation et démonstration SQLite](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40247570297). **F4-C en PR #39** sur propositions sociales sans exécution. Robot, thermie, RAM, odométrie et navigation non testés.

## F4-A — Mémoires sémantique et comportementale ([PR #37](https://github.com/Jean-Philippe56520/Microduck/pull/37), fusionnée)

- [x] Mêmes tables SQLite `ExperienceMemory` que F1-C/F2-C/P2a : uniquement des **catégories historiques fictives** dont la preuve source reste active ; les noms/IDs privés et les suivis d'objets ne sont jamais copiés. Aucune perception live ni vérification d'individu.
- [x] Hypothèses `texture`/`movement`/`affordance` **explicitement fictives**, à vocabulaire borné, non confirmées et séparées de toute observation. Le scénario ne lance ni Qwen ni analyse payante.
- [x] Mémoire comportementale : seuls les **suivis P2a explicites fictifs** d'une inspection peuvent donner `positive`/`negative`, biais descriptif **±0,12 maximal**, pas de droit actionneur. Rétractions, expiration 14 jours, quotas et suppression des données sources invalidées.
- [x] [635 tests Python réussis, 37 nouveaux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40246670514) et démonstration avec deux processus sur la même base SQLite. [Rapport F4-A](f4a-semantic-behavior-memory-2026-10-26.md).
- [x] **[PR #37 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/37)** après [635 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40246859987). F4-B en PR #38 : repères incertains sur fixtures uniquement. Robot physique et ressources embarquées toujours non testés.

## F3-E — [PR #36 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/36) : 48 images sans revue humaine indépendante ; contrat UYVY sur fixtures ; aucun capteur réel.

## F3-D — Évaluation élargie / ressources de l'hôte ([PR #35](https://github.com/Jean-Philippe56520/Microduck/pull/35), fusionnée)

- [x] 28 **nouveaux JPEG réels publics déclarés CC0 1.0**, auteurs et fichiers distincts des 20 sources F3-B. Séparation : **8 chats, 8 chiens, 12 hors domaine** (chaises/fleurs/oiseaux/balles). Provenance et annotations fondées sur les déclarations publiques, **non vérifiées juridiquement ou contre-annotées indépendamment**. [Catalogue et rapport](f3d-open-set-resource-benchmark-2026-10-26.md).
- [x] Évaluation avec **MobileNetV2 ImageNet ONNX CPU, seuil 0,7059010988271212 figé sur validation F3-B**, aucun ajustement utilisant les 28 nouvelles photos. [Exécution réelle F3-D](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671367) : **20/28 exactes**, dont **3/8 chats** et **5/8 chiens** ; **12/12 hors catégorie** rejetées, 2 chats confondus avec des chiens. Le rappel animal est **8/16 = 50 %**, insuffisant pour une reconnaissance fiable.
- [x] Mesures **Linux GitHub Actions, pas Rockchip** : inférence CPU médiane **9,036 ms/image**, p95 **9,240 ms**, pic RSS **108 148 Kio de tout le processus**, incluant runtime/décodage/bibliothèques. Ces nombres **ne sont pas** un budget mémoire utilisable sur le robot. Intervalles Wilson descriptifs avec échantillons non aléatoires ; 0/12 faux positifs hors catégorie **ne garantit pas un taux nul**.
- [x] **19 nouveaux tests hors réseau**, [570 tests Python validés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671272), et [F3-B sans régression](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671290).
- [x] [PR #35 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/35). F3-E [fusionnée via PR #36](https://github.com/Jean-Philippe56520/Microduck/pull/36), mais sans revue humaine indépendante ni caméra réelle. Aucune reconnaissance individuelle ni sécurité de navigation acquise.

## F3-C — Contrat de notifications constructeur et faux sons ([PR #34](https://github.com/Jean-Philippe56520/Microduck/pull/34), fusionnée)

- [x] Revue de la **révision constructeur épinglée** : `media.video` (dimensions, rotation, horloges, intrinsics) et `media.detections` (boîtes d'**autres Microducks** uniquement) sont des notifications **WebRTC** ; le socket local `/run/mediad/media.sock` accepte seulement `hello` et `media.frame` (pixels bruts), jamais ces notifications. Aucun abonnement WebRTC, aucun pixel reçu dans F3-C.
- [x] Parseur `passive_media_router.py` strict, **fixturé et non authentifié**, limitant taille, nombres, géométrie, score brut (qui peut être supérieur à 1), commandes et champs inventés ; aucune boîte complète conservée, `category=unknown`, moteur interdit.
- [x] Routeur de **faux signaux sonores** `MockAudioCueRouter` : caresses, ambiance, faux candidats `Microduck`/`stop`/`viens`, aucun modèle de mots-clés ni microphone réel. Le OEM `pet-detect` détecte les **caresses**, pas les animaux. `stop` fictif ne constitue pas un arrêt de sécurité.
- [x] [551 tests Python sur branche, 31 nouveaux F3-C](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40243859433), démonstration sans réseau, caméra, micro ni moteur. [Rapport et références OEM](f3c-oem-media-notifications-2026-10-26.md).
- [x] **[PR #34 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/34)** après [551 tests Python et démonstration passifs réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244104644). **F3-D engagée en PR #35**, toujours sans capteur OEM réel.

## F3-B — Ligne de base visuelle sur photos publiques ([PR #33](https://github.com/Jean-Philippe56520/Microduck/pull/33), fusionnée)

- [x] Catalogue de **20 JPEG réels** provenant de pages Wikimedia Commons publiquement déclarées **CC0 1.0**, 20 auteurs crédités distincts : 8 `train`, 6 `validation`, 6 `test` (deux chats, deux chiens et deux hors catégorie sur le test). Sources et droits déclarés vérifiés dans le catalogue ; aucune garantie cryptographique d'authenticité des droits, ni revue indépendante de toutes les étiquettes. **Aucune image ou empreinte de photo privée publiée.**
- [x] Banc CPU **kNN à caractéristiques RVB** sur photos : 2/6 prédictions exactes en test (seuls deux `unknown`), 0/4 animaux reconnus, couverture 0/6 — échec observé, sans embellir les résultats.
- [x] Comparaison avec le modèle préentraîné **MobileNetV2 ImageNet ONNX (Apache-2.0)**, poids téléchargés temporairement et SHA256 contrôlé : sur six photos de test **5/6 exactes** (deux chats, un chien, deux inconnus), un chien classé `unknown` ; couverture 3/6. Seuil choisi **sur validation uniquement**. [Exécution réelle CPU](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40242876466). **Ce n'est pas une précision de reconnaissance généralisable**, ni un benchmark RK3566/NPU.
- [x] Tests hors réseau des sources, classements, refus, droits déclarés, seuils et limites. Workflow d'images réelles distinct, sans médias versés au dépôt. [Rapport détaillé et pages sources](f3b-real-cc0-photo-baseline-2026-10-25.md).
- [x] **[PR #33 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/33)** après [520 tests Python et banc photo réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40243269591). F3-C fusionnée via PR #34, toujours sur les seules formes de notifications et signaux fictifs ; ni autres catégories ni locomotion acquises.

## F3-A — Protocole d'annotations et évaluation contrôlée ([PR #32](https://github.com/Jean-Philippe56520/Microduck/pull/32), fusionnée)

- [x] Contrat JSON v1 **sans image**, identifiants opaques, provenance et droits déclarés ; classes F1 `dog`/`cat`/`person`/`ball`/`toy`/`microduck`/`other_object`/`unknown`. **Aucune identité individuelle**, aucune image ou voix personnelle, aucune autorisation d'usage présumée vérifiée par le code.
- [x] Partitionnement `train/validation/test` avec rejets de groupes communs entre splits, IDs/empreintes exactes dupliqués, absence de classe `unknown` au test, métadonnées personnelles/chemins et JSON ambigus. Vérification des quasi-doublons visuels **non automatisée**.
- [x] Évaluateur de **prédictions fictives uniquement** : matrice de confusion, P/R/F1 par classe connue, macro-F1, couverture, abstention et rappel `unknown`. [482 tests Python sur branche, 32 nouveaux F3-A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40241592517). Démo : **28 métadonnées inventées, aucun pixel, aucune performance de modèle revendiquée.**
- [x] [PR #32 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/32). [Rapport et protocole F3-A](f3a-visual-dataset-protocol-2026-10-25.md). **F3-B est fusionnée via PR #33** avec première référence mesurée sur photographies publiques déclarées CC0.

## F2-D — Robustesse et budgets sur fixtures (PR #31, fusionnée sur `main`)

- [x] `PassiveCycleSupervisor` réutilise F1/F2 sur **la même SQLite**, vérifie la source fictive et limite les cycles, le nombre d'événements et les durées (budgets **souples**, pas watchdog temps réel). Aucune commande moteur, média ou Qwen.
- [x] Pannes et reprises : socket indisponible, retard, source non conforme, lecture répétée, SQLite fermée, échec partiel F1-C/F2-C, quota dépassé et redémarrage, sans transformer un souvenir historique en entrée fraîche.
- [x] [450 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240749032), **25 nouveaux tests F2-D**, CI `compileall` et deux **processus Python distincts** sur socket Unix fictif et SQLite partagée : 6+4 cycles, 5+3 observations, deux déconnexions, zéro moteur. Mesures Linux hôte CPU/processus/p50/p95/RSS explicites, sans extrapolation matérielle.
- [x] [PR #31 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/31), [450 tests validés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240989108). [Rapport F2-D](f2d-passive-resilience-2026-10-25.md). **F3-A et F3-B sont fusionnées ; F3-C est en PR #34.**

## F2-C — Corrections et ajustement de l'attention (PR #30, fusionnée sur `main`)

- [x] `PassiveLearning` réutilise les observations F1-C **fictives**, dans la même SQLite, pour enregistrer première catégorie, répétition, doublon de trame, incertitude ou rejet ; source `mock_fixture_journal` obligatoire. Aucun effet d'action réellement exécutée n'est inféré.
- [x] Corrections traçables : retrait d'une contribution erronée et recomposition du biais d'attention ; contributions par catégorie plafonnées entre −0,12 et +0,12, sans affecter l'apprentissage de locomotion MuJoCo.
- [x] Biais F2-C activable explicitement dans `AutonomyBrain.propose_balanced_passive(..., learning=...)` ; par défaut, l'algorithme F2-B est inchangé. Contrôle de source absente/incorrecte, observations périmées, redémarrage SQLite et refus de commande motrice.
- [x] **[425 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40240204045)**, 16 nouveaux F2-C et [PR #30 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/30). Aucune perception ni énergie physique validée. [Rapport](f2c-reversible-mock-learning-2026-10-25.md).

## F2-B — Arbitre motivé, cooldown et repos fictif (PR #29, fusionnée/testée sur `main`)

- [x] `AutonomyBrain.propose_balanced_passive()` conserve **le cerveau et la SQLite de F2-A/F1**, et ajoute `PassiveRhythm` en RAM seulement. **Les cinq motivations** interviennent dans les scores de `observe`, `inspect`, `listen` et `idle`. Aucun moteur ni son n'est déclenché.
- [x] Cadence cognitive **≥0,5 s** et blocage **3 s de la même attention/catégorie** ; une nouvelle catégorie peut susciter une autre proposition. Un état de prudence élevée peut favoriser **`idle`**.
- [x] **Repos fictif hystérétique :** entrée si `Motivations.energy` ≤0,22, sortie après ≥0,34. Cette énergie est une **variable simulée**, jamais la batterie ou l'autonomie du Rockchip. Pas de récompense ni d'apprentissage ML.
- [x] Mesures de **propositions uniquement** : décomptes par intention, blocages de cooldown, répétitions actives consécutives, fenêtre bornée à 32. Sous trois observations identiques : `observe`, `idle`, `idle` avec **2 blocages de cooldown**, sans moteur.
- [x] [409 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40239148712), **31 tests nouveaux F2-B** : cinq cycles sur vrai socket Unix d'un faux service, SQLite historique, réinitialisation d'horloge, pertes de source, repos et repli sûr, processus séparé. Aucun équipement physique testé.
- [x] **F2-C fusionnée via PR #30 :** catégories fictives déjà journalisées, nouveau/répété/inconnu, corrections et biais passifs persistants ; aucun effet d'action observé. [Rapport F2-C](f2c-reversible-mock-learning-2026-10-25.md).

[Rapport F2-B](f2b-motivations-cooldowns-2026-10-25.md). **F2-C et F2-D sont fusionnées et testées ; F3-A est en PR #32.**

## F2-A — Intentions cognitives passives (PR #28, fusionnée/testée sur `main`)

- [x] `AutonomyBrain.propose_passive` utilise le **cerveau existant** et la même SQLite `ExperienceMemory`/`PassiveObservationJournal` : pas de deuxième cerveau, aucune nouvelle table ni commande `robotd`.
- [x] Propositions **non exécutées** : `observe` si première occurrence de *catégorie* fictive ; `inspect` sur objet `unknown`/contradiction ; `listen` sur signal sonore fictif ; `rest` sur énergie **motivationnelle simulée** faible ; `idle` pour catégories déjà connues, source perdue ou absence de données fiables.
- [x] Refus conservateur des sources `sensor`/`robot` prétendues, événements périmés/futurs, faible confiance, `safe_area`/`floor_clear` falsifiés, catégories libres et DB indisponible. Les plans ne contiennent ni identité individuelle, ni signal moteur, ni action réellement exécutée ni demande Qwen.
- [x] **[378 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40237211717), dont 27 nouveaux F2-A** : faux socket Unix, projet F1, rappel après processus séparé, maintien de `halt` dans la sécurité indépendante, aucune mutation de préférences ou d'expérience.
- [x] **F2-B fusionnée/testée via PR #29** : arbitrage des cinq motivations, cooldown de catégorie, repos simulé et mesures de diversité. Aucun effet réel.

[Rapport F2-A](f2a-passive-cognitive-intentions-2026-10-25.md). **F2-B fusionnée/testée via PR #29 ; prochaine PR F2-C**, sans locomotion ni reconnaissance réelle.

## F1-D — Démonstration de bout en bout du pipeline passif F1 (PR #27, fusionnée et testée sur fixtures)

- [x] Deux **processus indépendants**, deux faux serveurs Unix locaux, une **SQLite partagée** ; combinaison réelle du lecteur F1-B, de la projection F1-A, du journal F1-C et d'`AutonomyBrain`, sans service de contrôle moteur.
- [x] **10 cycles fictifs** (6 + 4) : découverte d'une catégorie `ball`, rappel ultérieur, conflit `ball/toy` ⇒ `unknown`, `unknown`, perte de socket, signal fictif `knock`, redémarrage et reprise puis catégorie `dog`. **8 lignes de journal**, **4 occurrences de `ball`** (catégorie, pas individu), **2 pertes de source**, **10 intentions `halt`**, **0 commande motrice**.
- [x] Refus de rejouer une session dans le mauvais ordre **avant écriture**, horloge monotone renouvelée au second processus, aucune ancienne lecture relancée comme capteur frais. Seuls `mock` et les libellés catégoriels autorisés sont persistés ; pas de `track_id` ou médias.
- [x] [351 tests Python réussis et deux CLI GitHub Actions](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40235779649), **12 nouveaux tests F1-D** ; [rapport et mode d'emploi](f1d-integrated-passive-demo-2026-10-25.md).
- [ ] **Non démontré :** classe reconnue par vraie caméra/microphone, NPU, autonomie énergétique, comportement sur Microduck physique et exploration. F1 est **terminée au niveau protocole logiciel fictif uniquement** ; travail réel relevant de F3 et F7.

**F2-A et F2-B sont fusionnées/testées via PR #28 et #29 ; F2-C est la prochaine PR**, sans changer `robotd` ou le chantier P0/P1.

## F1-C — Mémoire des catégories passives dans la SQLite existante ([PR #26 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/26))

- [x] `PassiveObservationJournal` complète **la connexion SQLite d'`ExperienceMemory`** sans deuxième base. Seulement `PassiveRead` venant du contrat fictif F1-B : environnement et source `mock`, canal fixe `mock_fixture_unix`, observations d'objet/son, aucun événement de sécurité ni commande motrice.
- [x] `identified`, `unknown`, `conflict`, `low_confidence`, `stale` et `future` conservés **sans promotion d'une incertitude en catégorie sûre** ; pas de `track_id`, transcription, nom libre, pixel ou voix brute. Les anciennes données sont **historiques**, jamais converties en perception encore fraîche.
- [x] Deux **processus Python distincts** rouvrent la même SQLite et retrouvent un nombre croissant d'observations de *catégorie* (1 puis 2), avec horloges monotones différentes et identifiants de session séparés ; cela n'identifie **aucun animal ou objet individuel**.
- [x] **Rétention logique de 14 jours**, borne physique à **512 lignes**, consultation plafonnée à 100, séquences idempotentes et purge du contenu ancien ou anormalement futur.
- [x] **Tests logiciels F1-C : [339 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234908502), dont 24 nouveaux scénarios** avec données fictives ; [rapport de conception et limites](f1c-passive-sqlite-memory-2026-10-25.md). Aucun robot physique ni `mediad` constructeur testé.
- [x] **F1-D fusionnée/testée séparément** ([PR #27](https://github.com/Jean-Philippe56520/Microduck/pull/27)) : scénario de bout en bout sur source fictive, aucune perception matérielle validée ; [rapport F1-D](f1d-integrated-passive-demo-2026-10-25.md).

## F1-B — Adaptateur de source passive à provenance explicitement fictive (PR #25, fusionnée et testée logiciellement)

- [x] `FixtureUnixReader` lit des catégories de fixtures via **socket Unix local** ; trame JSON bornée 8192 octets, délai global 3 s, données âgées d'au plus 2 s, débit ≤2 lectures/s, séquences strictement croissantes, maximum 64 événements et refus conservateur. Toute source acceptée reste `mock`, même si le service déclare `sensor`.
- [x] Sonde `probe_official_mediad()` vérifiant seulement `hello` sur l'API OEM ; sélection du chemin officiel, identité du pair Unix et version/révision épinglées avant toute qualification locale. **Aucune image via `media.frame` et aucun flux `media.detections` réellement consommé.** Un socket temporaire de test ne peut pas se prétendre constructeur.
- [x] [315 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234054024), **20 nouveaux** sur sockets Unix réels entre processus fictifs : interruption, silence/délai, doublons, trames excessives, usurpation de provenance, commande/sécurité refusées et `hello` uniquement.
- [ ] **Réception de vraies catégories OEM, voix/caméra et validation sur robot : non réalisées.** L'API examinée ne fournit pas une classification chien/chat/personne sur son socket local. Aucun moteur ni stockage d'image/son.
- [x] **F1-C fusionné séparément dans `main`** : journal de catégories fictives en SQLite, repris dans deux processus ; [rapport F1-C](f1c-passive-sqlite-memory-2026-10-25.md). La démonstration F1-D est terminée en logiciel sur fixtures ; le traitement des vrais capteurs reste à faire en F3/F7.

[Rapport F1-B](f1b-passive-source-2026-10-25.md).

## F1-A — Contrat de perceptions passives (PR #24, fusionnée et testée logiciellement)

- [x] Réutilisation de `PerceptionEvent`/`PerceptionSnapshot` v1, ajout additif d'un événement `sound_label` limité à des catégories (pas de transcription, biométrie, modèle de son ou vraie capture).
- [x] Projection passive `summarize_passive` : `ball`, `toy`, `dog`, `cat`, `person`, `microduck` ou `unknown`, ainsi que signaux fictifs ; source **déclarée**, confiance ≥0,80, TTL, `track_id` éphémère, contradictions, limite 64 événements. Un événement non fiable, ancien ou incompatible ne devient pas un fait.
- [x] **[295 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40233207115)**, dont 26 nouveaux sur fixtures fictives ; `keyword_stop` n'est pas un arrêt moteur. Les données `safe_area`/`floor_clear` et les politiques OEM restent inchangées.
- [x] Inspection des sources `mediad` épinglées : `media.frame` propose une image brute locale ; `media.detections` fournit des boîtes de Microducks via une session WebRTC, **sans catégories animaux/personnes**. Aucune interface audio de catégories validée.
- [x] **F1-B fusionné et testé séparément**, puis **F1-C fusionné/testé sur `main`** pour observations persistantes fictives. Aucune classification ni identité constructeur réelle n'est acquise ; aucun média, moteur ou robot physique testé.

[Rapport F1-A](f1a-passive-observation-contract-2026-10-25.md). **F1-A/B/C/D et F2-A/F2-B fusionnées/testées en logiciel fictif ; prochaine étape F2-C.**

## P0j — Réanalyse hors ligne des forces de contact de P0e (PR #22, fusionnée)

- [x] Module `sim_p0j_load_transfer.py`, aucun socket ni pilote : trois SHA-256 immuables, 888 trames archivées, horloge physique continue, fenêtres `stand`/`walk` héritées de l'observation P0b 10 Hz et contrôle de `robot.stop` déjà archivé.
- [x] **[269 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946) et [replay OEM P0e réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655)** ; 12 nouveaux tests factices de classification des pieds, données manquantes/non finies, provenance et arrêt obligatoire.
- [x] **P0e recalculé :** repos 79/79 et marche 127/127 avec deux pieds chargés > 0,1 N ; **0/127 appui unipodal** pendant la fenêtre `walk`, répartition moyenne gauche 52,03 % au repos contre 44,54 % en marche. Les trajectoires de sites pied monde ne sont **pas** des vitesses de glissement réelles ; aucune force de propulsion signée exploitable dans le journal.
- [ ] **Causalité du défaut de propulsion, démarche stable et validation physique non établies.** Aucun nouvel essai moteur ; **P1a bloqué**.

[Rapport P0j](mujoco-p0j-load-transfer-2026-10-25.md).

## P0i — Comparaison bornée des politiques en deux boots MuJoCo (PR #21)

- [x] Banc expérimental : un essai `run_walk_trial` à **0,12 m/s** et **24 notifications** dans chaque nouveau processus OEM ; paire `alpha_walking/alpha_stand` d'abord, `velstand` avec `stand=none` ensuite, sélection effective vérifiée via `robotctl policy list`. Les trois SHA-256 ONNX v8 sont exigés, la scène et les révisions épinglées vérifiées.
- [x] **[257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915)** ; quatorze nouveaux tests couvrent les modèles, le manifeste, les refus, le stop, l'absence de données finies et la séparation des bras.
- [x] **[CI MuJoCo constructeur réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528)** : **alpha 1,443665 mm XY, VelStand 1,967688 mm XY**, variation +0,524023 mm ; 23/24 et 24/24 échantillons `walk`, deux confirmations `robot.stop`, PIDs différents, vitesse appliquée max 0,12 m/s, SQLite distinctes. **0/2 bras atteint 10 mm**.
- [x] Premier essai CI refusé sans commande B : confusion entre fichier modèle `robotd.toml` et paramètre réellement chargé `robotd-duck-a.toml`. Corrigée sans abaisser les exigences de sécurité.
- [ ] **Marche effective, cause racine et validation physique non démontrées.** Les premières mesures restent de petits déplacements relatifs ; contacts précis et inertie de la politique en boucle fermée non résolus.

[Rapport P0i](mujoco-p0i-controlled-policy-pair-2026-10-25.md).

## P0h — Sélection et filiation des politiques ONNX (PR #20)

- [x] **Contrat source :** `robotd` utilise normalement `velstand.onnx` sans slot debout, mais `duck-sim` force la paire `alpha_walking.onnx` / `alpha_stand.onnx` (seuil `0,05`). Provenance W&B déclarée dans les sources RL épinglées, sans preuve cryptographique d'identité des poids.
- [x] Nouveau diagnostic en lecture seule `sim_policy_lineage.py` et **[243 tests Python réussis sur main](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219827102)** : vérifications de sources, TOML, manifeste, `.source`, formes ONNX et refus conservateurs.
- [x] [CI MuJoCo officielle P0h réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) : trois modèles ONNX v8 présents, 10 entrées de manifeste, mêmes dimensions 61→14, SHA-256 différents, sorties CPU synthétiques différentes (L2 **0,2296** et **0,1524**) et **zéro nouvelle commande motrice**.
- [ ] Le rôle de cette divergence dans l'absence de translation n'est **pas prouvé**. P1a bloqué, pas de test matériel.

[Rapport P0h](mujoco-p0h-policy-slot-lineage-2026-10-25.md).

## P2b — Cycles cognitifs passifs reliés aux démons simulés (PR #19)

- [x] Exécuteur `sim_passive_cycles.py` : télémétries datées `robotd`/`tofd` via RPC limités en lecture, choix `AutonomyBrain`, journal SQLite de qualité/intention et reprise entre sessions, **sans API moteur et sans récompense**.
- [x] **234 tests Python réussis** sur branche : [CI P2b](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199119). Dix tests nouveaux, y compris sockets Unix fictives, reprise SQLite, horodatages, répétitions, pertes de capteurs et refus sûrs.
- [x] [CI MuJoCo constructeur](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) réussie : **3/3 + 3/3 cycles cohérents**, même SQLite réouverte, **3 puis 6 enregistrements**, séquences ToF progressives, `halt` six fois (sol non certifié), zéro moteur, récompense ou conséquence. JSON archivés.
- [ ] Aucun résultat moteur, visuel ou physique validé. P0h est terminé et fusionné, avec les politiques ONNX vérifiées ; les perceptions visuelles et sonores ne sont pas encore développées.

[Rapport P2b](p2b-passive-mujoco-cycles-2026-10-25.md).

## P0g — Contacts compilés statiques (PR #18, testé MuJoCo)

- [x] Trois variantes constructeur en scènes temporaires, même STAND, **mj_forward seulement**, 0 commande moteur. [214 tests](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208638362) et [MuJoCo OEM #40208635206 réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208635206).
- [x] Geoms compilées Walk/Groundcontact/AllCollisions **76/82/141**, masques-sol éligibles **2/10/69**. Même pose, masse simulée 0,73724318 kg, mêmes friction/solref/solimp des pieds et du sol ; 0 contact candidat statique sans relaxation dynamique, ce qui ne mesure PAS les contacts en marche.
- [ ] Cause inconnue, pas de correction motrice. **P0h terminé** : audit de provenance et sélection alpha_walking/velstand ; une comparaison motrice contrôlée exigerait un nouveau lot. **P2b** : cycles cognitifs passifs MuJoCo indépendants de la locomotion.

[Rapport P0g](mujoco-p0g-compiled-contacts-2026-10-25.md). P1a toujours bloqué, aucun test sur robot physique.

## P2a — Cycles fictifs multiples et mémoire persistante (PR #17)

- [x] **Boucle logique hors connexion, mock uniquement :** perception sourcée et horodatée → mémoire SQLite → motivation et intention → aucune exécution motrice → résultat fictif explicite avec observation fraîche → préférence graduelle → cycle suivant. Les intentions de marche/jeu sont marquées `blocked_motion`, jamais exécutées ni récompensées.
- [x] **Vérification CI :** [217 tests réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40207932413). Deux sessions avec une même base de données montrent **4 puis 8 lignes de journal**, une préférence fictive `0,06` réutilisée et **zéro commande moteur**. Tests de redémarrage, doublons, source LLM refusée, horodatages, perte de sécurité et retour sans preuve.
- [x] **P2b, déjà livré et validé :** plusieurs cycles passifs reliés à `robotd`/`tofd` réels **du simulateur**, sans activer `robot.move` ; garder les cas limites de fraîcheur, déconnexion et reprise SQLite. Pas de preuve de mobilité ni de validation embarquée.

[Rapport P2a](p2a-mock-cycles-2026-10-25.md).

## P0f — Contrats ONNX et variantes de géométrie (PR #16, testé en MuJoCo)

- [x] **Audit contrôlé :** lecture seule des sous-modules constructeur et RL épinglés, vérification des contrats du code d'observation (61), des actions (14, `mouth` exclue), de la pose HOME et du filtrage/échelle de `robotd`, de la provenance locale des fichiers `alpha_walking`/`alpha_stand` et de leurs SHA-256.
- [x] **Vérification ONNX réelle, mais indépendante :** [207 tests Python](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419766) et [MuJoCo headless #40200419709 réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419709). Les deux fichiers chargés de **793 705 octets** sont des réseaux non récurrents `obs [1,61] → actions [1,14]`. Pose HOME des 14 articulations : **0 rad de différence** ; variation de sortie brute synthétique du réseau de marche **0,147 L2** entre 0 et 0,12 m/s.
- [x] **Différences de sources identifiées :** tâche vitesse `robot_walk.xml` (85 géométries, **2** géométries explicitement classées `collision`), tâche VelStand `robot_allcollisions.xml` (150, **69**), runtime headless `robot_groundcontact.xml` (91, **10**). **Ce ne sont pas les contacts actifs et la variante exacte utilisée pour les poids ONNX v8 reste à établir.** Échelles de contrôle 1,0 dans la configuration RL de vitesse et 0,9 par défaut dans `robotd` : comparaison directe insuffisante sans version du réseau et filtres.
- [ ] **Cause et boucle motrice non vérifiées :** aucune observation/action brute de `robotd` capturée au même tick, aucune nouvelle mesure J2e ; P1a reste bloqué. P0g comparera les paramètres de contact compilés des trois variantes en MuJoCo **séparé**, passif et épinglé, et cherchera la provenance du checkpoint ONNX. P2 peut avancer sans marche.

Voir [rapport P0f](mujoco-p0f-policy-contract-2026-10-25.md). Les appels ONNX CPU sont **synthétiques** et ne représentent pas l'inférence réelle en boucle fermée.

## P0e — Audit du gain et du modèle de force actif (PR #15, testé MuJoCo)

- [x] **Code et sûreté :** sonde facultative dans l'unique processus OEM headless déjà vérifié ; capture au pas physique avant intégration (`ctrl`, `qpos`, `qvel`, gains, biais, `forcerange`, damping, frottement), `mj_step` constructeur appelé **une seule fois** et forces originales récupérées après. P0d reste utilisable sans le mode P0e ; erreurs diagnostiques n'interrompent pas la physique et aucune commande n'est ajoutée.
- [x] **Tests et simulation :** [199 tests Python + scénario OEM réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617). 79 trames `stand`, 127 trames `walk`, gains **0,44** et **0,55 N·m/rad** conformes au modèle OEM (quatre trames de transition 0,44 dans la fenêtre marche), effort prédit égal au solveur sur **2 884 échantillons**, **0 saturation** à la limite ±0,96 N·m. Double appui chargé **127/127** ; J2e **2,295 mm** de translation finale, stop et mémoire `no_progress_observed`.
- [ ] **Marche toujours bloquée :** P0e n'explique pas la faible excursion des hanches, la persistance du double appui ou l'absence de propulsion. P0f devra analyser sans réglage les entrées/sorties ONNX, mises à l'échelle et le simulateur d'entraînement à révision OEM connue ; pas de tentative P1a sans cause vérifiée.

Voir le [rapport P0e](mujoco-p0e-actuator-gains-2026-10-25.md). La capture Python pré-pas ajoute de la charge CPU non mesurée globalement, et aucune force/cadence n'est validée sur robot réel.

## P0d — Mesures native du solveur et consignes (PR #14, testée sur MuJoCo)

- [x] **Capture :** `mujoco.mj_step` constructeur conservé, copie facultative de contacts, forces normales/tangentielles, cibles articulaires `data.ctrl` et angles dans le même processus. Fichiers OEM intacts, aucun nouvel ordre moteur ; capture un pas sur quatre à 5 ms, journal JSONL via file asynchrone.
- [x] **Essai officiel :** [CI MuJoCo #40190232870](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190232870) réussi ; 888 relevés validés à l'analyse, `stand` 79, `walk` 126 à ~50 Hz. **Les deux pieds chargés sur 126/126** relevés pendant marche, forces normales moyennes gauche ~3,21 N et droite ~4,03 N, roulis hanche gauche consigne 0,157 rad / angle 0,011 rad, droite 0,167 rad / angle 0,006 rad. J2e : **2,222 mm**, arrêt confirmé.
- [x] **Robustesse logicielle :** [190 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697176), vérification provenance, pertes de trames, sauvegarde asynchrone et erreurs de sonde sans arrêt du solveur OEM.
- [x] **Répétition du diagnostic durci :** [MuJoCo #40190697090](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697090) réussi avec **190 tests**, 77 trames `stand`, **132 trames de marche, deux pieds chargés 132/132**, 1,597 mm final, `robot.stop` confirmé. Gains estimés sur les hanches/genoux ~0,52–0,55 N·m/rad, cohérents avec le `kp=0.55` du MJCF épinglé ; aucun écrêtage à ±0,96 N·m observé pour ces articulations. **Ce n'est pas une preuve que le gain est fautif.**
- [ ] **Causalité et marche :** contacts et cibles observés par une sonde de diagnostic, mais **pas** de cause démontrée ni de cycle de pas stable. P0e devra confronter gains, limites et écart de suivi des consignes de façon mesurée ; P1a reste bloquée.

Le [rapport P0d](mujoco-p0d-live-solver-2026-10-25.md) explique l'écart de temps entre contact, consigne et position, le surcoût d'instrumentation et les mesures non physiques. Le protocole OEM `body_server.op=read` **n'a pas été modifié** et ne transmet toujours pas contacts/consignes ; P0d lit `MjData` localement en mode diagnostic.

## P0c — Replay hors ligne des contacts géométriques (PR #13, testé en MuJoCo)

- [x] **Code et tests :** lecture du quaternion OEM, reconstruction de pose avec `mj_forward` dans un modèle indépendant, appariement géométrique semelles/sol, refus des données invalides, aucune commande moteur ni progression de la physique ; [179 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954).
- [x] **Simulation épinglée exécutée :** [CI MuJoCo #40188553954](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954) : les deux semelles montrent un léger chevauchement du sol à **16/16** instants de `stand` et **24/24** instants de l'essai de marche, distance signée entre environ **−0,534 et −0,289 mm** pendant `walk`. L'essai J2e de cette exécution s'arrête avec **1,997 mm** de déplacement net, `stop` confirmé, `no_progress_observed`.
- [ ] **Cause toujours inconnue :** les contacts dynamiques du solveur, forces/impulsions et cibles articulaires originales ne sont pas exposés par le protocole constructeur `op=read`. Le replay statique ne peut pas établir une alternance des appuis, une traction, une absence de décollage entre échantillons ou une démarche. P1a reste bloquée.

Voir le [rapport P0c](mujoco-p0c-contact-replay-2026-10-25.md) ; prochaine étude P0d : une instrumentation de diagnostic des contacts **au même tick** dans un environnement de simulation isolé, sans modifier la sécurité de `robotd` ni prétendre valider le robot réel.

## P0b — Repos comparé à un essai `walk` (PR #12, testé en MuJoCo)

- [x] **Code et tests :** la [PR #12](https://github.com/Jean-Philippe56520/Microduck/pull/12) ajoute `sim_walk_compare.py`, un crochet de mesure passive limité à la section J2e où `robot.stop` est garanti, et des tests d'arrêt sur perte de télémétrie. [167 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514224).
- [x] **Essai OEM émulé :** [workflow MuJoCo #40187514292](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514292) réussi avec `stand` 16/16, `walk` 23/24, vitesse appliquée déclarée ~0,12 m/s, 24 commandes, `robot.stop` confirmé, déplacement final **1,338 mm** et `no_progress_observed`.
- [x] **Excursions articulaires mesurées :** genou gauche 0,0223 rad et genou droit 0,0081 rad en fenêtre `walk`, distinctes des références repos ; ne pas déduire un cycle de pas de ces seules variations.
- [ ] **Blocage non levé :** les contacts des pieds et cibles articulaires ne sont pas fournis par le serveur OEM. Origine du manque de progression **non établie** ; P1a reste bloquée. Priorité : méthode non intrusive pour obtenir contacts/forces dans la même simulation, puis interprétation causale fondée sur les données.

Voir le [rapport de mesures P0b](mujoco-p0b-stand-walk-comparison-2026-10-25.md). Les mouvements et les métriques MuJoCo ne constituent pas une validation physique.

## P0a — Diagnostic articulations et politiques (testé en MuJoCo, 25 octobre 2026)

- [x] **Code proposé par PR #11 :** [PR #11](https://github.com/Jean-Philippe56520/Microduck/pull/11), nouvelle sonde passive `sim_joint_trace.py` et tests de formats, provenance, temps et cohérence des mesures.
- [x] **151 tests Python réussis :** [GitHub Actions #40178580633](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580633).
- [x] **Collecte MuJoCo effective :** [smoke test #40178580637](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580637) réussi ; `joint-trace.json` archivé avec 8 échantillons (5 Hz, durée simulée 1,4 s), politique `stand` 8/8, vitesse demandée/appliquée 0 m/s, variation nette du tronc **0,991 mm** et trajet XY cumulé **1,044 mm**. C'est un relevé passif au repos, pas un essai de locomotion.
- [ ] **Contacts des pieds :** indisponibles dans `op=read` du protocole OEM épinglé ; idem pour les cibles articulaires. Les valeurs restent explicitement inconnues ; examiner la possibilité d'un moyen de diagnostic constructeur compatible pour P0b, sans modifier ses mécanismes de sécurité.

Le capteur de courant est une approximation fournie par le serveur MuJoCo (`abs(actuator_force) * 100`) et ne doit pas être interprété comme un courant électrique réel. L'activation de `policy=walk`, la variation des articulations et l'absence de chute ne suffisent pas à valider une démarche. **Aucune nouvelle commande motrice ne fait partie de P0a** et le robot physique reste indisponible.

## Vision et périmètre

Créer un Microduck discret, curieux, explorateur et social : percevoir, retrouver ses souvenirs, choisir une intention sûre, agir, observer le résultat et adapter progressivement ses préférences. Il peut décider de ne rien faire. Le dialogue est secondaire.

Le robot doit conserver les fonctions essentielles sans PC ni Internet. `robotd` reste seul maître des moteurs et de la sécurité. Le modèle Qwen, facultatif, propose des hypothèses ; il ne commande jamais les moteurs et ne certifie jamais une observation. Priorité au Microduck, sans travail pour d'autres matériels à ce stade.

## État du socle et écarts restants

- [x] Dépôt de développement, tests Python et GitHub Actions présents.
- [x] Sources officielles `upstream/microduck` et `upstream/microduck_rl` liées par sous-modules Git sur des révisions précises.
- [x] Prototype Python : `AutonomyBrain`, motivations, intentions, garde-fous initiaux, mémoire SQLite d'objets/expériences et rétroaction sur les préférences.
- [x] Les hypothèses du LLM restent distinguées des étiquettes issues d'observations déclarées par les capteurs.
- [x] Treize cas de test automatisés dans `tests/test_autonomy.py` ; les exécutions CI consultées avant ce plan étaient réussies.
- [x] Audit documentaire du matériel et script `scripts/resource-audit.sh` préparés.
- [x] Connexion **en lecture seule** du compagnon aux vrais démons `robotd` et `tofd` exécutés en simulation MuJoCo (essai CI 2026-10-25).
- [x] Chaîne **bornée** perception → décision → action via `robotd` → résultat → mémoire démontrée dans MuJoCo (un essai volontaire, locomotion non validée).
- [ ] Boucle autonome **multi-cycles** et perception visuelle depuis `mediad` ; connexion des véritables pilotes et capteurs physiques non réalisée.
- [ ] Inférence visuelle chien/chat/personne, reconnaissance individuelle, intégration Qwen.
- [ ] Mesures et validation sur un Microduck physique.

Les scènes du prototype sont **fictives**. Aucun mouvement réel, capteur réel, taux de reconnaissance ou budget de ressources matériel n'a été validé. Le robot physique n'est pas encore disponible.

## Avancement du jalon J1 — 2026-10-25

- [x] `PerceptionEvent` et `PerceptionSnapshot` v1 ajoutés : horodatage monotone, durée de validité, provenance, confiance, identifiant d'objet suivi et distinction des environnements `mock`, `simulator` et `robot`.
- [x] Le moteur accepte `choose_from_snapshot` ; les données de sécurité manquantes, périmées, contradictoires, de faible confiance ou attribuées à une source non autorisée conduisent à `halt` (avec exception du repos sur batterie basse vérifiée).
- [x] La mémoire SQLite conserve la provenance `mock` / `simulator` / `sensor` d'une étiquette, et les hypothèses LLM restent distinctes.
- [x] 40 tests Python passés localement et sur GitHub Actions sur la branche de développement (13 tests historiques + 27 tests de perception).
- [x] Associer la provenance aux sockets de `robotd`/`tofd` et à la scène épinglée **dans MuJoCo**, avec validation du processus du simulateur.
- [ ] Établir l'authenticité de mesures de **capteurs physiques** via les vrais pilotes ; le seul texte `source="sensor"` n'est pas une preuve matérielle.
- [x] Lancer `duck-sim` sur Linux CI, relever sa santé et sa vitesse, puis connecter les observations MuJoCo en lecture seule ([exécution réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078)).
- [ ] Évaluer les garde-fous avec les capteurs, les pilotes et le matériel physique.

**Frontière de confiance :** la méthode historique `choose(Scene(...))` reste un chemin de démonstration synthétique ; toute intégration devra passer par des mesures réellement produites et vérifiées par un adaptateur. Ce module ne contrôle aucun moteur et `robotd` conserve seul l'autorité de sécurité.

## Phase 1 — Consolider le cerveau sur PC (V0 ; en cours)

**But :** disposer d'un moteur local déterministe, explicable, testable, séparé des capteurs et des commandes.

Travaux :
1. Définir un contrat versionné `PerceptionEvent` / `PerceptionSnapshot` : horodatage, provenance, confiance, identifiant suivi, durée de validité, incertitude et état des capteurs. Adapter le `Scene` existant sans casser les tests.
2. Traiter explicitement les données absentes, périmées ou contradictoires : ne pas transformer « inconnu » en « sol sûr ».
3. Renforcer la boucle motivations → souvenirs → choix → résultat ; éviter les actions répétitives et permettre `idle`/`rest` sans oscillations arbitraires.
4. Étendre progressivement SQLite : épisodes, objets/propriétés, repères incertains et résultats comportementaux. Séparer provenance et confiance ; conserver la possibilité de corriger une hypothèse.
5. Ajouter des tests de reprise, de persistance, de capteur perdu, de temporisation et d'échec. Utiliser des observations fictives uniquement.

**Critère de sortie :** tous les tests sont verts ; pour chaque entrée incertaine ou dangereuse, aucune intention de déplacement non sûre ; apprentissage reproductible sur plusieurs épisodes ; aucun PC ou LLM requis pour choisir une intention locale.

## Avancement J2a — client IPC en lecture seule (25 octobre 2026)

- [x] `microduck_companion/sim_ipc.py` : client Unix JSON-RPC 2.0 NDJSON avec liste blanche stricte (`robot.health`, `robot.subscribe`, `tof.stream`), délais, validation des réponses et trames ToF 8×8 brutes.
- [x] `microduck_companion/sim_probe.py` : outil de diagnostic ciblant les sockets locaux créés par `duck-sim` ; aucune commande moteur autorisée.
- [x] 25 nouveaux tests sur sockets Unix fictifs (22 IPC + 3 sonde), soit **65 tests logiciels** dans le projet. Validation CI à contrôler lors de la fusion.
- [x] Démarrage du vrai `duck-sim` officiel sur **Ubuntu CI** avec Rust/Cargo, Python 3.12 et les politiques ONNX épinglées ; reproductibilité sur poste Linux/WSL2 personnel non encore vérifiée.
- [x] Lire les trames des vrais démons simulés, mesurer l'état du contrôleur (~50 Hz), le ToF 8×8 et le facteur temps réel (1,00×) sur Ubuntu CI.
- [x] Convertir les lectures vérifiées en `PerceptionSnapshot` avec gestion d'incertitude ; la **scène plane épinglée** peut produire une attestation limitée à la simulation, jamais le ToF seul.
- [x] Tester **une intention bornée** `robot.move` puis `robot.stop` via `robotd`, sur MuJoCo seulement ; l'adaptateur pour les intentions générales et le robot physique reste à développer.

**Historique J2a :** les premiers tests utilisaient uniquement de faux sockets. **Mise à jour :** l'exécution CI du 25 octobre a depuis confirmé `robot.health`, `robot.state` et `tof.frame` sur les démons officiels sous MuJoCo. Toujours aucune mesure sur robot physique ni commande motrice issue du compagnon.

## Avancement J2b — pont télémétrie → cerveau (25 octobre 2026)

- [x] `microduck_companion/sim_bridge.py` : acquisition des télémétries officielles en lecture seule, contrôle de fraîcheur, santé, cadence moteur, chute et cohérence temporelle des sources ; `PerceptionSnapshot` conservateur (aucun sol ou espace déclaré sûr par le ToF).
- [x] `microduck_companion/sim_observer.py` : diagnostiquer une décision du cerveau sans envoyer de commande motrice.
- [x] `scripts/sim-smoke.sh` : contrôle des prérequis, lancement prévu de `duck-sim` sans interface graphique ni caméra, probes, puis arrêt propre ; réservé au clone Linux/WSL2.
- [x] **81 tests logiciels** exécutés en local : 65 tests existants + 16 tests de pont IPC, données absentes et réponses sûres, dont de faux sockets Unix.
- [x] Exécuter `scripts/sim-smoke.sh run` dans un environnement Linux GitHub Actions avec Rust/Cargo, Python 3.12, `uv`, sous-modules épinglés et politiques ONNX officielles.
- [x] Vérifier `robot.health`, `tof.frame`, la cadence effective de `robotd`, la vitesse MuJoCo et les décisions observées sur l'exécuteur CI.
- [x] Vérifier une petite zone plane **uniquement en MuJoCo** par provenance du modèle et vérité terrain ; ne jamais inférer la sécurité des escaliers à partir du ToF 8×8.

**Statut du jalon J2b :** lecture seule validée sur MuJoCo ; aucune validation sur robot. Les étapes ultérieures J2c/J2d ont ensuite attesté la **scène plane virtuelle** et la commande bornée. Le ToF 8×8 ne certifie toujours pas la sécurité du sol réel.

## Première validation MuJoCo officielle — 25 octobre 2026

Le jalon de **lecture seule** est désormais **simulé et testé** sur Ubuntu 24.04 via [GitHub Actions #40145369078](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078), utilisant les sous-modules épinglés et les politiques ONNX officielles :

| Contrôle | Observation réelle pendant cette exécution |
| --- | --- |
| Lancement et arrêt `duck-sim` | Réussis ; un Microduck, sans caméra, mode headless |
| `robotd` | `healthy`, ~50 Hz (exemple de santé à 50,1 / 50,0 Hz), 0 échéance manquée dans l'échantillon |
| Temps réel MuJoCo | `duck-sim realtime` : **1,00×** |
| `tof.stream` | Source `sim`, trames 150 et 151, **64 cellules** chacune |
| `sim_probe` | Lecture `robot.health`, `robot.state`, `tof.frame` validée ; aucune commande motrice |
| `sim_observer` | `environment=simulator`, `intention=halt`, `errors=[]`, `floor_certified=false` |
| Tests Python | **81/81 réussis** |

L'observation de batterie (~50 % dans le flux) et les données ToF sont **simulées**. La santé `robotd` et la cadence concernent uniquement l'exécuteur Linux de ce test. Ni l'évitement des escaliers, ni une exploration de maison, ni les consommations, températures et latences du robot physique ne sont validés.

**Prochain verrou à traiter :** vraie preuve de `safe_area` / `floor_clear` provenant d'un scénario de test MuJoCo borné, puis autorisation conditionnelle de courtes intentions via `robotd`, avec arrêt sûr.

## Phase 2 — Démarrer et observer le simulateur officiel (V1a ; vérifiée sur Ubuntu CI)

Plan opérationnel avec critères de sortie et étapes de validation : [J1b → J2 — MuJoCo](mujoco-integration-plan.md).

**But :** obtenir une base MuJoCo reproductible avant de connecter le cerveau.

Travaux :
1. Sur Linux ou WSL2, initialiser les deux sous-modules épinglés, préparer l'environnement Python de `upstream/microduck_rl` et les dépendances Rust/ONNX requises.
2. Utiliser `upstream/microduck/scripts/duck-sim` en mode `up` (sans conteneur) avec `DUCK_SIM_RL` pointant sur notre sous-module RL ; commencer **sans caméra** et avec un seul robot.
3. Confirmer le démarrage de `robotd` et `tofd`, `duck-sim status`, `duck-sim ctl health`, `duck-sim realtime` et l'arrêt propre.
4. Documenter les commandes, versions, téléchargements initiaux des politiques ONNX, erreurs de dépendances et mesures de référence. N'activer la caméra simulée qu'après cette validation.

Exemple de commandes depuis la racine du projet (procédure officielle ; le script `scripts/sim-smoke.sh` a été **effectivement exécuté sur CI** avec ces opérations de démarrage, santé, temps réel et arrêt) :

```sh
git submodule update --init --recursive
cd upstream/microduck_rl
uv sync
cd ../..
export DUCK_SIM_RL="$PWD/upstream/microduck_rl"
upstream/microduck/scripts/duck-sim
upstream/microduck/scripts/duck-sim status
upstream/microduck/scripts/duck-sim ctl health
upstream/microduck/scripts/duck-sim realtime
upstream/microduck/scripts/duck-sim down
```

**Critère de sortie :** démarrage et arrêt reproductibles, santé du robot virtuel contrôlée, facteur de temps réel mesuré et journaux diagnostiques disponibles. Le maintien de la boucle officielle à 50 Hz reste vérifié par les outils et journaux du constructeur, pas présumé.

## Avancement J2c — zone simulée à preuve bornée (25 octobre 2026)

- [x] `sim_flat_zone.py` : contrôle strict de la révision et de l'intégrité du simulateur officiel, de l'identité du processus `body_server`, de sa scène par défaut sans caméra et de sa pose dynamique. **Sans ces attestations, aucune preuve de sol sûr.**
- [x] `sim_zone_probe.py` : déduit `safe_area`, `floor_clear` et une distance à la **limite virtuelle** de la zone ; n'utilise jamais le ToF 8×8 pour inventer un sol sûr, et n'envoie aucun mouvement.
- [x] 22 nouveaux tests logiciels vérifiant limites, pose, trames invalides, sources périmées, scène non épinglée et processus inconnu ; 103 tests Python réussis sur GitHub Actions.
- [x] Sonde vérifiée en **véritable MuJoCo** : [CI #40173323079](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173323079), scène épinglée validée, réserve 0,7134 m, robot debout (tronc z=0,1155 m), décision `explore` sans commande motrice.
- [x] Autoriser **une intention courte et bornée** en simulation (J2d/J2e), avec vérification de zone, arrêt explicite et deadman constructeur préservé.
**Contrainte non négociable :** aucune preuve de sécurité MuJoCo n'est transposable à un Microduck physique ; des capteurs réels et des essais supervisés restent nécessaires.

**Statut J2c (historique) :** contrôles de zone codés et validés dans MuJoCo, initialement en lecture seule. La première commande bornée a **ensuite** été validée en J2d. Aucune transposition sur robot réel.

## J2d — Une seule intention robot.move bornée (25 octobre 2026)

- [x] `sim_motion.py` : vitesse avant fixée à **0,05 m/s**, quatre notifications sur ~0,4 s, sans rotation ; lecture de la vraie pose MuJoCo et de la santé `robotd` avant chaque commande.
- [x] `robot.stop` (appel discret) vérifié en fin d'essai, y compris sur pertes de capteur pendant une séquence de mouvement ; deadman constructeur conservé.
- [x] Double consentement explicite `--enable-once` + `MICRODUCK_SIM_MOTION_TEST=YES` ; le workflow normal sur `main` ne lance pas de mouvement.
- [x] 12 tests de contrôle de mouvement avec faux services Unix, **115 tests logiciels** réussis.
- [x] Impulsion exécutée sur le vrai `robotd` simulé : [CI #40173809463](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173809463), 4 `robot.move`, `robot.stop` confirmé, contrôleur sain ~50 Hz, MuJoCo 1,00×. Déplacement observé du tronc **0,185 mm** (trop faible pour valider la marche).
- [ ] Après cet essai, développer une vraie boucle continue perception → décision → action → conséquence → mémoire, avec limites réévaluées, sans Qwen.

**Statut : code + tests vérifiés ; chemin de commande et arrêt testés en vrai MuJoCo.** Une intention `explore` a déclenché un essai très bref sans preuve de locomotion effective. Aucun moteur réel ni pilote constructeur modifié.

## J2e — Essais de translation et mémoire des conséquences (mesurés ; locomotion non validée, 25 octobre 2026)

- [x] Revue du constructeur : le seuil par défaut de la politique station debout / marche est `0,05 m/s` ; précédente commande `vx=0,05 m/s` au seuil, seulement 0,185 mm de variation de position du tronc.
- [x] `sim_walk_trial.py` : essai unique `vx=0,12 m/s`, **24 notifications** espacées de 0,1 s au maximum, observation de la dérive au repos, contrôles des zones et santé avant chaque commande, `robot.stop` confirmé.
- [x] `episodic_memory.py` : persistance en SQLite des essais simulés ; résultats fiables distingués des hypothèses, préférences qui évoluent doucement et décisions suivantes adaptées. Aucun effet sur les intentions du vrai robot.
- [x] Tests unitaires avec faux sockets et mémoire persistante, y compris reprise, refus pour zone/connexion, apprentissage négatif et absence d'effet des résultats incertains.
- [x] **Quatre essais MuJoCo vérifiés** : [A : 12 commandes, 1,242 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175133570), [B : 12 commandes, 0,820 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175696383), [C : 24 commandes, 1,399 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176018018), [D : 24 commandes, 2,574 mm](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817). `robot.stop` confirmé ; résultat **`no_progress_observed`**, préférence `explore` 0 → −0,075 **pour chaque base CI éphémère**.
- [ ] **Priorité P0a :** expliquer pourquoi `walk` est exécutée à la vitesse prévue, mais le tronc n'a progressé que de **0,820 à 2,574 mm** ; examiner en **lecture seule** contacts des pieds, commandes d'articulations, pose et dynamique sans changer la sécurité OEM.

**Portée et verdict :** 142 tests Python dont le renforcement de l'accusé `robot.stop`, et boucle mesure → mémoire réellement exécutée sous MuJoCo. **Locomotion non validée** malgré `policy=walk` 23 fois sur 24 et `max_applied_vx≈0,12 m/s`. Le résultat d'acceptation de la translation reste `NOT_MET` (confirmé sur la [CI finale #40176410817](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) : 24 commandes, **2,574 mm** de translation, dérive 0,192 mm, `robot.stop` confirmé ; le workflow technique est **réussi** sans déclarer de marche). Un seul essai par lancement sur la branche expérimentale ; la CI principale et le robot réel ne reçoivent aucune commande.

## Phase 3 — Boucler perception, décision et action dans MuJoCo (V1b)

**But :** démontrer la première autonomie observable, sans modifier le contrôle moteur officiel.

Travaux :
1. Ajouter un adaptateur de perception qui lit les états `robotd` et flux `tofd` simulés puis produit le contrat de la phase 1. Commencer par injecter des **événements fictifs étiquetés comme tels** pour les objets non encore détectés par caméra.
2. Construire un adaptateur d'intentions JSON-RPC vers les seules opérations documentées et autorisées de `robotd`, avec liste blanche, vitesse/zone limitées, durée de validité et arrêt sûr en cas de perte de données.
3. Ne jamais bloquer la boucle motrice sur SQLite, la perception, l'IA ou une requête réseau. `robotd` conserve ses protections.
4. Tester une séquence complète : nouveauté → inspection sûre → résultat observé → souvenir SQLite → comportement ultérieur adapté.
5. Ajouter des scénarios de capteur absent, obstacle, risque de chute, batterie simulée faible, interruption de connexion et reprise. Mesurer collisions, arrêts de sécurité, latences, décisions par minute et répétitions.

**Critère de sortie :** démonstration rejouable de la boucle complète, sans commande directe de servomoteur, tests d'échec concluants et mesures enregistrées. Aucun résultat MuJoCo ne vaut validation sur matériel.

## Phase 4 — Vision et interactions sociales (V2)

**But :** remplacer progressivement les événements fictifs par une perception mesurable.

Travaux :
1. Brancher `mediad --sim-camera` / `media.frame` dans une scène adaptée et mesurer le coût CPU et la cadence de simulation.
2. Développer la détection **multi-classe** d'objet, personne, chien et chat ; distinguer catégorie, suivi temporel et identité individuelle.
3. Préparer sur PC des données locales privées pour Nessquick et Kitty ; évaluer précision, rappel, faux positifs et option « inconnu » avant toute prétention à la reconnaissance individuelle.
4. Pour Malo, privilégier une identification volontaire ou une balise locale plutôt qu'une reconnaissance biométrique continue. Aucune donnée personnelle dans GitHub.
5. Ajouter des interactions discrètes et sûres (regarder, s'arrêter, s'approcher uniquement en zone contrôlée). Les mots-clés audio seront abordés après cette première validation visuelle.

**Critère de sortie :** jeu de validation séparé des données d'entraînement, métriques documentées et repli sûr sur « inconnu ». Les performances des modèles RKNN ne sont pas présumées à partir de MuJoCo.

## Phase 5 — Qwen local facultatif sur PC (V3)

**But :** améliorer l'interprétation d'une situation complexe sans rendre le robot dépendant du PC.

Travaux :
1. Créer un client réseau local isolé, temporisé et limité en fréquence ; aucune commande motrice issue d'une réponse Qwen.
2. Comparer d'abord Qwen multimodal 4B, puis 9B, selon qualité des hypothèses, latence, mémoire et consommation réellement mesurées sur le PC.
3. Enregistrer les propositions comme **hypothèses sourcées**, non comme observations ; n'apprendre d'un résultat que lorsqu'il est vérifié.
4. Tester PC indisponible, réponse tardive, incohérente ou fausse, et réseau coupé.

**Critère de sortie :** le robot simulé continue ses comportements locaux hors connexion ; aucune hallucination de Qwen n'autorise une action physique.

## Phase 6 — Portage embarqué et validation physique (V4 ; après disponibilité du robot)

**But :** faire fonctionner une version légère du cerveau sur Microduck avec les services officiels intacts.

Travaux :
1. Utiliser Rust pour le chemin embarqué critique si les mesures le justifient ; conserver des modules testables et une mémoire locale SQLite privée sous `/var/lib/robot/`.
2. Mesurer avec `scripts/resource-audit.sh` : RAM disponible, RSS des démons, partitions libres, CPU, fréquence et température en trois situations (repos, vision, vision + déplacement).
3. Vérifier la cadence et les délais de `robotd` avant et après intégration. Réduire ou suspendre la vision non essentielle en cas de surcharge, chaleur ou capteur incohérent.
4. Procéder à des essais physiques graduels dans une zone fermée sans risque de chute, sous supervision autour des enfants et animaux. Respecter les interfaces et le système de mise à jour constructeur.

**Critère de sortie :** fonctionnement autonome réel, garde-fous testés, mesures reproductibles et écarts avec la simulation documentés. Aucun budget de RAM, espace disponible, autonomie ou précision n'est considéré acquis avant mesure.

## Indicateurs communs et règle de validation

À chaque jalon, consigner :
- **Statut :** prévu / codé / tests unitaires passés / simulé / validé sur robot.
- **Décision :** motif de l'intention, capteurs exploités, informations inconnues, possibilité de rester inactif.
- **Apprentissage :** souvenirs effectivement réutilisés, préférences modifiées seulement après résultat constaté.
- **Sûreté :** collisions, arrêts préventifs, délais de traitement, absence d'action en cas de perte de capteur.
- **Ressources :** CPU, RAM, température, cadence et disponibilité de `robotd`, mesurées seulement dans l'environnement correspondant.
- **Vision :** précision, rappel, faux positifs, identités inconnues et performances en conditions variées.

Les documents et les tests doivent toujours distinguer un **test logiciel**, une **simulation** et un **essai sur robot physique**. Ne jamais publier de secret, image, voix, souvenir ou identité personnelle.

## Ordre de travail actualisé — voir le plan canonique

**Source de vérité de l'exécution :** [plan directeur F0–F8](plan-action.md), avec P0/P1 locomotion en chantier L séparé et suspendu, dépendances, critères de passage et trois prochaines PR. Les tableaux P0–P8 antérieurs ne représentent plus les priorités actuelles.

- **J1 — cerveau/perception contractuelle :** prototype codé et testé ; la reconnaissance visuelle et les capteurs réels restent à faire.
- **J2a–J2c — services officiels, zone plane :** vérifiés dans MuJoCo ; pas sur matériel.
- **J2d–J2e — commande bornée, arrêt, résultat, mémoire SQLite :** exécutés en simulation ; **aucune progression locomotrice démontrée**.
- **P0a terminé et fusionné :** mesure passive des articulations et de la politique (contacts dynamiques non exposés). **P0b en PR #12 :** comparaison `stand` / `walk` testée, insuffisance de marche confirmée, cause encore inconnue.
- **Ensuite :** compléter l'analyse de contacts et de propulsion avant P1a (translation de 10 mm sur trois essais) ; P2 (autonomie multi-cycles avec mémoire durable) et perception non motrice parallèles si P0 persiste.
- **Plus tard :** vision/social, Qwen PC facultatif, optimisation Rust/ressources, robot physique, puis automatisations optionnelles.

Les essais réussis en simulation ne valident **ni** la navigation domestique **ni** le stockage, la chaleur, la RAM et la batterie du Microduck réel.

## Références

- [README du projet](../README.md)
- [Audit matériel et limites](hardware-feasibility-audit-2026-10-25.md)
- [Simulateur officiel](https://github.com/pollen-robotics/microduck/blob/main/docs/robot/simulation.md)
- [Source simulation RL](https://github.com/pollen-robotics/microduck_rl)
- [Système Yocto officiel](https://github.com/pollen-robotics/microduck_yocto)

## Idées à tester plus tard (hors périmètre des jalons actuels)

Après la simulation d'autonomie et la perception : proposer des automatisations sous contrôle explicite, par exemple détecter l'ouverture d'une porte puis suggérer une alerte. Une détection fiable exigera un capteur adapté ou une validation visuelle mesurée ; tout envoi de message nécessitera un service de messagerie autorisé et une connexion. Aucune automatisation ou auto-modification de code n'est actuellement intégrée.
