# PER-OI-V7-V2-SRC-0 — échantillon prospectif source-only après STOP des 42 V1

**04/11/2026. Candidat.** [Porte fixée avant code](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6644374649), [amendement de cardinalité AVANT code](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6644380772). Base de branche `main@801d87dec0da7820fce58d94533fd04d525545aa` après [#310 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/310) et #313 fusionnée. Le [plan directeur](plan-action.md) demeure autoritaire ; ce rapport conserve les preuves, pas un déploiement.

## Pourquoi une étude V2 distincte ?

La sélection source-only de [#312](https://github.com/Jean-Philippe56520/Microduck/pull/312) était un candidat de 42 photos Open Images avec boîtes : [#314](https://github.com/Jean-Philippe56520/Microduck/pull/314) a exécuté le premier **vrai contrôle d'indépendance des sources** et trouvé **4 images parmi les 42 déjà inférées** dans les 288 images historiques Open Images. Pourtant **42/42** votes humains positifs et **42/42** URL de provenance HTTPS vérifiés. **#312 et #314 ont été fermées sans fusion**, pas de scores ni JPEG.

V2 n'est **pas** une « correction » postérieure du roster V1 : c'est une **nouvelle expérience prospective source-only**, sur de nouvelles portes fixées avant toute prédiction. On garde la vérité du STOP V1 intacte. Une image V1 uniquement sélectionnée en métadonnées **sans JPEG ni inférence** n'est pas une image de TEST déjà consommée ; l'exclure systématiquement rendrait artificiellement impossible de retrouver six `Tennis ball` parmi les neuf candidates historiques. En revanche, les 288 réellement inférées sont obligatoirement exclues **avant** le nouveau tirage.

## Réutiliser / adapter / créer

Réutiliser les sélecteurs source historiques `select_human_verified_cases` (#123), `_load_sources` (#295), `choose_cases` (#298), le parseur `_rows/_md5` et les SHA #311/#313, ainsi que le fichier COCO val GT épinglé dans le workflow officiel du projet pour #310. **Créer** un seul banc de recherche `experiments/per_oi_v7_v2_288_source.py`, sa suite fixture et une CI source-only. Aucune librairie nouvelle, photo privée ou publique téléchargée, ONNX, moteur, SQLite, modèle RKNN, Yocto, gitlink ou archives B10/B11 touchés.

**Sources et empreintes SHA-256 connues :** cinq sources officielles/vérifiées indépendamment :
- Catégories OI : `1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9`.
- Images OI val : `ed93a0e121fe345effdfc73563157cb500b33a17`.
- Labels humains OI : `92ddbdfceb3626e044df5e89100b24f6c22a79c1888a4bddd00a6f231d86d56a`.
- Boîtes OI val : `d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2`.
- COCO val 2017 annotations miroir SHA contrôlé : `e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f`.

Reconstituer **48 #123 + 192 #295 + 48 #298 = 288** images effectivement inférées et SHA W1 `6954c9a0136d262a01eeba44b1da35319cf5323d270c73bc306cfd7f5f33179a`. Les champs `OriginalURL` et `OriginalLandingURL` d'Open Images sont analysés **uniquement en mémoire sur CI**, sans les publier. Les identifiants de photo Flickr sont comparés à ceux tirés de `flickr_url` des **5 000** images COCO val. Un format de source inaccessible ou non reconnue rend la conclusion inconnue, **STOP** ; ne jamais comparer des IDs de corpus entre eux.

## Fixé avant source, succès et arrêts

Graine de sélection **figée** : `kwipi-per-oi-v7-v2-exclude-288-v1-20261104`. Cibles exactement **Tennis ball, Book, Bottle, Chair, Cat, Dog, Person**, six photos chacune. Les 42 V1 ne servent jamais de nouveau roster : chaque candidat V2 est sélectionné par hash déterministe graine/label/ImageID **après** exclusions de 288 images déjà inférées, licences photo déclarées CC BY 2.0, MD5 valides **non dupliqués**, rotation 0, URLs HTTPS originales et source Flickr identifiable/non présente dans COCO val, votes humains positifs exacts et boîtes humaines non groupées/dépeintes/intérieures. Ne jamais considérer les labels manquants comme négatifs. Taille/hauteur caméra = `unknown`.

**P1 positif :** lecture des cinq sources aux SHA épinglés, provenance et consentement **déclaratif** (pas prouvé par URL), 288 anciennes images exclues. **P2 :** 5 000 identités Flickr COCO val vérifiables (sinon `STOP`), zero collision des identités Flickr choisies, pas de doublon MD5. **P3 :** 42 nouveaux couples GT alloués, sept catégories × six positifs avec boîte et vote humain, même règle de score figée pour futur banc ; SHA roster publié **une seule fois, avant pixels**. **P4 :** fixtures adversariales, CI finale verte.

**N1 négatif :** SHA différent, source inaccessible, tag non humain, confiance fractionnaire, MID douteux, catégorie absente, bbox NaN/inversée, dessin/inside/groupe, licence non BY, MD5/ID doublon, URL/photo Flickr ambiguë, collision COCO, réemploi historique OI ⇒ **exclusion/STOP** selon erreur, jamais retuning. **N2 :** moins de 6 images dans une seule classe, notamment `Tennis ball` ⇒ **STOP sans relancer de tirage ou changer de cible**. **N3 :** zéro produit par un modèle ou photo réelle ne peut être déduit du succès CI ; pas de comparaison directe Nano/S/M avant les droits individuels et la non-duplication des pixels.

**Portée de PASS :** source nouvelle *potentiellement* qualifiable, **pas** certification juridique, fiabilité 95–100 %, perception depuis la caméra Microduck, NPU, consommation, 2 Hz, identification physique, focalisation, autonomie ou effet OEM. Les annotations OI, même humaines, ne constituent pas une vérité exhaustive pour toutes les classes. La vérification indépendante des droits de chaque auteur, les doublons photographiques et le contrôle des médias originaux seront une porte séparée. Sous-modules épinglés, `robotd` seul moteur/sûreté 50 Hz, `mediad` caméra et une seule SQLite inchangés.

**Retour arrière :** une PR non fusionnée en cas de STOP, archives et anciens rosters conservés. Aucun modèle installé sur robot absent.
