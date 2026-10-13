# Guide administrateur

## Première connexion

Le superadministrateur initial est créé avec `bootstrap_admin` dans un terminal privé. Ajouter son secret TOTP à une application d'authentification et conserver les codes de secours dans un coffre. Sur la connexion, saisir identifiant et mot de passe puis déplier « Code de sécurité ». Un code de secours peut remplacer le TOTP une seule fois.

## Campagne → import → vérification → export

1. Créer une campagne avec sa finalité, sa provenance et son budget fournisseur.
2. Dans Imports, choisir la campagne et un fichier CSV ou XLSX. La prévisualisation présente les lignes avant confirmation ; choisir la feuille Excel puis mapper téléphone, nom et référence.
3. Confirmer. Le tableau indique le résultat, les doublons et les erreurs. Le rapport CSV d'anomalies conserve les numéros de lignes sources. Si Redis est indisponible, la demande reste enregistrée et sera livrée par Beat après rétablissement.
4. Ouvrir Numéros & résultats : chercher par numéro, nom ou référence, filtrer par campagne et validité, puis consulter une fiche pour les sources, preuves et contrôles historiques.
5. Lancer Vérifier depuis Campagnes, lorsque les identifiants Lookup sont configurés. Les réserves estimées respectent le budget ; un recontrôle fournisseur n'est jamais lancé silencieusement après une réponse incertaine.
6. Dans Exports, choisir campagne, format CSV/XLSX, validité et colonnes. Le téléchargement reste privé jusqu'à expiration. Les fichiers expirés sont purgés par la tâche horaire.

La qualification locale et Basic Lookup ne prouvent pas qu'un humain répondra. Les autorisations sont distinctes de la validité et de la joignabilité.

## Administration et sécurité

- Administrateurs : inviter un compte et transmettre le lien de définition du mot de passe par un canal privé ; suspendre/réactiver un compte. Une promotion en superadministrateur exige un MFA déjà activé. Le compte courant ne peut pas se suspendre ou changer son propre rôle.
- Mon compte : activer le MFA en scannant le QR code, confirmer avec un TOTP, puis conserver les codes de secours. Leur renouvellement exige le mot de passe et un nouveau TOTP ; les anciens codes deviennent invalides.
- Paramètres : cache Lookup, cadence globale, durée des exports, conservation des imports, devise et état des connexions. Les tokens ne sont pas saisis ni affichés dans l'interface : ils restent dans l'environnement serveur.
- Exclusions : consigner les numéros à ne pas appeler. Une exclusion bloque l'admissibilité même si une autorisation avait été enregistrée auparavant.
- Fiche contact : consigner une preuve avec expiration puis documenter une décision administrative. L'autorisation exige une preuve encore valide et aucune exclusion.
- Appels : préparer le scénario et contrôler l'admissibilité. L'émission réelle reste désactivée tant que le scénario autorisé, les horaires et l'émetteur ne sont pas définis.
- Journal d'audit : consulter les opérations, acteurs, objets et justifications. Aucune modification des événements n'est possible via l'API.

## Alertes et erreurs

La cloche présente les erreurs de traitement visibles pour votre compte. Les tableaux d'imports, d'exports et de campagnes sont actualisés toutes les 10 secondes tant que la page est visible et qu'aucun formulaire n'est ouvert. Le dashboard se rafraîchit toutes les 15 secondes. Actualiser manuellement après une correction. Pour un incident fournisseur ambigu, demander une vérification au superadministrateur avant toute relance.
