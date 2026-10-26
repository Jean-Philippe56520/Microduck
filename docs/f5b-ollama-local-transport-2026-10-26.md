# F5-B — Client Ollama facultatif et banc de comparaison PC

**26 octobre 2026 — [PR #42](https://github.com/Jean-Philippe56520/Microduck/pull/42) fusionnée après revue du logiciel ; niveau de preuve : test HTTP local simulé.** La phase F5-A ([PR #41](https://github.com/Jean-Philippe56520/Microduck/pull/41)) est intégrée à `main`. Aucune requête à un **vrai** Ollama/Qwen ni mesure des 64 Go de RAM du PC, de puissance, d'accélération ou d'autonomie du robot n'a été effectuée par nos tests CI.

## 1. Architecture retenue

- **`OllamaLocalClient`** utilise la bibliothèque Python standard `http.client` vers **`POST /api/chat`**, non streaming, JSON structuré, sans images, outils, scripts ni transcription. Le client lit le **`PCRequest.to_wire()`** de F5-A : seulement des étiquettes **fictives** d'objet inconnu ou contradictoire et un identifiant aléatoire de requête, jamais des pistes, noms, médias, coordonnées, souvenirs ou personnes.
- **`OllamaEndpoint`** accepte uniquement une **adresse IP littérale** et son port. `http://127.0.0.1:11434` par défaut ; aucune découverte DNS, URL externe, redirection, cloud, proxy automatique ou clé d'API. Pour un protocole de laboratoire seulement, les IPv4 RFC1918 sur HTTP exigent `unsafe_private_lan_lab=True`. **Un LAN privé non chiffré ne prouve pas l'authenticité du serveur et peut être intercepté** : en utilisation future, préférer un tunnel SSH authentifié et restreint au loopback, validé indépendamment.
- **`OptionalOllamaWorker`** déporte une requête unique dans un thread. La décision cognitive du cerveau **préexiste** au PC ; `poll()` ne bloque pas l'activité locale, rejette le résultat après la limite monotone F5-A (2 secondes) et ne réinjecte aucun ordre. Une tâche bloquée conserve sa place jusqu'à terminaison ; aucun nouveau travail n'est accumulé. `close()` n'arrête pas de force un socket déjà exécuté ; la fermeture et les délais restent des mécanismes logiciels à valider avant déploiement.
- **`advisory_from_transport()`** utilise le parseur de confiance stricte F5-A. En F5-B, **aucun pixel ni caractéristique d'objet n'est transmis** : seule l'abstention `unknown` avec confiance déclarée **0** est acceptée à titre d'hypothèse non vérifiée. Une prétendue classification chien/chat/jouet, même formulée dans le JSON valide, est refusée faute de preuve. La réponse n'alimente ni `ExperienceMemory`, ni identification individuelle, ni `robotd`, ni son.
- **Limites** : enveloppe HTTP 16 384 octets, contenu modèle 4 096 octets, socket limité, au plus une consultation en cours via le worker, schéma et identifiant F5-A corrélés, refus de doublons et données additionnelles, erreurs/mauvais modèle/commandes/horodatage tardif. Le timeout socket seul **n'est pas une garantie de délai total en présence d'un pair malveillant qui délivre des octets lentement** ; le robot ne doit consulter qu'à travers la voie non bloquante, et aucun déploiement physique n'est approuvé ici.

Les classes et commandes sensorielles constructeur demeurent intactes : `robotd` reste seul responsable des mouvements à environ 50 Hz ; Qwen ne voit aucune image OEM et n'a aucun accès aux servos ou à la sécurité.

## 2. Vérifications automatisées

`tests/test_ollama_local_client.py` ouvre un **petit serveur HTTP simulé sur 127.0.0.1 uniquement**, qui **n'est pas Ollama**. Les tests couvrent le corps de requête expurgé, l'échange HTTP, les réponses de type F5-A, les erreurs de connexion, les délais, redirections non suivies, mauvaise identité modèle, enveloppes et champs malformés, sorties trop volumineuses, commandes et catégories non étayées, l'exclusion de LAN/Internet sans opt-in, le worker non bloquant et le repli hors connexion.

`microduck_companion/f5b_transport_demo.py` réalise un échange HTTP **réel en boucle locale**, mais uniquement contre ce serveur fictif, sans télécharger ni exécuter de modèle. `python -m microduck_companion.f5b_benchmark` lance le **mode à blanc**, aucun réseau. La [CI GitHub Actions (https://github.com/Jean-Philippe56520/Microduck/actions/runs/40251807307)](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40251807307) a réussi avec **781 tests Python**, la compilation, la démo HTTP fictive et le banc dry run, sans PC Ollama disponible.

## 3. Banc Qwen 4B puis 9B sur PC — non exécuté

Les tags du catalogue officiel [Ollama Qwen3.5](https://ollama.com/library/qwen3.5/tags) incluent `qwen3.5:4b` et `qwen3.5:9b`, deux modèles multimodaux. **Notre entrée F5-B est exclusivement textuelle et fictive**. La comparaison ne mesure donc **ni leur reconnaissance visuelle des animaux, ni leur précision sur de vraies images**, seulement leur capacité à **s'abstenir**, leur conformité au protocole et les temps mesurés sur le PC.

Sur le **PC local uniquement**, après consentement explicite à installer les modèles, exemple de commandes :

```bash
ollama pull qwen3.5:4b
ollama pull qwen3.5:9b
python -m microduck_companion.f5b_benchmark
python -m microduck_companion.f5b_benchmark --run-live --model both --samples 3 --timeout-s 60
```

- Le script réalise les tests dans l'ordre **4B puis 9B**, n'émet que des catégories fictives, sans média, et rapporte les durées HTTP (p50/p95 pour cet échantillon), le temps serveur déclaré, le chargement, les tokens et les rejets F5-A. Le timeout du **banc diagnostique** peut dépasser 2 secondes pour mesurer une réponse lente ; **elle reste rejetée par F5-A** après 2 s. Le bench est **bloquant et destiné au PC seulement**, jamais à la boucle de décision ni au robot.
- L'affichage ne contient ni contenu complet de réponse du modèle, ni identifiant privé, clé, nom, IP ou image.
- L'affichage de métriques serveur `total_duration` et `eval_duration` provient des valeurs **déclarées par Ollama**, qui doivent être distinguées du temps HTTP mesuré. `RSS` du processus Ollama, charge réelle CPU/GPU/NPU et consommation en watts **ne sont pas mesurés** par ce script : relever ces valeurs séparément avec des outils système validés, consigner plateforme, versions, quantification, charge et contexte.
- Les tailles de fichiers annoncées par le catalogue Ollama ne correspondent **pas** à la RAM réellement consommée. Avec un PC Ryzen AI et 64 Go de RAM, la possibilité de charger un modèle n'est **pas** une preuve de délai, d'accélération GPU/NPU ou d'énergie.
- En cas de non-installation, erreur de connexion, sortie malformée, forte latence ou hypothèse infondée, **aucune suggestion du PC n'est utilisée par le robot**.

Pour un PC sur réseau plutôt que localhost, **ne pas exposer le port Ollama directement par défaut** ; configurer un tunnel authentifié menant à un port loopback explicitement connu. Toute configuration réseau réelle, certificat, authentification, permissions de déploiement et audit de sécurité sera validée ultérieurement. Les interfaces Yocto/robot réels sont hors de ce lot.

## 4. Critères non encore satisfaits

- Aucune performance **4B/9B réellement mesurée** sur le PC utilisateur, aucun test GPU/NPU ou énergie, aucune évaluation multimodale avec images.
- Pas de preuve d'installation, de compatibilité du modèle et de structure de sortie avec un **vrai serveur Ollama** : l'API a été développée selon sa [documentation](https://github.com/ollama/ollama/blob/main/docs/api.md), mais l'interopérabilité réelle reste à confirmer.
- Aucun budget thermique/RAM/eMMC/CPU ou profil de latence du Microduck RK3566, aucun contrôle réel `robotd`/capteurs.
- Aucun service continu, résolution de contradictions ni fréquence intelligente de consultation : **F5-C** apportera quotas, critères de nouveauté et pannes cumulées. La reconnaissance des animaux et la locomotion resteront des chantiers distincts.

**Statut livré de F5-B :** client, worker et banc codés, [PR #42 fusionnée](https://github.com/Jean-Philippe56520/Microduck/pull/42) après [781 tests en CI](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40251807307) ; **validation Ollama/Qwen sur PC restant à effectuer**. Ne jamais présenter F5-B comme une comparaison réelle de performances tant que les résultats PC sont absents.
