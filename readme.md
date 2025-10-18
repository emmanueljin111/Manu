# Louange Planner

Application web permettant d'organiser et de planifier les temps de louange d'une église. Elle s'inspire du catalogue de chants disponible sur [epcp-louange.fr](https://www.epcp-louange.fr/) et fournit des outils de gestion pour les responsables, musiciens et techniciens.

## Fonctionnalités

- Gestion d'une base de chants (titre, auteur, thème, liens vers PDF, PPT, accords, mots-clés)
- Recherche et filtrage par thème ou mot-clé
- Création de plans de louange avec ordre des chants, tonalités et notes de transition
- Gestion de l'équipe (responsables, musiciens, techniciens)
- Export des plans en PDF et en PowerPoint (`.pptx`)
- Lien de partage public pour consultation sans authentification
- Calendrier des cultes et répétitions avec association d'un plan

## Prérequis

- Python 3.10+
- pip

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # sous Windows : .venv\Scripts\activate
pip install flask werkzeug
```

> Flask et Werkzeug sont nécessaires pour l'application et la gestion des mots de passe.

## Lancement

```bash
export FLASK_APP=app.py  # sous Windows : set FLASK_APP=app.py
python app.py
```

Le serveur démarre sur [http://localhost:5000](http://localhost:5000).

## Authentification

Un utilisateur administrateur est créé automatiquement :

- **Identifiant :** `admin`
- **Mot de passe :** `admin123`

Connectez-vous avec ce compte puis ajoutez d'autres utilisateurs via la base de données (non exposé dans l'interface).

## Structure du projet

```
app/
├── __init__.py
├── db.py
├── routes.py
├── services.py
├── exports/
├── static/
│   ├── css/app.css
│   └── js/app.js
└── templates/
    ├── base.html
    ├── auth/
    ├── calendar.html
    ├── dashboard.html
    ├── plans/
    └── songs/
app.py
```

Les exports PDF et PPTX sont générés dans `app/exports/`.

## Tests rapides

1. Se connecter avec l'utilisateur `admin`
2. Consulter la base de chants pré-remplie
3. Créer un plan de louange, ajouter des chants et définir l'équipe
4. Exporter le plan en PDF ou PPTX
5. Partager le plan via le lien public

## Remarques

- Les exports PDF et PowerPoint sont générés sans dépendances externes via une implémentation minimale.
- Les liens de la base de chants pointent vers les ressources du site epcp-louange.fr.
