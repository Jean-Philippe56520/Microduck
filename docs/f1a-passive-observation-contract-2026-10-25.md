# F1-A — Contrat minimal de perception passive et provenance (25 octobre 2026)

**État : codé et testé logiciellement sur [PR #24](https://github.com/Jean-Philippe56520/Microduck/pull/24), avec [295 tests Python réussis](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40232960339) (269 anciens et 26 nouveaux), sur données exclusivement fictives ; pas de capteur `mediad` raccordé, pas de modèle ML, aucune commande motrice ni validation physique.** Cette PR est le **premier lot de F1**, qui ne sera achevée qu'après F1-B, F1-C et F1-D. [Plan directeur](plan-action.md).

## 1. Sources du constructeur effectivement inspectées

Révision épinglée de `upstream/microduck` : `942e58e3aa6dbb28e7037203fff11866122c7567`.

| Source constructeur | Capacité constatée | Limite pour Companion |
| --- | --- | --- |
| [`mediad/src/frame.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/frame.rs) ; [`mediad/src/main.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/main.rs#L463-L484) | Socket Unix local `media.frame`, réponse JSON-RPC 2.0 puis pixels binaires ; capture à la demande et délai borné par la pipeline | Fournit des images **brutes**, pas une catégorie `chien`, `chat` ou `personne`. Aucune image n'est demandée ni stockée en F1-A |
| [`mediad/src/detect.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/detect.rs#L302-L338) | Notification `media.detections` : `width`, `height`, `took_ms` et boîtes `x0/y0/x1/y1/score` | **Aucun nom de classe ou ID individuel dans ce message**. Le détecteur OEM de Microducks ne sait pas identifier automatiquement d'autres espèces |
| [`mediad/src/main.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/main.rs#L678-L704) | Detections transmises en notifications sur le canal de contrôle d'une session WebRTC ; l'abonné lent peut perdre des messages | Ce n'est **pas** un abonnement JSON-RPC local autonome prêt à lire. Ne pas prétendre l'avoir implémenté en F1-A |
| [`duck-ipc-proto/src/lib.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs#L610-L620) | Nom officiel du RPC local `media.frame`, délibérément hors canal de contrôle | Pas d'API de catégories sonores identifiée lors de l'inspection ; **aucune donnée audio réelle n'entre dans F1-A** |

**Attention :** l'existence de `media.frame` et `media.detections` dans les sources n'est pas une validation de disponibilité sur un robot réel. `mediad` peut utiliser une caméra physique ou une source de test ; la provenance devra être vérifiée explicitement en F1-B.

## 2. Contrat logiciel réutilisé

- `PerceptionEvent` et `PerceptionSnapshot` restent le contrat **v1** déjà utilisé par le cerveau. L'ajout `sound_label` est une **extension additive de catégorie**, pas une modification des paramètres existants : source déclarée, `observed_at` monotone, `ttl_s`, confiance et `track_id` pour `object_label` uniquement. Les versions non prises en charge sont toujours refusées.
- `sound_label` autorise **seulement** `unknown`, `ambient`, `knock`, `bark`, `meow`, `speech`, `keyword_microduck`, `keyword_stop`, `keyword_viens`. Il s'agit de **catégories de fixtures** et non d'un modèle de reconnaissance opérationnel. Aucun texte libre, transcription ou empreinte vocale.
- `microduck_companion/passive_observations.py` expose `summarize_passive(snapshot, now=...)` et des `PassiveObservation` immuables. La sortie contient `kind`, `category`, `status`, `claimed_source`, `confidence`, `observed_at`, `track_id`. Le statut vaut `identified`, `unknown`, `conflict`, `low_confidence`, `stale`, `future` ou `untrusted`.
- Pour les **objets**, les catégories passives reconnues sont `ball`, `toy`, `dog`, `cat`, `person`, `microduck` et `other_object`. `unknown` et tout libellé libre ou nom non répertorié restent **inconnus**. Un ID de suivi est un lien **éphémère au sein de la source**, ni biométrie ni preuve d'identité de Nessquick/Kitty/Malo.
- Les vues regroupent les observations d'un même `track_id` (ou les catégories de sons présentes dans le même snapshot) : **deux labels contradictoires ne s'annulent pas par vote** ; ils produisent `conflict` et `unknown`. La confiance minimale est requise : **0,80** ; une observation admissible en dessous produit `low_confidence`.
- Les TTL objets et sons du contrat v1 sont bornés à **5 secondes**, avec horloge monotone ; un snapshot du futur et une mesure périmée ne produisent aucune catégorie utilisable. Une projection accepte au maximum **64 événements**, sinon **refuse** au lieu d'effacer silencieusement des observations.
- `source` est une **déclaration**, **pas une authentification réseau ou matérielle**. Le filtre existant distingue `mock`, `simulator`, `sensor`, `robotd`, `operator`, `llm_suggestion`. Une chaîne `sensor` n'établit pas qu'un vrai capteur a été lu. F1-B devra vérifier le processus et le transport local avant d'attribuer une source réelle.
- Une observation passive ne contient **aucun** `safe_area`, `floor_clear`, commande moteur, récompense ou analyse Qwen. `keyword_stop` **n'est pas** une voie d'arrêt de sécurité ; `PerceptionSnapshot.to_scene()` et `AutonomyBrain` ignorent le nouveau `sound_label` pour les décisions motrices.

**Compatibilité :** le contrat de sécurité v1, les champs existants et la conversion `to_scene` ne changent pas. Un ancien décodeur externe qui rejetait tout type inconnu doit être adapté avant de consommer `sound_label` ; cette PR **n'affirme pas** une compatibilité rétroactive avec des implémentations qui verrouillent exactement la liste des types v1. Les horodatages monotones ne sont pas directement comparables entre redémarrages : F1-C devra stocker un temps civil distinct de la validité TTL et identifier l'origine temporelle.

## 3. Exemples fictifs et résultat attendu

| Événement purement fictif | Provenance / fraîcheur | Projection passive |
| --- | --- | --- |
| Objet `ball`, `track-1`, confiance 0,95 | `mock` dans `mock`, frais | `identified : ball` ; rien sur la sécurité du sol |
| Objet `unknown`, `track-2` | `mock`, frais | `unknown` |
| Deux labels `ball` et `toy` sur le même `track-1` | `mock`, tous deux frais | `conflict`, catégorie `unknown` |
| Signal `knock` | `mock`, confiance 0,95 | `identified : knock` ; **aucun microphone connecté** |
| Signal `keyword_stop` | `mock` | Catégorie passive uniquement ; aucune commande `robot.stop` ni levée de sécurité |
| Catégorie `cat` attribuée par un LLM ou une source `mock` dans l'environnement `robot` | Source non autorisée | `untrusted` et `unknown` |
| Objet ou son expiré, venu du futur ou peu fiable | TTL / confiance non satisfaits | `stale`, `future` ou `low_confidence` ; pas d'identité vérifiée |

Toutes ces données sont **fictives**, sans photos, voix, informations personnelles ou identité animale/humaine publiées.

## 4. Vérifications et prochaines étapes

- [x] Nouveau type audio borné, sans transcription ni changement de pouvoir moteur.
- [x] Projection pure et déterministe de catégories passives ; conflits, sources et TTL explicites.
- [x] **26 nouveaux tests fictifs** : connu/inconnu, sons, faible confiance, conflits, sources non autorisées, futur/périmé, budget et absence d'autorisation motrice.
- [ ] F1-B **non développé** : adaptateur à une véritable source non motrice ou, à défaut, stub clairement étiqueté, authentification et timeouts.
- [ ] F1-C **non développé** : journal SQLite des découvertes avec reprise inter-processus.
- [ ] F1-D **non développé** : démonstration multi-observations ; aucun test sur robot physique.

La réussite de cette PR **ne termine pas la phase F1**. La locomotion reste suspendue et P1a bloqué. Le prochain jalon sera **F1-B uniquement**, après fusion et CI verte de F1-A.
