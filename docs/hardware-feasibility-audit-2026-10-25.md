# Audit de faisabilité matérielle — Microduck Companion

Date : 2026-10-25. Audit documentaire et revue de code, **sans accès au robot physique**. Les valeurs de RAM et stockage libres ne sont **pas mesurées**. Aucune capture d'image privée ou donnée biométrique ne doit être placée dans ce dépôt.

## Verdict

Le Microduck permet raisonnablement de viser : mémoire persistante locale, moteur d'autonomie, exploration prudente, observation visuelle événementielle, identification de catégories d'animaux et interaction sociale élémentaire. Il reste à développer et à valider : détection personnalisée d'animaux, identification non biométrique des personnes familières, reconnaissance vocale, exploration sûre en environnement non contrôlé, et intégration du cerveau autonome à robotd. Qwen multimodal se placera initialement sur un PC local.

## Sources de vérité et révisions

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

## Décisions et prochain travail

1. Concevoir un adaptateur `PerceptionEvent` entre observations simulées, `mediad` et le cerveau de Microduck Companion.
2. Simuler une détection multi-classe (animal/personne/objet) et tester la mémoire, les faux positifs et la perte de capteur.
3. Préparer une architecture de reconnaissance d'animaux personnalisée sur PC, entraînable avec données locales ; la conversion RKNN sera validée sur la carte réelle.
4. Associer les interactions humaines à une identité volontaire, sans collecte biométrique par défaut.
5. Différer la décision d'un modèle vision supplémentaire tant que RAM libre, température et cadence du système final n'ont pas été mesurées.

**Statut final : faisabilité d'architecture établie, marge chiffrée de RAM/stockage et fiabilité en conditions réelles non encore établies.**
