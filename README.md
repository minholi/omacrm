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
