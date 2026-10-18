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

## Fonctionnalité 7 — comptes rendus et tâches de suivi Assurance

Le conseiller du rendez-vous renseigne Oui/Non après sa fin et peut signaler un problème dans ce compte rendu. Non ou Problème impose un motif et crée exactement une tâche liée au rendez-vous et au setter initial, indépendamment de l’administrateur qui a réservé. Une répétition identique est idempotente ; une réponse différente ne remplace pas un compte rendu déjà enregistré. Le compte rendu ne peut être saisi pour un rendez-vous futur ou annulé. Une fois renseigné, le rendez-vous ne peut plus être annulé ni reporté pour effacer son résultat.

Les setters consultent uniquement leurs tâches, les administrateurs toutes les tâches, et les conseillers aucune tâche interne. Le tableau de bord compte les tâches ouvertes à chaque chargement : consulter une tâche ne supprime pas l’alerte. La clôture exige une justification et conserve date, auteur et audit. Les tâches comportent motif, priorité normale et échéance initiale à 24 heures, valeur provisoire à valider avec le client. Les listes ouvertes/clôturées sont paginées. L’absence de compte rendu reste un compte rendu à fournir, jamais un résultat Non automatique.

Limites : le signalement est actuellement inclus dans le compte rendu initial ; correction et signalement ultérieur distinct restent à livrer. Pas d’e-mail envoyé, de relance planifiée, de personnalisation de priorité/échéance ou d’escalade dans ce lot. Les notifications e-mail minimales seront intégrées séparément. La revue esthétique reste reportée à la fin. Tests de permissions, idempotence, rollback, alertes et clôture justifiée ; concurrence de soumission testée sur PostgreSQL dans la CI.

## Fonctionnalité 8 — priorité et échéance des tâches

L’administrateur peut replanifier une tâche ouverte : priorité basse/normale/haute/urgente, échéance future avec décalage ISO 8601 explicite et motif obligatoire. Une révision attendue protège les modifications simultanées ; une tâche clôturée ne peut plus être replanifiée. L’historique paginé, réservé à l’administration, conserve les valeurs avant/après, le motif et l’auteur. Les setters voient les nouvelles priorités/échéances de leurs tâches sans pouvoir les changer. Un indicateur signale les tâches en retard sans les clôturer ni retirer les alertes.

L’échéance initiale reste 24 heures et la priorité normale ; la règle automatique globale, les escalades et notifications e-mail restent à livrer. Six tests fonctionnels supplémentaires et un test PostgreSQL de modifications concurrentes, TypeScript/build et migration locale. Revue esthétique reportée à la fin.

## Fonctionnalité 9 — signalements ultérieurs et reprise du suivi

Après son compte rendu initial, le conseiller du rendez-vous peut ajouter des signalements horodatés distincts. Le compte rendu reste inchangé. Une même requête rejouée est idempotente ; un identifiant réutilisé avec un autre contenu est refusé. Les signalements sont paginés, limités au périmètre du rendez-vous et ne contiennent aucun auteur/setter interne dans leurs réponses publiques.

Chaque rendez-vous conserve au maximum une tâche de suivi. Un nouveau signalement crée cette tâche si nécessaire, conserve la tâche ouverte existante ou rouvre une tâche clôturée avec une nouvelle échéance à 24 heures. Ancienne clôture, résolution et révision sont conservées dans l’audit. Le setter voit le dernier signalement sur sa tâche ; l’administration dispose de l’historique complet. La clôture exige désormais la révision courante afin qu’un ancien formulaire ne puisse clôturer un nouveau signalement par inadvertance. Priorité et échéance existantes sont conservées quand la tâche était déjà ouverte ; priorité conservée à la réouverture.

Vérifications : tests de permissions, conservation du compte rendu, idempotence, réouverture, clôture périmée, audit/rollback et concurrence PostgreSQL. TypeScript/build et migration locale. Les notifications e-mail et règles automatiques d’escalade restent à livrer ; la revue visuelle reste reportée à la fin.

## Fonctionnalité 10 — règles de suivi configurables

L’administrateur Assurance configure le délai initial des nouvelles tâches, la priorité initiale et le délai de réouverture, avec motif obligatoire et contrôle de version. Délais bornés de 1 à 720 heures écoulées ; pas de calcul en jours ouvrés. Les valeurs initiales restent 24 heures et priorité normale tant qu’aucune règle n’est enregistrée. Les modifications sont auditées dans un historique paginé réservé à l’administration.

Les tâches ouvertes conservent leur planification et leur priorité, même après changement de règle. La réouverture utilise le délai configuré au moment du signalement tout en conservant la priorité de la tâche. Chaque tâche conserve en interne la révision de la règle appliquée. Tests des droits, bornes, anciennes versions, absence de modification rétroactive, création/réouverture et rollback ; concurrence PostgreSQL testée en CI, TypeScript/build et migration locale. Notifications e-mail et escalades restent à livrer ; aucun envoi n’est activé.

## Fonctionnalité 11 — notes horodatées des fiches Assurance

Ajout de notes conservées chronologiquement, paginées et liées au prospect. Le canal est choisi côté serveur : notes internes pour setters/administrateurs et notes conseiller pour ce rôle. L’administrateur consulte toutes les notes avec leurs auteurs internes ; les setters consultent les notes internes communes, chaque conseiller seulement ses propres notes sur ses dossiers autorisés. Aucun auteur de note interne ni contenu interne n’est transmis au conseiller.

Les notes internes nécessitent une prise en charge valide ; les notes du conseiller sont des ajouts indépendants qui ne modifient pas la fiche partagée. Les notes sont limitées à 5 000 caractères, conservées sans modification ou suppression par API ; un complément ou une correction s’ajoute sous forme de nouvelle note. Un identifiant de requête rend les reprises idempotentes. L’ajout est audité transactionnellement ; aucune donnée ne reste créée si l’audit échoue. La politique de partage avec les setters est volontairement restrictive pour les notes conseiller et pourra être précisée lors de la recette métier.

Vérifications : permissions, confidentialité entre canaux et conseillers, idempotence, limites, conservation et rollback ; test PostgreSQL de soumissions simultanées, TypeScript/build et migration locale. Champs configurables, documents, messagerie et revue finale des interfaces restent à réaliser.

## Fonctionnalité 12 — statistiques opérationnelles Assurance

Statistiques filtrées sur une période de 366 jours maximum, selon le début actuel du rendez-vous en UTC (bornes de dates incluses). Valeurs globales pour l’administrateur et ventilation paginée par setter responsable initial ; le setter ne voit que ses propres totaux, sans annuaire ni identités d’autres setters. Les conseillers n’ont pas accès à ce rapport interne.

Compteurs : rendez-vous, annulations, rendez-vous à venir, comptes rendus, Oui, Non, comptes rendus manquants après échéance, comptes rendus avec problème, signalements ultérieurs, tâches ouvertes/en retard/clôturées. Les agrégats distincts empêchent les signalements multiples de multiplier les rendez-vous ou tâches. Le taux effectué est Oui / comptes rendus renseignés ; il reste non calculable en l’absence de réponses, et n’est ni un taux de conversion contrat ni une déduction de présence. Une absence de compte rendu n’est jamais assimilée à Non.

Les tâches reflètent leur état actuel sur les rendez-vous de la période. Un report peut déplacer un rendez-vous vers une autre période ; il ne s’agit pas d’un journal historique figé. Les noms de setters sont le dernier instantané de réservation disponible. Appels Phonetico, contrats, ventes, exports statistiques et rapports Isolation ne sont pas comptabilisés dans ce lot. Six tests ciblés, suites SQLite/PostgreSQL en CI, TypeScript/build ; aucune migration nécessaire, revue esthétique différée.

## Fonctionnalité 13 — exports Excel et CSV des statistiques Assurance

Téléchargement depuis les statistiques avec les dates saisies et les mêmes autorisations serveur. Le classeur Excel propose une synthèse lisible et un onglet détaillé pour l’administration ; le setter ne reçoit que sa propre synthèse. CSV UTF-8 avec BOM, séparateur point-virgule et en-têtes français. Période UTC, date de calcul et définition du taux accompagnent les exports. Les valeurs non calculables restent explicitement indiquées, sans faux zéro.

L’export administrateur comprend tous les setters de la période, indépendamment de la page affichée, avec plafond explicite de 5 000 setters. Les noms dangereux sont neutralisés en CSV et stockés comme texte en Excel pour éviter les formules exécutables. Aucun prospect, coordonnée, note ou auteur d’interaction n’est exporté. Chaque export est audité, réponse non mise en cache. Les chiffres sont recalculés au moment du téléchargement et peuvent évoluer depuis l’affichage.

Douze tests ciblés statistiques/exports réussis, dont confidentialité, complétude au-delà de 25 lignes, lecture réelle du XLSX et neutralisation des formules ; suites complètes SQLite/PostgreSQL en CI, TypeScript/build. Aucune migration nécessaire. Revue esthétique reportée à la fin ; statistiques ventes/Phonetico/Isolation non incluses.

## Fonctionnalité 14 — champs personnalisables des fiches Assurance

L’administration définit jusqu’à 30 champs internes : texte (2 000 caractères), case à cocher, date ou liste de choix. Clé unique et stable, libellé, obligation et état actif configurables ; type et choix sont immuables une fois créés. L’archivage désactive la saisie tout en conservant les anciennes valeurs. Les mises à jour de configuration exigent une révision courante et un motif ; elles sont auditées.

Les setters et administrateurs renseignent les champs sur une fiche prise en charge, avec contrôle du jeton, de l’expiration, de la version de fiche et de configuration. Les champs obligatoires s’appliquent à l’enregistrement explicite de l’ensemble des champs métier actifs, sans bloquer les imports bruts ni la correction des coordonnées. Les dates, types, choix et clés sont validés côté serveur ; une case obligatoire exige une valeur booléenne renseignée et accepte Non. Les valeurs archivées sont conservées même lors d’une nouvelle saisie. Les modifications avant/après sont consultables dans le journal administrateur de la fiche.

Aucun schéma ni valeur personnalisée n’est exposé au conseiller ou aux exports existants. La saisie métier possède un enregistrement explicite distinct de la sauvegarde automatique des coordonnées ; une modification concurrente exige de recharger avant de reprendre. Import/mapping des champs personnalisés, partage sélectif conseiller et changements de type ne font pas partie de ce lot. Sept tests ciblés, concurrence PostgreSQL, TypeScript/build et migration locale. Revue visuelle reportée à la fin.

## Fonctionnalité 15 — documents privés des fiches Assurance

Dépôt, liste paginée et téléchargement de PDF, PNG et JPEG de 5 Mo maximum par fichier. Les documents internes sont accessibles aux setters et à l’administration ; les conseillers ne voient que leurs propres documents sur leurs dossiers autorisés. L’administration peut consulter les deux canaux. Le serveur impose ces permissions sur la liste comme sur chaque téléchargement, sans URL publique ni métadonnées internes exposées au conseiller.

Le dépôt interne exige une prise en charge valide. Un identifiant de requête et une empreinte SHA-256 rendent les nouvelles tentatives idempotentes et refusent la réutilisation avec un autre contenu. Documents append-only, téléchargements audités, réponses privées non mises en cache et téléchargement forcé avec protection nosniff. Les octets, métadonnées et audit sont enregistrés dans une même transaction de la base Assurance ; aucune pièce n’est placée dans Git ou servie comme fichier statique.

La vérification porte sur extension, signature et taille ; elle ne constitue pas une analyse antivirus ni une validation complète des fichiers. Le stockage binaire augmente le volume de la base et de ses sauvegardes ; quotas par dossier, antivirus, suppression/rétention réglementaire, partage sélectif et stockage objet restent à définir avant déploiement à grande échelle. Cinq tests couvrent permissions, téléchargements, idempotence, refus des fichiers et annulation transactionnelle si l’audit échoue ; suites complètes et CI PostgreSQL, typage et compilation. Migration 0013. Revue esthétique différée.

## Fonctionnalité 16 — pipeline commercial Assurance

Statuts configurables depuis « Statuts et champs métier » : clés stables, libellés, ordre et archivage, jusqu’à 30 étapes. Les onze étapes initiales reprennent le cahier des charges : à contacter, en cours, à rappeler, intéressé, RDV réservé, RDV effectué, incident, suivi, mandat, contrat, clôturé. Le statut initial to_contact reste actif pour les imports. Les clés existantes ne peuvent pas être supprimées ; l’archivage conserve les fiches concernées et les rend filtrables dans la liste. Le paramétrage exige un administrateur, une révision courante et un motif, avec audit avant/après.

Depuis une fiche prise en charge, setter ou administrateur choisit explicitement un statut actif et renseigne un motif. Jeton, expiration, version de fiche et version du pipeline sont vérifiés dans une transaction ; les changements concurrents ne peuvent pas s’écraser. Le journal administrateur conserve auteur, date, ancien/nouveau statut, libellé et justification. Le conseiller consulte seulement le statut/libellé de ses dossiers autorisés, sans auteur ni motif interne, et ne peut pas les modifier. La liste permet la recherche combinée au filtre de statut.

Les statuts sont commerciaux et manuels : aucune création automatique de compte rendu, tâche, mandat ou contrat, aucune déduction d’un résultat de rendez-vous. Les changements entre étapes actives sont libres sous verrou ; clôturer ne supprime pas une fiche et ne bloque pas sa reprise autorisée. Le cycle contractuel, règles de transition conditionnelles, automatisations et vue Kanban ne sont pas livrés dans ce lot. Six tests fonctionnels et un test de concurrence PostgreSQL, suite Assurance complète, typage/build et migration 0014. Revue esthétique différée.

## Fonctionnalité 17 — réouverture administrative des tâches Assurance

L’administrateur peut rouvrir une tâche clôturée depuis les listes « Clôturées » ou « Toutes ». Un motif, une priorité et une échéance future avec décalage ISO 8601 explicite sont obligatoires. La même tâche reste liée au rendez-vous et au setter responsable ; aucun doublon ni changement du compte rendu n’est créé. La réouverture efface les champs de clôture courants, incrémente la révision et rétablit la tâche dans la liste ouverte et le compteur d’alertes au prochain chargement.

Le journal administrateur conserve l’auteur et le motif de réouverture, l’ancienne date/auteur/justification de clôture et les valeurs avant/après. Les historiques antérieurs restent intacts, même après une nouvelle clôture. Une révision attendue et une écriture conditionnelle empêchent deux administrateurs de rouvrir simultanément la même version, ou un ancien formulaire de clôturer la tâche réouverte. Échec d’audit et modification sont annulés ensemble. Ni setter ni conseiller ne peuvent rouvrir une tâche ou lire cet historique interne.

Réouverture manuelle uniquement : la priorité et l’échéance explicites remplacent celles de la tâche, sans réappliquer automatiquement la politique globale. La réattribution à un autre setter, les e-mails et rappels planifiés restent à livrer. Six tests fonctionnels et un test PostgreSQL de réouvertures concurrentes, suite Assurance, TypeScript/build ; aucune migration nécessaire. La revue esthétique reste différée.

## Fonctionnalité 18 — réattribution des tâches Assurance

L’administrateur choisit un setter Assurance actif dans l’annuaire central paginé et justifie le transfert d’une tâche ouverte. Le portail vérifie le compte et son rôle, puis émet une attestation de deux minutes liée au setter cible, à l’administrateur et à la tâche. Assurance vérifie sa signature, sa finalité et sa durée sans consulter la base du portail. Comptes suspendus, autres rôles, preuves altérées/périmées ou liées à un autre acteur/dossier de tâche sont refusés. Une attestation déjà délivrée peut rester valide jusqu’à deux minutes après révocation.

Seule la responsabilité actuelle de la tâche change ; priorité, échéance, rendez-vous et setter d’origine sont conservés. La tâche sort du périmètre de l’ancien responsable et entre dans celui du nouveau, avec le compteur d’alertes recalculé au chargement. Le nouveau responsable peut la clôturer ; un ancien formulaire, même avec une révision devinée, ne peut plus écrire après transfert. Les réouvertures et nouveaux signalements conservent le responsable actuel. Transférer une tâche ne donne pas accès aux autres rendez-vous du setter d’origine.

La révision attendue et une écriture conditionnelle protègent transferts/clôtures concurrents. L’audit administrateur conserve avant/après, origine, nom cible attesté, acteur et motif, sans exposition aux conseillers. Les statistiques restent regroupées selon le setter d’origine du rendez-vous ; elles ne constituent pas une mesure de la charge actuelle des tâches, distinction indiquée dans la définition et les exports. Une tâche clôturée doit être rouverte avant transfert. Aucun e-mail ni transfert en masse dans ce lot.

Huit tests métier, quatre tests du portail et deux tests de concurrence PostgreSQL ajoutés ; suites Assurance/portail, typage et compilation. Aucune migration nécessaire, revue esthétique différée.

## Fonctionnalité 19 — affectations et file de prospects Isolation

Depuis le portail /crm, l’administrateur Isolation consulte les prospects existants de toutes les campagnes, recherche par nom/téléphone/référence et filtre par responsable ou absence d’affectation. Il attribue un prospect à un setter, le transfère ou retire son affectation avec motif obligatoire. L’annuaire central est paginé et limité aux setters Isolation actifs. Une attestation signée, liée à l’administrateur, au prospect et au setter cible, expire sous deux minutes. Les noms sont des instantanés de l’attestation ; la révocation centrale empêche les nouvelles attestations/tickets, mais ceux déjà émis peuvent rester valables deux minutes.

Le setter arrive directement dans sa file, paginée et recherchable, et ne consulte que ses prospects actuellement attribués, y compris par accès direct à l’API. Un transfert ou retrait coupe son accès au prochain chargement. La fiche de consultation expose une liste de champs explicite : coordonnées disponibles, campagne, validité de format, état technique déjà stocké et responsable. Aucun appel, Lookup ni normalisation supplémentaire n’est déclenché. Aucune identité locale d’administrateur n’est créée pour les setters : les identifiants centraux restent distincts des comptes historiques.

Les nouvelles routes de travail ont leur propre authentification par ticket Isolation et leurs contrôles serveur. Les anciens endpoints d’administration, imports, Lookup, appels et exports restent interdits aux setters. Le rôle client n’accède pas encore à cette file. Révision attendue et mise à jour conditionnelle empêchent deux affectations concurrentes de s’écraser ; audit et affectation sont atomiques. L’administration consulte l’historique avec acteur central, valeurs avant/après et motif. Aucune modification des imports, doublons techniques ou résultats Lookup existants.

Limites : affectations unitaires, consultation uniquement côté setter. Qualification commerciale, notes, rappels, appels Phonetico, visites, portail client et affectations en masse restent à livrer. L’interface historique conserve sa session distincte pour l’administration des imports/Twilio. Six tests métier et un test de concurrence PostgreSQL ajoutés, quatre tests du portail, suites Isolation/portail et CI Assurance, TypeScript/build. Migration Isolation 0007 appliquée localement ; CI PostgreSQL étendue à la concurrence Isolation. Revue esthétique différée.

## Fonctionnalité 20 — observations commerciales et rappels Isolation

Le setter sur ses prospects attribués, ou l’administrateur Isolation sur tout prospect, ajoute une note ou un résultat commercial : à contacter, en cours, à rappeler, intéressé, non intéressé, non joint. Chaque observation exige un texte et reste dans un historique paginé avec date, identifiant central et rôle de l’auteur. Les résultats commerciaux sont distincts de la validité de format, de l’état de ligne et des résultats Lookup/Voice : non joint ne signifie pas numéro invalide et aucune vérification ni appel réel n’est déclenché.

Le résultat À rappeler exige une date future avec décalage ISO 8601 explicite. Les rappels à échéance possèdent un compteur persistant recalculé au chargement et un filtre de file ordonné du plus ancien au plus récent. Leur consultation ne les efface pas. Une note laisse le rappel inchangé ; une qualification peut le reprogrammer ou le retirer en choisissant un autre résultat, avec ancienne date et état conservés dans l’historique. Le transfert d’un prospect transfère aussi son rappel courant au nouveau responsable.

Une version commune protège observations et affectations ; chaque sauvegarde revérifie le responsable dans l’écriture conditionnelle, même si le transfert intervient après la lecture initiale. L’identifiant de requête et une empreinte rendent les nouvelles tentatives identiques idempotentes et empêchent les doublons. Une tentative concurrente avec une version dépassée peut demander un rechargement ; les observations enregistrées ne sont jamais remplacées. En cas d’échec d’audit, qualification, rappel, note et version sont annulés ensemble. L’ancien setter perd aussi l’accès aux historiques après réattribution. Les administrateurs et les prochains clients autorisés Isolation pourront retracer les auteurs ; le portail client n’est pas livré dans ce lot.

Limites : un seul rappel courant par prospect, statuts initiaux fixes, pas de planification de plusieurs tâches, de notification e-mail, d’appel ni de visite. L’identité de l’auteur est conservée par identifiant central et rôle ; aucun compte administrateur local n’est créé pour représenter un setter. Huit tests fonctionnels et deux tests PostgreSQL ajoutés ; 82 tests Isolation locaux dont trois réservés à PostgreSQL, CI complète, typage et compilation. Migration 0008 appliquée localement. Revue esthétique différée.

## Fonctionnalité 21 — réservation et suivi des visites Isolation internes

Réservation depuis un prospect attribué à un setter, liste paginée globale ou par prospect, consultation, report et annulation justifiés. Le portail revalide le setter actif et exige exactement un client Isolation actif, conformément au lancement mono-client. L’attestation signée est propre à la réservation, liée au prospect et à l’acteur, valable deux minutes ; le setter ne peut en obtenir que pour lui-même. L’administrateur peut réserver pour le responsable du prospect, en conservant distinctement l’auteur réel et le setter d’origine.

Les visites conservent prospect, client et setter d’origine avec instantanés de noms, auteur de réservation, dates UTC, fuseau IANA, statut et révision. L’identifiant de requête rend les reprises de réservation idempotentes. Les dates exigent un décalage cohérent avec le fuseau, y compris aux changements d’heure. Le calendrier interne réserve une seule visite simultanée par client ; il empêche aussi les chevauchements pour un même prospect, tout en acceptant des créneaux adjacents. Un verrou transactionnel par client et une écriture sur le prospect protègent réservations et reports concurrents.

Le setter consulte et gère uniquement les visites des prospects actuellement attribués. Un transfert déplace ce périmètre sans réécrire le setter d’origine de la visite. Le report revalide les participants et conserve le client ; l’annulation reste possible par l’administration même après retrait de l’affectation. Toute modification incrémente la version commune du prospect. Les révisions de visite empêchent les reports/annulations périmés ; les visites commencées ne sont plus réécrites par ces commandes. L’historique administrateur conserve chaque créneau, motif, statut et acteur. Audit et mutations sont atomiques.

Calendrier strictement interne (calendar=internal) : ni disponibilités ni synchronisation Google/Microsoft/Calendly garanties, aucun e-mail envoyé. La réservation ne change pas automatiquement le résultat commercial ou le rappel du prospect. Le portail client et les résultats des visites restent à livrer ; une visite passée reste planifiée en l’absence de résultat, jamais déclarée effectuée par déduction. Les tickets/attestations déjà délivrés peuvent subsister deux minutes après révocation. Dix tests fonctionnels, trois tests PostgreSQL de concurrence et quatre tests portail ajoutés ; suites Isolation/portail, CI Assurance, typage/build. Migration 0009 appliquée localement. Revue esthétique différée.

## Fonctionnalité 22 — portail client Isolation et résultats des visites

Le compte client Isolation entre dans son espace depuis /crm avec sa session centrale. Il consulte uniquement les visites portant son identifiant client et les dossiers liés à ces visites, avec recherche/pagination et une liste explicite de coordonnées. Le nom et l’identifiant du setter d’origine restent visibles sur la visite, conformément à la confidentialité propre à Isolation. Les visites et dossiers d’un autre client restent inaccessibles, même par URL directe ; aucun accès aux imports, Lookup, exports administratifs, file setter ou journal interne n’est ouvert au client.

Le tableau de bord affiche les visites à venir, résultats enregistrés et résultats encore attendus après la fin d’une visite non annulée. Le filtre « résultats à renseigner » et le compteur persistent après consultation. Le client concerné renseigne Oui/Non, un résultat cohérent (effectuée, suivi nécessaire, intéressé, non intéressé, non effectuée) et un commentaire obligatoire. Une absence de réponse reste un résultat manquant, jamais un Non déduit automatiquement. L’administration et le setter actuellement responsable du prospect peuvent consulter le résultat, mais ne le remplissent pas à la place du client.

Le premier résultat est conservé avec identifiant client et date ; une répétition identique est idempotente, une réponse différente ne remplace pas l’historique. Une révision de visite et un verrou transactionnel empêchent les réponses concurrentes de s’écraser. Une visite future, annulée ou modifiée entre-temps ne peut pas recevoir un résultat ; une visite déjà renseignée ne peut plus être reportée/annulée pour effacer son issue. Audit, résultat et incrément de version sont atomiques. Un transfert du prospect change le périmètre setter sans réécrire le setter d’origine ni retirer au client son résultat.

Limites : calendrier externe, statistiques détaillées par setter, partage de notes commerciales/historique interne, compléments/corrections des résultats et suivi automatique restent à livrer. Les dossiers liés à des visites annulées restent consultables dans l’historique client ; les durées de conservation doivent être cadrées avant production. Aucun résultat de visite ne modifie les états techniques des numéros ou ne crée automatiquement un contrat. Dix tests fonctionnels et deux tests PostgreSQL ajoutés ; 107 tests Isolation locaux dont huit réservés à PostgreSQL, typage/build et CI complète. Migration 0010 appliquée localement. Revue esthétique différée.

## Fonctionnalité 23 — statistiques des visites Isolation

Statistiques consultables dans les espaces administrateur, setter et client Isolation, sur une période de 366 jours maximum selon le début actuel des visites en UTC. Compteurs : visites réservées, prospects distincts liés à ces visites, annulations, visites à venir, résultats renseignés, Oui, Non, résultats manquants, intéressés, non intéressés et suivi nécessaire. Le taux effectué est Oui / résultats renseignés ; le taux d’intérêt est intéressés / visites effectuées. Sans dénominateur les taux restent non calculables ; un résultat manquant ne devient pas Non.

L’administration dispose des totaux et d’une ventilation paginée par setter d’origine. Le client voit uniquement ses visites, totaux et ventilation ; les noms de setters sont tirés de ses seules visites autorisées. Le setter reçoit uniquement les totaux de ses réservations dont il conserve actuellement le prospect : un transfert retire les visites de son périmètre statistique, sans réécrire leur origine dans les statistiques administrateur/client. Cette limite protège les dossiers retirés ; ces chiffres ne sont pas un classement historique exhaustif du setter. Les noms sont les derniers instantanés de réservation du périmètre autorisé. Les prospects distincts par groupe ne s’additionnent pas nécessairement au total global.

Les filtres de permissions s’appliquent avant chaque agrégat et avant la recherche du nom ; aucun téléphone, note, résultat libre ou dossier individuel n’est exposé dans les statistiques. Réponses non mises en cache. Un report déplace une visite entre périodes et les résultats reflètent l’état actuel, pas une photographie historique. Appels Phonetico, ventes, contrats, contacts sans visite, exports et statistiques d’activité commerciale restent hors de ce lot. Sept tests ciblés, suite Isolation et CI PostgreSQL, typage et build ; aucune migration nécessaire. Revue esthétique différée.

## Fonctionnalité 24 — exports Excel et CSV des statistiques Isolation

Téléchargement des statistiques selon les dates saisies et les mêmes périmètres serveur que l’affichage. L’administration exporte les totaux et tous les setters ; le client uniquement les agrégats de ses visites et leurs setters d’origine ; le setter uniquement sa synthèse autorisée, sans liste d’autres setters. La pagination affichée ne limite pas les exports. Plafond explicite de 5 000 setters par export, à réduire en restreignant la période si nécessaire.

Le classeur Excel comprend une synthèse avec libellés français, période UTC, date de calcul et définition des indicateurs, puis un onglet filtrable par setter lorsqu’il existe des groupes autorisés. CSV UTF-8 avec BOM, séparateur point-virgule et en-têtes français. Les taux sans dénominateur restent « Non calculable ». Les noms pouvant devenir des formules sont neutralisés en CSV et forcés en texte en Excel. Aucun téléphone, dossier individuel ni note libre n’est exporté.

Les téléchargements sont audités avec acteur central, période, format et rôle ; réponses sans cache, en pièce jointe et nosniff. Les chiffres sont recalculés à chaque téléchargement : un report ou une réattribution peut changer le résultat depuis la dernière consultation. Les définitions et limites de la fonctionnalité 23 restent valables, notamment le périmètre du setter après transfert et les prospects distincts non additionnables entre groupes. Cinq tests dédiés avec lecture réelle des CSV/XLSX, confidentialité, complétude sur 27 setters, neutralisation des formules et refus d’accès ; suite Isolation/CI PostgreSQL et typage/build. Aucune migration nécessaire, revue esthétique différée.

## Fonctionnalité 25 — compléments aux résultats des visites Isolation

Le client concerné peut ajouter des précisions après le résultat initial d’une visite. Les compléments sont distincts, horodatés, paginés et conservés avec l’identifiant client ; aucun ne modifie ou ne supprime le résultat initial, son issue commerciale ou les statistiques. La lecture est autorisée au client de la visite, au setter actuellement responsable du prospect et à l’administration, avec les mêmes contrôles par URL que les visites. Un transfert retire la lecture à l’ancien setter sans effacer les contributions.

Chaque ajout exige un texte de 3 000 caractères maximum et un identifiant de requête unique. Une reprise identique retourne le complément existant ; la réutilisation avec un autre contenu ou une autre visite est refusée. Le verrou de visite sérialise les ajouts simultanés ; complément et audit sont transactionnels. Le journal administrateur conserve l’auteur central et la référence du complément. Aucun résultat absent ne peut recevoir de complément, ni setter ou administrateur écrire à la place du client.

Cinq tests fonctionnels et un test de concurrence PostgreSQL ajoutés : permissions, idempotence, historique/pagination, résultat conservé et annulation si l’audit échoue. Suite Isolation, typage/build et CI complète ; migration 0011 appliquée localement. Limites : précisions textuelles uniquement, aucune correction structurée du résultat, notification ou tâche automatique ; revue esthétique différée.

## Fonctionnalités suivantes non livrées

1. Gestion et migration complète des comptes, MFA, invitations, récupération et navigation unifiée avec Isolation.
2. Statistiques et suivi métier Isolation, partage autorisé des interactions et affectations en masse (portail client, résultats, file setter, qualification, notes, rappels et visites internes livrés).
3. Fiches métier Assurance complètes (import brut, verrouillage et affectations multi-conseillers livrés).
4. Phonetico dans chaque CRM, après validation des opérations réelles du fournisseur.
5. Connecteurs agendas externes, notifications e-mail et règles de relance (comptes rendus, signalements et tâches persistantes livrés).
6. Contrats, statistiques métier, sauvegardes externes et déploiement final.

Les prochains éléments seront découpés en fonctionnalités plus petites, chacune avec sa PR fusionnée avant la suivante. Aucun de ces modules n'est déclaré terminé par la présence de son emplacement dans le dépôt.
