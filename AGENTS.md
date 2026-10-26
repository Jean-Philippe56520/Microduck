# Instructions de contribution aux agents — Microduck Companion

**Appliquer impérativement le [protocole « réutiliser avant de créer »](docs/development-reuse-protocol.md) pour chaque demande et PR.** Le code courant, les tests et les sous-modules épinglés font foi, jamais une ancienne discussion.

1. Lire README.md, docs/plan-action.md, docs/roadmap.md, docs/hardware-feasibility-audit-2026-10-25.md et les fichiers concernés.
2. Chercher d'abord la solution officielle dans upstream/microduck (robotd, mediad, tofd, pet-detect, protocoles), puis les classes et adaptateurs déjà présents dans microduck_companion/. Relever leurs révisions, responsabilités et limites vérifiées.
3. Établir une mini-matrice réutiliser / adapter / nouveau. Toute nouvelle capacité doit justifier ce que l'existant ne peut pas faire, et éviter les doublons. Ne pas confondre la roadmap OEM M9 avec un cerveau actif : à la révision épinglée dans ce projet, M9 n'est pas porté.
4. Réutiliser les interfaces officielles et garder robotd seul propriétaire des moteurs et de la sécurité. Aucun LLM, événement audio/visuel, scénario fictif, ToF ou souvenir ne donne une autorisation de déplacement. Ne pas toucher aux pilotes, unités système ou sous-modules sans lot distinct.
5. Préserver la confidentialité (aucune photo, voix, identité personnelle ou secret committé), les quotas de ressources et les conditions d'arrêt. Aucun modèle hôte n'est validé RK3566 sans mesures physiques.
6. Une PR ciblée, des tests de réussite **et d'échec**, puis README, plan, roadmap et audit mis à jour. Déclarer précisément prévu / codé / testé sur fixtures / simulé / validé sur robot. Lier les CI et la PR dans le compte rendu.

**R1 actuel :** réutiliser passive_media_router.py, oem_frame_preflight.py, sim_ipc.py, passive_sources.py et perception.py ; **aucun nouveau lecteur caméra, microphone ou socket constructeur.** Les observations OEM de fixtures sont non authentifiées et ne sont jamais une source sensorielle pour le cerveau.
