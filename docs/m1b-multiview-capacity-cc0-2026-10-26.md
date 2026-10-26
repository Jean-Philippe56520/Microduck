# M1-B — Capacité configurable, groupes multi-vues et tests de similitude sur médias publics

**26 octobre 2026 — [PR #50](https://github.com/Jean-Philippe56520/Microduck/pull/50), étude hors robot.** Cette phase corrige le dépassement du plafond global M1-A, implémente une couche expérimentale M1-B à signatures multiples et mesure les limites d'une représentation simple d'images/sons. **Aucun modèle de reconnaissance fiable ni moteur réel n'est intégré.**

## 1. Correction de M1-A : plafond global exact

L'ancienne insertion calculait `len(rows)` **uniquement dans la modalité entrante**. Une base contenant 256 images pouvait recevoir un audio supplémentaire et atteindre **257 signatures**. Le correctif de `compact_multimodal_memory.py` vérifie désormais **`SELECT COUNT(*)` sur images ET audio** avant l'insertion, puis supprime globalement la plus ancienne empreinte si nécessaire. Le contrat legacy **256 lignes maximum** est maintenu pour compatibilité ; M1-A ne change pas de schéma, et les tests vérifient explicitement **256 images → 1 son → 255 images + 1 son**.

**La nouvelle politique M1-B est une couche distincte dans la même connexion SQLite `ExperienceMemory`, pas une migration automatique de M1-A.** Les données des deux tables expérimentales ne sont pas additionnées par un budget universel de la mémoire du robot. Ne pas brancher les modules à de vrais capteurs tant qu'un stockage global en octets incluant **toutes** les tables, fichiers WAL et buffers n'a pas été validé.

## 2. Groupes de souvenirs et variantes

`multiview_pattern_memory.py` conserve les empreintes de M1-A : **64 octets image** (gris 32×32, grille de contraste) et **16 octets audio** (histogramme spectral/enveloppe sur PCM16 8kHz). Elles ne sont **pas des embeddings appris**. La couche M1-B crée deux tables `m1b_groups` et `m1b_signatures`, dans la SQLite existante, et autorise plusieurs empreintes par groupe, une modalité par groupe.

- Une **observation clairement similaire** à une signature déjà liée incrémente un seul compteur de groupe et le compteur de la signature correspondante. Une photo ou un fichier son brut n'est pas sauvegardé.
- Une **vue très différente** est séparée par défaut. Il faut un **`group_hint` et `synthetic_same_source_claim=True`** explicitement fournis par la fixture pour l'associer au même groupe ; ce drapeau n'atteste aucune identité réelle et ne peut pas venir d'une hypothèse Qwen non vérifiée.
- Un rapprochement au-dessus du seuil avec deux groupes concurrents presque équivalents ou une contradiction `cat`/`dog` retourne `ambiguous_unverified` et **n'écrit pas de correspondance**. Si le quota de comparaisons ne permet pas d'examiner **tous** les candidats, `search_budget_exhausted` signifie **ni connu, ni nouveau** ; aucune association n'est créée.
- Une étiquette `person` visuelle ou `speech` sonore est refusée dans les fixtures. **Il ne s'agit pas d'un filtre de confidentialité sur des médias réels inconnus : ne pas brancher une caméra ou microphone réel sans filtre fiable indépendant.**
- Les transactions `BEGIN IMMEDIATE` sérialisent les opérations d'insertion/éviction entre processus SQLite, sans certifier la sécurité de la boucle cognitive entière. La suppression des groupes retire aussi leurs signatures. Lorsqu'une connexion rouvre la base avec un budget plus strict, les anciennes signatures et groupes sont ramenés dans le nouveau quota.

## 3. Limites de prototype configurables — **pas des limites sûres du RK3566**

| Contrôle | Valeur initiale M1-B | Garantie limitée |
| --- | ---: | --- |
| Groupes visuels ou sonores | **1 024** | Maximum de groupes dans les tables M1-B |
| Empreintes actives | **4 096** | Images et audio **réunis**, non par catégorie |
| Empreintes représentatives par groupe | **6** | Les exemples les moins rencontrés/les plus anciens sont remplacés |
| Octets des empreintes dans les BLOB | **256 Kio** | Une **somme de BLOB**, pas le disque total consommé |
| Comparaisons exhaustives par observation | **4 096** | Si le nombre de candidats dépasse, **refus de conclure** |
| Rétention sans nouvelle rencontre | **180 jours** | Supprime le groupe et ses variantes expirées |

Toutes ces valeurs sont modifiables par `MultiviewLimits` et validées pour éviter des plafonds incohérents. Le nombre d'empreintes n'a **aucun rapport direct** avec une précision fiable d'identification. Une forme de peluche vue sous un nouvel angle peut produire une empreinte trop différente ; le regroupement « même objet » n'est pas automatique dans cet état.

Le champ `sqlite_allocated_pages_bytes` aide à observer les pages **allouées par le fichier SQLite principal** sur le runner, mais ne comprend pas une éventuelle WAL, les autres fichiers de robot, l'espace disque libre, ni la RAM réelle de Linux. Aucune limite du fichier SQLite entier n'est imposée dans M1-B pour ne pas perturber les autres mémoires. L'audit du montage `/var/lib/robot` reste obligatoire (F6-D).

## 4. Preuves exécutées

### Tests locaux et coûts sur GitHub Actions

La [CI Python M1-B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40302369729) a exécuté **922 tests Python**, **4 Rust**, et deux processus indépendants utilisant la même SQLite de test. Le banc de charge `--host-scaling` sur **512 images fictives sans parenté** a relevé sur runner Linux :

| Mesure hôte | Résultat |
| --- | ---: |
| Observations traitées | 512 |
| Groupes et signatures retenus | 512 et 512 |
| Octets de BLOB de signatures | **32 768 octets** |
| Pages allouées SQLite principal (exclut WAL) | **204 800 octets** |
| Temps de cycle complet de cette fixture, médiane | **1,738 ms** |
| Temps de cycle maximal sur cet essai | **4,947 ms** |

Ces durées **incluent Python et SQLite** sur le runner CI, pas une caméra réelle, détection d'objets, compression JPEG ou accélération NPU. Une seule passe ne suffit pas à déterminer un p95 stable et ne peut pas être transposée au RK3566.

### Petit banc indépendant sur photos et sons réels déclarés CC0

Le banc facultatif `m1b_public_media_eval.py --public-cc0` télécharge **uniquement** six photographies Wikimedia Commons du catalogue F3-B déjà documenté, plus deux sons ambiants déclarés CC0. Les JPEG et OGG sont décodés **en mémoire uniquement** avec Pillow 11.3.0 et `imageio-ffmpeg` 0.6.0 sur hôte. Les fichiers ne sont ni commités, ni insérés en SQLite, ni transmis à un autre service.

Sources visuelles (six auteurs distincts, liste historique CC0 à revérifier) : [Cat_looking.jpg](https://commons.wikimedia.org/wiki/File:Cat_looking.jpg), [Cute_cat_2024.jpg](https://commons.wikimedia.org/wiki/File:Cute_cat_2024.jpg), [Dog_in_forest.jpg](https://commons.wikimedia.org/wiki/File:Dog_in_forest.jpg), [My_cute_dog.jpg](https://commons.wikimedia.org/wiki/File:My_cute_dog.jpg), [Flower_photo_normal.jpg](https://commons.wikimedia.org/wiki/File:Flower_photo_normal.jpg), [Bird_image.jpg](https://commons.wikimedia.org/wiki/File:Bird_image.jpg).

Sources sonores : [Door knocker audio.ogg](https://commons.wikimedia.org/wiki/File:Door_knocker_audio.ogg) (Mx. Granger, CC0), [Sound Effect - Door Bell.ogg](https://commons.wikimedia.org/wiki/File:Sound_Effect_-_Door_Bell.ogg) (Amada44, CC0) ; deux **enregistrements de sons d'environnement, sans parole volontairement choisie**. Vérifier licence et métadonnées des pages avant toute réutilisation de ce corpus.

Résultats effectivement obtenus dans [l'exécution CC0 #40302657292](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40302657292) :

| Contrôle à seuils M1-A **figés** | Correspondances observées |
| --- | ---: |
| Même fichier image, luminosité augmentée | **6/6** |
| Même fichier image, **rotation de 12°** | **0/6** |
| Même fichier image, **recadrage de 3 pixels** | **0/6** |
| Même fichier audio, gain modifié | **2/2** |
| Même fichier audio, décalage temporel de **16 ms** | **1/2** |
| Rapprochements automatiques entre photographies de fichiers distincts (indicateur partiel de fausse fusion) | **0** |
| Rapprochements automatiques entre les deux enregistrements audio distincts | **0** |

**Interprétation :** les changements triviaux de luminosité/gain sont supportés sur ce minuscule corpus ; les rotations/recadrages échouent et l'alignement temporel sonore est fragile. Les échantillons visuels distincts **ne sont pas des vues du même objet** : l'absence de fausse fusion ne prouve ni précision ni capacité à reconnaître plusieurs angles. Les deux sources sonores sont distinctes, et le petit effectif ne mesure pas le comportement dans la maison. **Aucune valeur de confiance ou d'identité individuelle n'est validée**, malgré les noms de catégories de la fixture. Les pages de droits sont des déclarations publiques, non une garantie juridique indépendante.

## 5. Reproduction et limites

```bash
python -m unittest discover -s tests -v
python -m microduck_companion.m1b_multiview_demo --database /tmp/m1b-fixture.sqlite3 --session first
python -m microduck_companion.m1b_multiview_demo --database /tmp/m1b-fixture.sqlite3 --session second
python -m microduck_companion.m1b_multiview_demo --host-scaling

# Seulement avec accès Internet volontaire et droit d'utiliser des médias CC0 :
python -m pip install pillow==11.3.0 imageio-ffmpeg==0.6.0
python -m microduck_companion.m1b_public_media_eval --public-cc0
```

Le **mode normal n'effectue aucun accès Internet**. Le workflow [`m1b-cc0-media-study.yml`](../.github/workflows/m1b-cc0-media-study.yml) exécute le banc indépendant dans GitHub Actions, avec accès public explicite. Les tests de non-régression simulent les réponses réseau pour éviter de dépendre de Commons ; une indisponibilité du corpus public doit apparaître comme un échec **du banc externe**, jamais comme une précision inventée.

**Non réalisé :** véritable reconnaissance multi-angle d'un objet ; embeddings appris calibrés, intégration `mediad`/`tofd`, détection locale fiable de parole, mémoire globale du robot plafonnée, mémoire non volatile vérifiée, latences/RAM/thermie/énergie du RK3566, Qwen/Ollama réel ou déplacement. **Aucune donnée de Malo, Kitty, Nessquick ni média privé ne figure dans GitHub.**

## 6. Décision : maintenir un prototype, comparer de petits embeddings ensuite

**M1-B n'est pas un système d'identification.** L'analyse montre que multiplier les empreintes artisanales et élever les quotas peut stocker plus de motifs, **sans résoudre la robustesse visuelle ou acoustique**. La priorité suivante est de comparer des embeddings de petite taille et les représentations M1-B à **jeu de données autorisé et séparé par source**, mesurer rappels, faux rapprochements, refus `unknown`, latence et RAM hôte, puis seulement considérer une intégration sur matériel. L'appareil doit pouvoir rester autonome sans PC, mais cette phase ne le valide pas.
