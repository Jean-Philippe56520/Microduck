# M1-B2 — Banc comparatif hôte d'empreintes visuelles et audio (pilote)

**26 octobre 2026 — [PR M1-B2](https://github.com/Jean-Philippe56520/Microduck/pulls) — étude expérimentale sur PC/runner, non déployée.** Ce document décrit un protocole, pas une reconnaissance d'objets éprouvée ni un résultat matériel.

## Question et choix

M1-B a constaté sur 6 photos/2 sons publics que 64 octets visuels et 16 octets audio étaient invariants au seul changement simple de luminosité/volume : rotation 12° et recadrage 3 pixels ont donné 0/6, décalage audio 16 ms 1/2. Augmenter le nombre d'empreintes ne corrige pas cette fragilité.

Ce sous-lot compare à métriques égales, sur *les mêmes* photos/enregistrements publics :

| Candidat | Descripteur persistant théorique | Poids nécessaires | Limite |
| --- | ---: | --- | --- |
| M1-B gris 8×8 | 64 octets/photo | aucun | apparence et position des pixels |
| MobileNetV2 ImageNet, **distribution 1 000 classes** ONNX, CPU | 4 000 octets/photo si float32 | ~14 Mo | représentation *sémantique*, **pas** un embedding d'identité ni une boîte d'objet |
| M1-B spectrogramme artisanal | 16 octets/extrait | aucun | sons simples, dérive temporelle |
| Google YAMNet ONNX, **1024 dimensions** moyennées, CPU | 4 096 octets/extrait si float32 | ~16,1 Mo | similarité d'événement sonore, **pas** reconnaissance d'une source individuelle |

Les 4 000/4 096 octets sont un **calcul de stockage de float32**, pas la RAM réellement consommée par ONNX, Python, les tenseurs intermédiaires ou SQLite. Le prototype conserve en RAM des tuples Python de float et ne stocke pas ces signatures en SQLite : la valeur n'est **pas** une mesure de fichier ou de RSS. Les poids ne sont jamais poussés dans GitHub, ni sur Microduck.

Le MobileNetV2 réutilise le modèle [ONNX Model Zoo du banc F3-B](f3b-real-cc0-photo-baseline-2026-10-25.md), SHA256 `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`. Ce pilote emploie **ses 1 000 probabilités de classes** comme descripteur appris ; on ne peut pas déduire de deux chats « même chat ». YAMNet est l'export ONNX [Audio Magic](https://huggingface.co/audiomagic/yamnet-onnx) des poids Google sous Apache-2.0, révision `f25b741c2f0bdc6d7e6db24b5fddda23347dbafd`, SHA256 `d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e`. Les poids externes et leur déclaration de licence/provenance restent à recontrôler à la réutilisation.

## Protocole reproductible

- **Médias en accès explicite seulement :** 12 photographies du catalogue CC0 déclaré F3-B, séparées en six **validation** et six **test**, et les deux sons environnementaux CC0 déclarés du précédent M1-B. Pas de photos, voix ni données du foyer. Les droits déclarés ne sont pas vérifiés juridiquement.
- **Contrôle d'absence de doublon exact** entre photos de validation/test ; les groupes de crédit photographique du catalogue sont déjà distincts selon la partition. Il n'existe **aucun couple vérifié du même animal ou du même objet physique**.
- **Positifs d'apparence (même fichier dérivé) :** luminosité +10 %, rotation de 12° et recadrage 9 % environ par bord. **Négatifs approximatifs :** paires de fichiers distincts, sans preuve qu'ils représentent des individus différents.
- **Audio :** fenêtre PCM 1 s, 16 kHz, volume ×0,8, décalage 16 ms, bruit blanc numérique reproductible d'environ 26 dB de rapport signal/bruit. C'est une perturbation numérique, non une deuxième prise de son authentique.
- **Scores :** distance normalisée M1-B pour les caractéristiques artisanales, cosinus pour les descripteurs appris. Le cosinus n'est **pas** une probabilité. Seuil visuel appris gelé à partir du **maximum des scores de paires inter-fichiers de validation seulement** ; comparaison strictement supérieure, et aucune consultation des résultats test pour choisir le seuil. Seuil audio **0,95 arbitraire et non calibré**, vu les deux seules sources.
- **Mesures hôte** : succès sur variations, rapprochements potentiellement indus inter-fichiers, temps d'inférence CPU par modèle (médiane/p95/max) sans prétraitement, temps CPU process après chargement des modèles, pic RSS process total, octets de poids et taille théorique de signature. Aucune mesure Microduck RK3566, batterie, température, NPU ou délai moteur.

## Exécution

Le workflow optionnel `.github/workflows/m1b2-host-embeddings.yml` est déclenché à l'ouverture ou à la mise à jour de la PR sur les chemins du lot (et peut être déclenché manuellement). La CI Python générale exécute également les tests hors ligne **sans installer de modèles, ni télécharger de médias**. Les modèles et photos/sons sont récupérés uniquement dans les jobs expérimentaux et jamais publiés comme artefacts.

Le benchmark refuse de démarrer sans `--public-cc0`, deux chemins de poids, empreintes SHA256 conformes et catalogue exact. Si un média/poids est inaccessible, le job **échoue sans substituer des chiffres fictifs**. Commande en environnement hôte adapté :

```bash
python -m microduck_companion.m1b2_host_embeddings \
  --public-cc0 \
  --image-model /chemin/prive/mobilenetv2-12.onnx \
  --audio-model /chemin/prive/yamnet.onnx
```


## Résultats mesurés sur CI hôte (pilotage expérimental, pas validité robot)

[GitHub Actions M1-B2 #40309136430 — dernier code testé](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40309136430) : pipeline ONNX public **réussi** sur le commit `70ed3ad`; [CI Python générale #40309129962](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40309129962) : **934 tests Python réussis** (ainsi que les étapes générales, dont Rust). La PR peut évoluer après ces exécutions ; vérifier le SHA des checks avant toute fusion.

### Reconnaissance de transformations du *même fichier* (six photos TEST)

| Épreuve | M1-B 64 octets | MobileNetV2 distribution 1 000 classes |
| --- | ---: | ---: |
| +10 % luminosité | 6/6 | 6/6 |
| Rotation 12° | 0/6 | 6/6 |
| Crop ~9 % bord | 0/6 | 6/6 |
| Rapprochements inter-fichiers potentiellement indus (15 paires) | 0/15 | **1/15** |

Le seuil cosinus appris, gelé depuis les *seuls* 15 couples inter-fichiers de validation, vaut **0,107929** ; il ne mesure pas une probabilité d'identité. Le cas de rapprochement inter-fichiers sur TEST montre un risque de fusion non justifiée ; aucun couple n'est étiqueté « même objet physique » ou « individus physiques différents ». Le succès après transformation du *même JPEG* n'est pas une preuve d'invariance au point de vue naturel.

### Reconnaissance de transformations du *même enregistrement* (deux sons)

| Épreuve | M1-B 16 octets | YAMNet 1024 × float32 |
| --- | ---: | ---: |
| Volume ×0,8 | 2/2 | 2/2 |
| Décalage temporel 16 ms | 1/2 | 2/2 |
| Bruit numérique ~26 dB de rapport signal/bruit | **2/2** | 0/2 |
| Rapprochements entre les deux fichiers | 0/1 | 0/1 |

Seuil audio YAMNet **0,95 heuristique**, **non calibré**. Deux sons et une seule paire négative ne permettent aucun taux de fausse identification réaliste. Le modèle audio appris est **moins robuste au bruit de ce petit banc**, donc ne remplace pas M1-B dans cette configuration.

### Consommation hôte (une exécution ; mesures du runner et non du robot)

| Mesure | Valeur |
| --- | ---: |
| Poids MobileNetV2 | 13 964 571 octets |
| Poids YAMNet | 16 093 355 octets |
| Inférence image ONNX CPU, médiane / p95 | 6,86 / 7,29 ms (48 appels) |
| Inférence son ONNX CPU, médiane / p95 | 3,60 / 3,99 ms (8 appels) |
| Pic RSS du processus complet | 145 180 Kio |
| Temps CPU utilisateur après chargement des modèles | 1,226 s |
| Temps CPU système après chargement des modèles | 0,041 s |

Ces durées d'inférence excluent prétraitements, téléchargements et collecte ; le RSS inclut Python, ONNX et les deux modèles ensemble. Impossible d'en déduire le coût isolé d'un modèle, la marge RAM sur RK3566, la consommation électrique ou la thermie. Les valeurs varient d'un runner à un autre.

**Décision provisoire :** poursuivre vers un vrai corpus multi-vues et davantage de sons indépendants, avec un meilleur embedding visuel *d'instance* et un seuil audio calibré ; **aucun modèle sélectionné pour le robot et aucune modification de SQLite M1-B ou de la politique PC**.

## Interprétation et décision

L'expérience ne couvre **pas** les prises de vue naturelles multi-angles du même objet, l'identification de Nessquick/Kitty, une vraie maison bruyante, les paroles, ni le rejet d'un inconnu réellement vu par caméra. Le protocole doit être **élargi à des séquences multi-vues consenties et tracées par source**, avec négatifs crédibles (objets proches, autres chats et chiens, sons voisins), seuil gelé sur validation, puis test indépendant, avant de retenir un modèle.

Si le modèle appris fusionne trop de fichiers distincts, si le rappel après transformation est bas ou si sa ressource hôte est disproportionnée, **ne pas l'intégrer** ; conserver M1-B expérimental. Aucun code ne branche Qwen, `mediad`, `robotd`, SQLite réelle ni motricité. Le robot demeure hors ligne et sûr indépendamment de ce banc.

**État :** tests hors ligne et étude sur médias publics exécutés en CI hôte avec résultats consignés ci-dessus ; pas de conclusion de précision en milieu domestique, ni de validation RK3566. Le sous-lot reste expérimental, sans intégration au robot.
