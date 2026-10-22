# Recette avec données fictives

## Environnement disponible

Une base PostgreSQL de recette distincte contient des données entièrement
synthétiques. Les fichiers SQLite habituels et le CRM du port 5173 restent
inchangés. La recette s'ouvre sur **http://localhost:5174/crm** ; utiliser ce nom
d'hôte pour la distinguer du CRM habituel. Les cookies du portail sont également
distincts en mode démo. L'onglet porte le titre « AMX — DÉMO FICTIVE ».

La racine du port 5174 mène aussi au CRM unique, sans ancienne application
CallVerify séparée. **Vérification des numéros** est accessible uniquement à
`admin.demo` après sélection d'Isolation ; aucune vérification fournisseur réelle
n'est activée dans cet environnement. Voir [le point d'entrée unique](CRM_ENTRYPOINT.md).

Les identifiants et le mot de passe aléatoire figurent uniquement dans
`private-media/demo-volume-20261022/ACCES.txt`. Ce dossier et son manifeste sont
ignorés par Git. Le mot de passe commun est réservé à cette recette locale.

| Données | Assurance | Isolation |
| --- | ---: | ---: |
| Prospects | 5 000 | 5 000 |
| Rendez-vous | 1 250 | 1 250 |
| Comptes rendus passés | 478 | 478 |
| Tâches de rappel | 1 667 | 1 667 |
| Notes | 5 000 | 5 000 |
| Résultats d'appel déclarés | 5 000 | 5 000 |
| Campagnes | Sans campagne dans ce modèle | 6 |

22 comptes et 33 appartenances : `admin.demo`, `setter.demo01` à
`setter.demo10` dans les deux espaces, `conseiller.demo01` à
`conseiller.demo05` en Assurance, `closer.demo01` à `closer.demo05` en Isolation,
et un seul `client.demo` Isolation. Le compte administratif historique Isolation
créé pour porter les campagnes est inactif et n'a aucun mot de passe utilisable.

## Scénarios à parcourir

1. **Setter** : se connecter avec `setter.demo01`, choisir l'espace voulu,
   consulter prospects, rechercher, changer les filtres et paginer. En Isolation,
   les 500 prospects affectés à ce setter sont visibles ; en Assurance, le pool
   partagé existant reste visible, les rendez-vous et tâches gardent leur auteur.
2. Ouvrir les fiches : consulter qualification Assurance ou C2 Isolation,
   notes, résultats déclarés et rappels. Créer/modifier une note ou une tâche,
   terminer une tâche puis vérifier l'historique. Aucun bouton ne peut passer un
   appel réel : aucun poste ni secret fournisseur n'est configuré dans la recette.
3. **Rendez-vous** : consulter les dates passées et futures, annulations,
   résultats renseignés ou manquants, ainsi que les instantanés de qualification.
   Les dix setters ont chacun un conseiller attribué en Assurance. Les visites
   Isolation sont réparties entre cinq closers et le client unique.
4. **Conseiller/closer** : se connecter au compte correspondant, comparer son
   agenda et ses fiches autorisées ; renseigner un résultat sur un rendez-vous
   passé sans résultat ou corriger un résultat selon les permissions existantes.
5. **Client/administration** : comparer les statistiques par semaine et période,
   setter et closer, vérifier les ventes/présences renseignées et les résultats
   manquants, télécharger les exports proposés. Les annulations et inconnus ne
   doivent pas devenir automatiquement des absences ou des ventes perdues.

Les écritures manuelles de recette restent dans la base démo. Les numéros ont
un indicatif régional volontairement invalide `000`, les courriels utilisent
`example.invalid`, les noms et adresses portent Démo/Fictif. Les statuts et
historiques sont des scénarios synthétiques ; ils ne prouvent aucune action réelle.
Les résultats techniques Lookup, le journal NEWT et les connexions externes ne
sont pas simulés comme des observations fournisseur réussies.

## Recréer un autre jeu

Préparer une instance PostgreSQL locale jetable et ses variables opérateur `PG*`,
sans utiliser le serveur de production. Créer un **nouveau dossier vide** sous
`private-media/`, puis :

```powershell
New-Item -ItemType Directory private-media/demo-autre
.venv/Scripts/python.exe scripts/crm_demo.py create --output private-media/demo-autre/demo.json --contacts-per-space 5000 --seed 20261022
```

Le volume est paramétrable de 40 à 20 000 prospects par espace (5 000 par défaut).
La graine stabilise les noms, valeurs et identifiants de requête ; les dates sont
relatives à la création, les mots de passe et le nom de base restent aléatoires.
Une nouvelle base et trois schémas sont créés et migrés avant le remplissage ORM.
Chaque service remplit ses données dans une transaction et refuse un second
remplissage. Une erreur marque le manifeste `failed` ; aucun service démo ne peut
être lancé avec ce manifeste. Ne pas supprimer manuellement des lignes pour
contourner ce refus : créer une autre recette. Aucun reset ni écrasement d'une base
existante n'est fourni. Les dates des événements de création sont celles du
remplissage ; ce n'est pas une reconstitution chronologique de vie réelle.

## Lancer et arrêter la recette

L'instance PostgreSQL désignée par le manifeste doit être démarrée, puis :

```powershell
.venv/Scripts/python.exe scripts/crm_demo.py serve --manifest private-media/demo-volume-20261022/demo.json --node "C:/Users/HP/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
```

Adapter le chemin Node selon le poste. Le superviseur lance les trois API sur
8190/8191/8100 et Vite sur 5174, tous en boucle locale. Un port occupé provoque un
refus, sans arrêter le programme qui l'occupe. Ctrl+C arrête uniquement les
processus enfants de cette recette ; la base reste disponible pour la reprise.
L'instance PostgreSQL n'est pas arrêtée par le superviseur. Les journaux sont dans
le dossier privé du manifeste. Le démarrage ne remplit ni ne réinitialise la base.

L'environnement des sous-processus utilise une liste explicite, sans charger
`.env` ni hériter de ses bases, mots de passe téléphoniques, SMTP ou OAuth. Seules
les clés de signature de la recette sont reprises du manifeste. Lookup est
désactivé, courriels en mémoire, aucun worker de rappel/mail/calendrier n'est lancé,
aucun poste téléphonique ni calendrier distant n'est créé. Les proxys Vite de
recette ciblent uniquement les ports de recette, sans repli vers le CRM courant.

## Contrôles et limites

Cinq tests dédiés, dont une recette PostgreSQL réelle à 120 prospects par espace,
vérifient les garde-fous, rôles, liens entre fiches/tâches/rendez-vous/résultats,
permissions de configuration, plages de dates et absence de données fournisseur.
La recette dédiée est rejouée en CI PostgreSQL 17. La suite core complète compte
241 tests, dont 19 ignorés sur SQLite ; typage Vue et build réussis. L'avertissement
Vite de bundle >500 kB reste présent.

Le jeu volumineux n'est pas une validation de charge à utilisateurs simultanés,
ni une recette d'appels, d'envois, d'OAuth, de synchronisation externe ou de
migration des données actuelles. Importer les sources actuelles, comparer et
sauvegarder/restaurer la base commune restent des étapes distinctes.
