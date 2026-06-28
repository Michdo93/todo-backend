# ToDo-Backend

FastAPI Backend für die To-Do-Liste-App – Deploy auf Render.com.

## Lokale Entwicklung

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# Docs: http://localhost:8000/docs
```

## Deploy auf Render.com

Render.com → New → Web Service → Repo verbinden. `render.yaml` wird automatisch erkannt.

**Pflicht-Umgebungsvariablen:**

| Variable | Beschreibung |
|----------|-------------|
| `SECRET_KEY` | JWT-Key (min. 32 Zeichen, Render generiert automatisch) |
| `ALLOWED_ORIGINS` | `https://Michdo93.github.io` |
| `RENDER` | `true` |

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| POST | `/auth/register` | Registrierung |
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Profil |
| GET | `/lists` | Alle Listen (mit item_count, done_count) |
| POST | `/lists` | Neue Liste |
| GET | `/lists/{id}` | Liste mit allen Items |
| PUT | `/lists/{id}` | Liste umbenennen |
| DELETE | `/lists/{id}` | Liste löschen |
| POST | `/lists/{id}/items` | Item hinzufügen |
| PATCH | `/lists/{id}/items/{item_id}` | Item bearbeiten/abhaken |
| DELETE | `/lists/{id}/items/{item_id}` | Item löschen |
| DELETE | `/lists/{id}/items/done/clear` | Alle erledigten löschen |
| GET | `/admin/users` | Alle User |
| PATCH | `/admin/users/{id}/toggle-active` | Sperren/Entsperren |
| PATCH | `/admin/users/{id}/toggle-admin` | Admin-Rechte |
| DELETE | `/admin/users/{id}` | User löschen |
| GET | `/admin/stats` | Statistiken |
