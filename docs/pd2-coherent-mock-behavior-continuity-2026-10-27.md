# PD2 — Continuité des comportements fictifs de Kwipi (16 noms OEM)

**27 octobre 2026 — lot logiciel sur fixtures, aucun mouvement exécuté, aucune humeur ressentie, aucun modèle ou capteur actif.** Objectif : relier les portraits de personnalité déjà décidés par F2/F4 à des **candidatures descriptives stables** parmi les 16 états OEM historiques, sans générer une deuxième décision moteur ni promettre 16 animations installées. [PD0](pd0-behavior-states-selective-qwen-2026-10-27.md) fixe le cadrage, [PD1](pd1-oem-expression-capabilities-2026-10-27.md) fixe les capacités réellement vérifiées dans le code constructeur. [Cat-A2b](plan-action.md) reste prioritaire pour la perception réelle à faible hauteur.

## 1. Architecture : réutiliser avant de créer

| Source relue | Décision PD2 |
| --- | --- |
| OEM épinglé [`942e58e3`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) : `robotd`, `idle_head`, `pet-detect`, `voice.play` | **Ne pas modifier**. Regards/bâillements idle et `coo` de caresse restent propriétés de `robotd`. Les autres états historiques ne sont pas des primitives offertes aux applications. Contrôleur moteur 50 Hz inchangé. |
| OEM [PR #381](https://github.com/pollen-robotics/microduck/pull/381) cerveau et [#414](https://github.com/pollen-robotics/microduck/pull/414) cartographie | **Ouvertes, non fusionnées au 27/10/2026** ; aucune fonction ou carte supposée installée. |
| Communauté [registre C3](community-reference-registry-2026-10-26.md) : QuackNav/microduck-brain, Quacksat, microduck-twin, GC-RENCAO, Smartulf123, quack-control, microduck-lab/studio | Références de veille ; **aucun import tiers** (API, licence, modèle et sûreté non approuvés pour Kwipi). |
| F2 `AutonomyBrain`, `PassiveRhythm`, les **cinq `Motivations` existantes** | **Réutiliser** : PD2 s'exécute **après** l'intention F2/F4, garde le repos et la prudence décidés localement. Pas de nouveau minuteur, boucle ni poids d'IA. |
| P-A/P-B `BehaviorPortrait`, F4-A `BehavioralMemory`, `ExperienceMemory` | **Réutiliser** la même SQLite, la familiarité et les corrections. Un souvenir fictif `inspection_reserved` peut rendre l'exploration fictive moins probable. Une rétraction F4-A annule ce frein à la prochaine lecture. PD2 n'écrit rien. |
| P-C `MockExpressionHint`, `MockOemConditions`, PD1 `expression_capability_for` | **Réutiliser** : `Petted` est une indication de `coo` déjà possédé par OEM, `Startle` une hypothèse sans animation ; aucun nouveau son. Chaque sortie PD2 répète le statut non exécutable PD1. |
| EX1/EX2/EX3 et F5-Qwen | Aucun second apprentissage causal, aucun flux d'événements, consultation PC ni transmission multimodale. Les expériences EX2 restent **temporelles et fictives** ; elles ne prouvent pas l'exécution d'un état historique. |

**Nouveau code justifié :** `microduck_companion/behavior_continuity.py` est un petit post-traitement descriptif, possédé paresseusement par **le même `AutonomyBrain`** via `describe_behavior_continuity()`. Il évite de modifier le sélecteur F2, garde la source `mock` et utilise PD1 comme source unique des capacités. Pas de deuxième machine de contrôle : `MockBehaviorContinuity` ne réveille jamais un processus, ne décide pas un mouvement et ne possède aucune API d'action.

## 2. Correspondance des 16 états et origine des candidatures

| Nom historique | Déjà présent / source de candidature fictive | Statut d'action réel |
| --- | --- | --- |
| **Chill** | P-A `idle` ; repos tranquille ou abstention | **Non exécuté par PD2** |
| **LookAround** | P-A `observe/inspect/listen` | **Non exécuté** |
| **Nap** | P-A `rest` avec énergie **simulée** ; priorité sur les animations | **Non exécuté** |
| **BallPlay** | P-A `play_cue` social fictif, pas coup de pied | **Non exécuté** |
| **Wander** | `new_space`, seulement après proposition **LookAround**, curiosité/énergie suffisantes et faible prudence | **Aucune navigation** |
| **TurnInPlace** | `viewpoint_ambiguity`, après proposition **LookAround** et motivation appropriée | **Aucune rotation** |
| **GroundPick** | `floor_object`, après attention portée à un objet peu familier, prudence et énergie adéquates | **Aucun ramassage, sol non vérifié** |
| **Zoomies** | `play_burst`, seulement après **BallPlay**, énergie/jeu élevés et prudence faible | **Aucune course** |
| **Dance** | `rhythm_pattern`, uniquement après **BallPlay**, sans analyse réelle de musique | **Aucune danse** |
| **Stretch** | `after_rest`, seulement après un état **Nap** décrit précédemment | **Aucun étirement moteur** |
| **Ruffle** | `social_settle`, seulement après un portrait **Chill/sociable** | **Aucun geste** |
| **Preen** | `quiet_grooming` sur **Chill** et motivation calme appropriée | **Aucune toilette** |
| **Sneeze** | `sneeze_like` déclaré artificiellement sur **Chill** | **Aucun son, aucun détecteur** |
| **Held** | `held_like` déclaré artificiellement sur **Chill**, prise en main **non détectée réellement** | **Aucun mouvement ou permission** |
| **Petted** | P-C `MockOemCue(petting_start)` donnant `oem_owned` seulement dans un scénario fictif autorisé | **Pas de second `coo`** |
| **Startle** | P-C bruit fictif donnant `hypothesis` si autorisé et non auto-produit | **Aucun réflexe moteur** |

**Dix contextes sont déclaratifs et fictifs**, pas des classes de capteurs installées. Les noms `new_space` ou `floor_object` ne prouvent **ni géolocalisation, ni sol sûr**. `Sneeze` ne suggère pas l'existence d'un détecteur d'éternuement, `Held` n'implique pas un dispositif de portage validé. Tous les états hors des quatre portraits P-A restent **candidats descriptifs**, même lorsqu'un scénario les sélectionne. PD1 conserve **zéro commande historique à 16 états attestée**.

## 3. Conditions de continuité et corrections

`MockBehaviorContinuity` conserve seulement pendant le processus :
- **Inertie de 2 secondes fictives** pour éviter une alternance descriptive à chaque cycle ;
- **Cooldown de 8 secondes fictives** après avoir quitté un état historique non descriptif ;
- **Préemption immédiate** si `MockOemConditions` indique `stop_requested`, `fallen` ou `busy`, même à horodatage dupliqué ;
- **Repos P-A `Nap` prioritaire** sur les candidats de jeu ou d'animation ;
- **Aucune promotion d'indices périmés/futurs** : chaque contexte hors `none` a une fenêtre de 1,5 seconde fictive ;
- Horloge monotone reculant ou contexte devenu incompatible : retour prudent, sans maintenir artificiellement le candidat ;
- Réutilisation de `BehaviorPortrait.inspection_habit` : un historique fictif F4-A défavorable inhibe certains candidats ; une correction F4-A peut restaurer leur candidature sans recalcul de poids séparé.

Ces délais et seuils de motivation sont **des valeurs expérimentales de test, pas des mesures de sûreté ou d'humeur sur le RK3566**. Une simulation de catégorie inconnue ne devient jamais une identité. Les événements contradictoires doivent mener à l'abstention.

**Après un redémarrage** : les **souvenirs SQLite corrigibles préexistants** restent persistants si le fichier SQLite le permet ; **l'inertie d'expression et les cinq valeurs `Motivations` ne sont pas encore persistées par PD2**. Le nouveau processus reprend les valeurs F2 par défaut, puis peut relire ses souvenirs F4-A. Éviter de présenter une préférence fictive comme un trait appris d'une conséquence réelle. La persistance durable et l'authentification d'expérience exigent un futur lot séparé.

## 4. Invariants contrôlés par le code

- `MockBehaviorSituation` accepte uniquement dix contextes de laboratoire typés, plus `none`, de provenance `mock_expression_situation_only` ; aucun texte libre, identité, commande, image, audio ou marqueur `sensor`.
- `MockBehaviorDisposition` exige **toujours** les preuves PD1, `executed=False`, `hardware_verified=False`, `physical_execution_authorized=False` et zéro moteur, son, Qwen, écriture. Les sorties falsifiées sont rejetées.
- `AutonomyBrain.describe_behavior_continuity()` est **facultatif et post-décisionnel**. Les appels existants de `propose_balanced_passive()` et `describe_behavior()` restent inchangés. Aucun appel à `robotd`, `mediad`, `pet-detect`, Ollama, HTTP, microphone ou haut-parleur.
- P-C `Startle` et `Petted` ne sont interprétés qu'après vérification des indicateurs fictifs préexistants et ne génèrent pas d'ordre OEM. **La source OEM possède toujours la réponse de caresse.**
- Pas de stockage de cadence/émotion, table SQLite, requête réseau, boucle de surveillance, ni entraînement ML supplémentaire.

## 5. Validation et critères de suite

Le fichier [`tests/test_pd2_behavior_continuity.py`](../tests/test_pd2_behavior_continuity.py) contient des tests hôte couvrant : **les 16 noms**, les dix contextes fictifs et les quatre portraits existants, les hypothèses P-C, l'effet des motivations et de la prudence, l'absence de source, les horloges, l'inertie/cooldown, la préemption STOP/chute même à temps identique, l'interdiction de suivre une candidature contextuelle inéligible, la rétraction F4-A, la stabilité du schéma SQLite et l'absence de mouvement/Qwen. Relecture après réouverture, sans prétendre préserver une humeur persistante.

**Tests requis :** `python -m unittest discover -s tests -p test_pd2_behavior_continuity.py -v` et la suite complète en CI GitHub. **Niveau de preuve : PC/fixtures uniquement**, pas MuJoCo, pas RK3566/robot physique, aucune validation des sons, de la carte, des moteurs, de l'énergie de batterie, de l'IMU ou du sol. Aucun budget de CPU/RSS/température n'est inventé.

## 6. Après PD2

- **Cat-A2b reste prioritaire** : vraies vues basses, annotations indépendantes, inconnus et confusions. Tant que la perception est fictive, les nouveaux états ne sont pas observés au domicile.
- **PD3** : détecter un besoin sémantique pour F5/Qwen sans le déclencher sur une humeur ou un bruit seul ; le contrat F5 actuel ne transmet ni image ni indice utile discriminant, donc l'abstention prévaut.
- **PD5–PD6** : recherche OEM épinglé/PR/tiers, puis réutilisation des **primitives réellement commandables**, simulation OEM, audit de RAM/température/stockage et validation supervisée. Le ToF frontal 8×8 n'est pas un lidar 360° ; aucune navigation libre, objet au sol ou réaction à une personne/animal ne doit être automatisée sans protections.
- **PD7** : mesurer l'évolution réelle des intentions face aux souvenirs et les taux de refus. Ne conserver aucune voix/photo en continu ni secret personnel.

**Décision :** PD2 teste la **cohérence d'une humeur exprimable**, pas les seize comportements physiques ni des émotions réelles. Les 12 états non portés restent disponibles comme **étiquettes historiques de scénarios**, pour préparer une future liaison sûre et justifiée aux fonctions OEM.
