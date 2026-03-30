# Suunto Export Activity

Utilitaire Python pour exporter les activités Suunto via OAuth2, parser les fichiers `.fit` / `.json`, et générer un format structuré (`JSON` + `CSV`) pour analyse avancée (y compris avec un LLM).

## Fonctionnalités

- Authentification OAuth2 (URL d'autorisation, échange code, refresh automatique)
- Appel API Suunto (`/v2/workouts`) avec pagination simple
- Téléchargement des ressources d'activité (`.fit`, `.json`) quand disponibles
- Parsing FIT (session, laps, GPS, FC, dénivelé, allure estimée)
- Parsing JSON natif avec normalisation
- Export:
  - `activities.json` (hiérarchique, riche)
  - `activities.csv` (plat, agrégé)

## Prérequis

- Python 3.10+
- Accès API Suunto (`client_id`, `client_secret`, `subscription key`)
- Docker + Docker Compose (optionnel)

## Installation

```bash
cd /Users/mio/DEV/SuuntoExportActivity
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

1. Copier le fichier d'exemple:

```bash
cp .env.example .env
```

2. Remplir au minimum:

- `SUUNTO_CLIENT_ID`
- `SUUNTO_CLIENT_SECRET`
- `SUUNTO_SUBSCRIPTION_KEY`
- `SUUNTO_REDIRECT_URI`

Le loader `.env` est interne (pas de dépendance `python-dotenv`) : les variables du fichier `.env` sont chargées automatiquement.
La CLI lit aussi directement ces variables d'environnement (pratique avec Docker Compose).
Pour `parse-local`, seules les variables optionnelles sont nécessaires (par exemple `SUUNTO_MAX_HR`).

## Utilisation Docker

1. Préparer l'environnement:

```bash
cp .env.example .env
mkdir -p output .tokens data
```

2. Construire l'image:

```bash
docker compose build
```

3. Commandes principales:

```bash
docker compose run --rm suunto-export auth-url
docker compose run --rm suunto-export exchange-code --code "<AUTH_CODE>"
docker compose run --rm suunto-export export
```

Notes:
- `output/` et `.tokens/` sont montés en volume persistant.
- `data/` est monté dans le conteneur sur `/data`.
- Pour `parse-local`, dépose tes fichiers `.fit/.json` dans `./data` puis lance:

```bash
docker compose run --rm suunto-export parse-local
```

## Flux OAuth2

### 1) Générer l'URL d'autorisation

```bash
suunto-export auth-url
```

Ouvrir l'URL, autoriser l'application, puis récupérer le `code` depuis le callback.

### 2) Échanger le code contre un token

```bash
suunto-export exchange-code --code "<AUTH_CODE>"
```

Le token est stocké dans `SUUNTO_TOKEN_PATH` (par défaut `.tokens/suunto_token.json`).

## Export complet depuis l'API

```bash
suunto-export export \
  --output-dir ./output \
  --start-date 2026-01-01 \
  --end-date 2026-12-31
```

Tu peux aussi définir `SUUNTO_OUTPUT_DIR`, `SUUNTO_EXPORT_START_DATE`, `SUUNTO_EXPORT_END_DATE` dans `.env` et lancer simplement `suunto-export export`.

Résultat:

- `output/raw/` : fichiers sources téléchargés
- `output/activities.json` : activités normalisées
- `output/activities.csv` : vue tabulaire agrégée

## Traitement local de fichiers déjà exportés

Si l'accès API est limité, tu peux parser directement des fichiers locaux:

```bash
suunto-export parse-local \
  --input /chemin/vers/mes-fichiers \
  --output-dir ./output
```

Si `SUUNTO_LOCAL_INPUT` est défini dans `.env`, l'argument `--input` devient optionnel.

## Structure JSON (exemple)

```json
{
  "activity_id": "123",
  "type": "trail",
  "date": "2026-03-29",
  "duration": "01:30:00",
  "distance": 15.5,
  "elevation_gain": 800,
  "heart_rate": {
    "avg": 145,
    "max": 178,
    "zones": {
      "z1": 180,
      "z2": 120,
      "z3": 95,
      "z4": 40,
      "z5": 8
    }
  },
  "laps": [
    {
      "lap_number": 1,
      "distance": 5.0,
      "pace_avg": "05:30/km",
      "hr_avg": 140
    }
  ],
  "gps_track": [
    {
      "lat": 46.1,
      "lon": 6.2,
      "altitude": 745.2,
      "timestamp": "2026-03-29T07:11:25Z"
    }
  ],
  "notes": "Sensations : 7/10"
}
```

## Gestion d'erreurs intégrée

- Token expiré ou absent: refresh automatique si possible, sinon erreur explicite
- Réponse API invalide: exceptions contextualisées
- Fichier corrompu/non supporté: activité ignorée avec warning de parsing

## Limites connues

- Le schéma exact des ressources workout peut varier selon le compte/endpoint Suunto; le code applique une recherche tolérante des URLs FIT/JSON.
- Les zones FC reposent soit sur les valeurs session, soit sur un calcul basé sur `SUUNTO_MAX_HR`.

## Tests rapides

```bash
python -m compileall src
```
