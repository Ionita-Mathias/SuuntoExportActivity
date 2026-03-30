# Suunto Export Activity

CLI Python pour exporter et analyser **vos propres** activités Suunto via Suunto Cloud API, avec OAuth2, parsing FIT/JSON et sortie structurée JSON/CSV.

Compatible avec Suunto.
Usage personnel uniquement.
L'API Suunto Cloud est utilisée **en l'état**, sans garantie.

## Fonctionnalités orientées conformité

- OAuth2 uniquement (aucune gestion de mot de passe Suunto)
- Consentement explicite avant export/traitement/suppression (désactivable volontairement pour l'automatisation)
- Approche local-first pour les données
- Mode de stockage des tokens:
  - `memory` (par défaut, recommandé)
  - `file` (optionnel)
- Limitation du débit API (`SUUNTO_RATE_LIMIT_PER_MINUTE`, par défaut `10`)
- Filtrage par utilisateur via le `sub` JWT (ou `SUUNTO_OWNER_USER_ID`)
- Commande de suppression des exports (`delete-data`)
- Chiffrement optionnel des sorties (`.enc`) via passphrase

## Capacités principales

- Récupération des workouts via `https://cloudapi.suunto.com/v2/workouts`
- Téléchargement des ressources associées (`.fit`, `.json`)
- Parsing FIT/JSON: métadonnées, FC, laps, GPS, dénivelé, allure
- Exports:
  - `activities.json`
  - `activities.csv`

## Exemples de types d'export

- `export` API complet (workouts Suunto + parsing + JSON/CSV)
- `parse-local` (fichiers `.fit`/`.json` déjà présents en local)
- `export` chiffré (`.enc`) pour stockage hors machine locale

Types d'activités courants observés:

- `TrailRun`
- `Run`
- `BackcountrySki`
- `AlpineSki`
- `Ride`
- `Walk`

## Exemple de structure JSON

```json
{
  "activity_id": "123",
  "type": "trail",
  "date": "2026-03-30",
  "duration": "01:30:00",
  "distance": 15.5,
  "elevation_gain": 800,
  "heart_rate": {
    "avg": 145,
    "max": 178
  },
  "laps": [
    {
      "lap_number": 1,
      "distance_km": 5.0,
      "pace_avg": "05:30/km",
      "hr_avg": 140
    }
  ],
  "gps_track": [
    {
      "lat": 46.1,
      "lon": 6.2,
      "altitude": 745.2,
      "timestamp": "2026-03-30T07:11:25Z"
    }
  ],
  "notes": "Sensations 7/10"
}
```

## Exemple de colonnes CSV

- `activity_id`
- `type`
- `date`
- `duration`
- `distance_km`
- `elevation_gain`
- `elevation_loss`
- `hr_avg`
- `hr_max`

## Installation

```bash
cd /Users/mio/DEV/SuuntoExportActivity
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Si vous souhaitez chiffrer les exports:

```bash
pip install -e '.[crypto]'
```

## Configuration

```bash
cp .env.example .env
```

Variables API minimales:

- `SUUNTO_CLIENT_ID`
- `SUUNTO_CLIENT_SECRET`
- `SUUNTO_SUBSCRIPTION_KEY`
- `SUUNTO_REDIRECT_URI`

Valeurs importantes par défaut:

- `SUUNTO_TOKEN_STORAGE=memory`
- `SUUNTO_REQUIRE_CONSENT=true`
- `SUUNTO_RATE_LIMIT_PER_MINUTE=10`

## Langue de l'application

- Par défaut, la CLI utilise la langue systeme:
  - systeme en francais => interface en francais
  - toute autre langue systeme => interface en anglais
- Override possible:
  - variable d'environnement `SUUNTO_LANG=fr|en`
  - argument CLI global `--lang fr|en`

## Flux OAuth2

1. Générer l'URL d'autorisation:

```bash
suunto-export auth-url
```

2. Échanger le code et exporter en une seule commande (recommandé avec le mode `memory`):

```bash
suunto-export export --auth-code "<AUTH_CODE>"
```

Vous pouvez aussi échanger le code séparément:

```bash
suunto-export exchange-code --code "<AUTH_CODE>"
```

## Commandes

### Export depuis l'API

```bash
suunto-export export \
  --start-date 2026-01-01 \
  --end-date 2026-12-31 \
  --output-dir ./output
```

### Parsing local

```bash
suunto-export parse-local \
  --input /chemin/vers/fichiers \
  --output-dir ./output
```

### Export chiffré

```bash
suunto-export export --auth-code "<AUTH_CODE>" --encrypt-output --passphrase "<SECRET>"
```

### Suppression des données exportées

```bash
suunto-export delete-data --output-dir ./output
```

Pour effacer aussi le cache token (si `SUUNTO_TOKEN_STORAGE=file`):

```bash
suunto-export delete-data --output-dir ./output --include-tokens
```

## Docker

```bash
cp .env.example .env
mkdir -p output .tokens data

docker compose build

docker compose run --rm suunto-export auth-url
docker compose run --rm suunto-export export --auth-code "<AUTH_CODE>"
```

Pour le parsing local en Docker, placez les fichiers dans `./data` puis:

```bash
docker compose run --rm suunto-export parse-local --input /data
```

## Bonnes pratiques

- Ne partagez pas vos exports, tokens ou credentials.
- N'utilisez pas de scraping ni de méthode non autorisée.
- Ce projet est prévu pour usage personnel, sauf accord partenaire valide.

## Vérification rapide

```bash
python -m compileall src
```
