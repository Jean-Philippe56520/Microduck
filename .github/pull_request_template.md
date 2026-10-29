## Porte 0 — jalon et valeur démontrable (OBLIGATOIRE)

- **Jalon du plan directeur / besoin réel de Kwipi :** [A–H, F, MEM, Cat ; lien précis].
- **Résultat attendu pour Kwipi :** [scénario entrée → meilleure décision / preuve / abstention ; ou correction de sûreté/obligation documentaire].
- **Écart constaté sur la baseline :** [SHA, fichiers/tests, mesure ou fait vérifiable ; pas une intuition].
- **Pourquoi réutiliser/tester l'existant ne suffit pas :** [ou « aucun nouveau code », justifié].
- **Témoin / cas positifs et négatifs :** [comparaison avant/après, inconnus, erreurs et sécurité].
- **Critère de passage et critère d'arrêt fixés AVANT résultat :** [preuve, seuil justifié, environnement ; si donnée externe absente → `bloqué` et pivot].
- **Valeur obtenue et décision de clôture :** [`progres_demontré`, `test_logiciel_seul`, `bloque_source_externe`, `insuffisant`, `abandonne_non_prioritaire`; liens mesures ou « pas encore mesuré »].

**Refuser** les PR qui ajoutent une couche de préparation sans démontrer leur nécessité pour un jalon. CI verte, fichiers changés et nombre de tests **ne sont pas le résultat fonctionnel**. Une pièce de preuve facultative indisponible n'interdit pas un autre jalon indépendant. Documentation seule : démontrer quelle décision de travail obligatoire elle corrige. Voir [protocole anti-dérive](../docs/development-reuse-protocol.md).

## Objectif et statut réel

Décrire précisément la fonction livrée : prévu / codé / test logiciel (fixtures ou médias publics) / simulé / validé sur robot. Éviter les affirmations non mesurées.

## Inventaire réutilisation avant développement (obligatoire)

- **Responsabilité et propriétaire** : robotd / mediad / tofd / autre OEM / Companion.
- **Sources OEM inspectées, révisions et liens** : [chemins, SHA, état réel ; ou « non inspecté »].
- **Sources Companion inspectées** : [chemins et fonctions déjà disponibles].
- **Composants réutilisés ou adaptés** : [noms précis, contrats préservés].
- **Nouveau code et nécessité démontrée** : [qu'est-ce que l'existant ne permet pas ?].
- **Risque de doublon / interface constructeur future (dont M9) / plan de retrait** : [aucun ou justification].

Voir [le protocole de réutilisation permanent](../docs/development-reuse-protocol.md).

## Porte préalable « constructeur d'abord » (obligatoire)

- [ ] **Baseline OEM épinglée** : manuel, scripts, politiques, scène, actionneurs, configuration normale et tests consultés (ou « sans objet », justifié)
- [ ] **Installation réellement active** : versions/SHAs, fichiers/poids, paramètres, journaux et état observé comparés à la baseline
- [ ] **Réutilisation d'abord** : preuve que les outils OEM et les composants Companion existants ne suffisent pas avant toute nouvelle logique
- [ ] **Observabilité avant action** : diagnostic en lecture seule examiné ; si essai actif, question, témoin, limites, stop, rollback et mesure d'effet explicités
- [ ] **Conclusion graduée** : observation ≠ hypothèse ≠ cause prouvée ; absence de preuve classée inconnue ; PR ouvertes ≠ fonctions livrées

Le [dossier de reprise SIM-E2](../docs/reprise-microduck-oem-sim-e2-2026-10-28.md) illustre le piège « vitesse OEM appliquée ≠ vitesse physique du robot ». Indiquer explicitement « sans objet » si une case ne s'applique pas au lot documentaire.

## Sûreté, confidentialité et ressources

- [ ] robotd garde l'autorité motrice, aucune contournement du contrôle 50 Hz et des protections constructeur
- [ ] provenance et fraîcheur vérifiées ; fixtures, données WebRTC et hypothèses Qwen ne deviennent pas des capteurs authentifiés
- [ ] pas de photos, voix, secrets, noms privés ou identités personnelles dans GitHub
- [ ] RAM/CPU/stockage/thermie mesurés à la bonne cible ; les résultats hôte ne deviennent pas des promesses pour RK3566
- [ ] sans PC ou capteur indisponible : comportement local sûr et silencieux
- [ ] sous-modules et licences préservés ou changement documenté dans un lot distinct

## Vérifications et preuves

- [ ] tests nominaux et d'échec exécutés (détailler commande et résultat réel)
- [ ] README, roadmap, plan directeur, audit matériel actualisés si applicables
- [ ] liens GitHub CI / rapports / limites fournis
- [ ] aucune validation physique prétendue sans robot physique

**Décision à la revue** : réutilisation confirmée / exception justifiée / PR à réviser.
