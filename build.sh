#!/usr/bin/env bash
# Script de build pour Render
set -o errexit

# Installer les librairies système pour GeoDjango (GDAL, GEOS, PROJ)
apt-get update && apt-get install -y --no-install-recommends \
  gdal-bin libgdal-dev libgeos-dev libproj-dev \
  binutils libproj-dev

# Exporter le chemin GDAL pour Python
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal

# Installer les dépendances Python
pip install --upgrade pip
pip install -r requirements.txt

# Collecter les fichiers statiques
python manage.py collectstatic --no-input

# Appliquer les migrations
python manage.py migrate --no-input
