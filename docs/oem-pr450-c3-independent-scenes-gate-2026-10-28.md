# Audit OEM #450 et porte C3 — 28 octobre 2026

**Statut : analyse documentaire uniquement, sans changement de code, simulation active ni validation robot.** Références : [plan directeur](plan-action.md), [protocole de réutilisation](development-reuse-protocol.md), [reprise SIM-E2](reprise-microduck-oem-sim-e2-2026-10-28.md), [C1](c1-conservative-category-recall-2026-10-28.md), [C2](c2-durable-hypothesis-corrections-2026-10-28.md), [Cat-A2b #78](https://github.com/Jean-Philippe56520/Microduck/issues/78), [SIM-E2 #101](https://github.com/Jean-Philippe56520/Microduck/issues/101).

## 1. OEM #450 : observation et portée

Au pin constructeur `microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `scripts/duck-sim` déclare `walk="$POLICIES/alpha_walking.onnx"` et `stand="$POLICIES/alpha_stand.onnx"` (lignes 242–243). Dans le même pin, `robotd-params/src/lib.rs`, `PolicyParams::resolved_with`, documente par défaut le comportement `velstand.onnx` sans réseau `stand` pour le mode marche (autour des lignes 2101–2115). Le simulateur et les valeurs par défaut du robot ne sont donc **pas alignés**. Le pin `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` reste inchangé.

La [PR constructeur #450](https://github.com/pollen-robotics/microduck/pull/450), **proposition distincte de l'OEM épinglé**, annonce de remplacer le couple alpha par `walk=velstand.onnx`, `stand=none` et d'ajouter un test de non-dérive des slots du simulateur. Dans sa description, l'auteur rapporte en **simulation macOS** une rotation sur place d'environ 0° avec alpha contre +245° en 4 s avec velstand à `vyaw=1.0` ; ce résultat concerne le **yaw**, non une preuve de translation avant, ni une mesure WSLg reproductible sur notre installation. L'auteur signale aussi un échec de test Rust sous charge parallèle, passant isolément : ne pas résumer la CI comme entièrement verte ni traiter cette PR comme fusionnée sans recontrôle.

**Hypothèse à étudier :** le décalage de politiques peut expliquer une partie des différences de comportement du twin, mais **n'explique pas encore causalement** nos 3,500 mm de translation nette en 32 échantillons à consigne 0,08 m/s, ni les biais articulaires au repos. Les archives P0d/e/f/i/j et les traces SIM-E2-B/C restent les témoins de référence ; les défauts d'actionnement, contacts, gain, observabilité ONNX et équivalence des scènes ne sont pas départagés.

**Preuve discriminante future :** comparer à configuration constante, sur une branche/protocole séparés et avec approbation, la révision exacte et les politiques effectivement chargées, la consigne, la pose, les articulations, les contacts et le déplacement net, avec témoin fixe, bornes de temps et arrêt OEM. **Critères d'échec :** politiques non authentifiées, modèle ou scène différents, trace désynchronisée, limites OEM, absence de témoin, commande appliquée confondue avec déplacement physique. Ne pas mettre en œuvre cette expérience à ce stade : lire d'abord les tests/source de #450 et les archives déjà acquises. **Risque et retour arrière :** modifier `duck-sim` ou les ONNX brouillerait notre baseline ; aucun fichier, modèle, sous-module, service ou paramètre ne change dans ce lot.

**Demande au constructeur :** la capture opt-in `obs[61]`/`raw_actions[14]` au même tick reste une capacité non disponible par les API épinglées ([SIM-E2-D](sim-e2d-oem-onnx-tick-observability-2026-10-28.md)) ; ne pas inventer les 14 actions précédentes ni les composantes de pose manquantes. Une demande a été envoyée, mais réponse/accord non confirmés. La PR #450 ne résout pas cette lacune d'observabilité.

## 2. C3 : protocole de généralisation, pas score inventé

**Question testable :** le rappel C1, après corrections C2, améliore-t-il une décision **passive** sur une scène indépendante de ses souvenirs, sans accroître les erreurs, au regard du même décideur sans mémoire ? Le vrai bénéfice sera mesuré sur des catégories sourcées Cat-A2b, non sur des captures ou sessions arbitrairement qualifiées d'indépendantes.

**Réutiliser / adapter / créer** :
- **Réutiliser** `ExperienceMemory`, `memory_consolidation.py`, F1-C/F2-C et leurs tests, `AutonomyBrain`, C2 et la validation locale Cat-A2b ; OEM `robotd` reste seul pilote. Aucun import d'une mémoire QuackNav, Twin ou autre tiers et aucune seconde SQLite.
- **Adapter plus tard** un banc d'évaluation hors ligne, seulement quand les vrais groupes de scènes et annotations indépendantes autorisées sont prêts ; préserver provenance, corrections, `unknown`, source et caractère non vérifié des propriétés.
- **Ne pas créer maintenant** de faux détecteur, images de substitution présentées comme terrain, nouveaux poids, nouveau daemon, ordre moteur, stockage média GitHub ou branchement direct Qwen/F2.

**Plan de comparaison appariée** sur exactement les mêmes exemples TEST, avec mêmes règles de sûreté, horloges et version code :
1. Définir *avant évaluation* les unités de scène : lieu/séance/objet/source indépendants explicitement justifiés ; regrouper toutes les vues liées pour empêcher fuite entre souvenirs et TEST. Des « sessions de fixtures » C1 ne prouvent pas cette indépendance.
2. Construire le rappel à partir d'un ensemble antérieur distinct ; journaliser provenance, confiance, hypothèses rétractées, doublons et observations indécidables. Geler seuils et données TEST.
3. Comparer **A sans mémoire ni PC**, **B avec C1/C2 sans PC**, **C avec mémoire et conseil Qwen 9B facultatif** uniquement sur un sous-ensemble consenti, sans texte Qwen converti en fait ni commande. Le mode C n'est pas un prérequis pour A/B.
4. Mesurer par scène : catégorie attendue vs suggérée/unknown, taux d'erreur et d'abstention, contradictions, décisions d'inspection passive, nombres de rappels corrects/erronés, temps CPU/RSS et taille SQLite/WAL. Rapporter dénominateurs, intervalles/incertitude et différences appariées ; aucune récompense EX ni effet moteur.
5. Tests négatifs : scène nouvelle ressemblant à une ancienne, objet partiel, humain sur écran vs présence réelle, basse hauteur, source périmée, correction conservée après TTL/redémarrage, catégorie inconnue, rappel contradictoire, PC indisponible, erreur/timeout Qwen et consentement absent.

**Critères de non-passage :** annotations indépendantes absentes, fuite entre scènes, mémoire qui augmente les faux positifs sans justification, tombstone requalifiée en fait, dépendance au PC pour les décisions hors ligne, attribution causale sans fin d'acte OEM + effet indépendant. **Retour arrière :** banc en lecture seule, aucun schéma ni moteur modifié ; supprimer les seuls rapports synthétiques, conserver les corrections mémoire. **Mesures robot** (RK3566, thermique, 50 Hz, RSS, stockage) restent une porte indépendante obligatoire.

## 3. Verdict de ce lot

- **OEM #450 :** écart de configuration documenté ; piste importante, aucune preuve de locomotion réparée ni fusion OEM présumée.
- **C3 :** protocole et critères préparés ; aucune généralisation ni amélioration cognitive revendiquée tant que Cat-A2b n'apporte pas des scènes réellement indépendantes et une vérité terrain validée.
- **Code / tests :** aucun code modifié, aucun test exécuté ni simulé dans ce lot documentaire ; aucun changement des gitlinks.
