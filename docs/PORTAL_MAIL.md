# E-mails du portail AMX

Les invitations et récupérations de mot de passe sont mises en file dans la base du portail, dans la transaction de la demande. La réponse « mis en file » ne garantit ni acceptation SMTP ni réception dans la boîte du destinataire.

## Développement

Avec le même environnement que le serveur portail (notamment DEBUG, PORTAL_SECRET_KEY et PORTAL_DB_*), appliquer les migrations puis traiter un lot :

```powershell
./.venv/Scripts/python.exe manage.py migrate --settings=portal.backend.settings
./.venv/Scripts/python.exe manage.py dispatch_portal_mail --settings=portal.backend.settings --status
./.venv/Scripts/python.exe manage.py dispatch_portal_mail --settings=portal.backend.settings --limit 100
```

Le mode continu ajoute `--loop --interval 10`. En DEBUG, le transport par défaut écrit les messages dans `private-media/portal-mail` ; ces fichiers contiennent des liens privés et restent hors Git. Ne pas utiliser de données réelles dans les tests. Le worker doit partager exactement la même clé de chiffrement et la même base que le serveur.

## Production

Configurer PORTAL_PUBLIC_URL (HTTPS), les PORTAL_EMAIL_* et PORTAL_FROM_EMAIL. Générer une clé Fernet, puis la conserver dans le gestionnaire de secrets comme PORTAL_MAIL_KEY :

```powershell
./.venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Ne pas publier la sortie ou placer la clé dans Git. Elle est obligatoire hors DEBUG ; en développement uniquement, une clé dérive du secret du portail si aucune clé dédiée n’est renseignée. Une rotation sans conservation de l’ancienne clé rend les messages en attente illisibles : traiter la file avant rotation, puis émettre de nouveaux liens si nécessaire. Sauvegarder la clé séparément de la base, avec accès restreint.

Le service Docker `portal-mail` partage l’environnement et la base du portail, avec redémarrage automatique. Appliquer les migrations avant son démarrage. Le mode `--status` n’envoie rien et affiche uniquement les totaux pending/sending/sent/failed/expired. Les actions `mail.queued`, `mail.sent`, `mail.retry`, `mail.failed` et `mail.expired` sont auditées sans destinataire, corps, lien ou exception SMTP.

## Reprises et limites

Le worker réserve un message pendant 60 secondes par mise à jour conditionnelle. Deux workers ne peuvent pas obtenir la même réservation active. Une réservation abandonnée redevient disponible après expiration. Cinq tentatives SMTP au maximum, espacées de 60, 120, 240 puis 480 secondes. Au dernier échec, le contenu chiffré est effacé ; demander un nouveau lien ou renvoyer l’invitation pour recommencer. Les lignes d’historique restent conservées ; leur purge réglementaire reste à définir.

Chaque envoi recontrôle l’expiration et la validité du lien : invitation révoquée/remplacée/acceptée, droits retirés à l’émetteur, récupération invalidée par changement du compte. Les contenus sont effacés après envoi, expiration ou échec définitif. Une révocation concurrente juste après ce contrôle peut laisser partir un ancien e-mail, mais son lien reste refusé à l’acceptation.

SMTP fournit ici une livraison « au moins une fois » : si le processus s’arrête après acceptation SMTP mais avant enregistrement du succès, un doublon peut être émis. Le message reçu ne prouve pas sa lecture. Pas encore de retour de rebond, notification métier rendez-vous, tableau de supervision, alerte externe, politique de conservation ou déploiement SMTP validé. La file doit être surveillée et le worker maintenu actif ; un serveur web seul n’envoie plus ces e-mails.

## Notifications métier Assurance

Un relais serveur récupère les notifications `report` et `incident` des sept derniers jours dont la tâche reste ouverte. Les notifications de reprise historique ne déclenchent pas d’e-mail. Aucun accès direct à la base Assurance : deux routes HTTP internes, protégées par des signatures de 60 secondes avec une clé dédiée `ASSURANCE_MAIL_BRIDGE_KEY`, distincte des accès utilisateurs et à partager uniquement entre Assurance et le portail. Ne jamais exposer cette clé au navigateur. Configurer `ASSURANCE_INTERNAL_URL` vers le service Assurance de confiance (réseau Docker privé par défaut en production, `http://127.0.0.1:8091` en développement). Utiliser HTTPS si la connexion traverse un réseau non fiable ; les redirections sont refusées et le délai HTTP est de cinq secondes.

Avec le même environnement que le portail :

```powershell
./.venv/Scripts/python.exe manage.py relay_assurance_mail --settings=portal.backend.settings
./.venv/Scripts/python.exe manage.py relay_assurance_mail --settings=portal.backend.settings --loop --interval 30
```

Le relais ne transmet aucun e-mail lui-même. Il ajoute les messages à la file chiffrée, que `dispatch_portal_mail` traite séparément. Docker fournit `assurance-mail-relay`, en plus de `portal-mail`. Migrations portail à appliquer avant démarrage. Un passage récupère au maximum 100 événements avec un curseur persistant ; après la fin du parcours, le relais recommence pour reprendre les réattributions ou les comptes corrigés. Le registre évite de remettre en file le même événement pour le même compte, même avec deux relais concurrents. Les compteurs de commande n’affichent aucune adresse ou signature.

Le portail résout le compte central du setter : compte actif, accès Assurance actif avec rôle setter, adresse valide et non partagée avec un autre compte actif. Sinon l’événement est ignoré pour ce passage, puis réévalué lors d’un prochain parcours pendant sa fenêtre de sept jours. Le message contient seulement un avis de suivi et le lien du portail, nécessitant une connexion normale ; aucun lien de connexion automatique, nom, téléphone, note, identifiant de prospect ou identité de setter. L’e-mail ne prouve pas sa lecture et ne résout pas la tâche.

Avant SMTP, les droits et l’adresse sont revérifiés ainsi que le responsable et l’ouverture de la tâche via Assurance. Une tâche clôturée, réattribuée ou sortie de la fenêtre expire dans la file. Une panne du service déclenche une reprise, jamais un envoi sans vérification. Après transfert, un prochain parcours peut mettre en file pour le nouveau responsable. Une modification entre le dernier contrôle et SMTP reste possible ; le texte minimal ne révèle aucune donnée de dossier.

Limites : pas de rappel périodique pour le même incident, de notification d’une réouverture administrative ou d’escalade. Les e-mails expirent sept jours après l’événement ; une panne prolongée peut donc entraîner une absence d’e-mail, sans effacer l’alerte interne. Après un échec définitif ou une adresse changée après mise en file, le même événement/compte n’est pas remis automatiquement en file ; la boîte interne reste la référence. Les limites SMTP et de surveillance ci-dessus s’appliquent. Ne pas annoncer la réception d’un e-mail sur la seule mise en file. Aucun transport SMTP réel n’a été validé dans ce lot.

## Rappels périodiques Assurance

Un troisième worker, dans le service Assurance et sa propre base, génère les rappels :

```powershell
./.venv/Scripts/python.exe manage.py generate_assurance_reminders --settings=apps.assurance.backend.settings
./.venv/Scripts/python.exe manage.py generate_assurance_reminders --settings=apps.assurance.backend.settings --loop --interval 60
```

Le service Docker `assurance-reminders` lance cette boucle. Migrations Assurance 0017/0018 et portail 0007 à appliquer avant démarrage. Le relais portail traite désormais les flux `incidents` et `reminders` par défaut ; `--stream incidents` ou `--stream reminders` permet de les isoler pour exploitation. Leurs curseurs et clés de déduplication sont distincts, afin que des identifiants égaux ne se confondent pas.

L’administrateur règle les rappels depuis Assurance → Rappels actifs → Régler les rappels : activation séparée des tâches et des comptes rendus, intervalle de 1 à 720 heures pour chaque type, délai de 0 à 720 heures après la fin d’un rendez-vous avant premier rappel de compte rendu. Valeurs initiales : actifs, intervalle de 24 heures et délai de compte rendu de 24 heures. Ce sont des heures écoulées UTC, sans calendrier de jours ouvrés. Les modifications exigent la révision actuelle et un motif, avec audit atomique.

Chaque tâche dépassée revient à son setter actuel ; un compte rendu manquant revient au seul conseiller du rendez-vous. Une absence de compte rendu ne devient jamais Non et ne crée pas de tâche d’incident. Les périodes partent de l’échéance de tâche ou de la fin du rendez-vous augmentée du délai. Un seul événement par objet, destinataire, échéance, règle et période ; après une panne, seul le rappel courant est créé. Le worker parcourt les candidats en flux par blocs de 200 et valide chaque objet dans sa propre transaction, avec verrous et unicité. Il ne représente pas un journal des périodes manquées. Une modification des règles invalide les anciens rappels et peut créer immédiatement un rappel de la nouvelle règle au prochain passage.

Les rappels actifs sont consultables dans le CRM avec pagination, lien vers les tâches/rendez-vous et rafraîchissement toutes les 60 secondes lorsque la page est visible. Ils disparaissent du périmètre actif après clôture, compte rendu, annulation, report, changement d’échéance, désactivation de la règle ou expiration de la période. Un transfert retire le rappel au précédent setter ; le worker peut en créer un pour le nouveau dans la période courante. Les événements antérieurs restent dans la base, sans accès utilisateur à un historique complet dans ce lot. Lire l’écran ou l’e-mail ne résout rien.

Avant SMTP, le portail revérifie le rôle attendu (setter ou conseiller) et Assurance recontrôle l’état actuel du rappel. Le message est neutre, sans identité de setter ni donnée de prospect. Les e-mails en attente restent soumis à leur durée maximale de sept jours et aux reprises SMTP existantes ; un ancien rappel dont la période est terminée est écarté, même si l’e-mail n’a pas encore atteint sept jours. Une période future peut fournir un nouveau rappel après un échec du précédent. Aucun message réel envoyé pendant la validation ; SMTP réel et exploitation des trois workers restent à valider avant production. Les limites de contrôle juste avant SMTP, de doublons après crash et de non-preuve de réception demeurent.

Pas encore d’escalade vers un administrateur, de jours ouvrés, de quotas journaliers par utilisateur ou de politiques par conseiller/setter. Les paramètres sont globaux pour Assurance. Sur de grands volumes, mesurer la durée de balayage et la capacité du relais avant de choisir une cadence courte.
