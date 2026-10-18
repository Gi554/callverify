# Méthode de livraison

- Traiter une fonctionnalité à la fois. Avant de démarrer la suivante : terminer la fonctionnalité courante, la vérifier, créer son commit, pousser, ouvrir une PR et fusionner vers main.
- Utiliser staging comme branche intermédiaire. Ne pas ajouter de préfixe codex aux branches. N'ouvrir d'autre branche que si nécessaire, avec un nom descriptif sans ce préfixe.
- Chaque PR décrit précisément le comportement livré, les vérifications et les limites. Ne pas présenter une base technique comme un module métier terminé.
- Tenir docs/DELIVERY.md à jour avec les fonctionnalités livrées et celles restant à réaliser. Préserver les secrets et données de recette hors de Git.
- Prioriser les fonctionnalités et leurs contrôles. Reporter la revue esthétique et les retouches d'interface à la revue finale demandée par l'utilisateur ; conserver des commandes utilisables pour chaque parcours livré.
