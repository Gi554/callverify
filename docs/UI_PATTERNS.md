# Panneaux latéraux

Utiliser `frontend/src/SidePanel.vue` par défaut pour les nouvelles fiches et formulaires qui doivent conserver le contexte de la page. Appliquer ce modèle aux autres parcours au fil de leur reprise avec l’utilisateur.

- `open` est contrôlé par le parent. `requestClose` demande la fermeture ; le composant ne la force jamais.
- Le parent valide la sauvegarde, la libération des verrous et les éventuels brouillons avant de remettre `open` à `false`.
- `closeDisabled` bloque la croix et Échap pendant une opération qui ne doit pas être interrompue.
- Donner un `title` explicite et, si utile, `subtitle` et `eyebrow`. L’en-tête reste visible ; le dialogue natif gère le focus et rend l’arrière-plan inerte.
- Le contenu défile par défaut ; le slot `footer` reste fixe pour les actions. Un formulaire peut fournir son propre défilement avec `scrollable=false`.
- L’ouverture depuis la droite, les couleurs douces, le plein écran sur petit écran et la réduction des animations sont centralisés.

Éviter les grandes colonnes de formulaires juxtaposées. Regrouper les tâches par rubriques, conserver leurs brouillons pendant la navigation et ne pas afficher de tableau vide ou de bouton inactif sans explication utile.
