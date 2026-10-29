# Images publiques pour essais rapides de vision de Kwipi

**Diagnostic complémentaire sans réentraînement (29/10/2026) :** [analyse des sorties brutes et des confusions balle → parapluie/orange/gâteau](../../docs/yolox-nano-ball-miss-raw-head-diagnostic-2026-10-29.md) ; [JSON des 13 observations](yolox_raw_head_diagnostic.json), [CI #40953575507](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40953575507). Trois balles reçoivent des scores `sports_ball` très bas (0,0537 / 0,0139 / 0,0016) : **ne pas baisser le seuil ni inventer une réétiquette sur ces vues**. Des classes non ciblées offrent des indices de forme, mais aussi des confusions sur les images « inconnu ». La piste « objet possible, catégorie inconnue » n'est **pas codée** et demanderait de nouvelles images de contrôle.

**Résultat YOLOX réel sur ce lot (29/10/2026) :** [rapport JSON image par image](yolox_baseline_results.json), [CI GPU absent/CPU hôte](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40950364823) réussie. Proposition de catégorie attendue : chats **3/4**, chiens **2/2**, balles **0/3**, chaise **1/1**, personne **1/1**, deux images sans cible **2/2** sans proposition. Seuil YOLOX-Nano **0,25** inchangé ; inférence médiane CPU runner **23,632 ms**. Certaines photos source >4 096 px ont été réduites **en mémoire**; les originaux Git sont intacts. Ces catégories image-level ne sont ni un score mAP ni une preuve de localisation correcte ou un test NPU/robot. **Décision : conserver le témoin, ne pas retoucher les seuils pour faire reconnaître ces mêmes balles, chercher une nouvelle source/proposition adaptée aux petites balles dans un autre lot.**

13 images effectivement conservees dans ce repertoire Git : 4 chats, 2 chiens, 3 balles, 1 chaise isolee, 1 personne et 2 scenes negatives. Elles servent a regarder les sorties des detecteurs existants sans imposer de hauteur de prise de vue ni reconstruire un banc.

- Fichiers JPEG/PNG d'origine (ou leurs versions compressees publiques), sans photos privees.
- Le fichier `manifest.json` indique pour chaque image sa categorie attendue, sa source, sa licence declaree et son empreinte Git.
- Ces categories sont **des attentes au niveau image**, non des boites de verite terrain. Une image peut contenir d'autres objets ; `unknown` signifie seulement qu'aucune des cinq categories cibles n'est attendue.
- **Aucun test de reconnaissance n'a ete execute par ce lot.** On pourra utiliser le detecteur YOLOX et les scripts existants; les performances reste a mesurer.
- Des vues variees, pas de promesse de hauteur 20-30 cm. La chaise est une image detouree, pas une scene de logement.
- Ne pas reutiliser ces images comme nouvelles donnees independantes si un modele a deja ete ajuste dessus. Ne pas les envoyer a Qwen ou sur le robot par defaut.
- Les licences par fichier peuvent differer de celle du code Microduck. Les variantes sous CC BY-SA gardent la mention d'auteur et le lien d'origine dans le manifeste; le fichier image reste sous sa propre licence. Les photos RoboCup et TripoSR sont publiees dans des depots sous MIT mais les droits individuels ne sont pas confirms: usage exploratoire, pas de redistributions externes tant que ces droits ne sont pas clarifies.

Verification de l'integrite des copies : `python -m unittest discover -s tests -p test_public_vision_smoke_assets.py -v`.

**But concret :** voir si une balle, un chat, une chaise ou un humain sont proposes par le detecteur. Le score mAP/IoU et la validation de vision embarquee sont distincts et non revendiques ici.
