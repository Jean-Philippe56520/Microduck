# F4-D — Associations locales volontaires et révocables sur fixtures

**26 octobre 2026 — [PR #40](https://github.com/Jean-Philippe56520/Microduck/pull/40), fusionnée après revue.** Cette étape suit [F4-C fusionnée via PR #39](https://github.com/Jean-Philippe56520/Microduck/pull/39), après [689 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40248575737). **Aucun robot physique, lecteur NFC/BLE, caméra ni dispositif réel d'identification disponible dans cette phase.**

## 1. Objectif et frontière de confiance

Le but à terme est de permettre une interaction **personnalisée et volontaire**, sans surveillance biométrique continue. F4-D construit seulement **le contrat logiciel d'association d'un jeton fictif présenté explicitement**. Ce n'est ni une reconnaissance faciale, ni une classification d'un animal individuel, ni une méthode de prouver qu'une personne réelle a donné son accord.

`microduck_companion/revocable_mock_identity.py` s'appuie sur la **SQLite `ExperienceMemory` existante**, sans deuxième cerveau. La table `f4d_mock_optin_associations` ne conserve que :

- Une **référence aléatoire opaque** de 32 caractères hexadécimaux ;
- Une **empreinte HMAC-SHA256** d'un jeton de 32 octets, calculée avec une clé de 32 octets **fournie au constructeur du registre et conservée seulement en mémoire par ce module** ;
- Une **catégorie générique** `pet_cat`, `pet_dog`, `child` ou `adult`, des dates d'inscription/expiration et le dernier numéro de séquence de présentation ;
- La provenance `fictional_voluntary_token_only`.

**Le jeton brut et la clé HMAC ne sont pas écrits dans cette table.** `MockTokenPresentation.token` est exclu de la représentation `repr` des objets pour éviter une fuite évidente dans un journal. Les **identifiants, noms, photos, exemples vocaux, noms d'animaux individuels, pseudonymes du foyer, pistes de suivi, textes libres et localisations** n'appartiennent pas au schéma F4-D. Les références opaques **restent pseudonymes et pourraient constituer des données personnelles si elles étaient liées hors du dépôt à un individu réel** : ne jamais publier de base réelle.

Le HMAC protège contre le stockage brut du jeton mais **ne démontre ni l'entropie réelle du jeton, ni l'authenticité de sa présentation, ni la sûreté physique ou la protection de la clé sur l'eMMC**. La démo publique utilise volontairement des valeurs fixes de fixture **non secrètes et impropres à tout usage réel**. Une future implémentation doit générer des jetons aléatoires avec un générateur cryptographiquement sûr, protéger la clé hors dépôt, configurer des permissions et éventuellement le chiffrement au repos.

## 2. Consentement déclaré, contrôle parental et cas `unknown`

`MockOptInContext` déclare `operator_opt_in`, `supervised`, `privacy_reviewed` et `token_presented_voluntarily`. **Toutes les options sont fausses par défaut.** Une catégorie `child` exige **en plus** `guardian_approved=True` et `child_assent_declared=True` **à l'inscription et à chaque nouvelle présentation**. Pour les animaux, la présentation du jeton est une **initiative déclarée du responsable dans la fixture**, pas un consentement attesté de l'animal.

Ces champs sont des **affirmations de scénario de test**, pas des contrôles d'identité d'un opérateur, une signature parentale, un acte juridique de consentement, une preuve de présence du mineur ou un certificat BLE/NFC. Même lorsque tous les booléens sont vrais, les réponses maintiennent **`real_identity_verified=False`**, **`real_guardian_verified=False`**, **`physical_actions_authorized=False`**, **`motor_commands_issued=0`** et **`speaker_commands_issued=0`**.

Le rapprochement n'a lieu qu'avec le **jeton fourni explicitement à la méthode `present`** et une présentation fictive récente. Une photo, un mouvement, un nom, une voix, une catégorie `person` ou une hypothèse LLM **ne déclenchent jamais cette méthode**. Aucune transformation d'un souvenir `pet_dog` en identité réelle n'est autorisée. Sans jeton connu, sans opt-in, avec consentement retiré ou après expiration/révocation, la sortie n'identifie personne : **`unknown` ou un statut de refus**, sans référence opaque.

## 3. Durées, anti-rejeu et retrait

| Barrière | Paramètre F4-D | Limite de la preuve |
| --- | --- | --- |
| Stockage | **24 associations maximum** dans SQLite | Ce n'est pas une mesure de RAM ou d'eMMC réelle |
| Jeton et clé | **32 octets chacun**, HMAC-SHA256, domaine de calcul distinct | L'entropie n'est pas vérifiée ; aucune clé de production fournie |
| Durée | 7 jours par défaut, admissible de **60 secondes à 30 jours** | Nécessité d'une réinscription volontaire après expiration |
| Fraîcheur | Présentation fictive horodatée de **2 secondes maximum**, aucun horodatage futur | Pas d'authentification de l'horloge ou d'un vrai périphérique |
| Répétition | Séquences strictement croissantes, mémorisées dans SQLite **entre processus** | Ce n'est pas un protocole anticlonage ou un challenge cryptographique réel |
| Révocation ciblée | Référence opaque **et** jeton correspondant + consentement d'opérateur déclaré ⇒ suppression de la ligne | Le jeton ne peut plus être rapproché après suppression |
| Retrait global | `forget_all` sous déclaration d'opérateur, possible même lorsque l'assentiment antérieur d'un enfant n'est plus disponible | Aucun historique d'identité n'est rejoué |
| Panne SQLite | Statut `history_unavailable` ou refus/erreur ; **jamais une association confirmée** | Ce mode dégradé n'autorise aucune action |

**Révocation ciblée et `forget_all` effacent les lignes de registre**, mais **la suppression SQL n'est pas une garantie d'effacement forensique** des pages SQLite, du journal WAL, des sauvegardes, des journaux système ou d'une copie antérieure. La conception du vrai déploiement doit définir chiffrement, rotation de clés, purge des sauvegardes, contrôle de permission et audit de l'exercice des droits. Le module ne renouvelle pas implicitement une association ni ne la réactive après retrait. Une nouvelle association exige une nouvelle demande déclarée.

Une clé différente ne retrouve pas les jetons HMAC existants ; le programme n'en déduit pas une nouvelle identité. Une personne qui a perdu sa clé doit utiliser une procédure locale de purge/rotation définie séparément, jamais reclassifier les observations par biométrie pour retrouver l'identité.

## 4. Tests et démonstration en deux processus

- `microduck_companion/revocable_mock_identity.py` : registre HMAC test, classes génériques, refus des noms ou chaînes arbitraires, opt-in déclaré, vérification à chaque présentation, séquences, dates, révocation, purge ;
- `tests/test_revocable_mock_identity.py` : **34 tests supplémentaires** sur clés et jetons malformés, catégories refusées, contrôle parental au moment de l'inscription **et de chaque utilisation**, inconnus, rejoués, cas expirés, redémarrages, clés différentes, révocation ciblée, purge globale, plafonds, confidentialité, faux indicateurs `verified`, absence de moteur et base SQLite fermée ;
- `microduck_companion/f4d_optin_demo.py` : **deux processus Python indépendants**, avec une **clé et un jeton de fixture publics et fictifs**, et un seul fichier SQLite. Le premier refuse une inscription sans opt-in, inscrit une catégorie fictive `pet_dog`, et retrouve une référence opaque. Le deuxième présente une nouvelle séquence fictive, retrouve l'association, la **révoque**, puis vérifie que la présentation suivante devient `unknown` et qu'il reste **zéro association active**. La démo ne montre pas les jetons en sortie.
- `.github/workflows/python-tests.yml` : lance la suite Python, `compileall` et les deux processus de la démonstration.

[**CI GitHub Actions : 723 tests Python réussis, dont 34 nouveaux F4-D, compilation et démonstration complète en deux processus**](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40249168929).

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests
python -m microduck_companion.f4d_optin_demo --database /tmp/microduck-f4d-fixture.sqlite3 --session first
python -m microduck_companion.f4d_optin_demo --database /tmp/microduck-f4d-fixture.sqlite3 --session second
```

## 5. Ce qui reste strictement non livré

- Aucun lecteur NFC/BLE, émetteur d'identifiants, protocole physique résistant au rejeu ou authentification d'un vrai adulte/parent ;
- Aucune **identification personnelle réelle**, ni correspondance effective avec un animal individuel, ni biométrie animale/humaine ;
- Aucun visage, voix, photo, échantillon d'apprentissage ou souvenir privé importé, ni donnée réelle à charger dans GitHub ;
- Aucun lien entre l'association et les propositions sociales F4-C, les choix moteur `robotd`, le PC Qwen ou des actions physiques ;
- Aucune mesure RAM/RSS/température du RK3566, consommation énergétique ou sécurité à proximité d'un enfant ou d'un animal réel.

**Statut : codé et testé sur fixtures fictives, non validé sur robot physique.** Le prochain lot logiciel **F5-A**, distinct de F4-D, posera **le contrat de Qwen facultatif sur PC**, avec hypothèses typées, refus des ordres moteurs, délais et repli local hors réseau. Une suggestion LLM ne devra jamais devenir une observation authentifiée ou un accès à une identité.
