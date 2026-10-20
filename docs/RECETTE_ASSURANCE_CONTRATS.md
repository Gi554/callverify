# Recette transversale Assurance : import jusqu’à l’export

Cette recette porte sur le registre **administratif**. Elle ne valide ni la signature juridique, ni un cycle commercial complet. Aucune donnée financière et aucun appel ne sont nécessaires.

## Vérification automatisée

Depuis la racine du dépôt sous PowerShell :

```powershell
$env:DEBUG='true'
.venv/Scripts/python.exe manage.py test apps.assurance.backend.crm.test_agreement_journey --settings=apps.assurance.backend.settings --noinput
```

La commande utilise une base de test jetable, sans purger la base locale. Les identifiants et fichiers sont synthétiques et créés en mémoire. Toute requête via Requests provoque l’échec du scénario ; aucun fournisseur n’est sollicité.

Deux tests parcourent les mêmes étapes par les API métier, une fois avec un CSV et une fois avec un XLSX :

1. Aperçu de trois lignes sans création de fiche ; confirmation de deux lignes avec téléphone fourni et rejet de la ligne sans téléphone, avec numéro de ligne physique.
2. Nouvel envoi identique avec le même identifiant d’import : aucune création supplémentaire. Deux lignes source ayant le même téléphone restent deux fiches, conformément à l’import brut Assurance.
3. Recherche et prise en charge du prospect ; correction de son nom et incrément de version.
4. Création d’un contrat En suivi puis nouvel envoi identique : un seul contrat.
5. Téléversement d’une pièce interne puis nouvel envoi identique : un seul document. Association au contrat, téléchargement et contrôle des octets.
6. Registre filtré sur la référence et l’échéance à sept jours : un résultat, une pièce et un suivi dans les statistiques.
7. Ouverture du fichier Excel généré : nom corrigé, jours avant fin et nombre de pièces cohérents ; e-mail exclu.
8. Archivage : retrait des alertes de suivi, classement Hors suivi dans la synthèse, historique de création/liaison/archivage conservé.
9. Ancienne version de liaison refusée ; pièce originale conservée et non partagée implicitement à un conseiller affecté.
10. Conseiller : fichier interne non téléchargeable, registre et export refusés. Retour administrateur et libération effective de la fiche.

## Checklist manuelle dans le navigateur

À exécuter dans un espace de recette avec un compte administrateur Assurance et des données synthétiques. Garder fichiers, identifiants et captures de recette hors de Git. Ne pas utiliser de coordonnées client réelles pour filmer.

- [ ] Dans Imports, choisir un CSV ou XLSX avec Nom/Téléphone/Email et une ligne sans téléphone. Contrôler l’aperçu et les correspondances avant confirmation.
- [ ] Après confirmation, vérifier les nombres importés/rejetés et le motif avec sa ligne. Assurance conserve le téléphone brut : cela ne déclenche pas une validation Lookup.
- [ ] Dans Contacts, rechercher la fiche, l’ouvrir, prendre en charge, modifier le nom et attendre le message d’enregistrement.
- [ ] Dans Mandats et contrats de la fiche, créer un contrat avec référence unique, état En suivi, dates cohérentes et motif. Choisir une date de fin entre aujourd’hui et sept jours pour la suite.
- [ ] Ajouter une pièce interne dans Documents du dossier. Dans les pièces du contrat, actualiser les documents disponibles, sélectionner la pièce, fournir un motif et associer. Télécharger pour vérifier le fichier.
- [ ] Fermer la fiche proprement. Ouvrir le registre central, rechercher la référence, sélectionner Échéance proche et horizon 7 jours, puis Rechercher.
- [ ] Contrôler le résultat, la pièce active et la synthèse. Le résumé applique tous les filtres ; l’encart des alertes préexistantes exclut le filtre alerte, comme indiqué à l’écran.
- [ ] Télécharger Excel. Vérifier les lignes, dates et libellés dans Excel/LibreOffice, puis la feuille Périmètre. L’export utilise les filtres **saisis**, même si une nouvelle recherche n’a pas encore été appliquée à l’écran.
- [ ] Rouvrir la fiche, reprendre en charge, archiver le contrat avec motif puis fermer. Vérifier son absence dans les échéances proches et sa présence avec le filtre Archivé, classé Hors suivi.
- [ ] Consulter l’historique depuis la fiche. Contrôler les motifs et le maintien des liens documentaires.
- [ ] Dans une session conseiller affecté à la fiche, vérifier que ce contrat et sa pièce interne n’ont pas acquis un partage implicite. Ne pas partager une pièce confidentielle pour réaliser ce contrôle.

## Portée de la validation

Les tests automatiques couvrent les API et le contenu du XLSX, pas les clics, le rendu visuel, le téléchargement natif du navigateur ou l’authentification centrale réelle. La checklist manuelle reste à exécuter ; elle n’est pas déclarée réussie par sa présence dans le dépôt. Les tests utilisent des tickets métier de recette et une date UTC figée, pas des comptes de production. La revue esthétique globale reste différée.
