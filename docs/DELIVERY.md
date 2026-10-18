# Suivi des livraisons CRM AMX

Une fonctionnalité est terminée après vérification, commit, push, PR et fusion dans main. Le cahier des charges métier est CRM_AMX_Cahier_des_charges.docx du 18 octobre 2026.

## Correctifs CallVerify livrés

- PR 4 : nombres Excel avec suffixe .0, première ligne sans en-tête, diagnostic des campagnes sans numéro exploitable, état de ligne principal, badges, exports et séparation du résultat Basic.

## Fonctionnalité 1 — portail et accès aux espaces

Livrable du présent lot : portail de développement /crm, connexion et déconnexion centrales, droits explicites par espace, entrée directe pour un seul espace et sélection pour les comptes multi-espaces. Les tickets sont signés, limités à deux minutes et propres à chaque audience. Les services Assurance et Isolation possèdent des bases séparées et vérifient leurs droits côté API. Assurance ne propose aucune route Twilio.

Les quelques routes de lecture Assurance servent à vérifier le périmètre conseiller ; elles excluent les identifiants internes du setter. Le socle initial était en lecture seule ; la fonctionnalité 3 ajoute l’import. L’édition reste bloquée jusqu’au verrouillage. L’administration des accès initiale était assurée par des commandes serveur ; voir la fonctionnalité 2 pour l’interface livrée ensuite.

Limites de ce lot : l'interface CallVerify historique conserve sa session propre ; la navigation commune vers ses parcours complets n'est pas encore migrée. Les rôles setter/client Isolation n'ont pas encore de routes métier. MFA, invitations et récupération de mot de passe centrales restent à intégrer avant production. Les tickets émis avant une révocation peuvent rester valides jusqu'à deux minutes.

## Fonctionnalité 2 — gestion des utilisateurs et accès

Le portail /crm propose aux administrateurs une liste paginée et une recherche limitée à leurs espaces administrés. Ils peuvent créer un compte avec mot de passe initial validé, associer un compte existant, modifier un rôle et suspendre ou réactiver un accès. Une suspension ne désactive ni le compte global ni ses autres espaces. Les modifications sont auditées sans mot de passe ; les modifications de son propre accès sont interdites. Un superutilisateur central sans rôle explicite ne bénéficie pas d’accès implicite.

Vérification : 15 tests du portail, contrôle TypeScript, build Vite et lecture de l’écran local. Les invitations par e-mail, la récupération, le MFA et l’intégration complète de la session Isolation restent à réaliser. Les tickets déjà délivrés expirent sous deux minutes.

## Fonctionnalité 3 — import brut et consultation des contacts Assurance

Depuis /crm → Assurance, l’administrateur importe un CSV (UTF-8 ou Windows-1252 ; séparateur détecté virgule, point-virgule ou tabulation) ou un XLSX (première feuille). L’aperçu et l’option en-tête précèdent une correspondance explicite téléphone/nom/e-mail. Aucun numéro n’est normalisé, dédoublonné ni envoyé à Twilio. Les textes sont conservés tels que lus, y compris un format de téléphone inhabituel ou un e-mail non validé ; la mise en forme Excel ne constitue pas une valeur et n’est pas reprise. Les formules sont conservées comme texte, jamais calculées.

Limites : 5 Mo, 10 000 lignes, 100 colonnes, 10 000 caractères par cellule. Le téléphone doit être présent ; nom/téléphone limités à 250 caractères et e-mail à 254. Les lignes entièrement vides sont ignorées, les autres rejets indiquent le numéro de ligne physique et le motif. Rapport et historique persistants, réservés aux administrateurs ; rejets téléchargeables en CSV. Colonnes sources et correspondance conservées en interne. Une confirmation rejouée avec le même identifiant et contenu n’insère pas de doublons ; un nouvel import volontaire conserve les doublons métier.

Liste commune paginée et recherche pour les setters, périmètre affecté pour les conseillers, fiche en lecture seule et aucune métadonnée du setter dans les réponses publiques. Les contacts importés ne sont pas affectés, initialement invisibles aux conseillers. Vérification : 18 tests Assurance (dont 5 000 lignes et rollback), TypeScript/build, parcours réel sur fichier fictif et téléchargement du rapport. Deux contacts de démonstration sont présents dans la base locale Assurance ; aucune donnée Isolation modifiée.

La fiche métier complète (champs configurables, notes, interactions, documents), la modification sous verrou et l’affectation des conseillers restent à réaliser.

## Fonctionnalité 4 — prise en charge et modification sous verrou Assurance

Les setters et administrateurs prennent une fiche en charge pendant trois minutes. La consultation par les autres setters reste possible. Chaque acquisition possède un jeton distinct ; renouvellement, sauvegarde et libération exigent le bon utilisateur, le bon jeton et un verrou encore valide. L’expiration permet une nouvelle acquisition. Une version attendue empêche une ancienne sauvegarde d’écraser un changement plus récent, même depuis deux requêtes du même compte. Acquisition et écritures utilisent une mise à jour conditionnelle transactionnelle ; aucune décision de concurrence ne repose sur le navigateur.

Le parcours fonctionnel permet de modifier nom, téléphone et e-mail sans normalisation. Sauvegarde automatique après 1,2 seconde sans saisie, commande d’enregistrement immédiat et libération à la fermeture. Le renouvellement s’effectue toutes les 30 secondes pendant l’activité visible ; après deux minutes sans interaction, il s’arrête et le verrou expire. La fermeture de l’application ou une perte réseau peuvent laisser le verrou jusqu’à son expiration ; un brouillon non sauvegardé reste local à la fiche ouverte. Le déverrouillage forcé est réservé à l’administrateur, avec motif obligatoire. Les prises en charge, libérations, modifications avant/après et interventions administrateur sont auditées ; le journal paginé est réservé aux administrateurs. Les conseillers ne reçoivent aucun identifiant de verrou ni auteur interne et n’ont aucun accès à ces actions.

Vérifications : 27 tests Assurance exécutés sur SQLite ; deux tests supplémentaires de concurrence (acquisitions et sauvegardes simultanées) s’exécutent dans la CI PostgreSQL dédiée. Contrôle TypeScript, build et migration locale. La revue visuelle est reportée à la fin à la demande de l’utilisateur. Statuts métier, champs configurables, notes/documents et affectation multi-conseillers restent dans les lots suivants.

## Fonctionnalité 5 — affectations multi-conseillers Assurance

L’administrateur associe plusieurs conseillers à un setter, consulte les associations avec recherche/pagination, suspend ou réactive une association et consulte son historique. Le couple setter/conseiller est unique. La suspension conserve l’association et ses événements ; une révision attendue interdit d’écraser une modification concurrente. Les setters consultent uniquement leurs propres associations actives. Les conseillers n’ont accès ni à la collection, ni aux détails, ni aux historiques des associations.

Le portail expose aux seuls administrateurs Assurance un annuaire filtré des setters/conseillers actifs. Avant une création ou une réactivation, il vérifie l’état du compte et le rôle Assurance, puis signe une attestation de deux minutes pour ce couple et cet administrateur. Assurance la vérifie avec une finalité distincte des tickets de connexion ; les identifiants transmis sans preuve, preuves altérées, périmées ou émises pour un autre acteur sont refusés. Les bases restent indépendantes et aucun secret de compte n’est transmis. Les suspensions ne requièrent pas de nouvelle attestation, afin de permettre le retrait d’une ancienne association même si un compte a été désactivé.

Les noms stockés sont des instantanés actualisés à la réactivation. Une association active ne constitue pas une preuve permanente qu’un compte central conserve son rôle ; la réservation devra revalider les accès avant d’accepter un conseiller. Une attestation émise juste avant une révocation peut rester valable deux minutes, comme les tickets métier existants. L’affectation ne donne pas à elle seule accès à un dossier prospect : les rendez-vous et leurs droits seront livrés séparément.

Vérifications : tests du portail (annuaire, rôles, révocation, CSRF et attestation), tests Assurance (périmètres, multiples conseillers, doublons, historique, réactivation et rollback), plus création et modification concurrentes sur PostgreSQL dans la CI. TypeScript/build et migration locale ; aucune retouche esthétique ni création de comptes de démonstration pour ce lot.

## Fonctionnalité 6 — rendez-vous Assurance internes

Réservation depuis une fiche prise en charge, avec une attribution active et une confirmation centrale récente des rôles. Un setter réserve pour ses propres attributions ; un administrateur peut réserver pour un setter attribué, en conservant séparément le responsable initial et l’auteur réel de l’opération. Un identifiant de requête rend les nouvelles tentatives de la même réservation idempotentes. Chaque rendez-vous conserve prospect, attribution, conseiller, setter responsable, auteur interne, créneau UTC, fuseau IANA, statut et révision.

Un verrou transactionnel par conseiller et un verrou sur la fiche prospect empêchent les chevauchements internes, y compris entre setters différents ou conseillers différents pour le même prospect. Deux créneaux adjacents sont acceptés. Les dates exigent un décalage explicite cohérent avec le fuseau IANA ; les heures locales inexistantes au changement d’heure sont refusées. Le report et l’annulation exigent un motif interne et une révision courante. Les créneaux précédents, états et auteurs restent dans le journal administrateur. Une attribution suspendue bloque réservation et report, mais autorise encore l’annulation d’un rendez-vous existant.

Liste paginée filtrée par prospect, période et statut : l’administrateur voit tous les rendez-vous, le setter uniquement les siens, le conseiller uniquement ceux qui le concernent. Le conseiller accède aux dossiers liés à ses rendez-vous sans recevoir attribution, identité de setter, auteur, motif libre ou historique interne. Un rendez-vous annulé reste dans son historique et maintient le lien au dossier ; la durée de conservation et la visibilité post-contrat restent à valider avec le client. Les anciennes affectations explicites des dossiers Assurance restent reconnues pendant la transition.

Limite explicite : calendrier interne seulement. Google/Microsoft/Calendly ne sont ni consultés ni synchronisés et aucune disponibilité externe n’est garantie. Les réponses portent calendar=internal. Les comptes rendus Oui/Non, incidents, tâches et notifications seront livrés ensuite ; un rendez-vous passé ne devient jamais automatiquement effectué ou non effectué. Les noms des participants sont conservés à la réservation et l’attestation centrale déjà émise peut rester valable deux minutes après révocation.

Vérifications : tests du portail et Assurance pour les permissions, fuseaux, confidentialité, reports, annulations, idempotence et rollback ; CI PostgreSQL pour les courses réservation/réservation, réservation/report, reprise d’une même requête et conflits sur un prospect entre conseillers. TypeScript/build et migrations. La revue des interfaces reste reportée à la fin ; les commandes du lot sont utilisables sans identifiants d’agenda externe.

## Fonctionnalités suivantes non livrées

1. Gestion et migration complète des comptes, MFA, invitations, récupération et navigation unifiée avec Isolation.
2. Dossiers Isolation, affectations des setters, travail des prospects et suivi des visites.
3. Fiches métier Assurance complètes (import brut, verrouillage et affectations multi-conseillers livrés).
4. Phonetico dans chaque CRM, après validation des opérations réelles du fournisseur.
5. Connecteurs agendas externes, comptes rendus, incidents, tâches et alertes persistantes (rendez-vous internes livrés).
6. Contrats, statistiques métier, sauvegardes externes et déploiement final.

Les prochains éléments seront découpés en fonctionnalités plus petites, chacune avec sa PR fusionnée avant la suivante. Aucun de ces modules n'est déclaré terminé par la présence de son emplacement dans le dépôt.
