# Plan directeur opérationnel — Microduck Companion

**Référence unique pour les prochains travaux · version du 25 octobre 2026 · dépôt `Jean-Philippe56520/Microduck` · branche de référence `main`.**

**Décision : priorité à l'autonomie cognitive et aux perceptions *sans déplacement*.** Le diagnostic de locomotion P0a–P0j est conservé, mais les nouveaux essais moteurs sont **mis en attente**, pas déclarés résolus. Le précédent ordre P0 → P1 → P2 est archivé dans [l'ancien plan](plan-action-historique-2026-10-25.md). La [roadmap](roadmap.md) conserve les résultats historiques, le [plan MuJoCo](mujoco-integration-plan.md) décrit les procédures et l'[audit matériel](hardware-feasibility-audit-2026-10-25.md) répertorie les limites connues. **Ce fichier définit seul les phases et lots prioritaires.**

## 1. Mission, contrat de fonctionnement et limites

Créer un Microduck **curieux, explorateur, social et peu bavard**. Sa boucle cible est : percevoir → comparer aux souvenirs → apprécier nouveauté, motivations et risques → choisir une intention sûre (y compris ne rien faire) → agir dans les limites autorisées → constater un effet → mémoriser et adapter lentement ses choix. Curiosité, sociabilité, jeu, énergie et prudence sont **des variables de décision**, ni émotions ni conscience.

**Architecture non négociable :**

- **Local et autonome :** les réactions rapides, les motivations, la mémoire utile, le repos et les décisions essentielles fonctionnent sans PC ni Internet. Préférer un cerveau léger, puis Rust pour le portage embarqué si les mesures le justifient ; SQLite privée et persistante.
- **Constructeur préservé :** `robotd` reste seul responsable des moteurs, de la boucle ~50 Hz, du deadman, des politiques ONNX et des protections. `mediad` gère caméra et audio ; `tofd` fournit le ToF 8×8. Réutiliser leurs interfaces officielles et contrôler la provenance des messages.
- **Deux voies séparées :** une **voie cognitive passive** peut enregistrer une découverte ou choisir `observe`/`idle` sans autoriser de mouvement ; une **voie d'action physique** nécessite indépendamment capteurs, zone, état, délai et autorisation du contrôleur. Ne jamais transformer une perception d'objet ou un avis Qwen en certificat de sol.
- **Assistance facultative :** PC/Ollama/Qwen pour situations nouvelles ou contradictoires, avec délai et quota ; une réponse est une **hypothèse**, jamais une commande moteur ni un fait vérifié.
- **Vie privée :** pas de caméra/micro continuellement enregistrés, pas de données d'enfants ou animaux privés, de souvenirs identifiants ou de secrets sur GitHub ; préférer des jeux fictifs, stockage local privé et corrections possibles.
- **Mesure honnête :** distinguer `prévu`, `codé`, `test logiciel`, `test simulateur`, `validé sur robot`. Aucun résultat MuJoCo ne garantit autonomie énergétique, sécurité domestique, NPU ou performances thermiques.

**Sûreté :** un sol inconnu, un danger, une perte de ToF, des données périmées, une batterie insuffisante ou un état incohérent **interdisent tout déplacement**. Une observation passive reste possible si elle n'actionne aucun moteur et si sa source est exploitable. Une détection ToF 8×8 ne certifie pas escaliers, sol ni navigation dans toute la maison. Aucun essai autonome auprès d'enfants ou d'animaux.

## 2. État de référence vérifié (avant cette réorganisation)

| Sous-système | État constaté | Limite |
| --- | --- | --- |
| Prototype Python : motivations, choix, PerceptionSnapshot, expériences, SQLite | Codé et testé | Pas un exécutable embarqué validé |
| P2a : cycles fictifs et préférences | Test logiciel sur sessions persistantes | Résultats fictifs clairement étiquetés |
| P2b : 6 cycles passifs sur `robotd`/`tofd` dans MuJoCo officiel, base SQLite réouverte | Test simulateur confirmé ; 6 intentions `halt`, zéro moteur | Ni vision `mediad` intégrée ni exploration physique |
| Diagnostic locomoteur P0a–P0j | Test simulateur et relectures confirmés | P0i : 1,444 mm alpha / 1,968 mm VelStand ; seuil indicatif 10 mm non atteint ; cause inconnue |
| P0j : charges normales du solveur P0e | Replay vérifié : 127/127 relevés de marche avec deux pieds en charge | Ni force XY signée de propulsion ni preuve de marche |
| Tests automatisés | [269 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230116442) | Nombre de tests ≠ nombre de fonctions validées |
| Détection chien/chat/personne/voix sur nos données | Non développée ni validée | Un détecteur OEM d'autres Microducks ne remplit pas ce besoin |
| Qwen intégré au cerveau ; Rust embarqué ; robot physique | Non validés | Microduck physique indisponible ; ressources réelles inconnues |

**Éléments existants à réutiliser** : `microduck_companion/perception.py` (`PerceptionEvent`, `PerceptionSnapshot`, provenance/TTL), `autonomy.py` (`AutonomyBrain`, motivations), `episodic_memory.py` (SQLite), `sim_bridge.py` et `sim_passive_cycles.py` (télémétrie et journaux passifs). Ne pas reconstruire un deuxième cerveau, un deuxième schéma de mémoire ni un moteur maison.

## 3. Ordre des phases et règles de passage

| Phase | Priorité / état | Livrable de fin de phase | Prérequis déterminant |
| --- | --- | --- | --- |
| **F0 — Socle existant** | Acquis au niveau prototype/tests ; maintien continu | Contrats, démos et sécurité de base documentés ; CI verte | Aucun |
| **F1 — Perception passive et mémoire d'observations** | **En cours : F1-A/F1-B/F1-C fusionnés et testés, F1-D prochain** | Événements sourcés, inconnus, lecture différée SQLite, zéro moteur | F0 |
| **F2 — Autonomie cognitive sans locomotion** | Ensuite | Plusieurs décisions motivées, peu répétitives ; conséquence observée ; relecture après reprise | F1, mémoire F0 |
| **F3 — Vision et sons légers** | Ensuite, avec lots indépendants | Détection de *catégories*, suivi et signaux sonores mesurés ; `unknown` crédible | F1 ; banc d'essai et données autorisées |
| **F4 — Sociabilité et mémoires enrichies** | Après observations fiables | Rencontres, préférences, lieux incertains et interactions volontaires | F2 + F3 |
| **F5 — Qwen facultatif sur PC** | Après un cœur local fonctionnel | Hypothèses vérifiables avec timeout, quotas, repli hors réseau | F2 et contrats F3 |
| **F6 — Préparation embarquée / performances** | Préparation possible sur PC ; validation différée | Interfaces compactes, portage ciblé Rust, plan de mesure matériel | F1–F5 selon modules ; robot pour chiffres réels |
| **F7 — Validation progressive sur vrai Microduck** | **Suspendue à réception du matériel** | Mesures et tests physiques par sous-système, sécurité de mouvement surveillée | Robot disponible, ressources mesurées, fonctions pertinentes validées |
| **F8 — Fonctions optionnelles** | Après socle sûr | Alertes consenties et petits services sans dépendance pour autonomie locale | Fonction concernée validée |
| **L — Locomotion P0/P1, chantier indépendant** | **Mis en pause ; non résolu** | Preuve de translation puis de démarche dans le MuJoCo constructeur | Hypothèse testable, protocole mesuré, revue de sûreté |

**Passage de phase :** une phase n'est « terminée » que lorsque ses critères de sortie propres sont démontrés dans le bon environnement. On peut avancer **les fonctions sans moteurs** même si L reste bloqué. En revanche, **aucune exploration mobile automatique** ne s'ouvre tant que locomotion, sol et garde-fous ne sont pas validés séparément.

## 4. Détail phase par phase

### F0 — Maintenir le socle sans régression (existant)

**Portée :** conserver `robotd` et les politiques OEM, tests `unittest`, interface de perception versionnée et persistance SQLite. Réduire les risques de duplication des modules et maintenir README, roadmap, plan et audit cohérents. Le chiffre de 269 tests est **une référence au commit CI historique**, pas un objectif numérique.

**Sortie / contrôle permanent :** suite Python complète verte sur chaque PR, révisions constructeur indiquées lorsqu'elles interviennent, signalement explicite des sorties fictives, aucune donnée privée et aucun mouvement ajouté incidemment.

### F1 — Perception passive et traces sourcées (EN COURS, F1-A/F1-B/F1-C FUSIONNÉS ET TESTÉS)

**Objectif :** faire entrer une observation non motrice dans le cerveau, avec horodatage, source, confiance, catégorie éventuellement inconnue, puis mémoriser sa découverte. Ne pas faire croire que les capteurs du simulateur voient des objets : **MuJoCo n'émule ni caméra, ni microphones, ni NPU**.

**Lots de travail, dans l'ordre :**

- **F1-A — Contrat minimal d'événements passifs ([PR #24](https://github.com/Jean-Philippe56520/Microduck/pull/24), fusionnée et testée logiciellement).** Inspecter les interfaces existantes `perception.py`, `autonomy.py`, mémoire et la disponibilité documentaire de `mediad`. Réutiliser `PerceptionEvent`/`PerceptionSnapshot` ; ne changer la version qu'avec migration/tests. Définir la frontière entre observation, classification et autorisation de déplacement. Ajouter des fixtures fictives `objet familier` / `objet inconnu` / `signal sonore`, source, confiance, TTL, identifiant de suivi éphémère et conflit. **Pas de modèle de vision, pas de capture privée, zéro API moteur.** **Résultat F1-A :** [295 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40233207115), dont 26 nouveaux ; catégories `object_label` et `sound_label`, confiance, TTL, source déclarée et refus de contradictions, via [rapport F1-A](f1a-passive-observation-contract-2026-10-25.md). Les interfaces `mediad` observées dans le code OEM n'ont pas été raccordées : une chaîne `sensor` n'est pas une authentification. `keyword_stop` n'est pas un arrêt moteur.
- **F1-B — Adaptateur de lecture non motrice ([PR #25](https://github.com/Jean-Philippe56520/Microduck/pull/25), fusionnée et testée sur `main`).** Le module `passive_sources.py` lit des catégories de **fixtures par socket Unix local**, puis force `source=mock`, `environment=mock` ; il refuse usurpation de source, commandes/sécurité, trame > 8192 octets, âge > 2 s, doublons/séquences régressives et débit > 2 Hz. La sonde OEM `probe_official_mediad()` n'envoie **que `hello`** et exige chemin système, UID Unix local du pair, API 44 et révision épinglée pour un statut vérifié. **La sonde ne lit ni images, ni catégories OEM.** [315 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234054024), dont 20 nouveaux. **Aucun robot/daemon constructeur testé ; pas de véritable reconnaissance.** [Rapport F1-B](f1b-passive-source-2026-10-25.md).
- **F1-C — Journalisation passive et reprise ([PR #26 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/26), tests logiciels réussis).** `PassiveObservationJournal` ajoute un journal **dans la SQLite existante d'`ExperienceMemory`**, accepte uniquement les catégories fictives F1-B (`mock`), conserve `identified`/`unknown`/`conflict` sans promouvoir les hypothèses. Deux processus Python distincts ont rouvert **la même SQLite**, retrouvé 1 puis 2 occurrences de *catégorie* et prouvé que les temps monotones ne se réutilisent pas après redémarrage. **24 nouveaux tests** ; rétention logique 14 jours et limite 512 observations, pas d'identité animale, d'images, voix ou noms libres. [Rapport F1-C](f1c-passive-sqlite-memory-2026-10-25.md). Ce n'est pas une perception de capteur réel.
- **F1-D — Démonstration de bout en bout.** Enchaîner plusieurs observations sur fixtures fictives avec scénario nouveau / déjà vu / incertain / capteur perdu ; sauvegarde et relecture ; **aucune action motrice**. Si la source constructeur est disponible, documenter distinctement les preuves réelles acquises par cet adaptateur.

**Critères de sortie F1 :** au moins deux sessions indépendantes sur une seule SQLite ; fraîcheur, origine, conflits et confiance testés ; `unknown` maintenu si ambigu ; aucun mouvement ni faux `safe_area`/`floor_clear` ; suite CI verte ; rapport distinguant fixtures et services officiels. **F1-A, F1-B et F1-C fusionnés ; F1-C testé en logiciel, seulement sur fixtures, avec reprise interprocessus. F1-D (démonstration intégrée) reste à faire. La phase F1 demeure inachevée ; aucune perception physique réelle validée.**

### F2 — Intention et apprentissage comportemental sans déplacement

**Objectif :** relier les perceptions F1 aux motivations, à l'ennui, à la nouveauté et à la mémoire, sans forcer la boucle moteur à attendre l'IA.

**Lots :** F2-A intentions exclusivement passives (`observe`, `inspect`, `listen`, `idle`, `rest`) sans exécuter `look_at` ou marche ; F2-B arbitre des motivations, repos, cooldown et décisions non répétitives ; F2-C conséquences **vérifiées** (nouvelle information, observation répétée, tentative refusée) et préférences lentement ajustées, sans « entraîner le modèle » ; F2-D scénarios multi-sessions, panne/retard de capteur, budget de calcul et latence. **Un événement fictif n'est jamais une récompense physique.**

**Critères de sortie F2 :** un scénario déterministe « nouveau → observer → retrouver le souvenir → décider autrement », contrôle `idle` et `rest`, un échec capteur qui n'autorise rien de dangereux, préférences stables et corrigibles, persistance après arrêt, tests et métriques de fréquence/répétition.

### F3 — Catégories visuelles et signaux sonores

**Objectif :** distinguer *catégorie* et *individu* ; mesurer sur données privées/autorisées et synthétiques avant toute confiance.

**Lots :** F3-A protocole de données annotées et train/test séparés, provenance/licences, jeux sans images personnelles dans GitHub ; F3-B ligne de base de détecteurs légers pour objet, jouet, personne, chien, chat, avec classe `unknown` et suivi ; F3-C routeur d'événements `mediad` si interface contrôlée, détection sonore/mots-clés légers (`Microduck`, `stop`, `viens`) sans dialogue obligatoire ; F3-D benchmark précision/rappel, matrice de confusion, faux positifs, latence et consommation mesurées dans l'environnement disponible.

**Critères de sortie F3 :** métriques par classe, ensemble d'évaluation indépendant, gestion de la fausse reconnaissance et de l'inconnu ; toute validation RKNN/INT8/NPU reste **à mesurer sur la carte cible**. Le mot « stop » vocal **ne remplace jamais** un mécanisme matériel ou `robotd` d'arrêt sûr.

### F4 — Comportement social, personnalité légère et plusieurs mémoires

**Objectif :** expériences utiles, familiarité progressive, préférences non répétitives, mouvements uniquement si voie motrice déjà autorisée.

**Lots :** F4-A mémoire sémantique (objets/propriétés/confiance) et comportementale (succès/échecs) ; F4-B repères spatiaux avec incertitude, **sans inventer une carte de maison** ; F4-C interactions brèves et silencieuses (regard intentionnel non exécuté avant validation, sons courts, jeu simulé, repos) ; F4-D association **volontaire** d'identités sous contrôle humain. Distinguer « chien » de Nessquick et « chat » de Kitty ; une balise/interaction explicite est préférable à la biométrie constante. Pour Malo, contrôle parental et consentement, jamais de photos ou identifiants personnels dans le dépôt.

**Critères de sortie F4 :** mémoire observée vs hypothèse distinguées, correction et oubli local possibles, taux d'erreurs documenté, absence de stockage continu média, comportements interrompus par incertitude et aucun signe d'« émotion réelle » revendiqué.

### F5 — Assistant Qwen facultatif sur PC local

**Lots :** F5-A contrat de requête/réponse typé (`observations`, `hypotheses`, `confidence`, `source`, `ttl`) et interdiction des ordres moteurs ; F5-B Ollama + comparaison Qwen multimodal **4B puis 9B** seulement si pertinent pour qualité/latence/consommation du PC ; F5-C déclenchement parcimonieux (nouveauté/contradiction), délais, quotas et repli local ; F5-D adversarial : hallucinations, sortie malformée, PC absent, coupure réseau et contradiction avec capteurs.

**Critères de sortie F5 :** un cycle complet continue **sans PC** ; aucun avis Qwen n'écrase une observation certifiée, n'autorise une zone ou ne pilote `robotd`. Mesures réelles de latence et de coût matériel sur le PC, sans accélération GPU/NPU supposée.

### F6 — Préparation embarquée et optimisation

**Lots :** F6-A recenser fonctions indispensables hors PC, interfaces JSON-RPC OEM, installation/arrêt propre et stockage SQLite dans `/var/lib/robot` si confirmé ; F6-B comparer Python prototype à un noyau Rust ciblé seulement si la simplicité/mesure le justifie ; F6-C budget d'événements, débit et contrôle de la consommation ; F6-D plan d'audit `scripts/resource-audit.sh` au repos, en vision et en déplacement **uniquement une fois le robot disponible et la locomotion sûre**.

**Critères de sortie F6 :** intégration préparée sans remplacer `robotd`/`mediad`/`tofd`, aucune fonction critique liée au réseau ou PC, profils explicites et gardes thermiques prévus. RAM libre, RSS, stockage utilisable, fréquence, température et autonomie **ne sont pas validés tant que l'unité physique n'a pas été instrumentée**. Distinguer Zero 3W/IMX219 de Seeed beta/GC2093 et la capacité annoncée des partitions réellement disponibles.

### F7 — Validation physique, après réception

**Ordre obligatoire :** identifier exactement carte/révision, système constructeur et interfaces ; mesurer RAM libre, RSS, températures, stockage et cadence au repos ; tester observations et mémoire privées hors réseau ; valider réactions stationnaires ; seulement ensuite mouvements courts **sur sol contrôlé, sous surveillance, enfants/animaux éloignés**, après résolution indépendante du chantier L. Tester arrêts, panne de ToF, caméra absente, batterie faible, réseau coupé et reprise.

**Critères de sortie F7 :** chaque capacité estampillée `validé sur robot` uniquement avec ses traces matérielles ; aucun chiffre MuJoCo converti en autonomie batterie ou fiabilité escaliers. Un prototype qui pense sans bouger peut être validé avant la marche.

### F8 — Options après les fonctions essentielles

Exemple : **porte ouverte → alerte e-mail** sur événement fiable et configuration consentie. Prévoir permission, destinataire explicite hors dépôt, anti-répétition, journal minimal, coupure réseau et absence d'alertes mensongères. Fonction réseau **facultative** et distincte de l'autonomie locale ; ne pas la déclarer codée avant tests.

## 5. Chantier L — locomotion constructeur (pause contrôlée)

**État : non résolu, non effacé.** Dernière comparaison P0i : **1,444 mm** alpha, **1,968 mm** VelStand sur une séquence courte dans MuJoCo OEM (deux arrêts confirmés, sous le seuil expérimental 10 mm). Relecture P0j : **127/127** relevés en marche avec les deux pieds chargés, différence de répartition ; ni force de traction signée ni origine du défaut démontrées. [Historique complet](plan-action-historique-2026-10-25.md).

**Reprise uniquement sur demande ciblée**, avec une hypothèse falsifiable (ex. force tangentielle **signée** et vitesse relative pied/sol dans le solveur d'origine), plan de collecte minimal, état initial/fin, invariants constructeur et budget d'essais fixé. Aucune retouche arbitraire des gains/politiques, aucune augmentation automatique de vitesse. À terme, l'exploration mobile exige d'abord une translation mesurée et reproductible (ancien critère de diagnostic : ≥10 mm sur trois essais indépendants, séparée de la dérive), puis une démarche soutenue et sûre, et ensuite une validation physique surveillée. **F1–F6 n'attendent pas cette preuve pour les parties immobiles.**

## 6. Les trois prochains lots de PR, une seule à la fois

| Ordre | PR de travail | Fichiers/prototypes concernés | Preuve obligatoire |
| --- | --- | --- | --- |
| **1 (prochaine après F1-C)** | **F1-D — Démonstration passive complète** | Chaîner F1-A + F1-B + F1-C : nouveau/ancien/inconnu/conflit, panne source et reprise SQLite ; aucune reconnaissance réelle | Deux sessions, données `mock`, récit de nouveauté de *catégorie* seulement, aucun ordre moteur ; tests intégrés et CI verte ; critères de sortie F1 vérifiés |
| **2 (seulement après validation F1-D)** | **F2-A — Intentions cognitives passives** | Utiliser les perceptions fiables et souvenirs pour proposer `observe`/`listen`/`idle`/`rest` sans exécuter de mouvements | Scénarios déterministes, refus prudent des données manquantes, aucune action motrice et CI verte |
| **3 (après F2-A)** | **F2-B — Diversité des motivations et repos** | Arbitre local des intentions, cooldown et limitation des répétitions | Mesurer diversité/répétition, choix possible de ne rien faire, tests de mémoire, sans parler de conscience |

**Après F1-D :** vérifier tous les critères de sortie F1 **avant** F2-A. Aucun lot ultérieur n'est lancé automatiquement. L'ordre est **conditionnel à la preuve de la PR précédente**, pas à une date. Ne pas fusionner une PR si elle masque des tests en échec, supprime un contrôle de sécurité ou revendique une capacité sensorielle non mesurée.

## 7. Protocole de travail pour chaque lot

1. **Inspecter `main` avant modification** : README, ce plan, audit, sous-modules épinglés, fichiers directement concernés et tests existants. Reprendre l'existant, pas les hypothèses d'anciens échanges.
2. **Une branche, une intention, une PR** ; changement minimal, licences OEM préservées, pas de secrets ni identités dans GitHub.
3. **Ajouter des tests ciblés** : cas nominal, `unknown`, source absente ou fausse, horloge périmée, conflit, redémarrage, échec fermé. Comparer les métriques réellement observées.
4. **Exécuter la CI** et, seulement si cela apporte une preuve nécessaire, la simulation officielle ; ne pas déclencher d'essai moteur lors d'une PR de cognition ou perception.
5. **Documenter trois niveaux** : ce qui est codé, ce qui est testé et l'environnement exact de la preuve. Donner l'URL PR, SHA ou CI, et les limites restantes.
6. **Mettre à jour le minimum nécessaire** : ce document pour l'état et la prochaine PR ; haut du README pour le résumé ; roadmap pour l'historique ; audit matériel uniquement si une nouvelle preuve matérielle change ses conclusions.
7. **S'arrêter à la PR achevée** et ne pas enchaîner automatiquement les lots suivants.

**Mesures suivies dans la durée :** taux de cycles locaux autonomes sans PC, fraîcheur et origine des perceptions, ratio d'inconnus/corrections, souvenirs réutilisés après reprise, diversité des intentions, faux positifs des catégories, latence, fréquence et ressources des services, mouvements refusés à juste titre, arrêts, dérive/chute et, plus tard, température/RSS/batterie réelles. Publier la valeur **uniquement si elle a été mesurée**, avec ses unités, contexte et limites.

## 8. Décision opérationnelle actuelle

**F1-A et F1-B sont fusionnées sur `main` ([PR #24](https://github.com/Jean-Philippe56520/Microduck/pull/24), [PR #25](https://github.com/Jean-Philippe56520/Microduck/pull/25)). F1-C est fusionnée sur `main` via [PR #26](https://github.com/Jean-Philippe56520/Microduck/pull/26) : [339 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234808363), dont 24 nouveaux. La SQLite existante conserve des catégories fictives et `unknown`/`conflict`, 14 jours maximum et 512 entrées, et deux processus séparés relisent le journal. Aucune reconnaissance réelle, capteur OEM, moteur, Qwen ou validation physique. La phase F1 reste inachevée ; **prochain développement F1-D : démonstration passive de bout en bout**.** Le chantier de marche reste suspendu en l'absence de nouvelle hypothèse démontrable ; P1a **n'est pas** débloqué. Le robot physique n'est toujours pas disponible. Aucun nouvel essai moteur ou portage Rust n'est impliqué par l'adoption de ce plan.
