# MEM-2B-WA — reconnaissance candidate de trois balles par vidéo (préenregistré 03/11/2026)

**Statut de ce commit : protocole fixé AVANT toute extraction, empreinte, prédiction ou résultat.**
Référence antérieure opposable : [préenregistrement en commentaire #280](https://github.com/Jean-Philippe56520/Microduck/pull/280#issuecomment-6604922467). Main de départ : `1ee8d702cb40e2158b79ac0821ee05542c0e741c`.

## Objectif et manque réel

La mémoire visuelle M1-B/MEM-2B garde seulement des empreintes 64 octets de fixtures et **n'identifie pas réellement un objet**. Le test historique sur 180 photos ABO de chaises a obtenu **0/48** rappels avec seuil MEM-2B gelé (0,94 et écart d'ambiguïté 0,025), malgré zéro faux candidat inconnu. Il manque une évaluation publique **sur une même instance filmée à des hauteurs différentes et deux imposteurs de la même catégorie**, sans ajustement sur ces images. Cette mesure ne prouve ni les conditions du Microduck, ni le NPU, ni une conséquence physique.

## Sources, intégrité et droits

Éditeur : University of Washington, [RGB-D Object Dataset](https://rgbd-dataset.cs.washington.edu/), [index cropped](https://rgbd-dataset.cs.washington.edu/dataset/rgbd-dataset/), [README](https://rgbd-dataset.cs.washington.edu/dataset/rgbd-dataset/README.txt), *Lai, Bo, Ren, Fox, ICRA 2011*. Le papier rend le jeu public **à la communauté de recherche** ; la documentation examinée ne donne **pas de licence explicite de redistribution ou d'usage commercial**. Autoriser au plus cette étude publique de recherche hôte, **jamais** republier médias ou descripteurs, ni commercialiser, installer sur le robot ou intégrer les images au firmware. Un doute sur les droits d'étude arrêterait ce lot.

Les trois archives externes sont épinglées par SHA-256, octets relevés **en WSL2 par l'opérateur AVANT l'essai**, et nom d'hôte HTTPS unique :
- `ball_1.tar` : 5 742 008 octets, SHA-256 `31fa833e059bf248acd1f3cdd8e0da5769bfc300429638d9a363fc9bd7fd7352`.
- `ball_2.tar` : 6 558 724 octets, SHA-256 `4d44cebe74da0255d785c9b24ea61967a6d21b94d605c5b11ddb3c0c342cb509`.
- `ball_3.tar` : 5 854 518 octets, SHA-256 `41609ef7f541cd879676aa2bcfb1c6c545dfb1eee10d4bc0a8e1d5d841efe479`.

Inventaire source attesté sans extraction : respectivement **820 / 783 / 809** `_crop.png` avec autant de profondeur, masques et positions. Vidéos strictement **1, 2, 4** et nombres (objet 1 : 288/273/259 ; objet 2 : 269/251/263 ; objet 3 : 265/261/283). Aucun visage/capteur/PC privé. Les fichiers sont des séquences corrélées sur *plateau tournant*, prises à trois hauteurs, et non des rencontres indépendantes du robot.

## Protocole de mesure gelé

1. Télécharger au plus **18 155 250 octets** dans un répertoire temporaire privé, HTTPS avec certificat et redirections HTTPS seulement. Comparer tailles, SHA et ensemble des nombres de vues. Refuser chemins TAR absolus/`..`, liens et fichiers inattendus. **Jamais extraire le TAR** ; décoder en mémoire exclusivement les RGB choisis. `Pillow==11.3.0`, mode PNG, RGB → `convert("L").resize((32,32), Image.Resampling.BILINEAR)` (sans masque, crop adaptatif, segmentation ou modèle). Le contraste M1-A natif est conservé et une image rejetée bloque l'essai, sans remplacer la vue.
2. Pour chaque objet, trier les frames numériquement de chaque vidéo. Références : vidéo **1**, aux indices zéro-based `floor(N/4)` et `floor(3N/4)`. Requêtes : vidéos **2 et 4**, aux indices `floor(N/4)`, `floor(N/2)`, `floor(3N/4)`. Interdiction de changer les poses si elles ratent.
3. Trois plis « une balle laissée inconnue ». À chaque pli, deux balles connues avec leurs **deux** empreintes de référence ; la troisième est un imposteur même catégorie non enregistré. Chaque pli : **12** requêtes de balle connue, **6** requêtes d'inconnue. Au total **36 positives**, **18 inconnues** corrélées. Baseline sans mémoire = aucune candidature (36 abstentions connues, 18 abstentions inconnues).
4. Reprendre sans modification `compact_multimodal_memory.image_fingerprint`, `MATCH_IMAGE=0.94`, `AMBIGUITY_GAP=0.025` et `r2b2_abo_confusables._mem2b_policy_candidate` (copie contractuelle du comparateur `MultiviewPatternMemory.probe_image`). **N'insérer aucune vraie photo dans l'unique SQLite `ExperienceMemory` limitée aux fixtures**. Tester séparément la parité du comparateur sur des fixtures synthétiques existantes. Aucune commande moteur, caméra, Qwen ou nouvel écrivain.
5. Compter **candidats exacts**, **mauvais candidats parmi les objets connus**, **faux rapprochements d'inconnues**, **abstentions**, dont ambiguïtés, par pli et vidéo ; publier seulement les comptes anonymes, latence CPU/RSS hôte si disponible, SHA des archives et statut. Ne pas publier images/fichiers originaux, vecteurs, exemples ou médias dans les artefacts GitHub.

**Critère de passage qualitatif gelé** : au moins **18/36** réponses positives correctes, **0/36** confusion de balles connues, **0/18** rapprochement erroné de la balle inconnue. Sinon **`INSUFFICIENT` et STOP** : pas d'affinage du seuil, de changement des poses ou de relance opportuniste. Tests/CI qui réussissent = exécution technique, **pas** preuve du passage qualitatif. Un passage ne certifierait au maximum qu'une candidature visuelle hôte sur trois objets, aucun apprentissage autonome.

**Conditions d'arrêt technique** : source/licence invalide, SHA, nombre de membres, boîtes, PNG/contraste, budget ou comparateur non conformes, fuite média ou rupture de confinement : pas de score. Retour arrière : supprimer fichiers/CI expérimentaux de la PR si aucun gain, ne conserver que la décision ; aucune migration SQLite, aucun changement OEM, sous-module, modèle, WIC B11 ou service. Les changements GitHub restent dans une PR brouillon jusqu'aux tests.
