# R1 — Contrat passif de métadonnées OEM, seulement sur fixtures

**26 octobre 2026 — étude logicielle sans capture et sans action physique.** R1 réalise la première étape définie par l'[audit R0](oem-reuse-audit-2026-10-26.md) : **réutiliser les parseurs et contrats existants**, ne créer ni nouveau pilote ni nouvelle boucle de perception. La nouvelle façade [oem_passive_fixture.py](../microduck_companion/oem_passive_fixture.py) est un adaptateur **sans socket, fichier, SQLite, appel IA ou moteur** ; elle n'accepte que des données fictives fournies directement par les tests.

## 1. Code existant effectivement réutilisé

| Donnée de fixture | Module / fonction EXISTANTS | Validation réemployée | Résultat R1 |
| --- | --- | --- | --- |
| Notifications **WebRTC** media.video / media.detections | passive_media_router.parse_oem_shape_notification | enveloppe JSON-RPC, géométrie, boîte à une classe, score brut non calibré, limites de taille | nombre de candidats Microducks **non authentifiés**, sans boîte, identité ou catégorie |
| En-tête local media.frame | oem_frame_preflight.parse_mock_frame_header | format UYVY, octets théoriques, limites et âge par horloge murale, réponse RPC | longueur **annoncée**, sans demander ni lire le corps des pixels |
| Trame tof.frame du simulateur / format OEM | sim_ipc.parse_depth et Notification | matrices 8×8, 64 distances et états, horodatage de réception *fictif* | uniquement 64 zones déclarées, séquence et âge local ; **ni obstacle certifié ni sol sûr** |
| Signal sonore d'expérience | passive_media_router.MockAudioCueRouter | schéma **inventé pour tests**, séquence, délai, limite de cadence et vocabulaire borné | signal de test **jamais un vrai événement micro** ; ni transcription ni stop moteur |
| Repli au cerveau | passive_sources.PassiveRead, perception.PerceptionSnapshot | frontière F1/F2 et environnement mock | statut **différent de ok**, événements vides, **aucune écriture mémoire ni intention physique** |

Les notifications media.video / media.detections appartiennent au **canal WebRTC**, pas au socket Unix media.frame. Un hello OEM sur le socket ne prouve ni l'origine d'une notification WebRTC ni sa fraîcheur. Les horloges local monotonic, OEM mono_ns et les temps Unix ne sont pas assimilées : les métadonnées vidéo n'ont **aucun âge de prise de vue prouvé**.

## 2. Garanties du contrat R1

- **Jamais de nouvelle source certifiée :** OEMFixtureMetadata contient toujours category=unknown, source_authenticated=false, motion_authorized=false, 0 moteur, 0 requête PC et 0 octet de média conservé. La classe rejette aussi les tentatives d'instanciation directe visant à forger ces champs.
- **Pas de promotion de signal :** même une notification « duck_candidates_unverified » ne reconnaît pas l'identité d'un Microduck, un événement synthétique « keyword_stop » ne déclenche pas un arrêt moteur, une matrice ToF valide ne garantit pas les escaliers, une frame « header_unverified » ne certifie pas l'existence d'une caméra.
- **Faible rétention :** un accusé par appel avec type de voie, statut, âge éventuellement vérifiable *dans la fixture*, taille d'en-tête et nombre agrégé ; aucune matrice, boîte, pixel, amplitude, texte de voix, photo, identifiant humain ou clé n'est conservé. L'objet inspector garde seulement le dernier numéro et temps de réception ToF fictifs, et réutilise le routeur audio mock pour la limitation de fréquence.
- **Défaillances fermées :** invalidité, source absente, horloge future/stale, temps régressant, duplicata, objets surdimensionnés, champ privé ou sécurité non prévu ne deviennent jamais un événement. La façade ne lance pas de requête réseau ou Unix, pas de thread, pas d'écriture SQLite et aucune instruction robotd.
- **Réutilisation de la mémoire existante :** to_passive_read() transforme une sortie R1 en un PassiveRead F1 **non-ok** avec PerceptionSnapshot mock vide. Les contrats F1-C/F2-A actuels refusent donc l'enregistrement et ne proposent que idle. Pas de nouveau schéma SQLite ni de deuxième cerveau.

### Ce que ce lot ne démontre PAS

Aucune authentification de transport réel, capture UYVY, acquisition microphone, horodatage OEM authentique, lecture physique ToF, classification d'objet, détection de mots-clés, identification de chat/chien/personne, apprentissage de véritable souvenir, déclenchement Qwen, navigation, action ou performance RK3566. Les comptes et longueurs sont ceux **des fixtures**, non des relevés matériels.

## 3. Protocole de validation

Les [tests R1](../tests/test_oem_passive_fixture.py) exercent les quatre voies, les erreurs de schéma et d'horloge, des doublons, des champs de sécurité injectés, la fraude par construction directe de compte rendu et l'intégration de repli avec **le même AutonomyBrain/ExperienceMemory/PassiveObservationJournal que F1/F2**. La suite Python générale rejoue les tests précédents : un changement du contrat doit échouer sans casser les lecteurs existants.

L'[audit R0](oem-reuse-audit-2026-10-26.md) et le nouveau [protocole permanent « réutiliser avant de créer »](development-reuse-protocol.md) guident chaque prochaine PR. [Consignes agents](../AGENTS.md) et [modèle de PR](../.github/pull_request_template.md) servent de rappels obligatoires ; un test de présence n'est pas une garantie automatique contre toute duplication. La revue du code reste requise.

**Critères de sortie R1 :** tests CI positifs sur dernier SHA, démonstration que toutes les sorties restent non authentifiées/non motrices, validation du chemin de repli sans enregistrement ; aucun code OEM modifié, aucun sous-module avancé et aucun nouveau pilote. En cas d'échec, R1 reste **non validé** jusqu'à correction.

## 4. Suite

**R2** : sur PC, vraies prises de vue différentes et consenties du *même objet*, sons enregistrés indépendamment, exemples négatifs similaires, taux de fausses fusions et rejet inconnu, pression CPU/RAM et croissance de SQLite. Un taux observé sur les fixtures R1 n'est pas une métrique de reconnaissance. La livraison du futur M9 par Pollen exige une **nouvelle inspection de code et d'interface**, non un remplacement supposé de notre moteur par défaut.

Les tests ne rendent pas le robot prêt à fonctionner physiquement : mesurer son CPU, la mémoire libre, les capteurs réels, le stockage persisté, la chauffe et la boucle moteur avant tout déploiement.
