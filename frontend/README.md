# Interface CallVerify

Vue 3 + TypeScript + Vite, avec une palette crème/olive et des accents lavande.

Depuis la racine du projet, les dépendances sont déjà installées sur ce poste :

```powershell
./scripts/frontend.ps1
```

Lancer l'API dans un deuxième terminal avec `./scripts/dev.ps1`. Interface : `http://127.0.0.1:5173`. Vite relaie `/api` vers Django avec les cookies de session et le CSRF.

Sur une nouvelle machine : `pnpm install`, puis `pnpm dev` dans ce dossier. Compiler avec `pnpm build`.

- `/` : connexion, MFA et récupération du compte.
- `/demo` : aperçu avec données fictives, sans modification serveur.
- `/#/dashboard`, `/#/campaigns`, `/#/imports`, `/#/results`, `/#/exports`, `/#/calls`, `/#/account` : pages authentifiées.
- `/#/admins`, `/#/audit`, `/#/exclusions`, `/#/settings` : administration réservée au superadministrateur.

Campagnes éditables et archivables, imports avec aperçu/feuille/mappage, résultats paginés et fiches détaillées, exports CSV/XLSX personnalisés, invitations et suspension, rôles, MFA/QR/codes de secours, paramètres et exclusions. Les alertes sont consultables par la cloche. Les listes de traitements se rafraîchissent toutes les 10 secondes et le dashboard toutes les 15 secondes lorsque la page est visible ; aucun rafraîchissement pendant un formulaire de traitement ouvert.

Les modales supportent Escape et conservent le focus clavier. Le backend contrôle chaque permission ; la visibilité du menu ne remplace pas ces contrôles.

Le build Docker utilise Nginx pour servir les fichiers Vue et relayer les API. L'override de production ajoute HTTPS via Caddy. Les secrets sont exclusivement configurés côté serveur. Les appels réels attendent le scénario et les informations fournisseur.

Police Google Fonts avec repli système si elle n'est pas disponible.
