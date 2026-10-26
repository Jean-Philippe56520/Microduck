# F5-A — Contrat PC facultatif de seules hypothèses (fixtures)

**26 octobre 2026 — [PR #41](https://github.com/Jean-Philippe56520/Microduck/pull/41) fusionnée, logiciel Python testé sur fixtures.** F4-D [fusionnée via PR #40](https://github.com/Jean-Philippe56520/Microduck/pull/40). La phase F5-A fournit **un contrat local sans réseau**. Elle ne lance ni Ollama, ni Qwen, ni caméra, ni microphone, ni dispositif NFC/BLE, ni moteur, ni haut-parleur.

## Pourquoi cette séparation

L'architecture conserve **AutonomyBrain** et la mémoire **ExperienceMemory** existants. La prise de décision F2-B est effectuée *avant* la préparation facultative d'une requête. Aucune réponse du PC ne retourne dans le calcul de l'intention, la mémoire de perception, les préférences apprises, une identité, la certification du sol ou les contrôles de robotd.

Le module **microduck_companion/pc_hypothesis_contract.py** fournit :
- start_optional_pc_cycle(...) : choisit une intention cognitive locale, puis peut construire une demande pour **une catégorie d'objet fictive inconnue ou contradictoire**. Une catégorie connue, une source périmée/invalidée, une entrée non passive, une personne, la parole ou un mot-clé ⇒ aucune demande.
- PCRequest.to_wire() : sérialise un JSON strict sans image, audio, texte libre, identifiant d'individu, track_id ou coordonnées. Les seuls champs d'observation sont kind=object_label, category=unknown, status=unknown/conflict et claimed_confidence. **source=mock_fixture_unix**, jamais une preuve de capteur OEM.
- parse_pc_reply(...) : parse une *réponse fictive* au format exact, au plus 4 096 octets, schéma v1, ID de corrélation, source déclarée pc_qwen_unverified, au plus 4 catégories génériques (`unknown/ball/toy/dog/cat/microduck/other_object`), confiance alléguée dans [0,1] et TTL positif au plus 5 s. Les doublons JSON, champs supplémentaires, commandes, mots libres, noms, valeurs non finies ou catégories liées aux personnes sont refusés **en entier**.
- finish_optional_pc_cycle(...) : renvoie **la même intention locale** avec une annotation séparée, ou un état pc_unavailable / response_rejected. Les hypothèses restent `verified=False`, `identity_verified=False`, `physical_actions_authorized=False` et zéro commande moteur/audio. Elles expirent au plus tard à l'échéance de la requête (2 s à partir de l'instant monotone local).

**Délai :** le chronomètre est celui du composant local *à réception*, pas un horodatage déclaré par le PC. F5-A rejette un résultat livré après deux secondes, mais **n'implémente pas de connexion ni de véritable interruption d'un appel réseau bloquant**. Les délais de socket, quotas de requêtes, déclencheurs parcimonieux, authentification du PC et comparaisons de modèles relèvent de F5-B/F5-C.

**Confiance :** même une hypothèse à confiance déclarée de 1,0 n'est ni un fait établi, ni un détecteur validé, ni une autorisation d'approcher un animal. Le module ne lit pas de données personnelles et ne sauvegarde aucun résultat de Qwen dans SQLite. Le risque d'un futur transport intercepté ou d'un faux PC n'est pas résolu par le simple champ source déclaré.

## Tests et exécution

La suite **tests/test_pc_hypothesis_contract.py** vérifie le repli hors connexion, l'immutabilité de l'intention, la protection des données et l'absence de commande, la cohérence des requêtes, les contradictions, la confidentialité, l'absence de demande sur source suspecte, le rejet des ordres moteurs/consentements fabriqués, des doublons, versions, paquets trop grands, latences, catégories inconnues et autres erreurs.

La démonstration **microduck_companion/f5a_contract_demo.py** enchaîne deux décisions locales sur données fictives, une sans PC puis une avec une réponse JSON fabriquée **dans le processus lui-même**. Elle constate deux fois la même intention `inspect`, une hypothèse non vérifiée, zéro appel PC, aucune écriture d'expérience et zéro actionneur.

```bash
python -m unittest discover -s tests -v
python -m microduck_companion.f5a_contract_demo
```

**Validation limitée :** [757 tests Python réussis, dont 34 nouveaux F5-A, compilation et démonstration fictive en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40250745954) sur hôte Linux GitHub Actions. Pas de mesure du PC Ryzen AI, 4B/9B, accélération, coût énergétique, délai réel de réseau ou budget mémoire RK3566. Aucun résultat matériel ni nouvelle marche MuJoCo.

**Étape suivante F5-B :** créer et mesurer séparément un client Ollama local sécurisé et comparer des modèles multimodaux 4B puis 9B, en conservant la possibilité de faire chaque cycle **sans PC**. Les réponses de ce client continueront à être traitées comme non vérifiées et sans contrôle des actionneurs.
