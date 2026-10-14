# Qualification technique : Lookup et observations Voice

## Périmètre actuel

Lookup est disponible sans appel, via les campagnes existantes. Il valide le numéro et récupère les packages techniques accessibles au compte ; les erreurs de package et les résultats bruts sont conservés. Un numéro valide ou un état Active ne démontre pas sa joignabilité. Seul un statut explicitement reachable est classé potentiellement joignable, sans preuve de sonnerie ni de réponse.

Aucun message vocal, aucune synthèse vocale, aucune conversation et aucune émission Voice ne sont implémentés dans cette version. Le point de lancement retourne 409 systématiquement, y compris si VOICE_ENABLED est surchargé. Les anciennes livraisons Voice ne peuvent pas appeler : elles sont bloquées. Les campagnes silencieuses et le raccrochage après sonnerie restent désactivés en attente de validation réglementaire au Canada.

TWILIO_PHONE_NUMBER recevra le numéro émetteur ultérieurement. Aucun numéro ne suffit à lever le blocage de lancement.

## Webhooks et historique

POST /api/webhooks/twilio/voice/ reçoit les statuts et POST /api/webhooks/twilio/amd/ reçoit les résultats AMD. Signature Twilio obligatoire, SID de tentative connu, compte cohérent lorsqu’il est présent, déduplication et conservation des états terminaux. Un SID inconnu est rejeté ; un futur adaptateur autorisé devra enregistrer les tentatives avant les callbacks.

Les statuts sont conservés séparément de Lookup : queued, initiated, ringing, in-progress, completed, busy, no-answer, failed, canceled. ErrorCode est enregistré sans exposer les exceptions ou identifiants secrets. Les événements reçus et les dates sont accessibles dans la fiche du contact, avec historique distinct de Lookup.

voice_rang signifie qu’un événement ringing a été reçu. Son absence signifie absence d’observation, pas absence certaine de sonnerie. voice_answered signifie connexion observée (in-progress ou completed), pas réponse humaine garantie : répondeur et serveur vocal peuvent également décrocher. Le statut completed ne constitue donc pas une classification human.

## AMD facultative

La préparation peut déclarer amd_enabled. Un futur adaptateur devra enregistrer amd_requested sur la tentative et utiliser les options construites par amd_parameters avec un callback public HTTPS. Cette fonction prépare MachineDetection=Enable et AsyncAmd, mais ne lance aucun appel. La réception AMD fonctionne sans CallStatus, conserve human, machine_start, machine_end_beep, machine_end_silence, machine_end_other, fax ou unknown. Une observation inconnue peut être affinée ensuite ; une estimation définitive ne sera pas écrasée par un événement tardif inconnu.

AMD est probabiliste : faux positifs et faux négatifs possibles, silence ou timeout pouvant produire unknown. Aucun résultat AMD ne garantit l’identité du répondant. Documentation primaire : https://www.twilio.com/docs/voice/answering-machine-detection

## Affichage et exports

La liste des résultats et les fiches distinguent classification Lookup et statut Voice. Le dashboard affiche tentatives, sonneries et connexions observées, répartition des statuts et estimations AMD : ces compteurs portent sur les tentatives, pas les numéros uniques. Les exports CSV/XLSX proposent les colonnes lookup_* et voice_* séparées, avec erreurs et dates. Le résultat synthétique correspond à la dernière tentative et à la dernière vérification Lookup de la campagne ; l’historique conserve les précédentes.

## Vérification

Tests locaux avec Twilio simulé et webhooks signés : aucun appel ni Lookup réel effectué pour cette modification. Validation réglementaire, émission autorisée, accès fournisseur et endpoint public restent à réaliser avant toute recette Voice réelle.
