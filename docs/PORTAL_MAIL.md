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
