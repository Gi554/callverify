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


## Exécution navigateur du 20 octobre 2026

Recette réalisée dans le navigateur intégré sur le frontend Vite et les deux services Django locaux, avec deux bases SQLite **séparées** de celles du projet, comptes administrateur/conseiller synthétiques et téléphonie désactivée. Le dossier de recette, les mots de passe, bases, captures et fichiers restent dans les emplacements privés ignorés par Git. Services temporaires arrêtés après déconnexion.

Résultats observés :

- Connexion centrale administrateur, entrée Assurance et aperçu CSV : trois lignes, aucune fiche créée avant confirmation. Correspondances choisies dans l’interface.
- Confirmation : deux contacts importés et ligne physique 3 rejetée pour téléphone manquant. Doublon de téléphone brut conservé.
- Ouverture et prise en charge ; correction du nom enregistrée puis contrat En suivi créé depuis la fiche, avec dates et motif.
- Téléversement d’une pièce PDF synthétique interne, association au contrat et téléchargement depuis Pièces liées. Comparaison des octets du fichier téléchargé avec la source : identiques. Le PDF de recette vérifie le transport, pas la qualité d’un document PDF métier.
- Registre central : référence, état, dates et une pièce active cohérents. Recherche par référence + Échéance proche + horizon 7 jours : une ligne et une unité dans les catégories Contrat, En suivi et Échéance proche.
- Téléchargement Excel déclenché par le bouton du navigateur. Classeur ouvert par le contrôle local : référence et nom corrigé présents, sept jours avant fin, une pièce liée, e-mail privé absent. La lecture graphique du classeur dans Excel/LibreOffice n’a pas été effectuée.
- Archivage depuis la fiche ouverte par le registre : historique avec motifs de création/liaison/archivage, pièce conservée. Retour à la recherche Échéance proche : zéro résultat et synthèse à zéro. Filtre Archivé sans alerte : une ligne, Contrat = 1, Archivé = 1 et Hors suivi = 1 ; compteur global des échéances proches revenu à zéro.
- Pour préparer le contrôle conseiller, affectation du seul prospect synthétique au compte synthétique dans la **base de recette**, hors interface. Cette préparation ne valide donc pas un parcours d’affectation métier.
- Déconnexion puis connexion centrale conseiller : une seule fiche visible, aucun module administratif Mandats et contrats. Fiche autorisée en lecture seule, zéro document visible et aucune interaction révélant la pièce interne. Aucun partage accordé ; aucun autre compte ou rôle existant modifié.
- Aucune erreur console relevée à la fin du parcours dans l’application. Une expiration temporaire du contrôle d’autorisation de l’outil navigateur a nécessité une nouvelle tentative ; ce n’était pas une erreur du CRM.

Aucun défaut applicatif reproduit dans ce parcours. Ce résultat ne remplace pas une recette complète : XLSX en entrée couvert par les tests API, pas retesté par les clics dans ce lot ; refus des accès directs non autorisés couvert par les tests API ; OAuth, SMTP, Phonetico, signature et rendu responsive non validés ici. Les étapes manuelles ci-dessus restent une checklist réutilisable, et non une déclaration de couverture de tous les modules.
