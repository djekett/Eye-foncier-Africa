#!/usr/bin/env bash
# Script de build pour Render
set -o errexit

# Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# Collecter les fichiers statiques
python manage.py collectstatic --no-input

# Appliquer les migrations
python manage.py migrate --no-input
