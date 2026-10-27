# Audit de faisabilité matérielle — Microduck Companion

**Addendum X2-A — 27/10/2026, aucune mesure embarquée :** [contrat de télémétrie simulée](x2a-simulated-observation-contract-2026-10-27.md). Le rôle attendu de `robotd/tofd` et les classes d'échec de la lecture sont codés sur branche ; tests CI à contrôler. Seules de petites structures de contrôle Python sont ajoutées au pont déjà présent, sans budget mesuré pour RK3566 ni état du stockage `/var/lib/robot`. Les seuils existants de **2 s**, **1 s** d'écart et **45 Hz** proviennent du protocole P2b, ne sont **pas** de nouveaux seuils validés en situation domestique. Pas de caméra, NPU, microphone, Qwen, action moteur, thermie ni charge réelle mesurés.

**Addendum X1 — 27/10/2026, vérification sur hôte seulement :** [dossier d'exécution](kwipi-execution-acceptance-2026-10-27.md). Le nouveau test transversal manipule la SQLite unique avec des catégories, décisions et effets strictement fictifs ([CI hôte finale #40425919775](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40425919775) réussie, 1 227 tests, 19 ignorés) ; il ne mesure pas les coûts du modèle, de la caméra, de la parole, de MuJoCo ou des processus OEM. Une API historique de feedback est refusée sans preuve d'action ; `choose()` n'ajoute plus de choix fictifs dans `experiences`, et aucune ligne historique n'est supprimée. **Aucune mesure du RK3566, RAM libre, stockage persistant, thermie, latence moteur, autonomie, média ou NPU.** Les 1 Go/32 Go ne sont pas une marge disponible ; audit `scripts/resource-audit.sh` sur la carte avant portage.

**Addendum PD3 — 27/10/2026, sans benchmark embarqué :** [opportunités Qwen fictives et refus transport](pd3-semantic-pc-opportunity-2026-10-27.md). La fonction de triage est pure, éphémère et n'interroge aucun service sur RK3566, ne transmet aucune image/voix et ne conserve aucune mémoire supplémentaire. Les seuils de deux échantillons, 0,5–30 s de séparation et 1 s de fraîcheur restent **de laboratoire** ; ni RSS, ni temps CPU, ni chaleur ni batterie sur 1 Go RAM/32 Go ne sont mesurés. Le PC Qwen est facultatif ; déploiement uniquement après Cat-A2b, protocole d'accès privé, vérification `scripts/resource-audit.sh` et sécurité `robotd` 50 Hz.


**Addendum PD2 — 27/10/2026, aucune preuve sur RK3566 :** [contrat de continuité purement fictif](pd2-coherent-mock-behavior-continuity-2026-10-27.md). Une petite structure Python process-local décrit la continuité de 16 noms historiques depuis F2/P-A/PD1 sans moteur, capteur, Qwen ni table SQLite supplémentaires. Les valeurs 2 s/8 s sont des temporisations de fixtures, **pas des mesures** de capacité 1 Go RAM/32 Go, consommation batterie ou délai robotd 50 Hz. L'inertie d'humeur n'est pas persistée ; les anciens souvenirs F4-A restent dans la SQLite existante si celle-ci est sur disque. Audit `scripts/resource-audit.sh` sur l'appareil avant portage.


**Addendum PD1 — 27/10/2026 :** [inventaire purement logiciel des 16 noms OEM](pd1-oem-expression-capabilities-2026-10-27.md). Les quatre correspondances `IdleHead`/petting dans le code épinglé ne sont **ni des commandes utilisables par Companion, ni une mesure sur l'appareil réel**. L'interface PD1 demeure sans RPC, capture, son, SQLite supplémentaire ou moteur ; ses coûts et l'éventuelle consommation RAM/CPU/thermique sur RK3566 **n'ont pas été mesurés**, et 1 Go de RAM / 32 Go nominaux ne sont pas une marge garantie. Maintenir `scripts/resource-audit.sh` avant toute nouvelle animation ou processus.


**Addendum PD0 — 27/10/2026, documentaire :** [16 comportements historiques, besoin sémantique et Qwen PC](pd0-behavior-states-selective-qwen-2026-10-27.md). Aucun état supplémentaire ne tourne sur RK3566 ; pas de budget d'humeur, d'animation, de transmission d'image, de consommation Ollama ou de mémoire persistante mesuré. F5 actuel est un contrat de catégories fictives sans médias ; plus tard, tout traitement multimodal est déporté vers PC facultatif et borné, sans bloquer `robotd` 50 Hz. Avant portage : audit `scripts/resource-audit.sh`, vérification du stockage réellement monté, RAM libre, CPU/thermie, propriétés des animations OEM et sûreté. Les 32 Go nominaux ne sont pas un espace libre garanti.


**Addendum EX2 (26/10/2026 ; [PR #71](https://github.com/Jean-Philippe56520/Microduck/pull/71), [CI hôte 1 139 tests, 19 ignorés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40413719554), non validé sur robot) :** [effets fictifs et Journal de Kwipi](ex2-mock-effects-kwipi-journal-2026-10-26.md). Un lecteur PC local ouvre une base de test EX1/EX2 existante en `mode=ro`, sans collecte ni écriture sur RK3566. Les fenêtres fictives (2 s avant/après), les plafonds de 256 effets/14 jours et l'export à 50 lignes ne sont pas des résultats de RAM/CPU/stockage physique. Aucun test moteur 50 Hz, température, eMMC, SQLite WAL ou autonomie réelle ; consulter le constructeur et `scripts/resource-audit.sh` après réception. Ne pas activer de journaux à haute fréquence ni de chemin persistant avant audit.


**Addendum EX1 (26/10/2026 ; [PR #70](https://github.com/Jean-Philippe56520/Microduck/pull/70), [CI hôte 1 111 tests, 19 ignorés](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40410788233)) :** [journal d'intentions fictives](ex1-mock-experience-ledger-2026-10-26.md) sur la connexion `ExperienceMemory` existante. Les plafonds de test (256 lignes, 14 jours, 50 sorties, résolution fictive dans 30 s) ne sont **pas** un budget RK3566. La taille complète SQLite (index/WAL compris), la RAM/RSS disponible, la consommation CPU/thermie, la mémoire libre et la cadence de `robotd` n'ont pas été mesurées sur Kwipi. Zéro nouvelle commande moteur, reconnaissance réelle, conséquence/causalité vécue ou preuve matérielle ; audit `scripts/resource-audit.sh` obligatoire avant portage.


**Addendum EX0 (26/10/2026) — [plan d'expériences de Kwipi](kwipi-experiential-learning-plan-2026-10-26.md) :** strictement documentaire. Les futures opérations action→effet, les primitives de contact, l'attribution causale et les retours sociaux n'ont **aucune mesure** sur RK3566 ni aucune validation mécanique. La taille de SQLite, sa rétention, les délais de perception/robotd, la force d'interaction, les ressources CPU/NPU, la thermique et l'autonomie ne peuvent être déduits des fixtures ou de Qwen. Conserver l'audit `scripts/resource-audit.sh` et la validation de la locomotion/du sol avant toute autonomie physique ; aucune action physique n'est autorisée par EX0.


**Addendum Cat-A2b (26/10/2026) :** [contrat de captures basses locales](cata2b-private-low-camera-protocol-2026-10-26.md), aucun robot ni caméra monté/testé. Les hauteurs acceptées **100–300 mm sont des déclarations de centre optique** appuyées par un fichier de règle privé et son SHA (intégrité d'octets, **pas métrologie physique vérifiée**), et non la hauteur totale de Kwipi. Aucun corpus bas réellement fourni, aucune inférence sur robot, aucune mesure CPU/RSS/NPU/thermie/stockage/consommation en conditions embarquées. Si un futur rapport Cat-A2b comporte des temps/RSS, ils seront **strictement hôte PC**. La porte `scripts/resource-audit.sh` sur le RK3566 reste obligatoire avant tout portage ou activation de caméra/robotd.


**Addendum Cat-A2a (26/10/2026) :** [banc de localisation 24 photos COCO VAL](cata2-coco-bbox-host-2026-10-26.md). Sur runner Python/ONNX CPU seulement, évaluateur de boîtes YOLOX Nano existant et fichiers temporaires de poids/image (pas d'archive ni de robot). [Mesures hôte CI #40400991178](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40400991178) : médiane ONNX CPU **23,037 ms**, p95 **24,504 ms**, pic RSS du **processus entier 174 068 Kio**, 24 inférences sur JPEG COCO, durée **3,097 s** avec récupération des images (hors téléchargement initial des poids/annotations). **Ces mesures ne sont pas des mesures sur le RK3566**, et n'incluent pas l'acquisition caméra OEM. **Aucune caméra physique à ~25 cm, performance NPU, RAM libre, chaleur, Wi-Fi, autonomie, charge `mediad` ou sécurité `robotd` mesurée.** `scripts/resource-audit.sh` sur robot final et validation graduelle nécessaires ; pas de déploiement OEM ou SQLite.


**Addendum P-C, expressions (26/10/2026) :** `oem_expression_hints.py` est une simple fonction de description, sans nouvelle acquisition, modèle IA, moteur ou audio **dans les fixtures**. Cela **ne mesure aucun coût sur RK3566** (RAM/RSS, charge audio `pet-detect`, CPU, batterie, chaleur, stockage et latence sont inconnus). Les réactions OEM à `petting_start` restent sous `robotd`, le portage P-C2 est différé. `scripts/resource-audit.sh` sur robot reste obligatoire.


**Addendum P-B (26/10/2026, sans matériel) :** ajout de lectures facultatives de la SQLite `ExperienceMemory` F4-A après décision F2/P-A, sans image, réseau, son, servomoteur, tâche de fond ou nouvelle table ; **aucun RSS, CPU, I/O SQLite p95, RAM libre, thermique ni délai sur RK3566 mesuré**. Ne pas extrapoler ces tests hôte. Le budget de lecture devra être profilé avant activation sur robot, sans attendre la boucle 50 Hz `robotd`. Le contrôle `scripts/resource-audit.sh` et ses exigences de sécurité restent obligatoires.


**Addendum P-A, personnalité à 16 états historiques (26/10/2026) :** le nouveau portrait `behavior_personality.py` lit seulement `ExperienceMemory` sur fixtures et décrit quatre états non exécutés ; **aucune mesure nouvelle de RSS, CPU, RAM libre, eMMC, chaleur, latence, batterie, NPU, microphone ou cadence des moteurs sur RK3566**. Il n'y a aucun portage, aucune garantie de consommation et aucun nouveau moteur. Les douze autres états attendent un contrat OEM/sûreté. Audit physique `scripts/resource-audit.sh` toujours obligatoire.


**Addendum Cat-A hôte (26/10/2026) :** [évaluation YOLOX-Nano catégorie-first](cata-category-detection-pilot-2026-10-26.md). Sur **32 images publiques** et **64 inférences CPU** (images entières et coupes artificielles) : **médiane ONNX 10,700 ms**, CPU utilisateur processus **2,703 s**, pic RSS processus **138 324 Kio**, durée réseau inclus **10,689 s**. Ce ne sont **ni** les coûts d'un pipeline caméra/ToF/robot complet **ni** une mesure RK3566/NPU, ni un budget thermique, de batterie, de stockage SQLite ou d'actionnement. Aucun détecteur catégorie embarqué validé, aucune marge mémoire présumée. `scripts/resource-audit.sh` reste obligatoire sur robot physique.


**Addendum catégorie-first (26/10/2026) :** [décision R2-C et nouveau plan](r2c-category-first-active-perception-2026-10-26.md). Le prototype de conseil sur parties d'objets ne consomme **aucune image, aucune inférence capteur, ni moteur** en fixtures ; il n'autorise donc aucune projection sur la faisabilité RK3566, les mouvements de tête, les charges NPU, la thermie, la mémoire persistante ni la consommation réelle. **Tout détecteur de catégories et la seconde observation par orientation réelle restent à mesurer sur PC puis sur le robot après `scripts/resource-audit.sh`.**

**Addendum R2-B+2 — image réelle, ressources hôte uniquement (26/10/2026) :** [rapport de 180 vues ABO de chaises](r2b2-confusable-objects-2026-10-26.md), [CI #40380437787](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40380437787). MobileNetV2 ONNX CPU : 180 inférences, **médiane 8,959 ms / p95 9,159 ms / maximum 11,549 ms**, hors prétraitement réseau/scoring ; **pic RSS du processus Linux 143 224 Kio** (~140 Mio), CPU utilisateur 9,634 s, durée murale réseau inclus 56,452 s. Rappel visuel insuffisant (MobileNetV2 4/48, M1-B 10/48) ; **aucune estimation de marge ARM, NPU, thermique, batterie, stockage ou impact moteur du RK3566 n'est autorisée.** Aucun portage validé.

**Addendum R2-B+1 audio réel — mesures hôte uniquement (26/10/2026) :** [rapport](r2b1-real-audio-results-2026-10-26.md). L'évaluateur existant a traité **34 extraits de 1 s** sur GitHub Actions : **0,124 s mur après préparation/collecte**, **0,124 s CPU utilisateur**, **pic RSS processus entier 52 700 Kio**. Les téléchargements partiels, découpes WAV et temps réseau sont exclus de ces mesures. **Ces valeurs ne prouvent ni RAM libre RK3566, ni température, ni autonomie, ni temps de traitement de Kwipi.** Test positif du code, résultat négatif de reconnaissance (0/10 connues et 1 fausse fusion) ; modèle non sélectionné.

**Historique du préparateur R2-B+1, PR #59 (PC seulement) :** [protocole initial DCASE/ToyADMOS](r2b1-independent-audio-2026-10-26.md). Cette phase n'avait utilisé que 10 WAV artificiels ; **les essais réels ont ensuite été effectués dans la PR #60**, avec résultats ci-dessus. Les temps et RSS éventuels de la CI concernent uniquement l'hôte. Ni modèle candidat RKNN, ni mémoire embarquée, ni marge thermique ou de stockage déduite de ces essais. L'audit physique via scripts/resource-audit.sh reste obligatoire.

**Addendum C3 — références externes uniquement (26/10/2026) :** [registre par chantier](community-reference-registry-2026-10-26.md). La [PR amont #414 `maploc v2 + mapd`](https://github.com/pollen-robotics/microduck/pull/414) annonce des résultats sur journaux physiques et précise `[map] enabled` **désactivé par défaut** jusqu'à mesure de coût CPU sur carte ; elle reste **ouverte/non fusionnée**, et n'a pas été exécutée sur notre appareil. Ces mesures amont ne valident ni nos ressources RK3566, ni la capacité à éviter les escaliers, ni une intégration de QuackNav/microduck-brain. Les règles d'audit et l'absence de robot physique restent inchangées.

**Rappel de planification après R2-B (26/10/2026) :** [plan des prochains essais](r2-follow-up-execution-plan-2026-10-26.md). Les mesures audio/visuelles et SQLite à venir seront **sur PC** ; aucune ne permettra de présumer la RAM disponible, le stockage libre, la thermie, les délais moteurs ou l'autonomie du RK3566. Aucun matériel n'est testé dans ce lot documentaire ; le `resource-audit.sh` physique reste une porte obligatoire avant portage.

**Addendum R2-B — 26 octobre 2026 :** [étude réelle sur 72 vues ABO](r2b-independent-capture-evaluation-2026-10-26.md), [runner CI #40322898625](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40322898625). MobileNetV2 ONNX CPU : médiane **8,95 ms**, p95 **9,40 ms** sur 72 inférences (hors prétraitement et téléchargement) ; pic RSS **114 764 Kio pour le processus entier**, 22,372 s mur incluant le réseau. **Ces mesures hôte ne renseignent pas la RAM libre, la chauffe, la consommation, les délais robotd ni la faisabilité RK3566.** Les médias restent en mémoire temporaire et non dans SQLite ; COIL à usage non commercial non exécuté, audio indépendant non évalué, aucune transmission personnelle ni commande constructeur.


**Addendum R2-A — 26 octobre 2026 :** [sélection d'une seule mémoire R2 sur fixtures](r2a-single-memory-selection-2026-10-26.md). Le protocole réutilise M1-B/`ExperienceMemory` avec un garde-fou optionnel contre la double persistance M1-A dans le chemin R2, sans migration ni suppression de données. Les signatures de 64/16 octets, le plafond de blobs et `PRAGMA page_count` **ne prouvent pas** la marge de stockage disponible du RK3566 (index, WAL, pages libres, système, RSS, caches). Une ancienne application peut toujours écrire séparément : l'opération R2 suivante refusera alors le mélange. Aucune mesure réelle RAM/CPU/thermie ni déploiement physique nouveau.


**Audit M1-B2 sur runner Linux (non transférable au RK3566) :** la [CI ONNX publique](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40309136430) a observé 145 180 Kio de **pic RSS du processus entier**, environ 14 Mo + 16,1 Mo de poids et des médianes d'inférence 6,86 ms image / 3,60 ms son (prétraitement et collecte exclus). Les vecteurs float32 de 4 000/4 096 octets ne sont PAS la RAM du modèle ni l'espace SQLite effectivement consommé. Sur Microduck, RAM libre, charge CPU, chauffe, disque réellement disponible et échéances moteurs restent inconnus. Aucun déploiement ou appel OEM/Qwen n'est issu de ce lot. [Rapport M1-B2](m1b2-host-embeddings-2026-10-26.md).

Date : 2026-10-25. Audit documentaire et revue de code, **sans accès au robot physique**.

**Addendum OEM R0 (26 octobre 2026) :** [audit de réutilisation du constructeur](oem-reuse-audit-2026-10-26.md) établi sur les révisions de sous-modules existantes, sans aucune modification OEM ni test matériel. `robotd` conserve seul les moteurs et les animations idle ; `mediad`, `tof` et le worker audio possèdent déjà leurs interfaces. L'ancien cerveau à 16 états est **documenté seulement** dans ce snapshot, M9 reste **non porté**. Avant tout branchement Companion, valider versions, contrôle des accès, provenance, durée de fraîcheur, RAM/stockage/thermie/cadence réelles et séparation du contrôle moteur. Ce document ne rapporte **aucune mesure matérielle nouvelle**. Les valeurs de RAM et stockage libres ne sont **pas mesurées**. Aucune capture d'image privée ou donnée biométrique ne doit être placée dans ce dépôt.

**Addendum R1.5 — 26 octobre 2026 :** [audit rétroactif de non-duplication](r15-retrospective-reuse-audit-2026-10-26.md). M1-A et M1-B ont des tables SQLite distinctes malgré des extracteurs communs ; conserver les deux comme expériences ne signifie pas lancer deux mémoires persistantes sur le RK3566. La taille des signatures n'est pas celle des pages, index, WAL ou du RSS réel. Les 24 démonstrations et les nombreux outils MuJoCo sont de l'**historique de laboratoire**, pas un lot de services à installer sur le robot. Toujours aucune mesure physique de mémoire libre, chaleur, moteur ou batterie ; code OEM et essais matériels inchangés.

**Addendum R1 — 26 octobre 2026 :** la [passerelle passive sur fixtures](r1-oem-passive-fixture-contract-2026-10-26.md) ne contacte **aucun capteur** et ne lance **aucune inférence** ; elle réutilise les validations de formats OEM existantes, produit uniquement des métadonnées non authentifiées et refuse de promouvoir `floor_clear`, une identité d'objet ou une commande. Aucun nouveau chiffre de RAM/CPU/stockage/thermie/cadence moteur du RK3566 n'est disponible. Les tests CI de structure ne constituent pas une validation matérielle.

**Mise à jour de cohérence :** le [plan d'action consolidé](plan-action.md) définit les priorités. P0g compare les modèles MuJoCo compilés, avec géométries différentes mais contacts de semelles/sol identiques sur les paramètres examinés ; ce n'est pas une preuve de marche. Essai moteur historique P0e : 2,295 mm et arrêt confirmé. Dernière comparaison contrôlée P0i : 1,444 mm / 1,968 mm, deux arrêts confirmés, cause inconnue. P0j a relu **hors ligne** les forces P0e archivées ([269 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40230029946), [replay P0e confirmé](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40229765655), [PR #22 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/22)) : 79/79 relevés `stand` et 127/127 relevés `walk` avec deux pieds en charge, part gauche 52,03 % → 44,54 %, zéro essai moteur supplémentaire. Cela n'établit ni force de propulsion signée, ni démarche, ni sécurité du robot réel. P2a fournit des cycles fictifs persistés. P2b ajoute sur [PR #19](https://github.com/Jean-Philippe56520/Microduck/pull/19) des cycles passifs alimentés par les télémétries simulées, [testés logiciellement (234 tests Python) et en MuJoCo officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40216199277) : six cycles passifs sur deux sessions, six intentions `halt`, zéro commande motrice ou récompense. Ces données ne valident pas le matériel. P0h ([PR #20](https://github.com/Jean-Philippe56520/Microduck/pull/20)) identifie en source la différence de sélection ONNX entre les defaults `robotd` (`velstand`) et `duck-sim` (paire `alpha`) ; [243 tests Python sur main](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219827102) et [audit des trois modèles ONNX du MuJoCo officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40219277997) réussis (61→14, bundle v8 local, hashes distincts, sorties synthétiques comparées, 0 moteur). Cette divergence ne prouve pas la cause de non-marche. P0i ([PR #21](https://github.com/Jean-Philippe56520/Microduck/pull/21)) a comparé les deux configurations sur [MuJoCo officiel](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40221935528) : **24 commandes par configuration**, alpha **1,444 mm** XY et VelStand **1,968 mm**, deux arrêts confirmés, seuil de 10 mm **non atteint**, aucun gain locomoteur prouvé ; [257 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40222688915). Les deux simulations ne mesurent ni traction fiable, ni autonomie, ni chauffe ou tenue mécanique du robot réel. Aucun matériel Microduck réel n'a été mesuré.

## Addendum F3-C — 26 octobre 2026

Revue de la revision constructeur epinglee dans le depot (sans acces au robot) : le socket Unix local de mediad permet une identification hello et la requete media.frame, qui renvoie des pixels bruts. Les notifications media.video et media.detections sont destinees au canal WebRTC, pas a ce socket. Les detections OEM concernent les autres Microducks, pas les chiens ou chats. Le classificateur pet-detect signale les sons de caresses, pas des animaux ou des mots-cles.

Le parseur F3-C ne traite que des donnees fictives reproduisant les formats officiels : aucun capteur, moteur ou composant materiel n'a ete teste. Les voies de communication OEM doivent etre inspectees et autorisees de maniere independante avant toute integration reelle. Aucune nouvelle mesure thermique, RAM, NPU, batterie ou cadence motrice n'est disponible. Voir [rapport F3-C](f3c-oem-media-notifications-2026-10-26.md).

## Addendum F3-D — 26 octobre 2026 (mesures Linux sur hôte de CI)

Le [banc F3-D sur 28 nouvelles photos publiques déclarées CC0](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671367), toutes externes au foyer, utilise **MobileNetV2 ImageNet ONNX** sur le **CPU du runner GitHub Actions Ubuntu**, et aucun composant du Rockchip Microduck. La mesure de pic RSS est de **108 148 Kio (~105,6 Mio) pour tout le processus Python** (NumPy, Pillow, ONNX Runtime et bibliothèques comprises), avec **9,036 ms d'inférence CPU médiane** et p95 **9,240 ms** sur 28 images. Il est **incorrect** d'en déduire la RAM du modèle seul, les FPS réels, la marge de 1 Go de RAM, la chauffe ou la consommation de batterie du robot ; le modèle ne tourne pas sur le NPU Microduck dans cet essai.

Sur le jeu additionnel, **8/16 photos de chiens/chats** sont reconnues selon les étiquettes publiques (3/8 chats et 5/8 chiens), avec **12/12 photos hors des deux catégories** rejetées. Ces données ne sont pas tirées au hasard, leurs descriptions n'ont pas de deuxième annotation indépendante, et la présence éventuelle des images dans le jeu de préentraînement ImageNet n'a pas été auditée. **Aucune reconnaissance fiable d'animaux ni navigation sûre n'est démontrée.** Voir [rapport détaillé F3-D et inventaire des 28 sources](f3d-open-set-resource-benchmark-2026-10-26.md). Les mesures du script `scripts/resource-audit.sh` sur un Microduck réel restent **non effectuées**.

## F3-E — limite documentaire

Le nouveau contrat F3-E teste des en-têtes `media.frame` sur fixtures, sans capture physique. Les 48 photos publiques n'ont pas été contre-annotées indépendamment. RAM et capteurs du robot restent inconnus. [Rapport F3-E](f3e-annotation-frame-preflight-2026-10-26.md).

## Addendum F4-A — 26 octobre 2026 (mémoire logicielle uniquement)

Le [lot F4-A](f4a-semantic-behavior-memory-2026-10-26.md) ajoute des tables bornées dans la SQLite existante : catégories F1-C/F2-C fictives, hypothèses non confirmées, succès/échecs explicitement fictifs issus de P2a. La durée de conservation configurée est 14 jours avec plafonds d'entrées et retractions ; **ce n'est pas une mesure de taille réelle de base, RAM libre, endurance eMMC ou performances du RK3566**. [Tests et redémarrage sur CPU GitHub Actions](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40246670514) valident le prototype Python, **pas les pilotes `mediad`/`tofd`, les capteurs ou l'énergie du robot**. Le script `scripts/resource-audit.sh` n'a pas été lancé sur matériel Microduck, qui reste indisponible. Aucun nouveau résultat sur la locomotion ou la thermie.

## Addendum F4-B — 26 octobre 2026 (repères fictifs sans localisation physique)

Le [contrat F4-B](f4b-uncertain-spatial-memory-2026-10-26.md) **ne mesure aucune position du Microduck ni aucun obstacle**. `uncertain_spatial_memory.py` conserve jusqu'à **256 points de fixtures** dans la SQLite existante, sur une durée configurée de **14 jours**, avec coordonnées bornées, rayons d'incertitude et confiance **déclarés par la fixture**, non étalonnés. Les deux cadres de référence sont inventés : aucune géométrie de pièce, pose du robot, orientation, repère ToF/IMU, odométrie ou carte physique n'a été déterminée.

Les incohérences spatiales supprimant les coordonnées, la barrière de confiance déclarative, la rétraction, les limites de capacité et le `halt` en l'absence de capteurs sont **testés sur CPU Linux CI** : [662 tests Python et démonstration en deux processus](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40247354468). Les résultats **ne valident ni la détection de sol/escaliers, ni les distances réelles du ToF 8×8, ni l'évitement d'animaux, ni la navigation libre**. Les champs `navigation_authorized`, `floor_clearance_verified` et `real_sensor_authenticated` restent systématiquement faux.

Aucune mesure supplémentaire de RAM libre, occupation disque SQLite réelle sur Yocto, température, charge CPU sur RK3566, fréquence moteur, autonomie ou accès à un robot physique. Les plafonds de tables ne sont **pas une preuve de marge de mémoire/stockage**. Le script `scripts/resource-audit.sh` doit encore être exécuté sur le futur robot dans le protocole prévu, avant tout déploiement.

## Addendum F4-C — 26 octobre 2026 (social uniquement fictif)

Le [rapport F4-C](f4c-social-cue-contract-2026-10-26.md) présente des **propositions de comportements sans aucune exécution**. Les durées `glance=250 ms`, `play_cue=300 ms` et `chirp=180 ms` sont des **durées nominales de messages de simulation**, et **non des mouvements de tête/sons réellement mesurés**. Les drapeaux de consentement et de supervision sont déclarés sur des fixtures, sans vérification juridique, parentale ou physique ; l'analyse des classes animales ne prouve aucune reconnaissance individuelle.

[689 tests Python réussis en CI hôte Linux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248330199), dont 27 nouveaux F4-C, ont confirmé la proposition `silence` par défaut, les limites de fréquence et la persistance d'un cooldown entre deux processus Python. La SQLite ne conserve que catégorie, type de proposition et horodatage ; les limites **128 lignes / 7 jours / 2 sons fictifs par 10 min** sont des contraintes logicielles, **pas des mesures de charge ou d'énergie sur le RK3566**.

Aucun matériel Microduck testé : **zéro émission audio**, zéro moteur/servo/regard, zéro caméra/microphone authentifiés, aucun capteur ToF réel, aucune RAM libre, température, fréquence de contrôle ou autonomie énergétique mesurée. La taille d'une table ou une durée nominale de proposition ne permet pas d'inférer une capacité physique. Avant intégration : audit avec `scripts/resource-audit.sh`, politiques OEM préservées et contrôles de consentement réels.

## Addendum F4-C — 26 octobre 2026 (interactions sociales fictives)

La [phase F4-C](f4c-social-cue-contract-2026-10-26.md) ajoute une couche **non exécutable** de propositions sociales sur `AutonomyBrain` et des catégories de **fixtures** : silence par défaut, regards, invitations au jeu, petits signaux sonores et repos théorique. **Aucun moteur de regard, haut-parleur, micro, caméra ni capteur OEM n'a été activé.** Les temps de 250 ms (`glance`), 180 ms (`chirp`) et 300 ms (`play_cue`) sont **des durées déclarées de propositions**, et non des latences, consommations ou temps d'action réellement mesurés.

Les [689 tests Python et deux processus de démonstration](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248330199) montrent le maintien du silence sans opt-in de scénario, l'absence de commande motrice/audio et les quotas de propositions **sur un hôte GitHub Actions uniquement**. Le contexte `operator_opt_in` n'est **pas un mécanisme réel de vérification du consentement**, même quand il est vrai dans un test. L'historique des propositions est borné à 128 lignes sur 7 jours dans la SQLite existante : ce seuil **ne mesure ni le RSS, ni la mémoire réellement libre, ni l'énergie, ni la température du Microduck**. Le robot physique reste indisponible ; il n'existe aucune mesure nouvelle de capacité sonore, cadence moteur, capteurs, comportement en présence d'enfants/animaux ni sécurité mécanique. L'audit `scripts/resource-audit.sh` reste à effectuer sur le RK3566 avant tout déploiement.

## Addendum F4-D — 26 octobre 2026 (associations volontaires fictives)

Le [rapport F4-D](f4d-revocable-optin-contract-2026-10-26.md) décrit un registre **strictement logiciel** d'associations volontaires fictives, dans la SQLite `ExperienceMemory`. Une clé et un jeton de fixture de 32 octets servent au calcul HMAC-SHA256 ; **la table conserve l'empreinte, la classe générique, une référence opaque et des dates/séquences, pas le jeton ni la clé bruts**. Il s'agit d'une réduction des données stockées, **pas** d'un chiffrement complet, d'une garantie d'anonymat, d'authentification réelle, de consentement parental vérifié ou d'effacement forensique des pages SQLite/WAL/sauvegardes.

Le prototype limite **24 associations** et des durées de 60 secondes à 30 jours, avec refus de rejeu et révocation. Ces limites constituent des **quotas configurés, sans valeur mesurée de RSS/eMMC, de disponibilité des ressources ni d'endurance du stockage RK3566**. [723 tests Python réussis sur hôte Linux CI, dont 34 nouveaux, et démonstration de révocation dans deux processus](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40249168929) : première session association fictive, seconde session retrait, statut `unknown` après retrait. **Aucun lecteur NFC/BLE, capteur individuel, source OEM, voix, photo, haut-parleur ni moteur réellement testé**, pas d'essai sur un animal ou enfant. La clé de production, la gestion privée et les règles de consentement effectives devront être conçues séparément avant toute utilisation réelle.

Aucun audit matériel n'a été ajouté : `scripts/resource-audit.sh` reste à exécuter sur le futur Microduck pour RAM libre, CPU, température, fréquence moteur, espace persistant et consommation. Le robot physique est toujours absent, et les systèmes de sécurité OEM restent inchangés.

## Addendum F5-A — 26 octobre 2026 (contrat d'hypothèses PC hors réseau)

Le [contrat F5-A](f5a-pc-hypotheses-2026-10-26.md), fusionné via [PR #41](https://github.com/Jean-Philippe56520/Microduck/pull/41) après [757 tests Python réussis en CI hôte](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40250745954), n'utilise **ni LAN, ni Ollama, ni Qwen, ni véritable inférence**. Une requête et sa réponse sont des JSON **fictifs**, générés/testés par Python sur hôte CI. Une fenêtre de validité logique de 2 s, au plus 4 096 octets de réponse et quatre hypothèses constituent des **bornes de protocole**, pas des mesures de latence, débit, mémoire ou énergétique du PC. Une confiance alléguée ne mesure aucune précision de modèle.

F5-A ne charge aucun modèle sur le RK3566, ne valide aucun accès caméra/audio/NPU et ne modifie ni `robotd`, ni `mediad`, ni `tofd`. **Aucune nouvelle valeur** de RSS, RAM libre, CPU, température, cadence de commande, capacité de stockage ou autonomie n'est établie pour le Microduck physique. L'exécution de `scripts/resource-audit.sh` sur le matériel reste nécessaire. L'authentification du futur serveur et les délais de réseau effectifs appartiennent à F5-B/C.

## Addendum F5-B — 26 octobre 2026

Le [rapport F5-B](f5b-ollama-local-transport-2026-10-26.md) décrit un client HTTP local Python et un worker sans interaction motrice. Les [781 tests Python réussis en CI hôte](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40251807307), dont les nouveaux tests réseau F5-B, utilisent un serveur HTTP simulé sur 127.0.0.1. Aucun véritable modèle Ollama ou Qwen 4B/9B n'a été exécuté et aucune mesure PC réelle n'est disponible. Le comparateur PC est en mode sans réseau par défaut.

Les limites configurées de taille de réponse et de délai sont des règles logicielles, pas des mesures de RAM, de latence Ollama, de GPU/NPU ou d'énergie. Les ressources du robot RK3566 et sa température restent inconnues. L'audit physique `scripts/resource-audit.sh` doit encore être effectué sur matériel réel. Le dépôt ne contient aucun modèle ni donnée privée.

## Addendum F5-C — 26 octobre 2026 (quota logiciel, pas de mesure matérielle)

La [phase F5-C](f5c-sparse-consultations-2026-10-26.md), développée en [PR #43](https://github.com/Jean-Philippe56520/Microduck/pull/43), limite les tentatives de consultation PC sur **observations fictives**. Les chiffres 60 s, 2 consultations par 10 min, 8 par jour, 3 s de reprise des demandes interrompues et 300 s après deux pannes sont des **seuils logiciels de départ**, ni des mesures énergétiques ni une cadence viable démontrée sur le RK3566. La transaction SQLite a une attente configurée de 20 ms, **sans garantie de délai sur le robot**.

Les [798 tests Python sur GitHub Actions, y compris la démonstration SQLite inter-processus](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40252645890), ne consultent aucun vrai Ollama, ne pilotent aucun actionneur, ne mesurent ni puissance, latence radio réelle, RAM libre, température, autonomie, eMMC, NPU ou fréquence moteur du Microduck. Aucun chiffre de performance Qwen 4B/9B sur le PC n'a été produit. Le script `scripts/resource-audit.sh` reste à exécuter sur matériel physique lorsqu'il sera disponible, et les interfaces de sécurité OEM restent seules responsables des mouvements.

## Addendum F5-D — 26 octobre 2026 (tests de résistance HTTP et annotations fictives)

La [phase F5-D](f5d-adversarial-pc-contract-2026-10-26.md), fusionnée via [PR #44](https://github.com/Jean-Philippe56520/Microduck/pull/44) après [808 tests Python et une démonstration fictive réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40253911518), ajoute des essais contre des réponses JSON/HTTP **fictives** : faux ordres moteurs, faux consentement/identités, étiquette animale non fondée, retards et rejouements. Le flux HTTP de test hostile ne sort pas de **127.0.0.1** ; aucun vrai Ollama ou Qwen n'est lancé, aucun contrôle de `robotd` ou capteur du robot n'est testé.

Le délai monotone total sur le **corps** de la réponse Ollama est une propriété logicielle testée sur l'hôte CI ; il ne garantit ni un délai strict pour les **en-têtes** d'un pair malveillant, ni l'interopérabilité avec le serveur Ollama réel, ni l'authentification du PC. La limite `Content-Length` et l'interdiction de réponses `chunked` sont des choix prudents **à vérifier sur la version Ollama installée**. La consultation reste facultative, hors de la boucle moteur.

**Aucune nouvelle mesure physique** de RAM libre, RSS, CPU/NPU, latence de mouvement, eMMC réellement disponible, batterie ou température RK3566 n'est fournie par F5-D. Les résultats de tests logiciels GitHub Actions ne doivent pas être présentés comme une validation de sûreté sur le Microduck. `scripts/resource-audit.sh` et les essais supervisés restent à réaliser sur le robot physique après acquisition.

## Addendum F6-A — 26 octobre 2026 (inventaire OEM et risque de stockage non persistant)

Le [contrat F6-A](f6a-embedded-readiness-2026-10-26.md), fusionné via [PR #45](https://github.com/Jean-Philippe56520/Microduck/pull/45) après [830 tests Python et une démonstration fictive réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40254981871), consulte la révision **OEM épinglée** du dépôt (`942e58e3aa6dbb28e7037203fff11866122c7567`) et un **snapshot documentaire Yocto** (`91691234f3b518a94ee4391f8567c9486335f507`), sans installer de programme sur une carte.

**Point de vigilance démontré par lecture du code Yocto :** le montage `/var/lib/robot` est **conditionnel** à la présence de `data`. Un dossier sur le système racine ne suffit pas : une SQLite ouverte sous ce chemin pourrait survivre moins longtemps que prévu et ne pas suivre les bascules A/B. F6-A refuse donc de **sélectionner une SQLite persistante** sur simple preuve textuelle. Les contrôles `mountinfo` et identités de cartes sont réalisés **sur fixtures**, pas sur du matériel réel.

Les sockets OEM `/run/robotd.sock`, `/run/mediad/media.sock` et `/run/tofd/tof.sock` sont inventoriés, **jamais contactés** par ce lot ; les moteurs, caméras, ToF, réseau et Qwen ne sont pas activés. Cette documentation ne mesure ni RAM/CPU libre, charge NPU, surface du stockage eMMC utilisable, thermie, batterie, cadence de la boucle motrice ou latence sur robot. L'audit `scripts/resource-audit.sh` reste nécessaire **sur unité physique** avant tout portage ou installation.

## Addendum F6-B — 26 octobre 2026 (comparaison de calcul hôte, aucun portage)

La [PR #46](https://github.com/Jean-Philippe56520/Microduck/pull/46) étudie la **seule expression numérique de score passif** `PassiveRhythm._score` en Rust standard (programme expérimental indépendant) et compare ses résultats au Python existant. [CI hôte Linux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40256023791) : **841 tests Python**, **4 tests Rust** et **1 500 cas de parité exacte**. Sur un banc de **120 000 scores**, la boucle Python a pris **38,031 ms** puis **32,587 ms** ; l'expérience Rust **3,503 ms** puis **2,060 ms**. Les RSS **de processus hôte entiers** mesurés séparément étaient **17 068 Kio** en Python et **2 132 Kio** en Rust minimal.

**Ces chiffres ne représentent pas deux cerveaux de même périmètre :** le programme Rust ne charge aucune base SQLite, perception, protections, interfacing OEM ou réseau, tandis que Python charge l'interpréteur et le module. On ne doit **pas** extrapoler l'écart de temps ou de mémoire à une marge RAM RK3566, à une durée de batterie, ni à la cadence de `robotd`. **Décision F6-B : aucun portage Rust intégré pour l'instant**, attendre l'audit matériel réel et un protocole complet à charge égale. [Rapport méthodologique F6-B](f6b-python-rust-score-study-2026-10-26.md).

## Addendum F6-C — 26 octobre 2026 (fenêtres de ressources du processus hôte)

La [PR #47 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/47), [CI Python de 861 tests réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40257453473), ajoute un garde d'admission **facultatif et non préemptif** au superviseur de perceptions fictives F2-D. Il peut refuser des cycles avant la lecture d'un faux socket Unix et des événements avant cognition/SQLite, sans file d'attente ni action sur les moteurs. Ses seuils **0,5 s / 8 cycles / 32 événements sur 10 s**, et les éventuels plafonds CPU/RSS, **ne proviennent d'aucune mesure du RK3566**. La sécurité et les cadences de `robotd` restent exclusivement du ressort constructeur.

La [CI Python F6-C](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40257113819) valide **861 tests** et un pipeline complet sur six sollicitations synthétiques (trois acceptées, trois refusées). Un seul essai sur hôte CI a fourni **p50 0,196 ms**, **p95 1,887 ms** (maximum des six), CPU moyen du **processus entier** **0,551 ms** par rapport, et pic historique RSS du processus **18 324 Kio**. Ces valeurs ne représentent ni RAM disponible sur Microduck, ni latence des capteurs, ni thermie, puissance, consommation de batterie ou charge simultanée des pilotes OEM. Le contrôle est coopératif, et **ne peut ni interrompre une requête Python bloquée ni annuler une écriture SQLite achevée**.

`scripts/resource-audit.sh` reste à exécuter **sur une unité réelle**, dans l'ordre repos → vision → mouvement sécurisé seulement après validation locomotrice. Aucun seuil thermique ou énergétique réel n'est validé.

## Addendum F6-D — 26 octobre 2026 (protocole en lecture seule, aucune mesure RK3566)

Le [protocole F6-D](f6d-hardware-audit-protocol-2026-10-26.md), fusionné via [PR #48](https://github.com/Jean-Philippe56520/Microduck/pull/48), transforme `scripts/resource-audit.sh` en outil **à phases explicites**. `--plan` ne lit **aucun** capteur ni fichier système. Un relevé stationnaire **réel** exige un accès développeur autorisé sur une machine ARM64 déclarant RK3566, avec confirmation opérateur ; une deuxième mesure stationnaire en vision exige la revue manuelle du repos et une vision OEM démarrée **en dehors du script**. La phase mouvement est **définitivement refusée par F6-D**, la locomotion P0/P1 restant non résolue.

Les nouvelles sorties différencient `df` du **montage exact** `/var/lib/robot` et rapportent RAM disponible, RSS/CPU des seuls processus utiles, état OEM, fréquence et température **si l'unité les expose**. **Ni `robotd` à 50 Hz, ni les deadlines manquées, ni la latence capteur, ni la batterie ne sont instrumentés par cet outil** ; l'absence de mesure bloque une validation physique, même si le script lui-même renvoie normalement des données. Les conditions d'interruption sont documentées sans inventer de seuil de température ou de RAM libre.

La [CI hôte F6-D](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40289135442) a réussi **878 tests Python** plus la vérification syntaxique POSIX, les refus de commande et le scénario de checklist fictive. **Zéro collecte sur le Microduck réel**, zéro installation, aucune autorisation de marche, aucune nouvelle mesure de RAM/RSS/thermie matérielles.

## Addendum M1-A — 26 octobre 2026 (empreintes visuelles et sonores synthétiques)

Le [prototype M1-A](m1a-compact-multimodal-memory-2026-10-26.md) en [PR #49](https://github.com/Jean-Philippe56520/Microduck/pull/49) extrait **64 octets** de caractéristiques image (pixels gris 32 × 32 synthétiques) et **16 octets** de spectre/enveloppe d'un signal PCM16 synthétique. Une nouvelle table dans la connexion SQLite `ExperienceMemory` agrège les rencontres et est limitée à **256 lignes actives**, **180 jours** de rétention. La démonstration sur [CI Linux](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40297726482) compte **10 rencontres par motif sur 2 motifs**, soit **80 octets de champs empreinte** en SQLite, **hors entêtes, index, pages, journaux, autres tables et fichiers médias qui ne sont pas stockés**. **Il n'existe pas de plafond du fichier SQLite en Mo**, de preuve de son montage `data` sur robot, ni de mesure de son RSS sur RK3566.

Les entrées sont **synthétiques**, les étiquettes sont des assertions fictives sans modèle de classification, et une signature similaire ne prouve jamais l'identité d'un objet ou d'un son. M1-A ne préserve **ni photos ni enregistrements**, refuse les signatures déclarées `person` / `speech` mais **ne peut pas** détecter une personne ou parole dans un média inconnu ; toute capture réelle demeure interdite avant une revue de confidentialité et de sécurité. Aucun microphone, caméra, Qwen réel, OEM, moteur ni robot physique n'a été sollicité. Les critères de validation F6-D et les limites matérielles restent inchangés.

## Addendum M1-B — 26 octobre 2026 (quota corrigé et limites du rappel visuel/sonore)

La [PR #50 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/50) corrige le contrôle global de M1-A : la somme des signatures de **toutes les modalités** est désormais bornée à 256 dans la transaction, empêchant le passage transitoire à 257. Le nouveau prototype `MultiviewPatternMemory` sur la même SQLite relie jusqu'à 6 empreintes par **groupe de fixtures explicitement déclaré**, avec plafonds configurables **1 024 groupes / 4 096 signatures / 256 Kio de BLOBs**. Ces nombres sont des paramètres de test, **pas une mesure du stockage réel du RK3566 ni un plafond du fichier complet** : la [CI sur 512 signatures synthétiques](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40302743563) a montré **32 768 octets BLOB pour 204 800 octets de pages SQLite** sur hôte, hors WAL.

Un [banc facultatif de 6 images + 2 enregistrements publics CC0](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40302657292) a testé des changements du **même fichier**, pas des angles indépendants du même animal : **6/6** luminosité, **0/6** rotation de 12° et **0/6** recadrage ; son **2/2** amplitude et **1/2** retard de 16 ms. Une hausse arbitraire du nombre d'empreintes ne résout donc pas à elle seule le manque d'invariance de l'extracteur artisanal. Le lot ne reconnaît aucune identité, n'ouvre aucun capteur et n'effectue aucun déploiement. [Protocole et résultats M1-B](m1b-multiview-memory-2026-10-26.md).

## Verdict

Le Microduck permet raisonnablement de viser : mémoire persistante locale, moteur d'autonomie, exploration prudente, observation visuelle événementielle, identification de catégories d'animaux et interaction sociale élémentaire. Il reste à développer et à valider : détection personnalisée d'animaux, identification non biométrique des personnes familières, reconnaissance vocale, exploration sûre en environnement non contrôlé, et intégration du cerveau autonome à robotd. Qwen multimodal se placera initialement sur un PC local.

## Sources de vérité et révisions

- Système Yocto constructeur : https://github.com/pollen-robotics/microduck_yocto
- Carte beta avec stockage eMMC : https://github.com/pollen-robotics/microduck_yocto/blob/main/docs/agents/beta-board.md
- Plan des partitions de l'image : https://github.com/pollen-robotics/microduck_yocto/blob/main/meta-microduck-bsp/files/wic/microduck-ab.wks.in
- Fiche constructeur : https://store.pollen-robotics.com/products/microduck
- Kit presse : https://pollen-robotics.com/microduck/press-kit/
- Architecture et IPC : https://github.com/pollen-robotics/microduck/blob/main/docs/design/architecture.md
- État du projet : https://github.com/pollen-robotics/microduck/blob/main/docs/project/roadmap.md
- Bench NPU : https://github.com/pollen-robotics/microduck/blob/main/docs/project/npu-bringup.md
- Implémentation détection : https://github.com/pollen-robotics/microduck/blob/main/mediad/src/detect.rs
- Pacing et coûts CPU : https://github.com/pollen-robotics/microduck/blob/main/docs/project/idle-cpu.md
- Cartes : https://github.com/pollen-robotics/microduck/blob/main/robotd-params/src/board.rs
- Simulation : https://github.com/pollen-robotics/microduck/blob/main/docs/robot/simulation.md
- Capture photo : https://github.com/pollen-robotics/microduck/blob/main/docs/project/npu-bringup.md
- Petit classificateur audio : https://github.com/pollen-robotics/microduck/blob/main/pet-detect/README.md

## Configuration publique

| Ressource | Confirmée | Inconnue / précaution |
|---|---|---|
| SoC | Rockchip RK3566, 4 cœurs Cortex-A55 | fréquence réelle et throttling du produit final |
| RAM | 1 Go total | **MemAvailable réel**, RSS services, mémoire CMA/vidéo/NPU |
| Stockage | 32 Go nominal | partitions, système installé, espace libre, vitesse écriture, endurance |
| NPU | Rockchip INT8, ~0,8 TOPS dans la documentation Microduck | pilote actif et performance de la carte finale |
| Caméra | frontale, accès mediad, capture et WebRTC | définition/FOV du produit final non stabilisés par le kit presse |
| ToF | 8x8 distances, ~15 Hz dans le code | pas une cartographie 360° ni détection garantie du vide |
| IMU | 2 | cartes zero3 et beta différentes |
| Audio | microphones et haut-parleur, code audio et détection d'événements | reconnaissance de mots non livrée |
| NFC | 2 antennes annoncées, pilote nfcd | très courte portée, pas une localisation à distance |
| Liaisons | Wi-Fi et Bluetooth | versions radio de série non finalisées |
| Batterie | NP-F550, environ 1 h annoncée | consommation autonomie sur usage IA à mesurer |

Le code distingue `Board::Zero3` (Radxa Zero 3W, IMX219, BMI088) et `Board::Beta` (Seeed RK3566, GC2093, LSM6DSV16X). Ne pas extrapoler les résultats d'une carte de développement à toutes les unités de série.

## État du logiciel revu

- `robotd` : contrôle moteur à 50 Hz, politiques ONNX, intentions et sécurité.
- `mediad` : caméra, pipeline GStreamer/WebRTC et capture `media.frame`; `GET /frame` fournit une image PNG sur le LAN ; cette route n'a pas d'authentification supplémentaire dans la documentation. Limiter au réseau de confiance.
- `tofd` : ToF 8x8 et télémétrie sur socket ; autres IMU selon carte.
- `duck-detect` et `mediad/src/detect.rs` : détection de robots Microduck, INT8 `.rknn` NPU ou `.onnx` CPU, désactivée par défaut. Le décodeur actuel est prévu pour **une classe** ; un détecteur chien/chat/personne nécessite de l'entraînement et des modifications.
- `pet-detect` : classificateur audio de frottements/grattouilles du robot (~20 Ko), **pas** de détection d'animaux.
- `nfc`/`nfcd` : lecture de tags, actuellement utilisée pour l'appairage des manettes ; adaptation nécessaire pour souvenirs d'interaction.
- Cerveau autonome M9 encore à construire/intégrer ; ne pas le confondre avec les politiques motrices.
- **Limite du diagnostic MuJoCo (P0a) :** le protocole officiel épinglé `body_server` expose les positions/vitesses de 15 articulations, la pose du tronc et des courants **simulés non calibrés** ; ni les contacts réels des pieds dans MuJoCo, ni les cibles articulaires n'apparaissent dans l'opération `read`. Notre [sonde passive P0a](https://github.com/Jean-Philippe56520/Microduck/pull/11) a été [testée sur MuJoCo](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580637) (8 échantillons `stand`, 0,991 mm de dérive au repos, aucune commande). Cela ne dit rien sur les contacts d'un robot physique et ne résout pas la locomotion J2e.
- Le simulateur `scripts/duck-sim` exécute les vrais démons contre MuJoCo, avec capteurs simulés ; n'exerce pas les vrais pilotes NPU, ISP, BLE, servomoteurs ni la thermique.

## Mesures du fabricant sur carte Radxa Zero 3 (non représentatives garanties du produit final)

- Modèle de détection d'autres Microducks, YOLO11n 320x320 INT8 : **3,9 Mo sur disque**.
- Benchmark NPU sur un échantillon limité : p50 **25,7 ms** ; p95 **58,4 ms** ; cadence **2 Hz** ; température finale **63°C** dans ce test.
- En fonctionnement non limité, le détecteur a atteint **95°C** et le SoC a réduit sa fréquence à **408 MHz** selon le code de `mediad/src/detect.rs`.
- `mediad` inactif avec caméra : **6,1 % d'un cœur** sur la carte mesurée (le rapport ne donne pas la charge globale CPU/RAM du produit final).
- `tofd` : le relevé décrit ~0,5 % d'un cœur pour la télémétrie ToF ; l'IMU supplémentaire de la Zero 3 consommait davantage et a été désactivée par défaut.
- Ces mesures ne constituent ni un budget RAM global ni un engagement de précision sur chien/chat/personne.

## Faisabilité par fonction

| Fonction | Évaluation | Stratégie |
|---|---|---|
| Mémoire d'épisodes/préférences | Très favorable | SQLite locale, petits enregistrements, pas de vidéo continue |
| Motivations et choix d'activités | Très favorable | État et politiques comportementales peu gourmandes |
| Détection d'un chien/chat/personne | Favorable, à entraîner et valider | Petit détecteur quantifié NPU, quelques observations par seconde |
| Reconnaissance d'animaux familiers | Plausible, incertitude élevée | Exemples variés ; suivi temporel et vérification ; inconnus possibles |
| Identification d'une personne familière | Prévoir un mécanisme explicite non biométrique | NFC de proximité, BLE associé ou présentation volontaire |
| Compréhension de mots simples | Plausible | Modèle de mots-clés, attention au bruit des moteurs |
| Compréhension complexe et analyse de scènes | Sur PC | Qwen multimodal via réseau local, temporisation/fallback |
| Cartographie / exploration pièce | Partielle | Odometry + ToF + vision ; évaluer glissement, dérive et obstacles |
| Détection fiable des escaliers et animaux en mouvement | Non démontrée | Ne pas laisser le robot explorer un espace non sécurisé |
| Apprentissage autonome de nouvelles politiques motrices | Avancé | Utiliser simulateur et entraînement externe, pas sur le robot |
| LLM 4B/9B embarqué | Non réaliste | PC/serveur local |

Le module `pet-detect` n'identifie pas les chats et chiens. Un petit modèle de vision supplémentaire ne reconnaît pas automatiquement un individu précis : classifier l'espèce, retrouver un individu et garantir sa position sont trois problèmes distincts.

## Système d'exploitation officiel : stockage réellement réservé

Le troisième dépôt officiel `pollen-robotics/microduck_yocto` fournit le système Linux Yocto, les pilotes de cartes et la mise à jour A/B RAUC. À la date de cet audit, la fiche commerciale annonce **32 Go de stockage**, mais les documents d'une **carte beta** indiquent **64 Go eMMC, 1 Go LPDDR4X, sans slot SD**. Ce n'est pas une garantie de capacité de la version commerciale.

Le plan d'image `meta-microduck-bsp/files/wic/microduck-ab.wks.in` définit notamment :
- `rootfs_a` : **2 Gio** ;
- `rootfs_b` : **2 Gio** ;
- `data` : **8 Gio**, montée dans `/var/lib/robot` et persistante à travers les mises à jour A/B ;
- des petites partitions de démarrage, pour environ **12,1 Gio partitionnés** au total.

La partition `data` comporte déjà des politiques motrices, sons, configurations, profils Wi-Fi et autres données. **8 Gio est la capacité de la partition, pas l'espace libre mesuré**. Sur une puce 32 ou 64 Go, le reste peut demeurer non partitionné : ne pas confondre capacité eMMC et capacité immédiatement exploitable, et ne pas modifier les partitions sans procédure compatible avec les mises à jour signées du constructeur.

La mémoire SQLite du compagnon devrait vivre dans un répertoire propre sous `/var/lib/robot/` avec permissions privées et sauvegarde explicite, sans être mise sur GitHub. Le système Yocto destiné au client peut ne pas fournir SSH/root ; l'audit en ligne de commande nécessitera un accès développeur autorisé.

## Budget de ressources : règles de conception proposées, pas résultats mesurés

1. Conserver une grande marge RAM pour Linux, `robotd`, `mediad`, buffers vidéo et contrôleurs. Fixer un **objectif initial** de mémoire ajoutée très faible pour notre cerveau, puis arrêter l'intégration si `MemAvailable` ou les délais moteurs se dégradent. Ne pas annoncer un budget libre chiffré avant mesure.
2. Faire tourner au départ **un seul petit modèle visuel** à ~1–2 Hz ; n'ajouter aucun détecteur concurrent sans profilage.
3. Ne pas embarquer Qwen 0,5B ou plus par défaut sur un système avec seulement 1 Go de RAM et caméra/moteurs actifs.
4. Stocker dans SQLite les métadonnées et événements ; conserver des images uniquement sur demande et avec rétention courte. Les modèles peuvent être petits sur disque, mais les buffers et bibliothèques occupent plus de RAM que les poids seuls.
5. Préserver le fonctionnement 50 Hz de `robotd`. En cas de chaleur, délais manqués, manque mémoire ou capteur incohérent, suspendre la perception/activité non essentielle.

## Audit à exécuter sur une unité de série (non effectué)

Sur une connexion SSH autorisée au robot, à l'arrêt puis avec caméra, mouvements et modèle de vision actifs :

```bash
uname -a
cat /proc/device-tree/model 2>/dev/null || true
free -h
grep -E 'MemTotal|MemAvailable|SwapTotal|CmaTotal|CmaFree' /proc/meminfo
df -h / /opt/robot /var/lib/robot
df -i /
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
du -sh /opt/robot/daemon /opt/robot/detector /var/lib/robot 2>/dev/null
ps -eo pid,rss,%cpu,comm --sort=-rss | head -n 25
systemctl --type=service --state=running --no-pager
robotctl health
dmesg | grep -i rknpu | tail -n 20
```

Relever aussi la température du SoC, la fréquence CPU, le nombre de ticks moteurs manqués, les performances NPU, les latences d'images, l'autonomie sur batterie, les erreurs de capteurs et la qualité de reconnaissance en éclairage varié. Faire trois mesures : repos ; vision activée ; vision + déplacement. À confronter à la révision matérielle exacte.

## Décisions issues de l'audit (historique, non priorités actuelles)

1. L'adaptateur `PerceptionEvent` est **réalisé pour les démons simulés `robotd` et `tofd`** ; sa liaison à `mediad` et à la perception réelle reste à développer.
2. Simuler une détection multi-classe (animal/personne/objet) et tester la mémoire, les faux positifs et la perte de capteur.
3. Préparer une architecture de reconnaissance d'animaux personnalisée sur PC, entraînable avec données locales ; la conversion RKNN sera validée sur la carte réelle.
4. Associer les interactions humaines à une identité volontaire, sans collecte biométrique par défaut.
5. Différer la décision d'un modèle vision supplémentaire tant que RAM libre, température et cadence du système final n'ont pas été mesurées.

**Statut final : faisabilité d'architecture établie, marge chiffrée de RAM/stockage et fiabilité en conditions réelles non encore établies.**


## Outil de diagnostic préparé dans notre dépôt

Le script `scripts/resource-audit.sh` mesure, en lecture seule, `MemAvailable`, la mémoire CMA, la charge mémoire des processus, l'utilisation des partitions, la température et la fréquence CPU sur un robot où un shell est autorisé. Il n'a **pas encore été exécuté sur un Microduck physique**. Comparer repos, caméra active, et caméra + mouvements avant d'ajouter de nouveaux modèles.


## Avancement logiciel après l'audit du 25 octobre 2026

Le prototype `microduck_companion` possède maintenant un contrat `PerceptionEvent` / `PerceptionSnapshot` v1. Il filtre les lectures par environnement déclaré, type de source, confiance et durée de validité ; il refuse l'exploration quand une donnée essentielle (zone, sol, obstacle ou batterie) manque ou n'est pas assez fiable. Les objets fictifs, simulés et déclarés par capteur sont distingués dans la mémoire SQLite. Les essais automatisés couvrent les capteurs manquants, les lectures périmées, les contradictions, les hypothèses LLM et la provenance des objets.

**Aucune source physique n'est encore branchée et aucune preuve d'authenticité n'est fournie par la simple chaîne `source`.** Les limites du ToF 8×8 et de la caméra demeurent inchangées ; le logiciel ne doit pas prétendre que le sol est sûr à partir d'un capteur non validé. Ce travail ne modifie pas `robotd`, sa boucle à 50 Hz, ses politiques ONNX ni les garanties de sécurité matérielles. Les mesures de RAM, chaleur, CPU, espace libre et latence sur un Microduck physique restent à effectuer avec `scripts/resource-audit.sh`.


## Vérification du lien vers les démons (prototype de lecture seule)

Le nouveau module `sim_ipc.py` prépare l'acquisition de `robot.health`, `robot.state` et `tof.frame` par sockets Unix. Les messages de santé et de télémétrie sont validés (délais, formats, horodatage local, cellules ToF et statuts). Une sonde `sim_probe.py` affiche les résultats sans commande moteur et n'attribue jamais la propriété `floor_clear` aux distances ToF.

**Historique J2a :** les premiers 65 tests utilisaient des sockets Unix de démonstration, avant le lancement du simulateur officiel. **Depuis J2d/J2e, les commandes bornées et l'arrêt ont bien été testés via `robotd` dans MuJoCo**, mais ce résultat n'établit ni un évitement fiable d'obstacles ni une validation sur matériel physique.


## Mise à jour — pont d'observation MuJoCo en lecture seule

`sim_bridge.py` et `sim_observer.py` sont ajoutés après `sim_ipc.py` pour convertir les mesures des démons simulés en un `PerceptionSnapshot` conservateur. Ils vérifient la fraîcheur, les erreurs de lecture, la chute et la cadence mais ne prétendent pas mesurer la sécurité du sol. La décision `halt` est conservée sans `safe_area` et `floor_clear` validés ; une batterie faible confirmée peut donner une intention `rest`, sans mouvement commandé.

**Validation à cette étape :** 81 tests Python avec objets et sockets fictifs ; le conteneur local ne disposait pas de Rust/Cargo ni d'un accès GitHub direct. Un essai réel sur les démons MuJoCo simulés a **ensuite été réalisé par GitHub Actions** (résultats ci-dessous). La RAM, la température, la consommation et les latences sur robot restent inconnues.


## Nouvelle preuve logicielle — simulation officielle exécutée le 25 octobre 2026

[Exécution GitHub Actions #40145369078](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40145369078) — Ubuntu 24.04, `duck-sim` sans caméra, `microduck` et `microduck_rl` épinglés. Python 3.12, MuJoCo 3.10.0, NumPy 2.5.4, ONNX Runtime 1.28.0 ; politiques motrices officielles. Toutes les étapes GitHub Actions ont réussi.

| Observation sur la machine de simulation | Valeur observée |
| --- | --- |
| `robotd` | `healthy`, autour de 50 Hz (télémétrie ~49,996 Hz), 0 délai manqué sur les échantillons consultés |
| Temps réel du monde MuJoCo | 1,00× |
| Télémétrie `tofd` | source `sim`, 2 trames consécutives × 64 cellules |
| Pont `sim_bridge` | `errors=[]`, batterie déclarée ~50 % dans la simulation |
| Choix du cerveau | `halt` : sol/zone non certifiés |
| Commandes motrices du compagnon | aucune |
| Tests logiciels | 81/81 réussis |

Cette preuve établit uniquement que **les démons officiels simulés peuvent fournir des données au cerveau et fonctionner à cadence nominale dans cet environnement CI**. Les valeurs de batterie, de capteurs, de température et d'énergie du robot réel ne sont pas mesurées. L'absence de collision, la reconnaissance d'un animal, la fiabilité des escaliers et l'autonomie sans PC auxiliaire sur la carte RK3566 restent à démontrer.

**Avant mouvement autonome :** construire une preuve explicite de `safe_area` et `floor_clear` issue du simulateur (et non d'une supposition à partir du ToF 8×8), puis utiliser exclusivement un adaptateur filtrant les intentions à travers `robotd`. Aucun pilote ni mécanisme de sécurité du constructeur n'a été modifié pendant cet essai.


## Essai de certification de sol purement virtuel (J2c)

La passerelle `sim_flat_zone.py` prépare un contrôle basé sur la scène MuJoCo **officielle et épinglée** plutôt que sur les 64 valeurs ToF. Elle exige un processus `body_server` local, dans la scène plane par défaut, un robot unique, une position (vérité terrain) cohérente et un espace de travail artificiellement borné. **Cette vérification n'existe pas sur le Microduck réel**, qui n'a pas accès à sa position parfaite ni à la géométrie exacte d'une maison.

Ces contrôles sont codés et leur comportement est testé sur données fictives. La nouvelle sonde a été vérifiée avec le vrai simulateur dans [GitHub Actions #40173323079](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173323079) : scène et état simulés validés, réserve 0,7134 m, décision `explore` en lecture seule, aucune commande moteur envoyée. Cela ne change pas l'inconnue concernant les escaliers, l'évitement d'animaux ou la navigation sûre en milieu réel. Aucune valeur de RAM disponible, de température ou d'énergie n'a été mesurée sur le RK3566.


## J2d — Première commande de vitesse uniquement en simulation

`sim_motion.py` et `sim_motion_demo.py` préparent une première impulsion volontaire sur le Microduck virtuel, à vitesse avant fixe de 0,05 m/s pendant environ 0,4 s. Chaque impulsion passe uniquement par `robotd` et dépend de la géométrie MuJoCo épinglée, de la pose et des mesures de santé confirmées. `robot.stop` est requis ; le deadman de la politique constructeur n'est ni désactivé ni remplacé.

**Vérification à ce stade :** 115 tests Python, dont 12 tests de mouvements fictifs sur sockets Unix, **et essai réel en MuJoCo validé** ([CI #40173809463](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40173809463)). 4 notifications `robot.move`, réponse à `robot.stop` vérifiée ; différence de position simulée de **0,185 mm**, insuffisante pour prouver une marche. L'essai ne mesure pas l'arrêt physique ni la gestion d'obstacles. Les conditions expérimentales de sol/position n'existent pas sur le RK3566 physique ; aucune validation des escaliers, RAM, énergie ou température n'est possible par ce test.


## J2e — Démarche : seuil du constructeur et protocole de mesure simulé

La sélection entre les politiques ONNX de station debout et de marche dépend de la norme de vitesse de commande. Dans la révision officielle épinglée, la valeur par défaut de séparation est **0,05 m/s** (source : `duck-control/src/policy.rs`). Le premier test de commande à exactement ce seuil a observé seulement 0,185 mm de variation du tronc ; l'hypothèse « politique de station debout » est à confronter aux mesures réelles de la seconde expérience.

La nouvelle tentative demande `vx=0,12 m/s` en simulation bornée, après mesure de dérive. La base SQLite conserve uniquement des conséquences explicitement observées dans le simulateur vérifié ; les résultats incertains n'affectent pas les préférences. Une translation éventuelle ne démontre pas les contacts des pieds, la stabilité d'une démarche ou l'absence de glissade. Aucune commande physique, aucune mesure de l'énergie, de la température, du CPU ou de la RAM réelle n'est produite par cet essai.


## Résultats réels du jalon J2e — 25 octobre 2026

**Quatre exécutions** du **simulateur MuJoCo officiel** à 0,12 m/s, avec scène plane épinglée, contrôle de santé et commande `robot.stop` confirmée, ont montré des variations de position inférieures au seuil expérimental de 1 cm :

- [Essai A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175133570) : 12 commandes, translation **1,242 mm**, dérive initiale **0,105 mm**.
- [Essai B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40175696383) : 12 commandes, translation **0,820 mm**, dérive initiale **0,037 mm**, `policy=walk` sur **11/12** échantillons, vitesse appliquée maximale **0,12 m/s**, aucune limitation signalée.
- [Essai C](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176018018) : 24 commandes, translation **1,399 mm**, dérive initiale **0,273 mm**, `policy=walk` sur **23/24** échantillons, vitesse appliquée maximale **0,12 m/s** ; `deadman` rapporté dans un échantillon.
- [Essai D](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817) : 24 commandes, translation **2,574 mm**, dérive initiale **0,192 mm**, `walk` sur **23/24** échantillons, vitesse appliquée maximale **0,12 m/s**, arrêt confirmé et statut `WALK_TRANSLATION_ACCEPTANCE=NOT_MET` dans un workflow techniquement réussi (142 tests Python).

Dans chacun des quatre essais, la mémoire SQLite a mémorisé une **absence de progression** comme fait simulé vérifié (`no_progress_observed`), puis modifié faiblement la préférence `explore` de **0 à −0,075**. Les bases de CI sont éphémères ; la persistance d'un lancement à un autre est vérifiée par tests Python, **pas** par le partage d'une base entre ces **quatre** exécutions.

**Verdict des quatre essais historiques J2e (inchangés) :** le chemin d'intention, l'arrêt, les mesures et la mémoire simulée fonctionnent. **La locomotion n'est pas validée**, malgré `walk` et la vitesse appliquée. Les origines possibles (contacts, adhérence, dynamique du modèle, politique ONNX) restent des **hypothèses**, désormais examinées par les diagnostics P0a/P0b sans modification de sécurité motrice. Ne pas assimiler ces millimètres à une marche réelle, ne pas modifier les limites OEM sans analyse ciblée et ne jamais transposer une preuve de scène MuJoCo en preuve de sécurité physique. Pas d'autonomie matérielle mesurée.

### P0b — Mesures comparatives officielles MuJoCo (25 octobre 2026)

Dans le [workflow de simulation P0b réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40187514292), **16 relevés passifs `stand`** ont été suivis d'**un** essai J2e à 0,12 m/s : 24 commandes, **23/24 politiques `walk`**, vitesse appliquée déclarée maximale 0,12 m/s, `robot.stop` confirmé ; **seulement 1,338 mm** de déplacement final XY (X monde +0,0178 mm, Y monde +1,3375 mm), `no_progress_observed`. Les genoux ont bougé très peu (gauche 0,0223 rad, droite 0,0081 rad), sans établir de pas ou de propulsion. Les fenêtres articulaires du repos et de la marche ne coïncident pas exactement avec la fenêtre de mesure finale de J2e : voir le [rapport distinct](mujoco-p0b-stand-walk-comparison-2026-10-25.md) pour éviter toute soustraction erronée.

Le modèle épinglé comporte des géométries `left_foot_collision` et `right_foot_collision`, mais **aucune mesure des contacts dynamiques ni des cibles articulaires n'est exposée** par l'API constructeur `body_server.op=read`. L'activation `walk` ne prouve ni sol adhérent ni démarche ; cause toujours **inconnue**, seuil de 10 mm **non atteint**, aucun changement moteur OEM ni validation physique.


### P0c — Géométrie des semelles, pas forces (25 octobre 2026)

La [simulation officielle #40188553954](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40188553954) a validé le nouveau **replay géométrique hors ligne** de 40 poses P0b (quaternion complet + articulations), via `mj_forward` sur un MuJoCo séparé. **Les deux semelles chevauchent légèrement le sol à tous les instants échantillonnés** : 16/16 au repos et 24/24 en mouvement (distances de candidats à quelques dixièmes de millimètre). Dans ce **nouvel** essai, vitesse déclarée max 0,12 m/s, `walk` 23/24, déplacement net final seulement **1,997 mm**, `robot.stop` confirmé ; **179 tests Python réussis**.

Il s'agit d'un **proxy de géométrie**, non des contacts dynamiques originaux : pas de mesure de force normale/tangentielle, de friction réelle, de cibles d'actionneur, de glissement ni de décollage éventuel entre trames de 10 Hz. La cause reste **inconnue**, la locomotion et la sécurité sur le robot réel **non validées**. [Rapport P0c](mujoco-p0c-contact-replay-2026-10-25.md).


### P0d — Forces originales du solveur MuJoCo, toujours aucune validation matérielle (25 octobre 2026)

La [première CI officielle P0d](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190232870) a réussi techniquement avec un tap facultatif **dans le processus du simulateur**, sans changement de fichiers constructeur ni d'autorité motrice. Sur **126 trames** échantillonnées pendant l'essai `walk` (~50 Hz), les **deux pieds montrent chacun une force normale supérieure à 0,1 N sur 126/126 trames**. Forces normales moyennes simulées gauche **3,21 N** et droite **4,03 N**. Les consignes des hanches en roulis varient de **0,157 / 0,167 rad** tandis que les angles simulés varient de **0,011 / 0,006 rad**. Nouvel essai J2e : **2,222 mm** de translation, `robot.stop` confirmé, `no_progress_observed` : **marche non validée**.

La sonde mesure des **forces numériques MuJoCo et cibles de position au sein de la simulation**, pas les courants, efforts ou contacts d'un robot réel. Les caches de contacts peuvent être associés à l'état pré-intégration alors que `qpos` est post-intégration ; l'écart consigne-angle est approximatif. La capture ajoute une charge au simulateur (139 µs en moyenne, 452 µs maximum pour la section synchrone du premier essai), non comparable directement à des ressources RK3566. [Rapport P0d et limites](mujoco-p0d-live-solver-2026-10-25.md).


**Répétition P0d après durcissement :** [CI #40190697090](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40190697090) réussie, 190 tests Python, 132/132 trames de marche avec double appui sous charge, translation finale seulement **1,597 mm**. Le calcul descriptif de force par erreur de consigne (roulis hanches et genoux) donne **~0,52–0,55 N·m/rad**, cohérent avec le `kp=0.55` du MJCF épinglé. **Aucune saturation à ±0,96 N·m n'a été mesurée** pour ces articulations. Cette cohérence ne valide pas la locomotion et ne justifie pas un changement de gain sans étude contrôlée. Les limites de temps, de commande, de contact et de transposition au vrai robot restent celles du [rapport P0d](mujoco-p0d-live-solver-2026-10-25.md).


### P0e — Loi d'effort et gains actifs (MuJoCo seulement, 25 octobre 2026)

Le [scénario P0e officiel #40193139617](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40193139617) a réussi avec **199 tests Python**. La sonde facultative du simulateur épinglé a capturé les paramètres d'actionneur **avant** l'appel original `mj_step` (gain, biais, consigne, position, vitesse et limites), et les forces générées par ce même pas. Gains observés **0,44 N·m/rad** au repos (79/79 trames), **0,55 N·m/rad** sur 123/127 trames de marche (4 trames à 0,44). **2 884 valeurs d'effort** des 14 actionneurs correspondent exactement à la loi numérique du modèle, sans écrêtage à ±0,96 N·m sur les phases mesurées. Les deux pieds sont chargés à **127/127 instants de marche**. Pourtant, **2,295 mm** seulement de déplacement net final J2e et arrêt confirmé : la locomotion demeure **non validée**, cause inconnue.

Il ne s'agit pas d'une mesure de moteurs ni d'efforts réels sur RK3566/Microduck. L'instrumentation ajoute une charge Python au simulateur ; le coût de la lecture **avant** pas n'est pas quantifié et le temps de capture après pas ne mesure pas l'impact total. Le résultat mathématique ne démontre pas que la politique ONNX, les gains ou l'adhérence sont adaptés à une démarche physique. [Rapport détaillé P0e](mujoco-p0e-actuator-gains-2026-10-25.md).


### P0f — Contrats ONNX et différences de sources simulées (25 octobre 2026)

[CI P0f MuJoCo headless #40200419709](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419709) réussie avec **207 tests Python**. Les fichiers seedés du simulateur, dont la provenance **v8 est déclarée localement sans signature cryptographique**, sont de forme float32 `obs [1,61] → actions [1,14]` et ne sont pas récurrents. Les 14 références HOME du contrôleur et de l'entraînement concordent à **0 rad**. Sur des entrées **synthétiques**, le réseau de marche réagit au changement vx 0 → 0,12 m/s (norme L2 des sorties **0,147**). Cela ne mesure pas les observations/actions produites par le vrai `robotd` de la simulation. **Aucune nouvelle commande de marche n'a été lancée en P0f**.

Le code des tâches d'entraînement de vitesse, de VelStand et la scène headless utilisent respectivement `robot_walk.xml`, `robot_allcollisions.xml` et `robot_groundcontact.xml`. Dans ces trois XML épinglés : **2 / 69 / 10 balises géométriques explicitement classées `collision`** (total balises géométriques : **85 / 150 / 91**), pas un comptage de contacts actifs ou de géométries effectives après compilation. La provenance d'entraînement exacte des poids ONNX v8 reste à établir avant d'attribuer une différence à un réseau. Le facteur d'action `0,9` dans `robotd`, contre `1,0` déclaré dans une configuration RL de vitesse, n'établit pas seul une incompatibilité sans tenir compte du filtre et du checkpoint.

**Conséquence pour la faisabilité :** nouvelle piste de comparaison de paramètres de contact et de géométries, **pas** un correctif moteur livré, ni une validation de marche. Le dernier essai mesuré reste P0e (**2,295 mm**, seuil 10 mm non atteint). P0g devra comparer hors ligne les trois modèles épinglés avec protocole contrôlé. Le matériel physique, ses capteurs, la chaleur et ses marges de ressource ne sont **toujours pas mesurés**. [Rapport P0f](mujoco-p0f-policy-contract-2026-10-25.md).


### P0g — Comparaison MuJoCo compilée, sans dynamique (25 octobre 2026)

[CI P0g officielle réussie #40208635206](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40208635206) : **214 tests Python sur branche P0g**, 3 variantes OEM en copies temporaires, posture STAND identique ; **76/82/141 geoms compilées** et **2/10/69 masques de contact éligibles pour le sol** pour Walk/Groundcontact/AllCollisions. Même masse de modèle 0,73724318 kg et mêmes paramètres compilés des semelles/sol (friction, solref, solimp), 0 candidat à l'état initial brut **sans pas de physique**, résultat non représentatif du sol sous charge. Aucune modification OEM, aucune commande motrice, aucun test sur robot réel. La cause de non-marche reste inconnue ; la différence de sélection alpha_walking/velstand demeure une hypothèse de provenance à vérifier. [Rapport P0g](mujoco-p0g-compiled-contacts-2026-10-25.md).
