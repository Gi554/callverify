# Une seule application : CRM AMX

## Accès

La racine `/` et les anciennes adresses du front autonome (`/demo`, `/#/campaigns`,
`/#/admins`, etc.) normalisent l'adresse vers `/crm`, puis montent uniquement le
portail CRM. Le code d'amorçage ne choisit plus entre deux applications. Les
anciens composants `App.vue`, `Workspace.vue` et leur client API exclusivement
historique ont été retirés. Le titre HTML initial est celui d'AMX.

La page de connexion initiale demandée par l'utilisateur conserve son apparence et
sa marque CallVerify ; elle sert aux profils Assurance et Isolation du **même CRM**.
Elle ne donne pas accès à une deuxième application. Les retours OAuth sous
`/crm/oauth/...` et les liens centraux `#invite=`/`#reset=` sont préservés. Les liens
de récupération des anciens comptes locaux (`/reset-password?uid=...&token=...`)
ne sont pas convertis en jetons d'identité centrale : ils reviennent au portail.

## Parcours de vérification

Se connecter avec un compte central administrateur de l'espace **Isolation**,
puis ouvrir **Vérification des numéros** dans sa navigation. Cet écran regroupe :

1. Les listes Isolation.
2. L'import CSV/XLSX, son aperçu et sa confirmation.
3. Le contrôle Lookup explicite et les résultats, dont l'état de la ligne.
4. Les exports et leur téléchargement authentifié depuis le CRM.

Aucun lien ne renvoie vers l'ancienne application. L'écran n'est proposé ni aux
setters, ni au client, ni aux closers Isolation, ni dans l'espace Assurance.
L'API exige un ticket central portant l'audience Isolation et le rôle
administrateur. Une session administrative historique locale ne suffit pas.

Les routes d'import et d'export regroupent désormais GET et POST au même point
d'accès ; deux actions DRF concurrentes portant le même chemin ne peuvent plus
masquer une méthode. Le téléchargement utilise le client métier du portail pour
obtenir le ticket, puis un fichier Blob local ; il ne navigue plus directement
vers une URL sans autorisation. Un refus conserve l'erreur à l'écran et ne produit
pas de téléchargement.

## Vérifications et limites

Tests des anciennes entrées, OAuth et jetons centraux ; chargement des quatre
onglets ; import/confirmation/export avec traitement simulé et téléchargement
Excel synthétique ; matrice de refus sur onze accès en lecture/écriture pour les
rôles Isolation non administrateurs et tous les rôles Assurance ; refus d'une
session locale historique. Suite core : 245 tests, dont 19 ignorés. Frontend :
44 tests, typage et build réussis. Le bundle JS est désormais de 482,33 kB sur ce
build, sans l'ancien front autonome.

Treize contrôles HTTP sur la recette du port 5174 confirment le démarrage unique,
l'accès aux quatre onglets pour l'administrateur Isolation et leur refus avec un
compte setter ou un ticket administrateur Assurance. Revue visuelle à faire.
Aucun Lookup réel, appel, message ni traitement fournisseur lancé par ces tests.

Ce retrait concerne le front autonome. Les modèles, données, traitements et API
historiques du backend sont conservés pour compatibilité ; ils ne sont pas
transformés ou supprimés par ce lot. Le parcours de vérification offert dans le
CRM utilise exclusivement les routes centrales protégées d'Isolation. Aucune
migration de données ni fusion de comptes historiques n'est réalisée ici.
