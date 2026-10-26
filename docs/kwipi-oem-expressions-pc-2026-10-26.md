# Kwipi — P-C : expressions contextuelles, sans second système audio

**Date : 26 octobre 2026. Statut : contrat et prototype de descriptions sur fixtures.**
P-C prolonge [P-A : 16 états historiques](kwipi-behavior-personality-16states-2026-10-26.md) et [P-B : habitudes](kwipi-personality-continuity-pb-2026-10-26.md). Il ne remplace pas la priorité **Cat-A2** et **ne permet aucun son, regard ou mouvement réel**. Kwipi n'est pas présent pour des essais physiques.

## 1. Audit réutiliser / adapter / créer

| Source vérifiée | Existant/limite | Décision |
| --- | --- | --- |
| [OEM épinglé `942e58e3aa6dbb28e7037203fff11866122c7567`](https://github.com/pollen-robotics/microduck/tree/942e58e3aa6dbb28e7037203fff11866122c7567) : `pet-detect/src/worker.rs`, `pet-detect/README.md` | **Un seul micro/arecord**. `PettingEvent::Start/End` par classifier avec hystérésis ; `SoundEvent::Noise/Voice` par sentinelle RMS. **Voice n'est ni transcription ni reconnaissance d'« Hé Kwipi ! ».** | **Réutiliser plus tard les événements OEM**, sans créer de second microphone, classifieur, modèle ou canal audio |
| [`robotd/src/main.rs` autour des lignes 2604–2628](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/main.rs#L2604-L2628) | Sur `PettingEvent::Start`, `robotd` peut **déjà jouer `coo` si non tombé/occupé**. Les événements sonores ambiants sont **uniquement journalisés** (aucune réponse autonome). | **Ne jamais rejouer `coo`** ni déduire qu'il a effectivement été émis |
| [`robotd/src/idle_head.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/robotd/src/idle_head.rs) et [`sounds/src/personality.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/sounds/src/personality.rs) | Regards et bâillements idle déjà sous `robotd`; voix à traits stables selon une graine dans l'OEM | **Ne pas créer** seconde animation de repos, voix synthétisée ou personnage vocal concurrent |
| [OEM 16 états historiques](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/ideas/autonomous_behavior.md) et [PR #381](https://github.com/pollen-robotics/microduck/pull/381) | `Petted` / `Startle` figurent au catalogue historique ; M9 non porté, PR #381 **ouverte, non fusionnée**. L'ancien `Held` demande un audit du détecteur de prise en main | **Des candidats descriptifs seulement**, pas de deux états physiques nouvellement activés |
| Companion F2/F4 et P-A/P-B | `AutonomyBrain`, `BehaviorPortrait`, `MockSocialContext`, `MockSocialComposer` et l'unique `ExperienceMemory` font déjà la sélection, les préférences, le silence et les quotas des propositions sociales | **Adapter par une fonction pure après le portrait**, sans réarbitrer, écrire de mémoire, incrémenter les quotas ni exécuter une proposition |
| [Registre C3](community-reference-registry-2026-10-26.md) | GC-RENCAO, Smartulf et la PR constructeur #381 donnent des pistes sans code livré chez nous | **Aucun import tiers**, aucune nouvelle licence de modèle, audio ou média |

**Création justifiée :** `microduck_companion/oem_expression_hints.py` est un petit adaptateur *sans effet de bord* qui interprète des **étiquettes fictives** d'événements OEM, à côté du portrait P-A/P-B déjà calculé. Pas de nouveau daemon, pilote, contrôleur, scheduler, table SQLite, capture audio, synthétiseur, RPC ni dépendance. Le code OEM est licencié Apache-2.0 ; **aucun code OEM n'a été recopié**.

## 2. Contrat concret et limites

L'entrée `MockOemCue` ne transporte qu'une étiquette fictive choisie parmi `petting_start`, `petting_end`, `ambient_noise`, `ambient_voice` et une heure monotone. Source contractuelle : `mock_oem_event_only`. Ce **n'est pas** un flux matériel `PetHandle::try_recv_event/try_recv_sound`. Le `BehaviorPortrait` préexistant conserve l'état de référence, son affect simulé et, s'il a été chargé, l'habitude P-B. Une ancienne mémoire ne fabrique jamais un événement présent.

`MockSocialContext` F4-C est réutilisé comme **déclaration de consentement fictive**, jamais une authentification matérielle. `MockOemConditions` contient des indicateurs exclusivement fictifs de chute, occupation, émission audio propre, mouvement propre et demande d'arrêt. Ils ne certifient aucune sûreté physique. L'absence de déclaration, le mode calme, la perte de fraîcheur (limite 1,5 s), une chute/activité signalée, un arrêt demandé **ou un portrait P-B indisponible** ⇒ **silence**. La sentinelle OEM réelle dispose déjà de ses propres règles ; P-C n'y touche pas.

| Événement *mock* frais et autorisé | Description retournée | Ce que la description ne fait pas |
| --- | --- | --- |
| `petting_start` | `oem_owned / Petted` : `robotd` est déjà **propriétaire** de la réaction `coo` | **Aucun deuxième `coo`**, aucune certitude qu'une caresse réelle a eu lieu ou que `coo` a joué |
| `petting_end` | `silent` | Pas de mouvement, son, réécriture d'humeur |
| `ambient_noise` sans audio/mouvement propre et avec consentement fictif | `hypothesis / Startle` : bruit bref **ne prouve pas** une surprise | Pas de geste réflexe, sursaut physique ou apprentissage de danger |
| `ambient_voice` sans audio/mouvement propre et avec consentement fictif | `notice_only` : voix détectée **non comprise** | **Pas** de reconnaissance vocale, transcription, activation « Hé Kwipi ! », commande « stop/viens », consultation Qwen ou son |
| Pas d'événement, contexte refusé, danger fictif, temps expiré, source/catégorie invalide | `silent` ou exception de validation sur donnée malformée | Aucune action/autorisation ; pas de contournement de sécurité |

Toutes les sorties `MockExpressionHint` imposent `executed=False`, `physical_execution_authorized=False`, `real_sensor_authenticated=False`, `wake_word_recognized=False`, et **0 commande** moteur/son/capteur/PC/mémoire. Ce sont des descriptions, pas des instructions transmises au robot. En particulier, le flag fictif `quiet_mode` de Companion **ne peut pas éteindre** la réaction matérielle `coo` propre au constructeur : ce serait un autre chantier OEM et de sûreté.

Le format de sortie transporte la **tonalité P-A et l'habitude P-B** sans les modifier, n'ajoute aucune identité ni récompense, ne reprogramme pas le rythme F2 et ne touche pas aux tables de souvenirs existantes. Les versions d'état `Startle` et `Petted` sont des **candidats historiques distincts** : le `BehaviorPortrait.state` continue à n'autoriser que quatre interprétations P-A non exécutées.

## 3. Critères et étapes suivantes

La suite ciblée `tests/test_oem_expression_hints.py` teste source autorisée/refusée, fraîcheur, bruit vs voix, contexte muet, protection contre auto-bruit/mouvement, caresses OEM déjà traitées, arrêt/chute/activité, composant après P-A/P-B, absence d'écriture dans la SQLite, répétition idempotente, refus des champs d'action falsifiés et garde-fou d'absence de deuxième ordonnanceur.

**P-C est limité aux fixtures**. Il ne teste ni micro, ni caresse réelle, ni image, ni capteur OEM authentifié, ni serveur de son, ni radar d'obstacles, ni coût CPU/RSS sur RK3566. La CI hôte atteste seulement les contrats logiciels.

**P-C2 (distinct, non autorisé ici)** : envisager un adaptateur de lecture événementielle validé, *si l'OEM expose une interface supportée* ; ne jamais accéder à un second micro/arecord. Vérifier fraîcheur, confirmation de l'événement, autorisation opérateur et contrôle parental, provenance et état `robotd` sans bloquer 50 Hz ; utiliser uniquement les animations/sons officiels et tester la non-duplication de `coo`. Puis tests en simulation pertinents et robot réel sous supervision, après audit matériel. **Cat-A2 reste le prochain chantier prioritaire de perception.**
