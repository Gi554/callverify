# Informations publiques pour Google OAuth

Orvia CRM est exploité par AMX au Bénin. Le contact assistance et confidentialité confirmé est exosolutionquebec@gmail.com.

Valeurs pour Google Auth Platform → Branding :

| Champ | Valeur |
|---|---|
| Nom | Orvia CRM |
| Page d’accueil | https://orvia-crm.com/presentation/ |
| Politique de confidentialité | https://orvia-crm.com/confidentialite/ |
| Conditions d’utilisation | https://orvia-crm.com/conditions/ |
| Domaine autorisé | orvia-crm.com |

Le logo est facultatif et aucun nouveau logo raster n’est livré dans ce lot. Les trois pages sont de vrais fichiers HTML statiques copiés dans le build, servis par Nginx, sans session ni JavaScript. Elles ne passent pas par la normalisation de l’entrée CRM. La racine et les anciens chemins continuent leur parcours existant ; la page d’accueil déclarée à Google est /presentation/.

Le client OAuth Web conserve sa redirection exacte : https://orvia-crm.com/crm/oauth/google. Ne pas utiliser la page de présentation comme callback.

La présence des pages ne publie pas automatiquement le projet Google, ne valide pas le consentement et ne prouve pas sa conformité juridique ou l’approbation de Google. L’utilisateur doit compléter Branding, vérifier la propriété du domaine dans Search Console avec un compte propriétaire/éditeur du projet, puis suivre la vérification des autorisations demandées. Le code de vérification DNS éventuel doit être fourni par Google ; ne pas en inventer.

Les textes décrivent les usages existants et les limites connues : calendrier principal, jetons chiffrés, publication optionnelle, événements neutres, retrait/déconnexion distincts, révocation côté fournisseur, demandes de droits au contact, hébergement Contabo en Europe et envois Brevo. Aucun numéro d’immatriculation, adresse postale, durée fixe de rétention, certification ou déclaration APDP non confirmé n’est inventé. Les informations d’organisation et les pratiques de conservation devront être actualisées quand AMX les précisera.

Références :
- https://developers.google.com/identity/protocols/oauth2/production-readiness/policy-compliance
- https://developers.google.com/terms/api-services-user-data-policy
- https://service.apdp.bj/mise_en_conformite/politique_de_confidentialite
