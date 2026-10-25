# F3-D — Évaluation indépendante supplémentaire sur JPEG publics et mesures hôte

**26 octobre 2026 — [PR #35](https://github.com/Jean-Philippe56520/Microduck/pull/35), non fusionnée.** Cette étape suit F3-C, [fusionnée via PR #34](https://github.com/Jean-Philippe56520/Microduck/pull/34), et conserve l'interdiction absolue de commande motrice par la perception expérimentale.

## 1. Question mesurée et nouveau banc

Le premier banc F3-B portait sur **20 photos** déclarées CC0 de Wikimedia Commons, dont seulement **6 photos de test** (2 chats, 2 chiens, 2 images hors catégorie). MobileNetV2 ImageNet préentraîné obtenait 5/6 sur ce tout petit ensemble, avec un seuil de rejet sélectionné sur **les 6 photos de validation de F3-B**.

F3-D définit un **nouveau jeu d'évaluation**, distinct par **28 fichiers et 28 auteurs crédités** des fichiers et auteurs de **toutes les partitions F3-B**. Sa composition est figée dans `microduck_companion/visual_photo_f3d_catalog.py` :

| Étiquette utilisée | Photos réelles nouvelles | Précision de portée |
| --- | ---: | --- |
| `cat` | 8 | Chat domestique déclaré dans la description publique |
| `dog` | 8 | Chien déclaré dans la description publique |
| `unknown` — chaises | 4 | Hors des deux classes reconnues |
| `unknown` — fleurs | 4 | Hors des deux classes reconnues |
| `unknown` — oiseaux | 2 | Hors des deux classes reconnues |
| `unknown` — balles | 2 | Hors des deux classes reconnues |
| **Total** | **28** | **16 chats/chiens, 12 hors catégorie** |

**Choix méthodologique :** le seuil **0,7059010988271212** est gelé, repris *exactement* de [l'exécution F3-B et de sa validation](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40243269608). Il n'est **ni optimisé ni calibré** avec ces 28 nouveaux exemples. Il s'agit du même modèle MobileNetV2 ONNX ImageNet-1k, empreinte de poids `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`, 13 964 571 octets, licence Apache-2.0 déclarée par ONNX Model Zoo. **Aucun réentraînement** dans F3-D.

## 2. Résultats effectivement observés sur les 28 JPEG

[Dernier banc F3-D réussi en CI Ubuntu](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671367). **Ces nombres sont des résultats réels du traitement de JPEG téléchargés**, pas une simulation de prédictions ; les étiquettes restent **issues de la description publique des fichiers, sans double annotation indépendante**.

| Métrique | Résultat observé |
| --- | ---: |
| Réponses exactes selon ces étiquettes publiques | **20/28 = 71,4 %** |
| Chats effectivement reconnus comme chats | **3/8 = 37,5 %** |
| Chiens effectivement reconnus comme chiens | **5/8 = 62,5 %** |
| Total chats/chiens classés correctement | **8/16 = 50 %** |
| Confusions chat → chien | **2** |
| Chats ou chiens refusés comme `unknown` | **6** |
| Images hors catégorie correctement classées `unknown` | **12/12** |
| Faux annonces chat/chien sur les 12 hors catégorie | **0/12** |
| Couverture (réponse `cat` ou `dog`, y compris deux confusions) | **10/28 = 35,7 %** |

Matrice de confusion (lignes : catégorie attendue, colonnes : sortie classifieur) :

| Vérité / Sortie | `cat` | `dog` | `unknown` |
| --- | ---: | ---: | ---: |
| `cat` | 3 | 2 | 3 |
| `dog` | 0 | 5 | 3 |
| `unknown` | 0 | 0 | 12 |

**Les 71,4 % d'exactitude globale sont trompeurs si on les lit comme un taux de reconnaissance d'animaux : le rappel des catégories animales n'est que de 50 %.** L'abstention fonctionne sur les quelques exemples choisis, mais 0 faux positif parmi 12 « inconnus » **ne démontre aucun taux de fausse détection nul dans la vraie vie** : borne supérieure Wilson 95 % descriptive ≈ **24,2 %**, sur ces douze essais seulement. Pour le taux de bonnes réponses 20/28, l'intervalle Wilson descriptif est environ **52,9 % à 84,7 %** ; il ne constitue **pas** un intervalle de confiance généralisable à un foyer, car l'échantillon n'a **pas été tiré au hasard**. Les photos ne garantissent pas l'absence de doublons dans le corpus de préentraînement ImageNet du modèle externe.

**Bilan catégoriel :** chaises 4/4 refusées ; fleurs 4/4 refusées ; oiseaux 2/2 refusés ; balles 2/2 refusées. L'absence de faux positif sur ces quelques sujets ne vaut pas test des conditions domestiques (animaux en mouvement, éclairage faible, jouets proches, arrière-plans et occultations).

## 3. Mesures effectuées sur le Linux du runner, et non sur le RK3566

[CI F3-D du 26 octobre 2026](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671367) :

| Mesure sur l'hôte GitHub Actions | Valeur |
| --- | ---: |
| Modèle ONNX sur disque | **13 964 571 octets** |
| Médiane d'inférence brute ONNX CPU, 28 images | **9,036 ms/image** |
| p95 d'inférence CPU (rang discret), 28 images | **9,240 ms/image** |
| Maximum d'inférence CPU | **9,311 ms/image** |
| Médiane prétraitement d'une vignette JPEG vers tenseur ImageNet | **3,763 ms/image** |
| Pic RSS de **tout le processus Linux** | **108 148 Kio ≈ 105,6 Mio** |
| RSS initial du processus (avant session ONNX) | **54 676 Kio ≈ 53,4 Mio** |
| RSS après chargement de la session ONNX | **99 524 Kio ≈ 97,2 Mio** |
| CPU total consommé par le processus pendant le benchmark | **2,478 s** |
| Durée murale totale **avec téléchargement** | **6,795 s** |
| Octets JPEG publics effectivement lus | **1 106 133** |

L'exécution est forcée sur `onnxruntime CPUExecutionProvider` avec un seul thread intra-/inter-opérateur. Les mesures de processus **comprennent Python, NumPy, Pillow, ONNX Runtime, le modèle et la gestion du téléchargement** ; les différences de RSS ne sont pas une estimation rigoureuse de la mémoire propre au modèle. La durée murale comprend le réseau, pas seulement l'inférence. Le RSS n'a **aucune relation établie** avec la marge disponible sur le Rockchip RK3566 : les buffers caméra, robotd, mediad et NPU restent inconnus. Aucun pilote NPU, aucune consommation thermique, aucune batterie ou cadence de moteur n'a été évalué.

Un premier run F3-D réussi a totalisé **1 105 956 octets JPEG**, contre **1 106 133** dans ce second run, avec les mêmes nombres de classifications. Les vignettes externes ne sont **pas épinglées par hash dans notre dépôt** : leur contenu/octet exact peut varier. Il serait incorrect d'annoncer une parfaite reproductibilité des images ou des métriques dans le temps.

## 4. Catalogue des 28 pages sources déclarées CC0

Toutes les pages ci-dessous ont été localisées sur Wikimedia Commons comme fichiers publics **« Own work » et CC0 1.0 déclarés** à la date de revue. Ce sont des **déclarations** des contributeurs ; **les droits de chacun et les étiquettes n'ont pas été vérifiés par un deuxième annotateur**. Les noms ci-dessous sont des noms **publics de contributeurs Commons**, pas des personnes du foyer ; aucune image/voix personnelle ou donnée du robot n'est publiée.

| Page de fichier Wikimedia Commons | Auteur public déclaré | Groupe de test |
| --- | --- | --- |
| [A_photo_of_a_cat_sitting_down.jpg](https://commons.wikimedia.org/wiki/File:A_photo_of_a_cat_sitting_down.jpg) | Asabae2752 | cat |
| [Nopple_cat.jpg](https://commons.wikimedia.org/wiki/File:Nopple_cat.jpg) | Nopple | cat |
| [The_black_and_white_cat.jpg](https://commons.wikimedia.org/wiki/File:The_black_and_white_cat.jpg) | Khidoyatxon | cat |
| [Poised_Cat.jpg](https://commons.wikimedia.org/wiki/File:Poised_Cat.jpg) | Ian Rastall | cat |
| [Cat_lying_down.jpg](https://commons.wikimedia.org/wiki/File:Cat_lying_down.jpg) | Teojincheng | cat |
| [Black_cat_staring_at_the_camera_(2023-07-16).jpg](https://commons.wikimedia.org/wiki/File:Black_cat_staring_at_the_camera_(2023-07-16).jpg) | Roc0ast3r | cat |
| [Gato_doméstico_(Felis_silvestris_catus).jpg](https://commons.wikimedia.org/wiki/File:Gato_dom%C3%A9stico_(Felis_silvestris_catus).jpg) | Juan Emilio Prades Bel | cat |
| [Cat_image.jpg](https://commons.wikimedia.org/wiki/File:Cat_image.jpg) | Mohanraj55 | cat |
| [Animal_photography..dog.jpg](https://commons.wikimedia.org/wiki/File:Animal_photography..dog.jpg) | JAYASHREESATHIYAMOORTHY | dog |
| [Domesticated_dog.jpg](https://commons.wikimedia.org/wiki/File:Domesticated_dog.jpg) | Raizkgh | dog |
| [Petting_my_dog.jpg](https://commons.wikimedia.org/wiki/File:Petting_my_dog.jpg) | JaredMcKenzie | dog |
| [Cute_street_dog.jpg](https://commons.wikimedia.org/wiki/File:Cute_street_dog.jpg) | Abhi3120 | dog |
| [IMg_dog.jpg](https://commons.wikimedia.org/wiki/File:IMg_dog.jpg) | A140706 | dog |
| [Dog_smiling_at_the_camera_-_Reta,_Buenos_Aires,_Argentina_(04-01-2024).jpg](https://commons.wikimedia.org/wiki/File:Dog_smiling_at_the_camera_-_Reta%2C_Buenos_Aires%2C_Argentina_(04-01-2024).jpg) | Maxd2 | dog |
| [Guide_dog_at_RSM_2024.jpg](https://commons.wikimedia.org/wiki/File:Guide_dog_at_RSM_2024.jpg) | Whispyhistory | dog |
| [The_cute_dog(poppy).jpg](https://commons.wikimedia.org/wiki/File:The_cute_dog(poppy).jpg) | Ranjithkanth Tamilselvan J | dog |
| [Chair.JPG](https://commons.wikimedia.org/wiki/File:Chair.JPG) | Antonio Borrillo | chair |
| [Cultural_Chair.jpg](https://commons.wikimedia.org/wiki/File:Cultural_Chair.jpg) | 787IYO | chair |
| [Red_chair.jpg](https://commons.wikimedia.org/wiki/File:Red_chair.jpg) | Fitrah 9131 | chair |
| [A_Fabric_Chair.jpg](https://commons.wikimedia.org/wiki/File:A_Fabric_Chair.jpg) | Ashakemary | chair |
| [Flower_photos.jpg](https://commons.wikimedia.org/wiki/File:Flower_photos.jpg) | Abinayasekar357 | flower |
| [FLOWER(1).jpg](https://commons.wikimedia.org/wiki/File:FLOWER(1).jpg) | SIVA ARULMOZHLI | flower |
| [Flower_🌷.jpg](https://commons.wikimedia.org/wiki/File:Flower_%F0%9F%8C%B7.jpg) | E.Prabha | flower |
| [Pink_Paper_flower.jpg](https://commons.wikimedia.org/wiki/File:Pink_Paper_flower.jpg) | By atmika | flower |
| [Silhouette_of_Bird.jpg](https://commons.wikimedia.org/wiki/File:Silhouette_of_Bird.jpg) | Biveti46 | bird |
| [A_lighting_bird.jpg](https://commons.wikimedia.org/wiki/File:A_lighting_bird.jpg) | ManikDas1122 | bird |
| [Golf_ball_in_dirt,_sep_6_2026.jpg](https://commons.wikimedia.org/wiki/File:Golf_ball_in_dirt%2C_sep_6_2026.jpg) | Logan M Diel | ball |
| [Throwing_ball_exercise.jpg](https://commons.wikimedia.org/wiki/File:Throwing_ball_exercise.jpg) | Onwuka Glory | ball |

Les téléchargements restent éphémères en mémoire sur GitHub Actions, en **vignettes de 320 px**, avec contrôle de l'hôte HTTPS Wikimedia et refus des réponses non JPEG, des fichiers volumineux ou des erreurs réseau (pas de score partiel). Les empreintes SHA-256 des JPEG sont utilisées **en mémoire** pour refuser des copies exactes **à l'intérieur du nouvel ensemble**, sans publication ni garantie de détection des quasi-doublons ou d'un recoupement ImageNet. Les groupes d'auteurs sont distincts des 20 exemples F3-B. La procédure ne traite pas de vrais médias de la maison.

## 5. Code, tests et reproduction

- `microduck_companion/visual_photo_f3d_catalog.py` : catalogue fermé, 28 pages, auteurs, six groupes et détection d'un auteur/fichier réutilisé depuis F3-B.
- `microduck_companion/visual_photo_f3d_benchmark.py` : téléchargement strict, contrôle du modèle, inférence avec seuil figé, matrice de confusion, erreurs par groupe, faux positifs `unknown`, intervalles Wilson **descriptifs**, latences p50/p95 et mesures RSS/CPU **hôte**.
- `tests/test_visual_photo_f3d.py` et `tests/test_visual_photo_f3d_scoring.py` : 19 nouveaux tests **hors réseau**, sur identifiants, catégories, droits déclarés, refus des téléchargements non autorisés, mathématiques de scores, seuil figé et ressources Linux.
- [Pipeline dédié F3-D](https://github.com/Jean-Philippe56520/Microduck/blob/feat/f3d-open-set-resource-benchmark-20261026/.github/workflows/f3d-open-set.yml) : prend les poids ONNX Apache-2.0 depuis la source publique, vérifie SHA-256, traite les nouvelles photos en mémoire et écrit **uniquement les agrégats** dans les logs, sans téléchargement de médias privés ni commandes moteurs.

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
# Linux connecté, avec Pillow 11.3.0, NumPy 1.26.4, onnxruntime 1.21.0,
# et un fichier MobileNetV2 ONNX de SHA-256 attendu :
python -m microduck_companion.visual_photo_f3d_benchmark --model /chemin/mobilenetv2-12.onnx
```

**Preuve :** [570 tests Python réussis sur la branche (19 nouveaux F3-D)](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671272), [F3-D photos réelles et ressources hôte](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671367), [F3-B non régressé](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40244671290). Les chiffres de ce rapport datent du run F3-D précité ; le prochain commit documentaire nécessite encore un passage de CI.

## 6. Décision suivante, distincte de la présente PR

Le modèle ne peut pas être considéré prêt pour une interaction fiable avec les animaux : **8/16 animaux correctement reconnus** sur ce jeu, dont deux chats confondus avec des chiens. **F3-E**, sous réserve de revue et fusion F3-D, devra choisir entre extension/contre-annotation de données réellement indépendantes, benchmark de scénarios difficiles et étude d'un vrai détecteur spatial (boîtes) avec catégorie `unknown`, puis définir une interface `mediad` authentifiée et sans commandes moteurs. Toujours vérifier droits et confidentialité. Le portage RKNN, le fonctionnement sans PC, la thermie, les limites mémoire sur robot, les capteurs de sécurité et la locomotion **ne sont pas validés**.
