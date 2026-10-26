# Protocole de développement : réutiliser avant de créer

**Règle obligatoire pour tout futur développement Microduck Companion.** Ce protocole fait partie du référentiel de travail et doit être lu avec [le plan directeur](plan-action.md) et [l'audit de réutilisation OEM](oem-reuse-audit-2026-10-26.md). Il s'applique aux PR de code, de simulateur, de capteurs, de mémoire, de comportement et de documentation technique.

## 1. Avant d'écrire du code

1. **Lire l'existant actuel**, non les souvenirs d'anciennes conversations : `README.md`, `docs/plan-action.md`, `docs/roadmap.md`, `docs/hardware-feasibility-audit-2026-10-25.md`, les fichiers concernés, tests et dépendances.
2. **Inspecter les sous-modules épinglés** `upstream/microduck` et `upstream/microduck_rl` ; distinguer la branche publique actuelle de la **révision épinglée dans notre dépôt**. Les mécanismes du constructeur font foi pour les moteurs, capteurs, audio, vision, mises à jour et interfaces. Vérifier aussi les licences et droits d'utilisation.
3. **Chercher dans les modules Companion existants** avant tout nouveau module : `AutonomyBrain`, `ExperienceMemory`, `PerceptionSnapshot`, `passive_sources`, `passive_media_router`, `oem_frame_preflight`, `sim_ipc`, `sim_bridge`, `MultiviewPatternMemory`, `SelectivePCPolicy` et les tests.
4. **Rédiger une décision de réutilisation dans la PR**, avec chemins de source : fonctionnalité voulue → implémentation existante → ce qu'on réutilise → lacune démontrée → modification minimale. Si un doublon apparaît justifié, expliquer pourquoi une adaptation de l'existant ne suffit pas (contrat incompatible, sécurité, performances mesurées, licence, maintenance) ; demander une revue avant de maintenir deux implémentations.
5. **Séparer les niveaux de preuve** : documenté, codé, testé sur fixtures, exécuté en simulateur, mesuré sur hôte PC, validé sur robot. Un projet OEM ou une idée M9 **non portée** ne doit jamais être présenté comme une fonctionnalité livrée.

## 2. En développant

- **Une responsabilité, un propriétaire.** `robotd` : moteur, boucle 50 Hz, sûreté et arbitrage OEM ; `mediad` : caméra/audio et transport ; `tofd` : distance 8×8 ; Companion : mémoire et cognition passive **sans autorité motrice**. Ne pas ajouter de seconde boucle moteur, de pilote capteur, d'animation `IdleHead`, de stockage d'identité, de contrôleur cognitif moteur ou de client Qwen ayant autorité.
- **Étendre plutôt que recopier** le parseur, modèle de données, transport, schéma SQLite ou test déjà disponible. Réutiliser exactement les API publiques existantes ; si un adaptateur est nécessaire, le limiter à une façade bornée. Ne pas reproduire un algorithme constructeur sous un nouveau nom.
- **Sécurité et refus :** observations avec provenance, délai, statut inconnu, données absentes ; aucun avis LLM ne devient un capteur ou une autorisation de bouger. Les tests sur fixtures n'authentifient aucun capteur. Limiter taux, CPU/RSS, taille des buffers et conservation.
- **Protection des données :** ni voix/images privées, ni identité d'enfant/animal, ni secret sur GitHub ; ne conserver que métadonnées autorisées et compactes. Pas de copie de code tiers sans vérification de licence.
- **Évolution du constructeur :** si M9 ou une autre fonctionnalité OEM apparaît, **réévaluer le chevauchement avant de fusionner** de nouveaux comportements Companion. Ne pas avancer silencieusement un sous-module ni réécrire les garde-fous du constructeur.

## 3. Avant de fusionner

- Ajouter des tests ciblés positifs, négatifs, pannes et valeurs inconnues ; exécuter la CI et rapporter **uniquement les résultats réels**.
- Vérifier les risques de doublon : modules/classes/processus/stockage, chemins OEM, commandes, dépendances lourdes, coût CPU/RAM et latence. Comparer avec la solution déjà disponible.
- Mettre à jour README, plan directeur, roadmap et audit quand l'architecture, la preuve ou les limites changent.
- Utiliser la [checklist de PR](../.github/pull_request_template.md) et [l'inventaire de réutilisation](oem-reuse-inventory-2026-10-26.json). Une PR ne doit pas affirmer une fonctionnalité robot validée à partir d'une simple CI sur ordinateur.

**Règle de décision :** réutiliser l'existant lorsqu'il satisfait le besoin ; l'adapter à la marge lorsqu'il manque une capacité ; développer un nouveau composant **seulement** si la lacune est vérifiée et son coût supplémentaire justifié. Pour les moteurs et la sécurité, un doublon de contrôleur est exclu.
