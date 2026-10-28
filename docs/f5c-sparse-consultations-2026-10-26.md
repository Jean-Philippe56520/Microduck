# F5-C — Consultations PC parcimonieuses, quotas et repli local

**Addendum 28/10/2026 — objectif QW-GOAL-0, DOCUMENTATION UNIQUEMENT :** [politique cible de questions utiles motivées](qw-goal0-motivation-driven-qwen-policy-2026-10-28.md). Les limites 60 s / 2 par 600 s / 8 par 24 h ci-dessous sont **bien celles du code F5-C actuel**, conçues pour les essais fictifs, et **non un modèle de personnalité imposant de rares consultations**. Le futur QW-2 devra comparer une admission liée à la valeur attendue d'une question pour l'objectif, révisable même sans nouvelle image, et aux **limites de charge PC réellement mesurées**. Jusqu'à cette preuve, aucune limite actuelle n'est supprimée ni contournée ; consentement, une seule requête en vol, absence de boucle, backoff, confidentialité et `robotd` isolé restent obligatoires. Qwen réel 9B PC avec contexte mémoire reste à livrer dans QW-1/QW-2.


**26 octobre 2026 — [PR #43 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/43), logiciel Python testé sur données fictives.** F5-A (#41) et F5-B (#42) sont fusionnées. Aucun Microduck physique, vraie caméra, Ollama ou modèle Qwen 4B/9B n'est utilisé par les tests de cette phase.

## Contrat et intégration

`microduck_companion/selective_pc_policy.py` ajoute **SelectivePCPolicy** et **SelectivePCBridge**, exclusivement au-dessus du contrat F5-A et du worker F5-B. Le cerveau existant **AutonomyBrain** produit d'abord sa proposition cognitive locale `inspect` ; une requête facultative et anonyme n'est considérée que si elle concerne une catégorie d'objet **fictive** inconnue ou contradictoire, sans image et sans identité. « Unknown » n'est pas une preuve de nouveauté d'un objet réel.

- **Consentement de consultation explicite** `pc_opt_in=True` pour chaque appel du coordinateur. Par défaut, aucun accès réseau ; ni Qwen, ni moteur, ni son.
- **Quotas logiciels initiaux** (à revalider sur matériel) : intervalle minimum **60 s** ; maximum **2 tentatives par 600 s**, **8 tentatives par 24 h**. Toutes les tentatives réservées comptent, y compris les pannes et réponses rejetées. Aucune requête mise en file d'attente.
- **Une consultation réservée simultanément** dans la SQLite persistante **ExperienceMemory**. La réservation utilise `BEGIN IMMEDIATE` (transaction atomique) et une attente SQLite de 20 ms, **non garantie temps réel**. Une instance concurrente doit refuser la deuxième réservation.
- **Panne PC / réponse malformée** : seule l'issue anonyme (`pc_unavailable`, `response_rejected`, `hypotheses_unverified`) est enregistrée. Deux échecs consécutifs ouvrent un circuit de **300 s**. Une consultation interrompue est marquée indisponible après **3 s** lors de la prochaine réservation. Le délai logique F5-A est de **2 s** ; les réponses tardives ne modifient rien.
- **Horloges** : les quotas et le circuit reposent sur le temps civil fourni localement ; l'échéance F5-A sur le monotone. Un recul d'horloge civile bloque les nouvelles consultations. Une forte avancée erronée peut interrompre/altérer la politique : une source d'heure fiable sera requise avant déploiement.
- **Journal strictement minimal** : SHA-256 de l'identifiant **aléatoire de requête** (pas une personne ni un track), type fictif `unknown/conflict`, date et issue. Conservation limitée à 24 h lors des nouvelles réservations ; aucune image, voix, catégorie personnelle, lieu, texte de modèle ou contenu de conversation persisté.
- **Bridge non bloquant** : la méthode `submit` vérifie l'autorisation et les quotas avant de proposer la demande au worker F5-B ; `poll` récupère une annotation **non vérifiée** ou un résultat `pc_unavailable`. Les réponses ne modifient ni les motivations, ni les souvenirs vérifiés, ni `robotd`. En cas d'erreur SQLite, d'horloge ou de transport, la décision locale préexistante reste disponible.

Ces seuils sont **une politique prudente de prototype**, pas des mesures optimisées d'autonomie batterie, de performance ou de précision de modèle.

## Essais reproductibles

```bash
python -m unittest discover -s tests -v
python -m microduck_companion.f5c_policy_demo --database /tmp/f5c-example.sqlite3 --session first
python -m microduck_companion.f5c_policy_demo --database /tmp/f5c-example.sqlite3 --session second
```

Les deux commandes de démonstration s'exécutent dans **deux processus Python frais** avec la même SQLite : la première réserve une consultation fictive puis constate une absence de PC ; la seconde retrouve l'historique et refuse la demande à cause du cooldown. **Zéro réseau, zéro modèle, zéro robot ou pilote constructeur**. Les tests unitaires vérifient opt-out, source F5-A, persistance après réouverture, connexions SQLite concurrentes, transaction verrouillée, quotas glissants, quota journalier, anti-rejeu, pannes et backoff, horloge inversée, demande expirée, redémarrage pendant une demande, worker asynchrone fictif et absence de commande.

## Limites de preuve et étapes futures

F5-C ne mesure pas la latence réseau d'Ollama sur le PC de l'utilisateur, ni ses performances 4B/9B, consommation, RSS, puissance, GPU/NPU, ni la mémoire disponible ou température du RK3566. Aucun accès réel à `mediad`, `tofd` et `robotd` ; les intentions ne sont **pas des mouvements** et la locomotion reste non validée.

**F5-D** devra tester une résistance plus large aux réponses adversariales, à l'interception d'un réseau non authentifié, à la perte prolongée du PC, aux retours mal corrélés et aux pannes persistantes. Les horloges et l'initialisation SQLite ne disposent pas de preuve temps réel ; avant le robot, auditer les ressources et conserver les mécanismes OEM.

**Statut livré de la PR #43 :** [798 tests Python, compilation et démonstration en deux processus réussis en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40252645890), [PR #43 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/43) après revue ; validation physique et vrai PC Qwen toujours **non effectuées**.
