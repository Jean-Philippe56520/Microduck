# MEM-2B-R — Mesure publique candidate sur les chaises ABO (29 octobre 2026)

**Porte 0 : protocole préenregistré, avant résultats ; PR d'évaluation seule.**

## Décision recherchée
Les deux vues de carré synthétique de MEM-2B #173 ne prouvent pas la continuité d'objet. Le [banc historique R2-B+2](r2b2-confusable-objects-2026-10-26.md) avait déjà mesuré 180 JPEG de 30 séquences de chaises ABO (Amazon.com et Guillaumin et al., **CC BY 4.0**), dont 48 vues de produits inscrits et 24 d'inconnus, sur un seuil de validation **différent** (M1-B ancien : 0,876838). Résultat antérieur : 10/48 vues correctement rappelées, 2/24 faux candidats d'inconnus. Il ne s'agit ni d'instances physiques authentifiées ni de sessions photographiques indépendantes.

**Hypothèse falsifiable** : la règle fixe de candidature de MEM-2B (`MATCH_IMAGE=0,94` ; `AMBIGUITY_GAP=0,025`) pourrait fournir des rapprochements utiles sur ces **mêmes photos originales**, sans retoucher le seuil ni choisir les exemples après leur score. Le seuil est inchangé depuis #173.

**Témoin** : sans rappel, la voie MEM-2A ne donne aucun candidat par empreinte. Avec rappel, les références sont les angles 0 et 36 des 12 `spin_id` inscrits en TEST ; les angles 9,18,45,54 sont les requêtes. Les 6 autres `spin_id` du TEST sont les inconnus **de même catégorie**. Le jeu validation historique est maintenu distinct du TEST et n'ajuste pas la politique.

**Porte de sortie préfixée avant résultats** : au TEST, **au moins 24/48 candidats corrects**, **aucun rapprochement erroné entre inscrits**, **aucun faux rapprochement des 24 vues d'inconnus**. Sinon classer l'usage pour reconnaître/reprendre un même objet **insuffisant**, sans seuil réajusté, sans promouvoir le code comme perception embarquée ; conserver seulement le rôle de candidat non vérifié. Compter aussi les abstentions, ambiguïtés, succès par angle et collisions.

## Réutiliser / adapter / créer
- **Réutiliser** intégralement le lecteur/licence/roster/partitions de `r2b2_abo_confusables.py`, le descripteur de 64 octets, la fonction de score M1-B2 et les constants de `compact_multimodal_memory.py` déjà utilisés par `probe_image`. Aucun nouveau média, modèle ou téléchargement requis.
- **Adapter** seulement un évaluateur **pur**, sans SQLite, sur les descripteurs déjà présents en RAM, intégré au JSON **anonyme** du benchmark existant ; comparer son résultat au véritable `probe_image` **sur fixtures artificielles uniquement** pour vérifier le contrat. Les vrais JPEG **ne seront pas introduits dans les tables M1-B réservées aux déclarations de fixtures**.
- **Créer** quelques tests négatifs de collision, ex aequo, sources mélangées et empreintes invalides. Réutiliser le workflow R2-B+2 existant pour les 180 JPEG CC BY 4.0 et la CI Python/N1 habituelle. Ne créer aucun autre banc, outil de téléchargement, base ni modèle.
- **OEM et tiers** : `upstream/microduck@942e58e3` avec robotd seul pilote à 50 Hz ; `upstream/microduck_rl@b02fdea4`, sous-modules inchangés. OEM #381, #414 et #450 non fusionnées, QuackNav, microduck-brain/Quacksat/Twin/Smartulf références seulement. Aucun lien causal/robot/moteur.

## Limites et sécurité
Le test emploie les *mêmes séances de plateau tournant* par produit ; deux angles ne constituent pas deux sessions de capture. Les groupes sont déclarés par catalogue (`item_id`, `spin_id`), pas des identités physiques prouvées. L'évaluateur reproduit le score et l'ambiguïté M1-B sur des descripteurs réels **sans exécuter l'API SQLite réelle pour les photos publiques**, dont l'entrée est limitée aux fixtures ; une équivalence du comportement de comparaison est testée sur données synthétiques. Les candidats ne peuvent ni confirmer une catégorie, ni autoriser une action, ni attribuer une récompense. Images et poids restent dans le runner, aucune publication privée.

**Risques et retour arrière** : une identité supposée à tort à partir de deux empreintes ressemblantes ; si le résultat manque ou le code modifie les surfaces motrices/SQLite OEM, arrêter, ne pas fusionner. Sinon le comparateur reste strictement hôte et optionnel. Aucune revendication de caméra basse vérifiée, ni de ressources RK3566, ni de gait robot. Ne pas présenter une CI verte comme preuve de reconnaissance domestique.

## Résultats
En attente d'une exécution GitHub Actions identifiée de R2-B+2 sur cette branche. Ne pas inventer les comptes ni ajuster la porte ci-dessus.
