# CampusEquip frontend

The UI reads the existing project through the Flask API. In live mode,
PostgreSQL supplies campuses, equipment types and contracts; MongoDB supplies
event history and ingestion batches; Redis supplies the incident projection;
TimescaleDB supplies positions and measured Airflow task attempts. A live
return form can publish a return event through the existing axes 3-4 validation
and ingestion pipeline. The browser never connects directly to a database.

## Run the project and frontend

From `CampusEquip_etudiant` in PowerShell:

```powershell
docker compose up -d --build
docker compose --env-file .env -f app/docker-compose.yml up -d
```

Open <http://localhost:5173>, then use **Refresh** in the header if needed.
The frontend Nginx container joins the main Compose network and proxies
`/api/` requests directly to the Flask app container. The API endpoint is
`/api/prototype/snapshot`. Live return submissions use
`POST /api/prototype/events`; Flask publishes a one-event, hash-verified lot
and passes it through the same MongoDB ingestion function used by the event
pipeline. The source lot is retained under `axes_3_4/flux_ui/` for inspection.

For presentations, open <http://localhost:5173/pipeline.html>. This standalone
architecture view starts at PostgreSQL and progressively reveals connected
stages as you advance. Use Previous/Next or the arrow keys to navigate, Restart
to begin again, and Show complete architecture (or Escape) to inspect the full
map. Full screen is available from the presentation controls. Each stage has a
component, purpose, input, processing, output and technology explanation. Its
presentation controls are visual only and do not run pipeline commands.

If you do not have a `.env` file and use the default ports, omit the
`--env-file .env` option from the frontend command.

The existing Compose stack remains responsible for all databases and the
pipeline. Start it before the frontend so the `campusequip_default` network and
Flask app are available. The frontend Compose file only serves static files
and proxies API requests; the return-event endpoint is the only write operation
exposed by this prototype. It is bound to localhost. If port 5173 is occupied,
set `APP_PROTOTYPE_PORT=5174` in `.env`.

Stop only the frontend with:

```powershell
docker compose -f app/docker-compose.yml down
```

## Data boundaries

- **Live mode** shows actual project records. The returns page can append an
  immutable return event to MongoDB through the validated event pipeline; it
  does not alter PostgreSQL contract status, physical inventory, or availability.
- The project schema contains catalogue types and historical contracts, not
  physical inventory, availability, return due dates, inspection state, or an
  incident assignment workflow. The UI does not invent these values.
- MongoDB's event history and batch journal are read as stored. Redis and
  TimescaleDB are reported as separate data sources; Airflow task metrics are
  the attempts recorded in TimescaleDB, not a live Airflow scheduler status.
- If the API cannot be reached, the UI labels its illustrative fallback as
  **sample data**. Use **Preferences → Return to live data** to retry.
- The three roles are interface previews, not authentication or authorization.
- **Sample mode** keeps the original browser-local forms and simulation. Its
  actions do not enter the real pipeline.

For static-only exploration without Docker, run `python -m http.server 5173`
from this directory. That mode uses sample data because it cannot proxy the
project API.
