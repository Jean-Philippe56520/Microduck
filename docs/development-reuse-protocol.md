# Protocole permanent de développement — Réutiliser avant de créer

**Microduck Companion · applicable à chaque lot et à chaque PR dès le 26 octobre 2026.**

Le projet doit ajouter ce qui manque, sans réinventer les composants du constructeur ou de Companion. La [matrice R0](oem-reuse-audit-2026-10-26.md) et son [inventaire machine](oem-reuse-inventory-2026-10-26.json) recensent les premiers composants et leurs propriétaires. Le [registre C3 par chantier](community-reference-registry-2026-10-26.md) complète R0/R1.5 par une veille **officielle non fusionnée** et communautaire, sans présumer de compatibilité ou de permission de déploiement. Une fonctionnalité mentionnée dans une roadmap, comme le cerveau OEM M9, **n'est pas automatiquement codée ni déployée**.

## Vérifications obligatoires avant tout code

1. **Inspecter le dépôt actuel.** Lire README, plan d'action, audit matériel, fichiers et tests concernés. Contrôler les sous-modules Git épinglés upstream/microduck et upstream/microduck_rl. Le code GitHub fait foi ; les anciennes conversations et la roadmap OEM ne prouvent pas qu'une fonction existe.
2. **Rechercher l'existant** dans les services constructeur (robotd, mediad, tofd, pet-detect, détecteurs ONNX/RKNN, interfaces JSON-RPC, animations et sons), **puis** chez Companion (perception, passive_sources, passive_media_router, oem_frame_preflight, sim_ipc, AutonomyBrain, ExperienceMemory, SQLite, mémoire multimodale et contrats F5/PC). Regarder les tests et les modules historiques.
   - **Veille sans confusion de statuts :** comparer les interfaces de la version OEM épinglée aux éventuelles évolutions sur le dépôt officiel (issues/PR, en distinguant **ouvert/non fusionné** de **présent dans main**), puis vérifier les projets tiers pertinents **via C3**. Noter versions, fichiers exacts, licences code/poids/médias, résultats reproduits ou simplement annoncés, consommation et risques de doublon. Une référence externe n'est jamais une dépendance obligatoire ; ne pas intégrer sur la seule foi d'un README ou de MuJoCo.
3. **Choisir : réutiliser, adapter ou créer.** Pour chaque changement, consigner le propriétaire et la source, le statut réellement vérifié, les contraintes et le motif précis si du nouveau code est justifié. Préférer un petit adaptateur sans effet de bord à une nouvelle boucle de perception, un pilote ou un cerveau moteur.
4. **Limiter les modifications.** Faire une PR par responsabilité, sans mise à jour silencieuse des sous-modules ni copie de code constructeur non justifiée. Contrôler les licences avant réutilisation de sources ou de poids externes.
5. **Tester les cas d'échec** (source absente, donnée malformée, stale/future, relecture, incohérence, absence d'authentification, faux positifs, mémoire bornée et confidentialité). Ne jamais déduire une validation matérielle de la CI hôte ou de MuJoCo.
6. **Documenter l'état et les preuves** dans README, docs/plan-action.md, docs/roadmap.md et l'audit matériel pertinent. Employer les mentions « prévu », « codé », « test logiciel », « simulé », « validé sur robot » avec liens d'exécutions réelles.

## Responsabilités à ne pas dupliquer

- **robotd seul :** bus moteurs, sécurité, deadman, contrôle 50 Hz, politiques ONNX, animations OEM, arbitrage d'intentions physiques. Un résultat de vision, ToF, Qwen ou fixture ne certifie jamais le sol et ne commande jamais les moteurs.
- **mediad / tofd / pet-detect :** acquisition et interfaces de caméra, profondeur et audio. Distinguer le socket local mediad (hello/media.frame) des notifications WebRTC (media.video/media.detections). Une forme JSON OEM n'authentifie aucune source.
- **Companion :** réutiliser la mémoire et les contrats de décision existants plutôt que créer un second schéma SQLite ou un second moteur de comportement. Les modules F2 sont des prototypes sans action réelle ; si le cerveau OEM M9 devient disponible, étudier son API avant tout portage.
- **Vie privée :** pas de photo, de voix, d'identité personnelle ou de secrets dans GitHub ; ne pas promouvoir une catégorie (chien/chat/personne) en identité individuelle. Pas d'envoi Qwen sans autorisation explicite.
- **Performance :** p50/p95 et RSS sur PC ne sont pas la RAM disponible, la thermie, les latences motrices ni l'autonomie sur RK3566.

## Contenu obligatoire de chaque PR

Renseigner dans le [modèle de PR](../.github/pull_request_template.md) :
- **Périmètre, propriétaire et état réel** de la fonction.
- **Sources OEM et Companion inspectées**, avec liens et révisions (ou préciser qu'elles n'ont pas été inspectées).
- **Composants réutilisés**, composants nouveaux et pourquoi l'existant ne suffit pas.
- **Risques de doublon**, incompatibilités justifiées et plan de retrait/migration si le constructeur livre une fonction concurrente.
- **Tests, mesures, limites de preuve, sûreté et confidentialité**.

Une nouvelle logique redondante sans justification et sans stratégie de compatibilité **ne doit pas être fusionnée**. Les tests de présence des documents sont utiles mais **ne remplacent pas une revue humaine** de l'équivalence et de l'architecture.

### Application directe R1

La façade de fixtures R1 réutilise les parseurs F3-C (notifications WebRTC), F3-E (en-tête media.frame), sim_ipc (ToF) et MockAudioCueRouter (audio fictif), puis les types F1 PassiveRead / PerceptionSnapshot. Elle ne crée **aucun nouveau parseur média ni lecteur de socket**, ne sauvegarde pas les données brutes et ne transforme pas les métadonnées en capteurs authentifiés, catégories fiables ou commandes. L'échec rend une lecture sans événements.

**Reprendre cet audit à chaque nouvelle version constructeur ; ne pas maintenir indéfiniment une fonctionnalité parallèle lorsque l'amont propose déjà une solution compatible.**
