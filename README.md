# OmaCRM

A CRM built on Django whose primary interface is the
[django-unfold](https://unfoldadmin.com) admin. It follows a metadata-driven
architecture inspired by [EspoCRM](https://www.espocrm.com): built-in entity
definitions live in code while custom fields and layouts are stored in the
database and layered on top.

Currently implemented: accounts, contacts, leads (with conversion),
opportunities (with stage/probability rules), tasks, calls, meetings, cases,
knowledge base, documents, email templates/sending, calendar, stream/notes,
attachments, notifications, reminders, import/export, a REST API and
multi-currency.

## Quickstart

Requirements: [uv](https://docs.astral.sh/uv/) (Python 3.13 is managed by uv).

```bash
uv sync
uv run python src/omacrm/manage.py migrate
uv run python src/omacrm/manage.py seed_demo   # rich demo dataset (admin/demo/portal logins)
uv run python src/omacrm/manage.py runserver
```

Open http://127.0.0.1:8000/ — it redirects to the admin.

Useful commands:

```bash
uv run python src/omacrm/manage.py check              # system checks
uv run python src/omacrm/manage.py test               # test suite
uv run python src/omacrm/manage.py run_jobs           # process background jobs
uv run python src/omacrm/manage.py run_cron --process # enqueue scheduled jobs
uv run python src/omacrm/manage.py rebuild_metadata   # clear metadata caches
```

## Demo deployment behind a reverse proxy

For an HTTPS demo the app can run under gunicorn while a reverse proxy
(e.g. Traefik) terminates TLS and forwards plain HTTP to `127.0.0.1:8020`.
Whitenoise serves the collected static files in that setup.

```bash
uv sync --group server
export DJANGO_DEBUG=0
export DJANGO_SECRET_KEY="a-long-random-production-secret"
export DJANGO_ALLOWED_HOSTS=crm.example.com
export DJANGO_CSRF_TRUSTED_ORIGINS=https://crm.example.com
export DJANGO_SERVE_MEDIA=1   # optional: let Django serve uploaded media

uv run python src/omacrm/manage.py migrate
uv run python src/omacrm/manage.py collectstatic --noinput
uv run --group server gunicorn omacrm.config.wsgi:application --bind 127.0.0.1:8020
```

Environment variables read by `config/settings.py`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_DEBUG` | `1` | Set to `0` outside local development. |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated host names. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | *(empty)* | Comma-separated full origins, e.g. `https://crm.example.com`. |
| `DJANGO_SERVE_MEDIA` | `0` | Set to `1` to serve `MEDIA_ROOT` through Django (demo only). |
| `DJANGO_SECRET_KEY` | development fallback | Set a unique value in production. |

The proxy must forward `X-Forwarded-Proto` (Traefik does by default) so Django
recognizes HTTPS requests through `SECURE_PROXY_SSL_HEADER`.

## Documentation

- [ROADMAP.md](ROADMAP.md) — agreed plan, phase status, next steps and a
  resume checklist for future development.
- [AGENTS.md](AGENTS.md) — architecture, conventions, key concepts and gotchas.

## License

Licensed under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later) — the same license as EspoCRM. See [LICENSE](LICENSE).

OmaCRM is an independent reimplementation inspired by
[EspoCRM](https://www.espocrm.com); it is not affiliated with or endorsed by
the EspoCRM project, and contains no EspoCRM code.
