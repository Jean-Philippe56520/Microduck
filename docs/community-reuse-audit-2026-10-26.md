# C1–C2 — Audit des développements communautaires Microduck et comparaison avec Companion

**26 octobre 2026 — audit statique et comparatif, sans intégration de code tiers.**

**Addendum C3 (même date) :** la [matrice comparée **par chantier** et le registre de références](community-reference-registry-2026-10-26.md) ajoutent les PR sur le dépôt OEM [#414 (maploc v2/mapd)](https://github.com/pollen-robotics/microduck/pull/414) et [#381 (proposition d'autonomie)](https://github.com/pollen-robotics/microduck/pull/381), ainsi que Quacksat, Quack-control, Microduck Lab et Microduck Studio. **C3 remplace toute conclusion implicite selon laquelle QuackNav devrait précéder la vérification d'une solution de cartographie constructeur.** Les PR sont ouvertes et ne constituent pas des fonctions officielles fusionnées.

## 1. Objet, sources et niveau de preuve

**Demande couverte :** (C1) inspecter plusieurs projets publics pertinents et leur **code**, au-delà des seules annonces ; (C2) comparer leurs responsabilités au code déjà présent dans [notre dépôt privé](https://github.com/Jean-Philippe56520/Microduck), afin de signaler les réutilisations et les doublons possibles **avant** tout nouveau développement.

- Référence interne : branche `main` consultée le 26/10/2026 ; [README](../README.md), [plan directeur](plan-action.md), [roadmap](roadmap.md), [audit constructeur R0](oem-reuse-audit-2026-10-26.md), [audit rétrospectif R1.5](r15-retrospective-reuse-audit-2026-10-26.md), [audit matériel](hardware-feasibility-audit-2026-10-25.md) et [protocole de réutilisation](development-reuse-protocol.md).
- Revue ciblée de fichiers Python et Rust des six dépôts publics cités ci-dessous, de leurs README et de leurs fichiers `LICENSE` racine. Les fichiers observés sont sur leur branche `main` à la date de lecture ; ils peuvent évoluer.
- **Preuve « codé »** : fonctions/classes effectivement présentes dans les sources lues. **Preuve « testé/simulé »** : résultats et commandes rapportés par les auteurs, parfois accompagnés de fichiers de tests ou de traces ; nous ne les avons **pas exécutés indépendamment**.
- Cette revue **n'est ni** un audit exhaustif des six arborescences, **ni** une vérification de vulnérabilités, **ni** une certification de licences de modèles/poids/datasets, **ni** un test d'intégration, **ni** une validation sur le Microduck réel.
- Aucun modèle, poids, média, code externe, sous-module Git ni comportement moteur n'a été importé dans notre dépôt. Aucune donnée privée n'a été consultée.

## 2. Notre socle : capacités effectivement présentes

| Responsabilité | Code existant dans Companion | Statut et limite |
| --- | --- | --- |
| Motivations et arbitrage passif | [`autonomy.py`](../microduck_companion/autonomy.py), [`passive_rhythm.py`](../microduck_companion/passive_rhythm.py), [`passive_learning.py`](../microduck_companion/passive_learning.py), [`passive_resilience.py`](../microduck_companion/passive_resilience.py) | Codé et testé sur événements fictifs ; **propose** `observe/listen/idle/rest`, n'exécute pas le mouvement, ne mesure pas l'énergie physique. |
| Souvenirs, catégories et lieux | [`episodic_memory.py`](../microduck_companion/episodic_memory.py), [`uncertain_spatial_memory.py`](../microduck_companion/uncertain_spatial_memory.py) et modules F4 | SQLite et repères **fictifs incertains** ; **pas** de SLAM, d'odométrie exploitable ou de carte navigable réelle. |
| Mémoire image/son multi-vues | [`multiview_pattern_memory.py`](../microduck_companion/multiview_pattern_memory.py), M1-A/B/B2, [évaluation R2-B](../microduck_companion/r2b_independent_capture_eval.py) | Comparateurs et bancs hôte ; une voie M1-B expérimentale avec garde `r2a_single_writer`. Pas d'identité d'instance fiable ni de modèle validé sur RK3566. |
| Consultation PC | [`selective_pc_policy.py`](../microduck_companion/selective_pc_policy.py), [`ollama_local_client.py`](../microduck_companion/ollama_local_client.py) | Contrat et client réseau local testés contre des réponses fictives ; **pas** de véritable Qwen validé, pas d'ordre moteur. |
| Perception OEM et sécurité | Contrats R1, F3-C/E, F5/F6 ; [audit R0](oem-reuse-audit-2026-10-26.md) | Parseurs/fixtures et garde de ressources ; `robotd` demeure seul responsable des moteurs, `mediad` et `tofd` des acquisitions. Pas de capteur matériel intégré. |

**État du chantier actif inchangé :** [R2-B+1 audio physiquement réenregistré → R2-B+2 visuel confusable → R2-C comparaison → R2-D mémoire](r2-follow-up-execution-plan-2026-10-26.md). Le présent audit **ne prouve pas** la faisabilité matérielle et **ne remplace pas** ces évaluations.

## 3. Matrice de comparaison des six projets

### A — GC-RENCAO / microduck-companion

**Sources consultées :** [`life.py`](https://github.com/GC-RENCAO/microduck-companion/blob/main/life.py), [`brain.py`](https://github.com/GC-RENCAO/microduck-companion/blob/main/brain.py), [`navmap.py`](https://github.com/GC-RENCAO/microduck-companion/blob/main/navmap.py), [`actions.py`](https://github.com/GC-RENCAO/microduck-companion/blob/main/actions.py), [README](https://github.com/GC-RENCAO/microduck-companion).

- **Codé :** boucle comportementale `Life` à 10 Hz, réaction à la présence et à la main suivies par le navigateur, planificateur et « voix » Ollama, file d'actions. Navigation A* sur une carte **extraite de la scène MuJoCo**, donc connue par le simulateur, et non reconstruite par les capteurs du vrai robot.
- **Preuve annoncée :** démonstration et tests de simulation ; auteur explicite **aucune validation sur robot réel**. Le mode réel évite de lancer spontanément la marche sans position fiable.
- **Chevauchement :** comportement F2 (motivations, attention, repos), contrat PC F5. **Manque chez nous :** démonstration interactive/gestuelle aboutie et actions effectivement jouées en simulation.
- **Risque :** son LLM propose des actions qui vont directement à la file d'ordres `robotd`, contraire à notre séparation Qwen/contrôle moteur si repris tel quel ; la carte du simulateur donne une information absente du robot réel. Pas de mémoire épisodique multimodale équivalente vérifiée dans les fichiers consultés.
- **Décision : `ETUDIER PLUS TARD` les patterns de réactions et leur testabilité ; `NE PAS IMPORTER` le cerveau moteur, la file d'actions ni la navigation « vérité terrain » dans R2.**

### B — samoxis / microduck-brain

**Sources :** [`brain.py`](https://github.com/samoxis/microduck-brain/blob/main/src/microduck_brain/brain.py), [`hazards.py`](https://github.com/samoxis/microduck-brain/blob/main/src/microduck_brain/hazards.py), [`runner.py`](https://github.com/samoxis/microduck-brain/blob/main/src/microduck_brain/runner.py), [tests](https://github.com/samoxis/microduck-brain/blob/main/tests/test_brain.py), [README](https://github.com/samoxis/microduck-brain).

- **Codé :** machine à états `Brain.tick(Inputs) -> Command` pure, détection ToF de petits obstacles et de vides, mémoire temporaire des dangers en repère odométrique ; `runner.py` reçoit `tofd`/`robotd` et envoie `robot.move`/`robot.stop`.
- **Preuve annoncée :** 176 tests, traces de simulation et parcours de 300 s (0 chute annoncée), **pas de robot réel**. Les résultats de collisions du simulateur intégral ne couvrent pas tous les contacts.
- **Chevauchement :** contrats sécurité et réactions prudentes ; **mais pas de doublon** de notre F4-B, qui ne sait ni piloter, ni détecter un vide. Apport potentiellement important pour **l'étude** d'un futur évitement.
- **Risque :** deuxième boucle active commandant la locomotion à ~20 Hz, sécurité de sol dépendante du capteur frontal et de l'odométrie, angles morts ; incompatibilité d'autorité si une autre navigation ou le futur M9 commande simultanément.
- **Décision : `CANDIDAT A AUDIT CIBLE FUTUR` du modèle de danger et des replays ; `NE PAS BRANCHER` sur `robotd` dans R2.**

### C — andreagenovese / quacknav

**Sources :** [`quack-nav/src/lib.rs`](https://github.com/andreagenovese/quacknav/blob/main/quack-nav/src/lib.rs), [`cliff.rs`](https://github.com/andreagenovese/quacknav/blob/main/quack-nav/src/cliff.rs), [`places.rs`](https://github.com/andreagenovese/quacknav/blob/main/quack-nav/src/places.rs), [`explore/mod.rs`](https://github.com/andreagenovese/quacknav/blob/main/quack-nav/src/explore/mod.rs), [`Cargo.toml`](https://github.com/andreagenovese/quacknav/blob/main/Cargo.toml), [mesures](https://github.com/andreagenovese/quacknav/blob/main/docs/results.md).

- **Codé :** bibliothèque/daemon Rust avec `maploc`, repères nommés persistés, protection de bords, exploration par frontières, suivi d'itinéraires et outils JSON-RPC. Le module `maploc` est fourni **dans son workspace**. Le `Cargo.toml` dépend de `duck-ipc-proto` et `kinematics` au tag constructeur **`daemon-v0.17.6`**.
- **Preuve annoncée :** essais MuJoCo et « paper twin », 46/51 trajets réussis dans une campagne publiée, **sans validation physique** ; le rapport annonce 3 critères sur 7 remplis et 4 partiels.
- **Chevauchement :** **aucun système équivalent de SLAM/navigation** chez nous ; les repères historiques F4-B ne sont pas une carte exploitable. QuackNav est **complémentaire**, pas un remplacement direct de la SQLite cognitive.
- **Risque :** compatibilité **non vérifiée** entre le tag OEM de QuackNav et nos sous-modules épinglés dans R0, coût mémoire/CPU/RSS inconnu sur notre futur RK3566, concurrence avec toute autonomie OEM et incertitudes de sécurité près des escaliers.
- **Décision : `PRIORITE D'ETUDE POUR LA NAVIGATION FUTURE`, sous réserve de comparer interfaces exactes, ressources et propriétaire unique des intentions physiques. `HORS R2`.**

### D — Smartulf123 / microduck-companion

**Sources :** [`voice.py`](https://github.com/Smartulf123/microduck-companion/blob/main/voice.py), [`eyes.py`](https://github.com/Smartulf123/microduck-companion/blob/main/eyes.py), [`faces.py`](https://github.com/Smartulf123/microduck-companion/blob/main/faces.py), [`duck_adapter.py`](https://github.com/Smartulf123/microduck-companion/blob/main/duck_adapter.py), [`smoke_test.py`](https://github.com/Smartulf123/microduck-companion/blob/main/smoke_test.py).

- **Codé :** reconnaissance de commandes vocales locales avec `pywhispercpp`, tables de mots, webcam sur PC, détecteur de personnes YOLOX-Nano et suivi par histogrammes de couleurs ; biométrie YuNet/SFace facultative dans le projet. Adaptateur JSON-RPC vers `robotd`.
- **Preuve annoncée :** démonstration sous Windows/WSL2 et simulateur officiel ; **pas testé sur vrai Microduck**. Les révisions constructeur données dans le README correspondent aux préfixes utilisés par notre audit R0, sans preuve d'intégration avec notre cerveau.
- **Chevauchement :** F3 (étude perception), F5 (PC facultatif), et futures commandes sonores. **Différence :** la transcription de *paroles* n'est pas la reconnaissance d'un même bruit familier au fil du temps étudiée en R2-B+1.
- **Risque :** calculs et webcam **sur ordinateur**, pas validés en embarqué ; reconnaissance faciale persistante non justifiée pour l'identification volontaire de Malo ; faux positifs et commande moteur directe.
- **Décision : `REUTILISER DES IDEES DE DECOUPLAGE` voix→intention et d'évaluation, pas les données faciales ni l'adaptateur moteur. À considérer ultérieurement, pas comme réponse à R2-B+1.**

### E — digows / microduck-twin

**Sources :** [lanceur `microduck-twin`](https://github.com/digows/microduck-twin/blob/main/microduck-twin), [`duck-audio/src/main.rs`](https://github.com/digows/microduck-twin/blob/main/duck-audio/src/main.rs), [`duck-audio/src/field.rs`](https://github.com/digows/microduck-twin/blob/main/duck-audio/src/field.rs), [`deps.env`](https://github.com/digows/microduck-twin/blob/main/deps.env), [README](https://github.com/digows/microduck-twin).

- **Codé :** environnement de simulation autour des démons officiels et de MuJoCo, avec canal audio synthétique (distance, délai, occultation par murs, retour de sa propre voix) et panneaux/outils simulés. Dépendances OEM épinglées dans `deps.env` à des commits différents de nos références R0.
- **Chevauchement :** notre infrastructure MuJoCo et scripts `duck-sim`. **Apport distinct :** stimuli audio réciproques et environnement sensoriel de test. Les températures/batteries simulées ne sont **pas** des mesures physiques.
- **Risque :** deuxième lanceur/stack de simulation, risque de dérive des révisions et de duplication de notre infrastructure. Le README contient des formulations de statut à recontrôler contre les tests précis.
- **Décision : `OPTION POUR UN BANC D'INTEGRATION AUDIO FUTUR`, après audit de l'interface et des révisions. Ne remplace **pas** les prises sonores physiques indépendantes exigées en R2.**

### F — Lulzx / microduck-backflip

**Sources :** [environnement de backflip](https://github.com/Lulzx/microduck-backflip/blob/main/src/mjlab_microduck/tasks/microduck_backflip_env_cfg.py), [protocole d'évaluation](https://github.com/Lulzx/microduck-backflip/blob/main/docs/backflip.md), [README](https://github.com/Lulzx/microduck-backflip).

- **Codé :** environnement d'entraînement d'une nouvelle politique de saut arrière et critères stricts de décollage, rotation aérienne, réception ; chaîne PPO/CUDA expérimentale.
- **Preuve annoncée :** démonstration **assistée** en simulation, et non saut autonome validé sur robot. Le README distingue la licence du code Apache-2.0 de certains modèles 3D déclarés **CC BY-SA-NC**.
- **Chevauchement :** uniquement notre chantier locomotion L/P1 (suspendu), pas la mémoire/attention R2. Les politiques officielles et l'autorité motrice OEM demeurent prioritaires.
- **Décision : `HORS PERIMETRE` de C1–C2/R2 ; référence documentaire éventuelle pour un futur chantier locomotion.**

## 4. Verdict de non-duplication, par fonction

| Fonction envisagée | Existant chez nous | Apport communautaire | Décision avant tout développement |
| --- | --- | --- | --- |
| Curiosité, humeur, repos et réaction sociale | F2/F4, **propositions fictives** | GC `life.py` anime en simulation | Comparer les états et interfaces au M9 constructeur **avant** de coder un deuxième cerveau embarqué. Pas de greffe directe. |
| Mémoire d'événements, associations et apprentissage progressif | SQLite F1/F4/M1, corrections et provenance | Aucun des six dépôts ne démontre une mémoire multimodale personnelle identique sur les fichiers étudiés | **Poursuivre notre voie unique M1-B** ; ne pas créer une deuxième SQLite ni conclure qu'un groupe d'images identifie physiquement un objet. |
| Reconnaître le même objet et le même bruit malgré une autre prise | Bancs F3/M1/R2-B, qualité insuffisamment démontrée | Smartulf reconnaît des *commandes*, GC des *gestes* ; Twin simule l'air | **Ne change pas R2-B+1 / R2-B+2**. Corpus indépendant, négatifs proches, faux rapprochements et `unknown` restent nécessaires. |
| Évitement d'obstacles / de vides | Sécurité OEM et contrats de perception ; pas d'algorithme Companion navigable | Brain et QuackNav, avec replays et tests de simulation | **Ne rien porter maintenant** ; plus tard, audit croisé des contraintes ToF, odométrie, deadman et version des API. Ne pas faire tourner deux contrôleurs concurrents. |
| Carte, localisation, itinéraires et lieux nommés | F4-B stocke des repères fictifs, pas de SLAM | QuackNav ajoute une vraie chaîne de cartographie/navigation expérimentale ; GC a une carte d'appartement « vérité simulation » | **QuackNav à étudier** comme composant possible, non remplacé par F4-B ; pas d'annonce de navigation domestique sûre. |
| Assistant vocal et modèles sur PC | F5 contrat de consultation non bloquante, aucune réelle interaction multimodale | Smartulf Whisper/voix PC ; GC Qwen dialogue et outils | Préserver **Qwen hypothèse non vérifiée, jamais ordre moteur** ; ne pas réimplémenter le client Ollama ni reprendre la biométrie. |
| Simulation de perception acoustique | MuJoCo OEM et bancs audio sur fichiers | Twin audio simulé | Étudier comme **complément** et non nouveau simulateur officiel ; valider le son réel séparément. |
| Nouvelles politiques acrobatiques | Chantier L suspendu | Backflip PPO assisté | Aucune intégration ; sécurité et validation physique non établies. |

## 5. Compatibilité, licences et risques bloquants

1. **Autorité moteur :** `robotd` garde la propriété des actionneurs et de la sécurité constructeur. Des projets communautaires envoient des intentions `robot.move` via JSON-RPC ; cela n'en fait pas des contrôleurs compatibles entre eux ou sûrs en coexécution. Aucun LLM ne doit arbitrer directement les moteurs.
2. **Versions :** notre [audit OEM R0](oem-reuse-audit-2026-10-26.md) cite `microduck` `942e58e3...` et `microduck_rl` `b02fdea4...`. QuackNav suit le tag `daemon-v0.17.6`, Twin d'autres commits, GC apporte un patch de visualisation en simulation. **Les compatibilités des API, scènes et politiques n'ont pas été validées.** Recontrôler les pointeurs actuels des sous-modules avant toute PR de portage.
3. **Sensoriel :** ToF frontal 8×8 ≠ LiDAR 360°, une carte simulée ≠ localisation physique, une détection de danger simulée ≠ garantie anti-escalier. Les données de caméra/microphone et les seuils n'ont pas été vérifiés sur notre futur appareil.
4. **Ressources :** aucune mesure disponible de charge RAM, RSS, stockage, température, énergie ou délais moteurs après ajout de ces projets sur RK3566. Priorité à [`scripts/resource-audit.sh`](../scripts/resource-audit.sh) **lorsque le robot sera disponible**, sans déclencher de mouvement non autorisé.
5. **Vie privée :** pas d'identification faciale automatique d'un enfant, pas de stockage d'exemples privés ou de médias dans GitHub. Une catégorie personne/chat/chien ne prouve pas une identité individuelle.
6. **Licences :** les **six dépôts** disposent d'un `LICENSE` racine Apache-2.0 observé ; cela n'autorise **pas** à supposer les mêmes droits sur poids, médias, données de tests ou modèles 3D (le README Backflip mentionne notamment des fichiers 3D CC BY-SA-NC). Aucune copie effectuée ; en cas de réutilisation, auditer fichier par fichier les notices/attributions et les dépendances.
7. **Preuve et tests :** nous avons vérifié l'existence de fichiers sources et de certains tests, **sans les lancer**. Les chiffres de simulation publiés sont **déclarés par leurs auteurs** et ne sont pas des reproductions locales. Aucune CI de notre dépôt n'a été lancée pour cette revue documentaire.

## 6. Décision C1–C2 et clôture du périmètre

- **C1 — fait :** six dépôts publics vérifiés et sources ciblées inspectées, licences racine contrôlées. Audit statique **non exhaustif**.
- **C2 — fait :** matrice de responsabilités et doublons comparée aux modules du `main` privé, risques et réutilisations différées explicités.
- **À conserver immédiatement :** le fonctionnement actuel et le [protocole « réutiliser avant de créer »](development-reuse-protocol.md). **Aucun import de code, fusion de service ou nouvelle mémoire** n'est justifié par cette seule revue.
- **Pour un futur lot navigation séparé :** examiner d'abord QuackNav (API, maploc, ressources et propriétaire unique de l'autorité), puis les mécanismes de garde/replay de microduck-brain. Il ne s'agit pas d'un feu vert à la marche réelle.
- **Pour le prochain lot R2-B+1 :** conserver les bancs existants et chercher des enregistrements indépendants de bruits réels, non de parole ; ces projets communautaires ne remplacent pas les preuves manquantes.
- **Reste à faire, en dehors de C1–C2 :** revue approfondie de sécurité/licences d'un composant précis, comparaison effective de versions/pointeurs Git, essais reproductibles sur banc commun, puis intégration soumise à une PR distincte et à des tests ; **validation robot physique ultérieure**.

**Statut final : audit et comparaison documentés ; aucun code externe adopté, aucun test exécuté dans cette revue, aucune validation matérielle.**
