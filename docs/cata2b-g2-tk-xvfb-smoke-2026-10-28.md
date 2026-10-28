# Cat-A2b-G2 — essai graphique Tk réel sous Xvfb, sans média privé

**28 octobre 2026. [PR #122](https://github.com/Jean-Philippe56520/Microduck/pull/122), [CI #40718960461](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40718960461) réussie : 1 571 tests Python (5 ignorés) + 1 test graphique réel Tk/Xvfb. Statut de fusion à vérifier.** Réutilise l'éditeur graphique Cat-A2b-G #120 et le validateur des revues Cat-A2b-R #118. Aucun capteur, modèle, SQLite, Qwen, réseau privé, sous-module OEM ou moteur n'est impliqué.

## Audit préalable et critère de preuve

**Observation :** le logiciel Cat-A2b-G a réussi 1 571 tests Python dont 5 ignorés, mais la fenêtre Tk, les boutons et les événements de souris n'ont encore jamais été testés dans un vrai environnement graphique. Les 29 JPEG privés restent inaccessibles ici, et la piste OEM #450 est distincte et toujours ouverte.

**Hypothèse testée :** un serveur d'affichage virtuel Linux Xvfb peut faire fonctionner les véritables widgets Tk de l'éditeur, avec deux JPEG artificiels, et vérifier de bout en bout la saisie sans jamais ouvrir une photographie réelle.

**Preuves visées :** vraie fenêtre, image sans boîtes historiques préremplies, catégories/visibilité non présélectionnées, drag sur Canvas, confirmation de la première image, seconde image sans cible explicitement acceptée, déclarations de revue, export du JSON dans un répertoire temporaire, compatibilité avec le parseur existant #118. Les sorties restent des **annotations de fixture**, pas une vérité terrain indépendante.

**Critères d'échec / stop :** absence de serveur virtuel ou de Tk, rectangle absent, étiquette historique visible, mauvais dialogue négatif, export non terminé, sortie hors dossier temporaire, test qui s'éternise. Le scénario utilise une limite CI de 45 secondes et une borne interne de 10 secondes ; tout échec doit faire échouer la CI sans secours sur les vrais JPEG.

**Risque et retour arrière :** dépendance de la CI à Xvfb et Tk présents dans l'image Linux de GitHub ; retour arrière facile par retrait du seul scénario et de l'étape CI. Aucune migration, daemon, action motrice, modèle ou gitlink changé.

## Réutiliser / adapter / créer

| Source | Décision | Motif |
| --- | --- | --- |
| Éditeur privé #120 | Réutiliser sans changer ses fonctions | Tester le vrai Canvas au lieu de réécrire une interface |
| Vérificateur #118 et types Cat-A2b | Réutiliser | Contrat JSON, boîte, visibilité, SHA déjà livrés |
| CI Python existante | Adapter : une étape Xvfb | Réemploie Python 3.11, Pillow 11.3 et unittest |
| OEM épinglé microduck@942e58e3, microduck_rl@b02fdea4, robotd, mediad | Aucun changement | L'OEM a l'autorité sur moteur et caméra ; ce test n'ouvre ni l'un ni l'autre |
| QuackNav, microduck-brain, Twin, Quacksat, GC/Smartulf, OEM #381/#414/#450 | Ne pas importer | Aucun composant tiers requis et aucune PR constructeur présumée fusionnée |

## Test reproductible dans la CI Linux

Le scénario indépendant est conservé dans tests/gui_smoke_cata2b_editor.py : son nom ne commence pas par test pour éviter l'ouverture involontaire de Tk lors du unittest discover standard. La CI ajoute une seule étape explicite :

    command -v xvfb-run
    python -c 'import tkinter; from PIL import ImageTk'
    timeout 45s xvfb-run -a python -m unittest discover -s tests -p 'gui_smoke_cata2b_editor.py' -v

Le test fabrique deux JPEG 80×120, dont le premier possède une fausse étiquette historique « dog » invisible dans la GUI, puis génère une nouvelle boîte « cat » avec de vrais événements Tk simulant une souris. Il ne signifie ni qu'un humain a annoté les photos, ni que le robot a reconnu un chat.

## Limites et suite

Tests confirmés dans le Linux CI virtuel ; pas de GUI Windows/WSLg validée, aucun nouveau site, aucune contre-annotation indépendante, aucune mesure caméra à 20–30 cm, aucun gain cognitif C3-B et aucune preuve robot. Avant tout portage : exécuter l'audit OEM et les budgets RK3566 (RSS, CPU/NPU, disque/WAL, thermique, batterie, 50 Hz). La porte Cat-A2b #78 reste ouverte et exige des données réellement indépendantes.

Références : docs/plan-action.md, docs/cata2b-local-blind-editor-2026-10-28.md, docs/hardware-feasibility-audit-2026-10-25.md et docs/community-reference-registry-2026-10-26.md.

**Premier essai rouge, puis correction du test :** les événements synthétiques étaient mal synchronisés avec le dispatch Tk. Le scénario vérifie désormais le Canvas réellement affiché, le passage press/drag/release et les événements immédiats. **La fonction de l'éditeur n'a pas été modifiée** pendant cette correction ; le run #40718960461 a ensuite validé le parcours graphique complet.