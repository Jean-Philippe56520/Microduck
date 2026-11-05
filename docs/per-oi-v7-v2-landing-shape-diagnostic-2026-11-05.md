# PER-OI-V7-V2-ID-3 — diagnostic de la forme des trois URL Flickr historiques

**05/11/2026.** Porte fixée [avant code et nouveau test, issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6652318765). Base `main@4d4aca4d139dcd9c30b8baf6dde2d66b6c010a44` après [#317](https://github.com/Jean-Philippe56520/Microduck/pull/317) fusionnée **4/4 CI** au HEAD. `docs/plan-action.md` est l'autorité pour les décisions OEM.

## Observation et hypothèse sans extrapolation

Le roster Open Images V7 V2 de **42** scènes demeure gelé par SHA `282d67af8f97975b55149f4b104eaef79bcef1e94beb9522b207ff8a7193c28c`, avant toute inférence ou téléchargement de JPEG. La CI spécialisée [#317](https://github.com/Jean-Philippe56520/Microduck/pull/317) sur les cinq sources officielles épinglées mesure **3/288 sources OI historiques** classées `landing_unreadable_only` : URL photo Flickr directe parsable, URL landing non reconnue par l'extracteur actuel. **Ceci ne démontre pas** leur duplicité, l'absence de duplicité, leurs droits, ni même la forme de ces trois URL.

La [documentation officielle Flickr des URL](https://www.flickr.com/services/api/misc.urls.html) distingue les URL de page `flickr.com/photos/{user}/{photo-id}`, les **raccourcis** `flic.kr/p/{base58-id}`, et des formats historiques. La [documentation développeur](https://www.flickr.com/services/developer/api/) déconseille le scraping et les méthodes API exigent des permissions/clé. **Hypothèse seulement :** ces trois URL peuvent appartenir à un format public différent, mais n'ont pas encore été examinées individuellement.

## Action minimale et vérification indépendante

Adapter uniquement le **lecteur existant** `experiments/per_oi_v7_v2_288_source.py` : une fonction **d'analyse de forme, sans acceptation d'identité** `classify_flickr_landing_shape` avec deux catégories prédéfinies :
- domaine : `flickr_page_host`, `flickr_shortlink_host`, `other_host`, `invalid_url` ;
- chemin : `photo_page_numeric`, `photo_page_other`, `shortlink_base58`, `legacy_photo_gne`, `other`.

Les domaines sont classés par liste blanche : `flickr.com` et ses sous-domaines, `flic.kr` et `www.flic.kr` ; les domaines trompeurs, identifiants de connexion dans l'URL, schémas invalides et URL avec caractères de contrôle sont rejetés. Les raccourcis photo ne sont classés comme `shortlink_base58` que si les caractères sont tous conformes à l'alphabet annoncé par Flickr ; **aucune conversion base58 n'est tentée**, aucun lien suivi et aucune URL renvoyée.

Pour les seules lignes historiquement classées `landing_unreadable_only`, renvoyer **les compteurs agrégés** de combinaisons `domaine_catégorie/chemin_catégorie`. L'invariant `sum(compteurs_formes)==landing_unreadable_only` est imposé en CI et testé sur fixtures. La sortie ne contient **aucun** identifiant photo, ImageID, hôte inconnu brut, chemin, requête, titre ou auteur. Comparateur : résultats #317 avant adaptation, STOP initial conservé. Les cinq SHA sources, le SHA de roster, la graine, le quota 7×6, les poids, les tests et les exclusions ne changent pas.

**Positifs fixtures** : page Flickr numérique reconnue, raccourci base58 plausible, syntaxe `photo.gne`, sortie agrégée sur 42+288 fictifs ; **négatifs** : faux domaine `flickr.com.attacker`, URL contenant credentials, mauvais port, short-ID avec caractères exclus, source sélectionnée défaillante comptée séparément, et cas sans défaut. Chaque chemin a son test positif/négatif avant la vraie CI. Une CI technique verte avec trois formes répertoriées **ne vaut pas PASS scientifique**.

## Critères de succès/STOP et rollback

**PASS technique** : fixtures vertes + CI au HEAD final verte + répartition des trois landing URLs selon les seules catégories autorisées, SHA roster inchangé, `status=STOP_V2_FLICKR_IDENTITY_NOT_QUALIFIED` tant que les URL ne sont pas reliées par preuve indépendante au photo ID Flickr de l'URL directe. **STOP** si une URL reste classée de façon ambiguë, si l'acceptation d'identité est modifiée, si les chiffres ne somment pas à trois, si secrets/médias/identifiants sont exposés, ou si CI non verte ; revenir en arrière sans toucher au roster. Un parseur de formats alternatifs n'est envisagé qu'en lot distinct si le résultat prouve un gain, avec tests d'identités contradictoires.

**Aucun JPEG, modèle ONNX, inférence Nano/S/M, analyse de pixels, NPU RK3566, `mediad`, `robotd` moteur 50 Hz, SQLite, Yocto ou sous-module modifié.** Les licences actuelles/anciennes attribuées à chaque titulaire et les doublons perceptuels sont **toujours inconnus** : la comparaison sur photos réelles reste bloquée par RIGHTS-FLK-0 quelle que soit l'issue de ce diagnostic.
