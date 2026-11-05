# PER-OI-V7-V2-ID-2 — cause des trois identités historiques non vérifiables

**05/11/2026. Protocole [préenregistré AVANT code](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6652159663).** Base GitHub réelle `main@7f47a79ae54c6b33972e031e09e7265b9da51877` après [#316](https://github.com/Jean-Philippe56520/Microduck/pull/316) fusionnée (4/4 CI sur HEAD). `docs/plan-action.md` fait autorité ; ne pas modifier le classement des preuves.

## Manque prouvé

La CI réelle de #316 a traité les cinq sources officielles déjà épinglées et vérifié les **42/42** photos V2 sur leurs identités Flickr (image URL, landing URL et OriginalMD5), mais seulement **285/288** identités historiques sont entièrement interprétables. Trois entrées anciennes restent des **inconnues**, sans collision démontrée. Le statut est `STOP_V2_FLICKR_IDENTITY_NOT_QUALIFIED` et **pas** une confirmation d'indépendance ou de licence. [Résultat vérifié #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6652070798).

## Gain borné / réutiliser

Pas de nouvelle sélection ou nouveau modèle. Adapter seulement `audit_flickr_identity_rows` dans `experiments/per_oi_v7_v2_288_source.py` pour séparer **de façon exclusive** les raisons techniques de non-lecture, **sans changer le critère de STOP**. Compteurs anonymes répartis entre 42 sélectionnées et 288 historiques :

1. URL source et URL de destination toutes deux non interprétables comme identifiant Flickr.
2. URL source seule non interprétable.
3. URL de destination seule non interprétable.
4. Identifiants Flickr source/destination contradictoires.
5. Empreinte MD5 d'origine invalide.

L'ordre ci-dessus est fixé avant l'essai : en cas de plusieurs défaillances sur la même ligne, compter uniquement la première. Les lignes totalement absentes sont des **comptes séparés**, pas de fausses URL manquantes. Toujours `sum(cinq motifs × deux groupes) == unreadable_source_rows`.

**Tests positifs/négatifs** : sources entièrement cohérentes ; chaque défaut de source, landing, deux URL, divergence, MD5 ; combinaison URL+MD5 avec priorité exclusive ; ligne historique manquante et défaillance sur sélectionnée (pas confondue avec historique). Les tests fixtures précèdent l'accès aux cinq métadonnées officielles en CI. Les SHA des cinq sources et du roster V2 (`282d67af8f97975b55149f4b104eaef79bcef1e94beb9522b207ff8a7193c28c`) restent identiques.

**Résultat attendu :** un diagnostic utile permettant de déterminer s'il existe une voie de provenance vérifiable pour les trois anciennes photos, ou s'il faut constater `inconnu/STOP`. Même si les causes sont purement syntaxiques, aucune relaxation automatique des contrôles ou certification de licence n'en découle. En cas de changement de source, de hasard/quotas, de fuite d'ImageID/Flickr ID/URL, d'échec fixture/CI, ne pas fusionner.

## Limites et suite conditionnelle

**Aucun JPEG ou poids téléchargé, aucune inférence Nano/S/M, aucune requête Flickr, aucun média/secret/auteur/ID ou URL individuel publié**, aucune modification du moteur, caméra, SQLite, Yocto, sous-modules OEM, ROS ou NPU. Les droits individuels des photographies Flickr, les doublons perceptuels, les angles bas, la latence RK3566, la fiabilité et l'autonomie restent inconnus. `mediad` seule caméra et `robotd` seul acteur moteur/sûreté à 50 Hz. Retour arrière : fermer la PR sans fusion ou conserver un STOP documenté ; aucune tentative de maquiller les trois inconnues en zéro doublon. Lire le vrai résultat CI du HEAD final avant toute fusion.
