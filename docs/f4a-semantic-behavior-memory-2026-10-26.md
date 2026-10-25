# F4-A — Mémoire sémantique et comportementale conservatrice

**26 octobre 2026 — [PR #37](https://github.com/Jean-Philippe56520/Microduck/pull/37), non fusionnée.**

## 1. Objectif et choix d'architecture

Microduck Companion a déjà un [journal d'observations fictives F1-C](../microduck_companion/passive_memory.py) dans `ExperienceMemory`, un [apprentissage de nouveauté F2-C](../microduck_companion/passive_learning.py) à biais d'attention minime et des [cycles de conséquences entièrement fictifs P2a](../microduck_companion/mock_cycles.py). F4-A **réutilise cette base SQLite**, sans créer de second cerveau ni reconnecter des observations non authentifiées à la locomotion.

Le projet n'ayant pas de robot physique, le mot « observation » de cette PR désigne **uniquement une catégorie passée par un socket de fixture `mock`**, pas une vision caméra réelle. Les nouvelles tables enregistrent des **catégories historiques, jamais un animal individuel, un enfant, une identité, une voix ou un objet localisé**. Tous les résultats sont logiciels hors réseau.

## 2. Trois ensembles de données sans confusion de confiance

| Ensemble | Entrée réellement autorisée | Enregistré | Autorité permise |
| --- | --- | --- | --- |
| **Souvenirs sémantiques** `f4a_semantic_categories` | Ligne `identified` du journal F1-C, avec source `mock`, canal `mock_fixture_unix`, et preuve F2-C `new_information` ou `repeated_observation`, active et récente de 2 s maximum | Catégorie contrôlée, modalité objet/son, confiance **rapportée par la fixture** (non calibrée), horodatage mur et ID de preuve F1-C | **Historique fictif uniquement**. La relecture rejoint la preuve F1-C/F2-C toujours présente et active : sa rétraction ou son changement la rend invisible |
| **Hypothèses de propriétés** `f4a_property_hypotheses` | Appels de test explicitement fictifs, **pas une réponse d'un Qwen connecté** | Catégorie générique, propriété parmi `texture`/`movement`/`affordance`, valeur et confiance déclarées bornées ; aucune propriété libre | `fictional_llm_hypothesis_only` : **jamais confirmée**, jamais fusionnée à la table des observations, aucune décision de mouvement |
| **Mémoire comportementale** `f4a_mock_behavior_outcomes` | Cycle P2a existant `inspect_object` avec `disposition=mock_feedback`, suivi fictif explicite et `reward` exact ±0,4 | ID de cycle, résultat `positive`/`negative`, date d'import, retrait possible ; **aucun ID de cible ni suivi de personne** | Biais descriptif `clamp(0,04 × (succès − échecs), −0,12, +0,12)`, **non connecté à `robotd`, `AutonomyBrain` ou un modèle entraîné** |

Le biais F4-A est **un calcul réversible sur des résultats P2a scénarisés**. Il ne remplace ni la préférence existante `objects.preference` du prototype P2a, ni le biais F2-C de l'attention, ni la préférence de locomotion MuJoCo. Aucune preuve qu'une action réelle a réussi ne peut être déduite d'une proposition, d'une image ou d'un énoncé de LLM. La confiance mémoire n'est pas une probabilité de reconnaissance fiable.

## 3. Garde-fous, corrections et oubli

- Même connexion SQLite `ExperienceMemory` exigée pour F1-C, F2-C, P2a et F4-A. Les lignes ne peuvent pas être importées librement de fichiers JSON ni de Qwen. Une source absente, un ID étranger, un statut `unknown`, une classe conflictuelle, une faible confiance, une ancienne session ou une source non `mock` ne crée aucun souvenir sémantique.
- Les souvenirs sémantiques sont invalidés à la lecture si l'origine F1-C/F2-C est effacée, retirée ou contradictoire ; un retrait F4-A empêche la réactivation automatique d'une même ligne. Les observations ont une clé unique par ID, sans compter deux fois une catégorie dupliquée dans la même trame. **Aucun ID de suivi éphémère** enregistré dans les tables F4-A.
- Les hypothèses n'acceptent aucun texte libre, personne individuelle, position de maison, domaine médical, garantie de sécurité ou ordre moteur. Elles sont isolées et peuvent être rétractées manuellement, même après deux déclarations contradictoires.
- Les résultats comportementaux ne sont importés que depuis la table de cycles P2a après vérification de l'origine, de l'intention, de la disposition et du score exact. Les cycles `halt`, explorations bloquées, `play_with_object` et inspections sans conséquence **ne reçoivent aucun résultat**. Un changement de la preuve originale supprime l'influence du résultat.
- **Oubli et quotas :** rétention maximale déclarée **14 jours**, **256** entrées sémantiques, **64** hypothèses, **256** résultats comportementaux. Ces bornes limitent les lignes F4-A mais **ne mesurent pas** la RAM ni le stockage utile du robot. Les requêtes ont un plafond de 50 résultats.
- Rétraction logicielle `fixture_annotation_error` ou `source_retracted`; aucune réattribution d'un souvenir à une personne ou à une classe plus fiable.
- Les appels mémoire ne demandent ni caméra/voix/PC ni commandes motrices. **Les mécanismes de `robotd`, `mediad` et `tofd` restent inchangés.**

## 4. Tests et démonstration de persistance

Le code comprend `microduck_companion/category_semantics.py`, `microduck_companion/behavioral_memory.py` et `microduck_companion/f4a_memory_demo.py`, ainsi que **37 tests supplémentaires** dans `tests/test_category_semantics.py` et `tests/test_behavioral_memory.py`.

[Suite GitHub Actions : **635 tests Python réussis**, compilation et démonstration F4-A dans deux processus indépendants](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40246670514). Les tests couvrent la source F1-C/F2-C, la persistance après réouverture, les doublons, la fraîcheur, les catégories inconnues, les retraits et contradictions, les rapports de P2a, l'absence de moteur et la fermeture SQLite. La démonstration passe le même fichier SQLite entre **deux nouveaux processus** sans envoyer de médias ou de mouvements.

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.f4a_memory_demo --database /tmp/f4a-mock.sqlite3 --session first
python -m microduck_companion.f4a_memory_demo --database /tmp/f4a-mock.sqlite3 --session second
```

**Toutes les données de démonstration sont fictives.** La persistance de la base et la logique de retrait sont testées en CI Linux ; ni la capacité de stockage des partitions Yocto du produit final, ni le débit/latence embarqué, ni l'autonomie énergétique ne sont mesurés.

## 5. Non livré et suite conditionnelle

**Non livré dans F4-A :** identification individuelle d'un animal ou d'une personne ; apprentissage à partir d'une interaction physique ; mémoire spatiale ou carte de la maison ; capture de caméra ou de microphone ; modèle de perception entraîné ; intégration Qwen ; commande du regard ou des moteurs ; mesure du RK3566 ; locomotion sûre.

Le prochain lot **F4-B**, séparé après revue et fusion de F4-A, abordera des **repères spatiaux incertains et des limites de provenance**, d'abord sur des fixtures seulement. Le ToF 8×8 ne sera pas assimilé à une navigation libre ni à un LiDAR 360°. Les fonctions critiques et la sécurité continueront sans Internet ni PC. Les chiffres CI ne seront pas extrapolés au Microduck physique.
