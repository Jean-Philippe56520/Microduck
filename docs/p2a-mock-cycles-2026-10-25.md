# P2a — Cycles cognitifs fictifs persistants (25 octobre 2026)

**Statut : codé, testé sur données fictives.** [GitHub Actions #40207932413](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40207932413) : **217 tests Python réussis** (en comptant les tests existants), et deux sessions déterministes `session-a` et `session-b` sur **la même** base `$RUNNER_TEMP/p2a-memory.sqlite3`.

## Ce qui a été vérifié

- `MockCycleRunner` accepte seulement des `PerceptionSnapshot(environment="mock")` et des observations dont la source est exactement `mock`. LLM, simulateur ou données d'un robot réel ne peuvent pas se présenter comme ce scénario.
- À chaque cycle : récupérer les souvenirs et motifs, choisir une intention, classer les intentions motrices `explore` ou `play_with_object` en `blocked_motion`, enregistrer l'intention et son résultat **fictif** en SQLite, puis passer à une nouvelle observation. **Aucun `robot.move`, aucune API moteur, aucun accès réseau ni Qwen.**
- Un retour de préférence (positif ou négatif : amplitude fictive fixée à ±0,4) exige un événement `MockConsequence` **explicite**, associé à l'inspection d'un même objet suivi, une observation fictive ultérieure fraîche et un ordre temporel vérifié. Une simple répétition de détection ne devient jamais automatiquement un succès.
- Le renforcement appliqué dans le monde `mock` suit la petite mise à jour `p' = clamp(0,85 p + 0,15 r)`. Ce n'est **ni un apprentissage des poids de l'IA, ni un retour d'expérience du robot physique**. Le journal est atomique avec sa mise à jour de préférence et une contrainte SQLite empêche la double récompense du même numéro de cycle.
- Une perte de perception sûre déclenche `halt`, même si un succès fictif antérieur a été conservé en mémoire. L'intention précédente est rechargée après réouverture afin de conserver une légère pénalité de répétition.

## Deux sessions de démonstration CI

| Indicateur | Première session | Après fermeture et réouverture SQLite |
| --- | ---: | ---: |
| Cycles journalisés cumulés | **4** | **8** |
| Préférence du jouet fictif suivi | **0,06** | **0,06** |
| Commandes motrices envoyées | **0** | **0** |
| Validation réelle ou de démarche | Non | Non |

La seconde session ne produit **pas** une nouvelle récompense pour un mouvement non exécuté. Tests de cohérence et retour sans preuve : absence de récompense ; doublon SQLite : pas de seconde mise à jour ; source LLM ou `simulator` interdite dans le mock ; échantillon obsolète : décision sûre.

## Limites et suite

Cette démonstration est volontairement **hors des services MuJoCo officiels**, et n'atteste aucune performance de locomotion, capacité cognitive embarquée, température, batterie ni reconnaissance d'animaux réels. Les observations et conséquences sont des **fixtures synthétiques sans données personnelles**. L'architecture préserve `robotd` comme seule autorité motrice.

**P2b proposé :** collecter plusieurs snapshots datés des vrais services `robotd` et `tofd` **du simulateur**, faire choisir des intentions passivement sans envoyer d'ordres, journaliser les états/échecs et vérifier une base SQLite conservée entre deux sessions de collecte dans GitHub Actions. Le résultat devra distinguer intentions proposées et résultats réellement mesurés.
