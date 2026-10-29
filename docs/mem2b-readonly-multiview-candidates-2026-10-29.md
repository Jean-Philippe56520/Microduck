# MEM-2B — rappel candidat multi-vues conservateur (29/10/2026)

**État : codé et testé sur fixtures PC dans [PR #173](https://github.com/Jean-Philippe56520/Microduck/pull/173) (fusion après revérification du head et des CI).** Base `main@666fe28aa31d59451291978e2d1ae6a1205edb86`. Le plan directeur reste autoritaire.

## Porte 0 et preuve recherchée
Constat : MEM-2A relit catégories et objectifs fictifs, M1-B compare déjà des empreintes mais sa voie `observe_image` écrit en SQLite. Une comparaison avec/sans mémoire serait contaminée par l'enregistrement de l'observation à tester. Hypothèse : le même historique, interrogé sans écriture, permet deux rappels de candidats artificiels et refuse deux négatifs artificiels.

**Critères fixés avant le test** : 2/2 variantes positives renvoient un *candidat non vérifié*, contre 0/2 sans rappel ; 2/2 inconnues n'ont aucun candidat ; ambiguïté entre groupes, catégorie contradictoire, expiration, futur, budget de recherche incomplet : aucun ID de candidat exploitable. Zéro écriture pendant rappel, zéro mouvement, zéro Qwen. Un imposteur avec empreinte identique peut produire un **faux candidat** : c'est une limite à conserver, pas une réussite de reconnaissance.

## Matrice de réutilisation
- **Réutiliser** `ExperienceMemory`, `memory_recall.recall_memory`, C1/C2 et `image_fingerprint` M1-A ; une seule SQLite.
- **Adapter** `MultiviewPatternMemory` avec `probe_image` (SELECT borné), et ajouter `multiview_hint` facultatif au rappel MEM-2A. Aucun schéma ni contrôle moteur.
- **Créer** seulement des tests d'ablation positifs/négatifs. Ne pas intégrer QuackNav, microduck-brain, Quacksat ou nouveau modèle sans besoin.
- **OEM** : robotd épinglé `942e58e3aa6dbb28e7037203fff11866122c7567` propriétaire exclusif des moteurs 50 Hz ; microduck_rl `b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Aucune modification.

## Interprétation
Le groupe M1-B vient d'une déclaration **synthétique**, pas d'une preuve que deux images viennent réellement du même objet. La sonde ne promeut ni groupe en identité F0, ni catégorie historique en fait, ni conseil Qwen en action. Les deux variantes positives proviennent des mêmes carrés synthétiques (luminosité modifiée), et ne démontrent **pas** une généralisation sur scènes ou sessions réelles. Les scores ne sont pas des confiances calibrées. Les catégories partagées acceptées au raccord MEM-2B : `unknown/cat/dog`; les personnes sont exclues.

## Test et retour arrière
`python -m unittest discover -s tests -p test_mem2b_readonly_multiview.py -v`, puis CI Python et N1. [CI Python #40890582032](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40890582032) (1 766 tests réussis, 5 ignorés) et [N1 #40890582007](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40890582007) réussies sur commit `b3877657` ; uniquement sur fixtures PC. Tests : ablation, imposteur, ambiguïté, catégorie conflictuelle, budget, temps, entrées invalides, corrections et réouverture SQLite. `recall_memory` sans arguments nouveaux préserve MEM-2A ; retour arrière sans migration. Robot absent, RSS/latence RK3566, reconnaissance physique et causalité **inconnus**.

**Porte suivante** : tester sur vues réellement indépendantes et annotées avant d'affirmer une continuité d'objet ou une amélioration cognitive générale. Si CI échoue ou critères négatifs rompus, pas de fusion.

## Résultat et limite (tests hôte)

La CI a exécuté les **neuf nouveaux tests ciblés** et l'ensemble de la suite Python (1 766 tests réussis, cinq ignorés) sans erreur. Dans ces fixtures, le candidat apparaît pour les **deux variantes artificielles attendues** et pour aucune des deux observations négatives ; sans branchement du rappel aucun candidat n'est fourni. Un imposteur artificiel donnant la même empreinte produit bien un **faux candidat** (score 1), sans promotion en identité : la collision doit rester visible dans l'évaluation. Ambiguïté entre groupes, conflit de catégorie, expiration, budget incomplet, données invalides et reprise de SQLite sont vérifiés. Le test constate également l'absence d'écriture de données pendant les consultations. Ces résultats ne démontrent pas que F2 prend de meilleures décisions sur des scènes réelles.

**Décision :** preuve du contrat logiciel, statut `test_logiciel_seul` ; MEM-2B n'est **pas** validé pour la continuité d'objet physique. La prochaine preuve utile est un corpus multi-vues **indépendant et annoté**, avec faux rapprochements mesurés, sans retoucher les seuils sur le test. Ne pas enchaîner des outils supplémentaires à partir de cette seule CI.
