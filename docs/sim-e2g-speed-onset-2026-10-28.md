# SIM-E2G — un départ à 0,30 m/s réellement mesuré en MuJoCo OEM

**28 octobre 2026 · [PR #124](https://github.com/Jean-Philippe56520/Microduck/pull/124) ; [CI MuJoCo #40729501060](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40729501060) VERTE ; [CI Python #40729510582](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40729510582) VERTE.** Mesure **simulée constructeur**, pas sur robot et pas une démarche validée. SIM-E2 #101 reste ouverte.

## Observation, hypothèse, preuve et décision

**Constat préexistant :** P0i avait mesuré **1,444 mm** XY avec alpha et **1,968 mm** avec VelStand à `vx=0,12 m/s`, sur 24 commandes et deux boots isolés. En WSLg, `vx=0,08 m/s` avait produit **3,500 mm** nets sur 32 observations actives. Une politique `walk` et une consigne `applied` ne prouvent pas la translation. Le constructeur épinglé charge alpha en sim mais VelStand sur le robot ; la [PR OEM #450](https://github.com/pollen-robotics/microduck/pull/450) est **ouverte**, rapporte principalement une différence de yaw et n'est pas incorporée.

**Hypothèse externe précise :** [microduck_rl #59](https://github.com/pollen-robotics/microduck_rl/issues/59) signale que les politiques de **génération v5** peuvent rester sur place à 0,15 m/s depuis l'arrêt et commencer à avancer vers **0,30 m/s**. Cette preuve communautaire n'identifie pas notre v8, mais suggère un essai discriminant **sans réglage arbitraire de gain**.

**Question pré-enregistrée :** sur les sources et modèles v8 épinglés, la même commande constructeur de `vx=0,30 m/s`, `vy=vyaw=0`, provoque-t-elle **au moins 10 mm** de translation XY du tronc, avec sol, sécurité, vitesse appliquée, politique et arrêt vérifiés ? La référence P0i à 0,12 m/s est **historique, non randomisée et de durée différente** ; aucun ratio d'amélioration causal n'est déduit de ces chiffres.

## Porte OEM et limites de l'essai

- OEM `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, scène plate, PID/port du serveur certifiés par les validateurs existants. Aucune modification de gitlink.
- Politique chargée vérifiée **dans `robotctl policy list --json` et la configuration du daemon** : `alpha_walking.onnx` SHA `e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c` ; `alpha_stand.onnx` SHA `1569268713e40deea795dd2922dba50d3621e15a872855408b6b1b125b1c094b`. `velstand.onnx` SHA `2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492` est présent dans le jeu officiel mais **pas activé pour ce test**.
- Réutilisation de J2e `run_walk_trial` : baseline sans consigne (dérive maximale 5 mm), `robotd.health`, `robot.state`, horloge MuJoCo, zone plane, batterie >25 %, commande 10 Hz, **`robot.stop` accepté**, `deadman` OEM intact. Vitesse **allowlist** seulement 0,12 (historique) ou 0,30 (SIM-E2G) ; à 0,30, durée maximale réduite à **12 ticks**. Aucun changement de gain, de frottement, de scène, de politique, de modèle ou de sûreté.
- **Risque et retour arrière :** une commande plus forte peut épuiser les 0,50 m de marge de zone déclarée avant les 24 ticks historiques ; toute zone/horloge/santé non sûre interrompt le test, et l'état moteur demeure sous `robotd`. Le premier run, à 24 ticks, a été **interrompu après 21 commandes** : `walking trial aborted after 21 command(s)`. L'arrêt explicite a suivi le chemin contrôlé, mais **aucune pose finale valide n'a été publiée** ; cause de l'interruption **non identifiée**. La reprise à 12 ticks n'est pas un nouveau balayage de vitesses : elle réduit l'exposition à la frontière sans diminuer la marge. En cas de nouvel échec, arrêt du chantier actif, sans nouvelle variante.
- SQLite d'essai `sim-e2g-disposable.sqlite3` uniquement dans le dossier temporel du simulateur ; aucune mémoire du robot modifiée, aucune preuve de récompense causale, pas de média privé.

## Preuve OEM : résultat du run final

[GitHub Actions #40729501060](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40729501060), artefact `mujoco-headless-diagnostics` avec `sim-e2g-report.json` ; [Python #40729510582](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40729510582) vert.

| Grandeur réellement observée | Valeur |
| --- | ---: |
| Consigne X (vitesse de demande) | +0,300 m/s |
| Maximum X « applied » retourné par `robot.state` | +0,2999997 m/s |
| Échantillons politique | 12 / 12 `walk` |
| Limiteurs rapportés pendant le test | Aucun |
| Commandes `robot.move` envoyées | 12 |
| `robot.stop` explicitement confirmé | Oui |
| Dérive de référence sans mouvement | 0,0736 mm |
| Temps simulé depuis la référence | 1,420 s |
| Translation avant X du tronc | **+104,300 mm** |
| Translation latérale Y du tronc | **−34,223 mm** |
| Distance nette XY du tronc | **109,771 mm** |
| Seuil de signal de translation (10 mm) | **Dépassé** |
| Démarche stable, cause racine, robot physique | **Non validés** |

**Fait démontré :** une translation du tronc supérieure à 10 cm s'est produite lors d'une unique demande à 0,30 m/s, dans le simulateur OEM épinglé, avec des commandes et une politique réellement chargées, un sol de référence sans dérive significative et l'arrêt acquitté. Ce n'est pas un score de simulation inventé par fixture ; c'est un état MuJoCo mesuré via le protocole existant.

**Faits non démontrés :** vitesse de marche stationnaire (l'essai inclut l'accélération), cycle de pas ou alternance de contacts, répétabilité, validité du comportement physique du Microduck, origine exacte du seuil, performance de VelStand à froid, stabilité en terrain inconnu, apprentissage causal ou politique personnelle de Kwipi. La durée 1,42 s et les différentes sessions **interdisent** de présenter `109,771 / 1,444` comme un gain causal.

**Décision :** la branche alpha du simulateur épinglé **peut traduire à 0,30 m/s** ; les essais de 0,08–0,12 m/s restent non concluants pour le départ à faible vitesse, et une limite d'amorçage est une hypothèse renforcée, non prouvée. **STOP aux essais moteurs supplémentaires** tant qu'un protocole de répétabilité et d'effets indépendants n'est pas validé et que la réponse constructeur sur `obs[61]` et `raw_actions[14]` demeure absente. SIM-E2 #101 reste ouverte ; pas de déploiement sur robot.

## Réutiliser / adapter / créer

**Réutiliser :** OEM `duck-sim`, `robotctl`, `robotd` seul pilote, validators de provenance P0h/P0i, J2e et `ExperienceMemory` uniquement jetable. **Adapter :** autoriser une unique nouvelle vitesse 0,30 et raccourcir son enveloppe dans la boucle de sûreté J2e ; rendre lisible la catégorie d'abandon. **Créer :** un contrôleur CLI sans deuxième ordonnanceur, branch-only, sans télémétrie personnelle et ses tests adversariaux. Les projets QuackNav/microduck-brain, GC/Smartulf, Quacksat, Twin ne sont pas importés ; l'issue RL #59 fournit la référence communautaire, non une licence de recopier des poids.

**Limites ressources :** aucune mesure pertinente RK3566 (RAM/RSS, CPU/NPU, thermie, disque/WAL, batterie, boucle 50 Hz sur matériel) n'a été produite. `scripts/resource-audit.sh` reste indispensable avant portage.
