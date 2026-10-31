# Suivi des livraisons CRM AMX

## Isolation V2 â€” tenue, vente et rappel setter (lot 5)

Le formulaire client pose deux questions distinctes sans prÃ©sÃ©lection : visite tenue et vente
conclue. Les notes sont facultatives ; une vente sans prÃ©sence est refusÃ©e. Les anciens appels
API sans champ vente conservent un rÃ©sultat commercial inconnu. Le client peut corriger avec
rÃ©vision et motif ; les anciennes valeurs restent dans lâ€™audit. Le reprÃ©sentant affectÃ© conserve
son parcours dÃ©jÃ  versionnÃ© et applique les mÃªmes rÃ¨gles de suivi.

Une non-tenue crÃ©e un seul rappel sous 24 h liÃ© Ã  cette occurrence et notifie le setter responsable
actuel du prospect, conformÃ©ment Ã  la propriÃ©tÃ© des suivis existants. AprÃ¨s transfert du prospect,
les tÃ¢ches suivent son nouveau responsable ; lâ€™attribution statistique de la visite reste celle du
setter dâ€™origine. Les visites non tenues ne bloquent plus la rÃ©apparition dans la file active.
Une nouvelle correction nÃ©gative aprÃ¨s traitement peut rouvrir le mÃªme suivi en conservant
lâ€™ancienne rÃ©solution dans lâ€™audit. Une correction positive ne clÃ´ture pas automatiquement une
tÃ¢che dÃ©jÃ  ouverte. Les notifications sont privÃ©es ; leur lecture ne change aucun rÃ©sultat ni tÃ¢che.

VÃ©rifications : Oui/Non et vente indÃ©pendante, vente sans prÃ©sence refusÃ©e, notes vides, rejeux,
corrections motivÃ©es/auditÃ©es, rappel unique et rÃ©ouverture, atomicitÃ©, file active et notifications
entre setters. Les notifications/courriels client de rÃ©servation et les relances automatiques
restent le prochain lot ; aucun SMS ni rÃ©munÃ©ration Isolation nâ€™est annoncÃ© par ce lot.

## Isolation V2 â€” publication Google avec Ã©tat confirmÃ© (lot 4)

Le nouveau formulaire demande une publication Google : le contrÃ´le final requiert un compte
Google connectÃ© et la publication explicitement activÃ©e par le client. Lâ€™intention de visite
est conservÃ©e en base avec Ã©tat Â« en cours Â» avant lâ€™appel fournisseur. Le navigateur demande
ensuite sa publication avec une preuve signÃ©e liÃ©e Ã  la visite ; le worker existant reprend
Ã©galement les intentions si le navigateur se ferme. Le compte rendu Google est retransmis au
CRM par Ã©change serveur signÃ© et lâ€™interface distingue en cours, confirmÃ©, retirÃ© et Ã  vÃ©rifier.
Une visite nâ€™est jamais annoncÃ©e confirmÃ©e dans Google sur un simple enregistrement local.

Le moteur existant conserve une clÃ© de crÃ©ation persistante, recherche le mÃªme Ã©vÃ©nement lors
dâ€™une reprise et ne crÃ©e pas aveuglÃ©ment un second Ã©vÃ©nement aprÃ¨s rÃ©ponse incertaine. Il revÃ©rifie
les occupations avant Ã©criture et protÃ¨ge les Ã©vÃ©nements modifiÃ©s hors Orvia. Les retours de
publication vÃ©rifient client, rÃ©vision et horodatage ; une rÃ©ponse obsolÃ¨te ne confirme pas une
visite annulÃ©e ou modifiÃ©e. Le retour serveur a lieu aprÃ¨s libÃ©ration des verrous fournisseur.
Les anciens parcours API internes restent compatibles et identifiables comme internes. Assurance
ne publie toujours pas les rÃ©servations effectuÃ©es via un lien externe.

VÃ©rifications : intention/rejeu, preuve liÃ©e, statut sans preuve refusÃ©, mauvaise rÃ©vision/client,
annulation et horodatage, reprise aprÃ¨s rÃ©ponse incertaine avec mÃªme clÃ©, Google et activation
requises, publication aprÃ¨s sauvegarde et absence de double rÃ©servation frontend. Fournisseurs
simulÃ©s, aucune crÃ©ation rÃ©elle dans lâ€™agenda du client pendant les tests.
Limites : une rÃ©ponse fournisseur incertaine peut nÃ©cessiter une vÃ©rification manuelle ; aucune
transaction atomique commune entre Google et les bases. Notifications/courriels et autres lots V2
restent Ã  livrer ; ce lot ne constitue pas la V2 complÃ¨te.

## Isolation V2 â€” horaires du client et crÃ©neaux de lâ€™agenda (lot 3)

Le menu client expose Â« Agenda et disponibilitÃ©s Â» avec ses connexions personnelles et des plages
hebdomadaires au QuÃ©bec. Lâ€™administration peut rÃ©gler les horaires, mais ne connecte pas lâ€™agenda
personnel du client. Aucun reprÃ©sentant ne connecte dâ€™agenda (prÃ©cision utilisateur). Le client
reste unique ; les reprÃ©sentants restent affectÃ©s aux visites dans le CRM.

Les plages sont versionnÃ©es et auditÃ©es, limitÃ©es Ã  28, sans chevauchement ni traversÃ©e de minuit.
Lorsque la restriction est active, les jours sans plage sont fermÃ©s. Par compatibilitÃ©, elle est
dÃ©sactivÃ©e tant que le client nâ€™a pas choisi ses horaires ; aucun horaire rÃ©el nâ€™est inventÃ©.
Une rÃ©servation ou un report vÃ©rifie ces plages sous verrou et les rendez-vous existants ne
sont pas dÃ©placÃ©s lors dâ€™un changement dâ€™horaires.

Le sÃ©lecteur de crÃ©neaux setter interroge maintenant le compte connectÃ© par Ã©change serveur
signÃ©, puis combine uniquement les pÃ©riodes occupÃ©es avec les rÃ©servations Orvia et horaires
fermÃ©s. PÃ©riode limitÃ©e Ã  sept jours, aucune information privÃ©e dâ€™Ã©vÃ©nement. Absence de connexion,
erreur fournisseur ou rÃ©ponse invalide empÃªchent lâ€™affichage de crÃ©neaux libres. Le contrÃ´le
final existant est conservÃ©. Lâ€™ancien GET de disponibilitÃ© interne reste compatible ; le nouveau
parcours utilise le POST attestÃ©. Documentation API consultÃ©e :
https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query

VÃ©rifications : client/admin vs setter, rÃ¨gles de plage et rÃ©vision, audit atomique, rÃ©servation
hors horaires, crÃ©neaux externes signÃ©s et erreurs, absence de connexion et pÃ©riode bornÃ©e,
contrat du pont serveur sans donnÃ©es privÃ©es ; Ã©dition et conflit frontend, calendrier existant.
Limites : agenda principal du client seulement ; publication fiable de la visite dans Google,
notifications/courriels et autres lots V2 restent Ã  livrer. Aucun appel rÃ©el Ã  un agenda client
nâ€™est dÃ©clenchÃ© par ces tests simulÃ©s. La V2 nâ€™est pas dÃ©clarÃ©e terminÃ©e.

## Isolation V2 â€” qualification prÃ©remplie et Ã¢ge facultatif (lot 2)

Lâ€™Ã¢ge est facultatif lors de la programmation ; sâ€™il est renseignÃ©, ses bornes 0â€“120 restent
contrÃ´lÃ©es. Le coÃ»t dâ€™Ã©lectricitÃ© reste numÃ©rique facultatif. Les autres champs requis et
les valeurs Oui/Non inconnues ne sont pas inventÃ©s.

La qualification propose les coordonnÃ©es connues, ainsi que lâ€™adresse, la ville et le code
postal disponibles sur la premiÃ¨re ligne dâ€™import dâ€™origine non dupliquÃ©e. Seules des colonnes
explicitement reconnues sont utilisÃ©es, avec validation et normalisation du code postal.
Des colonnes contradictoires ou invalides restent vides ; aucun champ source privÃ© arbitraire
nâ€™est transmis. Les valeurs dÃ©jÃ  enregistrÃ©es dans la qualification, y compris un blanc explicite,
priment sur les valeurs proposÃ©es. Les copies historiques des visites restent inchangÃ©es.

VÃ©rifications : rÃ©servation sans Ã¢ge, maintien des autres champs obligatoires, imports valides,
conflictuels/invalides et doublons, droits dâ€™un autre setter, prioritÃ© du brouillon dans le
frontend, sauvegarde et conflits existants. Les crÃ©neaux rÃ©els et la publication Google de la
V2 restent Ã  livrer ; ce lot ne les annonce pas comme terminÃ©s.

## Isolation V2 â€” parcours dâ€™appel et qualification (lot 1)

PÃ©rimÃ¨tre confirmÃ© : un seul client Isolation pour le moment ; rÃ©munÃ©ration future en CAD avec
montant par visite tenue et prime supplÃ©mentaire de vente, configurables par setter.

Le choix des rÃ©sultats propose les sept libellÃ©s demandÃ©s, dont Â« NumÃ©ro non attribuÃ© Â» et
Â« Autre rÃ©sultat Â». Lâ€™ancien rÃ©sultat Injoignable reste lisible et acceptÃ© dans lâ€™API. RÃ©pondeur,
numÃ©ro non attribuÃ© et appel coupÃ© enregistrent avant de fermer la fiche ; en session, le dÃ©compte
habituel prÃ©pare le prochain prospect. Une erreur dâ€™enregistrement ou de rechargement conserve
la fiche ouverte. Le rappel conserve date/heure QuÃ©bec et note facultative. Â« Rendez-vous pris Â»
ouvre directement la qualification et la programmation ; aucun faux rendez-vous nâ€™est dÃ©clarÃ©
avant la rÃ©servation. Une visite crÃ©Ã©e enregistre son rÃ©sultat dâ€™appel liÃ© dans la mÃªme transaction,
sans doublon lors dâ€™une rÃ©pÃ©tition. Le retour de programmation recharge la rÃ©vision de la fiche.

Les libellÃ©s visibles Â« Formulaire C2 Â» deviennent Â« Qualification Â» ; les routes et snapshots
historiques C2 restent compatibles. Ce lot ne livre pas les nouvelles disponibilitÃ©s Google,
notifications, non-qualifiÃ©s ou rÃ©munÃ©rations de la V2.

### Isolation V2 â€” lots restants

1. Agenda Google du client et reprÃ©sentants : jours/heures, crÃ©neaux rÃ©els, contrÃ´le final,
   publication fiable et Ã©tats dâ€™erreur explicites ; qualification prÃ©remplie et Ã¢ge facultatif.
2. Visites programmÃ©es, historique par occurrence, tenue/vente et rappels setter sur non-tenue.
3. Notifications et courriels de rÃ©servation ; relance de rÃ©sultat aprÃ¨s 24 h configurable.
4. Rendez-vous non qualifiÃ©s : motifs, recherche ville/code postal, tri et rÃ©activation de la
   mÃªme fiche sans perte dâ€™historique.
5. Statistiques hebdomadaires et rÃ©munÃ©ration CAD : visite tenue + prime de vente, versionnement
   des rÃ¨gles et dÃ©doublonnage du processus commercial lors dâ€™une reprogrammation.
6. Recette complÃ¨te par rÃ´le ; SMS conditionnÃ© Ã  un service intÃ©grÃ©. Revue esthÃ©tique finale
   sÃ©parÃ©e. Assurance conserve son parcours de rÃ©servation externe.

## Statistiques Assurance : journÃ©es du QuÃ©bec cohÃ©rentes

Lâ€™ancien module Statistiques (administrateur et setter) utilise maintenant America/Toronto
pour les bornes de pÃ©riode, les sÃ©ries quotidiennes, la pÃ©riode prÃ©cÃ©dente et les dates par
dÃ©faut. Ses compteurs ne basculent plus sur la journÃ©e suivante Ã  minuit UTC. Les raccourcis
7/30 jours et mois courant/prÃ©cÃ©dent suivent la date du QuÃ©bec, mÃªme si le navigateur est en
Europe. Les exports CSV/XLSX identifient leurs dates de pÃ©riode comme QuÃ©bec ; lâ€™horodatage
du calcul reste explicitement en UTC. Les rÃ¨gles mÃ©tier des indicateurs et les permissions
restent celles de ce module ; la rÃ©munÃ©ration conserve ses rÃ¨gles propres de prÃ©sence validÃ©e.

VÃ©rifications : rendez-vous Ã  23 h 30 le dimanche du passage Ã  lâ€™heure dâ€™hiver, exclusion du
lendemain, regroupement quotidien, date par dÃ©faut, en-tÃªtes CSV/XLSX et raccourcis mensuels
avec une horloge UTC dÃ©jÃ  au lendemain. Tests de permissions/export existants et typage Vue.
Aucune donnÃ©e ni configuration dâ€™agenda nâ€™est modifiÃ©e.

## Suivi hebdomadaire et rÃ©munÃ©ration Assurance en CAD

Lâ€™administration dispose de Â« Suivi et rÃ©munÃ©ration Â» : semaine du lundi au dimanche au QuÃ©bec
par dÃ©faut, navigation de sept jours et pÃ©riode personnalisÃ©e de 366 jours maximum. Le tableau
prÃ©sente par setter les appels Orvia dont le poste a dÃ©crochÃ©, rendez-vous enregistrÃ©s, transmis
par le nouveau formulaire externe, Ã  venir, honorÃ©s, absents dÃ©clarÃ©s, prÃ©sences validÃ©es pour
rÃ©munÃ©ration, prÃ©sences sans tarif et montant valorisÃ© en CAD. Les rÃ©servations externes jamais
transmises sont inconnues du CRM ; les anciennes occurrences restent dans Â« Pris Â». Les appels
composÃ©s hors Orvia ne sont pas reconstituÃ©s Ã  partir des rÃ©sultats manuels de fiche. Une panne
du service dâ€™appels donne une valeur indisponible, pas un faux zÃ©ro. Les totaux dâ€™appels incluent
les administrateurs, le tableau dÃ©taille les setters associÃ©s ou connus par un rendez-vous.

Le tarif est individuel, nullable, versionnÃ©, modifiable seulement par un administrateur avec
motif auditÃ©. Aucun tarif rÃ©el nâ€™est inventÃ© Ã  la migration. Une prÃ©sence confirmÃ©e conserve son
tarif et sa rÃ©vision lors de sa validation ; une correction nÃ©gative ou une annulation lâ€™exclut
du montant courant sans effacer son ancien tarif. Un tarif de zÃ©ro est distinct dâ€™un tarif
absent. Les prÃ©sences anciennes sans tarif peuvent Ãªtre valorisÃ©es pour une pÃ©riode avec motif,
confirmation et contrÃ´le de rÃ©vision ; aucun montant dÃ©jÃ  valorisÃ© nâ€™est remplacÃ©. Les calculs
utilisent des dÃ©cimaux Ã  deux positions, et non des flottants. Les accÃ¨s setter/conseiller nâ€™ont
aucun accÃ¨s aux tarifs ni aux donnÃ©es de rÃ©munÃ©ration.

Le dÃ©tail par setter affiche chaque occurrence, conseiller, date QuÃ©bec, prÃ©sence, tarif conservÃ©,
date de valorisation et montant actuellement retenu. Lâ€™export CSV reprend toutes les pages du
pÃ©rimÃ¨tre appliquÃ© avec protections contre les formules de tableur et Ã©chec explicite si les
appels sont indisponibles. Il peut Ãªtre rÃ©gÃ©nÃ©rÃ© aprÃ¨s correction dâ€™une prÃ©sence ; ce suivi
nâ€™est pas une clÃ´ture de paie et ne dÃ©clenche aucun paiement.

VÃ©rifications : droits, tarifs nÃ©gatifs/dÃ©cimales/revisions, somme de centimes, absence et annulation,
corrections Oui/Non/Oui, conservation des tarifs anciens, valorisation idempotente/audit atomique,
semaine QuÃ©bec et changement dâ€™heure, appels acceptÃ©s distincts des refus/incertitudes/blocages,
absence de fuite des tarifs via les sorties conseiller. Concurrence de valorisation contrÃ´lÃ©e
sur PostgreSQL en CI. Tests frontend de tarifs, pÃ©riode appliquÃ©e, dÃ©tails et export multi-page.

Les lots fonctionnels demandÃ©s dans la demande Assurance du 30 octobre sont implÃ©mentÃ©s.
Restent : revue esthÃ©tique finale si demandÃ©e, recette mÃ©tier par les utilisateurs et Ã©ventuel
raccordement SMS (aucun service dâ€™envoi SMS nâ€™est intÃ©grÃ© Ã  ce parcours).

## Relance conseiller Ã  J+1, 18 h au QuÃ©bec

Le premier rappel de compte rendu manquant intervient le lendemain de la date du rendez-vous,
Ã  18 h dans America/Toronto par dÃ©faut. Lâ€™administration peut modifier lâ€™heure et les minutes
avec rÃ©vision et motif auditÃ©. Le calcul suit les jours locaux et les changements dâ€™heure ; un
ancien rendez-vous de plusieurs jours doit Ãªtre terminÃ© avant la relance. Les anciens dÃ©lais
en heures restent acceptÃ©s par lâ€™API pour compatibilitÃ© mais ne pilotent plus cette Ã©chÃ©ance.

Une seule relance est prÃ©vue par occurrence et destinataire, mÃªme aprÃ¨s changement de rÃ¨gle.
Le courriel contient le nom du prospect, la date/heure du rendez-vous au QuÃ©bec et le lien vers
sa fiche autorisÃ©e. Le contrÃ´le avant envoi exclut annulation, compte rendu dÃ©jÃ  saisi, changement
de destinataire ou reprogrammation. Aucun statut de prÃ©sence nâ€™est inventÃ©. Les comptes de
recette .invalid ne reÃ§oivent pas de mail. Le seuil dâ€™activation antÃ©rieur et la fenÃªtre de sept
jours Ã©vitent une reprise massive dâ€™anciennes relances. Les Ã©vÃ©nements de lâ€™ancienne cadence
nâ€™ont aucune Ã©ligibilitÃ© avant recalcul du nouveau seuil.

VÃ©rifications : gÃ©nÃ©ration avant/Ã  lâ€™Ã©chÃ©ance, transitions hiver/Ã©tÃ©, modification administrateur,
permissions, absence de doublon, annulation/compte rendu et flux signÃ©. Relais mail et rendu HTML
Ã©chappÃ© vÃ©rifiÃ©s avec moteur locmem, sans envoi Ã  un conseiller rÃ©el ; typage frontend vÃ©rifiÃ©.
Limites : SMS non intÃ©grÃ© pour ce parcours ; rÃ©munÃ©ration CAD encore Ã  livrer.

## Retour conseiller Oui/Non et suivi dâ€™absence Assurance

Le conseiller rÃ©pond Ã  Â« Le prospect a-t-il rÃ©pondu Ã  la rencontre ? Â», avec rappel du type
vidÃ©o/tÃ©lÃ©phone et notes facultatives. Oui donne le statut Â« Rendez-vous validÃ© Â» ; Non donne
Â« Non honorÃ© Â» et un rappel setter prÃ©vu au plus tard sous 24 heures, mÃªme si la rÃ¨gle gÃ©nÃ©rale
de suivi prÃ©voit un dÃ©lai supÃ©rieur. Une tÃ¢che fermÃ©e est rouverte et auditÃ©e lorsquâ€™une nouvelle
absence le nÃ©cessite ; les tÃ¢ches et anciennes rÃ©solutions ne sont pas effacÃ©es de lâ€™historique.
Les corrections restent motivÃ©es et versionnÃ©es. Une ancienne dÃ©claration de vente est conservÃ©e
lorsquâ€™elle nâ€™est pas modifiÃ©e ; aucune rÃ©ponse commerciale supplÃ©mentaire nâ€™est requise.

Le setter reÃ§oit une notification de prÃ©sence/absence, peut ouvrir le rendez-vous concernÃ©
dans le bon mois de lâ€™agenda et consulter les observations du conseiller. La lecture ne valide
aucune rencontre. Le conseiller consulte les diffÃ©rentes occurrences du mÃªme prospect depuis
le panneau de rendez-vous et peut passer de lâ€™une Ã  lâ€™autre avec protection des saisies non
enregistrÃ©es. Les libellÃ©s Assurance sont aussi cohÃ©rents dans les dossiers et exports ; Isolation
conserve ses libellÃ©s et rÃ¨gles propres. Le dÃ©compte existant reste fondÃ© sur les prÃ©sences.

VÃ©rifications : notes/vente facultatives, conservation des ventes anciennes, correction auditÃ©e,
notification dÃ©dupliquÃ©e et privÃ©e, absence sous 24 h et rÃ©ouverture, refus avant fin/annulation
ou par un autre rÃ´le, historique scoped, exports et rÃ¨gle gÃ©nÃ©rale de suivi. Tests frontend
Oui/Non sans valeur implicite, notes vides, historique et accÃ¨s au rendez-vous setter.
Limites : une correction de prÃ©sence ne clÃ´ture pas automatiquement un suivi dÃ©jÃ  ouvert ;
le setter le termine selon ses permissions. Le nouveau dÃ©lai de relance Ã  J+1 18 h et le calcul
de rÃ©munÃ©ration CAD sont les deux lots suivants.

## Fiche, rÃ©sultats dâ€™appel et navigation Assurance simplifiÃ©s

Toutes les ouvertures de fiche setter/administrateur utilisent les quatre rubriques guidÃ©es :
coordonnÃ©es, appels et rappels, qualification et rendez-vous, historique. Les rÃ©sultats proposÃ©s
sont Â« Rendez-vous pris Â», Â« RÃ©pondeur Â», Â« NumÃ©ro non attribuÃ© Â», Â« Appel coupÃ© Â», Â« Pas
intÃ©ressÃ© Â», Â« A demandÃ© Ã  Ãªtre rappelÃ© Â» et Â« Autre rÃ©sultat Â». Lâ€™ancien rÃ©sultat Â« Injoignable Â»
reste lisible dans lâ€™historique et acceptÃ© pour compatibilitÃ© API, sans Ãªtre proposÃ© en saisie.
RÃ©pondeur/numÃ©ro non attribuÃ©/appel coupÃ© enregistrent le rÃ©sultat avant la fermeture de fiche
et lâ€™avancement de la session dâ€™appels ; aucun formulaire de qualification nâ€™est ouvert.
Le choix rendez-vous ouvre le formulaire combinÃ©. Les tÃ¢ches de rappel peuvent Ãªtre crÃ©Ã©es
avec date et heure sans note obligatoire.

Les anciens formulaires Assurance de rÃ©servation, disponibilitÃ©s et reprogrammation internes
sont retirÃ©s de lâ€™interface. Lâ€™agenda reste consultatif ; Â« Nouveau rendez-vous Â» renvoie Ã  la
fiche prospect. Une reprogrammation passe par le fournisseur puis une nouvelle transmission.
Lâ€™annulation du suivi dans Orvia reste disponible avec motif et indication de lâ€™action Ã  faire
aussi dans le fournisseur. Les API internes antÃ©rieures restent protÃ©gÃ©es pour compatibilitÃ©.

Le conseiller dispose de deux rubriques principales : Â« Mes rendez-vous Â» et Â« Mes prospects Â».
Son lien se rÃ¨gle dans le volet repliable Â« Mon lien de rÃ©servation Â» de ses rendez-vous.
Les donnÃ©es et connexions existantes ne sont pas effacÃ©es.

VÃ©rifications : tests des sept choix et de lâ€™avancement aprÃ¨s sauvegarde, rappel sans note,
absence de chargement des disponibilitÃ©s internes, navigation conseiller, conservation du
parcours de transmission et de lâ€™agenda ; typage et lint. Le retour Oui/Non du conseiller,
la relance J+1 18 h et les rÃ©munÃ©rations restent Ã  livrer sÃ©parÃ©ment.

## RÃ©servations externes exclues de la publication calendrier

Les occurrences Assurance enregistrÃ©es via un lien externe, comme celles issues de Calendly,
ne sont jamais publiÃ©es une seconde fois par le connecteur Google/Microsoft dâ€™Orvia. Le
fournisseur de rÃ©servation reste propriÃ©taire de son Ã©vÃ©nement ; seule la fiche de suivi
est conservÃ©e dans Orvia. VÃ©rification : passage dans le vrai moteur de synchronisation,
sans appel de publication ni suppression dâ€™un Ã©vÃ©nement du fournisseur externe.

## Transmission combinÃ©e Assurance aprÃ¨s rÃ©servation externe

La fiche guidÃ©e setter rÃ©unit Â« Qualification et rendez-vous Â» : qualification Assurance,
seul champ Â« Notes utiles pour le conseiller Â», conseiller associÃ©, ouverture de son lien
dans un nouvel onglet, type vidÃ©o/tÃ©lÃ©phone, date/heure America/Toronto et confirmation que
la rÃ©servation externe est faite. Lâ€™unique attribution est prÃ©sÃ©lectionnÃ©e ; recherche et
pagination permettent de choisir parmi plusieurs conseillers. Â« Envoyer le rendez-vous Â»
enregistre qualification, occurrence, rÃ©sultat dâ€™appel Â« Rendez-vous pris Â» et notification
dans une transaction idempotente. Aucun appel API de rÃ©servation/contrÃ´le de disponibilitÃ©s
externe nâ€™est exÃ©cutÃ© par cette transmission ; les conflits dÃ©jÃ  connus dâ€™Orvia sont refusÃ©s.

Le conseiller voit une notification dans son agenda Orvia, avec accÃ¨s direct au rendez-vous.
Le type de rencontre et la copie de qualification y sont conservÃ©s. La lecture dâ€™une
notification ne renseigne aucun rÃ©sultat de rencontre. Chaque transmission/reprogrammation
crÃ©e une nouvelle occurrence liÃ©e au mÃªme prospect ; lâ€™historique reste consultable dans
le formulaire. Les anciennes notes complÃ©mentaires restent stockÃ©es, mais ne sont pas
copiÃ©es dans une nouvelle transmission externe. La fiche guidÃ©e masque les anciens blocs
statut commercial, notes internes et documents et expose lâ€™historique aussi aux setters.

VÃ©rifications : atomicitÃ© et rollback, rÃ©pÃ©tition idempotente, rÃ©vision/verrou et affectations,
validations du lien/type/heure/confirmation, confidentialitÃ© des notifications, conservation
des occurrences ; concurrence PostgreSQL dans la CI. Tests frontend de prÃ©sÃ©lection, envoi
combinÃ©, fuseau QuÃ©bec, choix multiple et reprise aprÃ¨s rÃ©ponse interrompue ; rÃ©gressions
qualification, rappels et agenda. ContrÃ´le typage/lint et contrat API mis Ã  jour.

Limites : notification de nouveau rendez-vous **dans Orvia**, pas encore dâ€™e-mail dâ€™annonce ;
le fournisseur externe nâ€™est pas synchronisÃ©. Les anciens composants/API de rÃ©servation et
de reprogrammation existent encore pour compatibilitÃ© et doivent Ãªtre retirÃ©s des autres
entrÃ©es dâ€™interface dans la simplification suivante. La nouvelle relance J+1 18 h, le retour
conseiller simplifiÃ© et la rÃ©munÃ©ration ne sont pas livrÃ©s par ce lot.

## Liens externes de rÃ©servation des conseillers Assurance

Chaque conseiller peut enregistrer son lien public HTTPS depuis Â« Mon agenda et disponibilitÃ©s Â».
Lâ€™administrateur peut le modifier depuis Â« Associations â†’ Lien de rÃ©servation Â» ; il est commun
aux associations du mÃªme conseiller. Le setter voit uniquement les liens de ses associations
actives et peut les ouvrir dans un nouvel onglet depuis Â« Mes conseillers Â». Les changements
sont versionnÃ©s, les conflits refusÃ©s et lâ€™action auditÃ©e sans copier la requÃªte du fournisseur
dans lâ€™audit. Aucun appel au fournisseur ni connexion Microsoft/Calendly nâ€™est nÃ©cessaire pour
enregistrer ou ouvrir ce lien.

VÃ©rifications : droits par rÃ´le, isolation entre conseillers/setters, associations suspendues,
URL HTTPS sans identifiants, suppression du lien, conflits de version et concurrence PostgreSQL
dans la CI. Limite : cette livraison gÃ¨re les liens ; elle ne constitue pas encore le nouveau
parcours complet de transmission manuelle ni une synchronisation du fournisseur.

### Demande Assurance du 30 octobre â€” Ã©tat actuel

Les liens externes, la transmission combinÃ©e, la fiche simplifiÃ©e, les retours Oui/Non,
la relance J+1 Ã  18 h et le suivi des rÃ©munÃ©rations CAD sont implÃ©mentÃ©s et dÃ©crits en tÃªte
de ce document. Les paragraphes plus anciens conservent le pÃ©rimÃ¨tre de chaque livraison
Ã  sa date. La recette utilisateur et lâ€™Ã©ventuel raccordement SMS restent distincts.

## Relance douce du conseiller aprÃ¨s un rendez-vous Assurance

Un compte rendu manquant dÃ©clenche une seule relance au conseiller assignÃ©, une heure aprÃ¨s
la **fin** du rendez-vous par dÃ©faut. Lâ€™e-mail invite Ã  indiquer prÃ©sence/absence, vente ou
contrat conclu et notes ; son bouton ouvre directement le panneau du rendez-vous, mÃªme
dans un mois passÃ© et aprÃ¨s une connexion avec plusieurs espaces autorisÃ©s.
Lâ€™ouverture du lien ne modifie aucune donnÃ©e et les permissions habituelles sâ€™appliquent.

Les workers existants gÃ©nÃ¨rent le rappel, le transmettent au portail puis lâ€™envoient via
la file SMTP. Lâ€™Ã©ligibilitÃ© est revÃ©rifiÃ©e avant lâ€™envoi : compte rendu dÃ©jÃ  saisi,
annulation, report du crÃ©neau ou changement de conseiller rendent lâ€™ancien rappel caduc.
Lâ€™identitÃ© persistante empÃªche une nouvelle relance du mÃªme crÃ©neau au mÃªme conseiller,
y compris aprÃ¨s changement de politique ; une reprogrammation constitue un nouveau crÃ©neau.
Les adresses de dÃ©monstration en `.invalid` sont exclues du relais.

Lâ€™activation de la migration dÃ©marre aux rendez-vous se terminant aprÃ¨s son passage pour
les politiques existantes, sans relancer le stock historique. Les tÃ¢ches et escalades
administrateur conservent leurs rÃ¨gles ; les escalades ne sont pas activÃ©es par cette livraison.
Lâ€™administration peut suspendre les relances et ajuster le dÃ©lai initial. Le champ API
historique `report_interval_hours` reste acceptÃ© pour compatibilitÃ©, sans rÃ©pÃ©tition des
relances conseiller.

VÃ©rifications : Ã©chÃ©ance exacte Ã  une heure, absence de doublons, expiration, politique,
flux signÃ©, rÃ´le/adresse destinataire, arrÃªt avant SMTP, lien et maintien aprÃ¨s connexion,
agenda passÃ© et accÃ¨s refusÃ© ; concurrence des workers dans la CI PostgreSQL.
Commandes opÃ©rateur : `generate_assurance_reminders` (service Assurance),
`relay_assurance_mail --stream reminders` et `dispatch_portal_mail` (portail), avec les
settings de chaque service. Limites : traitement Ã  la cadence des workers, puis dÃ©lai du
fournisseur mail ; rattrapage limitÃ© Ã  sept jours aprÃ¨s lâ€™Ã©chÃ©ance et aucune absence dÃ©duite
automatiquement. Le test SMTP utilise une boÃ®te mÃ©moire, sans envoi rÃ©el Ã  un conseiller.

## Bloc logo alignÃ© sur la barre latÃ©rale

Le bloc sombre du logo dÃ©passait la barre latÃ©rale resserrÃ©e : il gardait lâ€™ancienne largeur de 248 px alors que la colonne est passÃ©e Ã  216 px. Il fait maintenant exactement 216 px et son logo est plus petit (icÃ´ne 28 px, Â« Orvia Â» 21 px). Lâ€™en-tÃªte passe de 78 Ã  64 px de haut (barre latÃ©rale et zone de travail suivent), et le tiroir mobile fait aussi 216 px.

Limites : rÃ©glage visuel non vÃ©rifiÃ© Ã  lâ€™Ã©cran par moi ; revue esthÃ©tique Ã  la revue finale.

## Barre latÃ©rale resserrÃ©e

La barre latÃ©rale du CRM (setters, administrateurs) est plus compacte : colonne de 216 px au lieu de 248 px, entrÃ©es de 38 px au lieu de 58 px avec 2 px dâ€™Ã©cart au lieu de 9 px, icÃ´nes de 19 px au lieu de 26 px, texte de 13,5 px, groupe Â« Pilotage Â» resserrÃ© (entrÃ©es de 34 px), logo du haut lÃ©gÃ¨rement rÃ©duit. Toutes les entrÃ©es dâ€™un administrateur tiennent ainsi sans dÃ©filement sur un Ã©cran courant. Aucun changement de contenu ni dâ€™ordre des entrÃ©es.

Limites : rÃ©glage purement visuel, non vÃ©rifiÃ© Ã  lâ€™Ã©cran par moi (pas de compte de test utilisable dans le navigateur) ; la revue esthÃ©tique reste Ã  la revue finale.

## Retrait de la simulation publique pour les essais tÃ©lÃ©phoniques rÃ©els

Le portail monte exclusivement le CRM authentifiÃ©. Les liens Â« Simuler un appel Â», la page
dâ€™aperÃ§u et son adaptateur en mÃ©moire sont retirÃ©s. Un ancien lien `?simulation=appel` est
nettoyÃ© en conservant les autres paramÃ¨tres et fragments, puis affiche le CRM normal.
La modale de dÃ©compte des sessions rÃ©elles reste disponible avec ses contrÃ´les et son arrÃªt.
VÃ©rifications : normalisation des liens, tableaux Assurance/Isolation, navigation, typage,
lint et build ; CI avant fusion. Aucun appel rÃ©el dÃ©clenchÃ© pendant cette livraison.
Les associations tÃ©lÃ©phoniques et secrets de dÃ©ploiement sont gÃ©rÃ©s hors Git.

## Composeur : appel dâ€™un numÃ©ro saisi aussi en Isolation

Le composeur dâ€™Isolation fonctionne dÃ©sormais comme celui dâ€™Assurance : Â« Appeler ce numÃ©ro Â» retrouve le prospect qui porte ce numÃ©ro ou en crÃ©e un dans une campagne technique Â« Appels directs Â», confiÃ© Ã  la personne qui compose, puis ouvre le parcours dâ€™appel habituel. Le prospect crÃ©Ã© Ã  la main est marquÃ© appelable (Â« Appel libre : numÃ©ro composÃ© par lâ€™utilisateur Â») : câ€™est un choix assumÃ©, car sinon aucun numÃ©ro tapÃ© ne pourrait partir. Refus avec message : numÃ©ro de la liste dâ€™exclusion, prospect dâ€™un autre setter, prospect existant en attente dâ€™autorisation dâ€™appel dâ€™un administrateur, numÃ©ro non nord-amÃ©ricain. Le champ de saisie a la mÃªme prÃ©sentation dans les deux espaces ; Â« Trouver la fiche Â» reste disponible.

Limites : aucun contrÃ´le de consentement ni de vÃ©rification de ligne pour un appel libre, seulement les rÃ¨gles dâ€™appel (heures, liste dâ€™exclusion) ; non essayÃ© dans un navigateur ; revue visuelle reportÃ©e Ã  la revue finale.

## Composeur : appeler un numÃ©ro saisi (Assurance)

Dans Â« Appels â†’ Composer Â», le setter ou lâ€™administrateur Assurance compose un numÃ©ro au clavier (ou le tape) et clique sur Â« Appeler ce numÃ©ro Â» au lieu de chercher une fiche. Le CRM retrouve la fiche qui porte ce numÃ©ro, quel que soit son format, ou en crÃ©e une vide (crÃ©Ã©e par la personne, tracÃ©e dans lâ€™audit), puis ouvre le parcours dâ€™appel habituel : prise en charge de la fiche, confirmation ou dÃ©crochÃ© automatique, heures autorisÃ©es, liste dâ€™exclusion, qualification et historique restent rattachÃ©s Ã  un dossier. Si le numÃ©ro appartient Ã  la fiche dâ€™un autre setter, lâ€™appel est refusÃ© avec un message ; une fiche crÃ©Ã©e Ã  la main reste visible de son auteur mÃªme quand les lots sont actifs. Â« Trouver la fiche Â» reste disponible pour chercher par nom.

Limites : Isolation inchangÃ© (un appel Isolation exige une fiche dont la conformitÃ© est validÃ©e, donc pas dâ€™appel libre) ; lâ€™appel libre ne vÃ©rifie pas de consentement : seules les rÃ¨gles dâ€™appel sâ€™appliquent ; non essayÃ© dans un navigateur ; revue visuelle reportÃ©e Ã  la revue finale.

## DÃ©crochÃ© automatique du poste (option NEWT, dÃ©sactivÃ©e par dÃ©faut)

NEWT (Phonetico) a confirmÃ© par e-mail que le dÃ©crochÃ© automatique fonctionne dans le logiciel de bureau, aprÃ¨s redÃ©marrage du logiciel, et dans lâ€™application mobile. Le CRM sait dÃ©sormais envoyer le paramÃ¨tre `_a=Y` avec la commande dâ€™appel : le poste du setter dÃ©croche tout seul et le prospect est composÃ© immÃ©diatement, sans geste du setter, y compris dans une session dâ€™appels enchaÃ®nÃ©s. Le rÃ©glage `NEWT_AUTO_ANSWER` (dÃ©faut `false`) sâ€™active dans le `.env` du serveur, puis un redÃ©ploiement ; il vaut pour Assurance et Isolation. Les garde-fous (heures, liste dâ€™exclusion, 60 secondes entre deux commandes) sâ€™appliquent avant lâ€™envoi.

Limites : non essayÃ© avec un vrai appel ; le format exact de la rÃ©ponse de NEWT avec `_a=Y` nâ€™est pas confirmÃ© (toute rÃ©ponse inattendue reste classÃ©e Â« indÃ©terminÃ© Â», sans relance) ; un setter qui sâ€™Ã©loigne de son poste le laisse dÃ©crocher seul : Ã  expliquer aux Ã©quipes.

## Simulation interactive de lâ€™interface dâ€™appel Assurance

`/crm?simulation=appel` propose un dÃ©compte puis la vraie fiche Assurance et son composant
dâ€™appel, alimentÃ©s exclusivement par un adaptateur en mÃ©moire. Aucun callback mÃ©tier rÃ©el,
appel HTTP, appel Phonetico, courriel ou Ã©criture calendrier nâ€™est utilisÃ©. Les coordonnÃ©es
sont fictives, le numÃ©ro invalide et le mode simulation reste signalÃ© dans la fiche. Le
rÃ©sultat acceptÃ© simule seulement le dÃ©crochage du poste et la composition ; aucun audio
ni conversation ne sont reproduits. RÃ©sultats, notes, rappels, qualification et rÃ©servation
peuvent Ãªtre essayÃ©s en mÃ©moire. Les actions non implÃ©mentÃ©es sont refusÃ©es sans rÃ©seau.
Les tableaux Assurance et Isolation proposent le lien vers cet aperÃ§u Assurance.
La fermeture/redÃ©marrage supprime les saisies ; le dÃ©compte est arrÃªtÃ© Ã  la sortie.
VÃ©rifications : adaptateur sans rÃ©seau, typage, lint, build et CI avant fusion. La recette
visuelle et le vÃ©ritable parcours opÃ©rateur restent distincts.

## Session dâ€™appels â€” dÃ©compte en modale

Le dÃ©compte entre deux prospects est affichÃ© dans une modale commune Ã  Assurance et Isolation.
Ã€ zÃ©ro, le parcours existant ouvre la prochaine fiche et demande lâ€™appel aprÃ¨s ses contrÃ´les.
Â« Appeler maintenant Â» avance immÃ©diatement ; Â« ArrÃªter la session Â», Ã‰chap ou le fond arrÃªtent
le minuteur et la session. La fermeture ne dÃ©clenche jamais un appel. Les minuteurs sont nettoyÃ©s
Ã  la sortie et avant un nouveau dÃ©compte. VÃ©rifications : tests des deux tableaux, typage, lint
et build ; aucun appel rÃ©el effectuÃ©.

## IcÃ´ne du navigateur : rechargement forcÃ©

Lâ€™icÃ´ne Orvia (`/favicon.svg`) est servie correctement, mais les navigateurs avaient mÃ©morisÃ© son absence. Son adresse porte dÃ©sormais un numÃ©ro de version (`?v=2`) dans le CRM et les trois pages publiques, ce qui oblige chaque navigateur Ã  la recharger. Ã€ lâ€™avenir, changer lâ€™icÃ´ne impose dâ€™incrÃ©menter ce numÃ©ro. Limite : lâ€™icÃ´ne reste la version simple actuelle, en attendant le logo dÃ©finitif.

## Typographie plus compacte pour administrateurs et setters

Les deux rÃ´les reÃ§oivent une taille de texte plus discrÃ¨te en Assurance et Isolation :
menus Ã  13 px, titres de page Ã  25 px (22 px sur petit Ã©cran), sous-titres Ã  17 px,
tableaux/libellÃ©s/actions Ã  11,5 px et champs Ã  12 px sur ordinateur. Les indicateurs
volumineux sont rÃ©duits sans supprimer leur adaptation Ã  la largeur des cartes. Les champs
tactiles restent Ã  16 px pour Ã©viter le zoom de saisie sur mobile. Les surfaces de clic et
les icÃ´nes restent inchangÃ©es. Conseillers, closers, client, connexion et prÃ©sentation ne
reÃ§oivent pas cette classe de rÃ´le. VÃ©rifications : typage, lint, formatage, tests de
navigation et build ; validation visuelle par le client restant Ã  effectuer.

## Favicon Orvia sur le portail et les pages publiques

Le symbole Orvia existant est servi Ã  `/favicon.svg` et dÃ©clarÃ© dans le portail CRM,
la prÃ©sentation, la confidentialitÃ© et les conditions. Le mÃªme symbole est utilisÃ© dans
les onglets du navigateur. Validation : SVG et liens contrÃ´lÃ©s, build et CI avant fusion.
Le navigateur peut conserver temporairement son ancienne icÃ´ne en cache.

## SÃ©lection dâ€™espace â€” continuitÃ© avec la connexion Orvia

AprÃ¨s la connexion, les comptes disposant de plusieurs espaces accÃ¨dent Ã  une page dÃ©diÃ©e,
sans la navigation mÃ©tier vide. Elle reprend le fond crÃ¨me, le vert olive et le lilas de la
connexion : cartes Assurance et Isolation, rÃ´le par espace, compte connectÃ© et dÃ©connexion.
Seuls les accÃ¨s transmis par la session sont proposÃ©s. Les boutons restent accessibles au
clavier, le contenu sâ€™adapte au mobile et les mouvements respectent la prÃ©fÃ©rence de rÃ©duction
des animations. Le cas sans accÃ¨s affiche une explication. Lâ€™ouverture automatique dâ€™un seul
espace et la reprise du dernier espace au rechargement sont conservÃ©es.

Validation : typage Vue, lint, formatage, build et contrÃ´les CI avant fusion. La vÃ©rification
visuelle dans un navigateur reste Ã  effectuer ; aucune modification des droits mÃ©tier.
Le test PostgreSQL de double soumission tÃ©lÃ©phonique dÃ©finit explicitement sa configuration
de recette, pour ne plus dÃ©pendre de lâ€™heure rÃ©elle Ã  MontrÃ©al ; les restrictions de production
et leurs tests dÃ©diÃ©s sont inchangÃ©s.
Les identifiants des comptes crÃ©Ã©s Ã  la demande restent hors de Git dans un fichier privÃ©.

## Dimensionnement pour environ 20 setters et entretien automatique

Serveur visÃ© : 8 vCPU, 24 Go de RAM. Le portail, Assurance et Isolation passent Ã  4 processus de 2 tÃ¢ches chacun (au lieu de 2 ou 3 processus dâ€™une tÃ¢che), pour quâ€™un appel qui attend lâ€™opÃ©rateur ne bloque pas les autres Ã©crans ; chaque processus se relance aprÃ¨s environ 1 000 demandes, ce qui libÃ¨re la mÃ©moire sans intervention. En production, tous les services redÃ©marrent seuls (incident ou redÃ©marrage du serveur), les journaux Docker sont limitÃ©s (3 fichiers de 10 Mo) et Redis est plafonnÃ© Ã  1 Go sans Ã©viction. Le script `scripts/maintenance.sh`, lancÃ© aprÃ¨s chaque dÃ©ploiement vÃ©rifiÃ©, conserve les 5 derniÃ¨res sauvegardes de `.backups` (elles sâ€™accumulaient sans limite) et retire les images et caches Docker inutilisÃ©s depuis 7 jours. La limite de connexions passe de 10 Ã  30 par minute et par adresse : un bureau de 20 personnes partage une adresse et se connecte Ã  la mÃªme heure. Le script `scripts/load_test_setters.py` simule des setters connectÃ©s (lecture seule, aucun appel) et affiche mÃ©dianes, p95 et erreurs ; essayÃ© en local avec 5 setters.

Limites : aucune mesure nâ€™a Ã©tÃ© faite sur le serveur rÃ©el ni avec 20 setters ; le premier dÃ©ploiement recrÃ©e tous les conteneurs (interruption de quelques minutes) ; les appels restent espacÃ©s de 60 secondes par setter cÃ´tÃ© portail ; la limite de connexions plus haute affaiblit un peu la protection contre le devinage de mots de passe, compensÃ©e par des mots de passe de 12 caractÃ¨res minimum.

## Lâ€™administrateur sâ€™attribue un lot et lance sa propre session dâ€™appels (Assurance et Isolation)

Dans Â« Attribuer des lots Â» (Assurance) et Â« Lot de la semaine Â» (Isolation), lâ€™administrateur apparaÃ®t dans la liste des destinataires, marquÃ© Â« administrateur Â» cÃ´tÃ© Assurance : il peut se donner un nombre de prospects, comme Ã  un setter. Le bouton Â« Lancer une session dâ€™appels Â» est maintenant proposÃ© Ã  lâ€™administrateur : la session parcourt uniquement les prospects de son propre lot (nouveaux filtres `mine=true` cÃ´tÃ© Assurance et `owner=me` cÃ´tÃ© Isolation), avec le mÃªme compte Ã  rebours arrÃªtable ; sâ€™il nâ€™a pas de lot, un message lui indique de sâ€™en attribuer un. Lâ€™administrateur continue de voir tous les prospects de lâ€™Ã©quipe ; ses appels passent par les mÃªmes garde-fous (heures, liste dâ€™exclusion) que ceux des setters.

Limites : la preuve du portail pour un lot accepte setter ou administrateur actif de lâ€™espace ; le test dâ€™appel rÃ©el reste Ã  faire ; revue visuelle reportÃ©e Ã  la revue finale.

## Retrait de lâ€™onglet OpportunitÃ©s (Assurance)

Lâ€™onglet Â« OpportunitÃ©s Â» de lâ€™administrateur Assurance disparaÃ®t : câ€™Ã©tait un second tableau des mÃªmes fiches par statut commercial, dÃ©jÃ  prÃ©sent dans Â« Prospects Â» (tableau par statut, avec import, lots et appels). Le menu de lâ€™administrateur devient Accueil, Prospects, Rendez-vous, TÃ¢ches ; les rÃ©glages du pipeline (Ã©tapes) restent dans Â« ParamÃ¨tres mÃ©tier Â». Aucune donnÃ©e nâ€™est supprimÃ©e.

## Calendly â€” notifications signÃ©es, annulations, reports et rapprochement

Le conseiller active la synchronisation depuis ses agendas connectÃ©s aprÃ¨s le consentement et
le choix de sa page. Orvia crÃ©e une souscription propre Ã  son utilisateur, sans gÃ©rer une Ã©quipe
Calendly. La clÃ© serveur `CALENDLY_WEBHOOK_SIGNING_KEY` est nÃ©cessaire. Sans activation, aucune
nouvelle rÃ©servation nâ€™est envoyÃ©e ; le contrÃ´le prÃ©alable Ã©vite les fausses demandes en attente.
Un timeout dâ€™activation est rapprochÃ© par lecture avant tout nouvel essai de crÃ©ation.

Les notifications `invitee.created`/`invitee.canceled` sont authentifiÃ©es sur leurs octets exacts,
limitÃ©es en taille, dÃ©dupliquÃ©es et mises en file durable sans stocker questions/notes/courriels
reÃ§us. Le worker `portal-calendly` vÃ©rifie lâ€™Ã©tat canonique chez Calendly, suit les chaÃ®nes de
reports et livre des versions signÃ©es au service Assurance. Les doublons et livraisons anciennes
ne crÃ©ent pas de rendez-vous supplÃ©mentaire et ne remettent pas un ancien crÃ©neau. Le snapshot
de qualification, les affectations et le dossier sont conservÃ©s ; les changements externes sont
attribuÃ©s au systÃ¨me Calendly dans lâ€™audit, sans les faire passer pour une action du setter.

Une rÃ©ponse de crÃ©ation perdue est rÃ©cupÃ©rable par lâ€™identifiant opaque du webhook, aprÃ¨s contrÃ´le
du compte, de la page, du destinataire et du crÃ©neau. Un rapprochement pÃ©riodique des rÃ©fÃ©rences
connues couvre aussi les notifications manquÃ©es. La commande de rÃ©cupÃ©ration contrÃ´lÃ©e documentÃ©e
dans `docs/CALENDLY.md` permet le cas oÃ¹ rÃ©ponse et webhook sont tous deux perdus, sans crÃ©er de
rendez-vous externe. Les erreurs sont reprises puis signalÃ©es. Les liens de report/annulation
Calendly sont disponibles sur les rendez-vous pour les rÃ´les autorisÃ©s.

Un report externe crÃ©ant un conflit est reflÃ©tÃ© et signalÃ© ; les comptes rendus dÃ©jÃ  enregistrÃ©s
ne sont jamais Ã©crasÃ©s automatiquement : le changement est signalÃ© pour examen. DÃ©connecter le
compte arrÃªte le suivi mais conserve les rendez-vous/historiques. Les Ã©vÃ©nements personnels non
liÃ©s Ã  une demande Orvia ne sont pas associÃ©s par supposition Ã  un prospect. Les pages dâ€™Ã©quipe
et les formulaires Calendly exigeant des champs additionnels non fournis ne sont pas couverts.

VÃ©rifications : signatures invalides/expirÃ©es, rÃ©ception dupliquÃ©e, intention perdue,
rattachement incorrect refusÃ©, chaÃ®ne de reports et annulation tardive, livraison rejouÃ©e,
conflit externe et compte rendu prÃ©servÃ© ; reprise Vue aprÃ¨s timeout/fermeture de fiche ;
concurrence PostgreSQL et contrÃ´les CI avant fusion. Les tests fournisseur sont simulÃ©s :
identifiants, consentement, activation et rÃ©servation rÃ©elle de recette restent Ã  effectuer.

## Lots Assurance : tous les setters du portail proposÃ©s

Correctif de la premiÃ¨re livraison des lots Assurance : le panneau Â« Attribuer des lots Â» nâ€™affichait ni setter ni champ de nombre tant quâ€™aucun conseiller nâ€™Ã©tait associÃ© Ã  un setter. Il liste maintenant tous les setters Assurance actifs depuis le portail, avec le nombre de prospects en cours de chacun, et le formulaire (setter, nombre de prospects â€” les premiers, par dÃ©faut 100 â€”, provenance) est toujours visible. Le setter est attestÃ© par une nouvelle preuve signÃ©e du portail (lot-proof), comme pour Isolation, au lieu de dÃ©pendre dâ€™une association avec un conseiller.

VÃ©rifiÃ© sur le CRM local : attribution des deux fiches de dÃ©monstration au setter de recette, le cloisonnement sâ€™active ensuite. Limite : revue visuelle reportÃ©e Ã  la revue finale.



## Calendly â€” rÃ©servation depuis la fiche Assurance, heure de MontrÃ©al

Le setter ou administrateur choisit Calendly dans la rÃ©servation du prospect, puis une attribution
active, une date au QuÃ©bec et un crÃ©neau proposÃ© par le compte personnel du conseiller. MontrÃ©al
(`America/Toronto`) est imposÃ© pour ce parcours, avec conversion des instants et tests des passages
Ã©tÃ©/hiver, dont les deux occurrences de lâ€™heure rÃ©pÃ©tÃ©e en automne. Bail de fiche, rÃ©vision de
qualification, attribution et conflits internes sont contrÃ´lÃ©s avant envoi. La durÃ©e vient de la
page personnelle choisie par le conseiller. Nom, courriel et identifiant opaque sont transmis Ã 
Calendly ; la qualification reste partagÃ©e dans Orvia, via le snapshot du rendez-vous confirmÃ©.

Une confirmation canonique Calendly crÃ©e un rendez-vous dans les parcours existants. Les demandes
incertaines persistent sans compter comme rendez-vous, bloquent le crÃ©neau et se retrouvent depuis
la fiche ; aucun renvoi automatique dâ€™Ã©criture aprÃ¨s timeout. Google/Microsoft ne republient pas
ces Ã©vÃ©nements. Annulations/reprogrammations Orvia bloquÃ©es pour ce fournisseur en attendant le
lot webhooks, afin dâ€™Ã©viter la divergence. Les anciennes connexions doivent Ãªtre rÃ©autorisÃ©es avec
les nouveaux scopes. Identifiants/consentement et forfait compatible restent nÃ©cessaires.

Tests de bail/droits/qualification/idempotence, attente, conflit, timeout et refus fournisseur,
RPC interne signÃ©, conversion MontrÃ©al et non-rÃ©gression services/Vue. Les contrÃ´les CI prÃ©cÃ¨dent
la fusion. Tests externes simulÃ©s ; aucun rendez-vous rÃ©el crÃ©Ã©, recette fournisseur en attente.
La synchronisation crÃ©ations/annulations/reports et le rapprochement automatique restent le lot
suivant, demandÃ© dans la mÃªme tÃ¢che.

## Garde-fous dâ€™appel : heures autorisÃ©es et liste dâ€™exclusion (Assurance et Isolation)

Le portail refuse dÃ©sormais, avant toute commande Ã  lâ€™opÃ©rateur, un appel placÃ© hors des heures autorisÃ©es ou vers un numÃ©ro de la liste dâ€™exclusion. Les heures par dÃ©faut sont 9 h 30â€“21 h 30 en semaine et 10 hâ€“18 h le week-end, heure de MontrÃ©al ; elles sont rÃ©glables, dÃ©sactivables et le fuseau est modifiable. Lâ€™administrateur gÃ¨re les deux dans AccÃ¨s â†’ Â« RÃ¨gles dâ€™appel Â» : rÃ©glage des heures avec lâ€™Ã©tat du moment, ajout de numÃ©ros en lot (collÃ©s, un par ligne ou sÃ©parÃ©s par des virgules, normalisÃ©s comme les numÃ©ros composÃ©s), recherche et retrait. Le message de refus est affichÃ© au setter (y compris en session dâ€™appels, qui nâ€™envoie rien), le refus est tracÃ© dans lâ€™audit sans enregistrer le numÃ©ro, et aucune commande ni ligne dâ€™historique nâ€™est crÃ©Ã©e.

Comportement Ã  connaÃ®tre : le contrÃ´le des heures est actif dÃ¨s le dÃ©ploiement ; pour un test hors horaires, lâ€™administrateur le dÃ©sactive dans Â« RÃ¨gles dâ€™appel Â». Limites : lâ€™heure est celle dâ€™un seul fuseau, pas celle du prospect ; lâ€™exclusion porte sur le numÃ©ro composÃ© exact, sans importer de liste officielle ; la liste est partagÃ©e par les deux espaces ; revue visuelle reportÃ©e Ã  la revue finale.


## Session dâ€™appels enchaÃ®nÃ©s avec compte Ã  rebours (Isolation)

Sur la page Prospects Isolation, le setter lance une Â« session dâ€™appels Â» : le premier prospect de son tableau (avec un numÃ©ro, hors Â« Non intÃ©ressÃ© Â») sâ€™ouvre en parcours dâ€™appel et la commande dâ€™appel part dâ€™elle-mÃªme, sans confirmation, une fois les contrÃ´les habituels passÃ©s (appels activÃ©s, poste associÃ©, conformitÃ©). AprÃ¨s son Ã©change, le setter clique sur Â« Terminer Â· prospect suivant Â» : un compte Ã  rebours de 10 secondes sâ€™affiche avec Â« Appeler maintenant Â» et Â« ArrÃªter la session Â». Ã€ zÃ©ro, le prospect suivant est ouvert et appelÃ© ; Ã  la fin de la liste, la session sâ€™arrÃªte avec un message. MÃªme mÃ©canique que la session Assurance.

Limites : le dÃ©compte dÃ©marre Ã  la fermeture de la fiche, pas Ã  la dÃ©tection de fin dâ€™appel ; sans dÃ©crochÃ© automatique NEWT, le setter dÃ©croche son poste Ã  chaque appel ; pas de contrÃ´le serveur des plages horaires ni des listes dâ€™exclusion ; un prospect dont lâ€™appel est bloquÃ© est simplement affichÃ© comme tel puis le setter passe au suivant ; test dâ€™appel rÃ©el Ã  faire ; revue visuelle reportÃ©e Ã  la revue finale.

## Lot de la semaine aux setters (Isolation)

Sur la page Prospects Isolation, lâ€™administrateur ouvre Â« Lot de la semaine Â», choisit un setter et un nombre de prospects (1 Ã  1000) : les prochains prospects non attribuÃ©s, ni en rendez-vous ni refusÃ©s, lui sont donnÃ©s. Le panneau indique la semaine en cours, les prospects non attribuÃ©s, le nombre en cours par setter avec la date de son lot, et Â« Reprendre Â» rend Ã  lâ€™Ã©quipe les prospects que le setter nâ€™a pas encore travaillÃ©s (statut Â« Ã€ contacter Â»). Lâ€™attribution se fait Ã  la main, chaque semaine ; elle est rejouable sans doublon, tracÃ©e dans lâ€™audit, et le setter est attestÃ© par le portail. Un setter Isolation ne voyait dÃ©jÃ  que ses prospects : rien ne change pour lui.

Limites : la rÃ©partition existante par sÃ©lection (25 prospects) est conservÃ©e ; pas dâ€™attribution automatique chaque semaine ; les prospects dont la conformitÃ© dâ€™appel nâ€™est pas validÃ©e peuvent faire partie dâ€™un lot (lâ€™appel reste bloquÃ© pour eux) ; la session dâ€™appels enchaÃ®nÃ©s Isolation est la fonctionnalitÃ© suivante ; revue visuelle reportÃ©e Ã  la revue finale.

## Session dâ€™appels enchaÃ®nÃ©s avec compte Ã  rebours (Assurance)

Sur la page Prospects, le setter lance une Â« session dâ€™appels Â» : le premier prospect de son tableau (avec un numÃ©ro) sâ€™ouvre en parcours dâ€™appel et la commande dâ€™appel part dâ€™elle-mÃªme, sans Ã©tape de confirmation, une fois les contrÃ´les habituels passÃ©s (appels activÃ©s, poste associÃ©). Le setter qualifie le prospect, rÃ©serve Ã©ventuellement un rendez-vous, puis clique sur Â« Terminer Â· prospect suivant Â» : un compte Ã  rebours de 10 secondes sâ€™affiche avec Â« Appeler maintenant Â» et Â« ArrÃªter la session Â». Ã€ zÃ©ro, le prospect suivant est ouvert et appelÃ© ; Ã  la fin de la liste, la session sâ€™arrÃªte avec un message.

Limites : le dÃ©compte dÃ©marre Ã  la fermeture de la fiche, pas Ã  la dÃ©tection de fin dâ€™appel (le journal NEWT arrive aprÃ¨s coup) ; sans dÃ©crochÃ© automatique NEWT (option payante non activÃ©e), le setter doit dÃ©crocher son poste Ã  chaque appel ; aucune plage horaire ni liste dâ€™exclusion nâ€™est encore contrÃ´lÃ©e cÃ´tÃ© serveur ; le test avec de vrais appels reste Ã  faire avec le poste de recette ; revue visuelle reportÃ©e Ã  la revue finale.

## Attribution de lots de prospects aux setters (Assurance)

Sur la page Prospects, lâ€™administrateur Assurance ouvre Â« Attribuer des lots Â», choisit un setter, un nombre de prospects (1 Ã  1000) et Ã©ventuellement un import dâ€™origine : les prochains prospects non attribuÃ©s et non traitÃ©s lui sont donnÃ©s. Il voit le nombre de prospects en cours par setter et peut Â« Reprendre Â» les prospects non travaillÃ©s (ceux qui ne sont pas verrouillÃ©s). Chaque opÃ©ration est rejouable sans doublon et tracÃ©e dans lâ€™audit. Changement de comportement : tant quâ€™aucun lot nâ€™a Ã©tÃ© attribuÃ©, les setters partagent la liste comme avant ; dÃ¨s le premier lot, chaque setter ne voit que les prospects de son lot, et lâ€™administrateur voit tout. Les setters proposÃ©s sont ceux qui ont un conseiller associÃ© actif.

Limites : lâ€™Ã©quivalent cÃ´tÃ© Isolation existe dÃ©jÃ  (rÃ©partition par sÃ©lection de 25 prospects maximum) et nâ€™est pas modifiÃ© ; lâ€™appel automatique avec compte Ã  rebours est la fonctionnalitÃ© suivante ; revue visuelle reportÃ©e Ã  la revue finale.


## Calendly â€” connexion personnelle et page prÃ©fÃ©rÃ©e du conseiller Assurance

Premier parcours livrÃ© : OAuth par conseiller, profil, pages personnelles actives, choix persistant
dâ€™une page prÃ©fÃ©rÃ©e, ouverture chez Calendly, actualisation et dÃ©connexion locale. Accessible dans
les agendas connectÃ©s et Mon compte. Un compte par conseiller, indÃ©pendant de lâ€™abonnement central
et de Google/Microsoft ; aucune place Calendly crÃ©Ã©e ni souscription dÃ©clenchÃ©e. Configuration
serveur `CALENDLY_CLIENT_ID`/`CALENDLY_CLIENT_SECRET`, callback `/crm/oauth/calendly`, scopes de
lecture seulement. Sans identifiants le bouton est dÃ©sactivÃ©. ProcÃ©dure : [CALENDLY.md](CALENDLY.md).

Jetons, profil et pages chiffrÃ©s ; OAuth PKCE/session/Ã©tat Ã  usage unique et rÃ©visions ; rotation
des jetons sÃ©rialisÃ©e et persistÃ©e mÃªme si la dÃ©couverte suivante Ã©choue ; Ã©chec ambigu du
renouvellement traitÃ© par reconnexion. Audits sans contenu externe ni secret. Protection des liens
et endpoints, pagination bornÃ©e, seuls les types personnels solo proposÃ©s. DÃ©connexion accessible
au propriÃ©taire mÃªme aprÃ¨s retrait du rÃ´le, sans toucher aux comptes des autres ni Ã  Google.
Politique publique complÃ©tÃ©e pour le traitement Calendly facultatif.

VÃ©rifications : tests backend de droits, chiffrement, OAuth refusÃ©/expirÃ©/rejouÃ©/autre session,
retour obsolÃ¨te aprÃ¨s dÃ©connexion, choix hors compte, rotation et perte de rÃ´le ; concurrence
PostgreSQL incluse dans la CI ; parcours Vue de choix/actualisation et fournisseur non configurÃ©,
non-rÃ©gression du parcours agenda existant, typage et build. Aucun compte Calendly rÃ©el connectÃ©
ni rÃ©servation effectuÃ©e ; recette OAuth rÃ©elle en attente des identifiants et du consentement
du conseiller. Le navigateur local Ã©tant dÃ©sactivÃ©, aucune recette visuelle revendiquÃ©e.

**Limites et suite** : ce lot ne rÃ©serve pas dans Orvia, ne transmet pas de prospect, ne synchronise
pas les rÃ©servations/annulations/reports, nâ€™ajoute aucun Ã©vÃ©nement ou dÃ©compte CRM. Le partage aux
setters selon leurs associations, la rÃ©servation compatible avec le forfait du conseiller et les
webhooks restent Ã  livrer. Ne pas prÃ©senter ce connecteur comme un module de rÃ©servation terminÃ©.

## Renommage visible AMX / CallVerify en Orvia

Les textes visibles passent Ã  Â« Orvia Â» : page de connexion, logo et titre de lâ€™onglet, messages de session et de mot de passe, notifications de tÃ¢ches, libellÃ©s des Ã©vÃ©nements dâ€™agenda, expÃ©diteur par dÃ©faut des e-mails, application dâ€™authentification (TOTP) et documentation de dÃ©ploiement. Limites volontaires : les pages ConfidentialitÃ© et Conditions gardent AMX comme exploitant lÃ©gal ; les noms techniques (classes CSS, clÃ©s de stockage, dÃ©pÃ´t, bases, clÃ© de propriÃ©tÃ© des Ã©vÃ©nements Google Â« AMXSyncKey Â») sont inchangÃ©s pour ne pas casser la production ni les Ã©vÃ©nements dÃ©jÃ  synchronisÃ©s.


## Vitrine Orvia CRM â€” prÃ©sentation commerciale Assurance

La page publique `/presentation/` devient une vitrine centrÃ©e sur le cÅ“ur mÃ©tier Assurance : fiches prospects, qualification, rÃ©sultats dâ€™appels, rappels, rendez-vous, relais setter/conseiller/administrateur et suivi de prÃ©sence/conclusion. Aucune mention commerciale de lâ€™Isolation. Le rythme et les codes graphiques de la rÃ©fÃ©rence Patch sont adaptÃ©s dans un HTML/CSS original : bleu Ã©lectrique quadrillÃ©, grands titres condensÃ©s, accents violet/orange, visuels gÃ©omÃ©triques originaux, parcours numÃ©rotÃ©, aperÃ§u explicitement illustratif, agendas, offres, FAQ et contact final. Aucun contenu, tÃ©moignage, logo client, chiffre de performance ou police propriÃ©taire de Patch repris.

Les trois formules Â« Essentiel Â», Â« Ã‰quipe Â» et Â« Sur mesure Â» sont indicatives, sur devis, avec pÃ©rimÃ¨tre et conditions Ã  convenir. Les actions ouvrent un courriel prÃ©rempli au contact confirmÃ© ; aucun paiement, abonnement ou rÃ©servation automatique. Les fonctionnalitÃ©s spÃ©cifiques ou intÃ©grations sur mesure sont prÃ©sentÃ©es comme Ã  Ã©valuer. Les dÃ©pendances de tÃ©lÃ©phonie et le fonctionnement de Google sont explicitÃ©s ; Microsoft/Calendly ne sont pas annoncÃ©s comme disponibles.

Polices libres Archivo et Barlow Condensed livrÃ©es localement avec licences OFL. Feuille de style propre Ã  la prÃ©sentation ; les deux pages juridiques et la vÃ©rification Search Console restent inchangÃ©es. Navigation mobile et FAQ natives, skip-link, un h1, sections nommÃ©es, focus visible et rÃ©duction du mouvement. Le petit script local ferme le menu mobile et ajoute des animations dâ€™apparition ; tout le contenu, la navigation et les contacts restent utilisables sans JavaScript. Aucun traceur, cookie, formulaire de collecte ni chargement tiers ajoutÃ©. Cette refonte remplace la description antÃ©rieure de la prÃ©sentation comme une page sans script ; les pages juridiques restent sans script.

Validation : formatage explicite des actifs publics, syntaxe JavaScript, liens/ancres/sections et fichiers rÃ©fÃ©rencÃ©s, SVG, prÃ©sence des licences et du HTML dans le build Vite, absence dâ€™Isolation dans la prÃ©sentation. Le navigateur est dÃ©sactivÃ© dans les rÃ©glages Work : aucune comparaison visuelle au pixel prÃ¨s, recette mobile visuelle ni audit/certification RGAA/WCAG revendiquÃ©. Les styles adaptatifs sont fournis mais leur rendu doit encore Ãªtre revu visuellement. Les contrÃ´les GitHub et les contenus HTTPS sont vÃ©rifiÃ©s avant clÃ´ture de livraison. Aucun appel, consentement externe, e-mail envoyÃ© ni Ã©vÃ©nement crÃ©Ã©.

Suite : revue visuelle de la prÃ©sentation par lâ€™utilisateur, adaptation des offres et tarifs ; puis reprise du premier consentement Google du conseiller. Cette prÃ©sentation ne constitue pas une validation juridique, une approbation Google ni un module de vente/facturation.

## VÃ©rification du domaine pour Google Search Console

Ajout du fichier de vÃ©rification Google Ã  la racine publique (/google6195fcacccb8a875.html), servi tel quel par Nginx sans session, afin de prouver la propriÃ©tÃ© de orvia-crm.com avant la validation de lâ€™Ã©cran de consentement OAuth. Le fichier ne contient aucun secret. Limite : la validation elle-mÃªme se fait dans Search Console aprÃ¨s dÃ©ploiement.

## Connexion des agendas â€” prÃ©sentation et logos des fournisseurs

Lâ€™onglet conseiller Â« Mes agendas connectÃ©s Â» prÃ©sente Google Calendar et Microsoft Outlook dans deux cartes distinctes avec leurs logos officiels, conservÃ©s localement dans le build. Le composant partagÃ© reprend cette prÃ©sentation dans les autres accÃ¨s personnels aux agendas. Le bandeau et les trois Ã©tapes expliquent connexion, horaires puis activation volontaire de la publication. Lâ€™Ã©tat de chaque fournisseur provient toujours de lâ€™API : non connectÃ©, connectÃ© ou connexion non activÃ©e (Â« Ã€ venir Â»). Un compte dÃ©jÃ  connectÃ© doit Ãªtre dÃ©connectÃ© avant de choisir un autre fournisseur ; les commandes de retrait des Ã©vÃ©nements et de rÃ©cupÃ©ration restent accessibles.

Les outils de consultation des pÃ©riodes occupÃ©es, publication, pause, synchronisation manuelle et historique sont conservÃ©s. Le retrait des Ã©vÃ©nements, la rÃ©cupÃ©ration par mot de passe/confirmation et les limites de confidentialitÃ© restent regroupÃ©s dans des dÃ©tails dÃ©pliables. Les boutons dÃ©sactivÃ©s ne prÃ©sentent plus dâ€™explication technique OAuth ; aucune activation Microsoft/Calendly ni changement dâ€™autorisations ou dâ€™API dans ce lot. La mise en page passe en une colonne sur petit Ã©cran, possÃ¨de des Ã©tats de chargement/erreur et respecte la rÃ©duction des animations.

Validation : typage Vue, ESLint sur les composants modifiÃ©s, trois tests du parcours agenda (horaires, conflit de rÃ©vision, fournisseur non configurÃ© et conversion des dates avec fuseau), build Vite et contrÃ´le visuel du parcours conseiller dans la recette locale (connexion, ouverture des deux onglets, logos et fournisseurs non configurÃ©s). Les contrÃ´les CI prÃ©cÃ¨dent la fusion. Aucun consentement Google rÃ©el, Ã©criture calendrier, appel ou e-mail dÃ©clenchÃ© ; les Ã©tats connectÃ©s et la publication rÃ©elle restent Ã  recetter avec le propriÃ©taire du compte. Les logos sont documentÃ©s dans `frontend/src/assets/calendar/README.md`.

Suite : le conseiller autorise son compte Google en production ; vÃ©rifier ses crÃ©neaux occupÃ©s, puis la publication sur un rendez-vous de test explicitement choisi. Microsoft et Calendly restent en attente Ã  la demande de lâ€™utilisateur.

## Import de contacts visible pour lâ€™administrateur Assurance

Sur la page Prospects, lâ€™administrateur voit dÃ©sormais un bouton Â« Importer des contacts Â» en haut Ã  droite : il ouvre directement lâ€™Ã©cran dâ€™import (CSV ou Excel) sans passer par Â« Liste et imports Â». Quand le tableau est vide, un message lâ€™invite Ã  importer une liste avec le mÃªme bouton. Les setters et conseillers ne voient pas ce bouton. Limite : aucun changement du format dâ€™import ni des rÃ¨gles de dÃ©doublonnage ; revue esthÃ©tique reportÃ©e Ã  la revue finale.

## Pages publiques Orvia CRM pour lâ€™identitÃ© OAuth

Correctif de permissions aprÃ¨s la premiÃ¨re recette HTTPS : le checkout de production en umask restrictif produit des fichiers publics en 600, conservÃ©s par Vite, qui rÃ©pondent 403 pour Nginx. Lâ€™image web normalise uniquement son rÃ©pertoire dâ€™assets compilÃ©s en dossiers 755/fichiers 644 ; aucun fichier privÃ© ni secret nâ€™est concernÃ©. La correction est vÃ©rifiÃ©e sur les trois pages et la feuille de style, puis intÃ©grÃ©e au build pour rÃ©sister aux prochains dÃ©ploiements.

Trois pages publiques sont servies sans session : `/presentation/` (fonctionnalitÃ©s et accÃ¨s CRM), `/confidentialite/` et `/conditions/`. Les informations confirmÃ©es sont AMX, BÃ©nin et lâ€™adresse de contact assistance/confidentialitÃ© choisie par lâ€™utilisateur. Les pages sont du HTML statique avec une feuille de style locale, une navigation commune, liens croisÃ©s et raccourci vers `/crm`, sans script, suivi ni requÃªte Ã  lâ€™API. Le build les copie dans ses fichiers publics ; le fallback existant de Nginx sert leurs index. La racine/connexion et les callbacks OAuth ne sont pas modifiÃ©s.

La politique dÃ©crit comptes/dossiers, donnÃ©es de calendrier lues/utilisÃ©es/conservÃ©es/partagÃ©es, permissions Google, publication facultative dâ€™Ã©vÃ©nements neutres, jetons chiffrÃ©s, arrÃªt de publication, retrait/dÃ©connexion et rÃ©vocation Google, demandes de suppression et autres droits, cookies nÃ©cessaires, fournisseurs Contabo/Brevo et traitement hors BÃ©nin. Elle prÃ©cise lâ€™utilisation limitÃ©e des donnÃ©es Google et leurs exclusions publicitaires/vente/entraÃ®nement gÃ©nÃ©ral. Aucun renseignement dâ€™immatriculation, adresse postale, durÃ©e fixe de conservation ou dÃ©claration rÃ©glementaire non confirmÃ© nâ€™est inventÃ©. Les conditions dÃ©crivent comptes autorisÃ©s, responsabilitÃ©s de saisie, usages, agendas et disponibilitÃ© sans garantie absolue.

Validation : format des fichiers publics, contrÃ´le des liens internes et de lâ€™absence de script, identitÃ©/contact, compilation Vite et prÃ©sence des trois documents/feuille de style dans le build. Les contrÃ´les GitHub prÃ©cÃ¨dent la fusion ; la recette de production vÃ©rifiera chaque contenu HTTPS sans authentification aprÃ¨s CD. Aucun consentement, appel, e-mail ni Ã©vÃ©nement externe crÃ©Ã©. Aucune donnÃ©e privÃ©e ni secret ajoutÃ©.

Limites : ces pages ne constituent ni une validation juridique exhaustive, ni une approbation Google, ni une publication automatique de lâ€™application OAuth. Les durÃ©es opÃ©rationnelles de rÃ©tention restent Ã  prÃ©ciser par AMX. Aucun logo raster ajoutÃ©. `docs/GOOGLE_PUBLIC_PAGES.md` fournit les champs Ã  recopier dans Branding et distingue ces liens de lâ€™URI de retour OAuth.

Suite : vÃ©rifier les pages publiques aprÃ¨s CD, renseigner les liens dans Google Auth Platform, vÃ©rifier le domaine dans Search Console, puis terminer le premier consentement et les Ã©tapes Google nÃ©cessaires Ã  la publication.


## Google Calendar configurÃ© en production â€” consentement propriÃ©taire attendu

Le client OAuth Web Google crÃ©Ã© par lâ€™utilisateur est configurÃ© dans le `.env` privÃ© du VPS. Lâ€™ID et le vrai secret client ont Ã©tÃ© saisis localement puis transmis par SSH vÃ©rifiÃ© aprÃ¨s autorisation explicite de lâ€™utilisateur. Une premiÃ¨re saisie avait confondu ID et secret ; cette valeur a Ã©tÃ© retirÃ©e, puis remplacÃ©e aprÃ¨s contrÃ´le quâ€™ils sont distincts. La configuration prÃ©cÃ©dente est sauvegardÃ©e hors Git ; la clÃ© de chiffrement calendrier existante reste inchangÃ©e. Aucun secret, fichier OAuth ni jeton nâ€™est ajoutÃ© au dÃ©pÃ´t. Les services ont Ã©tÃ© rechargÃ©s avec la configuration Compose valide.

Validation serveur : paramÃ¨tres Google chargÃ©s, redirection exacte `https://orvia-crm.com/crm/oauth/google`, URL dâ€™autorisation vers Google avec PKCE S256 et accÃ¨s hors ligne, absence du secret dans cette URL et page de retour HTTPS Ã  200. Aucun compte Google interrogÃ© par cette recette ; aucun consentement rÃ©el, Ã©change de code, lecture des pÃ©riodes occupÃ©es ni publication dâ€™Ã©vÃ©nement encore validÃ©. ZÃ©ro agenda connectÃ© Ã  ce stade. Cette livraison est une configuration serveur, pas une intÃ©gration fournisseur entiÃ¨rement recettÃ©e.

Le parcours existant permet au conseiller Assurance et au client Isolation de connecter leur propre agenda principal. Les administrateurs et setters ne consentent pas Ã  leur place. Chaque propriÃ©taire doit Ãªtre autorisÃ© dans lâ€™audience du client OAuth ; en mode Google Test, ajouter ses comptes aux utilisateurs tests. La publication automatique des rendez-vous demande ensuite une activation explicite du propriÃ©taire. Aucun rappel, e-mail, appel ou Ã©vÃ©nement externe nâ€™a Ã©tÃ© crÃ©Ã© par ce lot. Microsoft reste non configurÃ© et Calendly est reportÃ©.

Suite : effectuer le premier consentement Google depuis le compte propriÃ©taire, vÃ©rifier la connexion et les pÃ©riodes occupÃ©es, puis activer et recetter la publication sur un rendez-vous de test autorisÃ©. PrÃ©parer ensuite Microsoft et la publication/validation OAuth Google pour lâ€™accÃ¨s hors mode test.

## Accueil â€” section Â« Alertes et notifications Â» refondue

Les deux panneaux repliables de lâ€™accueil Assurance (Â« Alertes et notifications Â» pour lâ€™administrateur, Â« Rappels et notifications Â» pour le setter) deviennent une seule section toujours visible, avec des cartes Ã  chiffres.

- **Ã‰chÃ©ances des mandats et contrats** (administrateur) : trois tuiles â€” date de fin dÃ©passÃ©e, dans les 30 jours, sans date de fin. Les deux premiÃ¨res sont cliquables, et se colorent quand elles sont non nulles.
- **Notifications de suivi** (administrateur et setter) : tuiles Â« liÃ©es Ã  un suivi ouvert Â» et Â« non lues Â», puis Â« Voir les notifications Â» (filtres, marquer comme lue, pagination, inchangÃ©s) et Â« Ouvrir les tÃ¢ches de suivi Â».
- **Rappels automatiques** (administrateur seulement) : compteur dâ€™escalades administratives actives et rÃ©glage de la cadence des rappels, avec le mÃªme formulaire et les mÃªmes rÃ¨gles quâ€™avant.
- Le bloc **Â« Rappels actifs Â»** et ses boutons (liste des rappels, tÃ¢ches de suivi, rendez-vous et comptes rendus) sont retirÃ©s pour tous les rÃ´les : les notifications de suivi couvrent les mÃªmes Ã©vÃ©nements. Le rÃ©glage des rappels nâ€™est pas perdu : il reste dans la carte des administrateurs.
- Mise en page adaptÃ©e : deux colonnes sur ordinateur, une colonne sur tÃ©lÃ©phone, sans dÃ©bordement.

Validation : typage, ESLint, Prettier, 119 tests frontend et build ; contrÃ´le dans le CRM local en administrateur (trois cartes, rÃ©glage des rappels et liste des notifications qui sâ€™ouvrent et se ferment), en setter (une seule carte) et en vue tÃ©lÃ©phone 375 px (une colonne, aucun dÃ©bordement).

Limites : aucun test automatisÃ© dÃ©diÃ© Ã  ces trois composants (vÃ©rifiÃ©s dans le navigateur). Les chiffres Ã©taient Ã  zÃ©ro dans la base locale : le rendu avec des donnÃ©es rÃ©elles (listes de notifications, tuiles colorÃ©es) reste Ã  voir en production.

## E-mails â€” nouveau format avec bandeau et mise en page mobile

Les e-mails du portail adoptent un format Ã  bandeau : logo en haut Ã  droite, titre en majuscules sur fond bleu, Â« Bonjour PrÃ©nom, Â», informations en liste Ã  puces, bouton arrondi et pied de page en deux colonnes. Le modÃ¨le sâ€™adapte aux tÃ©lÃ©phones : sous 480 px, le bouton occupe toute la largeur, les marges se resserrent et le pied de page sâ€™empile. Le prÃ©nom est dÃ©duit de lâ€™identifiant (Â« camille.exemple Â» devient Â« Camille Exemple Â») ; une adresse e-mail nâ€™est jamais affichÃ©e. Les appelants (invitation, mot de passe oubliÃ©, rappels Assurance) passent simplement lâ€™identifiant, et `layout()` reste compatible avec lâ€™existant.

Validation : deux tests du modÃ¨le (prÃ©nom et Ã©chappement, rÃ¨gles responsives) ; suites portail (246) et Assurance (347) ; Ruff ; galerie bureau et mobile contrÃ´lÃ©e dans le navigateur : trois e-mails en deux tailles, sans dÃ©bordement horizontal Ã  360 px, bouton en pleine largeur uniquement sur mobile.

Limites : rendu vÃ©rifiÃ© dans un navigateur, pas dans chaque messagerie (Outlook de bureau applique ses propres rÃ¨gles ; le bouton y reste lisible mais sans coins arrondis). Pas de logo image ni de mode sombre. Le texte brut de chaque e-mail est inchangÃ©.

## E-mails transactionnels Orvia CRM â€” HTML et texte

Les nouvelles invitations aux espaces Assurance/Isolation, rÃ©initialisations de mot de passe et notifications de suivi Assurance (rappels, signalements, escalades) utilisent une prÃ©sentation commune Orvia CRM : bandeau bleu nuit, titre explicite, bouton bleu, encadrÃ© dâ€™information et lien de secours copiable. Le HTML autonome utilise des tableaux et styles en ligne, sans police distante, image externe ni pixel de suivi. Les valeurs dynamiques sont Ã©chappÃ©es et les liens dâ€™action utilisent les URL existantes du CRM. Les objets et versions texte sont harmonisÃ©s avec Orvia CRM ; les dÃ©tails de dossiers ne sont pas ajoutÃ©s aux notifications de suivi.

Le HTML est conservÃ© dans la charge utile chiffrÃ©e de la file dâ€™envoi avec le texte, le destinataire et les garde-fous existants, puis envoyÃ© en multipart texte/HTML. Les messages en attente issus de lâ€™ancienne version, sans clÃ© HTML dans leur charge utile, restent envoyables en texte seul. Les liens Ã  usage unique, vÃ©rifications dâ€™Ã©ligibilitÃ©, expirations, reprises SMTP, audits et effacement terminal restent en place ; aucune migration de schÃ©ma. Les messages dÃ©jÃ  en attente ne sont pas rÃ©Ã©crits. Les rappels concernÃ©s sont les notifications existantes destinÃ©es aux utilisateurs autorisÃ©s, pas de nouveaux rappels de rendez-vous adressÃ©s aux prospects ni dâ€™e-mails Isolation ajoutÃ©s.

Validation : 244 tests du portail rÃ©ussis localement (11 scÃ©narios PostgreSQL ignorÃ©s sur SQLite), dont quatre nouveaux tests de rendu sÃ©curisÃ©, liens identiques et Ã©chappement HTML, refus dâ€™URL dangereuses, chiffrement/envoi multipart/effacement et compatibilitÃ© des anciennes charges utiles. Les parcours invitation, rÃ©cupÃ©ration et suivi existants vÃ©rifient maintenant aussi leur HTML. AprÃ¨s ces ajouts dâ€™assertions, 45 tests e-mail ciblÃ©s rÃ©ussis (3 scÃ©narios PostgreSQL ignorÃ©s localement), Ruff et gÃ©nÃ©ration de la galerie synthÃ©tique. La CI exÃ©cute aussi les parcours PostgreSQL. `python scripts/preview_crm_emails.py CHEMIN.html` gÃ©nÃ¨re une galerie locale bureau/mobile avec liens non utilisables et sans SMTP.

Point de production relevÃ© pendant ce lot : le CD de la livraison documentaire prÃ©cÃ©dente (40045103279) a appliquÃ© le commit et terminÃ© ses migrations, puis Ã©chouÃ© au contrÃ´le HTTPS /crm Ã  404. Les quatre DNS autoritaires LWS publient Ã  nouveau un AAAA vers lâ€™ancien hÃ©bergement ; le VPS ciblÃ© avec certificat valide et le domaine en IPv4 rÃ©pondent 200. La rÃ©solution normale privilÃ©gie lâ€™ancien serveur en IPv6. La correction DNS est demandÃ©e Ã  lâ€™utilisateur avant de dÃ©clarer le prochain CD validÃ©.

Limites : aperÃ§u HTML gÃ©nÃ©rÃ©, pas de validation visuelle exhaustive dans Gmail/Outlook ni en mode sombre. Les styles en ligne et tableaux facilitent la compatibilitÃ© sans la garantir dans tous les clients. Aucun e-mail rÃ©el supplÃ©mentaire envoyÃ© par ce lot ; la rÃ©ception en boÃ®te et les rendus natifs restent Ã  vÃ©rifier avec lâ€™utilisateur. Le transport et lâ€™expÃ©diteur Brevo restent ceux configurÃ©s sur le VPS. Aucun nouveau type dâ€™Ã©vÃ©nement mÃ©tier ni connecteur ajoutÃ©.

Suite : valider les aperÃ§us avec lâ€™utilisateur et relever les retouches prÃ©cises, puis vÃ©rifier les parcours transactionnels autorisÃ©s en messagerie rÃ©elle.


## CD activÃ© et premier dÃ©ploiement GitHub validÃ©

La variable de dÃ©pÃ´t `CD_ENABLED` est Ã  true aprÃ¨s autorisation explicite de lâ€™utilisateur. La validation CI de main a Ã©tÃ© relancÃ©e, puis le workflow Deploy CRM production a rÃ©ellement exÃ©cutÃ© le dÃ©ploiement du commit validÃ© via le compte SSH dÃ©diÃ© et la clÃ© hÃ´te vÃ©rifiÃ©e. ExÃ©cution GitHub `40044574801` rÃ©ussie : sauvegarde prÃ©alable des trois bases, fichiers et configuration privÃ©e, mise Ã  jour du clone, construction, migrations et contrÃ´les HTTPS par DNS normal. Le marqueur de dÃ©ploiement nâ€™est Ã©crit quâ€™aprÃ¨s les rÃ©ponses attendues. Lâ€™environnement production reste limitÃ© Ã  main et les secrets restent hors Git.

Validation aprÃ¨s ce premier CD : recette authentifiÃ©e HTTPS du portail (connexion, session, rÃ´le administrateur des deux espaces), lecture des listes Assurance et Isolation de production vides, dÃ©connexion effective. Aucun appel, rÃ©servation, e-mail supplÃ©mentaire ou jeu de dÃ©monstration crÃ©Ã© par cette recette. Le CD est dÃ©sormais opÃ©rationnel pour les futures fusions de main dont les contrÃ´les rÃ©ussissent ; ce lot ne promet ni absence dâ€™interruption pendant les migrations ni rollback automatique.

Limites conservÃ©es : sauvegardes privÃ©es locales au VPS, sans copie hors serveur ni recette de restauration complÃ¨te ; vÃ©rifications HTTP et parcours dâ€™accÃ¨s restreints, pas recette mÃ©tier exhaustive. La rÃ©ception du prÃ©cÃ©dent test Brevo reste Ã  confirmer par lâ€™utilisateur. Les connecteurs dâ€™appels, Twilio et agendas ne sont pas activÃ©s par le CD.

Suite : travailler avec lâ€™utilisateur la prÃ©sentation des e-mails transactionnels du CRM, puis vÃ©rifier les gabarits et les parcours concernÃ©s.


## Transport Brevo de production configurÃ© et test SMTP acceptÃ©

AprÃ¨s autorisation de lâ€™IP du VPS dans Brevo par lâ€™utilisateur, lâ€™authentification SMTP rÃ©ussit sur le port 587 avec STARTTLS et validation du certificat. Le refus prÃ©cÃ©dent Ã©tait identifiÃ© par le code 525 (IP non autorisÃ©e), distinct du refus 535 dâ€™identifiants. Le transport du portail et celui dâ€™Isolation sont configurÃ©s dans le `.env` privÃ© du VPS, avec lâ€™expÃ©diteur validÃ© indiquÃ© par lâ€™utilisateur et le nom Orvia CRM. La configuration prÃ©cÃ©dente a Ã©tÃ© sauvegardÃ©e hors Git avant modification ; Compose valide la configuration et les services ont Ã©tÃ© relancÃ©s. Aucune clÃ© SMTP ni adresse de destinataire nâ€™est ajoutÃ©e au dÃ©pÃ´t.

Validation : authentification SMTP depuis le VPS, envoi dâ€™un seul message de test explicitement autorisÃ© via `django.core.mail.send_mail` du portail (un message acceptÃ© par le relais), connexion SMTP Isolation sans envoi supplÃ©mentaire, quinze services en cours dâ€™exÃ©cution et page CRM en HTTPS Ã  200 via le DNS normal du VPS. Le secret est utilisÃ© sans affichage et reste dans des fichiers privÃ©s exclus de Git. Lâ€™utilisateur doit encore constater la rÃ©ception : lâ€™acceptation SMTP ne prouve pas la livraison en boÃ®te ni le classement hors spam.

Limites : test du transport, pas recette exhaustive des invitations, rÃ©initialisations et rappels planifiÃ©s. Lâ€™expÃ©diteur utilise lâ€™adresse Gmail choisie par lâ€™utilisateur ; lâ€™authentification dâ€™un domaine dâ€™expÃ©dition propre et la dÃ©livrabilitÃ© restent Ã  valider dans Brevo. Aucun autre message mÃ©tier, appel ou jeu de dÃ©monstration ajoutÃ©. CD toujours dÃ©sactivÃ© Ã  cette Ã©tape ; les sauvegardes hors serveur et la restauration rÃ©elle restent Ã  mettre en place.

Suite : confirmer la rÃ©ception du test, puis activer et valider le workflow CD sur un commit main contrÃ´lÃ©. VÃ©rifier ensuite les parcours transactionnels e-mail avec les destinataires autorisÃ©s.


## PremiÃ¨re installation HTTPS et administrateur de production

Le domaine racine pointe vers le VPS sur les serveurs DNS LWS ; lâ€™ancien AAAA a disparu de la zone autoritaire et du rÃ©solveur Cloudflare. La premiÃ¨re installation rÃ©elle a Ã©tÃ© exÃ©cutÃ©e avec la configuration privÃ©e existante : images reconstruites, trois bases PostgreSQL initialisÃ©es et migrÃ©es, services CRM dÃ©marrÃ©s et certificat HTTPS valide obtenu pour `orvia-crm.com`. Un premier administrateur dispose des deux espaces ; son mot de passe alÃ©atoire reste dans des fichiers privÃ©s sur le serveur et sur le PC de lâ€™utilisateur, jamais dans Git ni les journaux. Aucune donnÃ©e de dÃ©monstration nâ€™a Ã©tÃ© transfÃ©rÃ©e.

Recette HTTPS ciblant explicitement lâ€™IPv4 du VPS, sans dÃ©sactiver la validation du certificat : page CRM et CSRF Ã  200, connexion par mot de passe et session, accÃ¨s signÃ©s administrateur aux listes Assurance et Isolation vides, dÃ©connexion et refus de la session terminÃ©e. Les API sans authentification rÃ©pondent 401/403 ; une route interne du portail est inaccessible (404) ; HTTP redirige vers HTTPS (308). Une sauvegarde locale initiale des trois bases et des fichiers a Ã©tÃ© crÃ©Ã©e, avec contrÃ´le des catalogues `pg_restore --list` et de lâ€™archive ; cela ne constitue pas encore un test de restauration ni une sauvegarde hors serveur.

La sauvegarde via SSH a rÃ©vÃ©lÃ© quâ€™un processus Docker attachÃ© Ã  stdin pouvait consommer la suite du script CD transmis par SSH et laisser une sortie 0 sans dÃ©ploiement ni contrÃ´le final. `deploy-release.sh` fournit dÃ©sormais `/dev/null` aux exports, Ã  lâ€™archivage et au script de dÃ©ploiement ; la validation des dumps conserve son entrÃ©e fichier. Le nouveau test transmet rÃ©ellement le script sur stdin, avec enfants qui consomment lâ€™entrÃ©e : Ã©chec reproduit avant correction, puis suite complÃ¨te de neuf tests rÃ©ussie aprÃ¨s correction. Ruff et les contrÃ´les GitHub complÃ¨tent cette validation ; aucune modification des rÃ¨gles mÃ©tier.

Limites : certains rÃ©solveurs du PC et du VPS rÃ©pondent encore avec lâ€™ancienne IPv6 LWS en cache malgrÃ© la suppression autoritaire, ce qui peut afficher une page LWS/404. Les tests ci-dessus valident le VPS et son certificat, pas une propagation terminÃ©e partout. Le CD reste Ã  false jusquâ€™Ã  validation des contrÃ´les HTTPS sans ciblage dâ€™IP et recette du workflow complet aprÃ¨s correction. Lâ€™expÃ©diteur et le transport Brevo restent Ã  configurer ; invitations, rÃ©cupÃ©ration de mot de passe et rappels par e-mail ne sont pas dÃ©clarÃ©s opÃ©rationnels. Appels NEWT, lookup Twilio et agendas externes restent dÃ©sactivÃ©s/non configurÃ©s. Les contrÃ´les Django signalent encore des avertissements dâ€™en-tÃªtes/HTTPS gÃ©rÃ©s par Caddy et dâ€™absence de middleware CSRF sur lâ€™API Assurance Ã  jetons ; ils ne constituent pas une recette de sÃ©curitÃ© exhaustive. Aucune revue visuelle navigateur effectuÃ©e.

Suite : configurer lâ€™expÃ©diteur Brevo, constater lâ€™expiration des caches DNS, puis activer et tester le CD sur un commit main validÃ©. Restent aussi la copie des sauvegardes hors serveur, leur rÃ©tention et une restauration rÃ©elle sur une cible distincte.


## Domaine de production choisi â€” DNS encore chez LWS

Lâ€™utilisateur a choisi `orvia-crm.com`. Le clone propre du VPS a Ã©tÃ© synchronisÃ© avec main ; la configuration privÃ©e de production a Ã©tÃ© gÃ©nÃ©rÃ©e sur le serveur pour ce domaine, avec de nouvelles clÃ©s internes et mots de passe de bases alÃ©atoires, sans affichage ni transfert vers Git. Le fichier `.env` est vÃ©rifiÃ© en mode 600. La configuration Compose de production est valide ; DEBUG, les appels NEWT et la vÃ©rification Twilio restent dÃ©sactivÃ©s. Aucune clÃ© dÃ©jÃ  en place nâ€™a Ã©tÃ© rÃ©gÃ©nÃ©rÃ©e.

Le DNS observÃ© pointe encore vers lâ€™hÃ©bergement LWS, en IPv4 et IPv6. Lâ€™utilisateur doit remplacer le A du domaine racine par lâ€™IPv4 du VPS et supprimer lâ€™ancien AAAA du domaine racine, sans modifier les serveurs DNS ni les entrÃ©es de messagerie. La gestion reste chez LWS ; aucun accÃ¨s au compte LWS ni modification DNS nâ€™a Ã©tÃ© effectuÃ© par lâ€™agent.

Validation : gÃ©nÃ©ration du fichier privÃ© puis contrÃ´le de son domaine, de ses permissions et des indicateurs de fournisseurs ; `docker compose ... config -q` rÃ©ussi. Aucun service applicatif dÃ©marrÃ©, certificat obtenu, compte administrateur crÃ©Ã©, invitation envoyÃ©e ou appel passÃ©. Aucun secret ajoutÃ© au dÃ©pÃ´t. La configuration SMTP reste Ã  complÃ©ter et vÃ©rifier ; les identifiants Twilio concernent la vÃ©rification Isolation et ne sont pas requis pour prÃ©parer lâ€™installation du CRM.

Suite : constater le pointage DNS vers le VPS, renseigner la messagerie, terminer la premiÃ¨re installation et la recette HTTPS avant dâ€™activer le CD, toujours Ã  false.


## Secrets CD de production configurÃ©s â€” activation toujours suspendue

AprÃ¨s autorisation explicite de lâ€™utilisateur, la clÃ© SSH du compte de dÃ©ploiement dÃ©diÃ© et la clÃ© hÃ´te vÃ©rifiÃ©e ont Ã©tÃ© enregistrÃ©es respectivement dans les secrets `CD_SSH_KEY` et `CD_KNOWN_HOSTS` de lâ€™environnement GitHub `production`. La clÃ© privÃ©e est transmise directement Ã  la commande de gestion des secrets, sans affichage ni ajout aux fichiers suivis. Les secrets ne figurent pas dans le dÃ©pÃ´t public. Cette Ã©tape lÃ¨ve le blocage de transfert mentionnÃ© dans le lot prÃ©cÃ©dent.

Validation : prÃ©sence des deux noms de secrets contrÃ´lÃ©e sans lecture de leur contenu ; environnement toujours limitÃ© Ã  la branche main ; variable de dÃ©pÃ´t `CD_ENABLED` vÃ©rifiÃ©e Ã  `false`. Aucun workflow de dÃ©ploiement lancÃ© ni service applicatif dÃ©marrÃ© par ce lot. La connexion par cette clÃ© au compte de dÃ©ploiement avait Ã©tÃ© vÃ©rifiÃ©e pendant la prÃ©paration du VPS ; aucune exÃ©cution GitHub vers le VPS nâ€™est encore dÃ©clarÃ©e rÃ©ussie.

Restent Ã  faire : domaine/DNS, paramÃ¨tres SMTP, configuration privÃ©e dÃ©finitive, premiÃ¨re installation et migrations, administrateur de production, recette HTTPS des parcours authentifiÃ©s, sauvegardes hors serveur et restauration. Le CD sera activÃ© et testÃ© aprÃ¨s cette recette initiale, pas simplement Ã  la prÃ©sence des secrets.

Suite : finaliser lâ€™installation dÃ¨s rÃ©ception du domaine et des paramÃ¨tres de messagerie.


## PrÃ©paration rÃ©elle du VPS Ubuntu â€” publication en attente

Le VPS a Ã©tÃ© inspectÃ© par SSH aprÃ¨s connexion initiale de lâ€™utilisateur et autorisation dâ€™une clÃ© dÃ©diÃ©e : Ubuntu 24.04.5 LTS, architecture amd64, environ 24 Go de RAM et 290 Go de disque. Ubuntu Ã©tait dÃ©jÃ  installÃ© ; aucune rÃ©installation ni remise Ã  zÃ©ro du serveur nâ€™a Ã©tÃ© rÃ©alisÃ©e. Docker Engine 29.9.2 et le plugin Compose 5.6.1 ont Ã©tÃ© installÃ©s depuis le dÃ©pÃ´t APT officiel Docker. Docker dÃ©marre avec le systÃ¨me. Le compte de dÃ©ploiement `amx-deploy`, avec une clÃ© distincte de lâ€™accÃ¨s administrateur, appartient au groupe Docker ; le clone de main est placÃ© dans `/opt/amx-crm`. Le pare-feu UFW autorise SSH, HTTP et HTTPS, en IPv4 et IPv6. Les connexions par clÃ© administrateur et dÃ©ploiement ont Ã©tÃ© vÃ©rifiÃ©es avec contrÃ´le strict de la clÃ© hÃ´te dÃ©jÃ  approuvÃ©e par lâ€™utilisateur.

Lâ€™environnement GitHub `production` est limitÃ© Ã  la branche main, et les variables de dÃ©pÃ´t de connexion sont prÃ©parÃ©es ; `CD_ENABLED=false` reste explicite. Les secrets SSH ne sont pas enregistrÃ©s dans GitHub : le contrÃ´le dâ€™approbation automatique a refusÃ© ce transfert vers les secrets du dÃ©pÃ´t public en attendant une autorisation explicite de lâ€™utilisateur. Les clÃ©s privÃ©es et journaux de prÃ©paration restent dans le rÃ©pertoire local ignorÃ© par Git. Aucun mot de passe du VPS nâ€™a Ã©tÃ© collectÃ© dans le chat ou publiÃ©.

Validation sur le VPS : Docker actif et utilisable par le compte de dÃ©ploiement, clone propre, construction des images backend et frontend (avec typage Vue et build Vite), tÃ©lÃ©chargement des images PostgreSQL, Redis et Caddy. Aucun conteneur applicatif lancÃ© ; seuls SSH et les services DNS locaux Ã©coutent Ã  ce stade. Aucun `.env` de production ni base mÃ©tier initialisÃ©e ; aucune donnÃ©e de dÃ©monstration transfÃ©rÃ©e. La documentation de premiÃ¨re installation utilise maintenant le dÃ©pÃ´t APT officiel et ne propose plus le script de commoditÃ© Docker en production.

Limites : lâ€™utilisateur nâ€™a pas encore de domaine. La prÃ©paration du serveur ne constitue pas une production fonctionnelle. Restent Ã  faire : domaine et DNS, gÃ©nÃ©ration et conservation de la configuration privÃ©e, paramÃ¨tres SMTP, premiÃ¨re installation avec migrations, administrateur de production, recette HTTPS authentifiÃ©e, sauvegardes hors serveur et restauration, autorisation/configuration des secrets GitHub puis activation et recette du CD. Aucun appel ni envoi mÃ©tier effectuÃ©.

Suite : enregistrer la clÃ© dÃ©diÃ©e dans les secrets de lâ€™environnement GitHub production aprÃ¨s accord explicite, puis finaliser lâ€™installation dÃ¨s rÃ©ception du domaine et des paramÃ¨tres de messagerie.


## Pipeline CD prÃ©parÃ©e â€” activation serveur en attente

Le workflow Â« Deploy CRM production Â» attend la rÃ©ussite du workflow de validation sur un push de main du dÃ©pÃ´t dâ€™origine. Le commit validÃ© doit encore Ãªtre la tÃªte de main, vÃ©rifiÃ©e cÃ´tÃ© GitHub puis cÃ´tÃ© serveur. Les PR et branches ne dÃ©clenchent pas ce dÃ©ploiement. Les secrets sont limitÃ©s Ã  lâ€™environnement production ; clÃ© SSH et known_hosts vÃ©rifiÃ©s sont requis, sans collecte de clÃ© hÃ´te automatique ni dÃ©sactivation de sa vÃ©rification. Les dÃ©ploiements sont sÃ©rialisÃ©s et ne sâ€™interrompent pas Ã  chaque nouveau commit.

Le script serveur verrouille lâ€™installation, refuse les modifications Git suivies et les installations non initialisÃ©es, sauvegarde les trois bases PostgreSQL, les fichiers et le .env, puis change de commit et rÃ©utilise deploy.sh. Les services sont attendus au dÃ©marrage. Le succÃ¨s nâ€™est enregistrÃ© quâ€™aprÃ¨s rÃ©ponses attendues sur le HTTPS public du frontend et des trois API. Un Ã©chec avant validation ne laisse pas de marqueur de succÃ¨s ; une reprise du mÃªme commit reste possible. Aucun rollback de base automatique. Les archives privÃ©es sont exclues du build Docker et de Git. deploy/CD.md dÃ©crit les paramÃ¨tres, la premiÃ¨re installation, les limites et la restauration Ã  prÃ©parer.

Validation : huit tests Bash avec Git/Docker/HTTPS simulÃ©s (ordre sauvegarde/checkout/dÃ©ploiement, Ã©chec de sauvegarde, migration et disponibilitÃ©, commit dÃ©passÃ©, fichiers modifiÃ©s, verrou, arguments invalides, premiÃ¨re installation absente, reprise et idempotence), syntaxe Bash, Ruff, format et actionlint officiel v1.7.12 (archive vÃ©rifiÃ©e par SHA-256). Aucun contact SSH, changement ou dÃ©ploiement effectuÃ© sur le VPS ; aucun secret serveur saisi ou publiÃ©. Le mail dâ€™achat indique Ubuntu et lâ€™utilisateur root ; la version dâ€™Ubuntu, lâ€™accÃ¨s par clÃ© et le domaine HTTPS restent Ã  configurer.

Statut : code de la pipeline livrÃ©, CD dÃ©sactivÃ© par dÃ©faut (variable de dÃ©pÃ´t CD_ENABLED absente ou false), environnement/secrets et recette serveur non rÃ©alisÃ©s. Limites : construction sur VPS et interruption possible, sauvegardes locales dâ€™une application active sans instantanÃ© atomique entre services ; copie hors serveur, chiffrement, rÃ©tention et restauration pÃ©riodique Ã  mettre en place. Les contrÃ´les HTTP ne constituent pas une recette mÃ©tier authentifiÃ©e. Ce lot ne dÃ©clare pas la production dÃ©ployÃ©e.

Suite : obtenir un domaine, vÃ©rifier le VPS et son empreinte SSH, initialiser lâ€™installation, configurer les secrets GitHub puis valider le premier dÃ©ploiement avant activation du CD.


## Rendez-vous prÃ©cis depuis les dossiers clients

Lâ€™onglet Rendez-vous des dossiers administrateur Assurance et Isolation propose Â« Voir le rendez-vous Â» sur chaque ligne. Le panneau latÃ©ral charge lâ€™identifiant exact du rendez-vous/visite via les composants mÃ©tier existants, sans repasser par la liste des crÃ©neaux Ã  venir du prospect. Les rendez-vous passÃ©s et annulÃ©s restent donc directement consultables, avec qualification transmise, compte rendu et historique disponibles selon le module. Les actions existantes conservent leurs permissions et contrÃ´les serveur. Â« Ouvrir la fiche Â» et Â« Appels CRM Â» restent accessibles sÃ©parÃ©ment.

La fermeture est bloquÃ©e pendant une opÃ©ration et demande confirmation si des champs ont Ã©tÃ© modifiÃ©s depuis le dernier chargement/enregistrement ; une fermeture refusÃ©e conserve le panneau. Une fermeture confirmÃ©e recharge les compteurs et la liste du dossier avec leurs filtres. Aucune nouvelle API, rÃ¨gle de prÃ©sence, vente, quota ni action tÃ©lÃ©phonique ajoutÃ©e. Les rÃ©sultats conseiller/closer restent soumis Ã  leurs permissions, sans Ã©largissement Ã  lâ€™administrateur.

Validation : suite frontend complÃ¨te (119 tests), dont deux nouveaux scÃ©narios Assurance/Isolation : rendez-vous passÃ© annulÃ©, identifiant prÃ©cis distinct de la fiche, rÃ´le administrateur, fermeture pendant opÃ©ration et conservation des saisies si confirmation refusÃ©e ; typage, lint, format et contrÃ´les GitHub. Recette visuelle aprÃ¨s modification non rÃ©alisÃ©e : accÃ¨s navigateur local dÃ©sactivÃ© dans Work. Cette livraison ne constitue pas une revue esthÃ©tique exhaustive de lâ€™administration.

Suite : prÃ©parer le dÃ©ploiement continu aprÃ¨s rÃ©ception des paramÃ¨tres du serveur et du domaine ; ne pas activer de dÃ©ploiement rÃ©el sans cible configurÃ©e et vÃ©rifiÃ©e. Le fournisseur tÃ©lÃ©phonique reste dÃ©sactivÃ© dans la recette.


## Navigation des dossiers clients â€” repÃ¨res administrateur

Lâ€™ouverture dâ€™un dossier replace le titre du client dans la zone visible et lui donne le focus clavier, avec une marge sous lâ€™en-tÃªte fixe. Le retour Â« Tous les dossiers Â» restaure la derniÃ¨re recherche effectivement chargÃ©e et la page du rÃ©pertoire ; un brouillon de recherche non soumis ne remplace pas ce repÃ¨re. Le titre est Ã©galement remis en vue au retour. Les compteurs Â« RÃ©sultats des rendez-vous Â» et Â« Ã‰tapes commerciales des prospects Â» ont des groupes et libellÃ©s distincts ; le filtre actif est signalÃ© visuellement et par aria-pressed. Aucun statut mÃ©tier, quota, pÃ©rimÃ¨tre ni export modifiÃ©.

Validation : tests de navigation/recherche/page, dÃ©filement et focus au titre, Ã©tat du filtre actif ; suite frontend complÃ¨te, typage, lint et format. Le parcours Assurance a Ã©tÃ© observÃ© dans la dÃ©monstration sur Ã©cran Ã©troit et bureau avant correction : le dÃ©faut de position conservÃ©e masquait le titre. Cette correction ne constitue pas une refonte exhaustive des Ã©crans administrateur.

Suite : poursuivre la recette des fiches et des rendez-vous administrateur, puis traiter les Ã©carts visuels prÃ©cis relevÃ©s avec lâ€™utilisateur.


## Exports des dossiers clients â€” CSV et Excel

Dans Dossiers clients, les administrateurs Assurance et Isolation peuvent tÃ©lÃ©charger soit les rÃ©sultats de lâ€™onglet courant (prospects, rendez-vous, rÃ©sultats dâ€™appel, tÃ¢ches), soit la synthÃ¨se mÃ©tier gÃ©nÃ©rale du dossier. Lâ€™export de liste reprend la derniÃ¨re recherche et le statut effectivement chargÃ©s et porte sur toutes les pages, pas uniquement les 25 lignes affichÃ©es. La synthÃ¨se reste indÃ©pendante de ces filtres. Le format CSV utilise un sÃ©parateur point-virgule et un BOM UTF-8 ; le classeur Excel contient des cellules textuelles pour les valeurs susceptibles dâ€™Ãªtre interprÃ©tÃ©es comme des formules. Les appels rÃ©pÃ©tÃ©s pendant un tÃ©lÃ©chargement sont bloquÃ©s ; les fichiers portent lâ€™espace, le client et la section dans leur nom.

Les listes et exports partagent les mÃªmes requÃªtes et sÃ©rialiseurs de pÃ©rimÃ¨tre, avec les mÃªmes comptes rendus et auteurs. Les dates des fichiers sont en UTC ISO 8601 avec dÃ©calage explicite ; le fuseau du rendez-vous est conservÃ©. Les prÃ©sences et ventes dÃ©clarÃ©es du compte rendu restent consultables mÃªme aprÃ¨s annulation ; les indicateurs, eux, excluent ces annulations du dÃ©compte des prÃ©sences/ventes. Aucun compte rendu manquant nâ€™est transformÃ© en absence. Chaque export rÃ©ussi ajoute un audit (administrateur, client, section, format et nombre de lignes), sans tÃ©lÃ©phone, note ou recherche en mÃ©tadonnÃ©es. Au-delÃ  de 50 000 lignes CSV ou 20 000 lignes Excel, le fichier est refusÃ© explicitement, jamais tronquÃ©.

Limites affichÃ©es : export des listes mÃ©tier et de leurs indicateurs, sans piÃ¨ces jointes binaires, qualification complÃ¨te, historique technique NEWT, objectif administratif ni quota restant (ces derniers proviennent du portail). Les auteurs non nommÃ©s dans les listes restent identifiÃ©s par leur compte numÃ©rique. Les rÃ©sultats dâ€™appel sont des dÃ©clarations, pas des conversations connectÃ©es. Lâ€™historique complet des fiches peut prÃ©cÃ©der une rÃ©affectation ; les prospects de plusieurs dossiers ne constituent pas des populations disjointes. Le pÃ©rimÃ¨tre et cette rÃ¨gle sont rappelÃ©s dans les fichiers. Aucun nouveau connecteur, appel, message ou rÃ©servation ajoutÃ©.

Validation : 21 tests backend ciblÃ©s, dont 8 nouveaux tests dâ€™export ; 116 tests frontend, dont 3 nouveaux contrÃ´les des filtres appliquÃ©s, du nom du fichier et du verrouillage de tÃ©lÃ©chargement ; typage Vue, lint, format et build. Recette sur la base PostgreSQL synthÃ©tique : CSV complets de 250 prospects Assurance et 1 250 prospects Isolation, synthÃ¨ses Excel de 16 et 14 indicateurs relues avec openpyxl. Seules quatre entrÃ©es dâ€™audit dâ€™export ont Ã©tÃ© ajoutÃ©es aux donnÃ©es de recette. Aucun changement de schÃ©ma. Les autres exports de prospects conservent leur nom et leurs filtres par dÃ©faut. ContrÃ´le visuel navigateur non rÃ©alisÃ© (accÃ¨s local dÃ©sactivÃ© dans Work).

Ã€ suivre : revue des parcours administrateur et validation des interfaces avec lâ€™utilisateur. Les autres Ã©carts mÃ©tier/production restent recensÃ©s plus bas.


## Statistiques â€” tableau de bord (indicateurs, tendances, anneau et histogramme)

Les pages Statistiques Assurance et Isolation adoptent une prÃ©sentation de tableau de bord :

- **En-tÃªte** : Â« Bonjour, â€¦ Â» avec le pÃ©rimÃ¨tre affichÃ©.
- **Indicateurs** : quatre indicateurs en cartes, chacun avec sa tendance par rapport Ã  la pÃ©riode prÃ©cÃ©dente de mÃªme durÃ©e (badge vert ou rouge, inversÃ© quand une hausse est dÃ©favorable, comme les comptes rendus manquants) et une courbe quotidienne.
- **Graphiques** : un anneau Â« Issue des rendez-vous Â» et un histogramme Â« Volume des rendez-vous Â» regroupable par jour, semaine ou mois. Une infobulle donne le dÃ©tail au survol ou au clavier.
- **DÃ©tail par setter ou closer** : prÃ©sentÃ© dans une carte.

Contenu par espace :

- **Assurance** : rendez-vous, effectuÃ©s, taux effectuÃ© (Ã©cart en points) et comptes rendus manquants. Lâ€™anneau rÃ©partit effectuÃ©s, absences, autres non effectuÃ©s, sans compte rendu, Ã  venir et annulÃ©s.
- **Isolation** : rendez-vous rÃ©servÃ©s, tenus, ventes conclues et taux de conclusion. Lâ€™anneau rÃ©partit les ventes conclues, les tenus sans vente ou Ã  vente non renseignÃ©e, les non tenus, les rÃ©sultats manquants, les rendez-vous Ã  venir et les annulÃ©s. Lâ€™histogramme montre rÃ©servÃ©s, tenus et ventes.

Les filtres, exports, comparaisons et la mÃ©thode sont conservÃ©s.

Les API de statistiques renvoient en plus, hors export, `daily` (une ligne par jour, complÃ©tÃ©e par des zÃ©ros ; UTC en Assurance, fuseau choisi en Isolation) et `previous` (totaux de la pÃ©riode prÃ©cÃ©dente de mÃªme durÃ©e, avec le mÃªme pÃ©rimÃ¨tre de rÃ´le). Les exports CSV et Excel sont inchangÃ©s. La mise en page sâ€™adapte Ã  la largeur rÃ©ellement disponible : quatre, deux ou une colonne, sans dÃ©bordement sur tÃ©lÃ©phone.

Validation :

- Backend : un test Assurance et un test Isolation (sÃ©rie quotidienne, pÃ©riode prÃ©cÃ©dente, pÃ©rimÃ¨tre setter ou client).
- Frontend : test des tendances (hausse, stabilitÃ©, points, sens inversÃ©), de lâ€™histogramme et de la courbe.
- Les harnais existants affichent dÃ©sormais les vrais composants.
- Suites Assurance (335), Isolation (254) et frontend (108) complÃ¨tes, typage, ESLint, Prettier, Ruff et build.
- DÃ©mo `admin.demo` : Assurance et Isolation contrÃ´lÃ©s sur ordinateur et en vue tÃ©lÃ©phone.

Limites :

- **DÃ©mo** : les services de dÃ©mo, lancÃ©s sans rechargement par une autre session, ne renvoyaient pas encore la sÃ©rie quotidienne. Les tendances et lâ€™histogramme nâ€™y apparaÃ®tront quâ€™aprÃ¨s redÃ©marrage ; sans sÃ©rie, lâ€™histogramme affiche un message.
- **PÃ©riode prÃ©cÃ©dente** : les rendez-vous qui y sont Â« Ã  venir Â» ou Â« sans compte rendu Â» sont Ã©valuÃ©s Ã  la date du jour.
- **Contenu non repris de la maquette** : pas de colonne de messages.
## Connexion sans choix de profil et invitation en franÃ§ais clair

Lâ€™Ã©cran de connexion demande directement lâ€™identifiant et le mot de passe. Une personne qui nâ€™a quâ€™un espace entre directement dans cet espace : câ€™est le cas dâ€™un conseiller, qui arrive sur son agenda Assurance. Une personne qui a plusieurs espaces arrive sur Â« Mes espaces Â», qui ne prÃ©sente que les espaces autorisÃ©s. Lâ€™erreur Â« Votre compte nâ€™a pas accÃ¨s Ã  ce profil Â» disparaÃ®t donc. Lâ€™e-mail dâ€™invitation affiche lâ€™espace et le rÃ´le en franÃ§ais, par exemple Â« lâ€™espace Assurance en tant que Conseiller Â», et prÃ©cise que lâ€™espace sâ€™ouvrira directement.

Validation : test frontend de la connexion (identifiants seuls, mot de passe effacÃ© aprÃ¨s envoi) ; test backend du libellÃ© de lâ€™invitation ; suites portail (231) et frontend complÃ¨tes, typage, ESLint, Prettier et Ruff ; contrÃ´le visuel de lâ€™Ã©cran de connexion.

Limites : Ã  la reconnexion, une personne qui a plusieurs espaces choisit son espace dans Â« Mes espaces Â». Le dernier espace utilisÃ© nâ€™est rouvert automatiquement que lors de la reprise dâ€™une session existante.
## PrÃ©paration du dÃ©ploiement

Le dÃ©pÃ´t contient dÃ©sormais de quoi mettre le CRM en ligne sur un serveur Linux avec Docker :

- `deploy/env.production.template` : la configuration complÃ¨te, commentÃ©e en franÃ§ais.
- `scripts/generate_production_env.py` : crÃ©e le `.env` du serveur Ã  partir du domaine, avec des clÃ©s et mots de passe alÃ©atoires (clÃ©s Fernet valides). Il refuse de remplacer un fichier existant et nâ€™affiche jamais les valeurs.
- `scripts/deploy.sh` : vÃ©rifie la configuration, construit, migre les trois bases, lance `check --deploy` puis dÃ©marre ; il est rÃ©utilisÃ© tel quel pour les mises Ã  jour.
- `scripts/create_admin.sh` : crÃ©e le premier administrateur des deux espaces, avec un mot de passe saisi de faÃ§on masquÃ©e.
- Nouveau service `portal-call-journal` (profil `newt-journal`) : il rapproche les durÃ©es NEWT et ne dÃ©marre que si `NEWT_CDR_HISTORY_ENABLED=true`.
- `.dockerignore` exclut aussi `.claude`, toutes les bases SQLite et les variantes de `.env`.
- `.gitattributes` garde des fins de ligne Linux pour les scripts shell.
- `deploy/README.md` : guide pas Ã  pas en franÃ§ais (prÃ©requis, DNS, dÃ©ploiement, premier administrateur, mises Ã  jour, sauvegardes, dÃ©pannage).

Validation : gÃ©nÃ©ration testÃ©e (aucun marqueur restant, 12 secrets distincts, clÃ©s Fernet valides, refus dâ€™Ã©crasement et de domaine invalide) ; `docker compose config` valide avec la configuration gÃ©nÃ©rÃ©e, avec et sans le profil `newt-journal` ; syntaxe bash des scripts ; Ruff.

Limites : non exÃ©cutÃ© de bout en bout, faute de Docker dÃ©marrÃ© sur le poste de dÃ©veloppement ; la premiÃ¨re mise en ligne sur le serveur fera office de recette. Le serveur, le domaine et le compte SMTP restent Ã  fournir. Les sauvegardes automatiques restent Ã  planifier sur le serveur.
## SÃ©curitÃ© avant la mise en production

Un audit ciblÃ© a Ã©tÃ© menÃ© : contrÃ´les Django `check --deploy` des trois services en mode production, failles connues des dÃ©pendances avec pip-audit, recherche de motifs Ã  risque (routes publiques, SQL brut, HTML non Ã©chappÃ©, exÃ©cution de commandes, secrets en dur).

Corrections :

- **DÃ©pendances** : `cryptography` passe de 46.0.7 Ã  50.0.0 (sept avis de sÃ©curitÃ©) et `certifi` de 2026.7.22 Ã  2026.10.19. pip-audit ne signale plus aucune faille.
- **Limites de connexion derriÃ¨re Caddy** : le portail et lâ€™API Isolation ne retiennent plus que lâ€™adresse ajoutÃ©e par le proxy (`NUM_PROXIES=1` quand `TRUST_PROXY=true`). Un en-tÃªte `X-Forwarded-For` falsifiÃ© ne permet plus de contourner la limite de tentatives.
- **Caddy** : les routes internes entre services (`/api/portal/internal/`, `/api/assurance/internal/`) rÃ©pondent 404 depuis Internet ; elles restaient de toute faÃ§on protÃ©gÃ©es par des preuves signÃ©es. Ajout de lâ€™en-tÃªte HSTS et suppression de lâ€™en-tÃªte `Server`.

Points vÃ©rifiÃ©s sans correction nÃ©cessaire : cookies de session `Secure`, `HttpOnly` et `SameSite=Strict` ; protection CSRF du portail (Assurance nâ€™utilise pas de cookie) ; limite de tentatives sur la connexion et la rÃ©cupÃ©ration de mot de passe ; webhook Twilio vÃ©rifiÃ© par signature ; aucun SQL construit Ã  partir de donnÃ©es utilisateur ; aucun HTML non Ã©chappÃ© dans lâ€™interface ; aucun secret en dur.

Validation : suites portail (231), Assurance (334) et Isolation (253) complÃ¨tes avec les nouvelles versions ; `pip check` ; pip-audit sans faille ; contrÃ´le de lâ€™adresse retenue avec et sans en-tÃªte falsifiÃ© ; Ruff.

Limites : le Caddyfile nâ€™a pas pu Ãªtre validÃ© par Caddy lui-mÃªme (Docker indisponible sur le poste). Audit ciblÃ©, qui ne remplace pas un test dâ€™intrusion. Les points relevÃ©s par `check --deploy` restants sont couverts par Caddy (redirection HTTPS, X-Frame-Options, HSTS).
## Tests dâ€™intrusion (environnement local)

Une sÃ©rie de tests dâ€™intrusion a Ã©tÃ© menÃ©e sur lâ€™environnement local (127.0.0.1), avec des comptes et des donnÃ©es fictives, pour vÃ©rifier les contrÃ´les dâ€™accÃ¨s avant la mise en production. Aucune faille nâ€™a Ã©tÃ© trouvÃ©e ; aucun correctif nâ€™a Ã©tÃ© nÃ©cessaire.

ScÃ©narios vÃ©rifiÃ©s, tous bloquÃ©s comme attendu :

- **AccÃ¨s sans authentification** : les API mÃ©tier et dâ€™administration rÃ©pondent 403.
- **Ã‰lÃ©vation de privilÃ¨ges** : un setter ne peut pas crÃ©er dâ€™accÃ¨s ni se faire passer pour administrateur ; un conseiller nâ€™atteint pas les Ã©crans dâ€™administration.
- **AccÃ¨s horizontal** : un setter ne voit et nâ€™ouvre que ses prospects (fiche dâ€™un autre : 404) ; un conseiller ne voit que ses contacts attribuÃ©s. Lâ€™isolement est appliquÃ© cÃ´tÃ© serveur, pas seulement masquÃ© Ã  lâ€™Ã©cran.
- **Jetons dâ€™espace** : un jeton Isolation rÃ©utilisÃ© sur Assurance, tronquÃ© ou falsifiÃ© est refusÃ© (401). Le rÃ´le est fixÃ© par le serveur, non modifiable par le client.
- **CSRF** : toute Ã©criture sans jeton CSRF (connexion, crÃ©ation dâ€™accÃ¨s) est refusÃ©e (403).
- **Force brute** : la connexion est limitÃ©e (429 au-delÃ  du quota).
- **Ã‰numÃ©ration de comptes** : un compte inexistant et un bon compte avec mauvais mot de passe renvoient le mÃªme message Â« Identifiants incorrects Â».
- **Injection** : les tentatives SQL dans la recherche ne renvoient aucun rÃ©sultat ; un paramÃ¨tre dâ€™Ã©tat invalide est rejetÃ© (400).
- **Routes internes entre services** : elles exigent une preuve signÃ©e (403 sans elle) et sont en plus masquÃ©es par Caddy en production (voir lot sÃ©curitÃ©).
- **En-tÃªtes** : `X-Content-Type-Options: nosniff` prÃ©sent sur les rÃ©ponses.

Limites : tests ciblÃ©s sur les contrÃ´les dâ€™accÃ¨s et les abus courants, menÃ©s en local. Ils ne remplacent pas un test dâ€™intrusion professionnel sur lâ€™environnement de production rÃ©el, recommandÃ© une fois le CRM en ligne avec de vraies donnÃ©es.
## Dossiers clients â€” administration Assurance et Isolation

Nouvelle entrÃ©e Â« Dossiers clients Â» rÃ©servÃ©e aux administrateurs de chaque espace. Les comptes conseillers Assurance et le client Isolation existant sont prÃ©sentÃ©s sous forme de dossiers recherchables, paginÃ©s par 12, sans crÃ©er de nouveaux clients. Les comptes inactifs encore prÃ©sents dans lâ€™annuaire restent consultables. Chaque dossier ouvre une vue regroupant les prospects confiÃ©s (fiches distinctes, historique dâ€™attribution inclus), les rendez-vous de ce client, les rÃ©sultats dâ€™appel dÃ©clarÃ©s et les tÃ¢ches/rappels des fiches, avec recherche et pagination par 25. Les fiches traitÃ©es restent consultables.

Compteurs sur le dossier entier, indÃ©pendants des filtres de la liste : prospects et statuts commerciaux configurÃ©s, rendez-vous attribuÃ©s dont annulations, Ã©tats mÃ©tier mutuellement exclusifs, ventes explicitement conclues lors dâ€™un rendez-vous tenu, tÃ¢ches ouvertes et en retard. Les comptes rendus manquants ne deviennent pas des absences. Lâ€™objectif Assurance reste diminuÃ© uniquement par les rendez-vous tenus non annulÃ©s, toutes pÃ©riodes confondues ; une correction de rÃ©sultat se reflÃ¨te au prochain chargement. Les Ã©tats commerciaux restent distincts des preuves de prÃ©sence/vente. Une panne de statistiques affiche une indisponibilitÃ©, pas des zÃ©ros inventÃ©s.

Le suivi affiche le setter, lâ€™auteur rÃ©el de la rÃ©servation et du compte rendu, ou un identifiant stable si le nom historique nâ€™est plus rÃ©soluble. Les rÃ©sultats dâ€™appel et tÃ¢ches indiquent leur auteur/responsable et les notes. Depuis une ligne, lâ€™administrateur ouvre la fiche latÃ©rale existante (qualification, notes, piÃ¨ces, rendez-vous et journaux selon les commandes du module) ; en Isolation, lâ€™accÃ¨s aux visites/C2 est conservÃ©. Une action Â« Appels CRM Â» consulte les commandes tÃ©lÃ©phoniques de cette fiche, tous agents de lâ€™espace, avec compte, poste, Ã©tat et durÃ©e rapprochÃ©e disponible. Elle ne lance aucun appel et ne consulte pas NEWT.

PÃ©rimÃ¨tre explicite : les appels et tÃ¢ches reprennent lâ€™historique complet des fiches, y compris avant une rÃ©affectation ; ils ne prouvent donc pas une commande de ce client Ã  cette date. Les rendez-vous sont limitÃ©s Ã  ce client. Un prospect partagÃ© historiquement peut figurer dans plusieurs dossiers : ne pas additionner ces totaux comme une population unique de lâ€™espace. Le total Â« rÃ©sultats dâ€™appel Â» compte les dÃ©clarations, pas les conversations rÃ©ellement connectÃ©es. Â« Poste joint Â» signifie que la composition a pu commencer. Les appels passÃ©s hors CRM ne sont pas inclus. Lâ€™historique technique reste consultable par fiche, pas de total tÃ©lÃ©phonique global par client ni de nouvel export client livrÃ© dans ce lot. Lâ€™unicitÃ© du client Isolation existante reste inchangÃ©e ; aucun mÃ©canisme multi-client nâ€™a Ã©tÃ© ajoutÃ©.

Validation locale : 27 tests backend ciblÃ©s (2 contrÃ´les de concurrence PostgreSQL ignorÃ©s sur SQLite), dont 7 nouveaux tests de dossiers/permissions/pagination/historique ; 113 tests frontend, dont 3 nouveaux tests de navigation, dÃ©compte, panne et espace Isolation ; typage, lint, format et build. Recette API en lecture seule sur la base PostgreSQL synthÃ©tique de 10 000 prospects : 5 dossiers Assurance, 1 dossier Isolation ; dossier Assurance de 250 prospects et dossier Isolation de 1 250 prospects, appels dÃ©clarÃ©s et suivis paginÃ©s, cohÃ©rence des totaux vÃ©rifiÃ©e. Aucun appel, fournisseur, message, rÃ©servation ou donnÃ©e de recette dÃ©clenchÃ©/modifiÃ©. Aucun changement de schÃ©ma. Recette graphique navigateur non rÃ©alisÃ©e : contrÃ´le local dÃ©sactivÃ© dans Work.

Export du dossier et des indicateurs livrÃ© dans le lot dÃ©crit ci-dessus ; revue visuelle utilisateur des pages administrateur Ã  poursuivre. Les autres Ã©carts mÃ©tier/production recensÃ©s plus bas restent ouverts.


## Prospection active et traÃ§abilitÃ© du travail

Dans les tableaux Assurance et Isolation, les fiches avec un rendez-vous planifiÃ© ou un refus sortent de la prospection active par dÃ©faut. Assurance utilise le dernier rÃ©sultat dâ€™appel dÃ©clarÃ© (RDV pris / Pas intÃ©ressÃ©) et les rendez-vous planifiÃ©s ; Isolation utilise le statut Non intÃ©ressÃ© et les visites planifiÃ©es. Lâ€™option Â« Afficher aussi les fiches traitÃ©es Â» les retrouve dans le mÃªme pÃ©rimÃ¨tre dâ€™accÃ¨s, avec un badge explicite. Les filtres, la pagination et les exports utilisent la mÃªme sÃ©lection cÃ´tÃ© serveur. Aucune fiche, note, attribution, rÃ©sultat ou rendez-vous nâ€™est supprimÃ©, et le statut commercial personnalisÃ© nâ€™est pas Ã©crasÃ©. Les API historiques sans paramÃ¨tre queue conservent leur comportement. Le filtre de prospection Assurance est interne aux setters et administrateurs : il ne rÃ©vÃ¨le pas les rÃ©sultats dâ€™appels internes aux conseillers. Un nouveau rÃ©sultat explicite peut rÃ©ouvrir un refus ; une rÃ©servation annulÃ©e ne suffit plus Ã  bloquer la file, sauf si un rÃ©sultat RDV pris reste le dernier rÃ©sultat dÃ©clarÃ© en Assurance.

Lâ€™historique Assurance indique lâ€™identifiant exact de lâ€™auteur de chaque interaction pour lâ€™administrateur uniquement ; un onglet Historique est accessible dans la fiche latÃ©rale, avec accÃ¨s au journal des modifications (auteur, date et dÃ©tails avant/aprÃ¨s disponibles). Les noms des comptes sont rÃ©solus par le portail dans lâ€™espace autorisÃ©, y compris pour les accÃ¨s suspendus encore conservÃ©s. La mÃªme rÃ©solution rend les auteurs Isolation lisibles. Si un compte ne peut plus Ãªtre rÃ©solu, son identifiant reste affichÃ©. Les dates, dÃ©tails, rÃ©sultats et journaux existants sont conservÃ©s. La recherche de noms est bornÃ©e et interdite aux non-administrateurs.

Validation : 338 tests Assurance (26 ignorÃ©s sur SQLite), 36 tests Isolation ciblÃ©s (6 ignorÃ©s), 238 tests portail (11 ignorÃ©s), 110 tests frontend. Tests de retrait de la file active, rÃ©apparition explicite, accÃ¨s direct conservÃ©, export filtrÃ©, pÃ©rimÃ¨tres conseiller/setter/admin et historique sans fuite dâ€™identitÃ© aux autres rÃ´les ; recherche des auteurs avec contrÃ´le dâ€™espace et comportement en Ã©chec ; typage, lint, formatage et build. Aucun appel ou fournisseur interrogÃ©, aucune rÃ©servation rÃ©elle. Recette visuelle non effectuÃ©e (navigateur local dÃ©sactivÃ©). GitHub Actions reste indisponible Ã  cause du paiement/plafond du compte ; validation locale, avec les contrÃ´les PostgreSQL ignorÃ©s sur SQLite explicitement signalÃ©s.


## Appels sortants pour les administrateurs

Les administrateurs actifs peuvent prÃ©parer et confirmer leur propre appel dans Assurance et Isolation : icÃ´ne de tÃ©lÃ©phone de lâ€™en-tÃªte, boutons sur les prospects, action de la fiche et onglet Composer dans Appels. Leur historique dâ€™Ã©quipe reste accessible. Ils doivent disposer de leur propre poste NEWT, configurable dans lâ€™association des postes (qui accepte dÃ©sormais setters et administrateurs). Aucun poste dâ€™un setter nâ€™est utilisÃ© implicitement. Les rÃ¨gles de modification dâ€™un poste partagÃ© entre espaces exigent les droits administrateur dans chaque espace concernÃ©. Le diagnostic de poste accepte aussi les postes des administrateurs.

Le serveur transmet le rÃ´le effectif au service mÃ©tier pour la vÃ©rification finale, sans dÃ©guiser lâ€™administrateur en setter. Assurance conserve un verrou de fiche personnel et la rÃ©vision ; Isolation permet lâ€™appel dâ€™un prospect du pÃ©rimÃ¨tre administratif sans rÃ©attribution, tout en conservant autorisation, exclusions, numÃ©ro utilisable et rÃ©vision. Les autres rÃ´les restent refusÃ©s. Confirmation explicite, activation serveur, preuve liÃ©e Ã  lâ€™acteur, dÃ©duplication, dÃ©lai entre commandes, audit et vÃ©rification du rÃ©sultat restent inchangÃ©s. Les identifiants NEWT ne sont ni ajoutÃ©s ni exposÃ©s.

Validation : 236 tests portail (11 ignorÃ©s sur SQLite), 6 tests de preuve Assurance, 7 de preuve Isolation, 108 tests frontend sur le lot isolÃ© ; rÃ´le rÃ©el de la vÃ©rification, poste propre ou absent, accÃ¨s rÃ©voquÃ©, droits multi-espaces, non-vol du verrou, conservation du setter assignÃ© et exclusion tardive. Typage, ESLint, Ruff, Prettier, build. Aucun appel rÃ©el ni lecture rÃ©elle du fournisseur. Pas de recette navigateur (accÃ¨s local dÃ©sactivÃ©). GitHub Actions ne dÃ©marre pas ses jobs (paiement/plafond du compte) ; les validations locales sont conservÃ©es dans la PR. Les appels effectifs nÃ©cessitent toujours les secrets et lâ€™activation NEWT ; la dÃ©mo reste sans appel rÃ©el.


## Mes conseillers â€” contraste et rythme visuel

Correction des surcharges du thÃ¨me global qui aplatissaient les cartes (coins de 7 px, marges imposÃ©es, suppression des ombres) et rÃ©introduisaient des bordures dans la recherche. La page setter possÃ¨de dÃ©sormais ses rÃ¨gles contextualisÃ©es : bandeau compact bleu/lavande, cartes arrondies avec accents bleu/menthe/abricot, textes plus contrastÃ©s et boutons visibles. Lâ€™Ã©tat sans quota prÃ©cise toujours lâ€™absence dâ€™objectif. Les cartes remontent dans la page sans dÃ©placer les boutons sous une grande zone vide. Animation discrÃ¨te au survol, dÃ©sactivÃ©e avec la prÃ©fÃ©rence de mouvement rÃ©duit. DonnÃ©es, permissions et parcours conservÃ©s.

Validation : tests existants associations/navigation/filtre, typage, lint, formatage et build. Recette visuelle navigateur non effectuÃ©e (accÃ¨s local dÃ©sactivÃ© dans Work) ; correction guidÃ©e par la capture utilisateur et la cascade CSS identifiÃ©e. Aucun appel ni rÃ©servation dÃ©clenchÃ©.


## Mes conseillers â€” disposition annuaire selon rÃ©fÃ©rence

La prÃ©sentation setter reprend la rÃ©fÃ©rence fournie : fond gris bleutÃ©, bandeau de recherche intÃ©grÃ©, filtres nom/association, compteur des rÃ©sultats, grille de trois cartes sur grand Ã©cran (deux puis une sur petit Ã©cran), identitÃ© par initiales et boutons bleus arrondis. Les quotas, Ã©tats et rendez-vous tenus proviennent des donnÃ©es existantes. Aucun portrait, tarif, avis ou indicateur de disponibilitÃ© horaire fictif. Le bouton Â« PrÃ©parer un rendez-vous Â» ouvre les prospects : la rÃ©servation reste effectuÃ©e depuis une fiche et le conseiller doit y Ãªtre sÃ©lectionnÃ©. Les associations suspendues ne proposent pas cette action. Administration conservÃ©e.

Validation : tests associations et navigation/filtre setter, typage, ESLint, Prettier, build, contrÃ´les GitHub. Aucun appel ni rendez-vous dÃ©clenchÃ©. ContrÃ´le visuel navigateur non effectuÃ© : accÃ¨s au navigateur local dÃ©sactivÃ© dans Work.


## Mes conseillers â€” prÃ©sentation setter

La liste setter Assurance utilise des cartes sans photo, avec nom, association active/suspendue et objectif du conseiller : quota restant, rendez-vous tenus et progression. Les objectifs non dÃ©finis, en chargement ou indisponibles sont distinguÃ©s. Le total compte les associations accessibles ; recherche et pagination restent cÃ´tÃ© serveur. Les absences ne consomment pas le quota ; la progression est celle du conseiller, non une statistique personnelle du setter. PrÃ©sentation lavande/menthe cohÃ©rente avec lâ€™accueil et Appels, grille adaptative et Ã©tat vide. Le tableau administratif, ses commandes et panneaux restent disponibles.

Validation : tests de permissions et de crÃ©ation/filtrage des associations, typage, lint et build frontend. Aucun appel, message ou rÃ©servation dÃ©clenchÃ©. Recette visuelle navigateur non rÃ©alisÃ©e : accÃ¨s local dÃ©sactivÃ© dans Work.


## PrÃ©sentation de la page Appels

Page commune Assurance/Isolation : en-tÃªte propre, tons lavande et menthe cohÃ©rents avec lâ€™accueil, composition en deux panneaux (pavÃ© numÃ©rique et rÃ©sultats), Ã©tat vide explicatif et historique en carte. Le parcours reste une recherche de fiche puis ouverture du prospect ; aucun appel automatique ajoutÃ©. Adaptation en une colonne sur petit Ã©cran, focus clavier et rÃ©duction des animations. Aucun indicateur fictif.

Validation : tests existants de recherche, ouverture de fiche, historique et droits ; typage, lint et build frontend. ContrÃ´le visuel navigateur non effectuÃ© : accÃ¨s navigateur local dÃ©sactivÃ© dans Work. Le journal des durÃ©es NEWT, livrÃ© sÃ©parÃ©ment, est conservÃ©.

## Appels â€” durÃ©e rÃ©elle via le journal NEWT 511

Lâ€™historique des appels affiche une colonne Â« DurÃ©e Â», renseignÃ©e Ã  partir du journal NEWT (fonction 511). Ce journal est en heure de MontrÃ©al ; ses colonnes From, To, Description, DNID, Date, Time, Duration et Amount ont Ã©tÃ© confirmÃ©es par NEWT.

Chaque commande dâ€™appel conserve dÃ©sormais une empreinte chiffrÃ©e du numÃ©ro composÃ© (HMAC avec la clÃ© du portail), jamais le numÃ©ro en clair. Le rapprochement retient une ligne du journal si elle remplit trois conditions :

- elle vient du poste utilisÃ© pour lâ€™appel ;
- elle vise le mÃªme numÃ©ro (indicatif 1 ajoutÃ© si absent, puis comparaison des empreintes) ;
- elle commence entre 60 s avant et 3 min aprÃ¨s la commande.

Les cas incertains ne sont jamais tranchÃ©s :

- **Plusieurs lignes, ou une ligne commune Ã  deux commandes** : statut Â« Ã€ vÃ©rifier Â».
- **Aucune ligne au-delÃ  de 15 minutes** : statut Â« Absent du journal Â».
- **Aucune ligne avant ce dÃ©lai** : statut Â« En attente du journal Â».

Une durÃ©e rapprochÃ©e est dÃ©finitive. Seules les commandes Â« Poste joint Â» ou Â« IndÃ©terminÃ© Â» sont concernÃ©es.

Le rapprochement porte sur les sept derniers jours. Il se lance de deux faÃ§ons :

- **Depuis lâ€™historique dâ€™Ã©quipe**, par le bouton Â« Rapprocher le journal NEWT Â» rÃ©servÃ© Ã  lâ€™administrateur (`POST /api/portal/<espace>/call-history/reconcile/`). Il affiche le nombre de durÃ©es rÃ©cupÃ©rÃ©es, Ã  vÃ©rifier et absentes.
- **Par la commande `python manage.py reconcile_call_journal`**, qui accepte `--loop --interval 900` pour une exÃ©cution planifiÃ©e.

Garanties :

- **DonnÃ©es conservÃ©es** : seules la durÃ©e et lâ€™heure de dÃ©but sont enregistrÃ©es, sur nos propres appels. Les lignes globales du fournisseur ne sont jamais stockÃ©es ; le journal dâ€™audit ne contient ni numÃ©ro ni ligne brute.
- **Configuration** : le rapprochement exige `NEWT_CDR_HISTORY_ENABLED` et les accÃ¨s NEWT. Si le journal est indisponible, rien nâ€™est modifiÃ©.
- **Migration** : `identity.0018`, additive.

Validation :

- Backend : tests des rÃ¨gles de rapprochement sur les lignes dâ€™exemple fournies par NEWT (correspondance, ambiguÃ¯tÃ©, ligne partagÃ©e, autre poste, attente puis absence) ; droits du bouton, fenÃªtre de sept jours, dÃ©finitivitÃ© et journal sans numÃ©ro ; journal indisponible ou non configurÃ© ; empreinte et anciens appels.
- Frontend : formats de durÃ©e et statuts, bouton et compte rendu rÃ©servÃ©s Ã  lâ€™administrateur.
- Suites portail et frontend (107) complÃ¨tes, typage, ESLint, Prettier et Ruff.
- Non vÃ©rifiÃ© contre le vrai journal NEWT, les appels rÃ©els nâ€™Ã©tant pas activÃ©s.

Limites :

- **UnitÃ© de Duration** : elle est interprÃ©tÃ©e en secondes, ce que NEWT doit encore confirmer, de mÃªme que le traitement dâ€™un appel sans rÃ©ponse (durÃ©e 0 ou absence de ligne).
- **Pas de rÃ©ponse prouvÃ©e** : la durÃ©e ne prouve pas Ã  elle seule une conversation avec le prospect.
- **Anciens appels** : ceux passÃ©s avant ce lot nâ€™ont pas dâ€™empreinte et ne peuvent pas Ãªtre rapprochÃ©s.
- **ExÃ©cution planifiÃ©e** : la commande nâ€™est pas encore planifiÃ©e en production.

## Agenda et disponibilitÃ©s personnelles du conseiller Assurance

Le menu conseiller donne un accÃ¨s direct Ã  Â« Mon agenda et disponibilitÃ©s Â», avec deux onglets : horaires CRM et connexion Google/Microsoft. Le conseiller dÃ©finit ses plages hebdomadaires (plusieurs par jour), son fuseau et leur activation dans un panneau Ã  droite. Sans plage un jour est fermÃ© ; avec les horaires activÃ©s et aucune plage, aucune nouvelle rÃ©servation nâ€™est acceptÃ©e. Les profils existants restent sans restriction horaire personnalisÃ©e jusquâ€™Ã  activation explicite. Les rendez-vous dÃ©jÃ  pris restent conservÃ©s.

La configuration personnelle est sauvegardÃ©e avec rÃ©vision, contrÃ´le du rÃ´le et audit ; elle est verrouillÃ©e sur la mÃªme ligne que les rÃ©servations pour Ã©viter une Ã©criture concurrente incohÃ©rente. La crÃ©ation et la reprogrammation contrÃ´lent les horaires cÃ´tÃ© serveur, mÃªme pour une saisie manuelle. Le sÃ©lecteur de crÃ©neaux exclut les horaires fermÃ©s en plus des occupations CRM ; lorsquâ€™un horaire est configurÃ©, la grille couvre la journÃ©e complÃ¨te pour proposer aussi un horaire avant 8 h ou aprÃ¨s 20 h. Lâ€™agenda externe reste contrÃ´lÃ© lors de la confirmation. Les bornes inexistantes au changement dâ€™heure ne crÃ©ent pas de fausse plage libre.

La connexion personnelle Google/Microsoft existante est rÃ©utilisÃ©e, sans exposer les secrets OAuth. La consultation des pÃ©riodes occupÃ©es propose dÃ©sormais des dates/heures usuelles avec un fuseau explicite sur cet Ã©cran. Les commandes de synchronisation existantes restent disponibles. Une configuration OAuth manquante est indiquÃ©e ; aucune connexion rÃ©elle ne peut Ãªtre affirmÃ©e sur ce seul Ã©cran.

Validation : six tests backend ciblÃ©s (droits, rÃ©vision, plages invalides et chevauchements, rÃ©servation et reprogrammation refusÃ©es avant appel fournisseur, plages fermÃ©es dans les crÃ©neaux, fuseaux, changement dâ€™heure, rollback de lâ€™audit) ; suite Assurance 334 tests dont 26 ignorÃ©s sur SQLite, suites frontend, typage, ESLint, Prettier, Ruff et build. Tests du formulaire et du conflit conservant le brouillon, dates de consultation converties avec le dÃ©calage MontrÃ©al, configuration OAuth absente, liaison et extension de la grille horaire. Recette sur la dÃ©mo PostgreSQL : portefeuille personnel chargÃ© (250 prospects, 54 rendez-vous tenus), horaires fictifs du lundi au vendredi de 9 h Ã  17 h enregistrÃ©s et relus pour `conseiller.demo01`, week-end fermÃ©, boutons OAuth accessibles mais dÃ©sactivÃ©s faute de configuration serveur. Sauvegardes privÃ©es avant migrations des bases de dÃ©mo et SQLite locales ; migration additive Assurance 0029, mises Ã  niveau portail 0016/0017 nÃ©cessaires Ã  la recette.

Limites : plages rÃ©currentes le mÃªme jour, sans plage traversant minuit ni exceptions par date dans le CRM. Les absences ponctuelles peuvent Ãªtre bloquÃ©es dans lâ€™agenda externe connectÃ© ; ses occupations ne sont pas prÃ©chargÃ©es dans la grille CRM et sont vÃ©rifiÃ©es Ã  la confirmation. Lâ€™agenda externe principal est celui prÃ©vu par les intÃ©grations existantes. Les clÃ©s OAuth et le consentement du conseiller restent nÃ©cessaires Ã  une connexion rÃ©elle ; aucun appel, envoi de message ou consentement externe effectuÃ© pendant cette recette.

Suite : statistiques et exports des ventes dÃ©clarÃ©es, distinctes des contrats enregistrÃ©s.

## Mes prospects du conseiller et dÃ©compte sur les prÃ©sences uniquement

Le conseiller dispose dÃ©sormais dâ€™un onglet Â« Mes prospects Â» : liste personnelle paginÃ©e (25 lignes), recherche nom/tÃ©lÃ©phone/courriel, total des clients distincts attribuÃ©s, nombre de rendez-vous tenus, absences et reste sur lâ€™objectif fixÃ© par lâ€™administration. Un dossier liÃ© Ã  un rendez-vous sâ€™ouvre dans le panneau existant pour consulter/modifier la fiche et son rÃ©sultat. Un prospect directement attribuÃ© sans rendez-vous est listÃ©, sans inventer de rendez-vous ni de qualification. Une fiche explicitement rÃ©attribuÃ©e Ã  un autre conseiller sort de ce portefeuille ; les dossiers historiques sans attribution explicite restent liÃ©s Ã  leurs rendez-vous.

Correction de la rÃ¨gle prÃ©cÃ©dente : lâ€™objectif nâ€™est plus consommÃ© Ã  la rÃ©servation. Seuls les rendez-vous non annulÃ©s avec prÃ©sence explicitement confirmÃ©e (`report.performed=True`) consomment une unitÃ©. Absence, rendez-vous non tenu, planifiÃ©, en attente de rÃ©sultat ou annulÃ© : zÃ©ro unitÃ©. Une correction du rÃ©sultat recalcule le compteur ; enregistrer deux fois le mÃªme rÃ©sultat ne le double pas. Le reste est bornÃ© Ã  zÃ©ro, lâ€™objectif nâ€™interdit pas de dÃ©passer. Cette rÃ¨gle est commune Ã  lâ€™agenda, au choix du conseiller lors de la rÃ©servation et Ã  la liste des affectations. Lâ€™usage dâ€™un conseiller est limitÃ© Ã  lui-mÃªme dans son API ; setters/administrateurs conservent leur vue de prÃ©paration des rÃ©servations.

VÃ©rifications : tests backend de prÃ©sence/absence/annulation, correction aller-retour et rÃ©pÃ©tition, droits, unicitÃ© des prospects, recherche, pagination et rÃ©attribution ; tests frontend du calcul (rÃ©servations diffÃ©rentes des prÃ©sences), des compteurs et de la pagination, et suites existantes de rÃ©servation/affectation/calendrier ; typage, ESLint, Prettier, Ruff et build.

Limites : pas de pÃ©riode ni de remise Ã  zÃ©ro par lot : tous les rendez-vous historiques tenus comptent. Plusieurs rendez-vous tenus pour le mÃªme client consomment plusieurs unitÃ©s, tandis que la liste affiche des clients distincts. Le quota reste une information, sans blocage automatique des rÃ©servations. La connexion dâ€™agenda et le paramÃ©trage des disponibilitÃ©s constituent le lot suivant.

## Historique â€” quota initial et ancien dÃ©compte Ã  la rÃ©servation

Lorsquâ€™il invite un conseiller Assurance ou lui crÃ©e un compte, lâ€™administrateur doit saisir le Â« Nombre de prospects Ã  fournir Â» au client de ce conseiller : le champ est obligatoire dans les deux formulaires dÃ¨s que le rÃ´le Conseiller est choisi. Une invitation conserve ce quota jusquâ€™Ã  son acceptation, puis le transmet Ã  lâ€™accÃ¨s crÃ©Ã©. Lâ€™Ã©cran Utilisateurs et accÃ¨s permet de le modifier ou de lâ€™effacer. Un conseiller qui change de rÃ´le perd son quota. Toutes ces opÃ©rations sont journalisÃ©es, avec les valeurs avant et aprÃ¨s.

DÃ©compte : chaque rendez-vous rÃ©servÃ© pour le conseiller consomme une unitÃ©, et une annulation la rend. Le quota est visible par tous les membres Assurance :

- **Le conseiller** voit, en tÃªte de son agenda, le nombre de prospects qui lui restent Ã  recevoir et le nombre de rendez-vous rÃ©servÃ©s sur le quota. Une fois le quota atteint, la carte passe en orange.
- **Le setter et lâ€™administrateur** voient le reste de chaque conseiller lors du choix du conseiller Ã  la rÃ©servation, avec un avertissement quand le quota est atteint, ainsi que dans Â« Mes conseillers Â» / Â« Affectations Â» (Â« N restant(s) sur Q Â» ou Â« Non dÃ©fini Â»).

API :

- `GET /api/portal/assurance/advisor-quotas/` : rÃ©servÃ© aux membres Assurance actifs, liste les conseillers actifs et leur quota.
- `GET /api/assurance/advisor-usage/` : nombre de rendez-vous non annulÃ©s par conseiller.
- `prospect_quota` (1 Ã  100 000) est acceptÃ© par les invitations, la crÃ©ation dâ€™accÃ¨s et la modification dâ€™accÃ¨s ; il est refusÃ© pour tout autre rÃ´le que conseiller Assurance.

Les donnÃ©es sont enregistrÃ©es par la migration additive `identity.0017`.

Validation :

- Backend : quatre tests portail (transmission de lâ€™invitation Ã  lâ€™accÃ¨s et journal, rÃ©servation aux conseillers et bornes, modification et effacement au changement de rÃ´le, lecture par les membres et refus hors espace) et un test Assurance (rÃ©servations consommÃ©es, annulation rendue, authentification).
- Frontend : calcul du dÃ©compte, carte du conseiller (reste, quota atteint, absence de quota) et colonne Â« Prospects Ã  fournir Â» vue par un setter.
- Suites complÃ¨tes : portail 227, Assurance 326, frontend 100 ; typage, ESLint, Prettier, Ruff et build.

DÃ©mo non vÃ©rifiÃ©e : la migration 0017 nâ€™y est pas appliquÃ©e, et les services de dÃ©mo, lancÃ©s par une autre session, nâ€™ont pas Ã©tÃ© redÃ©marrÃ©s.

Limites :

- Le quota nâ€™empÃªche pas de rÃ©server au-delÃ  : il informe et avertit.
- Tous les rendez-vous non annulÃ©s du conseiller sont comptÃ©s, y compris ceux antÃ©rieurs au quota et les absences, et sans notion de pÃ©riode.
- Le quota est obligatoire dans lâ€™interface, mais facultatif dans lâ€™API ; les conseillers existants affichent Â« Non dÃ©fini Â» tant quâ€™un administrateur ne lâ€™a pas saisi.

## Export des prospects â€” CSV et Excel

Lâ€™Ã©cran Prospects propose dÃ©sormais Â« Exporter : CSV / Excel Â» au setter et Ã  lâ€™administrateur, en Assurance comme en Isolation. Le conseiller Assurance dispose du mÃªme bouton, Â« Mes prospects Â», dans son agenda.

Lâ€™export reprend exactement la visibilitÃ© de la liste. En Assurance, setter et administrateur voient tous les contacts, et le conseiller seulement ceux qui lui sont attribuÃ©s ou liÃ©s Ã  lâ€™un de ses rendez-vous. En Isolation, le setter voit ses prospects affectÃ©s et lâ€™administrateur toute lâ€™Ã©quipe. Lâ€™export applique aussi les filtres en cours : recherche en Assurance ; recherche, responsable, statut et rappels Ã  traiter en Isolation. Il porte sur toutes les pages, pas seulement sur celle affichÃ©e.

- **Colonnes Assurance** : rÃ©fÃ©rence de la fiche, nom, tÃ©lÃ©phone, e-mail, Ã©tape, date de mise Ã  jour, puis les champs mÃ©tier actifs. Pour le conseiller, seuls les champs que lâ€™administration lui a rendus visibles figurent dans lâ€™export.
- **Colonnes Isolation** : rÃ©fÃ©rence de la fiche, rÃ©fÃ©rence, nom, tÃ©lÃ©phone saisi, numÃ©ro normalisÃ©, campagne, setter, statut commercial et rappel prÃ©vu.
- **Format CSV** : UTF-8 avec BOM et sÃ©parateur point-virgule, pour une ouverture directe dans Excel en franÃ§ais.
- **Protection contre les formules** : en CSV, les valeurs qui pourraient Ãªtre lues comme des formules sont neutralisÃ©es, sans altÃ©rer les numÃ©ros de tÃ©lÃ©phone. En Excel, elles sont enregistrÃ©es comme du texte.

Chaque export est journalisÃ© (auteur, format, nombre de lignes, filtres). Endpoints : `GET /api/assurance/contacts/export/?file=csv|xlsx` et `GET /api/work-queue/export/?file=csv|xlsx`, rÃ©ponses `no-store`.

Validation : cinq tests Assurance (filtres et ordre, protection CSV et Excel, pÃ©rimÃ¨tre et champs du conseiller, refus, plafonds sans troncature) et trois tests Isolation (pÃ©rimÃ¨tre setter, filtres administrateur et Excel, refus). Deux tests frontend du composant dâ€™export (filtres transmis, tÃ©lÃ©chargement, message dâ€™erreur). Suites Assurance (325), Isolation (253) et frontend complÃ¨tes, typage, ESLint, Prettier et Ruff. Mesure locale : 50 000 lignes en CSV en 0,5 s, contre environ 7 s pour Excel en openpyxl.

Limites : au plus 50 000 lignes en CSV et 20 000 en Excel ; au-delÃ , lâ€™export est refusÃ© avec une invitation Ã  filtrer ou Ã  passer en CSV, sans jamais tronquer. Les donnÃ©es de qualification, les notes et lâ€™historique ne sont pas exportÃ©s. DÃ©mo non vÃ©rifiÃ©e en conditions rÃ©elles : les services de dÃ©mo, lancÃ©s par une autre session sans rechargement, nâ€™ont pas Ã©tÃ© redÃ©marrÃ©s.

## Appels â€” composeur, historique personnel et historique dâ€™Ã©quipe

Le module Â« Appels Â» est dÃ©bloquÃ© dans les deux espaces. Lâ€™icÃ´ne tÃ©lÃ©phone de lâ€™en-tÃªte du setter, jusquâ€™ici dÃ©sactivÃ©e, ouvre le composeur. Le setter tape un numÃ©ro (pavÃ© numÃ©rique) ou un nom : la recherche porte sur ses prospects (`contacts/` en Assurance, `work-queue/` en Isolation). Â« Appeler Â» ouvre la fiche du prospect en mode appel, avec les contrÃ´les, la qualification et lâ€™historique habituels. Aucun appel ne part dâ€™un numÃ©ro libre. Un numÃ©ro inconnu renvoie vers lâ€™import des prospects, car il nâ€™existe pas de crÃ©ation unitaire de fiche. Un bandeau signale que les appels rÃ©els ne sont pas encore activÃ©s, ou quâ€™aucun poste nâ€™est associÃ© au compte.

Lâ€™onglet Â« Mon historique Â» liste les appels du setter : prospect, date et rÃ©sultat en franÃ§ais. Â« Poste joint Â» signifie seulement que le poste a dÃ©crochÃ©. Un filtre porte sur le rÃ©sultat, et chaque ligne mÃ¨ne Ã  la fiche. Lâ€™administrateur voit lâ€™historique de toute lâ€™Ã©quipe, avec lâ€™appelant et le poste, et peut filtrer par rÃ©sultat et par setter. Le nouvel endpoint `GET /api/portal/<espace>/call-history/` est rÃ©servÃ© aux setters et administrateurs actifs de lâ€™espace. Il est paginÃ© par 25 et non mis en cache ; le filtre par appelant est refusÃ© au setter. Le nom du prospect est dÃ©sormais signÃ© dans la preuve dâ€™appel Ã©mise par le service mÃ©tier (120 caractÃ¨res au plus) et enregistrÃ© sur la tentative (migration additive `identity.0016`).

Validation : tests backend de la signature du libellÃ©, du pÃ©rimÃ¨tre setter/administrateur, des filtres et des refus ; tests dâ€™appel Assurance et Isolation existants ; quatre tests frontend du centre dâ€™appels (composeur vers la fiche en mode appel, numÃ©ro inconnu et recherche Isolation, historique setter sans appelant, historique dâ€™Ã©quipe filtrÃ© par setter) et un test du shell (icÃ´ne active, entrÃ©e Â« Appels Â»). Suites portail et frontend complÃ¨tes, typage, ESLint, Prettier, Ruff et build. DÃ©mo non vÃ©rifiÃ©e : la base PostgreSQL de dÃ©mo ne rÃ©pondait pas pendant le lot.

Limites : la tÃ©lÃ©phonie rÃ©elle reste dÃ©sactivÃ©e, donc les commandes sont refusÃ©es tant quâ€™elle nâ€™est pas configurÃ©e. Les appels antÃ©rieurs Ã  ce lot nâ€™ont pas de libellÃ© et sâ€™affichent Â« Fiche nÂ° X Â». La recherche du composeur dÃ©pend de la recherche existante des prospects (format du numÃ©ro saisi). Pas de durÃ©e dâ€™appel ni dâ€™enregistrement, et pas de crÃ©ation de fiche depuis le composeur.

## Conseiller Assurance â€” agenda, rÃ©sultat commercial et fiche client

Le conseiller accÃ¨de au calendrier mensuel partagÃ©, limitÃ© Ã  ses rendez-vous, avec recherche, filtres de statut et fuseau horaire. Chaque crÃ©neau ouvre un panneau Ã  droite : rÃ©sultat, fiche client modifiable et qualification reÃ§ue Ã  la rÃ©servation en lecture seule. Le rÃ©sultat demande explicitement la prÃ©sence Oui/Non et la vente ou le contrat conclu Oui/Non, avec note. Une vente ne peut pas Ãªtre dÃ©clarÃ©e sans rendez-vous tenu. Les anciens comptes rendus conservent une vente Â« non renseignÃ©e Â» ; aucune valeur positive ou nÃ©gative nâ€™est dÃ©duite rÃ©troactivement. Une correction exige un motif, une rÃ©vision Ã  jour et conserve les valeurs avant/aprÃ¨s dans lâ€™audit. Le rÃ©sultat est disponible aprÃ¨s la fin dâ€™un rendez-vous non annulÃ©. Lâ€™absence ou le besoin de suivi conserve le parcours existant de tÃ¢che setter, sans doublon.

Depuis son rendez-vous, le conseiller modifie les coordonnÃ©es et les champs de qualification partagÃ©s de la fiche client. Lâ€™API vÃ©rifie le conseiller du rendez-vous et refuse une fiche explicitement rÃ©attribuÃ©e Ã  un autre conseiller. Les fiches historiques sans attribution explicite restent accessibles au conseiller de leur rendez-vous. Une rÃ©vision pÃ©rimÃ©e ou un verrou setter actif bloque lâ€™Ã©criture ; les saisies restent Ã  lâ€™Ã©cran. Les notes internes courantes ne sont ni exposÃ©es ni modifiables par cette commande ; la qualification figÃ©e lors de la rÃ©servation reste intacte. Fermer le panneau demande confirmation en prÃ©sence de saisies non enregistrÃ©es.

Validation : neuf tests backend ciblÃ©s (droits, rÃ©attribution avant et aprÃ¨s verrouillage, conflits, verrou, audit et rollback, anciennes donnÃ©es, rÃ¨gles prÃ©sence/vente et rÃ©pÃ©tition sans doublon) ; suite Assurance complÃ¨te, avec 26 contrÃ´les PostgreSQL ignorÃ©s sur SQLite ; trois tests du panneau et un test dâ€™accÃ¨s au calendrier conseiller, suites frontend complÃ¨tes ; typage, ESLint, Prettier, Ruff et build. Recette Chrome sur la dÃ©mo PostgreSQL : connexion `conseiller.demo01`, calendrier personnel, rÃ©sultat prÃ©sence/vente et modification dâ€™une note partagÃ©e sur un rendez-vous fictif, qualification dâ€™origine conservÃ©e. Sauvegardes privÃ©es puis migrations additives 0027/0028 appliquÃ©es Ã  la dÃ©mo et Ã  la base SQLite locale.

Limites : vente dÃ©clarative, sans crÃ©ation automatique de mandat/contrat ni nouveau calcul de chiffre dâ€™affaires ; les agrÃ©gats et exports de ventes dÃ©clarÃ©es restent Ã  intÃ©grer. Une correction positive ne ferme pas automatiquement une tÃ¢che de suivi existante. Le motif des corrections est conservÃ© dans lâ€™audit, sans nouvel Ã©cran dâ€™historique dÃ©diÃ©. Synchronisation avec un agenda externe selon les intÃ©grations dÃ©jÃ  configurÃ©es ; aucun compte externe, appel ou message rÃ©el utilisÃ© pendant la recette.

Suite : poursuivre la revue des Ã©crans mÃ©tier et intÃ©grer les ventes dÃ©clarÃ©es aux statistiques et exports Assurance, en les distinguant des contrats enregistrÃ©s.

## Alertes des tÃ¢ches â€” extension Ã  lâ€™espace Isolation

Les alertes de lâ€™en-tÃªte fonctionnent dÃ©sormais dans les deux espaces pour le setter et lâ€™administrateur. Isolation nâ€™ayant pas de boÃ®te de notifications, les rappels en tiennent lieu : pastille et fenÃªtre (une fois par session et par espace) sur les rappels en retard, panneau des rappels ouverts avec le nom du prospect et la mention Â« en retard Â», bandeau Â« Nouvelle tÃ¢che Â» et notification du navigateur Ã  lâ€™apparition dâ€™un nouveau rappel ; ouvrir un rappel mÃ¨ne aux tÃ¢ches (pas dâ€™accusÃ© de lecture en Isolation). `follow-ups/` (Isolation) accepte `order=recent` pour lister les rappels les plus rÃ©cemment crÃ©Ã©s dâ€™abord ; lâ€™ordre par dÃ©faut (Ã©chÃ©ance) est inchangÃ© et toute autre valeur est refusÃ©e. Les prioritÃ©s Assurance sont affichÃ©es en franÃ§ais (basse, normale, haute, urgente).

Validation : test backend de lâ€™ordre `recent` ; test frontend Isolation (pastille sur les retards, fenÃªtre par espace, bandeau et notification du navigateur, aucun appel aux notifications Assurance ni accusÃ© de lecture) ; tests Assurance existants maintenus. DÃ©mo non vÃ©rifiÃ©e : la base PostgreSQL de dÃ©mo ne rÃ©pondait plus au moment du lot.

Limites : en Isolation, la pastille compte les rappels en retard (pas de notion de Â« non lu Â») ; un nouveau rappel nâ€™est repÃ©rÃ© que parmi les 25 plus rÃ©cents.

## Alertes des tÃ¢ches â€” cloche, bandeau, rappel des retards et notifications du navigateur

Pour le setter et lâ€™administrateur Assurance, la cloche de lâ€™en-tÃªte devient un centre dâ€™alertes (`TaskAlerts`), interrogÃ© toutes les 30 secondes : pastille du nombre de notifications non lues ; panneau listant les notifications ouvertes avec le nom du prospect, lâ€™Ã©chÃ©ance et la prioritÃ©, le nombre de tÃ¢ches en retard (de lâ€™Ã©quipe pour lâ€™administrateur) et lâ€™accÃ¨s aux tÃ¢ches ; ouvrir une notification la marque comme lue et mÃ¨ne aux tÃ¢ches. Une nouvelle notification affiche un bandeau Â« Nouvelle tÃ¢che Â» (Ouvrir, Fermer) ; les notifications prÃ©sentes au chargement ne dÃ©clenchent pas de bandeau. Sâ€™il existe des tÃ¢ches en retard, une fenÃªtre Â« N tÃ¢che(s) en retard Â» propose Traiter maintenant ou Plus tard, une seule fois par session. Les notifications du navigateur sâ€™activent depuis le panneau (accord demandÃ© au navigateur) et sâ€™affichent quand lâ€™onglet nâ€™est pas au premier plan. Lâ€™API des notifications renvoie dÃ©sormais `contact_id` et `contact_name` (fiche de la tÃ¢che, sinon celle de son rendez-vous) ; la liste blanche des champs est mise Ã  jour.

Validation : trois tests frontend (pastille, panneau et lecture ; bandeau et notification du navigateur onglet masquÃ©, sans doublon ; rappel des retards une fois par session) ; test backend des champs exposÃ©s ; suite Assurance 311. DÃ©mo `admin.demo` : panneau Â« 668 tÃ¢che(s) de lâ€™Ã©quipe en retard Â», fenÃªtre de retards puis Â« Traiter maintenant Â» vers les tÃ¢ches. Tests frontend, typage, ESLint, Prettier, build, Ruff.

Limites : pas de service worker, donc pas de notification navigateur lorsque lâ€™application est fermÃ©e ; e-mails toujours en attente de la configuration SMTP ; alertes limitÃ©es Ã  Assurance (les rappels Isolation nâ€™ont pas de boÃ®te de notifications). La dÃ©mo ne contient pas de notification non lue.

## Pilotage Assurance (4/4) â€” refonte UX/UI des paramÃ¨tres mÃ©tier

ParamÃ¨tres mÃ©tier repensÃ©s sans changer lâ€™API ni les donnÃ©es envoyÃ©es. Deux onglets : Â« Statuts du pipeline Â» et Â« Champs personnalisÃ©s Â». Chaque Ã©lÃ©ment devient une ligne compacte Ã©ditable sur place : numÃ©ro dâ€™ordre, libellÃ©, interrupteurs (Actif/ArchivÃ© ; pour les champs Obligatoire et Visible au conseiller), flÃ¨ches pour rÃ©ordonner les statuts, type et choix pour les champs. La Â« clÃ© stable Â» nâ€™est plus saisie : pour un nouvel Ã©lÃ©ment elle est gÃ©nÃ©rÃ©e depuis le libellÃ© (minuscules, sans accents, unique), puis affichÃ©e en petit et jamais modifiÃ©e pour un Ã©lÃ©ment existant. Une barre dâ€™enregistrement signale les modifications non enregistrÃ©es et ne demande le motif quâ€™Ã  ce moment, avec Annuler. Explications rÃ©duites Ã  une phrase, dÃ©tails dans Â« Ã€ savoir Â».

Validation : trois tests (gÃ©nÃ©ration des clÃ©s, pipeline avec barre dâ€™enregistrement, rÃ©organisation et charge utile identique, champs en onglet avec clÃ© gÃ©nÃ©rÃ©e) ; dÃ©mo `admin.demo` (interrupteurs, clÃ© Â« date_de_naissance Â» gÃ©nÃ©rÃ©e, rien enregistrÃ©). 83 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : rÃ©organisation par flÃ¨ches (pas de glisser-dÃ©poser) ; la clÃ© gÃ©nÃ©rÃ©e nâ€™est pas modifiable manuellement.

## Pilotage Assurance (3/4) â€” refonte UX/UI des mandats et contrats

Registre des mandats et contrats repensÃ© sans changer lâ€™API ni lâ€™export. Barre dâ€™outils : recherche, type en un clic (Tous, Mandats, Contrats), Â« Plus de filtres Â» repliÃ© (Ã©tat, horizon, bornes de dÃ©but et de fin, avec compteur de filtres actifs) et export Excel Ã  droite. Cartes dâ€™alerte (dates dÃ©passÃ©es, Ã©chÃ©ances dans lâ€™horizon, sans date de fin, total mandats/contrats) : les deux premiÃ¨res appliquent ou retirent le filtre dâ€™Ã©chÃ©ance. Pastilles de rÃ©partition par Ã©tat. Tableau allÃ©gÃ© : rÃ©fÃ©rence et prospect (identifiant technique retirÃ©), type et Ã©tat en pastilles, pÃ©riode lisible Â« dÃ©but â†’ fin Â», Ã©chÃ©ance, piÃ¨ces jointes. Fiche du prospect ouverte dans un panneau latÃ©ral avec garde des modifications, comme sur lâ€™Ã©cran Prospects. Ã‰tat vide explicatif (crÃ©ation depuis la fiche dâ€™un prospect, rÃ©initialisation). Mentions juridiques et pÃ©rimÃ¨tre de lâ€™export regroupÃ©s dans Â« Ã€ savoir Â».

Validation : trois tests (cartes dâ€™alerte et filtre de type, filtres avancÃ©s repliÃ©s et fiche en panneau, Ã©tat vide) ; dÃ©mo `admin.demo` Ã  1 440 px. 80 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : la dÃ©mo ne contient aucun mandat ni contrat (seul lâ€™Ã©tat vide est visible) ; dates dâ€™Ã©chÃ©ance toujours calculÃ©es en UTC.

## Pilotage Assurance (2/4) â€” refonte UX/UI des affectations

Ã‰cran Affectations repensÃ© sans changer lâ€™API ni les rÃ¨gles (attestation du portail, rÃ©vision, historique). Administrateur : barre dâ€™outils avec recherche, filtre dâ€™Ã©tat en un clic (Toutes, Actives, Suspendues) et bouton Â« Nouvelle association Â» ; la crÃ©ation (deux sÃ©lecteurs avec recherche et pagination) passe dans un panneau latÃ©ral et se referme aprÃ¨s lâ€™association ; liste lisible (avatars, setter â†’ conseiller, pastille Active/Suspendue, actions Suspendre/RÃ©activer et Historique) ; historique dans un panneau latÃ©ral en langage clair (Â« Association crÃ©Ã©e Â», Â« suspendue Â», Â« rÃ©activÃ©e Â», date, auteur) au lieu du JSON brut. Setter (Â« Mes conseillers Â») : liste simple des conseillers avec lesquels il peut rÃ©server ; texte obsolÃ¨te sur le Â« lot dÃ©diÃ© Â» retirÃ©.

Validation : trois tests (filtre dâ€™Ã©tat et historique lisible, crÃ©ation dans le panneau puis fermeture, vue setter sans commandes) ; dÃ©mo `admin.demo` Ã  1 440 px (filtre, historique, panneau de crÃ©ation avec 10 setters et 5 conseillers). Tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : pas de confirmation avant suspension (action rÃ©versible) ; lâ€™auteur de lâ€™historique reste un numÃ©ro dâ€™utilisateur.

## Pilotage Assurance (1/4) â€” refonte UX/UI des statistiques

Ã‰cran Statistiques (administrateur et Â« Mes statistiques Â» du setter) repensÃ© sans changer les calculs ni lâ€™API : barre dâ€™outils avec raccourcis de pÃ©riode (7 jours, 30 jours, ce mois, mois dernier), dates libres et Calculer, exports Excel/CSV regroupÃ©s Ã  droite ; ligne de contexte (pÃ©riode, pÃ©rimÃ¨tre, heure de calcul) ; quatre cartes clÃ©s (Rendez-vous avec annulÃ©s et Ã  venir, Taux effectuÃ© avec jauge, Absences dÃ©clarÃ©es, Comptes rendus manquants mis en Ã©vidence) et indicateurs secondaires en pastilles ; dÃ©tail par setter allÃ©gÃ© (identifiant technique retirÃ©, Â« dont N absents Â», badge orange des comptes rendus manquants, jauge du taux) ; mÃ©thodologie et rÃ©serves regroupÃ©es dans Â« Comment sont calculÃ©s ces chiffres ? Â». IntitulÃ©s de colonnes disponibles pour lâ€™affichage en cartes sur tÃ©lÃ©phone.

Validation : trois tests (cartes et dÃ©tail Ã©quipe, raccourci de pÃ©riode qui recalcule, setter sans tableau dâ€™Ã©quipe) ; dÃ©mo `admin.demo` Ã  1 440 px. 74 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : dates toujours en jours UTC (API inchangÃ©e) ; pas de graphique dâ€™Ã©volution dans le temps. Affectations, Mandats et contrats, ParamÃ¨tres mÃ©tier : lots suivants.

## Setter Assurance â€” retrait dâ€™OpportunitÃ©s

Le module OpportunitÃ©s nâ€™apparaÃ®t plus dans le menu du setter Assurance (Accueil, Prospects, Rendez-vous, TÃ¢ches, Mes conseillers, Appels, Mes statistiques). Il reste disponible pour lâ€™administrateur. Les statuts du pipeline restent utilisÃ©s par le tableau des prospects du setter.

Validation : dÃ©mo avec `setter.demo01`, menu sans OpportunitÃ©s. 71 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : retrait dâ€™interface ; lâ€™API du pipeline reste accessible aux setters (les statuts servent au tableau des prospects).

## Socle technique â€” fin des `import *` historiques

`core/views.py` et `core/tests.py` importent dÃ©sormais explicitement leurs modÃ¨les et sÃ©rialiseurs au lieu de `from .models import *` / `from .serializers import *`. Les exceptions Ruff correspondantes (F403/F405) sont retirÃ©es : tout le Python est contrÃ´lÃ© par les mÃªmes rÃ¨gles. Aucun module nâ€™importait de modÃ¨le via `core.views`. Aucun changement de comportement.

Validation : `ruff check` sans exception de ce type ; suites core 249, portail 221, Assurance 311, unittest base commune/dÃ©mo, `manage.py check`.

## Correctif â€” test dâ€™appel instable

`test_phone_calls.test_one_dispatch_replay_status_and_private_output` vÃ©rifiait que le poste (Â« 501 Â») et le numÃ©ro (Â« 1514â€¦ Â») nâ€™apparaissent pas dans la rÃ©ponse, y compris dans lâ€™identifiant de requÃªte alÃ©atoire : un UUID contenant Â« 501 Â» (#127) puis des microsecondes Â« 144501 Â» (#129) faisaient Ã©chouer la CI par hasard. Le test vÃ©rifie dÃ©sormais la liste exacte des champs renvoyÃ©s et lâ€™absence de ces chiffres dans les seules valeurs texte (hors identifiant alÃ©atoire et dates). Aucun changement applicatif.

## RÃ´les terrain â€” intitulÃ©s de colonne dans les cartes sur tÃ©lÃ©phone

En mode carte (tÃ©lÃ©phone, conseiller, closer et client), chaque valeur affiche dÃ©sormais lâ€™intitulÃ© de sa colonne au-dessus dâ€™elle ; la premiÃ¨re cellule (prospect ou dossier) sert de titre de carte, en gras. Colonnes Ã©tiquetÃ©es : rendez-vous Assurance (Conseiller, CrÃ©neau, Statut), visites du closer (Rendez-vous, Setter, RÃ©sultat), dossiers du client (TÃ©lÃ©phone, RÃ©fÃ©rence, Suivi) et indicateurs des statistiques Isolation. Affichage inchangÃ© sur ordinateur.

Validation : dÃ©mo Ã  375 px, statistiques du client avec intitulÃ©s (Â« Rendez-vous rÃ©servÃ©s Â», Â« Rendez-vous tenus Â»â€¦) et sans dÃ©bordement. 71 tests frontend, typage, ESLint, Prettier et build.

Limites : seuls ces quatre tableaux sont Ã©tiquetÃ©s ; un nouveau tableau destinÃ© aux rÃ´les terrain devra porter ses `data-label`.

## Titres en double supprimÃ©s

Sur les Ã©crans Ã  mise en page gÃ©nÃ©rique, le titre de page Ã©tait rÃ©pÃ©tÃ© par lâ€™en-tÃªte de la carte (Â« Visites Â» puis Â« Visites Â»), puis souvent par le composant (Â« Visites Isolation Â», Â« Rendez-vous Assurance Â»). Lâ€™en-tÃªte de carte est supprimÃ© partout (avec ses rÃ¨gles CSS devenues inutiles) ; les titres internes des listes de visites et de rendez-vous ne sâ€™affichent plus que lorsquâ€™ils apportent un contexte (fiche dâ€™un prospect : Â« Visites Â· nom Â», Â« Rendez-vous du prospect Â» ; formulaire de rÃ©servation).

Validation : dÃ©mo â€” Statistiques Assurance de trois titres Ã  deux, Visites du client Isolation Ã  un seul. 71 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : Â« Mes dossiers Â» du client garde le titre Â« Mon espace client Isolation Â» de son composant (la mise en page Contacts masque dÃ©jÃ  le titre de page) ; titres internes des autres modules inchangÃ©s.

## AccÃ¨s direct au dernier espace â€” fin de la page Â« Mes espaces Â»

Un compte autorisÃ© dans les deux espaces nâ€™est plus arrÃªtÃ© sur la page Â« Mes espaces Â» au rechargement ou au retour sur le site : le dernier espace utilisÃ© (mÃ©morisÃ© dans le navigateur) est rouvert, sinon lâ€™espace dâ€™accueil du portail, sinon le premier espace autorisÃ©. Le changement dâ€™espace se fait par le menu du profil. La connexion ouvrait dÃ©jÃ  lâ€™espace du profil choisi. La page ne subsiste que pour un compte sans espace actif. MÃ©morisation au mieux : stockage indisponible sans effet bloquant.

Validation : dÃ©mo avec `setter.demo01` â€” connexion Isolation puis rechargement : Isolation ; bascule Assurance par le profil puis rechargement : Assurance ; page de choix jamais affichÃ©e. 71 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : mÃ©morisation par navigateur (pas par compte cÃ´tÃ© serveur).

## Closer et client Isolation â€” cadre commun utilisable sur tÃ©lÃ©phone

Le closer et le client Isolation passent sur le cadre commun, comme le conseiller : leurs menus et libellÃ©s sont conservÃ©s (closer : Mes visites, Mes statistiques ; client : Vue dâ€™ensemble, Mes dossiers, Visites, Statistiques), sans recherche, appels ni Pilotage ; profil Â« Isolation Â· Closer Â» ou Â« Isolation Â· Client Â». La mise en cartes des tableaux sur tÃ©lÃ©phone (sous 700 px) est dÃ©sormais commune aux rÃ´les terrain (conseiller, closer, client) et portÃ©e par le cadre ; la copie propre au conseiller est retirÃ©e.

Validation : tests de cadre closer et client (libellÃ©s conservÃ©s, ni recherche, ni appels, ni Pilotage). DÃ©mo Ã  375 px : aucun dÃ©bordement horizontal pour le closer (visites, statistiques) ni pour le client (vue dâ€™ensemble, dossiers, visites). 71 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : en carte, les cellules nâ€™ont plus lâ€™intitulÃ© de leur colonne ; double titre Â« Visites Â» / Â« Visites Isolation Â» encore prÃ©sent sur plusieurs Ã©crans. Parcours terrain Ã  repenser plus tard.

## RÃ©servation Isolation â€” disponibilitÃ©s du client dans la fiche

La rÃ©servation de visite (Â« PrÃ©parer le C2 et rÃ©server Â») affiche la mÃªme grille que la rÃ©servation Assurance : crÃ©neaux du jour libres, occupÃ©s (barrÃ©s) ou passÃ©s, pour la durÃ©e choisie ; un clic remplit la date et lâ€™heure. La grille devient un composant partagÃ© `AvailabilitySlots`, utilisÃ© par les deux espaces.

Nouvelle API `GET visits/availability/?prospect_id=&start=&end=` : plages occupÃ©es du client Isolation (client unique garanti par le portail, donc toutes les visites planifiÃ©es) et du prospect. Horaires uniquement, aucune identitÃ© dâ€™autre prospect. Setters (prospects qui leur sont affectÃ©s) et administrateurs ; client refusÃ© ; sept jours au plus.

Validation : test backend (motifs client/prospect, administrateur, setter affectÃ©, autre setter 404, client 403, plages invalides) ; tests frontend du composant partagÃ© et de la requÃªte Assurance. DÃ©mo : client occupÃ© de 13 h 30 Ã  17 h 30, crÃ©neaux libres ensuite. Suites core 249, Assurance 311, 70 tests frontend, typage, lint, format et build.

Limites : agenda externe du client vÃ©rifiÃ© Ã  la confirmation seulement ; plage 8 hâ€“20 h fixe. Le report dâ€™une visite garde la saisie ISO existante.

## RÃ©servation Assurance depuis la fiche â€” disponibilitÃ©s du conseiller

Dans lâ€™onglet Rendez-vous de la fiche prospect, dÃ¨s quâ€™un conseiller attribuÃ© est choisi, une grille du jour (8 hâ€“20 h, pas de 30 minutes, navigation jour par jour) affiche les crÃ©neaux libres, occupÃ©s (barrÃ©s) et passÃ©s, selon la durÃ©e choisie et le fuseau affichÃ©. Un clic remplit la date et lâ€™heure ; la saisie manuelle reste possible. Plus besoin de rÃ©server Ã  lâ€™aveugle pour dÃ©couvrir Â« CrÃ©neau indisponible Â».

Nouvelle API `GET appointments/availability/?assignment_id=&start=&end=[&contact_id=]` : plages occupÃ©es du CRM pour le conseiller de lâ€™attribution et, si fourni, pour le prospect. Horaires uniquement (dÃ©but, fin, motif conseiller/prospect), aucune identitÃ© dâ€™autre prospect. RÃ©servÃ©e aux setters (leurs attributions actives) et administrateurs ; pÃ©riode de sept jours au plus, dates ISO avec dÃ©calage.

Validation : test backend (pÃ©rimÃ¨tre setter/administrateur, refus autre setter et conseiller, motif prospect, plages invalides, absence dâ€™identitÃ©) ; test frontend (requÃªte, crÃ©neaux occupÃ©s/libres, sÃ©lection). DÃ©mo : avec `setter.demo01`, crÃ©neau occupÃ© barrÃ© et crÃ©neaux passÃ©s grisÃ©s, clic reportÃ© dans le champ. 69 tests frontend, 311 tests Assurance, typage, lint, format et build.

Limites : lâ€™agenda Google/Microsoft du conseiller nâ€™est consultÃ© quâ€™Ã  la confirmation (contrÃ´le ponctuel existant), la grille peut donc proposer un crÃ©neau occupÃ© Ã  lâ€™extÃ©rieur. Plage 8 hâ€“20 h fixe, sans horaires de travail paramÃ©trables par conseiller.

## Conseiller Assurance â€” harmonisation simple, utilisable sur tÃ©lÃ©phone

Le conseiller passe sur le cadre commun (en-tÃªte, barre latÃ©rale, menu mobile) avec un seul menu, **Mes rendez-vous**, et Mon compte ; il y arrive directement Ã  lâ€™entrÃ©e dans lâ€™espace. Recherche, appels, Contacts, OpportunitÃ©s et Vue dâ€™ensemble ne lui sont plus proposÃ©s. La liste des rendez-vous nâ€™affiche plus de double titre ni le texte de rÃ©servation (le conseiller ne rÃ©serve pas) : un texte dÃ©diÃ© rappelle qualification et compte rendu ; la colonne Conseiller (toujours lui-mÃªme) est masquÃ©e. Sous 700 px, chaque rendez-vous devient une carte empilÃ©e, boutons pleine largeur ; vÃ©rifiÃ© Ã  375 px dans la dÃ©mo sans aucun dÃ©bordement horizontal.

Validation : test de cadre conseiller (menu unique, ni recherche, ni appels, ni Pilotage) ; client Isolation conservÃ© sur lâ€™ancien cadre. 68 tests frontend, typage, ESLint, Prettier et build. Aucun changement backend.

Limites : harmonisation volontairement minimale ; parcours conseiller (cartes par jour, appel direct, compte rendu mobile) Ã  repenser ultÃ©rieurement. Closer et client Isolation gardent lâ€™ancien cadre.

## Socle technique â€” formatage des templates Vue

Lot technique sans changement fonctionnel. Les `<template>` des 63 composants sont dÃ©sormais formatÃ©s par Prettier et contrÃ´lÃ©s en CI ; plus aucun composant exclu. Les fichiers `.vue` utilisent `semi: true` (dÃ©rogation commentÃ©e dans `.prettierrc.json`) : sans point-virgule, Prettier rÃ©partissait les gestionnaires Ã  plusieurs instructions (`emit(â€¦); ouvert = false`) sur plusieurs lignes que le compilateur Vue ne sait pas lire, ce qui cassait le build. Les conversions `as Record<string,string>` des templates (`AssuranceContacts`, `AssuranceQualification`, `AssuranceQualificationSnapshot`, `IsolationProspectActivity`, `Portal`) deviennent des constantes typÃ©es du script.

Tests : les recherches de boutons par texte exact comparent dÃ©sormais le texte sans espaces de bord (le formatage ajoute des espaces autour des libellÃ©s, sans effet Ã  lâ€™Ã©cran).

Validation : comparaison du texte produit par chaque template avant/aprÃ¨s â€” contenu identique, seules des espaces de dÃ©but/fin de texte apparaissent. Build, typage, ESLint, Prettier et 67 tests rÃ©ussis ; Ã©crans dâ€™accueil, visites et vÃ©rification contrÃ´lÃ©s en dÃ©mo sans erreur console.

Limites : ces espaces de bord pourraient se voir Ã  cÃ´tÃ© dâ€™une icÃ´ne dans un conteneur non flexible ; non constatÃ© sur les Ã©crans parcourus, Ã  surveiller lors de la revue esthÃ©tique finale.

## Socle technique â€” lint frontend (ESLint)

ESLint 9 (versions figÃ©es) avec rÃ¨gles de justesse uniquement : JavaScript et TypeScript recommandÃ©s, `vue/flat/essential` ; la mise en forme reste Ã  Prettier. `pnpm lint` et la CI lâ€™exigent. Exceptions commentÃ©es : `no-explicit-any` dÃ©sactivÃ©e (charges dâ€™API typÃ©es librement dans tout le projet), `catch` vides autorisÃ©s (stockage navigateur Â« au mieux Â»), nom Ã  un mot autorisÃ© pour le composant racine `Portal`.

Corrections : un Ã©lÃ©ment de la fiche tÃ¢che Assurance portait Ã  la fois `v-if` et `v-else` ; il devient `v-else-if="selected"`, comme voulu (fiche setter seulement quand une tÃ¢che est ouverte, Ã©diteur administrateur sinon). Imports dâ€™icÃ´nes, de composant et variables inutilisÃ©s retirÃ©s (`Portal`, `CrmOverview`, `AssuranceSetterTasks`, `AssuranceContacts`, `AssuranceContactFollowups`, `IsolationQualification`, `PortalLogin`), index de boucle inutile, imports inutiles dans six tests.

Validation : `eslint .` sans erreur, 67 tests frontend, typage, Prettier et build rÃ©ussis.

Limites : typage strict des rÃ©ponses dâ€™API (`any`) non entrepris.

## Socle technique â€” lint Python (Ruff check)

Lot technique sans changement fonctionnel. `ruff check .` (rÃ¨gles par dÃ©faut : pyflakes et erreurs pycodestyle) est dÃ©sormais exigÃ© en CI. Corrections : imports inutilisÃ©s retirÃ©s (les rÃ©-exports rÃ©ellement utilisÃ©s, comme `Unavailable` des contrÃ´les dâ€™agenda, sont conservÃ©s explicitement), imports tardifs remontÃ©s en tÃªte dans les tests, `appointments.py` et `calendar_sync.py`, affectations inutiles retirÃ©es en conservant les appels Ã  effet (dont `get_object()` qui contrÃ´le lâ€™accÃ¨s), `lambda` remplacÃ©es par des fonctions.

Exceptions explicites et commentÃ©es dans `ruff.toml` : imports tardifs des settings (configuration des schÃ©mas), des `urls.py` construits par blocs, des scripts opÃ©rateur (aprÃ¨s `django.setup()`) et des modules `isolation_followups`/`isolation_work` (imports mutuels) ; `import *` historiques de `core/views.py` et `core/tests.py`.

Validation : suites core 248, portail 221, Assurance 310, unittest base commune/dÃ©mo, `manage.py check` des trois projets, `ruff check` et `ruff format --check`.

Limites : ESLint pour le frontend reste Ã  ajouter dans un lot sÃ©parÃ© ; les `import *` de `core/views.py` et `core/tests.py` restent Ã  remplacer.

## Calendrier dâ€™Ã©quipe â€” filtre par membre cÃ´tÃ© serveur

`appointments/` (Assurance) accepte `setter_id` et `advisor_id` ; `visits/` (Isolation) accepte `setter_id`, `closer_id` et `client_id`. Ces paramÃ¨tres ne font que restreindre le pÃ©rimÃ¨tre dÃ©jÃ  appliquÃ© selon le rÃ´le : un setter ou un client ne voit jamais au-delÃ  de ses propres rendez-vous ; un identifiant non numÃ©rique est refusÃ© (400). Le calendrier transmet le membre choisi et recharge : naviguer de mois en mois sur un membre ne charge plus toute lâ€™Ã©quipe. Les membres rencontrÃ©s dans les mois dÃ©jÃ  chargÃ©s restent proposÃ©s dans le filtre.

Validation : deux tests backend (filtres Assurance et Isolation, combinaison, refus dâ€™identifiant invalide, absence dâ€™Ã©largissement pour setter/client), tests calendrier mis Ã  jour (paramÃ¨tres envoyÃ©s, mÃ©moire des membres). Suites core 248, Assurance 310, 67 tests frontend, typage, format et build. Aucune migration.

Limites : la vue Â« Toute lâ€™Ã©quipe Â» charge toujours le mois complet ; la liste des membres provient des rendez-vous dÃ©jÃ  chargÃ©s (pas dâ€™annuaire dÃ©diÃ©). Les API de dÃ©mo dÃ©jÃ  lancÃ©es doivent Ãªtre redÃ©marrÃ©es pour en bÃ©nÃ©ficier.

## Correctifs issus de la revue en dÃ©mo â€” parcours administrateur

Revue navigateur des lots administrateur sur la dÃ©mo fictive (`admin.demo`, Assurance et Isolation). Quatre dÃ©fauts corrigÃ©s :

- **Chiffres des cartes dâ€™accueil** : la taille des compteurs suit dÃ©sormais la largeur de la carte (container query), ils ne passent plus sous le bouton flÃ¨che sur Ã©cran moyen. Vaut aussi pour lâ€™accueil setter ; la date du prochain rendez-vous garde son retour Ã  la ligne.
- **Chargement du calendrier dâ€™Ã©quipe** : `appointments/` (Assurance) et `visits/` (Isolation) acceptent `page_size` bornÃ© Ã  100 ; le calendrier lâ€™utilise. Un mois de 620 rendez-vous passe de 28 requÃªtes sÃ©quentielles (â‰ˆ 9 s en dÃ©mo) Ã  7. Pagination par dÃ©faut inchangÃ©e (25) et `Pager` Isolation partagÃ© non modifiÃ© pour les autres listes.
- **LibellÃ©** : dans Â« TÃ¢ches de lâ€™Ã©quipe Â» Assurance, le bouton devient Â« Voir lâ€™agenda de lâ€™Ã©quipe Â» pour lâ€™administrateur.
- **Recherche sur mobile** : lâ€™icÃ´ne de recherche de lâ€™en-tÃªte ne se rÃ©duit plus Ã  une pastille vide.

Validation : deux tests backend (taille de page optionnelle et bornÃ©e, Assurance et Isolation), assertions frontend sur le libellÃ© et `page_size=100`. Suites core 247, portail 221, Assurance 309, migrations, 67 tests frontend, typage, format et build. En dÃ©mo : compteurs lisibles, libellÃ© et icÃ´ne mobile vÃ©rifiÃ©s ; la requÃªte calendrier porte `page_size=100`, mais les API de dÃ©mo dÃ©jÃ  lancÃ©es gardent lâ€™ancien code jusquâ€™Ã  leur redÃ©marrage (non redÃ©marrÃ©es).

Limites : le chargement reste sÃ©quentiel et cÃ´tÃ© navigateur pour le filtre par membre ; au-delÃ  de quelques milliers de rendez-vous par mois, un filtre serveur sera nÃ©cessaire.

## Prospects Assurance administrateur â€” tableau par statut et imports conservÃ©s

Lâ€™administrateur Assurance ouvre dÃ©sormais Prospects sur le mÃªme tableau que le setter : colonnes par statut du pipeline, cartes, recherche serveur, filtre de statut, pagination par colonne et fiche dans le panneau latÃ©ral avec ses commandes administratives existantes. IntitulÃ© Â« Ã‰quipe Assurance Â». Les commandes dâ€™appel ne sont pas proposÃ©es Ã  lâ€™administrateur, comme en Isolation. Une bascule **Tableau / Liste et imports** redonne lâ€™Ã©cran Contacts existant (imports CSV/XLSX avec aperÃ§u, mappage et historique, onglets et filtres) ; le nombre de contacts importÃ©s met toujours Ã  jour lâ€™accueil, et le retour au tableau le recharge. Aucun changement backend, aucune migration.

Validation : trois tests (tableau dâ€™Ã©quipe sans commande dâ€™appel, bascule vers la liste avec remontÃ©e de lâ€™import puis tableau rechargÃ©, setter inchangÃ© avec appel et sans bascule). Suite frontend 67 tests, typage, format et build rÃ©ussis.

Limites : lâ€™import reste dans lâ€™Ã©cran liste, sans refonte de son parcours. Pas de revue visuelle en navigateur ; revue esthÃ©tique diffÃ©rÃ©e.

## Calendrier dâ€™Ã©quipe administrateur â€” Assurance et Isolation

Lâ€™administrateur ouvre dÃ©sormais Rendez-vous ou Visites sur le calendrier mensuel dÃ©jÃ  utilisÃ© par le setter, intitulÃ© Â« Ã‰quipe Â» avec lâ€™agenda de toute lâ€™Ã©quipe. Un filtre **Membre de lâ€™Ã©quipe** regroupe setters et conseillers (Assurance) ou setters dâ€™origine, closers et clients (Isolation), construit Ã  partir des rendez-vous du mois chargÃ© ; la recherche couvre aussi ces noms. Une bascule **Calendrier / Liste** redonne accÃ¨s Ã  la liste de gestion existante sans rien retirer ; la rÃ©servation et le dÃ©tail complet restent disponibles depuis le calendrier. Les modifications de visites Isolation depuis la liste rafraÃ®chissent les compteurs de lâ€™espace. Aucun changement backend, aucune migration : les participants Ã©taient dÃ©jÃ  renvoyÃ©s aux seuls administrateurs.

Validation : quatre tests (filtre setter/conseiller Assurance sans nouvelle requÃªte, bascule liste/calendrier, groupes setters/closers/clients Isolation, setter sans filtre ni bascule). Suite frontend 64 tests, typage, format et build rÃ©ussis.

Limites : filtrage cÃ´tÃ© navigateur sur le mois chargÃ© ; un mois trÃ¨s chargÃ© est rÃ©cupÃ©rÃ© page par page (25 lignes) avant affichage. Un membre sans rendez-vous ce mois nâ€™apparaÃ®t pas dans la liste. Pas de revue visuelle en navigateur ; revue esthÃ©tique diffÃ©rÃ©e. Prochain lot : prospects Assurance administrateur alignÃ©s sur lâ€™Ã©cran setter, import conservÃ©.

## Accueil et navigation administrateur â€” Assurance et Isolation

Lâ€™administrateur utilise dÃ©sormais le mÃªme cadre que le setter : en-tÃªte avec recherche, tÃ¢ches et profil (Â« Assurance Â· Administration Â»), barre latÃ©rale sombre. La navigation principale regroupe Accueil, Prospects, Rendez-vous ou Visites, OpportunitÃ©s (Assurance) et TÃ¢ches ; un bloc **Pilotage** rassemble Statistiques, Affectations, Mandats et contrats, ParamÃ¨tres mÃ©tier, VÃ©rification des numÃ©ros (Isolation) et, pour les gestionnaires dâ€™accÃ¨s, Utilisateurs et accÃ¨s. Les commandes dâ€™appel restent rÃ©servÃ©es au setter. Conseiller, closer et client conservent lâ€™ancien cadre.

Nouvel accueil administrateur : prospects du pÃ©rimÃ¨tre, tÃ¢ches ouvertes et tÃ¢ches en retard de lâ€™Ã©quipe, raccourcis vers les affectations (Assurance) ou le nombre de prospects sans affectation (Isolation), lâ€™agenda et les statistiques, et les trois prochains rendez-vous ou visites de lâ€™Ã©quipe. Les alertes dâ€™Ã©chÃ©ance des mandats, rappels et notifications Assurance restent affichÃ©s, ouverts par dÃ©faut. Les compteurs viennent des API existantes (`follow-ups/summary/` en Assurance, total de `follow-ups/?state=overdue` en Isolation) : aucun changement backend, aucune migration. Un Ã©chec de compteur affiche Â« Indisponible Â» et une alerte avec reprise, jamais un zÃ©ro trompeur.

Validation : quatre tests de cadre (modules principaux et Pilotage, accÃ¨s rÃ©servÃ© aux gestionnaires, entrÃ©e active unique, autres rÃ´les inchangÃ©s) et quatre tests dâ€™accueil (compteurs et agenda Assurance, retards et prospects sans affectation Isolation, Ã©chec de compteur, accueil setter inchangÃ©). Suite frontend 60 tests, typage, format et build rÃ©ussis. Aucun appel, message ni fournisseur sollicitÃ©.

Limites : pas de revue visuelle en navigateur dans ce lot (environnement dÃ©mo non lancÃ©) ; revue esthÃ©tique diffÃ©rÃ©e. Les compteurs ne se rafraÃ®chissent quâ€™Ã  lâ€™ouverture ou via Actualiser. Le calendrier en vue dâ€™Ã©quipe et lâ€™alignement des prospects Assurance administrateur restent au lot suivant.

## Socle technique â€” formatage automatique du code

Lot technique sans changement fonctionnel. Python formatÃ© par Ruff 0.6.9 (`ruff.toml` : 100 colonnes, guillemets simples, migrations exclues) ; frontend formatÃ© par Prettier 3.3.3 (`frontend/.prettierrc.json` : guillemets simples, sans point-virgule, 100 colonnes) pour les `<script>`, `<style>`, fichiers TypeScript, configurations et tests. La CI refuse dÃ©sormais un code non formatÃ© (`ruff format --check .`, `pnpm exec prettier --check .`).

Les `<template>` Vue restent volontairement intacts grÃ¢ce Ã  un `<!-- prettier-ignore -->` : les harnais de test transforment par expressions rÃ©guliÃ¨res le rendu compilÃ©, que la remise en forme des templates modifie. Cinq composants sont exclus entiÃ¨rement (`AssuranceContacts`, `AssuranceQualification`, `AssuranceQualificationSnapshot`, `IsolationProspectActivity`, `Portal`) : le parseur Prettier ne lit pas les conversions `as Record<string,string>` de leurs templates. Seule adaptation des tests : les harnais tolÃ¨rent la virgule finale des imports dâ€™icÃ´nes.

Validation : bundle JS de production identique hors identifiants de portÃ©e Vue ; CSS identique hors espaces dans les valeurs de variables CSS et identifiants dâ€™animations portÃ©s. Suites core 246 (19 ignorÃ©s), portail 221 (11 ignorÃ©s), Assurance 308 (26 ignorÃ©s), unittest base commune/dÃ©mo, contrÃ´le des migrations des trois projets, 52 tests frontend, typage, builds principal et dÃ©mo rÃ©ussis.

Limites : templates Vue (environ 225 Ko) encore sur de longues lignes ; leur formatage demande dâ€™abord des harnais de test indÃ©pendants de la forme du code compilÃ©. Prochain lot fonctionnel inchangÃ© : accueil, navigation et calendriers administrateur.

## Reprise des tÃ¢ches â€” Isolation et administration Assurance

Isolation setter et administrateur disposent du tableau Ã€ traiter / En retard / TerminÃ©es, avec cartes, compteurs sur tout le pÃ©rimÃ¨tre filtrÃ©, recherche serveur avant pagination, 25 lignes par Ã©tat et chargement complÃ©mentaire indÃ©pendant. Les totaux sont indisponibles lorsquâ€™une colonne Ã©choue, plutÃ´t quâ€™affichÃ©s partiellement comme complets. Les Ã©chÃ©ances restent en heure de MontrÃ©al. Ã‰dition et clÃ´ture sâ€™ouvrent Ã  droite ; les brouillons et opÃ©rations en cours empÃªchent une fermeture silencieuse. La crÃ©ation manuelle depuis la fiche prospect reste disponible.

La recherche Isolation couvre nom, tÃ©lÃ©phone et note sans Ã©largir lâ€™affectation du setter ; lâ€™administration garde son pÃ©rimÃ¨tre existant et voit le nom du responsable actuel. Aucun changement de rÃ´le, aucune migration.

Assurance administrateur reprend le mÃªme tableau que le setter, avec vue dâ€™Ã©quipe et commandes administratives dans la fiche : rÃ©attribution, historique, planification, clÃ´ture et rÃ©ouverture. Les rÃ¨gles des suivis sont accessibles dans un panneau propre avec protection des modifications. Le sÃ©lecteur de date remplace la saisie ISO pour la planification et convertit explicitement lâ€™heure de MontrÃ©al, sans modifier les rÃ¨gles backend. Les setters ne reÃ§oivent aucune commande administrative.

Validation : tests dÃ©diÃ©s des tableaux et commandes par rÃ´le, pagination avec filtres appliquÃ©s, prÃ©paration de clÃ´ture sans POST automatique, planification avec dÃ©calage MontrÃ©al, recherche backend limitÃ©e au propriÃ©taire ; tests existants de crÃ©ation/clÃ´ture maintenus. Suite core : 246 tests dont 19 ignorÃ©s ; suite frontend 51 tests plus le test de planification administrateur, typage et build rÃ©ussis. Aucun appel, message ni fournisseur sollicitÃ©. Revue visuelle toujours indisponible dans Work.

Limites : tableaux Ã  actualiser, sans glisser-dÃ©poser ni garantie transactionnelle entre les trois lectures dâ€™Ã©tat ; les tÃ¢ches sont classÃ©es selon leur Ã©chÃ©ance rÃ©elle. Les outils administratifs existants restent disponibles dans les panneaux, sans refonte de leurs contrats mÃ©tier. Prochain lot : accueil, navigation et calendriers administrateur, et alignement des prospects Assurance administrateur en conservant lâ€™import.

## Reprise des prospects Isolation â€” setter et administration

La file Isolation utilise les cartes du modÃ¨le Assurance, sans photo : statuts vides masquÃ©s, recherche et filtres, pagination indÃ©pendante de 25 par statut, quatre cartes par ligne sur grand Ã©cran si un seul statut reste visible. Les six statuts commerciaux Isolation sont conservÃ©s. Chargement bornÃ© Ã  trois requÃªtes simultanÃ©es, rÃ©ponses pÃ©rimÃ©es ignorÃ©es, erreurs par colonne et recherche appliquÃ©e conservÃ©e lors de la pagination. La page utilise toute la largeur disponible.

Les cartes donnent accÃ¨s Ã  la fiche, Ã  la prÃ©paration explicite dâ€™appel pour le setter et au C2/visites. La fiche latÃ©rale sÃ©pare rÃ©sultat dÃ©clarÃ©, notes/statut, rappels et historique par onglets sans dÃ©monter leurs brouillons. La prÃ©paration recharge le numÃ©ro courant, conserve la confirmation CallAction et nâ€™envoie jamais automatiquement un appel. Fermeture bloquÃ©e pendant une commande et confirmation existante des brouillons prÃ©servÃ©e.

Lâ€™administrateur conserve la rÃ©partition et les affectations groupÃ©es (sur les cartes chargÃ©es), la recherche des setters, lâ€™affectation individuelle et lâ€™historique dans des panneaux Ã  droite. Aucun bouton dâ€™appel setter ajoutÃ© Ã  lâ€™administration, aucun nouveau droit. Les routes et contrÃ´les backend restent inchangÃ©s.

Validation : trois tests de composants dÃ©diÃ©s (statuts vides, pagination et recherche appliquÃ©e, ouverture de fiche/appel sans POST, commandes administrateur et absence dâ€™appel), suite frontend complÃ¨te, typage et build production. Aucun appel ni Lookup rÃ©el. Revue visuelle non rÃ©alisÃ©e : accÃ¨s navigateur local dÃ©sactivÃ© dans Work. La mise en forme ne vaut pas validation visuelle dÃ©finitive.

Prochain lot : harmoniser les tÃ¢ches Isolation puis les vues dâ€™administration communes (navigation, accueil et calendrier), en gardant les actions propres Ã  chaque rÃ´le.

## CRM unique â€” retrait du front autonome CallVerify

La racine, /demo et les anciennes pages Ã  hash montent dÃ©sormais uniquement le portail et normalisent leur adresse vers /crm. Lâ€™ancien choix entre App et Portal Ã©tait la cause de lâ€™application sÃ©parÃ©e encore visible Ã  la racine. Suppression des composants App.vue, Workspace.vue et de leur client API exclusivement historique ; titre HTML AMX. La connexion Ã  profils existante est conservÃ©e selon la demande initiale. Retours OAuth et liens centraux invitation/rÃ©cupÃ©ration prÃ©servÃ©s ; les anciens jetons locaux ne sont pas convertis en identitÃ©s centrales.

Le lot intÃ©grÃ© est nommÃ© VÃ©rification des numÃ©ros dans la navigation administrateur Isolation : listes, import/aperÃ§u/confirmation, Lookup explicite, rÃ©sultats et exports. Il reste absent des autres rÃ´les et dâ€™Assurance ; lâ€™API contrÃ´le lâ€™audience et le rÃ´le, sans accepter une session administrative locale historique. Correction des collisions de routes GET/POST import/export qui masquaient des mÃ©thodes. TÃ©lÃ©chargement des exports via le client mÃ©tier authentifiÃ©, sans navigation vers un lien sans ticket.

Validation : 245 tests core dont 19 ignorÃ©s, 44 tests frontend, typage et build rÃ©ussis (JS 482,33 kB). Tests des anciennes entrÃ©es et OAuth, quatre onglets, import/export synthÃ©tique, tÃ©lÃ©chargement et erreurs, refus de onze opÃ©rations pour six profils non autorisÃ©s et dâ€™une session locale. Treize contrÃ´les HTTP sur la recette vÃ©rifient racine unique et pÃ©rimÃ¨tres administrateur Isolation/setter/administrateur Assurance. Aucun fournisseur, appel ou Lookup rÃ©el exÃ©cutÃ© ; aucun compte ou fichier mÃ©tier supprimÃ©. Revue visuelle Ã  faire. [DÃ©tails et limites](CRM_ENTRYPOINT.md).

Limites : ancien front retirÃ©, traitements/modÃ¨les et API backend historiques conservÃ©s pour compatibilitÃ© ; aucune migration des donnÃ©es ou fusion de comptes. La recette 5174 a Ã©tÃ© rechargÃ©e, les serveurs habituels sont prÃ©servÃ©s. Prochain lot : reprendre la rÃ©pÃ©tition de centralisation des copies SQLite et la validation de restauration de la base commune.

## Recette volumineuse â€” donnÃ©es fictives dans une base commune sÃ©parÃ©e

Un gÃ©nÃ©rateur reproductible crÃ©e une nouvelle base PostgreSQL locale de recette, migre les trois schÃ©mas et remplit les parcours Assurance/Isolation par ORM. Aucun reset ni Ã©crasement dâ€™un jeu existant : nouveau dossier privÃ© vide, nom de base alÃ©atoire rÃ©servÃ©, manifeste synthetic/disposable et refus de second remplissage. Volume paramÃ©trable de 40 Ã  20 000 prospects par espace, 5 000 par dÃ©faut. Noms/adresses marquÃ©s DÃ©mo, courriels example.invalid et tÃ©lÃ©phones Ã  indicatif rÃ©gional invalide 000 ; aucune fausse preuve Lookup ou observation fournisseur.

Le jeu local crÃ©Ã© contient 10 000 prospects, 2 500 rendez-vous passÃ©s/futurs avec annulations et rÃ©sultats manquants, 956 comptes rendus, 3 334 tÃ¢ches en retard/Ã  venir/terminÃ©es, 10 000 notes et 10 000 rÃ©sultats dâ€™appel dÃ©clarÃ©s. Six campagnes Isolation. Vingt-deux comptes et 33 appartenances couvrent administrateur, dix setters dans les deux espaces, cinq conseillers Assurance, cinq closers Isolation et le client Isolation unique. Qualifications et C2 distincts, instantanÃ©s figÃ©s, attributions et liens de rappel conservÃ©s.

Un lanceur dÃ©diÃ© expose la recette sur localhost:5174/crm et les API sur 8190/8191/8100, sans repli vers les serveurs actuels. Refus des ports occupÃ©s, cookies portail distincts, arrÃªt des seuls processus enfants. Le lanceur ne charge pas .env et filtre les variables hÃ©ritÃ©es : aucun secret NEWT/Twilio/SMTP/OAuth, Lookup dÃ©sactivÃ©, courriels en mÃ©moire, aucun worker externe ni poste tÃ©lÃ©phonique connectÃ©. Manifestes, identifiants, donnÃ©es et journaux restent hors Git. Voir [le guide de recette](DEMO_DATA.md) et le fichier privÃ© ACCES.txt.

Validation : cinq tests dÃ©diÃ©s dont recette rÃ©elle PostgreSQL 18 Ã  120 prospects par espace, reprise refusÃ©e, intÃ©gritÃ© des liens, rÃ´les, scÃ©narios et environnement. Suite core : 241 tests dont 19 ignorÃ©s ; portail complet : 221 tests dont 11 ignorÃ©s ; typage et build Vue rÃ©ussis, avertissement bundle >500 kB conservÃ©. Dix-huit lectures HTTP rÃ©ussies via le proxy dÃ©mo couvrent connexion, tableaux de bord et listes des cinq rÃ´les sur le jeu volumineux. La CI PostgreSQL 17 rejoue le gÃ©nÃ©rateur. Revue visuelle Ã  faire ; aucun appel, message ou rendez-vous externe rÃ©el lancÃ©.

Limites : donnÃ©es synthÃ©tiques relatives Ã  la date de gÃ©nÃ©ration, pas une simulation de fournisseur ni un test de charge concurrent. Aucun transfert des fichiers SQLite habituels, aucune bascule. Prochain lot : rÃ©pÃ©tition du transfert de copies SQLite vers une autre cible commune, comparaison des donnÃ©es puis sauvegarde/restauration avant de considÃ©rer une bascule.

## Base commune â€” cible PostgreSQL jetable et sÃ©paration des schÃ©mas

La commande `scripts/crm_common_db.py` crÃ©e une nouvelle base de recette locale et trois schÃ©mas avec rÃ´les distincts et mots de passe alÃ©atoires conservÃ©s hors Git. Toute base/rÃ´le existant, destination non privÃ©e, rÃ©utilisation ou nom hors prÃ©fixe de recette est refusÃ©. Les services peuvent sÃ©lectionner explicitement leur schÃ©ma PostgreSQL via `CRM_DB_SCHEMA`, validÃ© contre leur identitÃ© ; la configuration actuelle sans ce rÃ©glage est inchangÃ©e. Les privilÃ¨ges publics de connexion, crÃ©ation de schÃ©ma et tables temporaires sont retirÃ©s sur cette cible.

Validation : cinq tests, dont une recette PostgreSQL 18 rÃ©elle avec les migrations des trois services dans une base unique, sÃ©quences et opÃ©rations locales, refus de lecture/Ã©criture/crÃ©ation interschÃ©mas, crÃ©ations publiques/temporaires, rÃ´les et bases. Suite core : 236 tests, dont 18 ignorÃ©s ; contrÃ´les de schÃ©ma et absence de modification des sources. Recette PostgreSQL 17 ajoutÃ©e Ã  la CI. Aucun appel, message ni fournisseur sollicitÃ© ; aucun service CRM courant arrÃªtÃ©.

Limites : cible vide uniquement ; donnÃ©es existantes non transfÃ©rÃ©es, bases courantes inchangÃ©es. RÃ´les de recette autorisÃ©s Ã  migrer leur propre schÃ©ma, sans sÃ©paration migrateur/applicatif de production. Import, comparaison des donnÃ©es, rÃ©fÃ©rences polymorphes, sauvegarde/restauration commune et bascule restent Ã  rÃ©aliser. Voir [le plan](DATABASE_CENTRALIZATION.md). Prochain lot demandÃ© : gros jeu de donnÃ©es fictives cohÃ©rent dans les deux espaces de recette, avec rendez-vous, rappels, rÃ©sultats et comptes par rÃ´le, sans connexion fournisseur rÃ©elle.

## PrÃ©paration de la base commune â€” audit SQLite en lecture seule

Un nouvel outil `scripts/crm_db_audit.py` contrÃ´le les trois sources locales sans les modifier : intÃ©gritÃ© et clÃ©s Ã©trangÃ¨res, inventaire et empreintes de structure, migrations attendues, rÃ©fÃ©rences aux identitÃ©s centrales et sources mÃ©tier des appels/calendriers selon lâ€™espace. Les rÃ©fÃ©rences sans clÃ© Ã©trangÃ¨re sont classÃ©es explicitement ; les exclusions polymorphes restent signalÃ©es comme non vÃ©rifiÃ©es. Un rapport agrÃ©gÃ© hors Git expose les blocages sans lignes mÃ©tier ni secrets. Refus des sources absentes/identiques, des liens et de tout Ã©crasement. Codes 0 (pÃ©rimÃ¨tre contrÃ´lÃ© sans problÃ¨me), 2 (blocages avec rapport), 1 (audit impossible). `migration_ready` reste toujours false, mÃªme avec la dÃ©claration opÃ©rateur `--quiesced`.

Lâ€™audit local du 22 octobre compte 22 tables portail, 29 Assurance et 33 Isolation ; 36 contrÃ´les dâ€™identitÃ©s et deux contrÃ´les de sources, sans blocage dÃ©tectÃ© dans ce pÃ©rimÃ¨tre. Neuf noms de tables sont communs Ã  plusieurs bases et doivent conserver leurs copies distinctes. Les services sont restÃ©s actifs : les instantanÃ©s sont cohÃ©rents sÃ©parÃ©ment, sans transaction commune. Aucune copie vers PostgreSQL ni bascule effectuÃ©e ; les trois bases actuelles restent distinctes.

Le [plan de centralisation](DATABASE_CENTRALIZATION.md) dÃ©crit la cible proposÃ©e : une base PostgreSQL, trois schÃ©mas et rÃ´les distincts, portail comme autoritÃ© dâ€™identitÃ©, conservation des identifiants et historiques. La configuration, le transfert, les contrÃ´les PostgreSQL, les rÃ©fÃ©rences polymorphes/JSON, les mÃ©dias et la restauration restent Ã  rÃ©aliser et Ã  Ã©prouver avant migration.

Validation : huit tests dÃ©diÃ©s ; suite core complÃ¨te de 231 tests rÃ©ussie, dont 17 ignorÃ©s. ContrÃ´les WAL, intÃ©gritÃ©, absence de fuite des valeurs et refus dâ€™Ã©crasement couverts. Aucun appel, accÃ¨s fournisseur, arrÃªt de service ou changement de configuration. Prochain lot : prÃ©parer une cible PostgreSQL isolÃ©e pour rÃ©pÃ©ter la centralisation et vÃ©rifier les permissions avant toute bascule.

## Historique Phonetico en fiche â€” consultation sortante filtrÃ©e

Les fiches Setter Assurance (Appel et rappels et activitÃ© du dossier) et Isolation (Fiche et suivi) proposent une consultation manuelle du journal Phonetico. Choix de sept dates maximum sans futur, en heure de MontrÃ©al, pagination de 25 lignes, date/heure locale et durÃ©e brute. Aucune lecture automatique au montage, aucun appel, ni commande dâ€™enregistrement/DTMF/raccrochage. Le journal fournisseur reste distinct des dÃ©clarations du setter, sans conversion en humain dÃ©crochÃ©, validitÃ© de ligne ou rÃ©sultat commercial. Lâ€™unitÃ© de Duration nâ€™Ã©tant pas confirmÃ©e, elle reste explicitement brute.

La fiche mÃ©tier Ã©met une preuve de lecture de 60 secondes, signÃ©e pour le setter, lâ€™espace, la ressource, la rÃ©vision et le numÃ©ro actuel normalisÃ©. Cette preuve ne peut pas autoriser un appel. Le portail exige un setter actif et prend son poste dans lâ€™association centrale, pas dans une saisie navigateur. Les API mÃ©tier vÃ©rifient lâ€™accÃ¨s avant et aprÃ¨s lecture fournisseur ; une fiche modifiÃ©e ou rÃ©attribuÃ©e pendant la lecture refuse la rÃ©ponse. En Assurance, le pÃ©rimÃ¨tre de contacts reste la liste partagÃ©e existante des setters, mais chaque compte consulte uniquement les lignes de son propre poste. En Isolation, lâ€™affectation du prospect est nÃ©cessaire. Conseillers, closers, clients et administrateurs nâ€™utilisent pas cet historique personnel.

Le rapprochement accepte seulement From Ã©gal au poste courant et To Ã©gal au numÃ©ro actuel de la fiche au format nord-amÃ©ricain. Il exclut les lignes hors dates, antÃ©rieures Ã  la derniÃ¨re association du poste, les dates sans instant interprÃ©table et les autres postes/numÃ©ros. Cela Ã©vite de livrer les appels dâ€™un ancien titulaire du poste. Les fiches ayant le mÃªme numÃ©ro peuvent correspondre aux mÃªmes lignes : il sâ€™agit dâ€™un rapprochement par poste/numÃ©ro, pas dâ€™une preuve de campagne dâ€™origine. Aucun rapprochement entrant ou avec un ancien numÃ©ro de fiche nâ€™est inventÃ©. Les heures rÃ©pÃ©tÃ©es/inexistantes au changement dâ€™heure ne sont pas devinÃ©es.

La lecture 511 reste bornÃ©e et Ã  hÃ´te/fonction fixes, HTTPS sans redirection, 1 Mio et 10 000 lignes maximum ; filtrage avant pagination. Aucun rapport global, description, DNID, montant ou numÃ©ro tiers nâ€™est renvoyÃ© ou persistÃ©. Lâ€™audit conserve uniquement ressource, dates, nombre de lignes rapprochÃ©es et page. Les erreurs fournisseur restent indisponibles, pas des historiques vides rÃ©ussis. Quota existant de cinq lectures/minute par utilisateur et verrou global NEWT conservÃ©s. Le flag serveur NEWT_CDR_HISTORY_ENABLED, indÃ©pendant des appels et du diagnostic, est false par dÃ©faut, documentÃ© dans .env.example et transmis par le compose CRM. Aucune configuration locale ou secret nâ€™a Ã©tÃ© modifiÃ© ni recette rÃ©elle effectuÃ©e.

Validation : portail identitÃ© complet 221 tests (210 rÃ©ussis, 11 ignorÃ©s), core complet 223 tests (206 rÃ©ussis, 17 ignorÃ©s), 14 tests Assurance ciblÃ©s historique/commandes/interactions, 5 tests frontend historique/commandes. ContrÃ´les double autorisation, suppression aprÃ¨s rÃ©vocation, poste/numÃ©ro, association temporelle, pagination, dates, erreurs, preuves distinctes, CSRF et pÃ©rimÃ¨tres. Typage Vue et build production rÃ©ussis ; aucune migration manquante dans les trois services. Aucun appel ni lecture de journal rÃ©el. Revue visuelle en attente, navigateur Work dÃ©sactivÃ© ; avertissement Vite >500 kB conservÃ©.

Limites : lecture non persistÃ©e et opt-in serveur ; la recette NEWT 511 rÃ©elle reste Ã  effectuer aprÃ¨s activation de ce rÃ©glage. Pas de son navigateur, dâ€™auto-answer ni de rapprochement de campagne/commande unique (le journal confirmÃ© ne fournit pas dâ€™identifiant suffisant). Les dates antÃ©rieures Ã  une rÃ©association sont volontairement exclues. La pÃ©riode affichÃ©e est rechargÃ©e Ã  chaque page et peut Ã©voluer chez le fournisseur. Prochain lot : prÃ©parer la centralisation physique des bases avec inventaire des liens et contrÃ´les de migration avant toute bascule.

## PrÃ©cisions Phonetico : contrat 244/245/511 confirmÃ©

La rÃ©ponse du support fournie par lâ€™utilisateur confirme : 245 appelle dâ€™abord le poste, puis compose le numÃ©ro extÃ©rieur aprÃ¨s rÃ©ponse ; Success confirme cette Ã©tape et non le dÃ©crochage du destinataire, Failure signale lâ€™Ã©chec du rappel au poste (support : dÃ©lai par dÃ©faut de 20 secondes). Lâ€™adaptateur accepte dÃ©sormais le format confirmÃ© Success/Failure,poste,numÃ©ro avec champs suivants vides, en plus de lâ€™Ã©cho de corrÃ©lation dÃ©jÃ  supportÃ©. Poste et destination doivent correspondre exactement ; un Ã©cho non vide diffÃ©rent, des donnÃ©es supplÃ©mentaires ou une rÃ©ponse malformÃ©e restent indÃ©terminÃ©s. La commande conserve son transport HTTPS bornÃ©, sa prÃ©vention des doublons, son timeout explicite existant et aucune relance automatique. Aucun changement nâ€™active les appels ni lâ€™auto-answer ; _a=Y nâ€™est pas envoyÃ©. Le support annonce travailler sur le dÃ©crochage automatique NEWT Desktop, mais le Â« now working properly Â» ne suffit pas Ã  attribuer ce correctif prÃ©cisÃ©ment au softphone et Ã  son audio.

244 : R = Ringing (sonnerie du poste), C = On Call (en communication), H = On Hold (en attente). Les observations affichent dÃ©sormais ces libellÃ©s confirmÃ©s ; elles ne prouvent ni humain au bout de la ligne ni validitÃ© du numÃ©ro. Une liste vide conserve disponibilitÃ© indÃ©terminÃ©e.

511 : en-tÃªte confirmÃ© From, To, Description, DNID, Date, Time, Duration, Amount. Le diagnostic administratif reconnaÃ®t cet en-tÃªte exact (aprÃ¨s retrait dâ€™espaces de bord), conserve le diagnostic sans donnÃ©es dâ€™appel et annonce le fuseau America/Toronto. Lâ€™adaptateur de lecture peut dÃ©coder ce CSV avec guillemets/accents et convertir les dates locales en UTC en appliquant les dÃ©calages saisonniers MontrÃ©al ; une heure ambiguÃ«/inexistante ou une date invalide reste sans instant dÃ©duit. Duration et Amount restent des valeurs brutes : le support nâ€™a prÃ©cisÃ© ni unitÃ© ni sÃ©mantique et aucune preuve de dÃ©crochage nâ€™en est dÃ©duite. Les rapports avec colonnes diffÃ©rentes restent non reconnus pour le mapping.

Validation : suite portail identitÃ© complÃ¨te 212 tests, 201 rÃ©ussis et 11 ignorÃ©s selon lâ€™environnement ; 3 tests frontend des commandes dâ€™appel, typage Vue et build production. Tests des rÃ©ponses 245 confirmÃ©es et incohÃ©rentes, du CSV, des dÃ©calages saisonniers et des limites dâ€™infÃ©rence. Aucun appel, aucun accÃ¨s NEWT rÃ©el, aucune lecture de journal rÃ©el, aucune modification des secrets/configurations dâ€™activation. Pas de migration nÃ©cessaire. Revue visuelle en attente, navigateur Work dÃ©sactivÃ© ; avertissement Vite >500 kB conservÃ©.

Limites : cette livraison fiabilise le contrat fournisseur ; elle ne prÃ©tend pas livrer lâ€™historique mÃ©tier en fiche. La lecture filtrÃ©e par numÃ©ro/poste est dÃ©sormais livrÃ©e ci-dessus ; sa recette fournisseur rÃ©elle reste Ã  rÃ©aliser. Les variantes dâ€™en-tÃªte, la durÃ©e, les numÃ©ros entrants et la recette fournisseur rÃ©elle restent Ã  contrÃ´ler. Les fonctionnalitÃ©s dâ€™appel ne sont pas testÃ©es en rÃ©el sans nouvelle demande explicite.

## RÃ©sultats dâ€™appel dÃ©clarÃ©s et tÃ¢ches de rappel Isolation

Depuis Mes prospects Isolation â†’ Fiche, le panneau de droite propose les sept rÃ©sultats : rendez-vous pris, rÃ©pondeur, numÃ©ro invalide dÃ©clarÃ©, appel coupÃ©, pas intÃ©ressÃ©, rappel demandÃ© et injoignable, avec note facultative. Aucune saisie nâ€™appelle Phonetico/Twilio, nâ€™exÃ©cute Lookup ou ne modifie le numÃ©ro importÃ©, sa validitÃ© technique ou le statut commercial existant. Le rÃ©sultat reste une dÃ©claration datÃ©e et attribuÃ©e Ã  son auteur. Â« Rendez-vous pris Â» exige une visite existante non annulÃ©e du mÃªme prospect, autorisÃ©e pour le setter ; le bouton C2 ouvre le parcours de rÃ©servation existant, puis le setter actualise et lie sa rÃ©servation avant dâ€™enregistrer le rÃ©sultat. Aucun rendez-vous fictif nâ€™est crÃ©Ã© par la dÃ©claration.

Le rÃ©sultat Rappel demandÃ© exige date et heure et crÃ©e atomiquement une tÃ¢che. Un rappel manuel peut aussi Ãªtre crÃ©Ã© depuis toute fiche, sans rendez-vous. Les horaires se saisissent dans un fuseau canadien et sont convertis en instants explicites ; les heures ambiguÃ«s/inexistantes sont refusÃ©es. Les tÃ¢ches sont affichÃ©es en heure de MontrÃ©al, avec filtres ouverts, Ã  venir, en retard, terminÃ©s et tous, et pagination. Le setter courant et lâ€™administration peuvent modifier date/note dâ€™une tÃ¢che ouverte et la terminer avec rÃ©solution obligatoire, sous rÃ©vision. Chaque crÃ©ation, modification et clÃ´ture sâ€™ajoute Ã  lâ€™historique interne de la fiche et Ã  lâ€™audit. Les Ã©vÃ©nements dâ€™appel et de tÃ¢che ne sont pas publiables au client via le partage des observations existant.

Les tÃ¢ches suivent le prospect lors dâ€™une affectation : le nouveau setter les reprend, le prÃ©cÃ©dent perd lecture/Ã©criture, le crÃ©ateur et lâ€™historique restent conservÃ©s. La prochaine Ã©chÃ©ance ouverte alimente le repÃ¨re de rappel de la fiche ; les tÃ¢ches restent ouvertes jusquâ€™Ã  leur clÃ´ture, indÃ©pendamment dâ€™un changement de qualification commerciale. Les anciennes dates de rappel sont reprises par la migration sans inventer leur crÃ©ateur ni des notes. Les futures saisies de rappel via lâ€™ancienne qualification crÃ©ent aussi une tÃ¢che. Les compteurs et le filtre des prospects en rappel intÃ¨grent les tÃ¢ches en retard. Un onglet TÃ¢ches de rappel est disponible pour setter/administrateur Isolation ; clients et closers nâ€™y ont pas accÃ¨s.

Validation : suite core complÃ¨te, 221 tests exÃ©cutÃ©s dont 204 rÃ©ussis et 17 ignorÃ©s selon SQLite/Windows ; 8 tests frontend sur rÃ©sultat dÃ©clarÃ©, conversion horaire, erreur gardant la saisie, crÃ©ation manuelle, clÃ´ture et shell. VÃ©rifications des permissions, transferts, historique, migration, rÃ©servation autorisÃ©e, rÃ©pÃ©titions mÃªme aprÃ¨s lâ€™Ã©chÃ©ance et rollback transactionnel sur erreur dâ€™audit. Typage Vue, build production, diff et absence de migration manquante validÃ©s. Migration 0017 appliquÃ©e aprÃ¨s sauvegarde SQLite hors Git. Aucun appel, visite rÃ©elle, message ou notification externe lancÃ©. Revue visuelle Ã  faire, navigateur Work dÃ©sactivÃ© ; avertissement Vite >500 kB conservÃ©.

Limites : rÃ©sultats dÃ©clarÃ©s et tÃ¢ches internes, sans dÃ©tection automatique dâ€™appel ni notification externe. La clÃ´ture dâ€™une tÃ¢che ne rÃ©Ã©crit pas le statut commercial. Les statistiques de visites ne comptent pas ces tÃ¢ches comme rendez-vous. Les rÃ©servations restent dans le C2 ; lâ€™historique des commandes fournisseur nâ€™est pas encore fusionnÃ© Ã  cette chronologie. La fermeture du panneau protÃ¨ge les saisies ; enregistrer avant de changer de module. Historique Phonetico dÃ©sormais livrÃ© ci-dessus ; la centralisation physique de la base et la recette des connecteurs restent Ã  poursuivre.

## Performances Isolation par semaine, setter et closer

La page Statistiques propose une semaine (lundiâ€“dimanche) ou une pÃ©riode personnalisÃ©e de 366 jours maximum, avec choix du fuseau Toronto/MontrÃ©al, Vancouver, Halifax ou UTC. Les bornes correspondent aux jours locaux inclus et respectent les semaines de 167/169 heures au changement dâ€™heure. Lâ€™interface dÃ©marre sur la semaine courante Ã  MontrÃ©al ; les requÃªtes historiques sans fuseau conservent leur comportement UTC. Les filtres modifiÃ©s nâ€™altÃ¨rent pas un rapport dÃ©jÃ  affichÃ© : il faut recalculer ; pagination et tÃ©lÃ©chargements utilisent ensuite ses critÃ¨res appliquÃ©s.

Compteurs : rendez-vous rÃ©servÃ©s dans le pÃ©rimÃ¨tre, tenus, non tenus dÃ©clarÃ©s, ventes explicitement conclues, tenus sans vente conclue dÃ©clarÃ©e, tenus dont la vente reste non renseignÃ©e, rÃ©sultats de tenue manquants, annulations, Ã  venir et visites sans closer. Taux de prÃ©sence = tenus / rÃ©sultats de tenue renseignÃ©s. Taux de conclusion observÃ© = ventes conclues / rendez-vous tenus, y compris ceux dont la vente reste Ã  renseigner ; ces inconnus sont affichÃ©s sÃ©parÃ©ment et ne deviennent pas des ventes perdues. Aucun dÃ©nominateur donne Â« Non calculable Â». Exemple testÃ© : 20 rendez-vous, 15 tenus, 5 non tenus et 5 ventes donnent 75 % de prÃ©sence et 33,3 % de conclusion parmi les tenus.

Le client Isolation unique et lâ€™administration comparent les groupes paginÃ©s par setter dâ€™origine ou closer actuellement attribuÃ©, avec groupe Â« Non attribuÃ© Â». Les totaux portent sur toute la pÃ©riode, pas seulement la page. Une rÃ©attribution dÃ©place les visites et rÃ©sultats courants dans le groupe du nouveau closer ; lâ€™auteur historique du rÃ©sultat reste dans lâ€™audit. Ces rapports dÃ©crivent donc lâ€™Ã©tat actuel de la cohorte de rendez-vous, pas une photographie historique dâ€™effectif. Le setter conserve son pÃ©rimÃ¨tre existant (ses rÃ©servations dont il conserve le prospect). Le closer accÃ¨de Ã  ses statistiques personnelles depuis son espace, limitÃ©es Ã  ses visites actuellement attribuÃ©es, sans groupes ni noms de tiers. Les autres API restent fermÃ©es au closer.

Exports Excel et CSV : toutes les lignes du regroupement affichÃ© (limite 5 000 groupes), mÃªme au-delÃ  de la pagination ; feuille SynthÃ¨se puis Par setter ou Par closer, intitulÃ©s franÃ§ais, dates/fuseau et dÃ©finitions des calculs. Aucun tÃ©lÃ©phone, qualification personnelle ou note libre de prospect. Protection contre les formules dans les noms conservÃ©e, tÃ©lÃ©chargements auditÃ©s. Une semaine et des dates personnalisÃ©es simultanÃ©es, fuseau inconnu, groupe invalide et bornes hors limites sont refusÃ©s.

Validation : suite core complÃ¨te, 209 tests exÃ©cutÃ©s dont 192 rÃ©ussis et 17 ignorÃ©s selon SQLite/Windows ; 10 tests frontend (statistiques, export selon filtres appliquÃ©s, pagination, erreur sans anciennes donnÃ©es, rÃ©sultats closer et shell). Typage Vue, build production et absence de migration manquante validÃ©s. Aucune migration nÃ©cessaire pour ce lot, aucun appel ni rendez-vous rÃ©el crÃ©Ã©. Revue visuelle encore Ã  faire, navigateur Work dÃ©sactivÃ© ; avertissement Vite >500 kB conservÃ©.

Les rÃ©sultats dâ€™appel dÃ©clarÃ©s et rappels Isolation sont dÃ©sormais livrÃ©s ci-dessus. Restent lâ€™historique fournisseur, la centralisation physique de la base, la recette externe des connecteurs et la revue des interfaces avec lâ€™utilisateur.

## Espace closer Isolation, attribution et rÃ©sultats corrigibles

Le rÃ´le Closer est disponible dans lâ€™administration et les invitations Isolation, distinct du client Isolation unique. Son espace affiche uniquement ses visites attribuÃ©es, leur crÃ©neau/fuseau, le setter dâ€™origine, la copie C2 et le rÃ©sultat. Il nâ€™accÃ¨de ni Ã  la file gÃ©nÃ©rale des prospects, ni aux vÃ©rifications techniques, ni aux visites dâ€™un autre closer, ni aux API historiques client/setter. Aucun nouveau compte de recette nâ€™a Ã©tÃ© crÃ©Ã©.

Depuis une visite, le client autorisÃ© et lâ€™administrateur choisissent un closer actif dans lâ€™annuaire paginÃ© et motivent son attribution/rÃ©attribution. Une attestation signÃ©e de 120 secondes lie acteur, visite et closer ; la mutation du service Isolation vÃ©rifie aussi le pÃ©rimÃ¨tre et la rÃ©vision. Le nom est celui du compte authentifiÃ©, pas une identitÃ© libre saisie dans le rÃ©sultat. Une rÃ©attribution retire immÃ©diatement les prochaines lectures/Ã©critures du prÃ©cÃ©dent closer dans le service, tout en conservant le rÃ©sultat et son auteur historique. La contrainte du client Isolation unique reste inchangÃ©e.

AprÃ¨s la fin dâ€™une visite non annulÃ©e, le closer attribuÃ© dÃ©clare explicitement rendez-vous tenu Oui/Non et vente conclue Oui/Non, avec note facultative. Une vente conclue exige un rendez-vous tenu. Les anciens rÃ©sultats restent avec vente Non renseignÃ©e ; un ancien intÃ©rÃªt nâ€™est jamais transformÃ© en vente. Chaque correction exige la rÃ©vision et un motif, conserve avant/aprÃ¨s, auteur et date dans lâ€™audit, et reste consultable dans lâ€™historique du closer et lâ€™historique administrateur existant. Lâ€™idempotence empÃªche de dupliquer une mÃªme soumission. Le rÃ©sultat courant reste visible dans les parcours client et setter ; leurs droits existants sont conservÃ©s.

Validation : suites complÃ¨tes core (200 tests, 183 rÃ©ussis, 17 ignorÃ©s SQLite/Windows) et portail identitÃ© (206 tests, 195 rÃ©ussis, 11 ignorÃ©s selon lâ€™environnement), 12 tests frontend (saisie closer, erreur conservant le brouillon, qualification ancienne, C2/rÃ©servation et shell), typage Vue et build production. Migration 0016 appliquÃ©e aprÃ¨s sauvegarde SQLite hors Git, aucune migration manquante core/portail, diff sans erreur. Aucun appel, visite rÃ©elle, invitation ou message externe lancÃ©. Revue visuelle Ã  effectuer, accÃ¨s navigateur local dÃ©sactivÃ© dans Work ; avertissement Vite >500 kB conservÃ©.

Limites : le client/administrateur attribue aprÃ¨s rÃ©servation ; le setter ne choisit pas un closer Ã  la crÃ©ation. Lâ€™agenda externe reste celui du client Isolation configurÃ©, sans nouvelle synchronisation personnelle du closer. Les contrÃ´les dâ€™activation dâ€™un compte sont ceux des tickets existants Ã  expiration courte. Les ventilations closer, ventes et taux de conclusion sont dÃ©sormais livrÃ©s dans le lot de performances dÃ©crit ci-dessus. La base physique commune reste Ã  rÃ©aliser.

## Formulaire C2 Isolation et copie conservÃ©e Ã  la rÃ©servation

Depuis Mes prospects Isolation, lâ€™action calendrier ouvre Visites et formulaire C2 dans le panneau de droite. Le setter affectÃ© et lâ€™administrateur peuvent enregistrer un brouillon avec nom/prÃ©nom, tÃ©lÃ©phone, adresse, ville, code postal canadien, grenier accessible Oui/Non/Non renseignÃ©, coÃ»t mensuel dâ€™Ã©lectricitÃ© facultatif, annÃ©e de construction et Ã¢ge. La nouvelle rÃ©servation exige tous ces champs sauf lâ€™Ã©lectricitÃ© ; zÃ©ro et Non restent des rÃ©ponses explicites. ContrÃ´les : Ã¢ge 0â€“120, construction 1600â€“annÃ©e courante, Ã©lectricitÃ© positive ou nulle Ã  deux dÃ©cimales, syntaxe du tÃ©lÃ©phone et du code postal. Ce contrÃ´le de saisie ne prouve pas la joignabilitÃ© et ne dÃ©clenche pas Lookup.

La date et lâ€™heure se choisissent en heure locale avec durÃ©e et fuseau canadien. Les horaires ambigus ou inexistants sont refusÃ©s. La rÃ©servation attend lâ€™enregistrement du C2 et sa nouvelle rÃ©vision, puis conserve les preuves, contrÃ´les de disponibilitÃ©, attribution setter et campagne existants. Chaque visite reÃ§oit une copie C2 datÃ©e, visible dans le dÃ©tail pour le client autorisÃ© et le setter de son pÃ©rimÃ¨tre. Cette copie ne change pas lors dâ€™une modification du brouillon, dâ€™un report, dâ€™une annulation ou dâ€™une rÃ©pÃ©tition idempotente. Les anciennes visites conservent explicitement lâ€™absence de copie et restent reportables selon les droits existants.

Le brouillon reste interne au parcours Isolation ; lâ€™espace client accÃ¨de Ã  la copie via ses visites, pas au brouillon. Lâ€™API historique de vÃ©rification nâ€™expose pas ce nouveau champ et ne permet pas de contourner sa validation. Les rÃ©sultats techniques, le tÃ©lÃ©phone importÃ© et le statut commercial restent distincts des coordonnÃ©es dÃ©clarÃ©es dans le C2. Les Ã©critures utilisent la rÃ©vision du prospect et un audit transactionnel ; conflit ou rÃ©attribution refusent lâ€™Ã©crasement. La fermeture du panneau demande confirmation pour un C2 modifiÃ©, et un Ã©chec de sauvegarde conserve la saisie.

Validation : 192 tests backend exÃ©cutÃ©s, 175 rÃ©ussis et 17 ignorÃ©s selon lâ€™environnement SQLite/Windows ; contrÃ´les des droits, conflits, validation, copie, historique, rÃ©sultats client, statistiques et sauvegardes existantes. Les tests ont utilisÃ© un rÃ©pertoire temporaire dans private-media pour contourner les droits du rÃ©pertoire temporaire sandbox Windows. 13 tests frontend sur le C2, son enchaÃ®nement avec la rÃ©servation, le calendrier et le panneau ; typage Vue et build production rÃ©ussis. Migration 0015 appliquÃ©e localement aprÃ¨s sauvegarde SQLite hors Git, aucune migration manquante. Aucun appel ni visite rÃ©elle crÃ©Ã©. Revue visuelle en attente, navigateur local dÃ©sactivÃ© dans Work ; avertissement Vite de taille de bundle conservÃ©.

Limites : copie consultable dans le CRM, sans ajout dâ€™informations C2 dans Google/Microsoft ni envoi de message. Le brouillon ne remplace pas le tÃ©lÃ©phone importÃ© utilisÃ© par la vÃ©rification technique. La navigation vers un autre module nâ€™est pas bloquÃ©e par ce formulaire ; enregistrer le brouillon avant de changer de page. Pas de reprise fictive des anciennes visites. Les rÃ´les/rÃ©sultats closer, les ventes conclues, les statistiques Isolation demandÃ©es et la base physique commune restent Ã  livrer. Suivi closer dÃ©sormais livrÃ© ci-dessus ; statistiques hebdomadaires/ventes et base physique commune restent Ã  livrer.

## Statuts mÃ©tier des rendez-vous Assurance

Les listes, fiches et calendrier distinguent PlanifiÃ©, ReprogrammÃ©, Rendez-vous fait, Absent, Non effectuÃ© â€” autre motif, Ã€ renseigner et AnnulÃ©. Le rÃ©sultat rÃ©el prime sur un ancien report ; un rendez-vous passÃ© sans compte rendu reste Ã  renseigner. Le conseiller choisit explicitement le rÃ©sultat, sans prÃ©sÃ©lection de prÃ©sence. Toute absence ou non-rÃ©alisation exige une note et conserve le suivi existant. Les rÃ©sultats restent immuables et les rÃ©pÃ©titions identiques idempotentes ; les droits et contrÃ´les de rÃ©vision existants sont conservÃ©s.

Chaque report conserve un compteur et sa date, sans altÃ©rer la qualification transmise. La migration reprend uniquement les reports attestÃ©s par lâ€™audit ; les anciens comptes rendus nÃ©gatifs restent Â« autre motif Â», mÃªme si leur note Ã©voque une absence. Lâ€™historique du contact affiche lâ€™absence dÃ©clarÃ©e. Les statistiques et exports CSV/Excel ajoutent les absences dÃ©clarÃ©es et les autres non-effectuÃ©s, tout en conservant le total des non-effectuÃ©s. Les filtres mÃ©tier sont distincts du statut technique historique.

Validation : 44 tests backend sur les statuts, filtres, autorisations, rÃ©servations, comptes rendus, statistiques et exports ; contrÃ´les complÃ©mentaires de chronologie. 13 tests frontend, typage Vue et build production rÃ©ussis. Migration 0026 appliquÃ©e localement aprÃ¨s sauvegarde SQLite hors Git ; aucune migration manquante. Aucun appel ni rendez-vous rÃ©el crÃ©Ã©. Revue visuelle encore Ã  faire, accÃ¨s navigateur local dÃ©sactivÃ© dans Work. Avertissement de taille du bundle Vite conservÃ©.

Limites : Assurance uniquement. Les corrections dâ€™un compte rendu dÃ©jÃ  enregistrÃ© restent soumises au parcours dâ€™historique existant ; aucune rÃ©Ã©criture silencieuse. Le taux effectuÃ© existant garde son dÃ©nominateur des comptes rendus renseignÃ©s et ne prÃ©tend pas remplacer les futures statistiques Isolation. Formulaire C2 Isolation dÃ©sormais livrÃ© ci-dessus ; rÃ©sultats closer et statistiques demandÃ©es restent Ã  rÃ©aliser.

## Qualification Assurance dÃ©diÃ©e et copie transmise au conseiller

Le formulaire Assurance est distinct des champs personnalisables : Ã¢ge (0â€“120), profession et situation matrimoniale selon les choix demandÃ©s, enfants/propriÃ©taire/fumeur/conseiller existant avec Oui/Non/Non renseignÃ©, assurances multiples, notes complÃ©mentaires et notes utiles au conseiller. Nom/tÃ©lÃ©phone/courriel restent dans les coordonnÃ©es. Les rÃ©ponses inconnues ne sont pas converties en Non. Aucune assurance connue est exclusive des autres choix, les doublons et choix inconnus sont refusÃ©s. Les champs restent facultatifs tant quâ€™aucune rÃ¨gle mÃ©tier de complÃ©tude obligatoire nâ€™a Ã©tÃ© dÃ©finie ; un formulaire partiel est conservÃ© comme tel.

La qualification est enregistrÃ©e avec verrou et rÃ©vision de contact, audit et protection du brouillon. Passer Ã  la rÃ©servation ou la confirmer enregistre la qualification modifiÃ©e ; un Ã©chec bloque le parcours. Chaque nouvelle rÃ©servation conserve une copie datÃ©e des coordonnÃ©es et de tous les champs du formulaire. Le conseiller autorisÃ© la lit depuis son rendez-vous, ou la derniÃ¨re copie de ses propres rendez-vous depuis la fiche. Les notes internes et champs personnalisÃ©s non partagÃ©s ne sont jamais copiÃ©s. Une modification de fiche ultÃ©rieure ne change pas une transmission prÃ©cÃ©dente ; reports, annulations et rÃ©pÃ©titions idempotentes prÃ©servent la copie. Les anciens rendez-vous affichent explicitement lâ€™absence de copie, sans rÃ©cupÃ©ration rÃ©troactive du brouillon actuel.

Validation : 42 tests backend ciblÃ©s rÃ©ussis (qualification, pÃ©rimÃ¨tres conseiller, instantanÃ©, conflits, rÃ©servations, partages existants, contrÃ´les calendrier et rappels), 10 tests frontend rÃ©ussis (qualification, rÃ©sultat dâ€™appel, commandes et panneau), typage Vue et build production. Migration 0025 appliquÃ©e localement aprÃ¨s sauvegarde SQLite hors Git ; aucun schÃ©ma manquant dÃ©tectÃ©. Aucun appel, rendez-vous de recette, e-mail ni notification externe envoyÃ©. Revue visuelle Ã  faire : accÃ¨s navigateur local dÃ©sactivÃ© dans Work. Avertissement Vite de taille du bundle conservÃ© (>500 kB).

Limites : transmission dans lâ€™espace CRM du conseiller ; pas dâ€™envoi par courriel ni de copie des informations personnelles dans la description Google/Microsoft. Les synchronisations calendrier existantes conservent leur configuration et leur recette externe reste Ã  faire. Les statuts mÃ©tier de prÃ©sence/absence sont livrÃ©s ci-dessus ; le formulaire C2 Isolation reste Ã  rÃ©aliser. La plateforme nâ€™est pas encore centralisÃ©e dans une seule base physique.

## RÃ©sultats dâ€™appel et rappels indÃ©pendants dâ€™un rendez-vous â€” Assurance

La fiche Setter propose lâ€™onglet Appel et rappels : sept rÃ©sultats mÃ©tier avec note facultative, rappel datÃ© en heure de MontrÃ©al lorsque demandÃ©, crÃ©ation manuelle dâ€™un rappel Ã  tout moment. Â« Rendez-vous pris Â» ouvre la qualification existante ; le rÃ©sultat est enregistrÃ© aprÃ¨s la rÃ©servation effective et liÃ© Ã  ce rendez-vous. Si lâ€™enregistrement du rÃ©sultat Ã©choue aprÃ¨s rÃ©servation, retour sur sa saisie pour rÃ©essayer sans rÃ©server de nouveau. Ce parcours ne dÃ©clenche aucun appel et ne prÃ©tend pas dÃ©tecter le dÃ©crochage. Le numÃ©ro invalide dÃ©clarÃ© par le setter nâ€™Ã©crase pas Lookup.

Les rappels sans RDV et les suivis existants figurent ensemble dans Mes tÃ¢ches et dans lâ€™historique du contact. Le setter peut modifier note/prioritÃ©/date dâ€™une tÃ¢che ouverte de son pÃ©rimÃ¨tre et la terminer avec rÃ©solution. Les rappels Ã  venir et en retard, les notifications et la gÃ©nÃ©ration pÃ©riodique restent compatibles. Lâ€™historique conserve les rÃ©sultats et notes, les rappels et leur rÃ©solution ; les opÃ©rations sont auditÃ©es. Les rÃ©sultats dâ€™appel sont internes et propres au setter, lâ€™administration garde son accÃ¨s. Idempotence des crÃ©ations, verrou de fiche et rÃ©vision pour les Ã©critures, clÃ´ture et modifications contrÃ´lÃ©es.

Validation : 61 tests backend rÃ©ussis (5 tests PostgreSQL ignorÃ©s sur SQLite), 7 tests frontend rÃ©ussis, typage Vue, build production et absence de migration manquante. Migration 0024 appliquÃ©e localement aprÃ¨s sauvegarde SQLite dans private-media. Aucun appel, notification externe ou rendez-vous de recette lancÃ©. ContrÃ´le visuel non rÃ©alisÃ© sur ce lot : lâ€™accÃ¨s au navigateur local est dÃ©sactivÃ© dans les rÃ©glages Work. Le build Ã©met dÃ©sormais un avertissement de taille du bundle (>500 kB), sans erreur de compilation.

Limites du lot initial : Assurance ; qualification et partage ont depuis Ã©tÃ© ajoutÃ©s dans la livraison dÃ©crite ci-dessus. C2 Isolation, closer, statistiques supplÃ©mentaires et base commune restent Ã  rÃ©aliser. Les rÃ©sultats restent des dÃ©clarations et ne remplacent pas les Ã©tats fournisseur. Le rÃ©sultat RDV pris ouvre dÃ©sormais le formulaire Assurance dÃ©diÃ©. Lâ€™historique des commandes fournisseur nâ€™est pas encore fusionnÃ© Ã  cette chronologie. Les statistiques de rendez-vous restent un cohort de RDV et ne comptent pas les rappels indÃ©pendants ; le tableau des tÃ¢ches et le compteur de lâ€™accueil les incluent.

## Nouveau pÃ©rimÃ¨tre mÃ©tier â€” prÃ©cisions du 22 octobre 2026

Premier lot livrÃ© : rÃ©sultats dâ€™appel dÃ©clarÃ©s et rappels manuels Assurance. Les rÃ©sultats sont distincts des Ã©tats techniques Lookup/Phonetico. Les tÃ¢ches acceptent dÃ©sormais un contact sans rendez-vous ; les tÃ¢ches existantes liÃ©es Ã  un rendez-vous sont conservÃ©es.

Suivi des lots :
- Qualification Assurance dÃ©diÃ©e : livrÃ©e dans la section ci-dessus.
- Transmission contrÃ´lÃ©e au conseiller : livrÃ©e dans le CRM avec copie datÃ©e. PrÃ©sence/absence/annulation/report : livrÃ©s dans le lot des statuts mÃ©tier ci-dessus, avec les preuves et transitions autorisÃ©es.
- Formulaire Isolation C2 distinct : livrÃ© ci-dessus avec brouillon et copie datÃ©e Ã  la rÃ©servation.
- Espace et permissions closer Isolation : livrÃ©s ci-dessus, attribution contrÃ´lÃ©e et rÃ©sultats corrigibles avec historique.
- Statistiques Isolation par semaine/pÃ©riode, setter et closer : livrÃ©es ci-dessus avec compteurs explicites, inconnus sÃ©parÃ©s, taux et exports. Exemple 5/15 = 33,3 %.
- Centralisation physique : les services utilisent actuellement des bases distinctes (portail, Assurance, Isolation). PrÃ©parer puis vÃ©rifier une migration vers une base commune en prÃ©servant identitÃ©s, liens, donnÃ©es et pÃ©rimÃ¨tres. Ce point nâ€™est pas livrÃ©.
- RÃ©sultats dâ€™appels et rappels Isolation : livrÃ©s ci-dessus. ComplÃ©ter ensuite la chronologie des commandes dâ€™appel fournisseur. Les campagnes silencieuses restent dÃ©sactivÃ©es et aucun appel de recette nâ€™est autorisÃ© par cette Ã©volution.


## Tableau des tÃ¢ches Setter Assurance

Page Mes tÃ¢ches reprise selon la rÃ©fÃ©rence : trois colonnes Ã€ traiter, En retard et ClÃ´turÃ©es, cartes sans photos avec prospect, prioritÃ© en franÃ§ais, Ã©chÃ©ance, signalement et rendez-vous source. DÃ©filement interne par colonne et chargement de 25 cartes supplÃ©mentaires. Panneau bleu dâ€™avancement calculÃ© sur les tÃ¢ches visibles selon les filtres, volumes par prioritÃ© et accÃ¨s aux rendez-vous. Aucun statut Â« en cours Â» ni pourcentage dâ€™avancement par tÃ¢che inventÃ© ; une tÃ¢che reste ouverte jusquâ€™Ã  sa clÃ´ture justifiÃ©e.

Le dÃ©tail sâ€™ouvre Ã  droite avec le motif complet, le dernier signalement et la rÃ©solution conservÃ©e. ClÃ´ture avec rÃ©vision et justification obligatoire, confirmation visuelle, actualisation du tableau et protection du brouillon Ã  la fermeture. Recherche serveur par prospect/motif et filtre de prioritÃ© appliquÃ©s Ã  toutes les colonnes et au rÃ©sumÃ©. Compteurs calculÃ©s sur lâ€™ensemble des rÃ©sultats, indÃ©pendamment des pages de cartes. Les rÃ¨gles, rÃ©attributions et rÃ©ouvertures administrateur restent dans leur parcours existant.

Validation : 18 tests backend rÃ©ussis sur le tableau et les opÃ©rations de tÃ¢ches ; 3 tests de concurrence rÃ©servÃ©s Ã  PostgreSQL ignorÃ©s sur SQLite. ContrÃ´les des pÃ©rimÃ¨tres setter, des colonnes exclusives, des filtres, de la pagination et de la clÃ´ture. Typage Vue, build production et revue navigateur bureau/mobile avec filtre de prioritÃ©. Le compte de revue ne contient aucune tÃ¢che : les cas renseignÃ©s et la clÃ´ture sont vÃ©rifiÃ©s dans la base de tests uniquement. Aucun appel, rendez-vous, tÃ¢che ou message rÃ©el crÃ©Ã© pour la revue.

Limites : prÃ©sentation Setter Assurance uniquement ; Isolation nâ€™a pas de module de tÃ¢ches Ã©quivalent livrÃ© ici. Pas de crÃ©ation manuelle ni de glisser-dÃ©poser : les tÃ¢ches restent gÃ©nÃ©rÃ©es par les suivis de rendez-vous existants et changent de colonne selon leur Ã©chÃ©ance ou leur clÃ´ture. Les compteurs sont rafraÃ®chis Ã  la demande et aprÃ¨s clÃ´ture. La prochaine reprise demandÃ©e par lâ€™utilisateur concerne le panneau des prospects ; recette globale et revue administrateur restent Ã  poursuivre.

## Calendrier mensuel Setter Assurance et Isolation

La page Rendez-vous/Visites Setter reprend la rÃ©fÃ©rence fournie : grille lundi-dimanche, navigation mensuelle, retour Ã  aujourdâ€™hui, repÃ¨res corail, cartes pastel, recherche locale, filtre de statut et choix du fuseau canadien. Un clic sur un Ã©vÃ©nement ouvre son dÃ©tail dans le panneau commun Ã  droite ; au-delÃ  de trois Ã©vÃ©nements par jour, Â« autres Â» ouvre la liste complÃ¨te. Les reports/annulations continuent dâ€™utiliser les commandes existantes, avec motif, rÃ©vision et contrÃ´les dâ€™accÃ¨s. Le report Assurance dispose de champs de date/heure locale et refuse les horaires ambigus ou inexistants. Le bouton RÃ©server guide vers la fiche prospect pour conserver le choix du conseiller et les contrÃ´les mÃ©tier.

Les API Assurance et Isolation acceptent une fenÃªtre de chevauchement bornÃ©e Ã  62 jours avec instants explicites. Le calendrier charge toutes les pages du crÃ©neau affichÃ© ; une erreur nâ€™est pas prÃ©sentÃ©e comme un calendrier partiel complet. Une ancienne rÃ©ponse ne remplace pas le mois courant. Les Ã©vÃ©nements de plusieurs jours et ceux se terminant Ã  minuit sont rÃ©partis selon le fuseau affichÃ©. Les pÃ©rimÃ¨tres de visibilitÃ© restent appliquÃ©s avant filtrage.

Validation : 15 tests de rendez-vous Assurance, 12 de visites Isolation et 8 tests frontend (dates, heure dâ€™Ã©tÃ©/hiver, chevauchements, chargement de 60 Ã©vÃ©nements paginÃ©s, rÃ©ponse pÃ©rimÃ©e, erreur et panneau latÃ©ral), typage Vue, build production. Revue navigateur Assurance/Isolation, mois suivant/aujourdâ€™hui, journÃ©e vide, entrÃ©e de rÃ©servation et prÃ©sentation mobile. Aucun appel ni rendez-vous rÃ©el crÃ©Ã©. Le compte de revue nâ€™a pas de rendez-vous ; la rÃ©partition des Ã©vÃ©nements et leur pagination sont couvertes par les donnÃ©es synthÃ©tiques des tests, pas par une rÃ©servation de recette.

Limites : ce nouveau calendrier concerne le rÃ´le Setter ; les parcours administrateur, conseiller et client restent conservÃ©s. Il affiche les rendez-vous internes, sans prÃ©tendre afficher les occupations externes Google/Microsoft ; leur contrÃ´le reste celui de la rÃ©servation existante. Recherche limitÃ©e au crÃ©neau chargÃ©. Pas de dÃ©placement par glisser-dÃ©poser. La rÃ©servation complÃ¨te depuis le calendrier reste orientÃ©e vers la fiche prospect ; recette externe et autres pages Ã  revoir avec lâ€™utilisateur.

## Accueil Setter : cartes pastel et vue opÃ©rationnelle

Refonte de lâ€™accueil Setter Assurance et Isolation suivant la rÃ©fÃ©rence fournie : fond doux, grandes cartes pÃªche/bleu/lilas, commandes noires arrondies, raccourci violet et panneaux plus lÃ©gers. Navigation AMX conservÃ©e. Les cartes ouvrent les prospects, les tÃ¢ches/rappels et lâ€™agenda. Les trois prochains rendez-vous disponibles sont affichÃ©s avec date, fuseau et statut ; les rappels et notifications restent accessibles dans leur volet dÃ©pliable.

Assurance : graphique alimentÃ© par lâ€™API de statistiques existante, sur les 30 derniers jours selon la date du rendez-vous en UTC, avec volumes effectuÃ©s/non effectuÃ©s/annulÃ©s/Ã  venir et nombre de comptes rendus. Aucune tendance, mesure IA ou donnÃ©e inventÃ©e. Les rendez-vous passÃ©s sans compte rendu ne sont pas assimilÃ©s Ã  des rendez-vous effectuÃ©s. Isolation conserve ses indicateurs disponibles et son agenda sans graphique Assurance. Chargement, absence de donnÃ©es et erreurs avec relance sont distinguÃ©s.

Validation : typage Vue et build production, contrÃ´le visuel bureau et mobile sur le compte Setter local. Aucun appel, rendez-vous ou message rÃ©el envoyÃ©. Les accueils administrateur/conseiller/client ne sont pas modifiÃ©s. La recette mÃ©tier globale et la reprise des autres pages restent Ã  rÃ©aliser suivant les retours de lâ€™utilisateur.

## Panneau latÃ©ral commun et fiche prospect guidÃ©e

Composant SidePanel rÃ©utilisable pour les futures fiches/formulaires : ouverture Ã  droite, contexte de page visible, en-tÃªte et actions fixes, fermeture contrÃ´lÃ©e et Ã‰chap protÃ©gÃ© pendant les opÃ©rations, dÃ©filement interne, format mobile et animation rÃ©duite selon les prÃ©fÃ©rences. La fiche prospect utilise trois onglets CoordonnÃ©es, Qualification et Rendez-vous ; les saisies restent montÃ©es pendant les changements dâ€™onglet. Les champs complÃ©mentaires vides et lâ€™historique de rendez-vous vide ne prennent plus de place. Sans conseiller attribuÃ©, un encart remplace le formulaire de rÃ©servation inutilisable. Une fermeture avec note, document ou qualification non enregistrÃ©s propose de rester ou dâ€™abandonner ces saisies.

Validation ciblÃ©e : typage Vue, tests du cycle ouverture/fermeture du panneau et des commandes dâ€™appel, revue visuelle navigateur et abandon dâ€™un brouillon local non enregistrÃ©. Aucun appel ni rendez-vous rÃ©el dÃ©clenchÃ©. La recette mÃ©tier globale reste reportÃ©e ; les autres modales seront reprises page par page suivant ce modÃ¨le (docs/UI_PATTERNS.md).

## Filtre de statut prospects

Suppression du double encadrement causÃ© par les styles globaux du sÃ©lecteur. Une seule bordure, flÃ¨che alignÃ©e Ã  droite et indicateur de focus autour du contrÃ´le complet. ContrÃ´le du diff effectuÃ© ; recette approfondie reportÃ©e.

## Quatre prospects par ligne

Lorsquâ€™un seul statut est visible, sa grille affiche quatre cartes par ligne sur grand Ã©cran (>1200 px), trois jusquâ€™Ã  1200 px, deux jusquâ€™Ã  1000 px et une jusquâ€™Ã  600 px pour prÃ©server la lisibilitÃ©. ContrÃ´le du diff effectuÃ© ; recette approfondie reportÃ©e.

## Largeur adaptative des cartes prospects

Les statuts visibles occupent la largeur disponible. Lorsquâ€™un seul statut est visible, ses cartes se rÃ©partissent horizontalement dans une grille adaptative, puis passent Ã  la ligne ; sur mobile elles restent en une colonne. Le dÃ©filement et le chargement par lots de 25 sont conservÃ©s. Recette approfondie toujours reportÃ©e.

## Colonnes prospects vides masquÃ©es

Les colonnes sans prospect ne sâ€™affichent plus. Tous les statuts restent sÃ©lectionnables dans le filtre et disponibles dans la fiche. Les erreurs de chargement restent visibles pour permettre de rÃ©essayer ; une recherche sans rÃ©sultat affiche un message unique. Recette approfondie toujours reportÃ©e Ã  la demande de lâ€™utilisateur.

## Prospects Setter Assurance : colonnes et fiche modale

Prospects prÃ©sentÃ© en cartes sans photos, groupÃ©es par les statuts configurÃ©s, avec recherche, filtre et pagination par colonne. Actions Modifier et PrÃ©parer lâ€™appel Ã  cÃ´tÃ© de chaque numÃ©ro. La modale prend automatiquement la fiche en charge, conserve la sauvegarde et la libÃ©ration du verrou, et ouvre la rÃ©servation avec choix parmi les conseillers attribuÃ©s, date/heure locale, durÃ©e et fuseau. Les heures inexistantes ou ambiguÃ«s du changement dâ€™heure sont refusÃ©es ; les conflits dâ€™agenda restent contrÃ´lÃ©s par le serveur. Le mode appel ouvre la prÃ©paration existante et exige une confirmation avant envoi ; aucun appel nâ€™est lancÃ© automatiquement. La modale reste disponible pour saisir les informations pendant lâ€™Ã©change, sans prÃ©tendre dÃ©tecter sonnerie ou dÃ©crochage.

Limites : cette reprise concerne Assurance ; Isolation conserve son parcours. Le compte setter.visite nâ€™a aucun conseiller attribuÃ© et ne peut pas rÃ©server tant que cette attribution nâ€™est pas configurÃ©e. La publication Google/Microsoft nÃ©cessite les connexions et rÃ©glages de synchronisation existants. Aucun appel ni rendez-vous rÃ©el crÃ©Ã©. VÃ©rifications approfondies et recette de bout en bout reportÃ©es Ã  la demande de lâ€™utilisateur ; contrÃ´le de compilation uniquement pour garder la page ouvrable.

## Accueil Setter : prÃ©sentation et accÃ¨s directs

Conversations retirÃ© du menu et de lâ€™en-tÃªte Setter. Accueil dÃ©diÃ© aux setters Assurance et Isolation : bienvenue, cartes pastel avec indicateurs rÃ©els et liens vers prospects/tÃ¢ches, prochain crÃ©neau, actions principales et agenda. Les rappels et notifications Assurance restent disponibles dans un volet repliable. Les autres rÃ´les conservent leur accueil. VÃ©rifications : connexion et accÃ¨s aux prospects dans le navigateur, ouverture des suivis, revue desktop/mobile, typage et build, tests des espaces. Aucun appel ni envoi de message dÃ©clenchÃ©. La prochaine page attend le retour de lâ€™utilisateur.

## Couleur du bloc logo Setter

Fond du logo AMX alignÃ© sur le bleu nuit de la barre latÃ©rale (#112330), texte blanc et sous-titre Ã©clairci. Sur ordinateur, le bloc occupe exactement la largeur du menu (248 px) et toute la hauteur de lâ€™en-tÃªte. La version mobile conserve un bloc compact.

## Cadre de navigation Setter selon la rÃ©fÃ©rence utilisateur

Barre blanche sur toute la largeur avec marque AMX, accÃ¨s Ã  la liste des prospects, raccourci vers les tÃ¢ches et profil. Menu bleu nuit, sÃ©lection bleue, statistiques sÃ©parÃ©es ; menu mobile et choix dâ€™espace dans le profil uniquement pour les comptes ayant plusieurs accÃ¨s. Appels, conversations et aide sans page dÃ©diÃ©e restent dÃ©sactivÃ©s et explicitÃ©s par leurs libellÃ©s. Aucun compteur fictif ni appel dÃ©clenchÃ©. Les interfaces des autres rÃ´les et le contenu des pages ne sont pas refondus par ce lot. Connexion Setter et rendu desktop contrÃ´lÃ©s dans le navigateur local ; typage, build et tests des espaces contrÃ´lÃ©s. La suite attend la validation de lâ€™utilisateur, page par page.

## Administration : parcours des invitations

Formulaire ouvert Ã  la demande, annulation avec effacement des champs, rÃ´les traduits, badges dâ€™Ã©tat et actions avec icÃ´nes et libellÃ©s accessibles. Actualisation, Ã©tats vide/erreur/chargement et pagination bloquÃ©e pendant les requÃªtes. Les messages distinguent lâ€™enregistrement de la mise en file dâ€™envoi ; aucune garantie de rÃ©ception nâ€™est affichÃ©e. Aucun e-mail de recette envoyÃ©. Revue visuelle et test rÃ©el dâ€™envoi restant Ã  effectuer. Prochaine reprise : attribution des postes tÃ©lÃ©phoniques.

## Administration : organisation des utilisateurs et accÃ¨s

SÃ©paration en rubriques Utilisateurs, Invitations, Postes tÃ©lÃ©phoniques et Journal des accÃ¨s. Une seule rubrique est montÃ©e Ã  la fois ; les modules annexes ne sont plus chargÃ©s systÃ©matiquement sous la liste. Le sÃ©lecteur dâ€™espace reste commun et limitÃ© aux espaces administrÃ©s. En-tÃªte unique, barre de recherche, tableau et badges harmonisÃ©s. CrÃ©ation, association, modification des rÃ´les et suspension conservent leurs contrÃ´les existants. Les formulaires internes des invitations/postes et les autres paramÃ¨tres restent Ã  revoir ; la refonte globale de lâ€™administration nâ€™est pas dÃ©clarÃ©e terminÃ©e. Validation visuelle rÃ©elle restant Ã  effectuer.

## Refonte de lâ€™Ã©cran OpportunitÃ©s Assurance

En-tÃªte compact sans titres englobants en double, contexte Assurance et compteur global signalant les rÃ©sultats partiels en cas dâ€™erreur. Colonnes Ã  dÃ©filement vertical indÃ©pendant dans un tableau Ã  dÃ©filement horizontal accessible au clavier ; cartes compactes et ouverture de fiche protÃ©gÃ©e des clics simultanÃ©s. Recherche serveur et pagination par Ã©tape conservÃ©es. Aucun glisser-dÃ©poser ni appel ajoutÃ©. Revue visuelle rÃ©elle restant Ã  effectuer, lâ€™accÃ¨s navigateur Work Ã©tant dÃ©sactivÃ© lors de cette livraison. Ã€ poursuivre : refonte de lâ€™administration (utilisateurs, accÃ¨s et paramÃ¨tres), puis revue globale des Ã©crans restants.

## Refonte de la liste Contacts Assurance

En-tÃªte compact propre Ã  Contacts, suppression des titres et cartes englobantes en double, onglet de liste, barre dâ€™actions avec recherche et actualisation, compteur et tableau plus dense. Le filtre de statut passe dans un panneau latÃ©ral modal natif avec application explicite, annulation et retrait du filtre actif. Import et fiche contact restent accessibles avec leurs permissions existantes. Ce lot concerne Contacts Assurance, pas lâ€™ensemble des Ã©crans CRM. Validation visuelle dans le navigateur non rÃ©alisÃ©e : lâ€™accÃ¨s local au navigateur est dÃ©sactivÃ© dans les rÃ©glages Work.

## Vue OpportunitÃ©s Assurance

Tableau en colonnes suivant les statuts commerciaux configurÃ©s, y compris les Ã©tapes archivÃ©es. Recherche serveur commune, compteurs par Ã©tape et pagination indÃ©pendante de 25 contacts avec Â« Afficher plus Â». Les cartes ouvrent la fiche existante : les changements de statut conservent sa prise en charge, sa justification et ses contrÃ´les de version. Les permissions restent celles des contacts (dont le pÃ©rimÃ¨tre conseiller). Aucun montant, glisser-dÃ©poser ou changement automatique de statut. Les colonnes se chargent avec trois requÃªtes simultanÃ©es maximum et prÃ©sentent leurs erreurs individuellement. Validation : typage et build frontend ; revue visuelle navigateur non rÃ©alisÃ©e.

Une fonctionnalitÃ© est terminÃ©e aprÃ¨s vÃ©rification, commit, push, PR et fusion dans main. Le cahier des charges mÃ©tier est CRM_AMX_Cahier_des_charges.docx du 18 octobre 2026.

## Correctifs CallVerify livrÃ©s

- PR 4 : nombres Excel avec suffixe .0, premiÃ¨re ligne sans en-tÃªte, diagnostic des campagnes sans numÃ©ro exploitable, Ã©tat de ligne principal, badges, exports et sÃ©paration du rÃ©sultat Basic.

## FonctionnalitÃ© 37 â€” parcours Qualification intÃ©grÃ© Ã  Isolation

Depuis lâ€™espace Isolation du portail CRM, le rÃ´le administrateur dispose dÃ©sormais dâ€™un unique parcours Â« Qualification Â» : crÃ©ation dâ€™une liste, aperÃ§u et mappage CSV/XLSX, confirmation de lâ€™import, lancement explicite de Twilio Lookup, consultation des rÃ©sultats techniques et demande dâ€™un export Excel. Le lancement Lookup reste volontaire : lâ€™import ne dÃ©clenche ni Lookup ni appel. Les setters restent limitÃ©s Ã  leur file de travail et ne peuvent ni crÃ©er une liste, ni importer, ni lancer Lookup, ni exporter.

Les nouvelles campagnes portent un marquage serveur Isolation et un propriÃ©taire central auditÃ©. Les campagnes de lâ€™ancienne interface CallVerify, mÃªme prÃ©sentes dans la mÃªme base technique, ne sont jamais retournÃ©es par les routes CRM de qualification. Le compte technique nÃ©cessaire Ã  la compatibilitÃ© de la clÃ© Ã©trangÃ¨re historique est dÃ©sactivÃ©, sans mot de passe utilisable ; lâ€™identitÃ© centrale qui lance chaque opÃ©ration est conservÃ©e dans lâ€™audit. Le lien de transition vers la racine CallVerify a Ã©tÃ© retirÃ© du CRM.

Limites : la racine historique et ses routes restent prÃ©sentes pour compatibilitÃ© des donnÃ©es existantes, mais ne font plus partie du parcours CRM. Lookup nÃ©cessite toujours ses identifiants et son activation serveur ; si ces paramÃ¨tres manquent, aucune requÃªte fournisseur nâ€™est envoyÃ©e. Lâ€™export reprend les colonnes techniques existantes. Aucune campagne dâ€™appel ni appel ne peut Ãªtre lancÃ© par ce module.

VÃ©rifications : tests ciblÃ©s des droits administrateur/setter et de lâ€™isolation des campagnes historiques, suite Isolation existante, vÃ©rification des migrations, TypeScript, tests frontend et build Vite. La suite complÃ¨te Core a Ã©galement Ã©tÃ© lancÃ©e : les tests mÃ©tier atteignent leur exÃ©cution, mais 30 tests de sauvegarde Ã©chouent dans ce bac Ã  sable Windows car le systÃ¨me refuse lâ€™Ã©criture/suppression des rÃ©pertoires temporaires ; ils ne concernent pas le parcours Qualification.

## Ajustement dâ€™interface â€” socle CRM compact

Le shell CRM connectÃ© reprend une disposition plus proche des rÃ©fÃ©rences fournies : liserÃ© bleu supÃ©rieur, navigation sombre plus dense, Ã©tat actif contrastÃ© et zone de travail gris bleutÃ©. Ce socle sâ€™applique sans modifier les routes mÃ©tier ni les droits, et servira aux prochaines listes, tableaux et vues Kanban.

## Ajustement dâ€™interface â€” liste Contacts Isolation

La liste Contacts Isolation utilise une barre de filtres compacte : recherche, responsable, statut commercial, rappels Ã  Ã©chÃ©ance et actualisation. Les donnÃ©es et contrÃ´les existants restent identiques ; cette livraison amÃ©liore leur lisibilitÃ© sur grand comme petit Ã©cran, avec les Ã©tats de ligne et actions dÃ©jÃ  disponibles.

## FonctionnalitÃ© 1 â€” portail et accÃ¨s aux espaces

Livrable du prÃ©sent lot : portail de dÃ©veloppement /crm, connexion et dÃ©connexion centrales, droits explicites par espace, entrÃ©e directe pour un seul espace et sÃ©lection pour les comptes multi-espaces. Les tickets sont signÃ©s, limitÃ©s Ã  deux minutes et propres Ã  chaque audience. Les services Assurance et Isolation possÃ¨dent des bases sÃ©parÃ©es et vÃ©rifient leurs droits cÃ´tÃ© API. Assurance ne propose aucune route Twilio.

Les quelques routes de lecture Assurance servent Ã  vÃ©rifier le pÃ©rimÃ¨tre conseiller ; elles excluent les identifiants internes du setter. Le socle initial Ã©tait en lecture seule ; la fonctionnalitÃ© 3 ajoute lâ€™import. Lâ€™Ã©dition reste bloquÃ©e jusquâ€™au verrouillage. Lâ€™administration des accÃ¨s initiale Ã©tait assurÃ©e par des commandes serveur ; voir la fonctionnalitÃ© 2 pour lâ€™interface livrÃ©e ensuite.

Limites de ce lot : l'interface CallVerify historique conserve sa session propre ; la navigation commune vers ses parcours complets n'est pas encore migrÃ©e. Les rÃ´les setter/client Isolation n'ont pas encore de routes mÃ©tier. MFA, invitations et rÃ©cupÃ©ration de mot de passe centrales restent Ã  intÃ©grer avant production. Les tickets Ã©mis avant une rÃ©vocation peuvent rester valides jusqu'Ã  deux minutes.

## FonctionnalitÃ© 2 â€” gestion des utilisateurs et accÃ¨s

Le portail /crm propose aux administrateurs une liste paginÃ©e et une recherche limitÃ©e Ã  leurs espaces administrÃ©s. Ils peuvent crÃ©er un compte avec mot de passe initial validÃ©, associer un compte existant, modifier un rÃ´le et suspendre ou rÃ©activer un accÃ¨s. Une suspension ne dÃ©sactive ni le compte global ni ses autres espaces. Les modifications sont auditÃ©es sans mot de passe ; les modifications de son propre accÃ¨s sont interdites. Un superutilisateur central sans rÃ´le explicite ne bÃ©nÃ©ficie pas dâ€™accÃ¨s implicite.

VÃ©rification : 15 tests du portail, contrÃ´le TypeScript, build Vite et lecture de lâ€™Ã©cran local. Les invitations par e-mail, la rÃ©cupÃ©ration, le MFA et lâ€™intÃ©gration complÃ¨te de la session Isolation restent Ã  rÃ©aliser. Les tickets dÃ©jÃ  dÃ©livrÃ©s expirent sous deux minutes.

## FonctionnalitÃ© 3 â€” import brut et consultation des contacts Assurance

Depuis /crm â†’ Assurance, lâ€™administrateur importe un CSV (UTF-8 ou Windows-1252 ; sÃ©parateur dÃ©tectÃ© virgule, point-virgule ou tabulation) ou un XLSX (premiÃ¨re feuille). Lâ€™aperÃ§u et lâ€™option en-tÃªte prÃ©cÃ¨dent une correspondance explicite tÃ©lÃ©phone/nom/e-mail. Aucun numÃ©ro nâ€™est normalisÃ©, dÃ©doublonnÃ© ni envoyÃ© Ã  Twilio. Les textes sont conservÃ©s tels que lus, y compris un format de tÃ©lÃ©phone inhabituel ou un e-mail non validÃ© ; la mise en forme Excel ne constitue pas une valeur et nâ€™est pas reprise. Les formules sont conservÃ©es comme texte, jamais calculÃ©es.

Limites : 5 Mo, 10 000 lignes, 100 colonnes, 10 000 caractÃ¨res par cellule. Le tÃ©lÃ©phone doit Ãªtre prÃ©sent ; nom/tÃ©lÃ©phone limitÃ©s Ã  250 caractÃ¨res et e-mail Ã  254. Les lignes entiÃ¨rement vides sont ignorÃ©es, les autres rejets indiquent le numÃ©ro de ligne physique et le motif. Rapport et historique persistants, rÃ©servÃ©s aux administrateurs ; rejets tÃ©lÃ©chargeables en CSV. Colonnes sources et correspondance conservÃ©es en interne. Une confirmation rejouÃ©e avec le mÃªme identifiant et contenu nâ€™insÃ¨re pas de doublons ; un nouvel import volontaire conserve les doublons mÃ©tier.

Liste commune paginÃ©e et recherche pour les setters, pÃ©rimÃ¨tre affectÃ© pour les conseillers, fiche en lecture seule et aucune mÃ©tadonnÃ©e du setter dans les rÃ©ponses publiques. Les contacts importÃ©s ne sont pas affectÃ©s, initialement invisibles aux conseillers. VÃ©rification : 18 tests Assurance (dont 5 000 lignes et rollback), TypeScript/build, parcours rÃ©el sur fichier fictif et tÃ©lÃ©chargement du rapport. Deux contacts de dÃ©monstration sont prÃ©sents dans la base locale Assurance ; aucune donnÃ©e Isolation modifiÃ©e.

La fiche mÃ©tier complÃ¨te (champs configurables, notes, interactions, documents), la modification sous verrou et lâ€™affectation des conseillers restent Ã  rÃ©aliser.

## FonctionnalitÃ© 4 â€” prise en charge et modification sous verrou Assurance

Les setters et administrateurs prennent une fiche en charge pendant trois minutes. La consultation par les autres setters reste possible. Chaque acquisition possÃ¨de un jeton distinct ; renouvellement, sauvegarde et libÃ©ration exigent le bon utilisateur, le bon jeton et un verrou encore valide. Lâ€™expiration permet une nouvelle acquisition. Une version attendue empÃªche une ancienne sauvegarde dâ€™Ã©craser un changement plus rÃ©cent, mÃªme depuis deux requÃªtes du mÃªme compte. Acquisition et Ã©critures utilisent une mise Ã  jour conditionnelle transactionnelle ; aucune dÃ©cision de concurrence ne repose sur le navigateur.

Le parcours fonctionnel permet de modifier nom, tÃ©lÃ©phone et e-mail sans normalisation. Sauvegarde automatique aprÃ¨s 1,2 seconde sans saisie, commande dâ€™enregistrement immÃ©diat et libÃ©ration Ã  la fermeture. Le renouvellement sâ€™effectue toutes les 30 secondes pendant lâ€™activitÃ© visible ; aprÃ¨s deux minutes sans interaction, il sâ€™arrÃªte et le verrou expire. La fermeture de lâ€™application ou une perte rÃ©seau peuvent laisser le verrou jusquâ€™Ã  son expiration ; un brouillon non sauvegardÃ© reste local Ã  la fiche ouverte. Le dÃ©verrouillage forcÃ© est rÃ©servÃ© Ã  lâ€™administrateur, avec motif obligatoire. Les prises en charge, libÃ©rations, modifications avant/aprÃ¨s et interventions administrateur sont auditÃ©es ; le journal paginÃ© est rÃ©servÃ© aux administrateurs. Les conseillers ne reÃ§oivent aucun identifiant de verrou ni auteur interne et nâ€™ont aucun accÃ¨s Ã  ces actions.

VÃ©rifications : 27 tests Assurance exÃ©cutÃ©s sur SQLite ; deux tests supplÃ©mentaires de concurrence (acquisitions et sauvegardes simultanÃ©es) sâ€™exÃ©cutent dans la CI PostgreSQL dÃ©diÃ©e. ContrÃ´le TypeScript, build et migration locale. La revue visuelle est reportÃ©e Ã  la fin Ã  la demande de lâ€™utilisateur. Statuts mÃ©tier, champs configurables, notes/documents et affectation multi-conseillers restent dans les lots suivants.

## FonctionnalitÃ© 5 â€” affectations multi-conseillers Assurance

Lâ€™administrateur associe plusieurs conseillers Ã  un setter, consulte les associations avec recherche/pagination, suspend ou rÃ©active une association et consulte son historique. Le couple setter/conseiller est unique. La suspension conserve lâ€™association et ses Ã©vÃ©nements ; une rÃ©vision attendue interdit dâ€™Ã©craser une modification concurrente. Les setters consultent uniquement leurs propres associations actives. Les conseillers nâ€™ont accÃ¨s ni Ã  la collection, ni aux dÃ©tails, ni aux historiques des associations.

Le portail expose aux seuls administrateurs Assurance un annuaire filtrÃ© des setters/conseillers actifs. Avant une crÃ©ation ou une rÃ©activation, il vÃ©rifie lâ€™Ã©tat du compte et le rÃ´le Assurance, puis signe une attestation de deux minutes pour ce couple et cet administrateur. Assurance la vÃ©rifie avec une finalitÃ© distincte des tickets de connexion ; les identifiants transmis sans preuve, preuves altÃ©rÃ©es, pÃ©rimÃ©es ou Ã©mises pour un autre acteur sont refusÃ©s. Les bases restent indÃ©pendantes et aucun secret de compte nâ€™est transmis. Les suspensions ne requiÃ¨rent pas de nouvelle attestation, afin de permettre le retrait dâ€™une ancienne association mÃªme si un compte a Ã©tÃ© dÃ©sactivÃ©.

Les noms stockÃ©s sont des instantanÃ©s actualisÃ©s Ã  la rÃ©activation. Une association active ne constitue pas une preuve permanente quâ€™un compte central conserve son rÃ´le ; la rÃ©servation devra revalider les accÃ¨s avant dâ€™accepter un conseiller. Une attestation Ã©mise juste avant une rÃ©vocation peut rester valable deux minutes, comme les tickets mÃ©tier existants. Lâ€™affectation ne donne pas Ã  elle seule accÃ¨s Ã  un dossier prospect : les rendez-vous et leurs droits seront livrÃ©s sÃ©parÃ©ment.

VÃ©rifications : tests du portail (annuaire, rÃ´les, rÃ©vocation, CSRF et attestation), tests Assurance (pÃ©rimÃ¨tres, multiples conseillers, doublons, historique, rÃ©activation et rollback), plus crÃ©ation et modification concurrentes sur PostgreSQL dans la CI. TypeScript/build et migration locale ; aucune retouche esthÃ©tique ni crÃ©ation de comptes de dÃ©monstration pour ce lot.

## FonctionnalitÃ© 6 â€” rendez-vous Assurance internes

RÃ©servation depuis une fiche prise en charge, avec une attribution active et une confirmation centrale rÃ©cente des rÃ´les. Un setter rÃ©serve pour ses propres attributions ; un administrateur peut rÃ©server pour un setter attribuÃ©, en conservant sÃ©parÃ©ment le responsable initial et lâ€™auteur rÃ©el de lâ€™opÃ©ration. Un identifiant de requÃªte rend les nouvelles tentatives de la mÃªme rÃ©servation idempotentes. Chaque rendez-vous conserve prospect, attribution, conseiller, setter responsable, auteur interne, crÃ©neau UTC, fuseau IANA, statut et rÃ©vision.

Un verrou transactionnel par conseiller et un verrou sur la fiche prospect empÃªchent les chevauchements internes, y compris entre setters diffÃ©rents ou conseillers diffÃ©rents pour le mÃªme prospect. Deux crÃ©neaux adjacents sont acceptÃ©s. Les dates exigent un dÃ©calage explicite cohÃ©rent avec le fuseau IANA ; les heures locales inexistantes au changement dâ€™heure sont refusÃ©es. Le report et lâ€™annulation exigent un motif interne et une rÃ©vision courante. Les crÃ©neaux prÃ©cÃ©dents, Ã©tats et auteurs restent dans le journal administrateur. Une attribution suspendue bloque rÃ©servation et report, mais autorise encore lâ€™annulation dâ€™un rendez-vous existant.

Liste paginÃ©e filtrÃ©e par prospect, pÃ©riode et statut : lâ€™administrateur voit tous les rendez-vous, le setter uniquement les siens, le conseiller uniquement ceux qui le concernent. Le conseiller accÃ¨de aux dossiers liÃ©s Ã  ses rendez-vous sans recevoir attribution, identitÃ© de setter, auteur, motif libre ou historique interne. Un rendez-vous annulÃ© reste dans son historique et maintient le lien au dossier ; la durÃ©e de conservation et la visibilitÃ© post-contrat restent Ã  valider avec le client. Les anciennes affectations explicites des dossiers Assurance restent reconnues pendant la transition.

Limite explicite : calendrier interne seulement. Google/Microsoft/Calendly ne sont ni consultÃ©s ni synchronisÃ©s et aucune disponibilitÃ© externe nâ€™est garantie. Les rÃ©ponses portent calendar=internal. Les comptes rendus Oui/Non, incidents, tÃ¢ches et notifications seront livrÃ©s ensuite ; un rendez-vous passÃ© ne devient jamais automatiquement effectuÃ© ou non effectuÃ©. Les noms des participants sont conservÃ©s Ã  la rÃ©servation et lâ€™attestation centrale dÃ©jÃ  Ã©mise peut rester valable deux minutes aprÃ¨s rÃ©vocation.

VÃ©rifications : tests du portail et Assurance pour les permissions, fuseaux, confidentialitÃ©, reports, annulations, idempotence et rollback ; CI PostgreSQL pour les courses rÃ©servation/rÃ©servation, rÃ©servation/report, reprise dâ€™une mÃªme requÃªte et conflits sur un prospect entre conseillers. TypeScript/build et migrations. La revue des interfaces reste reportÃ©e Ã  la fin ; les commandes du lot sont utilisables sans identifiants dâ€™agenda externe.

## FonctionnalitÃ© 7 â€” comptes rendus et tÃ¢ches de suivi Assurance

Le conseiller du rendez-vous renseigne Oui/Non aprÃ¨s sa fin et peut signaler un problÃ¨me dans ce compte rendu. Non ou ProblÃ¨me impose un motif et crÃ©e exactement une tÃ¢che liÃ©e au rendez-vous et au setter initial, indÃ©pendamment de lâ€™administrateur qui a rÃ©servÃ©. Une rÃ©pÃ©tition identique est idempotente ; une rÃ©ponse diffÃ©rente ne remplace pas un compte rendu dÃ©jÃ  enregistrÃ©. Le compte rendu ne peut Ãªtre saisi pour un rendez-vous futur ou annulÃ©. Une fois renseignÃ©, le rendez-vous ne peut plus Ãªtre annulÃ© ni reportÃ© pour effacer son rÃ©sultat.

Les setters consultent uniquement leurs tÃ¢ches, les administrateurs toutes les tÃ¢ches, et les conseillers aucune tÃ¢che interne. Le tableau de bord compte les tÃ¢ches ouvertes Ã  chaque chargement : consulter une tÃ¢che ne supprime pas lâ€™alerte. La clÃ´ture exige une justification et conserve date, auteur et audit. Les tÃ¢ches comportent motif, prioritÃ© normale et Ã©chÃ©ance initiale Ã  24 heures, valeur provisoire Ã  valider avec le client. Les listes ouvertes/clÃ´turÃ©es sont paginÃ©es. Lâ€™absence de compte rendu reste un compte rendu Ã  fournir, jamais un rÃ©sultat Non automatique.

Limites : le signalement est actuellement inclus dans le compte rendu initial ; correction et signalement ultÃ©rieur distinct restent Ã  livrer. Pas dâ€™e-mail envoyÃ©, de relance planifiÃ©e, de personnalisation de prioritÃ©/Ã©chÃ©ance ou dâ€™escalade dans ce lot. Les notifications e-mail minimales seront intÃ©grÃ©es sÃ©parÃ©ment. La revue esthÃ©tique reste reportÃ©e Ã  la fin. Tests de permissions, idempotence, rollback, alertes et clÃ´ture justifiÃ©e ; concurrence de soumission testÃ©e sur PostgreSQL dans la CI.

## FonctionnalitÃ© 8 â€” prioritÃ© et Ã©chÃ©ance des tÃ¢ches

Lâ€™administrateur peut replanifier une tÃ¢che ouverte : prioritÃ© basse/normale/haute/urgente, Ã©chÃ©ance future avec dÃ©calage ISO 8601 explicite et motif obligatoire. Une rÃ©vision attendue protÃ¨ge les modifications simultanÃ©es ; une tÃ¢che clÃ´turÃ©e ne peut plus Ãªtre replanifiÃ©e. Lâ€™historique paginÃ©, rÃ©servÃ© Ã  lâ€™administration, conserve les valeurs avant/aprÃ¨s, le motif et lâ€™auteur. Les setters voient les nouvelles prioritÃ©s/Ã©chÃ©ances de leurs tÃ¢ches sans pouvoir les changer. Un indicateur signale les tÃ¢ches en retard sans les clÃ´turer ni retirer les alertes.

Lâ€™Ã©chÃ©ance initiale reste 24 heures et la prioritÃ© normale ; la rÃ¨gle automatique globale, les escalades et notifications e-mail restent Ã  livrer. Six tests fonctionnels supplÃ©mentaires et un test PostgreSQL de modifications concurrentes, TypeScript/build et migration locale. Revue esthÃ©tique reportÃ©e Ã  la fin.

## FonctionnalitÃ© 9 â€” signalements ultÃ©rieurs et reprise du suivi

AprÃ¨s son compte rendu initial, le conseiller du rendez-vous peut ajouter des signalements horodatÃ©s distincts. Le compte rendu reste inchangÃ©. Une mÃªme requÃªte rejouÃ©e est idempotente ; un identifiant rÃ©utilisÃ© avec un autre contenu est refusÃ©. Les signalements sont paginÃ©s, limitÃ©s au pÃ©rimÃ¨tre du rendez-vous et ne contiennent aucun auteur/setter interne dans leurs rÃ©ponses publiques.

Chaque rendez-vous conserve au maximum une tÃ¢che de suivi. Un nouveau signalement crÃ©e cette tÃ¢che si nÃ©cessaire, conserve la tÃ¢che ouverte existante ou rouvre une tÃ¢che clÃ´turÃ©e avec une nouvelle Ã©chÃ©ance Ã  24 heures. Ancienne clÃ´ture, rÃ©solution et rÃ©vision sont conservÃ©es dans lâ€™audit. Le setter voit le dernier signalement sur sa tÃ¢che ; lâ€™administration dispose de lâ€™historique complet. La clÃ´ture exige dÃ©sormais la rÃ©vision courante afin quâ€™un ancien formulaire ne puisse clÃ´turer un nouveau signalement par inadvertance. PrioritÃ© et Ã©chÃ©ance existantes sont conservÃ©es quand la tÃ¢che Ã©tait dÃ©jÃ  ouverte ; prioritÃ© conservÃ©e Ã  la rÃ©ouverture.

VÃ©rifications : tests de permissions, conservation du compte rendu, idempotence, rÃ©ouverture, clÃ´ture pÃ©rimÃ©e, audit/rollback et concurrence PostgreSQL. TypeScript/build et migration locale. Les notifications e-mail et rÃ¨gles automatiques dâ€™escalade restent Ã  livrer ; la revue visuelle reste reportÃ©e Ã  la fin.

## FonctionnalitÃ© 10 â€” rÃ¨gles de suivi configurables

Lâ€™administrateur Assurance configure le dÃ©lai initial des nouvelles tÃ¢ches, la prioritÃ© initiale et le dÃ©lai de rÃ©ouverture, avec motif obligatoire et contrÃ´le de version. DÃ©lais bornÃ©s de 1 Ã  720 heures Ã©coulÃ©es ; pas de calcul en jours ouvrÃ©s. Les valeurs initiales restent 24 heures et prioritÃ© normale tant quâ€™aucune rÃ¨gle nâ€™est enregistrÃ©e. Les modifications sont auditÃ©es dans un historique paginÃ© rÃ©servÃ© Ã  lâ€™administration.

Les tÃ¢ches ouvertes conservent leur planification et leur prioritÃ©, mÃªme aprÃ¨s changement de rÃ¨gle. La rÃ©ouverture utilise le dÃ©lai configurÃ© au moment du signalement tout en conservant la prioritÃ© de la tÃ¢che. Chaque tÃ¢che conserve en interne la rÃ©vision de la rÃ¨gle appliquÃ©e. Tests des droits, bornes, anciennes versions, absence de modification rÃ©troactive, crÃ©ation/rÃ©ouverture et rollback ; concurrence PostgreSQL testÃ©e en CI, TypeScript/build et migration locale. Notifications e-mail et escalades restent Ã  livrer ; aucun envoi nâ€™est activÃ©.

## FonctionnalitÃ© 11 â€” notes horodatÃ©es des fiches Assurance

Ajout de notes conservÃ©es chronologiquement, paginÃ©es et liÃ©es au prospect. Le canal est choisi cÃ´tÃ© serveur : notes internes pour setters/administrateurs et notes conseiller pour ce rÃ´le. Lâ€™administrateur consulte toutes les notes avec leurs auteurs internes ; les setters consultent les notes internes communes, chaque conseiller seulement ses propres notes sur ses dossiers autorisÃ©s. Aucun auteur de note interne ni contenu interne nâ€™est transmis au conseiller.

Les notes internes nÃ©cessitent une prise en charge valide ; les notes du conseiller sont des ajouts indÃ©pendants qui ne modifient pas la fiche partagÃ©e. Les notes sont limitÃ©es Ã  5 000 caractÃ¨res, conservÃ©es sans modification ou suppression par API ; un complÃ©ment ou une correction sâ€™ajoute sous forme de nouvelle note. Un identifiant de requÃªte rend les reprises idempotentes. Lâ€™ajout est auditÃ© transactionnellement ; aucune donnÃ©e ne reste crÃ©Ã©e si lâ€™audit Ã©choue. La politique de partage avec les setters est volontairement restrictive pour les notes conseiller et pourra Ãªtre prÃ©cisÃ©e lors de la recette mÃ©tier.

VÃ©rifications : permissions, confidentialitÃ© entre canaux et conseillers, idempotence, limites, conservation et rollback ; test PostgreSQL de soumissions simultanÃ©es, TypeScript/build et migration locale. Champs configurables, documents, messagerie et revue finale des interfaces restent Ã  rÃ©aliser.

## FonctionnalitÃ© 12 â€” statistiques opÃ©rationnelles Assurance

Statistiques filtrÃ©es sur une pÃ©riode de 366 jours maximum, selon le dÃ©but actuel du rendez-vous en UTC (bornes de dates incluses). Valeurs globales pour lâ€™administrateur et ventilation paginÃ©e par setter responsable initial ; le setter ne voit que ses propres totaux, sans annuaire ni identitÃ©s dâ€™autres setters. Les conseillers nâ€™ont pas accÃ¨s Ã  ce rapport interne.

Compteurs : rendez-vous, annulations, rendez-vous Ã  venir, comptes rendus, Oui, Non, comptes rendus manquants aprÃ¨s Ã©chÃ©ance, comptes rendus avec problÃ¨me, signalements ultÃ©rieurs, tÃ¢ches ouvertes/en retard/clÃ´turÃ©es. Les agrÃ©gats distincts empÃªchent les signalements multiples de multiplier les rendez-vous ou tÃ¢ches. Le taux effectuÃ© est Oui / comptes rendus renseignÃ©s ; il reste non calculable en lâ€™absence de rÃ©ponses, et nâ€™est ni un taux de conversion contrat ni une dÃ©duction de prÃ©sence. Une absence de compte rendu nâ€™est jamais assimilÃ©e Ã  Non.

Les tÃ¢ches reflÃ¨tent leur Ã©tat actuel sur les rendez-vous de la pÃ©riode. Un report peut dÃ©placer un rendez-vous vers une autre pÃ©riode ; il ne sâ€™agit pas dâ€™un journal historique figÃ©. Les noms de setters sont le dernier instantanÃ© de rÃ©servation disponible. Appels Phonetico, contrats, ventes, exports statistiques et rapports Isolation ne sont pas comptabilisÃ©s dans ce lot. Six tests ciblÃ©s, suites SQLite/PostgreSQL en CI, TypeScript/build ; aucune migration nÃ©cessaire, revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 13 â€” exports Excel et CSV des statistiques Assurance

TÃ©lÃ©chargement depuis les statistiques avec les dates saisies et les mÃªmes autorisations serveur. Le classeur Excel propose une synthÃ¨se lisible et un onglet dÃ©taillÃ© pour lâ€™administration ; le setter ne reÃ§oit que sa propre synthÃ¨se. CSV UTF-8 avec BOM, sÃ©parateur point-virgule et en-tÃªtes franÃ§ais. PÃ©riode UTC, date de calcul et dÃ©finition du taux accompagnent les exports. Les valeurs non calculables restent explicitement indiquÃ©es, sans faux zÃ©ro.

Lâ€™export administrateur comprend tous les setters de la pÃ©riode, indÃ©pendamment de la page affichÃ©e, avec plafond explicite de 5 000 setters. Les noms dangereux sont neutralisÃ©s en CSV et stockÃ©s comme texte en Excel pour Ã©viter les formules exÃ©cutables. Aucun prospect, coordonnÃ©e, note ou auteur dâ€™interaction nâ€™est exportÃ©. Chaque export est auditÃ©, rÃ©ponse non mise en cache. Les chiffres sont recalculÃ©s au moment du tÃ©lÃ©chargement et peuvent Ã©voluer depuis lâ€™affichage.

Douze tests ciblÃ©s statistiques/exports rÃ©ussis, dont confidentialitÃ©, complÃ©tude au-delÃ  de 25 lignes, lecture rÃ©elle du XLSX et neutralisation des formules ; suites complÃ¨tes SQLite/PostgreSQL en CI, TypeScript/build. Aucune migration nÃ©cessaire. Revue esthÃ©tique reportÃ©e Ã  la fin ; statistiques ventes/Phonetico/Isolation non incluses.

## FonctionnalitÃ© 14 â€” champs personnalisables des fiches Assurance

Lâ€™administration dÃ©finit jusquâ€™Ã  30 champs internes : texte (2 000 caractÃ¨res), case Ã  cocher, date ou liste de choix. ClÃ© unique et stable, libellÃ©, obligation et Ã©tat actif configurables ; type et choix sont immuables une fois crÃ©Ã©s. Lâ€™archivage dÃ©sactive la saisie tout en conservant les anciennes valeurs. Les mises Ã  jour de configuration exigent une rÃ©vision courante et un motif ; elles sont auditÃ©es.

Les setters et administrateurs renseignent les champs sur une fiche prise en charge, avec contrÃ´le du jeton, de lâ€™expiration, de la version de fiche et de configuration. Les champs obligatoires sâ€™appliquent Ã  lâ€™enregistrement explicite de lâ€™ensemble des champs mÃ©tier actifs, sans bloquer les imports bruts ni la correction des coordonnÃ©es. Les dates, types, choix et clÃ©s sont validÃ©s cÃ´tÃ© serveur ; une case obligatoire exige une valeur boolÃ©enne renseignÃ©e et accepte Non. Les valeurs archivÃ©es sont conservÃ©es mÃªme lors dâ€™une nouvelle saisie. Les modifications avant/aprÃ¨s sont consultables dans le journal administrateur de la fiche.

Aucun schÃ©ma ni valeur personnalisÃ©e nâ€™est exposÃ© au conseiller ou aux exports existants. La saisie mÃ©tier possÃ¨de un enregistrement explicite distinct de la sauvegarde automatique des coordonnÃ©es ; une modification concurrente exige de recharger avant de reprendre. Import/mapping des champs personnalisÃ©s, partage sÃ©lectif conseiller et changements de type ne font pas partie de ce lot. Sept tests ciblÃ©s, concurrence PostgreSQL, TypeScript/build et migration locale. Revue visuelle reportÃ©e Ã  la fin.

## FonctionnalitÃ© 15 â€” documents privÃ©s des fiches Assurance

DÃ©pÃ´t, liste paginÃ©e et tÃ©lÃ©chargement de PDF, PNG et JPEG de 5 Mo maximum par fichier. Les documents internes sont accessibles aux setters et Ã  lâ€™administration ; les conseillers ne voient que leurs propres documents sur leurs dossiers autorisÃ©s. Lâ€™administration peut consulter les deux canaux. Le serveur impose ces permissions sur la liste comme sur chaque tÃ©lÃ©chargement, sans URL publique ni mÃ©tadonnÃ©es internes exposÃ©es au conseiller.

Le dÃ©pÃ´t interne exige une prise en charge valide. Un identifiant de requÃªte et une empreinte SHA-256 rendent les nouvelles tentatives idempotentes et refusent la rÃ©utilisation avec un autre contenu. Documents append-only, tÃ©lÃ©chargements auditÃ©s, rÃ©ponses privÃ©es non mises en cache et tÃ©lÃ©chargement forcÃ© avec protection nosniff. Les octets, mÃ©tadonnÃ©es et audit sont enregistrÃ©s dans une mÃªme transaction de la base Assurance ; aucune piÃ¨ce nâ€™est placÃ©e dans Git ou servie comme fichier statique.

La vÃ©rification porte sur extension, signature et taille ; elle ne constitue pas une analyse antivirus ni une validation complÃ¨te des fichiers. Le stockage binaire augmente le volume de la base et de ses sauvegardes ; quotas par dossier, antivirus, suppression/rÃ©tention rÃ©glementaire, partage sÃ©lectif et stockage objet restent Ã  dÃ©finir avant dÃ©ploiement Ã  grande Ã©chelle. Cinq tests couvrent permissions, tÃ©lÃ©chargements, idempotence, refus des fichiers et annulation transactionnelle si lâ€™audit Ã©choue ; suites complÃ¨tes et CI PostgreSQL, typage et compilation. Migration 0013. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 16 â€” pipeline commercial Assurance

Statuts configurables depuis Â« Statuts et champs mÃ©tier Â» : clÃ©s stables, libellÃ©s, ordre et archivage, jusquâ€™Ã  30 Ã©tapes. Les onze Ã©tapes initiales reprennent le cahier des charges : Ã  contacter, en cours, Ã  rappeler, intÃ©ressÃ©, RDV rÃ©servÃ©, RDV effectuÃ©, incident, suivi, mandat, contrat, clÃ´turÃ©. Le statut initial to_contact reste actif pour les imports. Les clÃ©s existantes ne peuvent pas Ãªtre supprimÃ©es ; lâ€™archivage conserve les fiches concernÃ©es et les rend filtrables dans la liste. Le paramÃ©trage exige un administrateur, une rÃ©vision courante et un motif, avec audit avant/aprÃ¨s.

Depuis une fiche prise en charge, setter ou administrateur choisit explicitement un statut actif et renseigne un motif. Jeton, expiration, version de fiche et version du pipeline sont vÃ©rifiÃ©s dans une transaction ; les changements concurrents ne peuvent pas sâ€™Ã©craser. Le journal administrateur conserve auteur, date, ancien/nouveau statut, libellÃ© et justification. Le conseiller consulte seulement le statut/libellÃ© de ses dossiers autorisÃ©s, sans auteur ni motif interne, et ne peut pas les modifier. La liste permet la recherche combinÃ©e au filtre de statut.

Les statuts sont commerciaux et manuels : aucune crÃ©ation automatique de compte rendu, tÃ¢che, mandat ou contrat, aucune dÃ©duction dâ€™un rÃ©sultat de rendez-vous. Les changements entre Ã©tapes actives sont libres sous verrou ; clÃ´turer ne supprime pas une fiche et ne bloque pas sa reprise autorisÃ©e. Le cycle contractuel, rÃ¨gles de transition conditionnelles, automatisations et vue Kanban ne sont pas livrÃ©s dans ce lot. Six tests fonctionnels et un test de concurrence PostgreSQL, suite Assurance complÃ¨te, typage/build et migration 0014. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 17 â€” rÃ©ouverture administrative des tÃ¢ches Assurance

Lâ€™administrateur peut rouvrir une tÃ¢che clÃ´turÃ©e depuis les listes Â« ClÃ´turÃ©es Â» ou Â« Toutes Â». Un motif, une prioritÃ© et une Ã©chÃ©ance future avec dÃ©calage ISO 8601 explicite sont obligatoires. La mÃªme tÃ¢che reste liÃ©e au rendez-vous et au setter responsable ; aucun doublon ni changement du compte rendu nâ€™est crÃ©Ã©. La rÃ©ouverture efface les champs de clÃ´ture courants, incrÃ©mente la rÃ©vision et rÃ©tablit la tÃ¢che dans la liste ouverte et le compteur dâ€™alertes au prochain chargement.

Le journal administrateur conserve lâ€™auteur et le motif de rÃ©ouverture, lâ€™ancienne date/auteur/justification de clÃ´ture et les valeurs avant/aprÃ¨s. Les historiques antÃ©rieurs restent intacts, mÃªme aprÃ¨s une nouvelle clÃ´ture. Une rÃ©vision attendue et une Ã©criture conditionnelle empÃªchent deux administrateurs de rouvrir simultanÃ©ment la mÃªme version, ou un ancien formulaire de clÃ´turer la tÃ¢che rÃ©ouverte. Ã‰chec dâ€™audit et modification sont annulÃ©s ensemble. Ni setter ni conseiller ne peuvent rouvrir une tÃ¢che ou lire cet historique interne.

RÃ©ouverture manuelle uniquement : la prioritÃ© et lâ€™Ã©chÃ©ance explicites remplacent celles de la tÃ¢che, sans rÃ©appliquer automatiquement la politique globale. La rÃ©attribution Ã  un autre setter, les e-mails et rappels planifiÃ©s restent Ã  livrer. Six tests fonctionnels et un test PostgreSQL de rÃ©ouvertures concurrentes, suite Assurance, TypeScript/build ; aucune migration nÃ©cessaire. La revue esthÃ©tique reste diffÃ©rÃ©e.

## FonctionnalitÃ© 18 â€” rÃ©attribution des tÃ¢ches Assurance

Lâ€™administrateur choisit un setter Assurance actif dans lâ€™annuaire central paginÃ© et justifie le transfert dâ€™une tÃ¢che ouverte. Le portail vÃ©rifie le compte et son rÃ´le, puis Ã©met une attestation de deux minutes liÃ©e au setter cible, Ã  lâ€™administrateur et Ã  la tÃ¢che. Assurance vÃ©rifie sa signature, sa finalitÃ© et sa durÃ©e sans consulter la base du portail. Comptes suspendus, autres rÃ´les, preuves altÃ©rÃ©es/pÃ©rimÃ©es ou liÃ©es Ã  un autre acteur/dossier de tÃ¢che sont refusÃ©s. Une attestation dÃ©jÃ  dÃ©livrÃ©e peut rester valide jusquâ€™Ã  deux minutes aprÃ¨s rÃ©vocation.

Seule la responsabilitÃ© actuelle de la tÃ¢che change ; prioritÃ©, Ã©chÃ©ance, rendez-vous et setter dâ€™origine sont conservÃ©s. La tÃ¢che sort du pÃ©rimÃ¨tre de lâ€™ancien responsable et entre dans celui du nouveau, avec le compteur dâ€™alertes recalculÃ© au chargement. Le nouveau responsable peut la clÃ´turer ; un ancien formulaire, mÃªme avec une rÃ©vision devinÃ©e, ne peut plus Ã©crire aprÃ¨s transfert. Les rÃ©ouvertures et nouveaux signalements conservent le responsable actuel. TransfÃ©rer une tÃ¢che ne donne pas accÃ¨s aux autres rendez-vous du setter dâ€™origine.

La rÃ©vision attendue et une Ã©criture conditionnelle protÃ¨gent transferts/clÃ´tures concurrents. Lâ€™audit administrateur conserve avant/aprÃ¨s, origine, nom cible attestÃ©, acteur et motif, sans exposition aux conseillers. Les statistiques restent regroupÃ©es selon le setter dâ€™origine du rendez-vous ; elles ne constituent pas une mesure de la charge actuelle des tÃ¢ches, distinction indiquÃ©e dans la dÃ©finition et les exports. Une tÃ¢che clÃ´turÃ©e doit Ãªtre rouverte avant transfert. Aucun e-mail ni transfert en masse dans ce lot.

Huit tests mÃ©tier, quatre tests du portail et deux tests de concurrence PostgreSQL ajoutÃ©s ; suites Assurance/portail, typage et compilation. Aucune migration nÃ©cessaire, revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 19 â€” affectations et file de prospects Isolation

Depuis le portail /crm, lâ€™administrateur Isolation consulte les prospects existants de toutes les campagnes, recherche par nom/tÃ©lÃ©phone/rÃ©fÃ©rence et filtre par responsable ou absence dâ€™affectation. Il attribue un prospect Ã  un setter, le transfÃ¨re ou retire son affectation avec motif obligatoire. Lâ€™annuaire central est paginÃ© et limitÃ© aux setters Isolation actifs. Une attestation signÃ©e, liÃ©e Ã  lâ€™administrateur, au prospect et au setter cible, expire sous deux minutes. Les noms sont des instantanÃ©s de lâ€™attestation ; la rÃ©vocation centrale empÃªche les nouvelles attestations/tickets, mais ceux dÃ©jÃ  Ã©mis peuvent rester valables deux minutes.

Le setter arrive directement dans sa file, paginÃ©e et recherchable, et ne consulte que ses prospects actuellement attribuÃ©s, y compris par accÃ¨s direct Ã  lâ€™API. Un transfert ou retrait coupe son accÃ¨s au prochain chargement. La fiche de consultation expose une liste de champs explicite : coordonnÃ©es disponibles, campagne, validitÃ© de format, Ã©tat technique dÃ©jÃ  stockÃ© et responsable. Aucun appel, Lookup ni normalisation supplÃ©mentaire nâ€™est dÃ©clenchÃ©. Aucune identitÃ© locale dâ€™administrateur nâ€™est crÃ©Ã©e pour les setters : les identifiants centraux restent distincts des comptes historiques.

Les nouvelles routes de travail ont leur propre authentification par ticket Isolation et leurs contrÃ´les serveur. Les anciens endpoints dâ€™administration, imports, Lookup, appels et exports restent interdits aux setters. Le rÃ´le client nâ€™accÃ¨de pas encore Ã  cette file. RÃ©vision attendue et mise Ã  jour conditionnelle empÃªchent deux affectations concurrentes de sâ€™Ã©craser ; audit et affectation sont atomiques. Lâ€™administration consulte lâ€™historique avec acteur central, valeurs avant/aprÃ¨s et motif. Aucune modification des imports, doublons techniques ou rÃ©sultats Lookup existants.

Limites : affectations unitaires, consultation uniquement cÃ´tÃ© setter. Qualification commerciale, notes, rappels, appels Phonetico, visites, portail client et affectations en masse restent Ã  livrer. Lâ€™interface historique conserve sa session distincte pour lâ€™administration des imports/Twilio. Six tests mÃ©tier et un test de concurrence PostgreSQL ajoutÃ©s, quatre tests du portail, suites Isolation/portail et CI Assurance, TypeScript/build. Migration Isolation 0007 appliquÃ©e localement ; CI PostgreSQL Ã©tendue Ã  la concurrence Isolation. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 20 â€” observations commerciales et rappels Isolation

Le setter sur ses prospects attribuÃ©s, ou lâ€™administrateur Isolation sur tout prospect, ajoute une note ou un rÃ©sultat commercial : Ã  contacter, en cours, Ã  rappeler, intÃ©ressÃ©, non intÃ©ressÃ©, non joint. Chaque observation exige un texte et reste dans un historique paginÃ© avec date, identifiant central et rÃ´le de lâ€™auteur. Les rÃ©sultats commerciaux sont distincts de la validitÃ© de format, de lâ€™Ã©tat de ligne et des rÃ©sultats Lookup/Voice : non joint ne signifie pas numÃ©ro invalide et aucune vÃ©rification ni appel rÃ©el nâ€™est dÃ©clenchÃ©.

Le rÃ©sultat Ã€ rappeler exige une date future avec dÃ©calage ISO 8601 explicite. Les rappels Ã  Ã©chÃ©ance possÃ¨dent un compteur persistant recalculÃ© au chargement et un filtre de file ordonnÃ© du plus ancien au plus rÃ©cent. Leur consultation ne les efface pas. Une note laisse le rappel inchangÃ© ; une qualification peut le reprogrammer ou le retirer en choisissant un autre rÃ©sultat, avec ancienne date et Ã©tat conservÃ©s dans lâ€™historique. Le transfert dâ€™un prospect transfÃ¨re aussi son rappel courant au nouveau responsable.

Une version commune protÃ¨ge observations et affectations ; chaque sauvegarde revÃ©rifie le responsable dans lâ€™Ã©criture conditionnelle, mÃªme si le transfert intervient aprÃ¨s la lecture initiale. Lâ€™identifiant de requÃªte et une empreinte rendent les nouvelles tentatives identiques idempotentes et empÃªchent les doublons. Une tentative concurrente avec une version dÃ©passÃ©e peut demander un rechargement ; les observations enregistrÃ©es ne sont jamais remplacÃ©es. En cas dâ€™Ã©chec dâ€™audit, qualification, rappel, note et version sont annulÃ©s ensemble. Lâ€™ancien setter perd aussi lâ€™accÃ¨s aux historiques aprÃ¨s rÃ©attribution. Les administrateurs et les prochains clients autorisÃ©s Isolation pourront retracer les auteurs ; le portail client nâ€™est pas livrÃ© dans ce lot.

Limites : un seul rappel courant par prospect, statuts initiaux fixes, pas de planification de plusieurs tÃ¢ches, de notification e-mail, dâ€™appel ni de visite. Lâ€™identitÃ© de lâ€™auteur est conservÃ©e par identifiant central et rÃ´le ; aucun compte administrateur local nâ€™est crÃ©Ã© pour reprÃ©senter un setter. Huit tests fonctionnels et deux tests PostgreSQL ajoutÃ©s ; 82 tests Isolation locaux dont trois rÃ©servÃ©s Ã  PostgreSQL, CI complÃ¨te, typage et compilation. Migration 0008 appliquÃ©e localement. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 21 â€” rÃ©servation et suivi des visites Isolation internes

RÃ©servation depuis un prospect attribuÃ© Ã  un setter, liste paginÃ©e globale ou par prospect, consultation, report et annulation justifiÃ©s. Le portail revalide le setter actif et exige exactement un client Isolation actif, conformÃ©ment au lancement mono-client. Lâ€™attestation signÃ©e est propre Ã  la rÃ©servation, liÃ©e au prospect et Ã  lâ€™acteur, valable deux minutes ; le setter ne peut en obtenir que pour lui-mÃªme. Lâ€™administrateur peut rÃ©server pour le responsable du prospect, en conservant distinctement lâ€™auteur rÃ©el et le setter dâ€™origine.

Les visites conservent prospect, client et setter dâ€™origine avec instantanÃ©s de noms, auteur de rÃ©servation, dates UTC, fuseau IANA, statut et rÃ©vision. Lâ€™identifiant de requÃªte rend les reprises de rÃ©servation idempotentes. Les dates exigent un dÃ©calage cohÃ©rent avec le fuseau, y compris aux changements dâ€™heure. Le calendrier interne rÃ©serve une seule visite simultanÃ©e par client ; il empÃªche aussi les chevauchements pour un mÃªme prospect, tout en acceptant des crÃ©neaux adjacents. Un verrou transactionnel par client et une Ã©criture sur le prospect protÃ¨gent rÃ©servations et reports concurrents.

Le setter consulte et gÃ¨re uniquement les visites des prospects actuellement attribuÃ©s. Un transfert dÃ©place ce pÃ©rimÃ¨tre sans rÃ©Ã©crire le setter dâ€™origine de la visite. Le report revalide les participants et conserve le client ; lâ€™annulation reste possible par lâ€™administration mÃªme aprÃ¨s retrait de lâ€™affectation. Toute modification incrÃ©mente la version commune du prospect. Les rÃ©visions de visite empÃªchent les reports/annulations pÃ©rimÃ©s ; les visites commencÃ©es ne sont plus rÃ©Ã©crites par ces commandes. Lâ€™historique administrateur conserve chaque crÃ©neau, motif, statut et acteur. Audit et mutations sont atomiques.

Calendrier strictement interne (calendar=internal) : ni disponibilitÃ©s ni synchronisation Google/Microsoft/Calendly garanties, aucun e-mail envoyÃ©. La rÃ©servation ne change pas automatiquement le rÃ©sultat commercial ou le rappel du prospect. Le portail client et les rÃ©sultats des visites restent Ã  livrer ; une visite passÃ©e reste planifiÃ©e en lâ€™absence de rÃ©sultat, jamais dÃ©clarÃ©e effectuÃ©e par dÃ©duction. Les tickets/attestations dÃ©jÃ  dÃ©livrÃ©s peuvent subsister deux minutes aprÃ¨s rÃ©vocation. Dix tests fonctionnels, trois tests PostgreSQL de concurrence et quatre tests portail ajoutÃ©s ; suites Isolation/portail, CI Assurance, typage/build. Migration 0009 appliquÃ©e localement. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 22 â€” portail client Isolation et rÃ©sultats des visites

Le compte client Isolation entre dans son espace depuis /crm avec sa session centrale. Il consulte uniquement les visites portant son identifiant client et les dossiers liÃ©s Ã  ces visites, avec recherche/pagination et une liste explicite de coordonnÃ©es. Le nom et lâ€™identifiant du setter dâ€™origine restent visibles sur la visite, conformÃ©ment Ã  la confidentialitÃ© propre Ã  Isolation. Les visites et dossiers dâ€™un autre client restent inaccessibles, mÃªme par URL directe ; aucun accÃ¨s aux imports, Lookup, exports administratifs, file setter ou journal interne nâ€™est ouvert au client.

Le tableau de bord affiche les visites Ã  venir, rÃ©sultats enregistrÃ©s et rÃ©sultats encore attendus aprÃ¨s la fin dâ€™une visite non annulÃ©e. Le filtre Â« rÃ©sultats Ã  renseigner Â» et le compteur persistent aprÃ¨s consultation. Le client concernÃ© renseigne Oui/Non, un rÃ©sultat cohÃ©rent (effectuÃ©e, suivi nÃ©cessaire, intÃ©ressÃ©, non intÃ©ressÃ©, non effectuÃ©e) et un commentaire obligatoire. Une absence de rÃ©ponse reste un rÃ©sultat manquant, jamais un Non dÃ©duit automatiquement. Lâ€™administration et le setter actuellement responsable du prospect peuvent consulter le rÃ©sultat, mais ne le remplissent pas Ã  la place du client.

Le premier rÃ©sultat est conservÃ© avec identifiant client et date ; une rÃ©pÃ©tition identique est idempotente, une rÃ©ponse diffÃ©rente ne remplace pas lâ€™historique. Une rÃ©vision de visite et un verrou transactionnel empÃªchent les rÃ©ponses concurrentes de sâ€™Ã©craser. Une visite future, annulÃ©e ou modifiÃ©e entre-temps ne peut pas recevoir un rÃ©sultat ; une visite dÃ©jÃ  renseignÃ©e ne peut plus Ãªtre reportÃ©e/annulÃ©e pour effacer son issue. Audit, rÃ©sultat et incrÃ©ment de version sont atomiques. Un transfert du prospect change le pÃ©rimÃ¨tre setter sans rÃ©Ã©crire le setter dâ€™origine ni retirer au client son rÃ©sultat.

Limites : calendrier externe, statistiques dÃ©taillÃ©es par setter, partage de notes commerciales/historique interne, complÃ©ments/corrections des rÃ©sultats et suivi automatique restent Ã  livrer. Les dossiers liÃ©s Ã  des visites annulÃ©es restent consultables dans lâ€™historique client ; les durÃ©es de conservation doivent Ãªtre cadrÃ©es avant production. Aucun rÃ©sultat de visite ne modifie les Ã©tats techniques des numÃ©ros ou ne crÃ©e automatiquement un contrat. Dix tests fonctionnels et deux tests PostgreSQL ajoutÃ©s ; 107 tests Isolation locaux dont huit rÃ©servÃ©s Ã  PostgreSQL, typage/build et CI complÃ¨te. Migration 0010 appliquÃ©e localement. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 23 â€” statistiques des visites Isolation

Statistiques consultables dans les espaces administrateur, setter et client Isolation, sur une pÃ©riode de 366 jours maximum selon le dÃ©but actuel des visites en UTC. Compteurs : visites rÃ©servÃ©es, prospects distincts liÃ©s Ã  ces visites, annulations, visites Ã  venir, rÃ©sultats renseignÃ©s, Oui, Non, rÃ©sultats manquants, intÃ©ressÃ©s, non intÃ©ressÃ©s et suivi nÃ©cessaire. Le taux effectuÃ© est Oui / rÃ©sultats renseignÃ©s ; le taux dâ€™intÃ©rÃªt est intÃ©ressÃ©s / visites effectuÃ©es. Sans dÃ©nominateur les taux restent non calculables ; un rÃ©sultat manquant ne devient pas Non.

Lâ€™administration dispose des totaux et dâ€™une ventilation paginÃ©e par setter dâ€™origine. Le client voit uniquement ses visites, totaux et ventilation ; les noms de setters sont tirÃ©s de ses seules visites autorisÃ©es. Le setter reÃ§oit uniquement les totaux de ses rÃ©servations dont il conserve actuellement le prospect : un transfert retire les visites de son pÃ©rimÃ¨tre statistique, sans rÃ©Ã©crire leur origine dans les statistiques administrateur/client. Cette limite protÃ¨ge les dossiers retirÃ©s ; ces chiffres ne sont pas un classement historique exhaustif du setter. Les noms sont les derniers instantanÃ©s de rÃ©servation du pÃ©rimÃ¨tre autorisÃ©. Les prospects distincts par groupe ne sâ€™additionnent pas nÃ©cessairement au total global.

Les filtres de permissions sâ€™appliquent avant chaque agrÃ©gat et avant la recherche du nom ; aucun tÃ©lÃ©phone, note, rÃ©sultat libre ou dossier individuel nâ€™est exposÃ© dans les statistiques. RÃ©ponses non mises en cache. Un report dÃ©place une visite entre pÃ©riodes et les rÃ©sultats reflÃ¨tent lâ€™Ã©tat actuel, pas une photographie historique. Appels Phonetico, ventes, contrats, contacts sans visite, exports et statistiques dâ€™activitÃ© commerciale restent hors de ce lot. Sept tests ciblÃ©s, suite Isolation et CI PostgreSQL, typage et build ; aucune migration nÃ©cessaire. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 24 â€” exports Excel et CSV des statistiques Isolation

TÃ©lÃ©chargement des statistiques selon les dates saisies et les mÃªmes pÃ©rimÃ¨tres serveur que lâ€™affichage. Lâ€™administration exporte les totaux et tous les setters ; le client uniquement les agrÃ©gats de ses visites et leurs setters dâ€™origine ; le setter uniquement sa synthÃ¨se autorisÃ©e, sans liste dâ€™autres setters. La pagination affichÃ©e ne limite pas les exports. Plafond explicite de 5 000 setters par export, Ã  rÃ©duire en restreignant la pÃ©riode si nÃ©cessaire.

Le classeur Excel comprend une synthÃ¨se avec libellÃ©s franÃ§ais, pÃ©riode UTC, date de calcul et dÃ©finition des indicateurs, puis un onglet filtrable par setter lorsquâ€™il existe des groupes autorisÃ©s. CSV UTF-8 avec BOM, sÃ©parateur point-virgule et en-tÃªtes franÃ§ais. Les taux sans dÃ©nominateur restent Â« Non calculable Â». Les noms pouvant devenir des formules sont neutralisÃ©s en CSV et forcÃ©s en texte en Excel. Aucun tÃ©lÃ©phone, dossier individuel ni note libre nâ€™est exportÃ©.

Les tÃ©lÃ©chargements sont auditÃ©s avec acteur central, pÃ©riode, format et rÃ´le ; rÃ©ponses sans cache, en piÃ¨ce jointe et nosniff. Les chiffres sont recalculÃ©s Ã  chaque tÃ©lÃ©chargement : un report ou une rÃ©attribution peut changer le rÃ©sultat depuis la derniÃ¨re consultation. Les dÃ©finitions et limites de la fonctionnalitÃ© 23 restent valables, notamment le pÃ©rimÃ¨tre du setter aprÃ¨s transfert et les prospects distincts non additionnables entre groupes. Cinq tests dÃ©diÃ©s avec lecture rÃ©elle des CSV/XLSX, confidentialitÃ©, complÃ©tude sur 27 setters, neutralisation des formules et refus dâ€™accÃ¨s ; suite Isolation/CI PostgreSQL et typage/build. Aucune migration nÃ©cessaire, revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 25 â€” complÃ©ments aux rÃ©sultats des visites Isolation

Le client concernÃ© peut ajouter des prÃ©cisions aprÃ¨s le rÃ©sultat initial dâ€™une visite. Les complÃ©ments sont distincts, horodatÃ©s, paginÃ©s et conservÃ©s avec lâ€™identifiant client ; aucun ne modifie ou ne supprime le rÃ©sultat initial, son issue commerciale ou les statistiques. La lecture est autorisÃ©e au client de la visite, au setter actuellement responsable du prospect et Ã  lâ€™administration, avec les mÃªmes contrÃ´les par URL que les visites. Un transfert retire la lecture Ã  lâ€™ancien setter sans effacer les contributions.

Chaque ajout exige un texte de 3 000 caractÃ¨res maximum et un identifiant de requÃªte unique. Une reprise identique retourne le complÃ©ment existant ; la rÃ©utilisation avec un autre contenu ou une autre visite est refusÃ©e. Le verrou de visite sÃ©rialise les ajouts simultanÃ©s ; complÃ©ment et audit sont transactionnels. Le journal administrateur conserve lâ€™auteur central et la rÃ©fÃ©rence du complÃ©ment. Aucun rÃ©sultat absent ne peut recevoir de complÃ©ment, ni setter ou administrateur Ã©crire Ã  la place du client.

Cinq tests fonctionnels et un test de concurrence PostgreSQL ajoutÃ©s : permissions, idempotence, historique/pagination, rÃ©sultat conservÃ© et annulation si lâ€™audit Ã©choue. Suite Isolation, typage/build et CI complÃ¨te ; migration 0011 appliquÃ©e localement. Limites : prÃ©cisions textuelles uniquement, aucune correction structurÃ©e du rÃ©sultat, notification ou tÃ¢che automatique ; revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 26 â€” changement du mot de passe central

Tous les utilisateurs connectÃ©s au portail /crm disposent dâ€™une commande Â« Mon mot de passe Â», y compris sans espace attribuÃ©. Lâ€™opÃ©ration exige le mot de passe actuel, un nouveau mot de passe distinct et sa confirmation. Les rÃ¨gles centrales sont vÃ©rifiÃ©es cÃ´tÃ© serveur (minimum 12 caractÃ¨res et refus des mots de passe courants), avec entrÃ©es limitÃ©es Ã  256 caractÃ¨res, sans suppression des espaces. Aucun identifiant cible ne peut Ãªtre transmis pour modifier un autre compte. La route est authentifiÃ©e par session, protÃ©gÃ©e par CSRF et limitÃ©e Ã  cinq tentatives par minute et par compte via le cache configurÃ©.

Une Ã©criture transactionnelle sÃ©rialise les changements sur le compte avant de vÃ©rifier le mot de passe actuel ; lâ€™audit et le nouveau hachage sont enregistrÃ©s ensemble. Le journal indique seulement le compte et lâ€™action, sans mot de passe ni hachage. La session utilisÃ©e est renouvelÃ©e et reste authentifiÃ©e ; les autres sessions portent lâ€™ancien hachage et sont rejetÃ©es Ã  leur prochaine requÃªte. Les rÃ´les et accÃ¨s des deux espaces restent inchangÃ©s. Les tickets mÃ©tier prÃ©cÃ©demment Ã©mis peuvent subsister jusquâ€™Ã  deux minutes ; le compte historique Isolation demeure distinct.

Huit tests supplÃ©mentaires avec de vraies sessions/CSRF : ancien mot de passe, rÃ¨gles de validation, confirmation, cible interdite, limitation des tentatives, reprise de connexion, invalidation de lâ€™autre session et rollback si lâ€™audit Ã©choue. Suite portail complÃ¨te, typage/build et CI. Aucune migration nÃ©cessaire. Limites : rÃ©cupÃ©ration de mot de passe oubliÃ©, invitations, MFA et limitation distribuÃ©e avant production restent Ã  livrer ; revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 27 â€” rÃ©cupÃ©ration du mot de passe central

Commande Â« Mot de passe oubliÃ© Â» depuis la connexion AMX, demande par adresse e-mail et saisie dâ€™un nouveau mot de passe confirmÃ©. La rÃ©ponse publique reste identique pour un compte connu ou inconnu, suspendu, sans mot de passe utilisable ou une adresse ambiguÃ« associÃ©e Ã  plusieurs comptes. Les erreurs SMTP ne dÃ©voilent ni destinataire ni Ã©tat du compte ; lâ€™Ã©chec est enregistrÃ© dans lâ€™audit sans dÃ©tail technique sensible. Demandes limitÃ©es Ã  cinq par heure par adresse IP, confirmations Ã  dix ; CSRF requis sur les deux opÃ©rations.

Lien signÃ© Django de 30 minutes, liÃ© au compte et invalidÃ© aprÃ¨s changement du mot de passe ou de lâ€™adresse e-mail. Le serveur utilise exclusivement PORTAL_PUBLIC_URL configurÃ©, jamais lâ€™hÃ´te envoyÃ© par le navigateur ; HTTPS requis pour le lien hors DEBUG. Le jeton est placÃ© dans le fragment de lâ€™URL, retirÃ© de la barre dâ€™adresse Ã  lâ€™ouverture et transmis uniquement dans le corps de confirmation. Il nâ€™est renvoyÃ© dans aucune rÃ©ponse API ni conservÃ© dans lâ€™audit. Nouveau mot de passe validÃ© cÃ´tÃ© serveur, Ã©crit atomiquement avec son audit ; anciennes sessions rejetÃ©es Ã  leur prochaine requÃªte, sans connexion automatique du demandeur. Les tickets mÃ©tier dÃ©jÃ  Ã©mis expirent au maximum sous deux minutes.

Transport portail distinct : PORTAL_EMAIL_* et PORTAL_FROM_EMAIL. En dÃ©veloppement, les e-mails vont par dÃ©faut dans private-media/portal-mail, hors Git ; les tests utilisent une boÃ®te en mÃ©moire. Docker configure un SMTP explicite, Ã  renseigner et tester avant envoi rÃ©el. Le service traite lâ€™envoi de faÃ§on synchrone avec dÃ©lai rÃ©seau maximal de dix secondes : file persistante, reprise dâ€™envoi, protection distribuÃ©e et rÃ©duction des Ã©carts de temps de rÃ©ponse restent Ã  renforcer avant production. Les adresses des comptes doivent Ãªtre renseignÃ©es et non ambiguÃ«s ; rÃ©cupÃ©ration sans adresse impossible. Sept tests dÃ©diÃ©s, suite portail, TypeScript/build et CI ; aucune migration. Aucun e-mail rÃ©el envoyÃ© pendant ce lot.

## FonctionnalitÃ© 28 â€” invitations aux nouveaux comptes centraux

Depuis Utilisateurs et accÃ¨s, lâ€™administrateur invite un nouveau compte avec identifiant, e-mail et rÃ´le compatible avec son seul espace. La liste paginÃ©e indique en attente, expirÃ©e, acceptÃ©e ou rÃ©voquÃ©e ; commandes de renvoi et rÃ©vocation. Aucun compte ni accÃ¨s mÃ©tier avant acceptation. Les comptes dÃ©jÃ  prÃ©sents sont refusÃ©s : leur association reste une commande sÃ©parÃ©e qui conserve leur mot de passe.

Lien alÃ©atoire de 24 heures dont seul le SHA-256 est stockÃ©. Fragment retirÃ© de la barre dâ€™adresse Ã  lâ€™ouverture, jeton transmis dans le corps protÃ©gÃ© par CSRF, jamais renvoyÃ© dans une API ni inscrit dans lâ€™audit. Le renvoi remplace le jeton ; expiration, rÃ©vocation et usage unique sont vÃ©rifiÃ©s cÃ´tÃ© serveur. Lâ€™acceptation exige un mot de passe confirmÃ© conforme aux rÃ¨gles centrales, revalide les droits de lâ€™Ã©metteur, crÃ©e atomiquement le compte, son seul accÃ¨s et lâ€™audit, sans connexion automatique. Les modifications de droits et acceptations sont sÃ©rialisÃ©es dans le mÃªme ordre ; contraintes insensibles Ã  la casse pour lâ€™identifiant et lâ€™e-mail des invitations.

Transport synchrone partagÃ© avec la rÃ©cupÃ©ration : fichiers privÃ©s en dÃ©veloppement, boÃ®te en mÃ©moire dans les tests ; SMTP rÃ©el Ã  configurer et valider. Ã‰chec dâ€™envoi affichÃ© avec possibilitÃ© de renvoi ; aucun e-mail rÃ©el envoyÃ© dans ce lot. Lâ€™historique rÃ©serve lâ€™identifiant et lâ€™adresse, y compris aprÃ¨s rÃ©vocation : pas de recyclage automatique ni dâ€™Ã©dition du destinataire/rÃ´le dâ€™une invitation ; lâ€™administration peut crÃ©er un compte par le parcours existant si nÃ©cessaire. File persistante, relances automatiques et limitation distribuÃ©e restent Ã  rÃ©aliser. Acceptation limitÃ©e par IP, administration limitÃ©e aux sessions autorisÃ©es sans quota dâ€™envoi spÃ©cifique pour lâ€™instant.

Sept tests fonctionnels et un test de double acceptation PostgreSQL ; suite portail de 62 tests (concurrence rÃ©servÃ©e Ã  PostgreSQL), typage/build. La CI vÃ©rifie dÃ©sormais aussi le portail sur PostgreSQL. Migrations 0003 et 0004 appliquÃ©es localement. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 29 â€” file persistante des e-mails du portail

Invitations et rÃ©cupÃ©rations ne dÃ©pendent plus dâ€™un envoi SMTP dans la requÃªte web. Le message est chiffrÃ© Fernet dans la base centrale, avec expiration, Ã©tat, nombre dâ€™essais et rÃ©servation de traitement ; crÃ©ation de la demande, mise en file et audit sont transactionnels. Le navigateur indique Â« mis en file Â», sans annoncer une livraison rÃ©ussie. Un worker traite les messages via dispatch_portal_mail (lot, boucle ou Ã©tat agrÃ©gÃ© sans envoi) ; le service Docker portal-mail est fourni. Commandes et configuration dans docs/PORTAL_MAIL.md.

RÃ©servation atomique de 60 secondes, reprise aprÃ¨s arrÃªt du worker, cinq tentatives SMTP maximum et dÃ©lais croissants. ContrÃ´le avant envoi des liens expirÃ©s, remplacÃ©s, acceptÃ©s, rÃ©voquÃ©s ou invalidÃ©s par le compte/droits ; aucun envoi dans ces cas. Destinataire, corps et jetons ne sont ni en clair dans la table ni dans les audits. Contenu effacÃ© aprÃ¨s succÃ¨s, expiration ou Ã©chec dÃ©finitif ; traces dâ€™Ã©tat conservÃ©es. ClÃ© PORTAL_MAIL_KEY obligatoire en production, Ã  sauvegarder sÃ©parÃ©ment et Ã  partager entre serveur et worker. Transport fichier privÃ© en dÃ©veloppement, mÃ©moire pendant les tests. Aucun e-mail rÃ©el envoyÃ©.

Limites explicites : livraison SMTP au moins une fois (doublon possible aprÃ¨s arrÃªt entre envoi et confirmation), rÃ©ception/lecture/rebonds non prouvÃ©s, supervision avancÃ©e et conservation Ã  dÃ©finir. Une rotation de clÃ© rend la file prÃ©cÃ©dente illisible sans ancienne clÃ©. Pas encore de notifications mÃ©tier ou rappels automatiques ; ce lot fiabilise uniquement les e-mails de comptes existants. SMTP rÃ©el non configurÃ© et worker Ã  maintenir actif ; le serveur web seul nâ€™envoie plus ces messages. Les limites dâ€™administration/invitations du lot 28 restent valables.

Sept tests de file et un test de rÃ©servation concurrente PostgreSQL ajoutÃ©s ; suites de rÃ©cupÃ©ration/invitation adaptÃ©es Ã  la livraison diffÃ©rÃ©e, 70 tests portail (deux rÃ©servÃ©s Ã  PostgreSQL), typage/build et CI complÃ¨te. Migration 0005 appliquÃ©e localement. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 30 â€” affectations en lot des prospects Isolation

Lâ€™administrateur Isolation sÃ©lectionne jusquâ€™Ã  25 prospects de la page courante et confirme une affectation/rÃ©attribution vers un setter actif ou un retrait commun, avec motif obligatoire. Annuaire central recherchÃ© et paginÃ© ; chaque affectation exige une attestation liÃ©e au prospect, au setter cible et Ã  lâ€™acteur. Le lot ne fait ni appel, ni Lookup, ni modification de qualification, rappel, historique de visite ou rÃ©sultat technique. Setter/client et identitÃ©s Assurance sont refusÃ©s cÃ´tÃ© API.

Toutes les rÃ©visions sont vÃ©rifiÃ©es dans une transaction : prospect manquant/modifiÃ©, cible dÃ©jÃ  identique, attestation invalide ou erreur dâ€™audit annulent le lot entier. Les Ã©critures sont ordonnÃ©es par identifiant et utilisent la mÃªme version commune que les affectations unitaires et activitÃ©s. Chaque prospect reÃ§oit une entrÃ©e dâ€™audit avant/aprÃ¨s avec motif et rÃ©fÃ©rence de lot. Aucun transfert ne rÃ©Ã©crit le setter dâ€™origine des visites.

Un identifiant de requÃªte conserve un rÃ©sultat historique minimal (identifiants/rÃ©visions), sans coordonnÃ©es. Une reprise identique par le mÃªme administrateur ne recommence pas les Ã©critures ; rÃ©utilisation par un autre acteur ou pour un contenu diffÃ©rent refusÃ©e. Une reprise peut retourner la rÃ©vision historique du lot si le dossier a Ã©voluÃ© depuis : recharger la liste pour lâ€™Ã©tat courant. Les attestations ne sont pas exigÃ©es Ã  nouveau pour lire le rÃ©sultat dâ€™un lot dÃ©jÃ  acceptÃ©. AprÃ¨s une coupure rÃ©seau, le formulaire conserve son identifiant tant que la sÃ©lection, la cible ou le motif ne changent pas ; un rechargement complet perd cette continuitÃ© cÃ´tÃ© navigateur mais les rÃ©visions empÃªchent de rÃ©appliquer le lot ancien.

Limites : sÃ©lection de la page courante seulement, effacÃ©e lors dâ€™un changement de page/filtre ; pas de sÃ©lection implicite des milliers de rÃ©sultats ni de rÃ©partition automatique Ã©quitable entre setters. Les fiches dÃ©jÃ  affectÃ©es Ã  la cible doivent Ãªtre dÃ©sÃ©lectionnÃ©es. Les attestations centrales restent valides deux minutes au maximum. Six tests fonctionnels et deux tests de concurrence PostgreSQL ajoutÃ©s ; suite core de 133 tests (onze rÃ©servÃ©s Ã  PostgreSQL), typage/build, contrÃ´le des migrations et CI. Migration 0012 appliquÃ©e localement. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 31 â€” notifications internes des incidents Assurance

BoÃ®te de notifications persistante dans lâ€™espace Assurance des setters et administrateurs, avec nombre dâ€™Ã©vÃ©nements liÃ©s aux tÃ¢ches ouvertes et nombre de non-lus. Un compte rendu Non/avec problÃ¨me et chaque signalement ultÃ©rieur crÃ©ent une notification distincte dans la transaction de lâ€™Ã©vÃ©nement ; les reprises idempotentes ne la dupliquent pas. Une notification de reprise est crÃ©Ã©e pour chaque tÃ¢che dÃ©jÃ  ouverte sans notification lors de la migration. Un signalement ne crÃ©e toujours quâ€™une seule tÃ¢che par rendez-vous.

Liste paginÃ©e, filtres suivi ouvert/rÃ©solu/tous et non lues, date de lecture par utilisateur, prioritÃ©/Ã©chÃ©ance actuelles et rÃ©fÃ©rence de tÃ¢che. Lecture explicite et idempotente, avec audit ; lire ne modifie ni la rÃ©vision, ni lâ€™Ã©chÃ©ance, ni la clÃ´ture de la tÃ¢che. Lâ€™administrateur ne marque pas comme lu pour le setter. La boÃ®te suit le responsable actuel de la tÃ¢che : lâ€™ancien setter perd lâ€™accÃ¨s aprÃ¨s transfert, le nouveau voit ses propres Ã©tats de lecture. Le verrou de tÃ¢che revalide ce pÃ©rimÃ¨tre avant dâ€™enregistrer une lecture. ClÃ´ture et rÃ©ouverture changent lâ€™Ã©tat actif des notifications sans effacer les lectures ; une rÃ©ouverture administrative ne crÃ©e pas de nouvel Ã©vÃ©nement non lu dans ce lot.

Aucun accÃ¨s conseiller ou identitÃ© Isolation, y compris par URL directe. RÃ©ponses par liste explicite de champs, sans nom de prospect, coordonnÃ©es, note dâ€™incident ou identitÃ© de setter ; aucun cache. La boÃ®te sâ€™actualise toutes les 30 secondes lorsque la page est visible, manuellement et aprÃ¨s les commandes de tÃ¢che du navigateur. Les Ã©vÃ©nements ouverts restent affichables aprÃ¨s dÃ©connexion/lecture jusquâ€™Ã  rÃ©solution de la tÃ¢che. Le nombre de notifications compte les Ã©vÃ©nements, pas les tÃ¢ches distinctes ; une tÃ¢che peut avoir plusieurs signalements. Le bouton ouvre les tÃ¢ches de suivi, dont les identifiants sont dÃ©sormais affichÃ©s.

Huit tests fonctionnels et un test de double lecture PostgreSQL ajoutÃ©s : autorisations, lecture indÃ©pendante, transfert, clÃ´ture/rÃ©ouverture, idempotence, reprise des tÃ¢ches ouvertes, filtres/pagination et rollback si notification ou audit Ã©choue. Suite Assurance de 154 tests (19 rÃ©servÃ©s Ã  PostgreSQL), TypeScript/build et contrÃ´le des migrations ; migrations 0015/0016 appliquÃ©es localement. Limites : notifications internes uniquement, aucun e-mail mÃ©tier, rappel programmÃ©, notification de rÃ©attribution/rÃ©ouverture dÃ©diÃ©e, push ou escalade automatique ; ces parcours restent Ã  livrer sÃ©parÃ©ment. Aucun message externe envoyÃ©. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 32 â€” e-mails de notification des suivis Assurance

Les Ã©vÃ©nements de compte rendu nÃ©cessitant un suivi et les nouveaux signalements alimentent dÃ©sormais la file chiffrÃ©e du portail via un relais serveur. Assurance expose seulement les rÃ©fÃ©rences dâ€™Ã©vÃ©nement, dates et identifiants centraux du setter actuel, sur des routes signÃ©es avec clÃ© dÃ©diÃ©e et durÃ©e de 60 secondes ; les tickets utilisateurs nâ€™y donnent aucun accÃ¨s. Le portail ne se connecte jamais Ã  la base Assurance. Il rÃ©sout lui-mÃªme les comptes, rÃ´les et adresses, sans transmettre lâ€™annuaire central Ã  Assurance.

Relais persistant par pages de 100 Ã©vÃ©nements, curseur reprenant aprÃ¨s panne, nouvelle exploration aprÃ¨s fin de parcours et registre unique Ã©vÃ©nement/destinataire pour Ã©viter les doubles mises en file, y compris entre relais concurrents. Compte actif, rÃ´le setter Assurance actif, adresse valide et non ambiguÃ« requis. Avant chaque tentative SMTP, les droits centraux, lâ€™adresse, la tÃ¢che ouverte et le responsable sont revÃ©rifiÃ©s. Assurance indisponible entraÃ®ne une reprise ; une tÃ¢che clÃ´turÃ©e ou rÃ©attribuÃ©e nâ€™est pas envoyÃ©e Ã  lâ€™ancien responsable aprÃ¨s contrÃ´le. Le prochain parcours peut notifier le nouveau setter. Message neutre, sans coordonnÃ©es, note, nom ou identifiant de prospect, avec lien vers /crm exigeant la connexion normale. Aucune donnÃ©e de setter nâ€™est envoyÃ©e au conseiller.

Deux commandes distinctes et services Docker : relay_assurance_mail met en file, dispatch_portal_mail envoie. Configuration, diagnostics sans donnÃ©es personnelles et limites documentÃ©s dans docs/PORTAL_MAIL.md. Seuls les Ã©vÃ©nements des sept derniers jours et les tÃ¢ches ouvertes sont concernÃ©s ; les notifications de reprise historique ne sont pas envoyÃ©es. Une lecture dâ€™e-mail ne clÃ´ture rien. Les garanties sont celles de SMTP au moins une fois : doublon possible aprÃ¨s arrÃªt entre envoi et confirmation, rÃ©ception/lecture non prouvÃ©es.

Cinq tests Assurance et neuf tests portail ajoutÃ©s, plus une concurrence PostgreSQL de dÃ©duplication du relais ; suites de 159 tests Assurance et 80 tests portail (respectivement 19 et trois rÃ©servÃ©s Ã  PostgreSQL), contrÃ´les des migrations et CI. Migration portail 0006 appliquÃ©e localement. Tests SMTP en mÃ©moire seulement, aucun message externe envoyÃ©. Limites : exploitation des deux workers et SMTP rÃ©el Ã  configurer/valider ; pas de rappels pÃ©riodiques, escalades, renvoi automatique dâ€™un mÃªme Ã©vÃ©nement aprÃ¨s Ã©chec dÃ©finitif/changement dâ€™adresse, ni notification dÃ©diÃ©e de rÃ©ouverture. FenÃªtre de sept jours ; lâ€™alerte interne reste la rÃ©fÃ©rence au-delÃ . Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 33 â€” rappels des tÃ¢ches en retard et comptes rendus manquants

Politique globale Assurance administrable : activation par type, intervalle de tÃ¢che, dÃ©lai aprÃ¨s fin de rendez-vous et intervalle des comptes rendus. Par dÃ©faut actifs, intervalles de 24 heures et dÃ©lai de compte rendu de 24 heures ; heures Ã©coulÃ©es UTC, sans jours ouvrÃ©s. Motif, rÃ©vision et audit atomique des changements. Ces rÃ¨gles nâ€™altÃ¨rent ni les Ã©chÃ©ances des tÃ¢ches ni les rÃ©sultats des rendez-vous.

Le worker Assurance produit un Ã©vÃ©nement pour la seule pÃ©riode courante par tÃ¢che dÃ©passÃ©e/setter actuel ou rendez-vous sans compte rendu/conseiller concernÃ©. DÃ©duplication par objet, ancrage temporel, destinataire, rÃ¨gle et pÃ©riode, avec verrouillage transactionnel et contrainte unique ; pas de rafale rÃ©troactive aprÃ¨s arrÃªt du worker. Les Ã©vÃ©nements constituent la trace automatique de gÃ©nÃ©ration, sans inventer un auteur humain. Aucun rÃ©sultat Non ou incident dÃ©duit dâ€™un compte rendu manquant.

Liste de rappels actifs paginÃ©e dans le CRM, compteurs, commandes vers les tÃ¢ches et rendez-vous et rÃ©glage administrateur. Les conseillers ne voient que leurs rappels de compte rendu, sans aucune donnÃ©e de setter ; les setters voient seulement leurs rappels de tÃ¢ches courantes. ClÃ´ture, rÃ©ponse, annulation, report, nouvelle Ã©chÃ©ance, transfert, dÃ©sactivation ou fin de pÃ©riode invalident immÃ©diatement lâ€™Ã©ligibilitÃ© serveur ; la liste visible se rafraÃ®chit manuellement ou toutes les 60 secondes. Les lectures ne rÃ©solvent rien. Lâ€™historique est conservÃ© en base, sans Ã©cran dâ€™historique exhaustif dans ce lot.

Le relais e-mail accepte un flux de rappels distinct des incidents, avec curseur et registre Ã©vÃ©nement/destinataire propres. RÃ©solution centrale du rÃ´le setter/conseiller et adresse, message neutre et contrÃ´le de lâ€™Ã©tat mÃ©tier avant SMTP ; les rappels devenus obsolÃ¨tes ne sont pas envoyÃ©s aprÃ¨s contrÃ´le. Un changement de rÃ¨gle invalide les anciens Ã©vÃ©nements et peut recrÃ©er un rappel courant au prochain passage. Services Docker, commandes et limites dans docs/PORTAL_MAIL.md. Aucun e-mail rÃ©el envoyÃ© ; SMTP en mÃ©moire pendant les tests.

Dix tests fonctionnels Assurance et une concurrence PostgreSQL ajoutÃ©s, plus quatre tests portail des flux et rÃ´les ; suites de 170 tests Assurance (20 rÃ©servÃ©s Ã  PostgreSQL) et 84 tests portail (trois rÃ©servÃ©s Ã  PostgreSQL), typage/build et contrÃ´les des migrations. Migrations Assurance 0017/0018 et portail 0007 appliquÃ©es localement. Limites : exploitation des trois workers et SMTP rÃ©el Ã  valider, pas dâ€™escalade administrateur, jours ouvrÃ©s, quota journalier par utilisateur ou rÃ©glage individuel. Le balayage est complet et en flux, sa capacitÃ© doit Ãªtre mesurÃ©e Ã  grande Ã©chelle. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 34 â€” escalades administrateurs Assurance

Les rÃ¨gles de rappel proposent une escalade facultative, dÃ©sactivÃ©e initialement, pour les tÃ¢ches durablement en retard et les comptes rendus toujours manquants. Seuils initiaux : 72 heures aprÃ¨s lâ€™Ã©chÃ©ance de tÃ¢che, ou 72 heures supplÃ©mentaires aprÃ¨s le dÃ©lai normal de compte rendu ; rÃ©pÃ©tition toutes les 24 heures. Seuils rÃ©glables de 1 Ã  2160 heures et rÃ©pÃ©tition de 1 Ã  720 heures, avec rÃ©vision et motif auditÃ©s. Le type de rappel parent doit rester activÃ©. Heures UTC Ã©coulÃ©es, sans jours ouvrÃ©s.

Les administrateurs Assurance disposent dâ€™un compteur et dâ€™un filtre rÃ©servÃ© aux escalades dans les rappels actifs. Aucune rÃ©affectation, clÃ´ture ou rÃ©ponse nÃ©gative automatique. Un transfert de tÃ¢che conserve la supervision administrative sans recrÃ©er lâ€™escalade de la mÃªme pÃ©riode. RÃ©solution, compte rendu, report, nouvelle Ã©chÃ©ance, dÃ©sactivation ou changement de rÃ¨gle invalident les Ã©vÃ©nements concernÃ©s. GÃ©nÃ©ration transactionnelle et idempotente, limitÃ©e Ã  la pÃ©riode courante aprÃ¨s une panne ; historique conservÃ© en base, sans Ã©cran exhaustif ni acquittement dÃ©diÃ©.

Un troisiÃ¨me flux du relais central adresse un message neutre Ã  chaque administrateur disposant explicitement dâ€™un accÃ¨s Assurance actif, avec compte actif et adresse valide non ambiguÃ«. Les administrateurs Isolation et les superutilisateurs sans cet accÃ¨s sont exclus. Assurance ne reÃ§oit aucun annuaire central : il expose une rÃ©fÃ©rence de diffusion administrative signÃ©e, sans donnÃ©e de prospect. Registre de dÃ©duplication par Ã©vÃ©nement/destinataire et recontrÃ´le du rÃ´le et de la situation avant chaque tentative SMTP. Les workers existants suffisent ; configuration dans docs/PORTAL_MAIL.md.

Huit tests fonctionnels et une concurrence PostgreSQL ajoutÃ©s cÃ´tÃ© Assurance, quatre tests portail supplÃ©mentaires. Suites : 179 tests Assurance (21 rÃ©servÃ©s Ã  PostgreSQL), 88 tests portail (trois rÃ©servÃ©s Ã  PostgreSQL), contrÃ´les des migrations et typage/build. Migration Assurance 0019 appliquÃ©e localement. Aucun e-mail rÃ©el envoyÃ© : SMTP en mÃ©moire pour les tests. Limites : diffusion Ã  tous les administrateurs Assurance actifs, pas de choix individuel ou de quotas ; capacitÃ© de balayage et de diffusion Ã  mesurer. SMTP rÃ©el et exploitation des workers restent Ã  valider ; doublon possible aprÃ¨s arrÃªt entre SMTP et confirmation, rÃ©ception non prouvÃ©e. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 35 â€” observations Isolation partagÃ©es au client

Depuis une visite Isolation, le setter actuellement responsable du prospect ou lâ€™administrateur consulte les observations et publie ou retire explicitement une note/qualification pour le client de cette visite. Les observations existantes et futures restent internes par dÃ©faut. La publication concerne ce client sur toutes ses visites du mÃªme dossier, y compris lâ€™historique annulÃ© ; elle ne donne aucun droit Ã  un autre client liÃ© au mÃªme prospect. Le client ne peut ni publier, ni modifier lâ€™observation, ni accÃ©der Ã  la file interne. Pagination, actualisation et confirmation avec motif sont disponibles dans le parcours Visites â†’ Observations partagÃ©es.

Le portail client ne reÃ§oit que les observations publiÃ©es : texte, qualification et anciennes/nouvelles dates de rappel Ã©ventuelles, date, rÃ´le et identifiant central de lâ€™auteur dâ€™origine. Les noms dâ€™auteurs ne sont pas rÃ©solus par ce lot ; lâ€™identitÃ© est conservÃ©e par identifiant, mÃªme aprÃ¨s transfert du dossier. Aucun motif interne de publication, audit, demande technique, empreinte ou rÃ©sultat Lookup nâ€™est exposÃ©. Cette publication ne modifie pas lâ€™observation source, la qualification courante, les rÃ©sultats de visite ni lâ€™Ã©tat technique de ligne.

Publication et retrait utilisent la mÃªme rÃ©vision transactionnelle de prospect que lâ€™affectation et les observations. Un ancien responsable est refusÃ©, une version pÃ©rimÃ©e ou une visibilitÃ© dÃ©jÃ  identique donne un conflit. Une contrainte unique activitÃ©/client conserve le choix courant ; lâ€™audit contient auteur, destinataire, visite, Ã©tats avant/aprÃ¨s, motif et rÃ©vision, sans recopier le texte. Une erreur dâ€™audit annule visibilitÃ© et rÃ©vision. Les lectures sont sans cache. Le retrait bloque les prochaines requÃªtes, sans effacer ce qui a dÃ©jÃ  Ã©tÃ© lu ou copiÃ© ; lâ€™utilisateur actualise lâ€™Ã©cran pour voir le nouvel Ã©tat. AprÃ¨s une rÃ©ponse rÃ©seau perdue, recharger avant de recommencer : pas de jeton de reprise dÃ©diÃ© dans ce lot.

Huit tests fonctionnels et deux tests de concurrence PostgreSQL ajoutÃ©s (double publication et publication face Ã  un transfert). Suite core : 143 tests, dont 13 rÃ©servÃ©s Ã  PostgreSQL ; tests ciblÃ©s revÃ©rifiÃ©s aprÃ¨s ajustements, contrÃ´le des migrations, typage et build. La CI PostgreSQL inclut le nouveau module. Migration core 0013 appliquÃ©e localement. Limites : partage observation par observation via une visite existante, sans notification e-mail, export dÃ©diÃ©, sÃ©lection en lot ou rÃ¨gle dâ€™expiration ; aucun partage automatique des anciennes notes. Les durÃ©es de visibilitÃ©/conservation restent Ã  valider avec le client. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 36 â€” rÃ©partition bornÃ©e des prospects Isolation

Lâ€™administrateur Isolation sÃ©lectionne jusquâ€™Ã  25 prospects sans responsable sur la page courante et jusquâ€™Ã  25 setters depuis lâ€™annuaire central paginÃ©. Une prÃ©visualisation serveur, sans Ã©criture ni rÃ©servation, rÃ©partit les prospects par identifiant croissant, Ã  tour de rÃ´le entre les identifiants de setters croissants. Les compteurs indiquent les parts avant confirmation ; lâ€™Ã©cart dans ce lot est au plus un. Un setter sÃ©lectionnÃ© peut recevoir zÃ©ro prospect si les destinataires sont plus nombreux que les dossiers. La charge antÃ©rieure, les disponibilitÃ©s et les lots prÃ©cÃ©dents ne sont pas utilisÃ©s : ce lot ne promet pas un Ã©quilibrage global.

La confirmation exige un motif et une attestation centrale rÃ©cente pour chaque couple prospect/setter effectivement utilisÃ©. Les noms sont issus des attestations, jamais du navigateur. Seuls les administrateurs Isolation peuvent prÃ©visualiser ou confirmer. Le serveur recalcule la rÃ©partition ; un prospect absent, dÃ©jÃ  affectÃ© ou dont la rÃ©vision a changÃ© annule tout le lot. Verrous dans lâ€™ordre des identifiants et version commune avec les affectations, activitÃ©s, visites et partages. Aucune rÃ©attribution automatique, aucun appel, Lookup ou changement de qualification. Les audits par prospect conservent le mode round_robin, le lot, les Ã©tats avant/aprÃ¨s et le motif.

Le registre de lots existant distingue la rÃ©partition dâ€™une affectation manuelle. Une confirmation identique du mÃªme acteur retourne le rÃ©sultat historique sans refaire les Ã©critures, mÃªme si les preuves ont expirÃ© ; une rÃ©utilisation du mÃªme identifiant avec un autre contenu/acteur est refusÃ©e. Le rÃ©sultat contient les identifiants des cibles et rÃ©visions historiques, sans tÃ©lÃ©phone ni nom. Lâ€™interface conserve son identifiant tant que sÃ©lection, setters et motif ne changent pas ; aprÃ¨s rechargement complet, cette continuitÃ© est perdue. Le parcours renouvelle les preuves avant confirmation et peut donc Ã©chouer cÃ´tÃ© annuaire si un destinataire a depuis perdu ses droits, mÃªme pour une reprise historique ; recharger les prospects pour vÃ©rifier lâ€™Ã©tat.

Six tests fonctionnels et deux tests de concurrence PostgreSQL ajoutÃ©s : aperÃ§u sans Ã©criture, Ã©quilibre dÃ©terministe, reprise et sÃ©paration des modes, permissions/preuves/bornes, rollback, 25 prospects, concurrence avec lâ€™affectation manuelle et double confirmation. Suite core de 151 tests (15 rÃ©servÃ©s Ã  PostgreSQL), tests ciblÃ©s, contrÃ´le des migrations, typage/build ; aucune migration nÃ©cessaire. Limites : page courante uniquement, aucune sÃ©lection massive ou exÃ©cution planifiÃ©e, pas de pondÃ©ration ou de quota par setter et pas de rÃ©servation des dossiers par lâ€™aperÃ§u. Les droits attestÃ©s peuvent rester valables deux minutes aprÃ¨s rÃ©vocation. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 37 â€” journal dâ€™administration des accÃ¨s du portail

Depuis Utilisateurs et accÃ¨s â†’ Consulter le journal des accÃ¨s, un administrateur consulte les Ã©vÃ©nements historiques de ses seuls espaces explicitement administrÃ©s : accÃ¨s accordÃ©/modifiÃ©, invitation crÃ©Ã©e/renouvelÃ©e/rÃ©voquÃ©e/acceptÃ©e. Liste de 25 Ã©vÃ©nements par page, tri du plus rÃ©cent au plus ancien avec identifiant dÃ©partageant les dates Ã©gales ; filtres par action, identifiant numÃ©rique dâ€™auteur et dates UTC incluses. Aucun nouveau droit implicite pour un superutilisateur central. Une suspension ou perte du rÃ´le administrateur bloque les requÃªtes suivantes immÃ©diatement.

RÃ©ponses par liste explicite de champs : action/libellÃ©, date, auteur central actuel (identifiant et nom de compte), identifiant du compte concernÃ©, rÃ´le/Ã©tat avant et aprÃ¨s, rÃ©fÃ©rence UUID dâ€™invitation et type dâ€™association lorsque ces informations existent. Aucune sÃ©rialisation brute des mÃ©tadonnÃ©es : adresses, mots de passe, jetons, contenu chiffrÃ© et champs inconnus sont exclus. Une trace dont lâ€™auteur a Ã©tÃ© supprimÃ© reste affichÃ©e sans identitÃ© dâ€™auteur ; les champs historiques absents ou mal formÃ©s sont omis. Aucun nom de compte cible ou adresse dâ€™invitÃ© nâ€™est rÃ©solu par cette route. Lecture seule, sans cache ni Ã©criture rÃ©cursive de consultation.

Sept tests fonctionnels ajoutÃ©s : pÃ©rimÃ¨tres, rÃ´les/rÃ©vocation, liste de champs et secrets imbriquÃ©s, dates et pagination, filtres invalides/Ã©critures refusÃ©es, parcours rÃ©el de crÃ©ation/modification dâ€™accÃ¨s et suppression dâ€™auteur. Suite portail de 95 tests (trois rÃ©servÃ©s Ã  PostgreSQL), contrÃ´le des migrations, typage/build et CI complÃ¨te. Aucune migration nÃ©cessaire. Limites : journal des accÃ¨s et invitations seulement, pas de connexions globales, dâ€™Ã©vÃ©nements mail ou dâ€™audit mÃ©tier centralisÃ© ; pas dâ€™export, de notification ou de scellement cryptographique. Les noms dâ€™auteurs sont ceux des comptes actuels, sans instantanÃ© historique. Les commandes serveur qui nâ€™ont pas Ã©crit ces Ã©vÃ©nements ne sont pas reconstituÃ©es. Conservation et archivage restent Ã  dÃ©finir. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 38 â€” rÃ©vocation des autres sessions centrales

Dans Mon compte et mes sessions, un utilisateur authentifiÃ© confirme son mot de passe actuel pour dÃ©connecter ses autres sessions du portail AMX, sans changer son mot de passe ni ses accÃ¨s. La session utilisÃ©e est renouvelÃ©e et conservÃ©e ; les onglets partageant le mÃªme cookie restent donc connectÃ©s. Le parcours reste accessible aux comptes sans espace. Protection CSRF, validation stricte des champs et quota de cinq tentatives par minute partagÃ© avec le changement de mot de passe.

Un compteur de rÃ©vocation par compte est contrÃ´lÃ© Ã  chaque authentification par session du portail. Les anciennes sessions sont refusÃ©es au prochain accÃ¨s protÃ©gÃ© et ne peuvent plus obtenir de ticket mÃ©tier ; les routes publiques permettent de retrouver un jeton CSRF et de se reconnecter normalement. Chaque nouvelle connexion adopte le compteur courant. Les sessions antÃ©rieures au dÃ©ploiement restent compatibles jusquâ€™Ã  une rÃ©vocation. IncrÃ©ment et audit sans donnÃ©e de session sont atomiques ; relecture verrouillÃ©e du compte et contrÃ´le du compteur empÃªchent deux anciennes sessions concurrentes de se conserver toutes les deux. Une erreur dâ€™audit annule la rÃ©vocation.

Sept tests fonctionnels et une concurrence PostgreSQL ajoutÃ©s ; suite portail de 103 tests (quatre rÃ©servÃ©s Ã  PostgreSQL), contrÃ´le des migrations et typage/build. Migration portail 0008 appliquÃ©e localement. VÃ©rifications avec vÃ©ritables sessions et CSRF : autre compte prÃ©servÃ©, rotation courante, ancienne session refusÃ©e, reconnexion au compteur courant, refus des mots de passe incorrects/champs supplÃ©mentaires, rollback et limitation des tentatives. Aucun jeton, identifiant de session ou mot de passe conservÃ© dans lâ€™audit.

Limites : rÃ©vocation des sessions centrales seulement, sans liste dâ€™appareils ni nombre de sessions actives. La session historique Isolation reste indÃ©pendante. Les tickets mÃ©tier dÃ©jÃ  Ã©mis peuvent rester valables deux minutes et une requÃªte dÃ©jÃ  authentifiÃ©e nâ€™est pas interrompue. Les anciennes lignes de session expirent selon les mÃ©canismes Django habituels ; cette action ne les efface pas toutes immÃ©diatement. Une perte de rÃ©ponse aprÃ¨s rÃ©vocation peut imposer une reconnexion sur lâ€™appareil courant ; le compteur reste la rÃ©fÃ©rence. Pas de MFA ou de rÃ©vocation immÃ©diate des tickets mÃ©tiers dans ce lot. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 39 â€” connexion et disponibilitÃ© Google/Microsoft

Conseiller Assurance et client Isolation connectent leur propre agenda principal depuis Mon compte et mes sessions. Un fournisseur Google ou Microsoft par espace ; remplacement explicite par un nouveau consentement, dÃ©connexion avec rÃ©vision et consultation des seules pÃ©riodes occupÃ©es sur une fenÃªtre maximale de 31 jours. Calendly exclu Ã  la demande de lâ€™utilisateur. Les boutons indiquent la configuration manquante cÃ´tÃ© serveur.

OAuth serveur avec PKCE, Ã©tat alÃ©atoire hachÃ©, tentative liÃ©e Ã  la session/espace/fournisseur et consommÃ©e une fois sous dix minutes ; secrets et jetons chiffrÃ©s avec clÃ© dÃ©diÃ©e. Callback relayÃ© par le frontend avec session/CSRF, code retirÃ© de lâ€™URL ; cookies Strict conservÃ©s et referrer supprimÃ©. Access/refresh tokens jamais exposÃ©s au navigateur. Les renouvellements sont sÃ©rialisÃ©s et persistÃ©s, y compris rotation du refresh token Microsoft ; une dÃ©connexion empÃªche un ancien callback de reconnecter. RÃ´les vÃ©rifiÃ©s Ã  chaque usage, aucune action pour un autre propriÃ©taire. Audits minimaux sans secret, erreurs fournisseur neutralisÃ©es.

Google utilise freeBusy ; Microsoft calendarView (occurrences dÃ©veloppÃ©es, pages contrÃ´lÃ©es). Aucun intitulÃ©, participant ou organisateur privÃ© retournÃ©. Les erreurs, pages excessives ou rÃ©ponses partielles ne donnent jamais un agenda libre. Treize tests fonctionnels/adaptateurs et deux concurrences PostgreSQL ajoutÃ©s ; suite portail de 118 tests (six rÃ©servÃ©s Ã  PostgreSQL), tests ciblÃ©s, migrations et typage/build. Migration portail 0009 appliquÃ©e localement. Configuration et limites dans docs/CALENDARS.md.

Limites : premiÃ¨re Ã©tape connexion/disponibilitÃ© seulement ; crÃ©ation, report, annulation et rÃ©conciliation des rendez-vous externes restent Ã  livrer sÃ©parÃ©ment, les rendez-vous CRM restant internes. Agenda principal uniquement, aucune rÃ©servation par une lecture ; contrÃ´les de disponibilitÃ© ponctuels sans garantie transactionnelle fournisseur. DÃ©connexion locale sans rÃ©vocation du consentement fournisseur ni suppression dâ€™Ã©vÃ©nements. Pas de connexion rÃ©elle validÃ©e sans applications OAuth et comptes de recette du client. Tests HTTP simulÃ©s, aucun appel rÃ©el aux fournisseurs. Exploitation, consentements Google/tenant Microsoft, purge des tentatives et conservation des clÃ©s Ã  valider avant production. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 40 â€” publication des rendez-vous Google/Microsoft

Activation explicite par conseiller Assurance/client Isolation depuis Mon compte et mes sessions. Publication unidirectionnelle des rendez-vous futurs : crÃ©ation, report, retrait aprÃ¨s annulation CRM. Worker sync_calendars et service Docker portal-calendars, synchronisation manuelle, pause, liste paginÃ©e des derniers Ã©tats et erreurs. DÃ©couverte par API mÃ©tier avec ticket du propriÃ©taire, sans accÃ¨s croisÃ© aux bases, bornÃ©e Ã  5000 rendez-vous futurs par connexion/passage ; les sources connues sont Ã©galement relues pour traiter les annulations. Filtre upcoming ajoutÃ© aux visites Isolation avec contrÃ´le de pÃ©rimÃ¨tre.

Ã‰vÃ©nement privÃ© Ã  libellÃ© neutre sans identitÃ©, setter, participant, invitation ou rappel. Marqueur de propriÃ©tÃ©, ETag/If-Match, contrÃ´le prÃ©alable des disponibilitÃ©s excluant le propre Ã©vÃ©nement. Les participants ou changements dâ€™horaires externes bloquent les mises Ã  jour. ClÃ© durable avant Ã©criture et recherche de reprise : pas de nouvelle crÃ©ation aveugle aprÃ¨s une rÃ©ponse incertaine. Les droits rÃ©voquÃ©s arrÃªtent la connexion. Retrait explicite avant remplacement/dÃ©connexion ; rÃ©cupÃ©ration par confirmation de nettoyage manuel avec mot de passe actuel, rÃ©vision et audit atomique. Cette confirmation ne supprime rien Ã  distance.

Quinze tests fonctionnels/adaptateurs et une concurrence PostgreSQL ajoutÃ©s au portail ; un test de filtre Isolation. Suite portail de 134 tests (sept rÃ©servÃ©s Ã  PostgreSQL), tests client Isolation, contrÃ´le des migrations, typage et build frontend. Migration portail 0010. Tests fournisseurs simulÃ©s ; applications OAuth et comptes de recette du client toujours nÃ©cessaires pour valider les consentements rÃ©els.

Limites : agenda principal uniquement, pas de synchronisation bidirectionnelle/webhooks ni dâ€™invitÃ©s. Confirmation CRM et publication externe ne sont pas atomiques ; un conflit externe laisse le rendez-vous interne intact et en erreur de publication. Modifications concurrentes chez le fournisseur possibles entre contrÃ´les. Un Ã©tat incertain impose une vÃ©rification manuelle ; retrait potentiellement partiel. Le registre expose le dernier Ã©tat, les audits gardent les actions techniques. ClÃ©s, worker, ALLOWED_HOSTS internes et configuration OAuth Ã  dÃ©ployer ; aucune preuve de prÃ©sence ou rÃ©sultat mÃ©tier dÃ©duite de lâ€™agenda. Calendly reportÃ©. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 41 â€” chronologie des interactions des fiches Assurance

La fiche prospect rassemble dÃ©sormais une chronologie des notes, documents, rendez-vous enregistrÃ©s, comptes rendus et signalements. Lecture seule, 25 lignes par page, tri stable par date dÃ©croissante puis type/identifiant, filtres par type et intervalle ISO 8601 avec dÃ©calage explicite (bornes incluses). Lâ€™interface permet de filtrer, actualiser et parcourir les pages sans prise en charge du dossier. Les ajouts rÃ©cents apparaissent aprÃ¨s actualisation ; pas de rafraÃ®chissement automatique dans ce lot.

Chaque source est filtrÃ©e cÃ´tÃ© serveur avant union/pagination SQL : conseiller limitÃ© Ã  ses propres notes/documents et rendez-vous ; setter aux notes/documents internes et Ã  ses rendez-vous ; administrateur Ã  lâ€™ensemble du dossier. Le pÃ©rimÃ¨tre de la fiche est vÃ©rifiÃ© avant la lecture, y compris par URL directe. Liste explicite de champs sans auteur, identitÃ© setter, attribution, mÃ©tadonnÃ©e dâ€™import, hash ou contenu binaire. RÃ©ponses sans cache et aucune Ã©criture lors de la consultation. Les corps de notes et comptes rendus dÃ©jÃ  autorisÃ©s sont affichÃ©s comme texte, les documents sont reprÃ©sentÃ©s par leur nom ; leurs tÃ©lÃ©chargements restent dans le parcours documents existant.

Sept tests ajoutÃ©s : cinq sources, confidentialitÃ© inter-conseillers/setters/contacts/espaces, dates et types invalides, bornes incluses, pagination avec dates identiques, absence de modification/audit de lecture et conservation dâ€™un rendez-vous annulÃ©. Suite Assurance de 186 tests (21 rÃ©servÃ©s Ã  PostgreSQL), typage/build frontend, vÃ©rification des migrations et CI PostgreSQL. Aucune migration ni nouvel appel fournisseur.

Limites : chronologie des enregistrements existants, pas un journal exhaustif des modifications. Un rendez-vous apparaÃ®t Ã  sa date de crÃ©ation avec son Ã©tat actuel ; reports, annulations dÃ©taillÃ©es, changements commerciaux et interventions administrateur restent dans leurs journaux dÃ©diÃ©s. Aucune identitÃ© interne rÃ©solue. Appels Phonetico, cycles des mandats/contrats, champs mÃ©tier dÃ©finitifs et rÃ¨gles de visibilitÃ© complÃ©mentaires restent Ã  livrer/valider. La prÃ©sence de cette chronologie ne signifie pas que toutes les fiches mÃ©tier sont terminÃ©es. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 42 â€” partage sÃ©lectif des champs mÃ©tier au conseiller Assurance

**Suivi de livraison : [PR #46](https://github.com/Gi554/callverify/pull/46).** VÃ©rifications locales rÃ©ussies ; validation CI et fusion consultables sur la PR. Lâ€™incident GitHub Actions du 19 octobre 2026 a retardÃ© la validation. Lâ€™utilisateur a autorisÃ© la prÃ©paration isolÃ©e du lot suivant pendant cette attente, sans inverser les fusions.

Lâ€™administration coche Â« Visible au conseiller Â» dans Statuts et champs mÃ©tier pour publier le libellÃ©, le type et la valeur actuelle dâ€™un champ sur les dossiers autorisÃ©s du conseiller. Tous les champs existants et nouveaux restent internes par dÃ©faut ; aucune donnÃ©e existante nâ€™est publiÃ©e par le dÃ©ploiement. Option globale par champ et non par prospect/conseiller. Le setter voit la mention de partage au moment de sa saisie. Le conseiller consulte une section en lecture seule de sa fiche et peut lâ€™actualiser ; aucun accÃ¨s au schÃ©ma complet ou aux commandes de saisie internes nâ€™est ajoutÃ©.

Route dÃ©diÃ©e avec contrÃ´le du rÃ´le et du pÃ©rimÃ¨tre contact existant (affectation directe ou rendez-vous du conseiller). Seuls les champs actifs dont lâ€™option est le boolÃ©en vrai sont retournÃ©s, via une liste de propriÃ©tÃ©s explicite. Champs inconnus, internes, archivÃ©s, configuration des obligations/choix et mÃ©tadonnÃ©es dâ€™auteur/setter restent exclus. Une valeur fausse reste Non et une valeur absente reste Non renseignÃ©. Le retrait du partage ou lâ€™archivage sâ€™applique aux requÃªtes suivantes sans effacer les valeurs conservÃ©es. La modification de visibilitÃ© rÃ©utilise la rÃ©vision de schÃ©ma, le motif obligatoire, le verrou et lâ€™audit atomique de configuration ; la saisie interne reste protÃ©gÃ©e par prise en charge et rÃ©visions.

Sept tests ajoutÃ©s pour dÃ©faut privÃ© historique, valeurs non boolÃ©ennes de configuration, liste de champs, rÃ´les/pÃ©rimÃ¨tres/espaces, lecture seule, retrait/archivage, rÃ©visions, rollback dâ€™audit et mises Ã  jour internes. Suite Assurance de 193 tests (21 rÃ©servÃ©s Ã  PostgreSQL), contrÃ´le des migrations, typage/build frontend et CI PostgreSQL. Aucune migration : option stockÃ©e dans le schÃ©ma JSON existant avec dÃ©faut de refus au niveau de la lecture.

Limites : partage global de champs actifs uniquement ; pas dâ€™exception par dossier, de publication figÃ©e, de notifications ni de synchronisation automatique des Ã©crans dÃ©jÃ  ouverts. Les valeurs dÃ©jÃ  consultÃ©es ne sont pas effacÃ©es du navigateur par une rÃ©vocation ultÃ©rieure. Notes/documents internes, appels et journaux administrateurs ne sont pas partagÃ©s par cette option. Les champs mÃ©tier obligatoires dÃ©finitifs et le cycle mandats/contrats restent Ã  prÃ©ciser. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 43 â€” partage explicite des documents internes Assurance

**Livraison : PR #47 vers staging, puis [PR #48 vers main](https://github.com/Gi554/callverify/pull/48).** Lâ€™utilisateur a autorisÃ© la poursuite pendant lâ€™incident Actions. Le lot 42 a ensuite Ã©tÃ© fusionnÃ© dans main via la PR #46 ; les documents sont passÃ©s par la PR #47 vers staging puis la [PR #48 vers main](https://github.com/Gi554/callverify/pull/48).

Lâ€™administration peut publier un document interne existant vers tous les conseillers ayant accÃ¨s au dossier. Nom de fichier public distinct obligatoire, extension conservÃ©e, motif et confirmation de vÃ©rification du contenu/mÃ©tadonnÃ©es exigÃ©s. Aucun document existant ou nouvel envoi nâ€™est partagÃ© par dÃ©faut. Le fichier original reste immuable, attribuÃ© Ã  son auteur et accessible dans le parcours interne ; publication/retrait modifient seulement une autorisation et un nom public avec rÃ©vision attendue et audit atomique avant/aprÃ¨s. Les documents personnels des conseillers ne peuvent pas Ãªtre publiÃ©s par cette commande.

Liste, tÃ©lÃ©chargement et chronologie utilisent la mÃªme autorisation : le conseiller voit ses propres documents et les documents internes publiÃ©s de ses seuls dossiers. Sur un partage, le nom interne et lâ€™identitÃ© de lâ€™auteur ne sont jamais renvoyÃ©s automatiquement ; lâ€™en-tÃªte de tÃ©lÃ©chargement et la chronologie utilisent le nom public. Le retrait coupe les prochaines requÃªtes sans supprimer le fichier interne. Lâ€™administration contrÃ´le la publication depuis la liste des documents de la fiche, sans nÃ©cessiter de verrou de saisie puisque le contenu du document nâ€™est pas modifiÃ©.

Huit tests fonctionnels et une concurrence PostgreSQL ajoutÃ©s : privÃ© par dÃ©faut, publication/listes/chronologie/tÃ©lÃ©chargement, nom public et confidentialitÃ© des mÃ©tadonnÃ©es applicatives, retrait, rÃ´les/pÃ©rimÃ¨tres, sÃ©paration des fichiers personnels, rÃ©vision, validation de la revue, audit et rollback. Migration Assurance 0020 ajoutant les trois attributs de partage avec valeurs privÃ©es par dÃ©faut. Tests fournisseurs inexistants : aucun service externe sollicitÃ©. Typage/build et suite Assurance de 202 tests (22 rÃ©servÃ©s Ã  PostgreSQL) vÃ©rifiÃ©s avant publication de la PR, y compris le lot 42 prÃ©sent dans staging.

Limites : partage du fichier intÃ©gral Ã  tous les conseillers autorisÃ©s du dossier, sans destinataire individuel ni expiration. La confirmation de revue est humaine : pas de suppression automatique des mÃ©tadonnÃ©es embarquÃ©es, de caviardage ou dâ€™analyse du contenu binaire. Pour un fichier contenant des informations internes, ne pas le publier ; prÃ©parer et dÃ©poser une version expurgÃ©e avant de lâ€™autoriser. RÃ©vocation effective aux prochaines requÃªtes, sans rÃ©cupÃ©ration des copies dÃ©jÃ  tÃ©lÃ©chargÃ©es ni rafraÃ®chissement automatique des Ã©crans. Notes internes non partagÃ©es par ce lot. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 44 â€” version publique des notes internes Assurance

**Suivi de livraison : [PR #49 vers staging](https://github.com/Gi554/callverify/pull/49), puis PR distincte de staging vers main.** PrÃ©paration isolÃ©e autorisÃ©e pendant lâ€™attente de la CI. Les champs et les documents ont Ã©tÃ© livrÃ©s avant les notes ; chaque lot conserve ses vÃ©rifications et ses PR propres.

Lâ€™administration rÃ©dige explicitement une version destinÃ©e aux conseillers autorisÃ©s du dossier, avec confirmation de revue et motif. La zone de rÃ©daction ne reprend pas automatiquement la note interne. Original et auteur restent inchangÃ©s ; seule la copie publique est retournÃ©e au conseiller dans la liste et la chronologie. Aucun partage par dÃ©faut. Les notes personnelles des conseillers restent rÃ©servÃ©es Ã  leur auteur et Ã  lâ€™administration et ne peuvent pas Ãªtre publiÃ©es par cette commande.

Publication et retrait exigent une rÃ©vision attendue et Ã©crivent un audit atomique avant/aprÃ¨s, contenant la version publique prÃ©cÃ©dente. Le retrait efface la copie publique courante sans effacer lâ€™original ni son historique administratif ; une nouvelle publication exige une nouvelle version et revue. Liste sans cache, contrÃ´le du pÃ©rimÃ¨tre contact Ã  chaque requÃªte et absence dâ€™auteur, mÃ©tadonnÃ©e de revue ou texte interne dans les rÃ©ponses conseiller. Aucun champ de partage nâ€™est acceptÃ© par lâ€™ajout de note ordinaire. Lâ€™administrateur utilise les commandes de publication dans la liste des notes de la fiche ; pas de verrou de saisie requis pour gÃ©rer la copie dâ€™une note immuable.

Huit tests fonctionnels et une concurrence PostgreSQL ajoutÃ©s : dÃ©faut privÃ©, copie seule dans liste/chronologie, retrait, original conservÃ©, rÃ´les/espaces/pÃ©rimÃ¨tres, notes personnelles, validation de revue et texte, rÃ©visions, audit et rollback. Migration Assurance 0021 : trois attributs avec partage dÃ©sactivÃ© et copie vide pour lâ€™historique. Suite Assurance de 211 tests (23 rÃ©servÃ©s Ã  PostgreSQL), typage/build et contrÃ´le des migrations avant publication ; aucun fournisseur externe sollicitÃ©.

Limites : publication Ã  tous les conseillers autorisÃ©s du dossier, pas par destinataire ni avec expiration. Revue humaine du texte, sans analyse automatique des identitÃ©s saisies. Lâ€™auteur et le texte internes ne sont jamais copiÃ©s automatiquement, mais lâ€™administration reste responsable du contenu quâ€™elle rÃ©dige. La date prÃ©sentÃ©e est celle de la note originale, pas celle de publication ; les dates de publication/retrait sont dans les audits. Pas de notification, export dÃ©diÃ© ou actualisation automatique des Ã©crans, et aucune rÃ©cupÃ©ration des informations dÃ©jÃ  consultÃ©es. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 45 â€” import des champs personnalisÃ©s Assurance

Lâ€™administrateur associe les colonnes CSV/XLSX aux champs mÃ©tier actifs depuis lâ€™aperÃ§u existant. Mapping mÃ©tier facultatif : aucune association conserve lâ€™import brut sans obligations mÃ©tier ; au moins une association applique la validation de tous les champs actifs, y compris les obligations. BoolÃ©ens oui/non, true/false ou 1/0 (casse ignorÃ©e), dates AAAA-MM-JJ ou cellule Excel date Ã  minuit, choix exacts et textes de 2000 caractÃ¨res maximum. Les coordonnÃ©es restent brutes, sans normalisation, dÃ©doublonnage ni fournisseur externe. Une erreur mÃ©tier rejette la ligne entiÃ¨re avec numÃ©ro physique et motif dans le rapport tÃ©lÃ©chargeable.

RÃ©vision de schÃ©ma prise Ã  lâ€™aperÃ§u, vÃ©rifiÃ©e avant validation puis sous verrou transactionnel Ã  lâ€™insertion. Mapping limitÃ© aux clÃ©s actives et colonnes distinctes, y compris entre coordonnÃ©es et champs mÃ©tier. Historique dâ€™import conservant mapping et rÃ©vision, valeurs typÃ©es sur les nouveaux contacts. Identifiant de requÃªte et empreinte incluent mapping mÃ©tier/rÃ©vision ; reprise exacte reconnue avant revalidation du schÃ©ma, changement de contenu refusÃ©. Aucun changement des contacts existants ou permissions de partage : un champ dÃ©jÃ  rendu visible au conseiller suit le rÃ©glage existant, indiquÃ© au mapping.

Huit tests ajoutÃ©s : CSV/XLSX, types et rapport, obligations et import brut, mapping/revision/champs archivÃ©s, reprise aprÃ¨s changement de schÃ©ma, changement pendant validation, permissions et rollback. Suite Assurance, typage/build et contrÃ´le des migrations ; aucune migration. Limites : premiÃ¨re feuille et bornes du lecteur existant, aucun mapping des colonnes inconnues en nouveaux champs, formule conservÃ©e comme texte et jamais calculÃ©e, pas de mise Ã  jour/dÃ©doublonnage de contacts, pas de dates locales ambiguÃ«s ni de nombres Excel sÃ©riels convertis arbitrairement. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 46 â€” association manuelle des postes Phonetico

Administration centrale â†’ Utilisateurs et accÃ¨s â†’ Postes Phonetico, par espace administrÃ©. Association locale dâ€™un poste numÃ©rique Ã  un compte setter actif, modification et retrait avec rÃ©vision attendue et motif. Un poste unique par compte et un compte unique par poste dans le dÃ©ploiement (hypothÃ¨se un seul PBX). Un compte prÃ©sent dans les deux espaces partage le mÃªme poste ; lâ€™administration de ses deux espaces setter actifs est exigÃ©e pour modifier cette association globale. Suspensions/changements de rÃ´le empÃªchent une nouvelle attribution mais laissent retirer lâ€™ancienne association. Les rÃ©visions sont conservÃ©es aprÃ¨s retrait pour refuser les formulaires anciens. Liste paginÃ©e de 25 comptes et rÃ©ponses sans cache, rÃ©servÃ©es aux administrateurs explicites ; aucun poste exposÃ© au conseiller ni aux API mÃ©tier.

Audits centraux avant/aprÃ¨s avec motif, sans secret fournisseur ; configuration et audit transactionnels. Sept tests fonctionnels ajoutÃ©s : unicitÃ©, rÃ©visions, retrait, pÃ©rimÃ¨tres et rÃ´les, droits multi-espaces, suspension, CSRF, validation stricte et rollback. Un test interdit tout accÃ¨s rÃ©seau pendant les parcours dâ€™association. Migration portail 0011 crÃ©ant le registre privÃ© des associations.

Limites : saisie manuelle non vÃ©rifiÃ©e auprÃ¨s du PBX, un seul PBX, pas de dÃ©tection de nouveaux postes ni crÃ©ation automatique de comptes. Aucune connexion fournisseur, aucun identifiant NEWT stockÃ©, aucune requÃªte 244/343/245 ou autre et strictement aucun appel lancÃ©. Pas de commande dâ€™appel ni lecture des Ã©tats/journaux livrÃ©e ; les tickets mÃ©tier ne contiennent pas le poste. VÃ©rification du poste dans le PBX Ã  la charge de lâ€™administrateur. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 47 â€” annuaire NEWT en lecture seule

Consultation explicite des postes depuis lâ€™administration centrale, rÃ©servÃ©e aux administrateurs des deux espaces car lâ€™annuaire fournisseur est global. Connecteur Ã©troit Ã  hÃ´te HTTPS fixe, fonction 343 seule, CSV, corrÃ©lation hexadÃ©cimale de dix caractÃ¨res ; aucune fonction gÃ©nÃ©rique ou commande dâ€™appel. DÃ©sactivÃ© par dÃ©faut, secrets exclusivement serveur et non renseignÃ©s par la livraison. Aucun appel rÃ©seau automatique, aucune crÃ©ation ou association de compte Ã  partir du rÃ©sultat. Affichage de 25 postes par page avec date ; adresse PBX exclue, noms indicatifs.

Validation stricte et bornes de rÃ©ponse/taille/nombre de postes, refus des rÃ©ponses vides, partielles, doublons et erreurs. TLS, redirections interdites, dÃ©lais et neutralisation des erreurs. AccÃ¨s session/CSRF, quota, sÃ©rialisation via verrou singleton de base centrale, audit du seul nombre de postes consultÃ©s ; pas de conservation de lâ€™annuaire et pas de cache navigateur. Migration portail 0012. Huit tests fonctionnels/adaptateurs et une concurrence PostgreSQL ajoutÃ©s, simulation HTTP uniquement. Documentation de configuration et limites dans docs/PHONETICO.md.

Limites : un seul PBX, aucune connexion rÃ©elle validÃ©e, aucune synchronisation pÃ©riodique ni preuve du titulaire du poste. Lecture 244/511, interprÃ©tation des Ã©tats, rapprochement avec les dossiers, crÃ©ation automatique des comptes et fonctions dâ€™appel non livrÃ©s. Strictement aucun appel lancÃ© et aucune requÃªte NEWT rÃ©elle effectuÃ©e. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 48 â€” consultation manuelle de lâ€™Ã©tat observÃ© NEWT 244

Depuis une association existante de setter actif, lâ€™administration des deux espaces peut consulter lâ€™Ã©tat du poste enregistrÃ©. Activation serveur indÃ©pendante dÃ©sactivÃ©e par dÃ©faut. Lecture uniquement, hÃ´te HTTPS et fonction 244 fixes, aucun paramÃ¨tre navigateur pour la fonction/poste/destination. Pas de polling ni dâ€™action sur un appel existant. MÃªme sÃ©rialisation et quota que lâ€™annuaire ; association relue sous verrou utilisateur pour ne pas interroger un ancien poste aprÃ¨s rÃ©attribution.

CSV strict de huit colonnes, neuviÃ¨me vide finale tolÃ©rÃ©e, poste exact et corrÃ©lation vÃ©rifiÃ©e. Codes R/C/H affichÃ©s bruts et dÃ©dupliquÃ©s, nombre dâ€™observations et date seulement ; destinations, noms, identifiants dâ€™appels/enregistrements exclus et non persistÃ©s. Conclusion toujours IndÃ©terminÃ© : aucun code nâ€™est traduit arbitrairement en disponibilitÃ© du poste ou validitÃ© dâ€™un numÃ©ro. RÃ©ponse vide ou absence dâ€™observation ne signifie pas Libre. RÃ©ponse mal formÃ©e/partielle, code inconnu ou corrÃ©lation non confirmÃ©e : erreur neutralisÃ©e sans rÃ©sultat positif. Audit minimal de consultation et rÃ©ponse sans cache.

Sept tests ajoutÃ©s : confidentialitÃ©, poste cÃ´tÃ© serveur, fonctions arbitraires refusÃ©es, dÃ©sactivation, configuration, rÃ´les/espaces/pÃ©rimÃ¨tre, suspension, CSRF, format/corrÃ©lation/limites et transport 244 uniquement. Tests fournisseur simulÃ©s, aucune requÃªte NEWT rÃ©elle ni appel lancÃ©. Pas de migration, configuration et limites dans docs/PHONETICO.md. InterprÃ©tation fournisseur rÃ©elle, journaux 511, historique et rapprochement CRM non livrÃ©s. Fonctions de composition/raccrochage/DTMF absentes. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 49 â€” diagnostic du format des journaux NEWT 511

PremiÃ¨re Ã©tape technique du futur historique Phonetico : consultation manuelle des en-tÃªtes du rapport 511, empreinte de schÃ©ma et nombre de lignes, sur une pÃ©riode explicite de sept dates maximum non futures. Le PDF ne spÃ©cifie pas les noms de colonnes ni le sens des rÃ©sultats, donc aucune correspondance ou interprÃ©tation nâ€™est inventÃ©e. Aucun appel dÃ©taillÃ© renvoyÃ© ou persistÃ©, aucune attribution Ã  un setter ou une fiche. Lâ€™interface indique explicitement que lâ€™historique mÃ©tier nâ€™est pas encore livrÃ©.

HÃ´te HTTPS et fonction 511 fixes, dates validÃ©es et formatÃ©es cÃ´tÃ© serveur, direction B, corrÃ©lation hexadÃ©cimale. Activation indÃ©pendante dÃ©sactivÃ©e par dÃ©faut. Droits administrateurs des deux espaces, session/CSRF, quota partagÃ©, verrou singleton commun aux lectures NEWT. RÃ©ponse bornÃ©e et CSV strict, refus des lignes partielles, en-tÃªtes vides/dupliquÃ©s ou formats inconnus. Audit de pÃ©riode, nombre de lignes et empreinte seulement. Tests fournisseur simulÃ©s, aucune requÃªte NEWT rÃ©elle et strictement aucun appel lancÃ©.

Huit tests fonctionnels/adaptateurs ajoutÃ©s : listes de champs, absence des donnÃ©es dâ€™appels, dates et fenÃªtres invalides, rÃ´les et CSRF, configuration, paramÃ¨tres arbitraires interdits, erreurs, limites et transport 511 seul. Suite portail, typage/build et contrÃ´le des migrations ; aucune migration. Limites : schÃ©ma rÃ©el, fuseau PBX et sÃ©mantique des bornes/statuts restent Ã  confirmer avant ingestion et rapprochement. ZÃ©ro ligne ne prouve pas lâ€™absence dâ€™activitÃ©. Aucun export brut ni historique CRM livrÃ© par cette base technique. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 50 â€” registre administratif des mandats et contrats Assurance

Depuis la fiche Assurance, lâ€™administrateur crÃ©e un suivi de type Mandat ou Contrat avec rÃ©fÃ©rence obligatoire, dates de dÃ©but/fin facultatives et Ã©tat interne Brouillon, En suivi ou ArchivÃ©. Le type reste immuable ; rÃ©fÃ©rence, dates et Ã©tat sont modifiables avec motif. Pas de suppression, archivage rÃ©versible. UnicitÃ© exacte de la rÃ©fÃ©rence par dossier/type, sans normalisation automatique de casse. Le registre, ses commandes et ses historiques sont interdits aux setters/conseillers et Ã  Isolation, y compris par URL directe. Aucun changement des rÃ¨gles de visibilitÃ© post-contrat existantes.

CrÃ©ation/modification protÃ©gÃ©es par prise en charge, jeton et rÃ©vision du contact, plus rÃ©vision de lâ€™enregistrement lors dâ€™une modification. Historique administratif paginÃ© avec acteur, date, motif et valeurs avant/aprÃ¨s. IncrÃ©ment de rÃ©vision contact et audit atomiques, rollback complet en cas dâ€™Ã©chec ; une sauvegarde sans changement nâ€™ajoute pas dâ€™Ã©vÃ©nement. Identifiant de crÃ©ation rejouable avec contenu/acteur identiques sans doublon ; la reprise retourne lâ€™Ã©tat courant, sans refaire une crÃ©ation, mÃªme si le verrou initial a expirÃ©. RÃ©utilisation avec un autre contenu/acteur refusÃ©e. Liste et historique sans cache, 25 lignes par page.

Neuf tests fonctionnels et deux concurrences PostgreSQL ajoutÃ©s : crÃ©ation/modification de donnÃ©es/archivage/rÃ©ouverture, sÃ©paration du statut commercial et des accÃ¨s, pÃ©rimÃ¨tres, lease/rÃ©visions, dates, identifiant de reprise, rÃ©fÃ©rences, liste/historique, refus de suppression et rollback crÃ©ation/modification. Migration Assurance 0022. Suite Assurance, typage/build et contrÃ´le des migrations avant livraison. Aucun appel ou service externe sollicitÃ©.

Limites : registre de suivi administratif seulement, aucun Ã©tat de signature/validitÃ© juridique, automatisation de pipeline, modÃ¨le de contrat, montant, versement, document liÃ© ou signature Ã©lectronique. Ã‰tats de suivi libres entre les trois valeurs ; ils ne dÃ©montrent pas un engagement contractuel. Dates sans fuseau et fin possible sans dÃ©but, car ces donnÃ©es sont facultatives ; lâ€™ordre est contrÃ´lÃ© quand les deux sont prÃ©sentes. Cycle mÃ©tier dÃ©finitif, documents associÃ©s, montants/versements et visibilitÃ© conseiller restent des lots sÃ©parÃ©s Ã  cadrer. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 51 â€” piÃ¨ces liÃ©es aux mandats et contrats Assurance

**PÃ©rimÃ¨tre confirmÃ© par lâ€™utilisateur : aucune fonction financiÃ¨re sur Assurance ou Isolation.** Les anciennes mentions de montants/versements parmi les pistes futures sont abandonnÃ©es ; elles ne reprÃ©sentent aucun dÃ©veloppement rÃ©alisÃ© ni prÃ©vu.

Depuis un suivi administratif, lâ€™administrateur associe un document interne existant de la mÃªme fiche ou retire ce lien avec un motif. Le fichier nâ€™est ni copiÃ© ni supprimÃ© ; son contenu, auteur et rÃ¨gle de partage conseiller restent inchangÃ©s. Les documents personnels des conseillers ne sont pas associables. Une mÃªme piÃ¨ce peut Ãªtre liÃ©e Ã  plusieurs suivis de son dossier ; maximum 50 liens actifs par suivi, listes des piÃ¨ces liÃ©es et disponibles paginÃ©es par 25. TÃ©lÃ©chargement depuis le registre via la route documentaire privÃ©e existante.

CrÃ©ation/retrait des liens soumis Ã  prise en charge, jeton, rÃ©vision de fiche et rÃ©vision de suivi. Liens dÃ©sactivÃ©s puis rÃ©activables sans doublon, historique avant/aprÃ¨s incluant les identifiants des documents, motif, acteur et date via le journal administratif du suivi. IncrÃ©ment des deux rÃ©visions et audit atomiques ; une action sans changement ne produit aucun Ã©vÃ©nement et une ancienne version est refusÃ©e. Liste sans cache ; mÃªmes droits administrateur Assurance et refus dâ€™Isolation/setters/conseillers que le registre. Aucun accÃ¨s supplÃ©mentaire aux fichiers ni changement de visibilitÃ© liÃ© au mandat/contrat.

Huit tests fonctionnels et une concurrence PostgreSQL ajoutÃ©s : association/retrait/rÃ©association, donnÃ©es et partage prÃ©servÃ©s, documents personnels et autre fiche refusÃ©s, pÃ©rimÃ¨tres, lease/rÃ©visions, audit/rollback, pagination et limite de 50. Migration Assurance 0023. Suite Assurance, typage/build et contrÃ´le des migrations avant livraison ; aucun appel ni service externe sollicitÃ©.

Limites : liaison des piÃ¨ces internes dÃ©jÃ  prÃ©sentes, sans tÃ©lÃ©versement spÃ©cifique, gÃ©nÃ©ration de contrat, signature ou cycle juridique automatique. Lâ€™historique contient les rÃ©fÃ©rences des piÃ¨ces, pas de copie binaire du fichier ; les originaux restent protÃ©gÃ©s contre suppression par les liens. Le retrait du lien nâ€™annule pas un partage conseiller dÃ©jÃ  accordÃ© sÃ©parÃ©ment. Suivis archivÃ©s modifiables selon la rÃ¨gle existante, aucun gel juridique dÃ©duit. Revue esthÃ©tique diffÃ©rÃ©e.

## FonctionnalitÃ© 52 â€” liste centrale des mandats et contrats Assurance

Module Mandats et contrats accessible Ã  lâ€™administrateur depuis la navigation Assurance. Liste de 25 suivis par page, ordre des derniÃ¨res modifications puis identifiant dÃ©croissant pour dÃ©partager les dates identiques. Recherche par rÃ©fÃ©rence ou nom du prospect, combinable avec type Mandat/Contrat, Ã©tat Brouillon/En suivi/ArchivÃ© et bornes inclusives sur dates de dÃ©but et de fin. Les filtres de date excluent les valeurs non renseignÃ©es et les bornes inversÃ©es sont refusÃ©es. Pas de tri, taille de page ou champ de recherche arbitraire cÃ´tÃ© navigateur ; filtres inconnus/rÃ©pÃ©tÃ©s et dates invalides refusÃ©s.

Colonnes de rÃ©fÃ©rence, prospect minimal (id/nom), type, Ã©tat, dates et nombre de piÃ¨ces actives, sans mÃ©tadonnÃ©es de setter, contenu documentaire, coordonnÃ©es ou champs privÃ©s. La commande Ouvrir la fiche charge le parcours existant, avec ses protections de prise en charge/rÃ©visions et son registre administratif. Retour Ã  la liste avec actualisation aprÃ¨s fermeture/modification. Aucun nouveau droit conseiller/setter et aucun pÃ©rimÃ¨tre Isolation ; route serveur de lecture seule, rÃ©ponse sans cache et aucune Ã©criture/audit dÃ©clenchÃ©e par une consultation.

Sept tests fonctionnels ajoutÃ©s : listes explicites et compteur de piÃ¨ces, recherche/filtres combinÃ©s, dates inclusives et valeurs absentes, filtres invalides/rÃ©pÃ©tÃ©s, rÃ´les/espaces, pagination avec dates Ã©gales et ouverture de fiche autorisÃ©e. Suite Assurance, contrÃ´le des migrations, typage/build et CI ; aucune migration. Aucun appel ni service externe sollicitÃ©.

Limites : registre administratif rÃ©servÃ© Ã  lâ€™administrateur, aucun export, action en masse, alerte dâ€™Ã©chÃ©ance ou changement de statut depuis la liste. Revue esthÃ©tique globale inspirÃ©e de GoHighLevel reportÃ©e Ã  la revue finale ; module ajoutÃ© dans la navigation fonctionnelle existante, fiche de dÃ©tail existante rÃ©utilisÃ©e. Toutes fonctions financiÃ¨res exclues sur les deux plateformes.

## FonctionnalitÃ© 53 â€” alertes dâ€™Ã©chÃ©ance des mandats et contrats

Encart administratif Assurance prÃ©sentant les suivis En suivi dont la date de fin est dÃ©passÃ©e, ceux arrivant Ã  Ã©chÃ©ance dans les 30 prochains jours (aujourdâ€™hui et borne finale inclus), et ceux sans date de fin. Brouillons et archivÃ©s exclus des compteurs. Calcul au jour UTC affichÃ© explicitement ; date passÃ©e strictement avant aujourdâ€™hui, aucun changement de statut ou dÃ©duction de validitÃ© juridique. Consultation persistante tant que les donnÃ©es justifient lâ€™alerte, sans acquittement implicite ni Ã©criture de lecture. Actualisation manuelle, toutes les 60 secondes si la page est visible, et aprÃ¨s modification depuis la liste centrale.

Les commandes ouvrent la liste centrale avec le filtre appropriÃ©. La liste propose les horizons 7/30/90 jours et badges textuels colorÃ©s pour Ã©chÃ©ance proche, date dÃ©passÃ©e, date manquante ou hors suivi. Nombre de jours calculÃ© cÃ´tÃ© serveur. Filtres combinables avec rÃ©fÃ©rence/prospect/type/Ã©tat/dates ; compteurs de liste calculÃ©s selon les filtres courants hors filtre alerte, Ã  la diffÃ©rence de lâ€™encart global. Les vues dâ€™alerte trient par date de fin puis identifiant ; la pagination de 25 reste inchangÃ©e. Aucune donnÃ©e personnelle dans les compteurs globaux. RÃ´les/pÃ©rimÃ¨tres administrateur Assurance inchangÃ©s et rÃ©ponses sans cache.

Sept tests ajoutÃ©s : bornes et horizons, absences de date/archivage/brouillons, persistance sans modification ni audit, filtres combinÃ©s, jours/badges, compteurs non multipliÃ©s par les piÃ¨ces, droits et paramÃ¨tres invalides, recalcul aprÃ¨s modification et changement de date UTC. Suite Assurance, typage/build et contrÃ´le des migrations ; aucune migration ni tÃ¢che serveur nÃ©cessaire. Aucun fournisseur externe ou appel sollicitÃ©.

Limites : alertes internes dÃ©rivÃ©es des dates renseignÃ©es et de lâ€™Ã©tat En suivi, sans e-mail, notification systÃ¨me, tÃ¢che de traitement ou horodatage dâ€™acquittement. Horizon choisi dans la vue, non paramÃ©trage global persistant. Pas de prise en compte dâ€™un fuseau client ou dâ€™heures dans les dates administratives. Une page laissÃ©e ouverte mais non visible nâ€™est actualisÃ©e quâ€™au prochain passage visible de la minuterie ou manuellement. Aucune fonction financiÃ¨re sur les deux plateformes. Revue esthÃ©tique globale diffÃ©rÃ©e.

## FonctionnalitÃ© 54 â€” export Excel du registre administratif Assurance

Lâ€™administrateur tÃ©lÃ©charge un fichier .xlsx depuis Mandats et contrats. Tous les filtres saisis (recherche rÃ©fÃ©rence/prospect, type, Ã©tat, bornes de dates, alerte et horizon 7/30/90 jours) sont repris, ainsi que le tri du registre, indÃ©pendamment de la pagination. Validation et construction de la requÃªte partagÃ©es avec la liste pour Ã©viter deux dÃ©finitions des rÃ©sultats. Limite de 10 000 suivis : dÃ©passement refusÃ© explicitement, sans fichier tronquÃ©. Les paramÃ¨tres inconnus, rÃ©pÃ©tÃ©s et la pagination sont refusÃ©s Ã  lâ€™export.

Feuille principale : rÃ©fÃ©rence, nom et identifiant de fiche, type et Ã©tat en franÃ§ais, dates Excel au format jour/mois/annÃ©e, libellÃ© dâ€™Ã©chÃ©ance, jours calendaires avant fin et nombre de piÃ¨ces actives. En-tÃªtes figÃ©s, filtres Excel et largeurs lisibles. Feuille PÃ©rimÃ¨tre : date de rÃ©fÃ©rence UTC, nombre de rÃ©sultats et filtres utilisÃ©s, limites administratives. Aucun fichier joint, tÃ©lÃ©phone, note privÃ©e, champ personnalisÃ© ou auteur inclus. ChaÃ®nes explicitement enregistrÃ©es comme texte, jamais comme formules ; caractÃ¨res de contrÃ´le XML incompatibles remplacÃ©s par le caractÃ¨re de remplacement. RÃ©ponse privÃ©e sans cache, tÃ©lÃ©chargement via ticket mÃ©tier existant. Aucune mutation, aucun appel ni fournisseur externe.

Sept tests dâ€™export : toutes les pages et confidentialitÃ©, cohÃ©rence des filtres/tri et dates, Ã©chÃ©ances/horizon, formules littÃ©rales, limite exacte et dÃ©passement, droits/paramÃ¨tres stricts et caractÃ¨res XML. Suite Assurance, contrÃ´le des migrations, typage/build et CI avant fusion ; aucune migration.

Limites : export ponctuel des donnÃ©es au moment de la requÃªte, pas un journal immuable ou une sauvegarde documentaire. Les filtres saisis peuvent diffÃ©rer de la derniÃ¨re recherche affichÃ©e ; ce comportement est annoncÃ© prÃ¨s du bouton. Pas dâ€™export financier, de coordonnÃ©es ou de piÃ¨ces binaires. Revue esthÃ©tique globale toujours diffÃ©rÃ©e.

## FonctionnalitÃ© 55 â€” statistiques administratives des mandats et contrats

La liste centrale affiche une synthÃ¨se des rÃ©sultats de la derniÃ¨re recherche appliquÃ©e : nombre total, rÃ©partition Mandat/Contrat, rÃ©partition Brouillon/En suivi/ArchivÃ© et rÃ©partition des Ã©chÃ©ances (dÃ©passÃ©e, proche, manquante, ultÃ©rieure, hors suivi). Les filtres du registre, y compris alerte et horizon 7/30/90 jours, sâ€™appliquent intÃ©gralement ; toutes les pages sont comptÃ©es. Chaque rÃ©partition est exhaustive et exclusive, aucune multiplication des suivis par leurs documents. Brouillons et archivÃ©s sont Hors suivi ; les autres catÃ©gories concernent uniquement En suivi. Date de rÃ©fÃ©rence UTC affichÃ©e et bornes identiques aux alertes existantes.

Calcul serveur en agrÃ©gats, mÃªmes droits administrateur Assurance et refus des autres rÃ´les/espaces, aucune identitÃ© ou coordonnÃ©e dans les statistiques. RÃ©ponse du registre existante enrichie, sans nouvelle route ni migration. La synthÃ¨se est effacÃ©e pendant le chargement et en cas dâ€™erreur, et actualisÃ©e par les commandes existantes de recherche/rafraÃ®chissement et aprÃ¨s modification de fiche. Les compteurs dâ€™alerte prÃ©existants restent explicitement calculÃ©s hors filtre dâ€™alerte ; la nouvelle synthÃ¨se inclut ce filtre.

Cinq tests ajoutÃ©s : totaux rÃ©conciliÃ©s et bornes UTC, filtres combinÃ©s/horizon, rÃ©sultats vides/confidentialitÃ©, indÃ©pendance de la pagination et des jointures documentaires, droits/paramÃ¨tres invalides. Suite Assurance, contrÃ´le des migrations, typage/build et CI avant fusion. Aucune Ã©criture, aucun appel ni accÃ¨s fournisseur.

Limites : photographie des Ã©tats administratifs courants, sans historique temporel, conversion commerciale, valeur financiÃ¨re ou validation juridique. Les requÃªtes de lecture ne constituent pas un instantanÃ© transactionnel immuable en prÃ©sence de modifications simultanÃ©es. SynthÃ¨se affichÃ©e uniquement dans le registre ; lâ€™export Excel existant conserve ses lignes et sa feuille PÃ©rimÃ¨tre sans nouvelle feuille statistique. Revue esthÃ©tique finale diffÃ©rÃ©e.

## Lot 56 â€” recette automatisÃ©e transversale du registre Assurance

Deux scÃ©narios de non-rÃ©gression traversent les API rÃ©elles dâ€™import CSV/XLSX, aperÃ§u/confirmation/rejeu, recherche et correction sous verrou, crÃ©ation/rejeu du contrat, tÃ©lÃ©versement/rejeu et liaison dâ€™une piÃ¨ce interne, tÃ©lÃ©chargement, liste filtrÃ©e, statistiques, contenu Excel, archivage, historique, conflit de version et libÃ©ration. ContrÃ´le du maintien des documents privÃ©s et refus du registre/export au conseiller affectÃ©. DonnÃ©es synthÃ©tiques en mÃ©moire, base de test jetable, aucune purge de la base locale et aucune requÃªte fournisseur autorisÃ©e par les scÃ©narios.

Aucun dÃ©faut reproduit sur ces deux parcours : ce lot ajoute une couverture transversale et ne prÃ©tend pas livrer une nouvelle fonction mÃ©tier. Guide de recette reproductible dans docs/RECETTE_ASSURANCE_CONTRATS.md, avec commande et checklist navigateur. Suite Assurance et CI avant fusion. Aucune migration ni modification de comportement applicatif.

Limites : API et contenu XLSX vÃ©rifiÃ©s automatiquement ; session centrale, clics, tÃ©lÃ©chargement natif et rendu visuel ne sont pas couverts par ces tests. La checklist navigateur reste Ã  exÃ©cuter et la revue esthÃ©tique finale demeure diffÃ©rÃ©e. Aucune recette rÃ©elle Phonetico, OAuth ou SMTP rÃ©alisÃ©e dans ce lot.

## Lot 57 â€” recette navigateur administrateur et conseiller Assurance

Recette rÃ©elle du parcours central de connexion, import CSV, correction sous prise en charge, contrat, ajout/liaison/tÃ©lÃ©chargement dâ€™une piÃ¨ce interne, liste/statistiques filtrÃ©es, tÃ©lÃ©chargement Excel et archivage/historique. Fichier effectivement tÃ©lÃ©chargÃ© contrÃ´lÃ© localement : rÃ©fÃ©rence, jours avant fin et compteur documentaire cohÃ©rents, coordonnÃ©es privÃ©es exclues. AprÃ¨s archivage, disparition des Ã©chÃ©ances proches et classement Hors suivi vÃ©rifiÃ©s dans lâ€™interface. Connexion conseiller avec une fiche synthÃ©tique prÃ©affectÃ©e : module administratif absent et piÃ¨ce interne non visible, aucun partage implicite. Rapport dÃ©taillÃ© et limites dans docs/RECETTE_ASSURANCE_CONTRATS.md.

Instance temporaire avec bases et comptes sÃ©parÃ©s, donnÃ©es synthÃ©tiques, aucun fournisseur activÃ© ; dÃ©connexion puis arrÃªt des services de recette. Captures, fichiers et secrets hors Git. Aucun dÃ©faut applicatif reproduit : lot documentaire, sans modification de comportement ou migration. ContrÃ´les CI avant fusion.

Limites : entrÃ©e XLSX et refus des routes directes restent couverts par les tests API, pas par ce parcours navigateur ; affectation conseiller prÃ©parÃ©e dans la base de recette, pas validÃ©e par clics ; lecture graphique Excel/LibreOffice, recette des fournisseurs et revue esthÃ©tique finale non effectuÃ©es. Ce lot ne dÃ©clare pas le projet complet.

## FonctionnalitÃ© 58 â€” sauvegarde locale chiffrÃ©e et restauration SQLite isolÃ©e

Outil opÃ©rateur scripts/crm_backup.py : gÃ©nÃ©ration dâ€™une clÃ© dans un fichier neuf sans affichage, sauvegarde explicite des trois bases locales et dâ€™un dossier mÃ©dia privÃ©, vÃ©rification et restauration vers un dossier neuf exclusivement. Snapshots SQLite en mÃ©moire via lâ€™API backup, WAL validÃ© compris ; documents binaires Assurance dans leur base et fichiers privÃ©s Isolation dans lâ€™archive. ZIP et manifeste entiÃ¨rement chiffrÃ©s/authentifiÃ©s Fernet, pas de fichier intermÃ©diaire en clair. Inventaire, tailles, empreintes, intÃ©gritÃ© SQLite, rÃ©fÃ©rences et nombres de lignes par table vÃ©rifiÃ©s avant toute restauration. DÃ©chiffrement/restauration ne lance aucun service ou fournisseur.

Sources distinctes et existantes, clÃ©/archive hors mÃ©dia, liens/jonctions/noms non portables refusÃ©s. Attestation explicite de services/Ã©critures arrÃªtÃ©s pour cohÃ©rence entre bases et fichiers sÃ©quentiels. Refus dâ€™Ã©craser archive, clÃ© ou dossier cible existant. Nettoyage du seul nouveau dossier cible en cas dâ€™erreur dâ€™Ã©criture. Limites locales : 256 Mio de contenu, 10 000 fichiers, manifeste de 1 Mio ; travail en mÃ©moire et aucune gestion automatique de gros volumes. RÃ©pertoire .backups ignorÃ© par Git. Commandes, conservation indÃ©pendante des clÃ©s et prÃ©cautions de reprise dans docs/BACKUP_LOCAL.md.

Dix tests ajoutÃ©s couvrant aller-retour, documents binaires/mÃ©dias, WAL, Ã©crasement/source prÃ©servÃ©e, clÃ©/altÃ©ration/empreintes/comptages, paramÃ¨tres/limites, chemins/liens, erreur disque et CLI. Le test de lien est ignorÃ© sur le Windows sans privilÃ¨ge de crÃ©ation ; exÃ©cutÃ© en CI Linux. Recette rÃ©elle des commandes sur trois bases Django migrÃ©es jetables : adhÃ©sion centrale, contrat/piÃ¨ce liÃ©e et octets Assurance, import et mÃ©dia Isolation restaurÃ©s puis contrÃ´lÃ©s. Suite core et CI avant fusion. Aucune base active modifiÃ©e ni service externe sollicitÃ©.

Limites : outil local SQLite, pas PostgreSQL/S3/Redis, pas de copie hors site, rotation ou planification ; aucun module de production complet dÃ©clarÃ©. Attestation dâ€™arrÃªt non vÃ©rifiable automatiquement ; droits Windows hÃ©ritÃ©s du dossier privÃ© (pas de configuration ACL par cet outil). ClÃ©s applicatives Ã  conserver sÃ©parÃ©ment ; tÃ¢ches et sessions restaurÃ©es inchangÃ©es, ordonnanceurs/fournisseurs Ã  laisser arrÃªtÃ©s jusquâ€™Ã  dÃ©cision explicite de reprise. Promotion des fichiers vers les chemins actifs non automatisÃ©e ; recette mÃ©tier isolÃ©e encore nÃ©cessaire aprÃ¨s restauration. Prochaine tranche : sauvegarde/restauration PostgreSQL et stockage externe de production.

## FonctionnalitÃ© 59 â€” dump PostgreSQL chiffrÃ© et restauration de contrÃ´le

Outil opÃ©rateur unitaire scripts/crm_pg_backup.py : source/service explicites, connexion libpq privÃ©e, dump custom sans fichier intermÃ©diaire en clair, chiffrement Fernet avec manifeste, empreinte et comptages par table. VÃ©rification de lâ€™archive et restauration sur base neuve prÃ©fixÃ©e crm_restore_, jamais une source existante. CREATE DATABASE exclusif, retrait de CONNECT/TEMPORARY Ã  PUBLIC, restauration transactionnelle sans propriÃ©taires/droits dâ€™origine, rapprochement des compteurs. Aucune commande DROP dans lâ€™outil ; cible conservÃ©e pour diagnostic en cas dâ€™Ã©chec. Aucun dÃ©marrage de service ni appel fournisseur.

Cinq tests simulÃ©s et une recette rÃ©elle PostgreSQL 17 dans la CI : base alÃ©atoire, relations, BYTEA et sÃ©quences, sauvegarde chiffrÃ©e, restauration dans une autre base alÃ©atoire, source prÃ©servÃ©e et cible existante refusÃ©e. Les clients officiels 17 sont installÃ©s dans ce job. Validation rÃ©elle locale indisponible (Docker arrÃªtÃ©, clients PostgreSQL absents) ; rÃ©sultat de la recette CI requis avant fusion. Documentation BACKUP_POSTGRES et OPERATIONS avec commandes et limites. Note de recette Phonetico actualisÃ©e : appel manuel demandÃ© confirmÃ© par lâ€™utilisateur, dÃ©tail 511 toujours HTTP 500 ; aucune fonctionnalitÃ© dâ€™appel automatique ou historique mÃ©tier dÃ©clarÃ©e livrÃ©e.

Limites : une base Ã  la fois (rÃ©pÃ©ter pour chaque service), attestation de maintenance, dump plafonnÃ© Ã  256 Mio et dÃ©lai de 120 secondes. Les comptages ne remplacent pas la recette mÃ©tier et verify ne remplace pas une restauration. Hors pÃ©rimÃ¨tre : mÃ©dias/S3, copie externe, rotation/planification, sauvegarde des rÃ´les globaux, PITR et recette de lâ€™infrastructure client. La prochaine tranche reste la copie externe et les mÃ©dias privÃ©s. Aucun changement esthÃ©tique.

## Lot 60 â€” audit des API face au cahier des charges

Relecture du cahier CRM AMX v1.0 du 18 octobre, comparaison des routes centrales/Assurance/Isolation, rÃ¨gles et tests existants. Matrice dans docs/AUDIT_API_CAHIER_DES_CHARGES.md distinguant dÃ©veloppÃ©/testÃ©, partiel, manquant, recette fournisseur et report explicite. Plan initial marquÃ© historique pour Ã©viter de confondre ses premiÃ¨res tranches avec lâ€™Ã©tat actuel. Audit statique et preuves historiques CI/navigateur, sans nouveau test fournisseur ou dÃ©claration de nouvelle recette exhaustive.

Ã‰carts confirmÃ©s : click-to-call Phonetico mÃ©tier absent malgrÃ© le test manuel rÃ©ussi ; CDR 511 bloquÃ© HTTP500 ; contrÃ´le dâ€™agenda externe non intÃ©grÃ© Ã  la confirmation de rÃ©servation ; MFA centrale absente et limitation distribuÃ©e Ã  terminer ; statistiques internes partielles et cycle contractuel administratif seulement. Google/Microsoft et SMTP diffÃ©renciÃ©s des fonctions absentes : connecteurs prÃ©sents, recette rÃ©elle encore requise. Finances exclues, Calendly et stockage externe reportÃ©s. Brouillons de copie externe conservÃ©s dans private-media/deferred-remote-backup hors Git, non livrÃ©s et retirÃ©s des modules de tests actifs.

Aucune nouvelle API ni interface livrÃ©e par ce lot documentaire. Ordre proposÃ© : click-to-call Assurance puis Isolation, rÃ©servation avec contrÃ´le externe, sÃ©curitÃ© centrale, statistiques mÃ©tier et rÃ¨gles contractuelles Ã  cadrer. La refonte esthÃ©tique reste distincte. Chaque fonctionnalitÃ© suivra tests, commit, push, PR et fusion avant la suivante.

## FonctionnalitÃ© 61 â€” click-to-call Assurance cÃ´tÃ© serveur

Autorisation dâ€™appel depuis une fiche sous prise en charge par le setter actif connectÃ©, preuve signÃ©e 60 secondes liÃ©e au dossier/version/numÃ©ro/jeton/UUID, puis endpoint central utilisant uniquement le poste associÃ© Ã  ce compte. Destination arbitraire, extension, fonction fournisseur, administrateur agissant pour un setter et conseiller refusÃ©s. Relecture mÃ©tier serveur-Ã -serveur avant Ã©mission ; coordonnÃ©es Assurance originales inchangÃ©es et aucune validation Lookup introduite. Registre durable avant rÃ©seau, idempotence par UUID/contenu, sÃ©rialisation par compte et espacement 60 secondes entre commandes distinctes. Consultation privÃ©e dâ€™une commande existante sans rÃ©Ã©mission. Flag NEWT_CALLS_ENABLED=false par dÃ©faut.

Adaptateur 245 unitaire sans auto-answer/retry/redirection, rÃ©ponse CSV corrÃ©lÃ©e bornÃ©e. AcceptÃ© signifie uniquement commande reÃ§ue ; rejetÃ©, bloquÃ©, indÃ©terminÃ© et rÃ©servation en cours distinguÃ©s. Interruption/rÃ©sultat ambigu jamais relancÃ©s automatiquement. Audit minimal Assurance et central, extension conservÃ©e cÃ´tÃ© serveur seulement, pas de secrets/preuves/numÃ©ros dans les audits. Migration portail 0013 ; aucune migration Assurance. Contrat API et commandes dans docs/ASSURANCE_CLICK_TO_CALL.md.

Cinq tests Assurance et douze tests portail/adaptateur, plus une concurrence PostgreSQL (double soumission, une seule Ã©mission simulÃ©e). Suites locales : 272 tests Assurance dont 26 rÃ©servÃ©s PostgreSQL, 178 portail dont 9 rÃ©servÃ©s PostgreSQL. CI et migrations Ã  contrÃ´ler avant fusion. Aucun appel rÃ©el ou flag activÃ© pendant cette livraison.

Limites : API backend, aucun nouveau bouton frontend ; Isolation non couverte, pas de raccrochage ou historique CDR, ni audio WebRTC. VÃ©rification distribuÃ©e instantanÃ©e, sans atomicitÃ© entre bases aprÃ¨s le dernier contrÃ´le ; dÃ©lai entre demandes ne garantit pas la disponibilitÃ© du poste. RÃ©servation interrompue conservÃ©e pour examen manuel, pas de rÃ©solution fournisseur automatique. Retention Ã  prÃ©ciser ; timeline et audit central non fusionnÃ©s en historique dâ€™appels du dossier. Recette rÃ©elle des nouveaux endpoints encore Ã  effectuer sur autorisation explicite. Prochaine fonctionnalitÃ© : Ã©quivalent Isolation sur les prospects attribuÃ©s.

## FonctionnalitÃ© 62 â€” client Isolation unique permanent

Correction explicite du pÃ©rimÃ¨tre utilisateur : Isolation comporte un seul client de faÃ§on permanente, pas uniquement au lancement. Contrainte unique conditionnelle en base centrale sur le rÃ´le client Isolation, indÃ©pendante de lâ€™activation du compte ou de lâ€™accÃ¨s. DÃ©sactiver le compte ou suspendre lâ€™adhÃ©sion ne libÃ¨re donc pas de place pour un second client. Administration API et commande grant_workspace refusent le changement de rÃ´le du client existant ; suspension/rÃ©activation du mÃªme accÃ¨s possibles. CrÃ©ation, promotion dâ€™un setter, invitation, renvoi et acceptation contrÃ´lÃ©s ; une ancienne invitation incompatible ne crÃ©e aucun compte orphelin et peut Ãªtre rÃ©voquÃ©e. Assurance reste indÃ©pendante avec plusieurs conseillers autorisÃ©s.

Migration portail 0014 : vÃ©rification prÃ©alable des adhÃ©sions client existantes (y compris suspendues), puis contrainte. Si plusieurs lignes existent, migration refusÃ©e avec explication et sans suppression ou choix automatique du client. Une correction explicite des donnÃ©es historiques est nÃ©cessaire dans ce cas. Sept tests ajoutÃ©s : contrainte, compte orphelin, promotion, suspension/rÃ©activation, conseillers multiples, invitations et commande, ainsi que prÃ©contrÃ´le de migration (certains regroupÃ©s en scÃ©narios). La visibilitÃ© existante original_setter et les auteurs des activitÃ©s partagÃ©es Isolation sont conservÃ©s. Tests client/visites/activitÃ©/statistiques Isolation rÃ©exÃ©cutÃ©s, CI avant fusion.

Limites : un compte central de rÃ´le client Isolation, rÃ©servÃ© mÃªme suspendu, aucun mÃ©canisme dâ€™organisation multi-client ni de transfert/remplacement livrÃ©. Une suppression ou modification SQL directe de lâ€™adhÃ©sion par un opÃ©rateur privilÃ©giÃ© nâ€™est pas un parcours autorisÃ© par lâ€™API et peut invalider cette rÃ¨gle ; les API nâ€™exposent pas de suppression de compte. Les fichiers/activitÃ©s restent soumis Ã  leurs rÃ¨gles de partage existantes : connaÃ®tre les auteurs ne publie pas toutes les notes privÃ©es. Aucun changement dâ€™interface, appel ou fournisseur. Le click-to-call Isolation reste la tranche suivante.

## FonctionnalitÃ© 63 â€” click-to-call Isolation cÃ´tÃ© serveur

Autorisation unitaire rÃ©servÃ©e au setter affectÃ© : preuve signÃ©e 60 secondes liÃ©e au prospect, rÃ©vision, compte, numÃ©ro et UUID. ConformitÃ© administrative allowed, tÃ©lÃ©phone normalisÃ© nord-amÃ©ricain, validitÃ© non invalide et exclusions contrÃ´lÃ©s, puis relus avant Ã©mission. Aucune destination ou extension arbitraire. ValiditÃ© inconnue non transformÃ©e en ligne active ; aucun Lookup ni modification des rÃ©sultats techniques. Client unique permanent et auteurs existants prÃ©servÃ©s.

Registre central partagÃ© avec Assurance mais cloisonnÃ© par espace et propriÃ©taire, idempotence et dÃ©lai commun 60 secondes par compte. Migration 0015 attribuant les anciens enregistrements Ã  Assurance. Double activation nÃ©cessaire : NEWT_CALLS_ENABLED et NEWT_ISOLATION_CALLS_ENABLED, tous deux false par dÃ©faut. Adaptateur 245 existant sans auto-answer/retry rÃ©utilisÃ©. Documentation et commandes dans docs/ISOLATION_CLICK_TO_CALL.md.

Six tests core et cinq portail ajoutÃ©s. Suites locales : 174 core (17 rÃ©servÃ©s PostgreSQL), 190 portail (9 rÃ©servÃ©s PostgreSQL), cinq tests mÃ©tier Assurance de rÃ©gression rÃ©ussis ; migrations cohÃ©rentes. CI PostgreSQL avant fusion. Aucun appel rÃ©el, secret ajoutÃ© ou flag activÃ©.

Limites : API backend sans nouveau bouton, audio navigateur, CDR, raccrochage ou historique client des appels. AcceptÃ© signifie commande reÃ§ue uniquement ; inconnue/en cours jamais relancÃ©e automatiquement. ContrÃ´le distribuÃ© sans transaction atomique entre services ; examen manuel aprÃ¨s interruption. Conservation et recette rÃ©elle Ã  finaliser. Prochaine fonctionnalitÃ© : contrÃ´le des disponibilitÃ©s externes Google/Microsoft lors de la rÃ©servation.

## FonctionnalitÃ© 64 â€” contrÃ´le externe Ã  la confirmation Assurance

CrÃ©ation et dÃ©placement de rendez-vous consultent cÃ´tÃ© serveur l'agenda principal Google/Microsoft du conseiller avant confirmation, sans paramÃ¨tre de contournement navigateur. Conflit externe 409, Ã©chec/connexion perdue 503 et rollback ; absence de connexion antÃ©rieure explicitement internal_only. Rejeu confirmÃ© sans nouveau rÃ©seau ; annulation indÃ©pendante du fournisseur. DÃ©placement excluant uniquement son Ã©vÃ©nement AMX marquÃ© et synchronisÃ©, ambiguÃ¯tÃ© refusÃ©e. Registre et audits ne publient aucun dÃ©tail d'Ã©vÃ©nement au setter. Configuration PORTAL_INTERNAL_URL, protocole signÃ© et commandes dans docs/BOOKING_EXTERNAL_CALENDARS.md ; aucune migration.

Quatre tests mÃ©tier et cinq centraux ajoutÃ©s, ainsi qu'une concurrence PostgreSQL de renouvellement unique. Suites locales Assurance 276 tests (26 rÃ©servÃ©s PostgreSQL), portail 196 (10 rÃ©servÃ©s PostgreSQL) ; migrations cohÃ©rentes, CI requise avant fusion. Aucun fournisseur rÃ©el, appel ou interface nouvelle.

Limites : photographie libre/occupÃ©e, pas de verrou externe ni garantie contre un changement aprÃ¨s contrÃ´le ; publication externe facultative distincte. Transactions ouvertes pendant lecture rÃ©seau ; limitation actuelle du portail locale et agrÃ©gÃ©e par IP, production Ã  dimensionner et recette OAuth rÃ©elle Ã  faire. Isolation non couverte par cette tranche, fonctionnalitÃ© suivante.

## FonctionnalitÃ© 65 â€” contrÃ´le externe Ã  la confirmation Isolation

CrÃ©ation et dÃ©placement de visites contrÃ´lent l'agenda principal Google/Microsoft du client unique, via preuve de service Isolation distincte d'Assurance. Attribution, versions et chevauchements internes restent contrÃ´lÃ©s ; setter d'origine et auteur conservÃ©s. Refus externe ou Ã©chec : aucune visite ni rÃ©vision de prospect modifiÃ©e. Rejeu confirmÃ© et annulation sans rÃ©seau fournisseur ; dÃ©placement excluant seulement son Ã©vÃ©nement AMX vÃ©rifiÃ©. ContrÃ´le interne explicitement indiquÃ© si aucun compte externe n'a jamais Ã©tÃ© connectÃ©. Transport partagÃ© avec Assurance, clÃ©s/audiences, propriÃ©taire et registres toujours sÃ©parÃ©s par espace.

Quatre tests mÃ©tier Isolation et trois centraux ajoutÃ©s, ainsi qu'une concurrence PostgreSQL dÃ©diÃ©e au renouvellement de jeton. Suites locales : 178 core (17 rÃ©servÃ©s PostgreSQL), 200 portail (11 rÃ©servÃ©s PostgreSQL), 276 Assurance (26 rÃ©servÃ©s PostgreSQL). Migrations cohÃ©rentes et CI avant fusion. Aucun fournisseur rÃ©el, appel, changement esthÃ©tique ou nouvelle migration. Configuration et commandes : docs/ISOLATION_EXTERNAL_CALENDAR.md.

Limites communes au lot 64 : photographie sans verrou fournisseur, agenda principal, transactions ouvertes pendant rÃ©seau, quota local partagÃ© par IP et dimensionnement Ã  valider en production. Connexion autrefois Ã©tablie mais perdue bloque, sans repli silencieux. Publication et recette rÃ©elle OAuth distinctes ; aucun module de synchronisation bidirectionnelle dÃ©clarÃ© complet. Prochaine fonctionnalitÃ© : authentification multifacteur centrale, avant la limitation distribuÃ©e et les autres Ã©carts de l'audit.

## FonctionnalitÃ© 66 â€” parcours d'appel depuis les fiches des deux espaces

Bouton Appeler rÃ©servÃ© aux setters dans la fiche Assurance sous prise en charge et les prospects Isolation attribuÃ©s. PrÃ©contrÃ´le central en lecture seule : activation et association de poste, sans numÃ©ro de poste ni secret exposÃ©. Confirmation explicite du numÃ©ro et explication du rappel sur le poste Phonetico. Assurance enregistre la fiche avant confirmation ; changement ultÃ©rieur du numÃ©ro bloque l'envoi. Les API mÃ©tier conservent tous leurs contrÃ´les.

UUID conservÃ© dans la session de l'onglet avant Ã©mission, aucune preuve stockÃ©e. AprÃ¨s rÃ©ponse ambiguÃ«/interruption : consultation GET seule, aucun renvoi automatique ou nouveau bouton d'Ã©mission tant que l'Ã©tat reste indÃ©terminÃ©/en cours. Statuts distincts et acceptation jamais prÃ©sentÃ©e comme dÃ©crochage. DÃ©connexion normale nettoyant les rÃ©fÃ©rences locales. Les flags restent dÃ©sactivÃ©s et aucun appel rÃ©el n'est exÃ©cutÃ©.

VÃ©rifications : test central des capacitÃ©s et rÃ©gression des appels (19 tests dont une concurrence PostgreSQL rÃ©servÃ©e CI), tests du composant avec transport simulÃ©, TypeScript et build. Pas de recette rÃ©elle Phonetico ou de validation utilisateur du rendu final. Limites : rÃ©fÃ©rences locales par onglet et fiche, pas de liste globale d'historique ni de rapprochement CDR ; une commande inconnue/absente doit Ãªtre examinÃ©e cÃ´tÃ© opÃ©rateur, aucun dÃ©blocage automatique. Prochaine tranche : structure du front et navigation cohÃ©rente pour la prÃ©sentation. MFA centrale, limitation distribuÃ©e, statistiques finales, recette des fournisseurs et production restent explicitement ouverts.

## FonctionnalitÃ© 67 â€” structure du front et vue d'ensemble communes

Nouveau cadre CRM avec barre latÃ©rale par rÃ´le, sÃ©lecteur des espaces autorisÃ©s, fil d'Ariane, compte et administration accessibles sans empiler les modules dans la page. Assurance : contacts, rendez-vous, tÃ¢ches, statistiques, conseillers et administration selon les droits ; Isolation : dossiers, visites et statistiques, client unique conservÃ©. Vue d'ensemble utilisant les compteurs mÃ©tier existants, actions de navigation et trois prochains rendez-vous/visites lus depuis les API ; absence et Ã©chec distinguÃ©s. Aucun graphique ou chiffre de dÃ©monstration dans le produit. Rappels/notifications dÃ©placÃ©s sur le dashboard ; fonctions existantes accessibles depuis leurs pages.

Fond clair, cartes blanches, accents olive et icÃ´nes cohÃ©rentes ; menu repliÃ© sur petit Ã©cran, tableaux dÃ©filants et retour en haut lors des changements de page. RÃ©ponses de chargement d'espace pÃ©rimÃ©es ignorÃ©es pour Ã©viter d'afficher une synthÃ¨se d'un autre espace aprÃ¨s navigation rapide. Aucun changement de droits ou de donnÃ©es serveur. Imports Lookup Isolation historiques toujours sÃ©parÃ©s et signalÃ©s, pas prÃ©sentÃ©s comme migrÃ©s.

VÃ©rifications : TypeScript/build et tests du parcours d'appel ; recette Chrome desktop et largeur 390 px sur serveur local sÃ©parÃ© avec rÃ©ponses synthÃ©tiques et mutations refusÃ©es. Navigation dashboard/contacts, changement Assurance vers Isolation et ouverture/fermeture du menu mobile observÃ©s. Captures de recette privÃ©es hors Git. Cette recette vÃ©rifie le rendu et le cÃ¢blage, pas une nouvelle recette des API rÃ©elles ou de tous les rÃ´les. CI avant fusion.

Limites : premiÃ¨re tranche visuelle, pas une refonte terminÃ©e de tous les formulaires mÃ©tier. Fiches dÃ©taillÃ©es, listes et agendas Ã  harmoniser ensuite ; filtres/route active non persistÃ©s dans l'URL, donnÃ©es client de prÃ©sentation Ã  prÃ©parer sÃ©parÃ©ment. MFA centrale, protection distribuÃ©e, complÃ©ments statistiques et cycle contractuel, CDR, recette des fournisseurs et production restent ouverts. PrioritÃ© suivante pour vendredi : listes de contacts et fiche dossier cohÃ©rentes avec cette structure.

## Correction 68 â€” accÃ¨s direct Ã  l'espace unique

Un compte avec un seul accÃ¨s actif entre directement dans cet espace, y compris si la valeur landing reÃ§ue est absente. La barre latÃ©rale affiche uniquement le nom de cet espace, sans liste de choix ou proposition de l'autre mÃ©tier. Le sÃ©lecteur n'est rendu que pour plusieurs espaces rÃ©ellement autorisÃ©s par la session. Aucun rÃ´le ni accÃ¨s ajoutÃ© en base. Trois tests de rendu couvrent Assurance seule, Isolation seule et double accÃ¨s. TypeScript et CI avant fusion. La refonte visuelle GoHighLevel demandÃ©e est la tranche suivante, pas dÃ©clarÃ©e livrÃ©e par cette correction.

## FonctionnalitÃ© 69 â€” palette CRM et fiche Assurance en panneaux

Reprise de la disposition Ã  partir de la documentation publique HighLevel (fiche contact, panneaux informations/activitÃ©/actions), sans copier ses captures dans le produit. Palette connectÃ©e bleu ardoise et accents doux, suppression du grand bandeau dÃ©coratif du dashboard. Fiche Assurance : informations et qualification Ã  gauche, interactions au centre, notes/documents/rendez-vous/contrats en onglets Ã  droite selon le rÃ´le. Les panneaux utilisent les composants et contrÃ´les mÃ©tier existants ; aucun message ou canal de conversation fictif ajoutÃ©. Liste masquÃ©e pendant la consultation du dossier et retour explicite. Onglets montÃ©s conservÃ©s pour ne pas perdre un brouillon lors du changement.

TypeScript, six tests frontend et build rÃ©ussis. Recette visuelle navigateur tentÃ©e sur instance synthÃ©tique : indisponible, contrÃ´le local dÃ©sactivÃ© dans les rÃ©glages Work. Ne constitue donc pas une validation graphique finale. Isolation et formulaires imbriquÃ©s restent Ã  harmoniser, aucune refonte exhaustive dÃ©clarÃ©e. Connexion CallVerify d'origine Ã  restaurer sÃ©parÃ©ment avec choix de profil selon la derniÃ¨re clarification utilisateur. Aucun appel ni donnÃ©e active modifiÃ©e.

## FonctionnalitÃ© 70 â€” connexion CallVerify et profils mÃ©tier

DÃ©cor SVG, fond crÃ¨me, marque et formulaire de la connexion CallVerify d'origine repris pour le portail central. Choix Assurance/Isolation prÃ©sentÃ© en profils visuels avant les identifiants ; formulaire du profil sÃ©lectionnÃ©, retour aux profils et rÃ©cupÃ©ration centrale prÃ©servÃ©s. Ce choix public n'est pas une attribution : la connexion centrale contrÃ´le l'adhÃ©sion active au profil demandÃ© avant de crÃ©er la session (paramÃ¨tre facultatif pour compatibilitÃ©). AprÃ¨s connexion, sÃ©lection de ce seul espace ; changement dans le CRM rÃ©servÃ© aux comptes multi-accÃ¨s. Aucun accÃ¨s crÃ©Ã© automatiquement. Les mots de passe sont effacÃ©s aprÃ¨s soumission ou changement de profil, jamais persistÃ©s.

Huit tests frontend couvrant notamment sÃ©lection/soumission/changement de profil et espace unique ; deux tests API de refus sans session et de connexion autorisÃ©e ajoutÃ©s. TypeScript/build et suite portail avant fusion. ContrÃ´le graphique navigateur indisponible car dÃ©sactivÃ© dans Work : validation visuelle finale Ã  faire, pas annoncÃ©e terminÃ©e. Aucune MFA fictive ajoutÃ©e au formulaire central ; la MFA centrale demeure Ã  livrer. La connexion historique CallVerify reste inchangÃ©e Ã  la racine. Suite : harmonisation de la liste et du suivi Isolation, puis revue utilisateur de la disposition et des couleurs.

## FonctionnalitÃ© 71 â€” harmonisation transversale des Ã©crans mÃ©tier

ThÃ¨me commun limitÃ© au CRM connectÃ© : palette bleu ardoise, surfaces blanches, accents doux, typographie, formulaires, Ã©tats de focus, boutons, tableaux, alertes, cartes, paramÃ¨tres et documents cohÃ©rents. La connexion CallVerify crÃ¨me/profils reste indÃ©pendante. Navigation mobile, champs et groupes de formulaires adaptatifs, dÃ©filement des tableaux conservÃ©s. Les modules existants rÃ©utilisent ces styles sans changer leurs appels serveur ou droits.

Prospects Isolation prÃ©sentÃ©s dans une table : identitÃ©, Ã©tat technique avec libellÃ©/badge, qualification commerciale distincte, setter, rappel et actions groupÃ©es Ã  icÃ´nes accessibles. Aucun rÃ©sultat technique recalculÃ© ; indÃ©terminÃ© conservÃ©. Client Isolation : dossiers Ã©galement tabulaires, accÃ¨s aux visites/rÃ©sultats maintenu. Contacts Assurance avec repÃ¨re visuel et ouverture de fiche au nom ; suivi prospect encadrÃ©. LibellÃ©s d'agenda actualisÃ©s pour reflÃ©ter les contrÃ´les Google/Microsoft dÃ©jÃ  livrÃ©s, sans promettre une publication externe automatique.

VÃ©rifications : TypeScript, huit tests frontend et build rÃ©ussis ; diff vÃ©rifiÃ© et CI avant fusion. Aucun appel rÃ©el, nouvelle donnÃ©e de prÃ©sentation ou changement backend. ContrÃ´le visuel navigateur encore indisponible (dÃ©sactivÃ© dans Work) : harmonisation du code livrÃ©e, validation esthÃ©tique et parcours rÃ©el de tous les rÃ´les non dÃ©clarÃ©s terminÃ©s. Les agendas restent des listes fonctionnelles, pas une grille calendaire livrÃ©e. Prochaine Ã©tape : recette visuelle utilisateur et corrections ciblÃ©es avant la prÃ©sentation, puis Ã©carts mÃ©tier/production dÃ©jÃ  recensÃ©s.

## FonctionnalitÃ©s suivantes non livrÃ©es

1. Migration complÃ¨te des comptes, MFA et navigation unifiÃ©e avec Isolation (gestion des accÃ¨s, invitations, rÃ©cupÃ©ration et consultation du journal dâ€™administration et rÃ©vocation des autres sessions livrÃ©es).
2. Statistiques et suivi mÃ©tier Isolation complÃ©mentaires, rÃ©partition selon charge/disponibilitÃ©s et sÃ©lection massive (rÃ©partition Ã  tour de rÃ´le bornÃ©e, portail client, rÃ©sultats, file setter, qualification, notes, partage explicite, rappels et visites internes livrÃ©s).
3. ComplÃ©ments des fiches Assurance : champs mÃ©tier dÃ©finitifs Ã  valider, cycle mÃ©tier complet des mandats/contrats (registre administratif rÃ©servÃ© aux administrateurs livrÃ© au lot 50 ; documents liÃ©s livrÃ©s au lot 51 ; visibilitÃ© et cycle Ã  prÃ©ciser, finances exclues) (partages champs/documents/notes suivis sÃ©parÃ©ment dans les lots 42 Ã  44) (coordonnÃ©es sous verrou, champs configurables avec partage conseiller explicite, notes, documents et chronologie des interactions livrÃ©s).
4. Phonetico dans chaque CRM, aprÃ¨s validation des opÃ©rations rÃ©elles du fournisseur.
5. Connecteur Calendly et synchronisation Google/Microsoft avancÃ©e (publication unidirectionnelle sur agenda principal livrÃ©e, recette rÃ©elle OAuth Ã  effectuer) ; rÃ¨gles avancÃ©es de relance (notifications e-mail, rappels pÃ©riodiques et escalades administrateurs Assurance livrÃ©s ; SMTP rÃ©el Ã  valider).
6. Cycle administratif final des contrats (sans finances), statistiques mÃ©tier, sauvegardes externes et dÃ©ploiement final.

Les prochains Ã©lÃ©ments seront dÃ©coupÃ©s en fonctionnalitÃ©s plus petites, chacune avec sa PR fusionnÃ©e avant la suivante. Aucun de ces modules n'est dÃ©clarÃ© terminÃ© par la prÃ©sence de son emplacement dans le dÃ©pÃ´t.
