# QW-GOAL-0 — Qwen guide les objectifs motivés de Kwipi, sans rareté arbitraire

**Date :** 28 octobre 2026. **Statut : cadrage uniquement**, aucun appel automatique Qwen, changement F5-C, code, SQLite, moteur ou modèle installé dans ce lot. **Autorité :** [plan directeur](plan-action.md), [plan objectifs/mémoire/Qwen](kwipi-goals-determination-memory-qwen-observability-plan-2026-10-28.md). Référence initiale : Companion `main@76b7fbee0105eefc83555792a5cf8ab73c48ff92`. Revalider main/gitlinks et PR au début du prochain chantier.

## 1. Observation, hypothèse, critères d'échec et retour arrière

**Correction fonctionnelle du propriétaire :** Qwen3.5 **9B facultatif sur PC** doit aider Kwipi à atteindre des **objectifs issus de ses motivations**, et non être traité comme une encyclopédie interrogée une fois par objet ou comme un privilège artificiellement rare. Une question peut être utile pour reconnaître une catégorie, lever une contradiction, trouver une nouvelle stratégie, anticiper des conséquences, proposer une observation complémentaire ou réévaluer une hypothèse après échec. **Une nouvelle image n'est pas une condition universelle de reconsultation** : une question utile réellement différente peut suffire. Ni dix rencontres, ni un compteur fixe, ni le seul niveau de détermination ne doivent déclencher un appel.

**Existant vérifié :** `AutonomyBrain`/F2 porte curiosité, sociabilité, jeu, énergie cognitive, prudence et **détermination DET-1** ; MEM-1 stocke des objectifs fictifs ; MEM-2A (PR #147 fusionnée, PC-fixtures) rappelle C1/C2 et les objectifs en lecture seule. `semantic_pc_opportunity.py` (PD3) est **un détecteur d'intérêt fictif, pas un expéditeur**. F5-A/B/C/D et F5 v2/v3 sont séparés ; Qwen réel sur PC demeure **manuel**, sans lecture autonome de SQLite. `SelectivePCPolicy` F5-C impose aujourd'hui `COOLDOWN_S=60`, `WINDOW_LIMIT=2` par 600 s, `DAY_LIMIT=8` par 24 h, une demande en vol et backoff : **garde d'étude déjà codée**, pas politique définitive de personnalité. `ask_analysis_once` historique bloque les reconsultations par identifiant : à revoir **uniquement dans un futur lot ciblé**. Aucune de ces portes n'est remplacée ici.

**OEM épinglé :** `pollen-robotics/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` : `robotd/src/intents.rs` (intents horodatés/deadman), `docs/design/robotd-design.md` (unique propriétaire moteur, 50 Hz), `mediad/src/sensor.rs` (caméra par version de carte). RL `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Version OEM active, politiques ONNX, caméra individuelle, latence/RSS RK3566 et `robotctl health/monitor` restent **inconnus** en absence de robot. Qwen n'ordonne aucun moteur.

**Hypothèse à vérifier :** évaluer le **gain informationnel attendu pour un objectif** avant de solliciter Qwen améliore l'utilité des consultations et diminue la répétition inutile, **sans plafond quotidien arbitraire de personnalité**. Les garde-fous de capacité/consentement restent distincts et mesurés.

**Échecs bloquants :** appels dès qu'une motivation franchit un seuil sans question utile ; boucle autoréférentielle de prompts ; contournement d'un consentement/timeout/circuit ; suppression immédiate des quotas F5-C sans tests ; Qwen lisant toute la SQLite ou des médias privés ; Qwen créant un objectif/mouvement/récompense tout seul ; scénario fictif revendiqué comme connaissance réelle ; double scheduler/writer ; latence du PC bloquant `robotd`. **Retour arrière :** conserver F5-C existant et la boucle locale sans Qwen ; aucun changement en production par ce document.

## 2. Principe cible : motivation → objectif → question utile

La **motivation explique pourquoi un objectif importe**, pas combien de requêtes le modèle aurait le droit de consommer.

| Contexte | Question possible | Limite |
| --- | --- | --- |
| Curiosité, inconnu | « Quels indices observer pour distinguer plante naturelle et plante artificielle ? » | L'objet doit d'abord être détecté ou l'incertitude signalée honnêtement |
| Détermination, objectif suspendu | « Quelle autre approche non motrice peut nous aider après notre tentative infructueuse ? » | Une intention/acceptation OEM n'est ni échec prouvé ni effet vérifié |
| Jeu avec objet inanimé | « Quelles interactions OEM plausibles puis-je examiner, avec quels risques ? » | Suggestions ≠ compétence chargée, sûreté ni permission moteur |
| Sociabilité | « Quel comportement d'observation passif serait approprié face à ce signal ambigu ? » | Pas de biométrie, identité ou interprétation certaine d'émotions |
| Prudence | « Quelle information manque pour apprécier cette situation ? » | Le danger déclenche inaction/stop ; le modèle n'autorise aucune dérogation |
| Exploration | « Quelle nouvelle observation non dangereuse pourrait clarifier cet environnement ? » | ToF frontal ≠ cartographie libre ni anti-escalier validé |

**Arbitrage prévu :** F2 détermine un but admissible/une question locale à partir de la scène fraîche, des motivations (y compris détermination), de l'humeur/état descriptif et des souvenirs ; un évaluateur **pur et réutilisant PD3** estime la **valeur attendue d'information** pour le but, son incertitude, les questions/réponses antérieures, les stratégies restantes et les contraintes d'attention/ressources. Une question spécifique, pertinente et susceptible de faire progresser cet objectif peut être offerte à F5 **même sans nouvelle prise de vue**. Une motivation élevée augmente la **pertinence/priorité** d'une question ; elle n'implique pas une requête automatique.

**Réévaluation après Qwen :** réponse toujours `pc_qwen_unverified`, éventuellement une catégorie/propriété/relation/stratégie/conséquence **hypothétique** avec provenance. Kwipi peut décider localement de mémoriser la conjecture non prouvée, de demander une autre analyse sous un angle réellement différent, d'observer, de changer de stratégie, de suspendre ou d'abandonner. Le modèle n'écrit pas directement SQLite, ne relance pas ses propres appels et ne donne aucun ordre moteur.

**Anti-boucle sémantique :** bloquer une question essentiellement identique adressée au même modèle avec les mêmes éléments et sans possibilité plausible de progresser ; accepter un **nouveau problème réellement distinct** (par exemple « identifier » puis « quels indices rechercher ? ») même si les images ne changent pas. Une réponse « ne sais pas » doit augmenter l'incertitude explicitement, non créer une récompense ou une consultation infinie. L'intérêt et la reprise sont décidés localement, indépendamment des propres incitations formulées par Qwen.

## 3. Distinguer utilité cognitive et protections techniques

**Pas de politique cible « huit questions par jour », « dix rencontres obligatoires » ou « Qwen seulement en dernier recours ».** Les plafonds **actuels** F5-C (60 s, 2/600 s, 8/24 h) restent **en vigueur dans le code** jusqu'à une PR distincte et des mesures. Le futur lot QW-2 devra évaluer leur remplacement par une **admission à la demande** fondée sur la pertinence et la capacité effective du PC, sans présenter des limites arbitraires comme un trait psychologique. Les protections non négociables restent :

- consentement opérateur explicite et révocable, politique d'autorisation des médias par session ; données compactes et expurgées **sélectionnées par Kwipi**, jamais la SQLite brute ;
- authentification/chiffrement si liaison réseau, quotas **techniques de charge**/backpressure adaptables d'après des mesures PC réelles, au plus une requête en vol, timeout, backoff après panne, déduplication et repli local ;
- observation/provenance fraîche quand la réponse en dépend, aucune commande moteur, blocage sur stop/danger/énergie/règles OEM, pas de connexion nécessaire pour vivre localement ;
- journal de raison d'appel ou de refus, but motivant, question abstraite, preuves de contexte, réponse utile/inutile/indéterminée, corrections, coût, latence/RSS ; pas de flux privé ni de chat infini entre agents.

La capacité PC peut être suffisante pour **plusieurs appels rapprochés réellement utiles** ; l'approche doit aussi fonctionner lorsque Qwen répond lentement, est absent, ou n'apporte rien. Une autorisation consentie n'est pas une autorisation motrice.

## 4. Réutiliser / adapter / créer

- **Réutiliser** F2/DET-1, MEM-1/MEM-2A/C1/C2, PD2/PD3, F5-A/B/C/D, Qwen3.5 9B PC réel, les contrats de réponses JSON et l'unique ExperienceMemory. **Adapter** l'estimation pure de besoin informationnel à un objectif et à un historique source, puis l'admission F5-C **après** validation des mesures et tests. **Créer uniquement** les contrats/questions structurées manquants, pas de second cerveau, démon ou base.
- Les sources tierces dans [registre C3](community-reference-registry-2026-10-26.md) restent des références à comparer en cas de besoin réel ; ne pas intégrer QuackNav, Twin, Quacksat ou autre agent pour un simple choix de question.

## 5. Lots et preuves exigées

1. **MEM-2B / Cat-A2b/C3-B** : distinguer scènes/nouvelles vues/continuité plausible sans preuve inventée d'identité d'une plante ; rester possible sans identification d'instance.
2. **DET-2 / PER-1** : objectif actif/suspendu et priorité cognitive attribuée par motivations/état cohérents ; la détermination n'est ni consentement réseau ni répétition.
3. **QW-1** : contexte expurgé de MEM-2A, question précise liée à un objectif, appel **réel au modèle 9B PC** si autorisé, JSON strict, comparaison avec/sans mémoire, aucun SQL fourni au modèle.
4. **QW-2** : remplacer `ask_analysis_once` et étudier l'admission F5-C **pilotée par valeur informationnelle et capacité**, sans suppression de garde de sûreté. Permettre des reconsultations utiles d'un objectif même sans nouvelle image, mais pas des invites répétitives sans gain attendu. Ajouter contrôle du consentement et une seule demande en vol.
5. **E2E-1** : ablations appariées curiosité/détermination/jeu/sociabilité/prudence basse/haute, objectifs abandonnés vs suspendus, questions utiles identiques/différentes, « ne sais pas », erreurs PC, refus confidentialité, stress mémoire, latence/RSS et demandes acceptées/refusées. Séparer *qualité de décision* d'une *action OEM exécutée* et d'un *effet indépendant*.

**Tests décisifs :** dix rencontres identiques + même question ⇒ pas de sollicitation répétitive ; même vue, nouvel objectif ou nouvelle question apportant une valeur attendue ⇒ consultation envisageable ; détermination forte + impasse = nouvelle stratégie/ou abstention, pas répétition aveugle ; Qwen indisponible = fonction locale ; aucune fuite de médias ou SQLite ; stop/danger = aucune permission moteur ; plusieurs questions utiles autorisées en simulation de capacité, indépendamment d'un plafond psychologique arbitraire. Les seuils et l'efficacité ne sont **pas validés** et seront évalués sur PC avant robot.

**Décision présente :** **planifié/documenté uniquement** ; MEM-2A #147 est codé et testé PC-fixtures, mais aucune politique QW-GOAL-0 n'est encore intégrée à Kwipi.
