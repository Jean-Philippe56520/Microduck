# F3-A — Contrat de données visuelles et protocole d'évaluation

**25 octobre 2026 — [PR #32](https://github.com/Jean-Philippe56520/Microduck/pull/32), en revue.** F3-A porte sur **les métadonnées et la méthode d'évaluation**, pas sur un modèle entraîné, ni sur des images réellement vues par le robot. [Plan directeur](plan-action.md).

## 1. Ce qui est effectivement livré

- `microduck_companion/visual_dataset.py` : validation stricte d'un manifeste JSON **v1**, avec 28 **échantillons totalement fictifs** utilisés par le banc F3-A (8 `train`, 8 `validation`, 12 `test`).
- Catégories visuelles bornées et reprises **sans créer de nouvelle identité** depuis `passive_observations.OBJECT_CATEGORIES` : `ball`, `toy`, `dog`, `cat`, `person`, `microduck`, `other_object`, `unknown`. Le label `dog` **ne signifie pas** qu'un animal particulier est reconnu.
- `microduck_companion/visual_dataset_demo.py` : génération de **28 lignes de métadonnées synthétiques**, sans image, caméra, audio ou fichier multimédia. Les empreintes SHA-256 sont dérivées de **jetons fictifs**, **pas du contenu d'images**.
- Évaluation de prédictions déclarées `source=mock_prediction` **sur les 12 échantillons du test** seulement. Une prédiction sous le seuil de confiance existant `DETECTION_CONFIDENCE=0.80` devient `unknown`.
- Refus strict des noms/chemins/URL/champs libres, des JSON ambigus (clés dupliquées, NaN/Inf), d'identifiants mal formés et de manifestes trop volumineux. Taille maximale des métadonnées : 512 Kio, 4 096 lignes. **Aucune image n'est chargée et aucune intention motrice n'est exécutée.**

**Ce n'est ni une détection d'objets (boîtes), ni un classificateur visuel :** le jeu fictif ne contient **pas de pixels**. Ce protocole mono-étiquette doit être étendu par versionnement pour les boîtes englobantes et les métriques IoU/mAP de F3-B.

## 2. Schéma de métadonnées et garanties

Le manifeste accepte exactement `schema_version`, `task=single_label_visual_category`, `samples`. Chaque ligne contient exactement :

| Champ | Rôle | Précaution |
| --- | --- | --- |
| `sample_id` | ID opaque de forme `s-` suivi de 16 hexadécimaux | Aucun nom personnel ni chemin |
| `group_id` | Groupe d'acquisition/séquence/domaine (opaque : `g-` + 16 hexadécimaux) | Tous ses échantillons doivent rester dans **une seule partition** |
| `fingerprint_sha256` | Empreinte 64 caractères hexadécimaux, pour doublons exacts | Dans la fixture : **jeton fictif**, pas une image ; pour de vrais médias le calcul doit rester local et privé |
| `split` | `train`, `validation` ou `test` | Aucune partition vide ; test avec **catégorie connue ET `unknown`** |
| `category` | Une des huit catégories F1 | `unknown` pour cas ambigu, hors classes ou impossible à trancher ; jamais un individu |
| `source_kind` | `synthetic_fixture`, `licensed_external`, `consented_private` | Seule la fixture synthétique est autorisée **par défaut** ; source déclarée ≠ source authentifiée |
| `rights_basis` | `generated_fixture`, `license_reviewed_locally`, `consent_recorded_locally` selon la source | **Déclaration** d'un contrôle externe, pas un certificat juridique |
| `annotation_basis` | `deterministic_fixture` pour synthétique ; `human_reviewed` pour source extérieure | Un outil ne démontre pas qu'une revue humaine a eu lieu |

La voie d'évaluation des prédictions fictives refuse toujours de calculer un « résultat du modèle » pour des données extérieures, même si les métadonnées ont été acceptées via `allow_external=True`.

### Barrières contre la fuite d'information

1. **IDs d'échantillon uniques** : un même échantillon ne peut pas compter plusieurs fois.
2. **Empreintes uniques** : un doublon exact référencé est rejeté entre toutes les partitions, pas seulement entre train et test.
3. **Groupes étanches** : il est interdit de faire passer une acquisition/séquence/animal/maison d'une partition à une autre **si leurs images appartiennent au même groupe identifié**. Les groupes portent des codes opaques et leurs correspondances éventuelles restent localement privées.
4. **Limite de preuve** : des captures voisines, recadrages, séquences visuellement identiques et prises de vues du même individu sous des IDs/groupes distincts ne sont **pas** automatiquement reconnus comme doublons. Un contrôle de quasi-doublons, de série temporelle, de scène, de foyer et de domaine capteur reste indispensable avant toute évaluation sur médias réels.
5. Le jeu `test` doit être **figé avant le choix du modèle et des seuils** ; le jeu `validation` sert aux choix de seuil et hyperparamètres. Le seuil 0,80 utilisé aujourd'hui est emprunté à F1 pour vérifier le comportement de l'évaluateur, **pas calibré pour un futur détecteur**.

## 3. Métriques du banc d'évaluation

Pour chaque prédiction sur le jeu `test`, le rapport donne : matrice de confusion *(vérité × catégorie annoncée)*, précision/rappel/F1 par classe connue, macro-F1 des classes connues effectivement représentées/prédites, rappel de `unknown`, exactitude globale, couverture (part de prédictions non `unknown`), exactitude conditionnelle sur la couverture et nombre de rejets sous le seuil. Une exactitude conditionnelle nulle ou indéfinie est correctement séparée d'une absence de couverture.

**Fixture illustratrice uniquement** (les prédictions ont été inventées par le code de démonstration, sans modèle ni image) :

| Paramètre fictif | Valeur |
| --- | ---: |
| Échantillons entraînement / validation / test | 8 / 8 / 12 |
| Prédictions exactes de la fixture | 9 / 12 |
| Exactitude arithmétique sur la fixture | 75 % |
| Couverture (prédiction différente de `unknown`) | 9 / 12 = 75 % |
| Exactitude parmi les 9 prédictions couvertes | 7 / 9 = 77,8 % |
| Cas réellement annotés `unknown` | 2 |
| Rappel fictif de `unknown` | 2 / 2 |
| Rejets de confiance sur les classes connues | 2 |
| Images ouvertes, caméra réelle, commandes motrices | 0 / 0 / 0 |

**Ces chiffres testent des formules, pas l'aptitude de Microduck à reconnaître quoi que ce soit.** Ils n'ont aucune signification statistique sur chien/chat/personne ; 12 exemples sont insuffisants même pour un benchmark visuel élémentaire. Aucune précision IoU/mAP ou mesure de faux positifs sur de vraies images n'existe encore.

## 4. Préparation des vraies données (avant F3-B)

- **Données de provenance claire** : privilégier d'abord des jeux réutilisables sous licences contrôlées ou des contenus synthétiques ; conserver hors GitHub les détails de droits, licences, autorisations d'utilisation et, le cas échéant, consentements ; un champ `rights_basis` ne les remplace pas.
- **Vie privée** : ni photos/voix du foyer, ni identités ou pseudonymes d'enfants, ni biométrie, ni correspondance entre `group_id` et personnes/animaux, ni empreintes de médias privés dans GitHub. L'identification individuelle de chien/chat/personne appartient à F4, sous consentement et préférence pour l'association volontaire.
- **Acquisition réelle** : toujours distinguer la caméra Zero 3W / IMX219 d'une beta Seeed / GC2093, les jeux externes et les fixtures. Les performances seront mesurées séparément par domaine, lumière, taille apparente, occultation, mouvement et catégories difficiles, avec `unknown` et faux positifs.
- **Annotation future** : pour un détecteur avec boîtes, spécifier et valider la résolution, les boîtes normalisées, la visibilité/occlusion, les situations « aucune cible », l'accord inter-annotateur et les erreurs de localisation ; publier des résultats sur un jeu indépendant avec mAP et métriques par classe. **Le schéma v1 ne stocke pas ces boîtes**, volontairement.
- **Données privées locales** : `datasets/private/`, `datasets/local/` et `.local_visual_data/` sont ajoutés à `.gitignore`. Cela réduit le risque de commit accidentel, sans remplacer la revue des fichiers avant toute publication.

## 5. Tests et reproduction

La suite `tests/test_visual_dataset.py` comprend **32 nouveaux tests** : catégories, structure, divisions, inconnus, doublons, références croisées, tentatives d'insertion de médias/identités, licence/consentement déclaratifs, confiance malformée, prédictions incomplètes ou non fictives, absence de couverture, matrice de confusion et distinction entraînement/test.

```bash
python -m unittest discover -s tests -p test_visual_dataset.py -v
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.visual_dataset_demo
```

**Validation :** [482 tests Python réussis sur la branche F3-A](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40241567760), dont 32 nouveaux. La CI comporte aussi la démonstration F3-A sur **zéro image**. La PR #32 reste à examiner/fusionner ; aucun essai MuJoCo, moteur, caméra, NPU, son, PC/Qwen ou robot physique n'a été effectué.

## 6. Critère de suite

F3-A constitue **une infrastructure de contrôle et un protocole**, pas un détecteur fonctionnel. La **prochaine étape indépendante F3-B**, après validation de la PR #32, sera de choisir des données véritablement utilisables (licences/droits vérifiés), implémenter une première ligne de base *visuelle* légère, établir des boîtes/mesures si détection et évaluer sur un ensemble réellement indépendant. Ne pas annoncer une reconnaissance individuelle ou un résultat RKNN sur Microduck avant sa mesure.
