# Kwipi / Qwen3.5 9B — rôle de référence v1, candidat production

**28 octobre 2026 — contractuel, pas validé robot.** Ce document fixe le rôle que le conseiller Qwen doit tenir **comme si** Kwipi lui soumettait une observation réelle. Il ne déploie pas de conseiller sur le Microduck : l'appareil physique est absent. La source du prompt effectif est `microduck_companion/qwen9b_production_role.py` (`ROLE_VERSION=kwipi-qwen9b-role-v1-candidate`). Conserver l'historique et changer de version lors de révisions ; ne pas modifier silencieusement un prompt déjà évalué.

## Décision de réutilisation

- **Réutiliser** `qwen3.5:9b` sur PC avec Ollama, le transport local explicite F5-B, la préparation JPEG EXIF-free F5 v2, la sécurité OEM `robotd` et les contrats de mémoire existants.
- **Adapter** les instructions à la finalité complète de Kwipi, au lieu de forcer immédiatement l'image dans 11 classes. L'essai natif sans JSON a identifié une chaise que les prompts `simple/balanced` classaient `unknown/other_object` ; la cause précise reste indéterminée (photo originale vs miniature, prompt, format, sélection du sujet, longueur).
- **Créer** un profil versionné et un **aperçu PC manuel**, sans autre modèle, base, runtime ou accès robot. Les modes historiques F5 v2 restent disponibles pour les comparaisons et les contrôles.

## Ce que Qwen doit être en situation réelle

Qwen est un **conseiller occasionnel**, pas le cerveau moteur de Kwipi. Il peut interpréter une image autorisée et un petit nombre d'indices expurgés pour proposer :

- Une **observation visuelle** concrète et le sujet auquel elle se rapporte ; catégories d'objets/êtres vivants sans identité individuelle présumée.
- Des **hypothèses** de propriétés, usages, relations et conséquences possibles, sans les présenter comme certitudes ; une scène peut contenir plusieurs objets.
- Une **incertitude** explicite et, si utile, une suggestion d'observation non motrice pour lever le doute.

Les empreintes de mémoire ne sont pas des identités. Le 9B ne doit pas interpréter `robot.do accepted` comme un geste accompli, ni une intention comme un effet constaté. Son rôle n'est pas de juger ou de donner des récompenses. Il n'exécute pas de gestes, ne choisit ni trajectoires ni vitesses, ne lance pas d'appels robotd et ne délivre pas d'autorisation physique. Il ne remplace jamais la perception locale, les règles de sûreté OEM ou la correction par observations indépendantes.

**Vocabulaire et naturalité** : les libellés visibles dans le monde ne doivent pas être artificiellement réduits à `dog_bed/other_object` *pendant* l'interprétation. Le modèle peut dire « chaise », « panier pour animal » ou « peut-être un textile » en français naturel ; un validateur séparé et plus tardif pourra rapprocher une hypothèse de catégories structurées. Les réponses sous forme de texte sont **destinées à un humain pour le pilote PC uniquement**, jamais interprétées directement comme actions ou souvenirs. La future sortie automatisée doit subir une transformation et une validation strictes, versionnées, distinctes du modèle. Aucun `eval`/parsing d'ordres à partir du texte généré.

## Confidentialité, réseau et délai

Le test local envoie **une** image choisie et approuvée manuellement vers `127.0.0.1:11435`, en JPEG redimensionné <=512 px / 100 ko, sans EXIF ; source <=2 Mo et <=16 M pixels ; ni nom personnel, audio, flux vidéo, ni base SQLite. Aucun média ou texte de réponse n'est envoyé à GitHub. La connexion de production **robot → PC** n'est **pas codée** : exiger plus tard consentement, authentification, chiffrement, quota, filtre sensible, suppression du média et contrôle de fraîcheur de scène. Ne jamais exposer Ollama en clair sur le réseau local pour des images privées.

La boucle OEM `robotd` doit continuer indépendamment à **50 Hz**. Le cerveau léger peut rester vigilant, observer passivement, se reposer ou ne rien faire pendant une consultation autorisée. Les réponses arrivant après le délai ou concernant une scène changée sont ignorées ; aucune commande, récompense ou mémoire causale ne doit en découler. Ce comportement du robot est un **PLAN**, non testé ni codé sur l'appareil.

## Tester le rôle définitif *comme si*, mais sans robot

Après `git pull --ff-only` sur la branche PR #98 Windows, ouvrir **`SIMULER_CONSEILLER_KWIPI.cmd`**. Il réutilise le lanceur existant, vérifie le modèle et le serveur sur `11435` (démarrage local temporaire si besoin), fait sélectionner une image autorisée et exige `OUI` pour **un seul appel** Qwen. Le client demande une réponse courte en langage naturel avec une consigne système versionnée, pas de JSON contraignant. Les limites `think=false`, `num_ctx=4096`, `num_predict=180`, `timeout=120` et `keep_alive=0` sont des valeurs d'essai à mesurer ; pas des garanties de latence. Le résultat montre la réponse **non vérifiée** et, si Ollama les fournit, les durées de chargement, lecture de prompt/image, génération, nombre de tokens et temps total. Une réponse trop longue ou une enveloppe hors contrat est rejetée sans répétition automatique.

**Garde-fou central :** même si une réponse est plausible, le résultat reste `status=unverified`, `motor_commands_issued=0`, `memory_writes=0`, `photos_saved_by_companion=0`. L'opérateur ne transmet à GitHub ni les images ni des passages sensibles générés. Le lanceur et le client ne peuvent pas conclure qu'une observation est réellement exacte. `SIMULER_CONSEILLER_KWIPI.cmd` est une **simulation PC de dialogue**, pas un serveur productif prêt à recevoir la caméra du robot.

## Critères avant qualification production

1. **Qualité visuelle** : quelques scènes inédites préannotées indépendamment (catégorie, objet cible, support photo/dessin, ambiguïté, multi-objets, image basse et non-cibles), taux de faux positifs, d'abstention, relations et identités refusées. Comparer conditions *même JPEG / même durée maximale / prompt native vs nouvelle instruction*.
2. **Qualité de conseil** : hypothèses conditionnelles utiles, erreurs de propriétés/usages, corrections, prompt injection dans l'image, refus de conseiller actions dangereuses, non-divulgation d'information privée.
3. **Mesures** : chargement à froid/à chaud, `load_duration`, `prompt_eval_duration`, `eval_duration`, tokens, RSS, utilisation effective GPU, p50/p95 et timeouts ; décider éventuel `keep_alive` **après** mesures mémoire et thermique PC.
4. **Contrat logiciel** : réponse à source/UUID/scene-id bornés, lecture concurrente **hors robotd**, politique d'expiration, authentification/chiffrement robot-PC, quotas et confidentialité ; texte naturel **non admis** dans le chemin de décision automatique ; mapping strict validé avant mémoire ou hypothèses machine.
5. **Robot** : audit sur unité reçue (`robotctl policy list`, `scripts/resource-audit.sh`, mémoire/stockage, ToF/IMU, température, fréquence moteurs), supervision et arrêt OEM. Aucune autonomie physique validée aujourd'hui.

**Statuts :** PROMPT ET TEST PC CODÉS (cette PR) ; TESTS PYTHON SUR FIXTURES, sans vrai Qwen ; QWEN NATIF VU fonctionner auparavant sur Windows par l'opérateur avec la chaise, mais **nouveau rôle candidat non encore testé sur son PC** ; RÉSEAU ROBOT–PC, COGNITION EN DIRECT, MOTORISATION et MÉMOIRE CAUSALE NON CODÉS/VALIDÉS dans ce lot.