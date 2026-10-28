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
