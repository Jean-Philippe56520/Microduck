# COG-A1-R0 — catalogue initial de references generales candidates

## Qualification finale apres fusion — 03/11/2026

### COG-A1-U1 — hygiène de relecture (nouveau correctif distinct, conditionnel à sa CI)

Le lecteur A1 avait un défaut de filtrage de caractères : son prédicat rejetait les codes ASCII de contrôle, mais laissait passer des commandes visuelles Unicode (direction, largeur nulle, séparation invisible) et un substitut isolé. Risque : masquer ou rendre trompeur le texte de connaissances *candidates pour la relecture humaine*, jamais créer un fait ou autoriser un skill. **Réutiliser** le parser actuel et ses limites de 16 KiB/32 règles ; **adapter uniquement** `_text` avec `str.isprintable()` (les accents français imprimables restent admis) ; **tester** cinq caractères refusés sur quatre champs, plus l'existant. Aucun ajout de modèle, de signification automatique, de nouvelle SQLite ou de commande. La PR de correctif devra réussir ses contrôles propres ; la fusion historique #287 reste qualifiée à son SHA. Critère STOP : échec CI, rejet de français lisible, changement du périmètre moteur/packaging ; aucune prétention de gain cognitif A2.

La [PR #287](https://github.com/Jean-Philippe56520/Microduck/pull/287) a ete **fusionnee** apres 9/9 CI `success` sur le HEAD `99d3187eba149803f81f3d3a86f961cb9cc955cc`, squash `3eea4fc88c3e65e6dd0f416a216aa7ef492b9e7f`. Les PR parentes #285/#286 sont egalement fusionnees avec 9/9 CI. Le workflow N1 a construit le **wheel Python normal du depot** et compare exactement les octets du JSON embarque a ceux de la source ; la CI Python complete est verte. Les tests unitaires de provenance recus en revue exigent l'URL **integralement exacte** de la cheatsheet OEM au SHA epingle (mauvais chemin, suffixes, autre SHA rejetes). La table de qualification et les phrases temporelles ci-dessous conservent l'etat **historique avant fusion**, sans requalifier les tests de maquette en validation robot.

**Statut livre :** lecteur `initial_knowledge.py`, huit references `candidate_for_operator_review`, JSON version 1 conditionnel et lecture seule ; six relations indexables par le vocabulaire F1, deux hors F1 (`chair`, `cloth`). Aucun F1 authentifie ne mesure pour autant leur usage physique : **0/8 proprietes/effets physiques verifiables via le seul contrat F1**, resultat de couverture d'API et non precision de modele. Pas de couplage F2/ExperienceMemory, moteur `robotd`, Qwen, nouveau modele, NPU, robot, distribution B11 ou fin OEM. **COG-A2 EN ATTENTE** de scenes independantes avec propriete verifiable, temoin complet F2/DET-1 + mock_social_cues + category_inspection + memoire, 4 positifs et 8 negatifs preregistrés. Ni `play_cue` ni inspection de contour ne constituent une nouvelle capacite A1 ; STOP si absence de gain mesurable. Aucun changement de seuil ou de scripts sensoriels pour faire passer un essai.

---

**03/11/2026 — premier lot fonctionnel *de lecture*, sans integrer les decisions F2.** Autorite : [plan d'action](plan-action.md) (COG-BASE-0, PR #285) et [audit COG-A0](cog-a0-reuse-knowledge-oem-matrix-2026-11-03.md) (PR #286). Cette PR A1 est volontairement issue de la branche d'audit tant que les PR #285/#286 ne sont pas fusionnees. Leur ordre et la revue du corpus restent une condition avant fusion d'A1.

## 1. Besoin, preuve, hypothese et arret predefini

**Besoin prouve par lecture du code :** `CategorySemantics` ne contient que les categories historiques F4-A et des hypotheses de propriete fictives, `memory_consolidation.py` n'est qu'un rappel conservateur et F2 ne possede pas de corpus general sourcé, versionne et expurge. L'objectif A1-R0 est de rendre disponibles de telles **propositions conditionnelles candidates** sans polluer la SQLite des experiences ni demander Qwen. **Ce lot n'ameliore pas encore le choix des intentions F2** : cette ablation relevera d'A1-R1/A2 et restera arretee si aucun gain mesure n'existe.

**Hypothese testable :** quelques references statiques avec conditions, contre-exemples et provenance lisibles sont extensibles par modification de donnees uniquement et ne peuvent pas se faire passer pour une observation, une politique motrice chargee, un effet OEM ou un souvenir vecu. **Temoin :** F2 de `main` inchange, qui ne connait pas ces references et produit donc toujours ses memes `PassiveIntent`. **Succès du premier lot :** references candidates recuperables sur une classe F1 deja admise, ajout d'une proposition sans modification de Python, rejet des fausses sources/skills/autorisations et distribution effective du JSON dans le wheel, sans nouvelle connexion SQLite, action OEM ou dependance PC. **STOP :** des donnees non bornees, lien implicite vers une categorie hors F1, permission motrice, collision avec les tests N1/N3 ou la compilation, ressources embarquees non qualifiees ou echec CI. **Retour arriere :** retirer uniquement module, JSON, tests et declaration `package-data` de cette PR.

## 2. Reutiliser / adapter / creer

| Controle | Choix | Raison |
| --- | --- | --- |
| `ExperienceMemory` et toutes ses tables F0/F1/F4/EX | **Ne pas modifier** | Les references sont des connaissances generales candidates, pas des experiences ou des observations. |
| `passive_observations.OBJECT_CATEGORIES` | **Reutiliser strictement** | `for_f1_label` ne renvoie rien pour `unknown`, `other_object`, `chair` ou `cloth`. Les deux derniers concepts ne sont visibles que comme references consultables, jamais comme detection F1. |
| `AutonomyBrain`, F2/DET-1 et `robotd` | **Ne pas modifier** | Aucun rappel de reference ne choisit, programme ou ordonne une action. Une etiquette `person` n'etablit pas qu'un humain est physiquement present. |
| `microduck_companion/initial_knowledge.py` | **Creer : lecteur pur minimal** | JSON strict, limites d'octets/listes/textes, provenance, anti-double cle, controle pin OEM et whitelist de noms documentaires. |
| `initial_knowledge_v1.json` | **Creer : brouillon versionne** | Huit references candidates pour ball/toy/cloth/chair/person/cat/dog ; aucune n'est declaree approuvee, observee, cause ou execution. |
| `pyproject.toml` | **Adapter minimalement** | Inclure seulement ce JSON dans le package Python normal via setuptools package-data. Les 20 modules publics N5 restent sur leur allowlist historique, sans dependance vers A1. |
| Qwen, MuJoCo, RKNN, ONNX, WIC B11, gitlinks OEM | **Ne rien changer** | Aucun besoin pour lire ou valider ce corpus. |

**Sources des candidates :** brouillon editorial humain/GPT-6 du 03/11 (source `author_draft`) et [cheatsheet du constructeur epingle](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/docs/robot/cheatsheet.md) pour les seuls liens OEM. **La revue humaine d'acceptation semantique de chaque phrase demeure requise** ; ce lot ne transforme pas la chaine `pinned_oem_documentation` en preuve que le skill est effectivement charge. Les noms OEM sont des liens documentaires, aucun appel `robot.do` ou `robot.policies` n'est effectue.

## 3. Bornes de donnees et controle

- Entrée : `bytes` JSON de **16 384 octets max**, une seule version de schema `1`, statut global `candidate_for_operator_review` uniquement ; champs exactement attendus, doublons de cles/propositions rejetes.
- Maximum 8 sources, 32 propositions, 6 conditions ou contre-exemples par proposition, texte borne, proprietes parmi `property/possible_use/limitation`.
- Aucun champ `verified`, `executed`, `can_authorize_actions` ou ordre moteur admis ; proprietes d'instance `physical_observation_verified`, `skill_loaded_verified`, `motor_action_authorized`, `causality_established` constantes **False**.
- Un nom `oem_skill_reference` n'est admis que si lie a **l'URL complete et exacte du seul document OEM relu** (`docs/robot/cheatsheet.md` au SHA epingle), sans accepter un autre chemin sur le meme commit, un suffixe ou une variante de requete, et a l'un des quatre noms de la premiere tranche : `kick_left/kick_right/ground_pick/sit_toggle`. Aucun de ces noms ne constitue un `robotctl policy list` verifie sur robot.
- Lectures par `importlib.resources`, sans reseau, camera, SQLite, modele, tache de fond, commande moteur ni traitement d'image. L'extension ajoute simplement une ligne candidate JSON, **pas du code moteur**.

## 4. Tests pre-enregistres avant execution et limites

**Positifs A1-R0 :** (P0) 8 references lisibles avec etats fictifs non autorisants ; (P1) deux candidats `ball`, dont un lien vers `kick_left` sans execution ; (P2) `chair/cloth` consultables comme references generales mais non mappes depuis F1 ; (P3) l'ajout d'une reference `ball` dans le JSON augmente son rappel sans changer de code Python ; (P4) inclusion effective du JSON dans la roue Python construite sur l'hote.

**Negatifs A1-R0 :** (N0) doublon cle ou ID, source absente, faux pin OEM, skill invente ; (N1) champ `verified/executed` injecte ; (N2) version/schema/statut non approuve, depassement des limites, valeurs JSON non finies ; (N3) tentative de mapper `unknown/other_object/chaise/cloth` en presence reelle ; (N4) source OEM supprimee pour un skill, refus ; (N5) aucune dependance SQLite, `robot.do` ou Ollama dans le lecteur. **Criteres de passage preregles avant execution :** 100 % des checks de parser ci-dessus et compilation Python, wheel avec JSON, zero effet moteur et pas de changement des tests existants en CI. La CI N1/N3 et les scripts de packaging existants font foi pour les regressions, pas seulement les tests cibles.

**Correction de revue P2 :** une URL de commit OEM epingle suivie d'un chemin different ne prouve pas que ce document a ete audite ; le lecteur exige desormais l'**egalite exacte** avec la cheatsheet source. Test negatif supplementaire : mauvais chemin, suffixe, fragment, requete et autre SHA, tous rejetes. Cette modification est candidate dans la PR, sa CI sur le nouveau SHA reste a verifier.

**Contrôle P4 ajouté en CI N1 :** vérifier le wheel **normal construit depuis le dépôt complet** en comparant, octet par octet, le JSON embarqué et sa source sur le commit PR (membre absent, doublé ou différent → échec). Ce contrôle est programmé, **pas encore validé au SHA corrigé** ; il ne qualifie pas le wheel N5 embarqué ni la consommation RK3566.

**Resultat initial sur environnement isole au moment de la preparation :** 11/11 nouveaux tests unittests reussis sur Python hote en utilisant une **copie minimale et explicite du vocabulaire F1**, non une execution du checkout GitHub entier (acces GitHub direct absent du shell local). Un wheel de cette maquette minimale a ete construit et contient `initial_knowledge_v1.json` ; **cela ne qualifie pas le packaging integral du depot**. Les CI sur le commit de PR, lorsqu'elles seront terminees, prouveront uniquement l'execution sur runner PC, ni la cognition A2, ni la ressource RK3566.

**Important :** les criteres d'A0 pour la recombinaison (quatre positifs P1-P4 et huit negatifs N1-N8 avec/sans memoire) **ne sont pas satisfaits par ce simple catalogue**. Ne pas les requalifier a posteriori, ne pas compter ces tests de parser comme gain cognitif et ne pas fusionner A1 au motif qu'une reference `ball` a ete lue correctement. Avant A2 : nouvelles situations independantes, comparaison aveugle F2 seul / F2 enrichi, source et contexte authentifies, abstentions et fausses certitudes quantifiees.

## 5. Qualification explicite

| Etat | Niveau |
| --- | --- |
| Format JSON, validateur, regles candidates | Code candidat en PR, pas une competence robot |
| Tests de validation et wheel minimal | Testes **PC-maquette**, non sur checkout complet |
| Integration F2, re-evaluation des motivations ou effets | **Non codes** |
| Comparaison prospective avec/sans connaissance et memoire | **Non realisee** |
| Chargement sur RK3566, ressources, skills charges, camera/micro/effet | **Non valides robot**, EN ATTENTE |
| Qwen | Suspendu, pas de dependance A1 |

**Prochain pas conditionnel :** apres revue du brouillon et CI complete, tester l'utilite de ces references sur F2 sans leur donner d'autorite sur les capteurs ni sur `robotd`. Si aucune difference utile n'apparait vs F2, **STOP** plutot que d'etendre le corpus arbitrairement.
