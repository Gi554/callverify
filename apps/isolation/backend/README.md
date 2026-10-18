# CRM Isolation

Le backend historique reste dans `core/` et `config/` pendant la migration afin de préserver les imports, Lookup, exports et l'authentification existants. Sa base reste indépendante de celles du portail et d'Assurance. Le déplacement physique des sources viendra dans une PR distincte.

L'adaptateur d'identité centrale s'appuie sur des tickets dédiés à Isolation. Les rôles setter et client n'ont aucun accès aux routes administratives historiques ; leurs routes métier seront ajoutées avec les affectations.
