# M1-B — Mémoire de motifs multi-vues, capacité configurable et premier banc public CC0

**26 octobre 2026 — [PR #50](https://github.com/Jean-Philippe56520/Microduck/pull/50), chantier expérimental logiciel.** Pas de Microduck physique, aucune prise de vue ni écoute réelle, aucune identification individuelle, aucun appel à Qwen. Le code M1-A reste la référence historique ; le nouveau stockage M1-B n'est pas automatiquement déployé ni branché aux services constructeur.

## 1. Pourquoi sortir du plafond de 256 empreintes ?

M1-A contenait un défaut de quota : le comptage utilisé avant insertion ne portait que sur la modalité consultée. **256 images suivies d'un son pouvaient créer 257 entrées**. La correction M1-B compte désormais **toutes les lignes image et audio dans la même transaction** puis évince l'empreinte la plus ancienne si nécessaire. Le test de régression remplit les 256 entrées avant d'insérer un son et vérifie que **255 images + 1 son = 256**.

Il faut surtout distinguer **un souvenir d'un objet/son familier** de ses **empreintes représentatives**. En réalité, plusieurs vues et acoustiques pourraient être reliées à un même souvenir, à condition d'en avoir la preuve. Dans ce prototype, le rapprochement automatique ne porte que sur des caractéristiques proches ; une deuxième vue très différente ne peut être liée **qu'au moyen d'un identifiant de groupe de fixture déclaré explicitement**, pas d'une décision inventée par le modèle.

## 2. Nouveau noyau `MultiviewPatternMemory` (experimental, sans capteurs)

`microduck_companion/multiview_pattern_memory.py` crée deux tables SQLite **sur la connexion `ExperienceMemory.conn` existante** :

- `m1b_groups` : modalité, catégorie de fixture non vérifiée, compteur de rencontres et dates ;
- `m1b_signatures` : plusieurs signatures par groupe, toujours **64 octets pour une image** ou **16 pour un son** dans le protocole synthétique courant, compteurs et date par signature.

La méthode de comparaison reste la formule M1-A : somme de différences absolues sur les octets, exprimée comme une **similarité arbitraire**, **pas une probabilité de reconnaissance**. Seuils fixes 0,94 image et 0,93 audio, sans apprentissage. Deux groupes de scores quasi égaux sont **ambigus**, les catégories de fixtures contradictoires le restent. Un seuil de nombre de comparaisons impose le résultat `search_budget_exhausted` si toutes les signatures pertinentes ne peuvent pas être examinées : **on préfère « inconnu » à un rapprochement incomplet**.

**Exemples de limites configurables du banc hôte, et non marges robot mesurées :**

| Paramètre M1-B | Valeur initiale de test |
| --- | ---: |
| Nombre de groupes (souvenirs) | 1 024 |
| Nombre de signatures visuelles et sonores ensemble | 4 096 |
| Nombre de variantes dans un groupe | 6 |
| Somme des champs d'empreintes | 256 Kio |
| Comparaisons maximales sur une requête | 4 096 |
| Rétention sans rencontre | 180 jours |

L'éviction s'applique **à toutes les modalités** en fonction de la récence ; les groupes sans empreinte sont supprimés. Un groupe peut conserver ses autres vues lorsqu'une variante peu utile est remplacée. Un lien entre deux vues est soumis à `synthetic_same_source_claim=True` et au groupe explicite : **ce drapeau n'est ni un consentement d'une personne ni une preuve de même objet physique**. M1-A n'est **pas automatiquement migré**, pour éviter une fusion injustifiée des observations anciennes. Lors d'une réouverture de SQLite avec des **quotas plus stricts**, M1-B retire les anciennes signatures/groupes qui dépasseraient ces nouveaux plafonds, avec un test de non-régression dédié.

Le budget de 256 Kio ne porte que sur les **BLOB d'empreintes**, pas sur le fichier SQLite, les tables d'épisodes, les index, les pages libres, ni le journal WAL éventuel. Une démonstration en hôte Linux a mesuré **80 octets de signatures mais 57 344 octets de pages SQLite** pour une base très petite ; elle ne mesure pas la place libre de la partition persistante du robot.

## 3. Données réelles publiques : premier diagnostic, pas une réussite de reconnaissance

Un **banc facultatif** `m1b_public_media_eval.py --public-cc0` télécharge uniquement des médias publiquement déclarés **CC0** sur Wikimedia Commons, les décode en mémoire, n'enregistre aucune photo ou forme d'onde dans SQLite, et produit des métriques agrégées. Le benchmark utilisé en CI porte sur :

- **6 photographies distinctes** du catalogue F3-B en validation (2 chats, 2 chiens, 1 fleur, 1 oiseau), prises par des personnes différentes, mais **pas des clichés sous différents angles du même animal ou du même objet** ;
- **2 enregistrements sonores environnementaux** distincts, [heurtoir de porte, Mx. Granger](https://commons.wikimedia.org/wiki/File:Door_knocker_audio.ogg) et [sonnette, Amada44](https://commons.wikimedia.org/wiki/File:Sound_Effect_-_Door_Bell.ogg), déclarés CC0 sur leurs pages. Aucune voix ni conversation enregistrée pour notre projet.

La source est vérifiée via HTTPS hôte Wikimedia autorisé et limites de tailles, puis les pixels JPEG sont convertis à 32×32 en RAM, les OGG en 8 kHz mono PCM via un décodeur local sur PC. **La licence déclarée et l'étiquette restent à recontrôler pour chaque réutilisation**, ce n'est pas une attestation juridique. En cas d'indisponibilité d'un fichier ou décodeur, le benchmark **échoue**, ne présente pas de chiffres partiels comme s'ils étaient complets.

**Résultats effectivement obtenus sur [GitHub Actions CI #40302657292](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40302657292), seuils M1-A inchangés :**

| Épreuve | Réussites / cas |
| --- | ---: |
| Même photo, luminosité seulement modifiée | **6/6** |
| Même photo, rotation de 12° | **0/6** |
| Même photo, crop de 3 pixels | **0/6** |
| Même enregistrement, volume réduit | **2/2** |
| Même enregistrement, retard de 16 ms | **1/2** |
| Rapprochement automatique de deux photos distinctes | **0 sur 6 nouveaux fichiers** |
| Rapprochement automatique de deux sons différents | **0 sur 2 nouveaux fichiers** |

Les deux dernières lignes sont des **proxies de fusion** avec des fichiers distincts : aucune vérité terrain de « même individu » ou de « même objet physique » n'a été établie ; il serait donc incorrect d'appeler ces résultats « précision » ou « taux de faux positifs » sur la maison.

**Conclusion empirique :** des variantes triviales de lumière et volume sont correctement rapprochées dans cette très petite étude, mais **la méthode échoue entièrement aux rotations et recadrages ici** ; la variation temporelle audio provoque également un oubli. Un nombre de signatures plus grand ne résout pas ce défaut d'**invariance**. Le portage d'un petit modèle d'embeddings visuels et acoustiques, optimisé seulement après mesures matérielles, est à étudier et comparer contre cette base. Les essais publics doivent couvrir ultérieurement différentes prises de vue réelles du même objet, davantage de sons indépendants, des ambiances bruyantes, le rejet `unknown`, et les faux rapprochements, avec séparation stricte des jeux et seuils calibrés hors test.

## 4. Mesure CPU/stockage hôte sur données artificielles

[`m1b_multiview_demo.py --host-scaling` en CI #40303522130](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40303522130) a fait **512 tentatives** de comparaison/écriture sur des pixels synthétiques aléatoires avec **512 groupes et 512 signatures**. Une exécution sur l'hôte CI a donné un temps médian de cycle Python + SQLite **1,845 ms**, un maximum **5,266 ms**, **32 768 octets d'empreintes BLOB** et **204 800 octets de pages SQLite** sans compter un éventuel WAL. Ces données ne mesurent ni NPU ni caméra, ni le CPU/RSS réel sous charge des services, ni la température, ni le risque pour la boucle moteur 50 Hz sur RK3566.

Les métriques de charge croissent avec le nombre de signatures examinées ; avant de porter le moteur de comparaison, il faudra une politique de rappel restreinte (pré-filtrage par catégorie, index approximatif robuste ou petits embeddings) et une mesure des erreurs d'un tel filtrage. Tant qu'on ne peut pas inspecter correctement le corpus, le programme **refuse de conclure** au lieu de sauter arbitrairement des signatures.

## 5. Confidentialité et sécurité

Ce lot traite **des fichiers publics CC0 et des fixtures artificielles uniquement**, jamais les médias des animaux ou personnes du foyer. Il refuse l'enregistrement d'empreintes étiquetées `person` et `speech` dans la simulation, mais **ne sait pas détecter une personne/parole si la catégorie `unknown` masque ces contenus** ; les vrais capteurs ne doivent donc pas être branchés directement. Les empreintes elles-mêmes peuvent encore porter de l'information sensible et nécessitent un stockage privé et une suppression/revue adaptées.

Aucun service OEM, Qwen/Ollama réel, transmission d'image/voix privée, commande moteur ou haut-parleur n'est activé. Le robot physique est indisponible ; pas de validation mémoire, fréquence, thermique, batterie ou qualité de reconnaissance sur son matériel. La consultation PC reste un **indice non exécuté**, avec quota et consentement séparés du chantier F5.

## 6. Suites et critères d'arrêt

La dernière [CI Python M1-B](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40303522130) valide **925 tests Python** et **4 tests Rust**. Ces tests comprennent le cas d'une réouverture avec des plafonds abaissés ; ils ne prouvent aucune performance sur le RK3566.

**M1-B prouve sur hôte uniquement :** corrigé 256 global de M1-A, groupes multi-empreintes de fixtures avec limites paramétrables et eviction, détection prudente des ambiguïtés, données publiques CC0 disponibles et erreurs mesurées, tests Python, deux processus et un stress de 512 cycles artificiels. **M1-B ne prouve pas :** identification d'objets réels dans de nouvelles vues, reconnaissance d'un animal ou son à travers le bruit, biométrie, fonctionnement embarqué ou absence de saturation du stockage système.

**Prochaine étape : M1-C (ou sous-lot scientifique M1-B2 selon résultats)** : évaluer des extracteurs d'empreintes **apprises** visuelles et sonores sous licences adaptées et sur des médias publics/consentis plus diversifiés ; comparer qualité, risque de mauvais rapprochement, volume et CPU/RSS hôte, puis seulement lancer un vrai banc RK3566 quand le robot sera disponible. Le PC Qwen reste optionnel et sans rôle de commande.
