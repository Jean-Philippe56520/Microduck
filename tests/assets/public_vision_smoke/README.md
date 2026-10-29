# Images publiques pour essais rapides de vision de Kwipi

13 images effectivement conservees dans ce repertoire Git : 4 chats, 2 chiens, 3 balles, 1 chaise isolee, 1 personne et 2 scenes negatives. Elles servent a regarder les sorties des detecteurs existants sans imposer de hauteur de prise de vue ni reconstruire un banc.

- Fichiers JPEG/PNG d'origine (ou leurs versions compressees publiques), sans photos privees.
- Le fichier `manifest.json` indique pour chaque image sa categorie attendue, sa source, sa licence declaree et son empreinte Git.
- Ces categories sont **des attentes au niveau image**, non des boites de verite terrain. Une image peut contenir d'autres objets ; `unknown` signifie seulement qu'aucune des cinq categories cibles n'est attendue.
- **Aucun test de reconnaissance n'a ete execute par ce lot.** On pourra utiliser le detecteur YOLOX et les scripts existants; les performances reste a mesurer.
- Des vues variees, pas de promesse de hauteur 20-30 cm. La chaise est une image detouree, pas une scene de logement.
- Ne pas reutiliser ces images comme nouvelles donnees independantes si un modele a deja ete ajuste dessus. Ne pas les envoyer a Qwen ou sur le robot par defaut.
- Les licences par fichier peuvent differer de celle du code Microduck. Les variantes sous CC BY-SA gardent la mention d'auteur et le lien d'origine dans le manifeste; le fichier image reste sous sa propre licence. Les photos RoboCup et TripoSR sont publiees dans des depots sous MIT mais les droits individuels ne sont pas confirms: usage exploratoire, pas de redistributions externes tant que ces droits ne sont pas clarifies.

Verification de l'integrite des copies : `python -m pytest -q tests/test_public_vision_smoke_assets.py`.

**But concret :** voir si une balle, un chat, une chaise ou un humain sont proposes par le detecteur. Le score mAP/IoU et la validation de vision embarquee sont distincts et non revendiques ici.
