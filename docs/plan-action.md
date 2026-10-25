# Plan d'action consolidé — Microduck Companion

**Référence opérationnelle unique · 25 octobre 2026 · Dépôt : `Jean-Philippe56520/Microduck`, branche `main`.**

Ce document précise **ce que nous faisons ensuite**, **dans quel ordre** et **quelles preuves autorisent à franchir un jalon**. La [roadmap](roadmap.md) conserve la vision à six phases et l'historique des changements ; le [plan technique MuJoCo](mujoco-integration-plan.md) conserve les protocoles et les essais J1b–J2e ; l'[audit matériel](hardware-feasibility-audit-2026-10-25.md) garde les limites et hypothèses des cartes. Ce plan est la **source de vérité pour les priorités courantes**, pas une promesse de délai.

## 1. Cible et frontières de sécurité

Construire un petit robot **curieux, explorateur, social et peu bavard**, qui observe, consulte sa mémoire, choisit des **intentions** plutôt que des mouvements directs, évalue les conséquences et fait évoluer lentement ses préférences. `idle` et `rest` sont des choix légitimes. Les fonctions essentielles devront être autonomes **sans PC et sans Internet** ; le PC/Qwen demeure un outil facultatif d'analyse des nouveautés, pas le pilote du robot.

Architecture à préserver :

- `robotd` : seule autorité sur les moteurs, boucle ~50 Hz, politiques constructeur ONNX, garde-fous, arrêt/deadman.
- `mediad` / `tofd` : capture et traitement caméra/audio et ToF 8×8 ; dialogue avec le compagnon via les interfaces officielles JSON-RPC.
- Compagnon : perceptions horodatées et sourcées → SQLite locale → motivations → intention → contrôle indépendant de sûreté → `robotd` → observation du résultat → mémoire.
- PC facultatif : Ollama + Qwen (d'abord 4B, puis 9B **si** les mesures le justifient), hypothèses avec provenance et confiance ; aucune sortie du LLM n'autorise directement une commande motrice.
- Ressources, données personnelles et modèles : pas d'API payante indispensable ; pas d'images/voix stockées en continu ; identités et exemples privés **hors GitHub**.

**Invariant permanent :** source absente, sol incertain, déconnexion, chaleur excessive, batterie basse ou position incohérente → refuser le déplacement ou demander une action sûre. **Une scène MuJoCo certifiée ne certifie jamais le sol d'une habitation réelle.** Le ToF 8×8 n'est pas un LiDAR ni une preuve anti-escalier.

## 2. État réellement vérifié à la date du plan

| Domaine | État | Preuve / limite |
| --- | --- | --- |
| Cerveau Python et motivations | **Codé, testé** | Choix d'intentions, refus si perception incertaine, démonstrations fictives |
| Mémoire SQLite | **Codée, testée** | Épisodes d'objets et expériences simulées ; préférences modifiées après conséquences vérifiées ; tests de persistance |
| Connexion `robotd` et `tofd` | **Simulée et vérifiée** | Démons officiels sous MuJoCo, JSON-RPC, ToF 64 cellules, cadence ~50 Hz |
| Zone de test MuJoCo | **Simulée et vérifiée** | Scène plane officielle épinglée, position du tronc, limites et état du contrôleur |
| Commande `robot.move` puis `robot.stop` | **Simulée et vérifiée** | Ordres bornés via `robotd`, confirmation explicite d'arrêt ; jamais sur robot réel |
| Chaîne résultat → mémoire → préférence | **Simulée et vérifiée pour un essai borné** | `no_progress_observed` et préférence d'exploration légèrement diminuée |
| **Marche/translation effective** | **NON validée — blocage actuel** | À 0,12 m/s demandés et appliqués, seulement **0,820 à 2,574 mm** observés sur quatre essais J2e (seuil expérimental : 10 mm) |
| Perception réelle chien/chat/personne, individus et voix | **À développer / mesurer** | Le détecteur officiel d'autres Microducks ne fournit pas ces catégories automatiquement |
| Qwen sur PC et repli hors connexion | **Prévu, non intégré au compagnon** | Aucune commande LLM de moteur autorisée |
| Cerveau embarqué et autonomie matérielle | **Non validés** | Robot physique indisponible ; CPU, RSS, RAM libre, chauffe et batterie réelle non mesurés |

**Tests logiciels :** **151 tests Python** réussis sur [GitHub Actions de la branche P0a](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580633). Le dernier essai MuJoCo J2e a terminé avec succès **technique**, mais avec `WALK_TRANSLATION_ACCEPTANCE=NOT_MET` : [journal du test](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40176410817).

Le comptage des tests correspond à cet état du dépôt : le mettre à jour **uniquement après un nouveau résultat CI**, pas à chaque révision documentaire.

## 3. Ordre de réalisation et dépendances

| ID | Priorité | Lot / livraison attendue | Dépendance | État |
| --- | --- | --- | --- | --- |
| **P0** | **Immédiate, bloquante** | Expliquer l'absence de locomotion dans la scène MuJoCo épinglée | Simulateur officiel J2e | **P0a instrumenté et testé en MuJoCo ; P0b à faire, cause inconnue** |
| **P1** | Haute | Démontrer une translation puis une démarche *mesurée* et sûre, sans contourner `robotd` | P0 | À faire |
| **P2** | Haute | Boucle autonome répétable perception → intention → action → effet → mémoire → choix suivant | P1 pour le déplacement ; cognition sans déplacement indépendante | Partiellement codée |
| **P3** | Haute | Vision/sons légers : catégories d'objets et d'animaux, signaux sociaux, inconnus | Contrats de perception existants ; validation d'une source mesurée | À faire |
| **P4** | Moyenne | Mémoire sémantique/spatiale et comportement social prudent, reconnaissance individuelle volontaire | P2 + P3 | À faire |
| **P5** | Moyenne | Assistance Qwen locale facultative (PC), hypothèses vérifiables et repli autonome | P2 + premières observations P3 | À faire |
| **P6** | Après mesures | Préparation embarquée Rust/SQLite, audits ressources, contrôle des latences | P2/P3 et accès au matériel pour la validation | À concevoir ; matériel absent |
| **P7** | Après réception | Essais progressifs sur vrai Microduck en zone contrôlée | P1–P6 selon la fonction, mesures physiques | Non commencé |
| **P8** | Optionnel | Automatisations sous consentement (ex. porte ouverte → alerte e-mail) | Détection fiable + réseau/service autorisé | Idée, pas une fonctionnalité codée |

L'ordre P0 → P1 → P2 est le **chemin critique pour l'exploration mobile**. Les tests de perception **sans commande motrice** (P3) peuvent avancer en parallèle si P0 se révèle plus difficile que prévu. Aucun blocage de marche ne justifie de modifier arbitrairement les moteurs du constructeur.

## 4. Exécution par lots et critères de sortie

### P0 — Diagnostiquer `walk` sans translation (première PR)

**Fait observé :** lors d'un essai de 24 notifications à 0,12 m/s, `robotd` a déclaré `walk` sur 23/24 échantillons, une vitesse appliquée proche de la commande et seulement **2,574 mm** de déplacement du tronc. L'activation de `walk` **ne prouve pas** une marche effective.

1. Vérifier la révision épinglée et les références OEM : sélection de politique, normalisation des observations, repères et unités du simulateur, contrôle de l'état `stand`/`walk`/`held`.
2. Ajouter **en lecture seule** un diagnostic horodaté : pose du tronc au cours du temps, vitesse mesurée, mouvements des articulations, commandes et états de politique, état et contacts des pieds si l'API MuJoCo les fournit. Ne pas inventer un contact que la source ne publie pas.
3. Comparer **à paramètres inchangés** : repos, `vx=0,12`, politique appliquée, contacts, progression, échauffement impossible à simuler. Vérifier la cohérence du serveur du corps avec la physique sans retoucher les modèles OEM.
4. Classer les hypothèses (ex. glissement, pieds verrouillés, repères/commandes, politique instable) comme **hypothèses** tant qu'un test n'a pas isolé la cause.

**Sortie P0 :** journal reproductible sur un MuJoCo officiel épinglé, diagnostic de la cause avec preuve ou mention explicite « cause encore inconnue », et tests nouveaux pour les mesures ajoutées. Pas d'augmentation automatique de vitesse ni de désactivation du deadman.

### P1 — Établir une locomotion réelle dans la zone simulée

1. Corriger **notre intégration** si le diagnostic P0 démontre une erreur chez nous. Si l'origine est OEM, conserver les mécanismes et documenter l'écart ; proposer un changement constructeur seulement avec justification et revue de licence/compatibilité.
2. Définir une courte trajectoire et mesurer : déplacement net, dérive sans commande, progression avant, écart latéral, contacts/pose et arrêt.
3. Répéter l'essai dans la **même scène épinglée**, avec limites de zone, expiration des intentions, arrêt confirmé et santé `robotd` surveillée. Zéro décision de marche si le sol ou l'état deviennent inconnus.

**Premier seuil de sortie :** au moins **10 mm de translation nette**, distinguables de la dérive, sur **trois essais indépendants** sans perte des protections. Ce seuil est un **critère proposé**, pas une performance actuelle. Il valide une translation, **pas** une démarche stable. Pour parler de démarche, ajouter ensuite un essai de progression soutenue d'au moins **5 cm** avec contacts, stabilité et absence de chute contrôlés ; revoir ces critères à partir du comportement réel du modèle plutôt que forcer les chiffres.

### P2 — Boucle d'autonomie et mémoire durable

1. Séparer clairement un essai diagnostic volontaire (J2e actuel) d'une boucle autonome non bloquante, avec intentions à durée limitée et aucun pilotage direct des articulations.
2. Gérer plusieurs décisions sûres (observer, regarder, explorer seulement si autorisé, jouer, `idle`, `rest`), plafonner la fréquence des initiatives, éviter les répétitions et supporter la perte de capteur au milieu de l'action.
3. En SQLite, conserver épisodes, provenance, horodatage, résultat, confiance et corrections. Ne modifier la préférence qu'après une conséquence **observée** ; séparer les hypothèses Qwen.
4. Test de réouverture de base entre **deux sessions distinctes** (pas seulement une base éphémère CI par exécution) et vérification que des échecs répétés influencent réellement une décision ultérieure.
5. Mesurer latence perception → intention, délai d'arrêt, cadence des moteurs, épisodes utiles, répétitions et raisons de refus.

**Sortie P2 :** démonstration reproductible en simulation **sans Qwen**, avec plusieurs cycles et un souvenir réutilisé après redémarrage ; arrêt sûr sur perte de source ; pas de boucle motrice bloquée.

### P3 — Perception d'objets, animaux et signaux sonores

1. Construire des jeux de test **fictifs ou expressément autorisés**, cloisonnés des données personnelles. Tester l'acheminement des événements par `mediad`/adaptateurs et le suivi d'objets ; MuJoCo n'émule pas les pilotes caméra/NPU.
2. Distinguer **détection d'une catégorie** (chien, chat, personne, jouet) et **identité individuelle**. Détecter « chien » ou « chat » ne prouve pas que l'animal est un individu familier. Conserver « inconnu » si la confiance manque.
3. Étudier de petits modèles légers, RKNN/NPU si effectivement compatibles et repli ONNX/CPU, avec cadence limitée et mesure de précision/rappel/faux positifs sur un ensemble séparé. Les mesures constructeur YOLO ne valident pas nos modèles.
4. Étudier les sons déjà accessibles ; essayer un détecteur de mots-clés local (« Microduck », « stop », « viens ») sans imposer de dialogue constant. `stop` doit conserver une voie de sécurité claire et prioritaire.

**Sortie P3 :** tests sur jeux annotés, métriques et taux d'inconnus documentés, provenance vérifiée et absence d'actions dangereuses en cas de fausse détection. Aucune promesse de reconnaissance individuelle par défaut.

### P4 — Comportement social, mémoire spatiale et reconnaissance volontaire

1. Ajouter une mémoire sémantique (propriétés d'objets), spatiale (repères avec incertitude) et comportementale (préférences/conséquences) sans multiplier les schémas inutiles.
2. Faire évoluer les motivations **progressivement** selon les résultats ; autoriser le repos, la curiosité, le jeu et les interactions discrètes.
3. Pour les personnes familières, privilégier des interactions ou balises **volontaires**, avec contrôle parental quand un enfant est concerné, **aucune biométrie permanente** et aucune identité privée dans le dépôt. Pour les animaux familiers, ne confirmer aucune identité individuelle sans preuve mesurée et autorisation adaptée.

**Sortie P4 :** interactions en simulation reproductibles, inconnus correctement préservés, souvenirs réellement consultés et absence de collecte permanente de voix/images.

### P5 — Qwen facultatif sur PC local

1. Expérimenter Ollama/Qwen multimodal **4B puis 9B** sur le PC disponible, en mesurant latence, consommation mémoire, qualité d'hypothèses et taux d'erreurs ; ne présumer aucune accélération GPU/NPU.
2. N'appeler le PC qu'en cas de nouveauté, contradiction ou difficulté. Définir budget de requêtes, délai, réponse typée, provenance et moyen de corriger une hypothèse.
3. Vérifier coupure réseau, PC absent et réponse fausse : choix sûr et fonctions locales maintenus ; **aucun chemin de commande moteur depuis Qwen**.

**Sortie P5 :** scénarios avec/sans PC comparés et chiffrés, moteur autonome local intact, sorties du LLM vérifiables et jamais transformées en faits non observés.

### P6 — Préparation embarquée et ressources

1. Réserver Rust aux fonctions embarquées qui le justifient, conserver les interfaces publiques et un SQLite persistant privé sous `/var/lib/robot/` ; aucun LLM embarqué obligatoire.
2. Préparer les profils : RAM réellement disponible, RSS des services, stockage libre, CPU, température, fréquence `robotd`, latence des perceptions et arrêts ; comparer repos, vision et déplacement.
3. Mesurer **sur la carte réellement reçue** avec `scripts/resource-audit.sh` ; distinguer carte Zero 3W et carte beta Seeed, stockage commercial et partitions disponibles. Ne pas inventer de marge mémoire ou d'autonomie énergétique.
4. Limiter la vision/activité si ressources ou température se dégradent ; préserver les mécanismes Yocto et les mises à jour OEM.

**Sortie P6 :** profil matériel reproductible et budgets fondés sur les mesures. Tant que le robot est absent, ce lot est une **préparation**, jamais une validation.

### P7 — Validation physique progressive (après livraison)

Essais de repos/observations, puis orientations de tête, puis déplacements très courts en **zone fermée et surveillée**, enfin interactions prudentes. Ne pas déclarer les escaliers sûrs ni l'évitement d'animaux mobiles avant tests spécifiques. Tester perte réseau, perte ToF/caméra, batterie faible, chauffe et arrêt, avec enfants et animaux à l'écart des premiers déplacements.

**Sortie P7 :** mesures sur le robot réel et preuve des garde-fous dans le contexte physique ; autonomie hors PC démontrée. Les résultats MuJoCo ne remplacent aucune de ces preuves.

### P8 — Fonctions optionnelles, après le socle de sûreté

Exemple déjà évoqué : **porte ouverte → alerte e-mail**. À tester plus tard avec un capteur ou une perception de porte validée, règle utilisateur explicite, destinataire autorisé, délai anti-répétition et journal d'envoi. Une alerte e-mail nécessite réseau et service de messagerie configuré ; **ce n'est pas une fonction actuelle**, ni une priorité devant la sécurité et l'autonomie.

## 5. Trois prochaines PR concrètes

| Livraison | Changement ciblé | Vérifications indispensables |
| --- | --- | --- |
| **PR #11 — P0a (validée en collecte MuJoCo)** | Diagnostic passif et horodaté des articulations, vitesses, pose et `robot.state.policy` ; pas de commande nouvelle. Contacts et cibles articulaires **absents** du protocole OEM : `null`, sans inférence. | Tests Python de branche [réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580633), collecte passive MuJoCo [réussie](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580637) : 8 échantillons `stand`, 0,991 mm de dérive en 1,4 s, 0 commande ; scène/processus épinglés et fail-closed. Cause de la marche encore inconnue. |
| **P0b** | Diagnostic comparatif repos/`stand`/`walk` à modèle OEM identique ; mesurer la cause des millimètres observés | Journal des contacts, articulation, distance, dérive, limites et arrêt ; résultat « expliqué » ou « non expliqué », sans falsifier |
| **P1a** | Seulement après diagnostic, correction ciblée de l'intégration et essai de translation courte | Trois essais mesurés, critère 10 mm, arrêt/deadman, absence de chute, état `robotd` et logs CI |

Si P0 révèle un problème dans une politique officielle impossible à corriger proprement, **ne pas bloquer tout le projet** : poursuivre en parallèle la cognition immobile, la perception sur jeux de test et la mémoire, sans présenter ces fonctions comme une navigation autonome.

## 6. Mesures communes et validation de chaque PR

Chaque livraison doit présenter :

- **Statut distinct :** `prévu`, `codé`, `test logiciel réussi`, `validé en MuJoCo`, `validé sur robot`. Jamais « validé » sans nommer l'environnement.
- **Résultat mesuré :** lien GitHub Actions, révision OEM, scène, source des signaux, unités, durée, répétitions, erreurs et limites. Pour une marche : ligne de base, trajectoire, contacts, glissement, chute et arrêt.
- **Sécurité :** autorisation explicite, délai court, échec fermé, séparation cerveau/`robotd`, aucun blocage de la boucle à 50 Hz ; déconnexion et surchauffe traitées quand l'environnement les rend mesurables.
- **Mémoire :** quelle observation est un fait, quelle hypothèse ne l'est pas, quelle préférence a changé, et preuve que la base peut être relue.
- **Qualité :** tests pertinents ajoutés, suite CI verte, documentation mise à jour et aucune donnée privée dans les commits.

Les indicateurs de précision de vision, de RAM, de températures et d'énergie doivent être **mesurés dans leur véritable environnement**. Ne pas convertir une taille de modèle en besoin de RAM ni une absence de chute MuJoCo en sécurité réelle.

## 7. Règles de maintien de ce plan

- **Ce fichier = prochaines actions et critères de passage.** `roadmap.md` = détail des phases et historique ; `mujoco-integration-plan.md` = procédures/essais J1b–J2e ; audit = limites matérielles. Ne pas gérer quatre backlogs concurrents.
- Mettre à jour dans une même PR : état et prochaine action ici, résumé et lien en haut du README, historique du jalon dans la roadmap, audit **uniquement si** une nouvelle preuve change l'évaluation.
- Garder les quatre essais négatifs J2e comme **historique inchangé** ([détails de mesure](hardware-feasibility-audit-2026-10-25.md)) et consigner séparément les prochains essais plutôt que réécrire les échecs.
- Des tests GitHub Actions verts ne signifient pas que la marche fonctionne. La fonction est acceptée seulement si **son propre critère physique/simulé** est atteint.
- Ne pas attribuer de date de livraison ni de seuil de consommation tant que les contraintes et mesures réelles n'existent pas.

**Décision actuelle : passer à P0b après [PR #11](https://github.com/Jean-Philippe56520/Microduck/pull/11) et [test P0a MuJoCo réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40178580637).** Les articulations et politiques sont accessibles via la lecture OEM ; les **contacts des pieds et les consignes articulaires ne sont pas exposés par ce protocole**, et ne doivent jamais être inventés. Aucun résultat de cette sonde ne valide une démarche ni le matériel réel.
