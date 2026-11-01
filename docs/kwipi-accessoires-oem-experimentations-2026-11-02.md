# Kwipi — accessoires officiels Microduck et idées d'expérimentations futures

**Date de l'inventaire :** 2 novembre 2026. **Statut :** NOTES PROSPECTIVES / NON CODÉ / NON TESTÉ SUR ROBOT.
**Référence Companion :** [main@0cd8430](https://github.com/Jean-Philippe56520/Microduck/tree/0cd843029b4ff9683135343d1431cb4f4f117dca).
**Référence constructeur épinglée :** [microduck@942e58e](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) ; consultation de l'amont [main@b2b0d21](https://github.com/pollen-robotics/microduck/tree/b2b0d213a402caeac492dd662ea891faa17f67c0) le 02/11/2026.
**Autorité des priorités :** [plan-action.md](plan-action.md), [protocole réutiliser avant de créer](development-reuse-protocol.md), [plan expérientiel](kwipi-experiential-learning-plan-2026-10-26.md) et [plan perception OEM](perception-oem-rknn-2hz-plan-2026-10-29.md).

> Journal destiné à préserver des idées discutées avant réception du robot, notamment la curiosité spontanée pour un accessoire et l'affichage de souvenirs. **Aucune nouvelle fonctionnalité, permission motrice, dépense ou priorité de développement n'est décidée ici.** Une annonce commerciale, une API documentée et une compétence réellement validée sur notre robot sont trois niveaux différents.

## 1. Inventaire vendeur : produits Microduck vérifiés

Sources commerciales officielles, consultées le 02/11/2026 :
- [Microduck](https://store.pollen-robotics.com/products/microduck) : batterie NP-F550 amovible, autonomie annoncée proche de 1 h, une caméra, ToF frontal 8 × 8, deux antennes NFC annoncées (tête et bec), manette incluse, RK3566 et 1 Go de RAM.
- [Accessory Pack](https://store.pollen-robotics.com/products/accessory-pack) : **33 EUR affichés** ; deux roulettes, un pointeur laser, un écran NFC Polaroid couleur à encre électronique de 1,54 pouce, dix tags NFC et une balle.
- [Dev Pack](https://store.pollen-robotics.com/products/dev-pack?variant=58531128967542) : **99,99 EUR affichés** ; trois moteurs de rechange, cinq câbles moteur, deux batteries, un chargeur double, dix tags NFC, crédit Hugging Face (valeur non confirmée), tournevis et vis.
- [Charger Pack](https://store.pollen-robotics.com/products/charger-pack) : **33 EUR affichés** ; deux batteries et un chargeur double.
- Ces prix et configurations sont révisables ; TVA et livraison dépendent de la commande. **Le kit NFC destiné à Reachy Mini n'est pas un accessoire Microduck validé.**

Le Dev Pack comprend déjà deux batteries et un chargeur double : ne pas acheter le Charger Pack par erreur en pensant obtenir une fonction différente. La présence de plusieurs batteries signifie **remplacement manuel**, pas deux emplacements, addition automatique des capacités, fonctionnement simultané ou changement à chaud prouvé. Prévoir l'arrêt propre et le rappel du contexte SQLite au redémarrage, à qualifier.

## 2. Hypothèses d'interaction, par objet

| Élément | Fonction constructeur / source | Possibilité intéressant Kwipi | État et limite |
| --- | --- | --- | --- |
| **NFC Polaroid** | La boutique décrit un écran couleur E-Ink NFC 1,54 pouce à présenter **contre la tête** pour voir les « rêves » ; formule marketing, pas rêve mesuré. | Afficher un pictogramme, une question, une représentation non privée d'un souvenir ou d'une découverte lors d'un rapprochement volontaire. | **Idée seulement.** Protocole de transfert des images, compatibilité des lecteurs et interface OEM de l'écran non établis. Ce n'est ni une caméra, ni une imprimante, ni un écran vidéo continu. |
| **Tags NFC** | Le code OEM sait sélectionner et lire des NTAG215 de type 2 et des enregistrements NDEF texte/URI ; la fonction actuelle de nfcd concerne surtout l'appairage Bluetooth d'une manette. | Associer prudemment une étiquette à un objet ou une station d'exploration ; éviter de redemander la même information lorsque le tag est connu. | L'identifiant d'un tag n'est pas une preuve visuelle, une identité physique sûre ou une distance. Interface d'événements NFC généraux vers Companion **non livrée**. |
| **Roulettes** | Choix de politique OEM « walk » / « roller », mode décrit dans le constructeur. | Comparer exploration supervisée à roulettes et marche, puis seulement envisager un comportement autonome borné. | **Support logiciel OEM**, mais disponibilité des politiques effectivement chargées et essai physique inconnus ; ne pas supposer navigation libre ni autonomie. |
| **Balle** | Une balle vendue ; les gestes de kick OEM existent sous conditions. | Observer un objet, retrouver son contexte en mémoire, interagir si cible/force/sol/effet sont suffisamment qualifiés ; jeu social hypothétique. | Détection multi-catégories et effet indépendant en conditions réelles non validés. « kick accepté » ne veut pas dire ballon touché ou jeu appris. |
| **Laser du pack** | Pointeur externe vendu pour des interactions basées sur un point lumineux. | Observation d'un repère lumineux **seulement si** un besoin scientifique pertinent, un détecteur validé et la sécurité optique le permettent. | Pas de poursuite autonome validée. **Ne pas confondre avec le laser interne ToF** ; ne pas viser des yeux, personnes ou animaux. |
| **Manette incluse** | Prise en charge OEM ; commandes et tests supervisés possibles, appairage par NFC sous conditions. | Témoin humain et arrêt/contrôle pendant des essais mécaniques. | Ce n'est pas une source d'autonomie ni de causalité. |
| **Batteries/chargeur** | Batteries amovibles et chargeur double. | Essais plus longs, validation de reprise après changement de batterie et sauvegarde de la mémoire. | Capacité à utiliser deux batteries **en parallèle** ou à changer sans éteindre : inconnue/non documentée ; ne pas improviser de câblage. |
| **Pièces, câbles, vis, outils** | Maintenance et réparation. | Remplacement après usure, étude de la fiabilité. | Ne délivrent aucune nouvelle compétence de cognition ou perception. |
| **Crédit Hugging Face** | Offre Dev Pack. | Option de développement ou d'entraînement sur PC, séparée du robot. | Montant, conditions et utilité réelle à vérifier ; ne rend pas le modèle Qwen embarqué. |

## 3. Point critique : lecture NFC != affichage du Polaroid

- La fiche Microduck annonce **deux antennes NFC, tête et bec**. Dans [nfcd épinglé](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/nfc/src/main.rs), la variante bêta peut utiliser un **ST25R100 SPI à deux antennes** ; le lecteur CLRC663 sur USB est également prévu et le logiciel gère son absence. **La version exacte livrée au propriétaire doit être vérifiée à réception**, sans supposer le lecteur présent et opérationnel.
- Le code [tag.rs](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/nfc/src/tag.rs) sélectionne des tags ISO-14443A / NTAG215 et lit leur mémoire ; il ne donne pas une position à distance et refuse les collisions de tags. [ndef.rs](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/nfc/src/ndef.rs) analyse texte/URI. La boucle nfcd (~5 Hz par défaut) exploite surtout une adresse Bluetooth de manette ; aucune API de découverte générique pour Companion n'a été identifiée dans les sources examinées.
- Des tags vierges NTAG215 peuvent être **personnalisés** à l'aide d'un téléphone/encodeur NFC compatible ; fabriquer physiquement une puce n'est pas nécessaire. La portée est typiquement de **quelques centimètres** et non de mètres, mais **aucune portée tête/bec n'est mesurée sur ce Microduck**. Un UID ou une chaîne NDEF peut être copié et ne doit pas être traité comme une identité non falsifiable.
- La page OEM nommée [card_polaroid.html](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/spaces/vetbook/card_polaroid.html) est une **carte Web de présentation**, pas un pilote démontré de l'écran NFC physique. Ne pas déduire un service d'envoi d'image de ce nom.
- Le fonctionnement du Polaroid annoncé par la boutique nécessite de **le présenter à la tête**. Le bec n'est pas requis pour porter l'objet. Le logiciel nfcd examiné ne prouve pas qu'il peut écrire des images vers l'accessoire ; demander la documentation/protocole du fabricant avant de coder.
- **Ne pas ajouter automatiquement un deuxième tag NFC sur l'écran** : risques d'interférence radio et ambiguïté des lectures. Un repère visuel distinct sur un support stable est un meilleur premier témoin ; un tag éventuellement placé sur le support devra être testé à part, sans confondre « support détecté » et « écran mis à jour ».

## 4. Scénario prospectif principal : Kwipi curieux du Polaroid

**Intention narrative, non capacité livrée :** Kwipi remarque le petit objet, sa curiosité lui donne envie d'y porter attention, il le revoit sous un autre angle, le compare à un souvenir, s'approche éventuellement et cherche à présenter sa tête/antenne. Il peut choisir de ne rien faire si la scène, l'objectif ou la sécurité ne le justifie pas.

Étapes observables à prouver **séparément** :

1. **Voir sans inventer** : mediad / RKNN propose une région ou un repère visuel frais, sans prétendre reconnaître forcément le Polaroid ; faux positifs sur écran, photo, objet ressemblant et scène vide à mesurer. Le NFC ne sert pas au repérage lointain.
2. **S'intéresser** : F2 / DET-1 et le rappel local choisissent *observer / attendre / inaction* ; pas de geste déclenché par Qwen ou par un simple score de ressemblance.
3. **Positionner sans collision** : commencer robot immobile, support stable et opérateur ; orientation de tête OEM uniquement si la posture et l'enveloppe sûre sont qualifiées. **Aucun contact appuyé ou « poser la tête dessus » autonome** tant que les efforts, l'alignement et l'arrêt ne sont pas prouvés.
4. **Valider la communication** : NFC effectivement lu sur la bonne antenne ; distinguer lecture de tag, alimentation de l'écran et transfert d'image vérifié, sans créditer un effet juste parce qu'une commande est acceptée.
5. **Option ultérieure de locomotion** : seulement après résolution des blocages SIM-E2 et validation OEM réelle du déplacement et des protections de sol. Le ToF 8×8 frontal n'est pas un capteur anti-escalier 360° ; pas de navigation libre présumée.
6. **Mémoriser avec prudence** : un événement NFC/une image affichée ne deviennent une expérience causale que si **fin OEM attestée + effet indépendant** ; hypothèse Qwen et ressemblance visuelle restent rétractables. Réutiliser l'unique ExperienceMemory.

Le support de Polaroid pourrait devenir un objet d'exploration *intéressant*, sans objectif obligatoire : curiosité, repos, attention sociale et inaction doivent rester possibles. Pas de « routine Polaroid » codée à l'avance comme comportement intelligent factice.

## 5. Registre d'essais futurs : ordre et portes (ne pas lancer maintenant)

| Porte | Objectif minimal / existant à réutiliser | Témoin positif et négatifs | Passage / STOP |
| --- | --- | --- | --- |
| **A0 — audit matériel documentaire** | Comparer fiche vendeur, variante physique, firmware réel, doc OEM NFC et protocole Polaroid ; aucun programme à modifier. | Positif : version de carte et interface documentées ; négatifs : lecteur absent, doc de transfert indisponible, incompatibilité. | **STOP** si lecteur ou protocole requis non disponible ; laisser en attente, ne pas créer un second pilote. |
| **A1 — démonstration manuelle Polaroid** | Personne tenant écran sur tête du robot immobile, méthode fabricant, objet de test non privé. | Positif : affichage visiblement confirmé ; négatifs : mauvais côté, écran absent, plusieurs tags, interruptions. | Consigner durée, réussite/échec, modèle écran/lecteur ; **STOP** si contact dangereux ou résultat non reproductible. |
| **A2 — perception sans mouvement** | mediad OEM + GT indépendante de plusieurs vues basses ; comparaison région/repère vs absence de région. | Positif : objet/support réel nouveau ; négatifs : écran affichant son image, photo, éclairage changeant, occlusion, objet presque identique. | Fixer avant essai précision/abstention, coût RAM/RSS/latence et seuils d'arrêt ; ne pas entraîner sur les images de contrôle. |
| **A3 — curiosité sans contact** | F2, ExperienceMemory et intention d'orienter/attendre d'abord en fixtures, puis OEM supervisé seulement si permis. | Positif : observation nouvelle vraiment pertinente ; négatifs : souvenir trompeur, source périmée, Qwen absent, demande répétitive, sol inconnu. | Amélioration mesurée vs décisions sans mémoire ; refus/inaction si doute, pas de récompense arbitraire. |
| **A4 — antenne proche, tête supervisée** | Utiliser robotd / robotctl et nfcd existants, avec support mécanique non agressif. | Positif : RF fonctionne sans appui et geste clos OEM ; négatifs : non-alignement, tag concurrent, absence de résultat, perte de suivi, arrêt demandé. | **STOP** au contact non maîtrisé, à une collision ou à un défaut de santé/latence moteur ; aucune boucle de force ad hoc. |
| **A5 — déplacement et expérience complète** | Même pile OEM ; seulement quand perception, locomotion, sécurité et A1-A4 sont prouvées sur matériel. | Positif : séquence authentifiée + fin OEM + résultat indépendant ; négatifs : objet déplacé, obstacle, personne à proximité, escaliers, faux souvenir, absence PC. | Pas de promotion sans effet indépendant ; arrêt en cas de risque ou de gain nul. |

**Critères chiffrés, nombres de scènes, ressources et tolérances** : à *préenregistrer avant chaque essai*, en fonction des moyens réellement disponibles. Ce document n'est pas un benchmark ni une autorisation de démarrer ces essais.

## 6. Idées cognitives à conserver, sans nouveau chantier

- Différencier **apprendre de ses expériences** (faits sourcés, correction, rappel, stratégies) de **réentraîner un réseau neuronal** ou de réaliser de l'apprentissage par renforcement moteur ; Kwipi vise une **architecture cognitive hybride embarquée**, pas un LLM permanent dans 1 Go de RAM.
- Exemple : balle observée, relation « peut rouler » proposée, test éventuel sûr et effet indépendant mesuré ; autre scène avec humain ou chaussette = nouvelles **hypothèses** de relation/usage, jamais « quelqu'un l'attrapera » comme fait garanti.
- Si un objet est inconnu, la connaissance obtenue de **Qwen3.5 9B PC facultatif** doit rester une suggestion sourcée et corrigible ; l'apprentissage local doit fonctionner sans PC. Pas de copie de SQLite, pas d'ordre moteur depuis Qwen, pas de données privées envoyées par défaut.
- Inspirations discutées : **MiRo-E** (comportements autonomes), **aibo** (compagnonnage durable), **iCub** (expérimentation active d'objets) et **Voyager** (bibliothèque de savoir-faire en environnement simulé). Ce sont des **références exploratoires** ; aucune supériorité de Kwipi sur ces projets n'est établie.
- Mesure de valeur cible : mêmes scènes inédites **avec et sans mémoire** (puis **avec et sans Qwen**) ; meilleure pertinence des observations/décisions et des corrections, sans hausse de fausses certitudes ni d'actions risquées. Réutiliser PER-SENSE, M1, EX4 et les jalons existants.

## 7. Décision, limites et réemploi

**Décision au 02/11/2026 : conserver ces options comme hypothèses non prioritaires.** Les achats restent facultatifs ; ni le Polaroid ni le NFC ne doivent bloquer la distribution V1 P16/P17, la perception, la mémoire ou la qualification robot. La priorité continue à être celle du [plan directeur](plan-action.md).

**Réutiliser :** robotd/robotctl pour tout geste, mediad pour la caméra, tofd pour la distance, nfcd constructeur pour la lecture si matériel présent, F2/DET-1 pour l'intérêt, ExperienceMemory mono-écrivain pour le rappel, Qwen 9B PC uniquement si utile et autorisé.

**Adapter plus tard, uniquement après preuve d'un gain :** exposer un événement NFC via une interface OEM existante et strictement bornée ; composer une image de petit format si un protocole documenté de transfert à l'écran existe. **Créer :** aucun composant dans ce lot documentaire ; pas de nouveau service lecteur NFC, caméra, pilote moteur, SQLite ou permission générale.

**Risques / arrêt :** interférences de tags, collisions tête/écran, chute en marche, défaut de reconnaissance, laser dirigé vers des yeux, surchauffe, perturbation de la boucle 50 Hz, identification trompeuse, divulgation d'images/souvenirs, achat inutilisable. L'absence de source ou de résultat est « inconnu/en attente », pas « fonctionne ». Retour arrière de ce lot : retrait de la note et des deux liens d'index ; aucun runtime, poids, gitlink OEM ni matériel modifiés.

**Preuve réelle de ce lot :** vérification documentaire de fiches constructeur et de fichiers OEM épinglés, puis dépôt de cette fiche. **Zéro** test PC nouveau, simulation MuJoCo, commande motrice, installation, NFC physique, affichage ou essai robot dans ce lot.
