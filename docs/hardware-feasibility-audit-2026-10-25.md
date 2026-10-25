# Audit de faisabilité matérielle — Microduck Companion

Date : 2026-10-25. Audit documentaire et revue de code, **sans accès au robot physique**. Les valeurs de RAM et stockage libres ne sont **pas mesurées**. Aucune capture d'image privée ou donnée biométrique ne doit être placée dans ce dépôt.

**Mise à jour de cohérence :** le [plan d'action consolidé](plan-action.md) fixe les priorités et les critères de passage. Quatre essais MuJoCo J2e, documentés ci-dessous, ont validé la chaîne de commande et de mémoire **mais pas la locomotion** (au mieux **2,574 mm** de mouvement du tronc). **P0a : diagnostiquer contacts et articulations en lecture seule.** Les anciennes décisions de faisabilité ci-dessous sont conservées comme historique, pas comme une seconde liste de tâches à exécuter.

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

**Verdict après quatre essais :** le chemin d'intention, l'arrêt, les mesures et la mémoire simulée fonctionnent. **La locomotion n'est pas validée**, malgré `walk` et la vitesse appliquée. Les origines possibles (contacts, adhérence, dynamique du modèle, politique ONNX) restent des **hypothèses**, à investiguer en **P0a** sans nouvelle commande motrice. Ne pas assimiler ces millimètres à une marche réelle, ne pas modifier les limites OEM sans analyse ciblée et ne jamais transposer une preuve de scène MuJoCo en preuve de sécurité physique. Pas d'autonomie matérielle mesurée.
