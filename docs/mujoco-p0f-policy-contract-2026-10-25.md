# P0f — Audit passif des contrats ONNX et variantes de modèle (25 octobre 2026)

**Statut : codé et testé sur les fichiers officiels épinglés.** [207 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419766) et [smoke test MuJoCo headless officiel réussi](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419709). L'audit n'a émis **aucune commande motrice depuis Microduck Companion**. Il est réalisé au sein du simulateur officiel lancé par `duck-sim`, mais l'inférence ONNX décrite ci-dessous est effectuée dans **des sessions CPU indépendantes**, sur entrées **synthétiques** ; elle ne reconstitue **pas** les observations, sorties brutes ou séquences réelles de `robotd`.

## Provenance et frontière de confiance

- Notre dépôt : [PR #16](https://github.com/Jean-Philippe56520/Microduck/pull/16) ; révision constructeur `microduck` **`942e58e3aa6dbb28e7037203fff11866122c7567`**, simulateur `microduck_rl` **`b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`**. Les deux sous-modules sont vérifiés propres et épinglés. La scène `scene.xml` est vérifiée contre son blob Git ; le processus `body_server` OEM est identifié et intact.
- Le fichier **généré par `duck-sim`**, `robotd.toml`, nomme les modèles `alpha_walking.onnx` et `alpha_stand.onnx`. L'audit refuse les chemins externes au jeu de politiques du simulateur et les réglages surchargés (gain, échelle d'action et filtres).
- Le jeu de fichiers fournit un enregistrement `.source` : `pollen-robotics/microduck-policies`, **version `v8`**. C'est une **déclaration de provenance locale non signée**, et **pas** une vérification cryptographique de l'origine Hugging Face. En revanche les empreintes SHA-256 permettent d'identifier sans ambiguïté **les octets testés**.
- Le contrôle du modèle est réalisé par l'ONNX Runtime CPU déjà présent dans `.venv` pour la simulation, sans modifier les fichiers, les paramètres de `robotd` ni les commandes. Le code rejette les dimensions ONNX, les tableaux et les données non finies ou incohérentes.

## Modèles ONNX effectivement chargés pour l'audit

| Modèle cité dans `robotd.toml` | Taille fichier | Entrée / sortie | Type | Empreinte SHA-256 |
| --- | ---: | --- | --- | --- |
| `alpha_walking.onnx` | 793 705 octets | `obs [1,61]` / `actions [1,14]` | Feed-forward, **non récurrent** | `e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c` |
| `alpha_stand.onnx` | 793 705 octets | `obs [1,61]` / `actions [1,14]` | Feed-forward, **non récurrent** | `1569268713e40deea795dd2922dba50d3621e15a872855408b6b1b125b1c094b` |

La compatibilité de forme et le type float32 de ces deux fichiers **sont vérifiés**. Le contrôleur OEM accepte aussi des modèles récurrents LSTM conformes au contrat, mais **ces deux modèles v8 chargés lors du test n'en sont pas**. L'absence d'état LSTM ne donne pas accès pour autant à l'historique d'actions brutes que `robotd` place dans son observation.

### Inférence indépendante et volontairement synthétique

Deux entrées sont envoyées au réseau `alpha_walking.onnx` **dans une session ORT créée séparément** : gyro nul ; gravité projetée `[0,0,-1]` ; position relative au HOME nulle ; vitesse articulaire nulle ; historique d'actions nul ; tête et pose du corps sans commande. Seule la vitesse `vx` passe de **0** à **0,12 m/s**.

- La sortie `actions` contient bien **14 valeurs finies** dans les deux cas, sans appel à `robotd`.
- La différence entre sorties brutes synthétiques vaut **0,1471178 en norme L2**. Le réseau chargé réagit donc à l'entrée `vx` de cet exemple. L'angle d'une articulation ou une distance au sol **ne peut pas** être déduit de cette différence.
- Le modèle debout a également répondu avec **14 actions finies** à l'observation neutre (vitesse nulle). Les sorties individuelles figurent dans `policy-contract.json`, pas dans cette conclusion.
- **Aucune identité temporelle** avec les anciennes consignes de `robotd` et **aucun** essai en boucle fermée n'ont été démontrés. Ne pas présenter les sorties synthétiques comme des mesures du robot en marche.

## Contrat observations/actions confronté au code OEM

| Bloc dans l'observation de `robotd` | Indices |
| --- | --- |
| Vitesse angulaire tronc | `[0:3]` |
| Gravité projetée | `[3:6]` |
| 14 angles **relatifs à HOME**, bouche exclue | `[6:20]` |
| 14 vitesses articulaires | `[20:34]` |
| 14 **actions brutes précédentes**, avant mise à l'échelle | `[34:48]` |
| Twist demandé (vx, vy, yaw) | `[48:51]` |
| Cible tête | `[51:55]` |
| Cible corps | `[55:61]` |

- **Pose HOME : différence maximale 0 rad** entre les 14 références explicitement définies dans `duck-control/src/model.rs` et `microduck_constants.py` du simulateur/entraînement épinglé. Cela exclut une différence dans **ces constantes**, pas les décalages réels liés aux capteurs, à la mécanique ou à la posture.
- **Sorties :** `robotd` applique aux 14 valeurs de politique `cible = HOME + scale × action`, avec la bouche absente de l'ONNX. Valeurs par défaut de configuration constructeur : `action_scale=0.9` (marche), `standing_action_scale=1.0`, filtres première-ordre des jambes `0.7` et de la tête `0.5` (poids de la nouvelle cible), gain 200 et ratio debout 0,8.
- La configuration RL de vitesse contient une échelle d'action `joint_pos_action.scale=1.0`. **Comparer directement 1.0 et 0.9 est insuffisant pour conclure à un défaut** : l'action du modèle et le pipeline de filtrage ainsi que les conditions d'entraînement/d'export doivent être confrontés selon la **version exacte du réseau**.

## Différence réelle d'inventaire géométrique XML

| Variante de modèle OEM épinglée | Usage d'après la configuration source | Total balises `<geom>` | Balises `<geom class="collision">` explicites |
| --- | --- | ---: | ---: |
| `robot_walk.xml` | Entraînement de tâche de vitesse (configuration `MICRODUCK_WALK_ROBOT_CFG`) | **85** | **2** |
| `robot_allcollisions.xml` | Tâche d'entraînement VelStand (`MICRODUCK_ALLCOLLISIONS_ROBOT_CFG`) | **150** | **69** |
| `robot_groundcontact.xml` | Scène headless `scene.xml` utilisée par `duck-sim` | **91** | **10** |

Les **deux semelles sont explicitement nommées dans les trois fichiers**. Ce comptage porte uniquement sur les balises déclarées, et **non** sur les contacts actifs, le nombre de collisions réellement résolues, ni la physique résultante compilée. Les classes par défaut, `contype`/`conaffinity`, et les paramètres de friction doivent être étudiés avant toute hypothèse causale. **De plus, les fichiers d'entraînement sources ne prouvent pas quelle variante exacte a généré chaque poids ONNX v8** ; le modèle `alpha_walking.onnx` doit être relié à son manifeste / processus d'export pour l'affirmer.

## Ce que P0f n'a pas fait

- Pas de nouvelle commande `robot.move`, pas d'essai de marche J2e. `duck-sim up` a lancé ses services et son mécanisme constructeur de maintien debout habituel. Le fait d'avoir vérifié ONNX et la provenance ne valide **pas** la locomotion.
- Pas de lecture **au même tick** du vrai tableau `[1,61]` passé à l'ONNX de `robotd`, de sa vraie sortie brute à 14 valeurs, des actions historiques ou de l'état du filtre. L'API `body_server.op=read` ne fournit pas ces données ; il faudrait un diagnostic constructeur en lecture seule correctement borné ou une comparaison d'exécutions de contrôle isolées.
- Pas de changement du code ni des seuils, gains, politiques, modèles, collision/friction, versions, limites de sécurité constructeur. Pas de robot physique.
- Les essais précédents restent distincts : P0e a mesuré **2,295 mm** de translation nette finale, et P0d les deux pieds sous charge. **P0f n'a pas produit de nouvelle mesure de marche.**

## Décision et prochaine étape

**Le contrat de dimensions est bon, la pose de référence statique concorde, et les modèles CPU donnent des sorties finies pour les observations synthétiques.** La différence des modèles de géométrie est documentée ; **son influence sur la locomotion n'est pas encore établie**, et P1a reste bloqué.

**P0g proposé :** analyser dans un MuJoCo **indépendant et hors ligne**, à pose et contrôle identiques, les paramètres de contact compilés des modèles `robot_walk`, `robot_groundcontact` et `robot_allcollisions` ainsi que leurs effets sur les candidats de contact au repos. Vérifier la provenance de l'export ONNX v8 avant d'attribuer la différence d'entraînement à ce réseau. N'autoriser une comparaison motrice en simulation qu'après définition d'un protocole sûr, sans changer les sources OEM. P2 (autonomie multi-cycle et SQLite) peut avancer en parallèle.

**Archive du workflow** : [GitHub Actions #40200419709](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40200419709), fichier `policy-contract.json` et logs du simulateur. Les SHA-256 identifient les fichiers testés mais ne sont pas une signature de l'éditeur.

