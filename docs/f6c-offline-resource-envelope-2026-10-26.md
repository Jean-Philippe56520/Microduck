# F6-C — Budgets d'événements et ressources du cerveau autonome sans PC

**26 octobre 2026 — [PR #47](https://github.com/Jean-Philippe56520/Microduck/pull/47), code Python expérimental sur données fictives.** Cette phase conserve `PassiveCycleSupervisor` F2-D, `AutonomyBrain`, les motivations et la même `ExperienceMemory`. Aucun robot, service constructeur, capteur ni modèle PC n'est activé.

## 1. Objectif et séparation des responsabilités

F6-C ajoute un **garde d'admission facultatif** `OfflineResourceGate`, injecté dans le superviseur F2-D existant. Il n'est **pas un deuxième cerveau** et ne remplace ni la boucle moteur OEM `robotd` de 50 Hz ni les capteurs `mediad`/`tofd`.

Chaîne testée avec la source *fictive* F1-B :

1. Le superviseur F2-D conserve son plafond de session `PassiveCycleLimits` (16 cycles, 128 événements par défaut). Si un garde F6-C est injecté, il réserve un créneau monotone **avant le moindre accès SQLite ou la lecture de socket fictive**.
2. Si le cycle respecte les quotas de temps et de fréquence, F1-B lit une nouvelle trame de catégories **fictives** depuis un socket Unix temporaire. Les contrôles de taille, source et fraîcheur F1-B restent inchangés.
3. Le garde F6-C vérifie le **nombre d'événements de la trame** contre la somme admise dans sa fenêtre glissante **avant** le choix de l'intention F2 et les écritures SQLite F1-C/F2-C. En cas de dépassement, toute la trame est rejetée, **sans file d'attente ni rejeu historique**.
4. Les choix `observe`, `inspect`, `listen`, `idle`, `rest` restent des **propositions non exécutées**. Les motifs de refus retournent `idle` et conservent le contrôle constructeur.
5. Après le cycle, F2-D rapporte des mesures **du processus hôte entier** et le garde peut bloquer les **cycles futurs** après une durée excessive ou une mesure anormale. Une transaction SQLite déjà achevée **n'est jamais prétendue annulée**.

L'absence de garde laisse inchangée la voie F2-D existante : aucun changement de seuil global sans opt-in du superviseur.

## 2. Seuils codés pour les fixtures — pas pour le RK3566

| Paramètre du garde F6-C | Valeur initiale | Portée réelle |
| --- | ---: | --- |
| Fenêtre glissante monotone | 10 s | État en RAM d'un seul processus |
| Intervalle minimal entre cycles admis | 0,5 s | **Admission** logicielle, pas cadence moteur |
| Cycles admis sur une fenêtre | 8 | Limite de lectures potentielles avant SQLite |
| Événements admis sur une fenêtre | 32 | Refus d'une trame entière si elle dépasse le solde ; limite contrôlée avant cognition/SQLite |
| Durée de retrait après dépassement CPU/temps | 5 s | Suspension des **cycles suivants**, sans interruption du cycle en cours |
| Seuil CPU par cycle | **désactivé** par défaut | Peut être configuré pour des tests ; mesure de temps CPU du processus complet |
| Seuil de RSS maximal du processus | **désactivé** par défaut | Peut être configuré pour des tests ; `ru_maxrss` Linux est un **pic historique de processus**, pas la RAM libre de l'appareil |

Le garde valide les paramètres, y compris les flottants finis et des plafonds supérieurs, mais **n'annonce aucun seuil sûr** de CPU, RAM, puissance ou température du Microduck. Les raisons de refus sont explicites : `budget_cycle_gap`, `budget_window_cycles`, `budget_window_events`, `budget_cooldown`, `budget_clock_reset`, `budget_missing_rss`, `budget_rss_limit`, etc.

**Horloge et absence de données :** recul monotone ⇒ verrouillage jusqu'à réinitialisation explicite de l'objet. Une horloge invalide après cycle ⇒ verrouillage. Si un seuil RSS est configuré mais que le relevé hôte est absent, F6-C refuse les cycles suivants plutôt que de supposer une marge. Un pic RSS au-dessus du seuil bloque le superviseur pour cette session. Sans seuil RSS, Windows ne déclenche pas de faux arrêt du seul fait de son absence de `ru_maxrss`.

**Nature exacte du quota :** les cycles sont réservés avant la lecture ; les événements sont comptés après parsing de la trame fictive mais avant intention/écriture mémoire. Une trame rejetée **après** cette réservation peut consommer du budget par prudence. Les contrôles sont **process-local, monotones, non persistants**, et ne prétendent pas synchroniser plusieurs cerveaux ou être inviolables dans un processus compromis. Aucun buffer de frames/médias n'est ajouté.

## 3. Tests et démonstration intégrée

- `tests/test_offline_resource_budget.py` : validation des paramètres, fenêtres glissantes, quotas, garde anti-rejeu d'horloge, séquences excédentaires, cadence, mesure CPU simulée, RSS absente ou excédentaire, dépassement de délai d'acquisition, conservation des précédents souvenirs sans les réutiliser comme capteurs, compatibilité F2-D sans garde.
- `microduck_companion/f6c_offline_budget_demo.py` : **vrai pipeline logiciel F1-B → F2-B → F1-C/F2-C**, piloté par un **faux socket Unix local** et six moments de temps **synthétiques**. Le garde utilise une fenêtre de 4 s, trois cycles et deux événements pour rendre les limites visibles dans un scénario court.
- Statuts de démonstration attendus : `ok`, `budget_cycle_gap`, `ok`, `budget_window_events`, `budget_window_cycles`, `ok`. Les deux rejets antérieurs à la lecture n'interrogent pas le faux serveur ; le rejet d'événement n'écrit aucune donnée en SQLite. **Trois observations fictives** sont journalisées, sans aucune commande motrice.

Reproduction sur Linux/WSL2, depuis le dépôt :

```bash
python -m unittest discover -s tests -v
python -m microduck_companion.f6c_offline_budget_demo
```

La CI compile les fichiers Python et lance le scénario avec les tests historiques. Les mesures `p50/p95`, temps CPU et `ru_maxrss` qu'il affiche sont les mesures du **processus GitHub Actions**, pas du robot. Les seuils de 4 s et deux événements de la démonstration sont des choix **de test**, pas une fréquence caméra, ToF ou moteur.

### Preuve effectivement mesurée sur GitHub Actions

La [CI F6-C #40257113819](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40257113819) a réussi : **861 tests Python**, soit **20 tests supplémentaires** par rapport à la base F6-B, et démonstration complète F6-C hors réseau. Les six sollicitations ont produit **trois acceptations**, **un refus de cadence**, **un refus de quota d'événements** et **un refus de quota de cycles**. Le superviseur a traité **quatre acquisitions F1-B**, écrit **trois observations** et enregistré **trois conséquences fictives** F2-C, sans aucun mouvement ni PC.

Mesures réellement produites par le **processus Linux GitHub Actions** pendant cette seule démonstration : latence p50 des six rapports **0,196 ms**, p95 par rang le plus proche **1,887 ms** (c'est le maximum des six), moyenne du **CPU du processus entier** par rapport **0,551 ms** et pic historique RSS de processus **18 324 Kio**. Les horloges de provenance des observations sont **synthétiques**, seules les mesures de charge du processus sont réelles. Ces chiffres ne garantissent aucun délai sur le robot et ne représentent ni consommation électrique, ni mémoire disponible du RK3566, ni performance de la vision.

## 4. Limites et risques vérifiables

- Les budgets CPU et de durée sont **coopératifs et a posteriori** : Python peut être bloqué par une requête I/O ou SQLite malgré F6-C. Un dépassement constaté ne coupe **pas** le thread ni la boucle `robotd`, et ne révoque pas une écriture déjà commise.
- Le quota d'événements agit **après la lecture et l'analyse de la trame F1-B**, mais avant la cognition et SQLite. Il ne peut éviter le coût initial de réception ni remplacer un ordonnanceur temps réel à priorité.
- Les contrôles sont en RAM, mono-processus, sans file d'attente ; ils ne s'appliquent ni automatiquement aux autres superviseurs ni aux véritables API OEM. Une instance concurrente ou plusieurs processus exigeraient une architecture distincte.
- Le champ `energy` des motivations F2 demeure **simulé** : ce n'est pas le niveau de batterie. Les relevés CPU du processus ne sont pas une mesure énergétique. Aucun seuil thermique ou batterie n'est implémenté par F6-C, faute de télémétrie matérielle validée.
- Pas d'enregistrement d'image ou de voix, ni de reconnaissance animale individuelle, ni de navigation ou détection d'escaliers validée. Le chantier locomotion reste séparé et suspendu.
- **Aucune validation de RAM libre, CPU/RSS, cadences ou thermie sur RK3566** ; aucun Ollama/Qwen réel 4B/9B sur le PC. La consommation réseau reste hors de ce garde.

## 5. Décision de phase et suite

**Livré :** un garde logiciel **facultatif**, contrôlable avec des tests déterministes, qui conserve le cerveau F2-D et refuse proprement les sollicitations excessives dans un scénario hors PC. **Non livré :** un scheduler temps réel, un service Yocto, une mesure d'énergie, un correctif de locomotion ou une validation embarquée.

**Prochaine étape F6-D :** préparer le protocole d'audit `scripts/resource-audit.sh` pour une unité physique, distinguer les étapes réalisables **sans robot** du relevé réel au repos/vision/déplacement surveillé, et fixer les critères de non-déploiement. Aucun chiffre hôte ne sera converti en marge mémoire ou autonomie du Microduck.
