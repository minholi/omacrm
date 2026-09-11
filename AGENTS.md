# AGENTS.md

## Overview

`omacrm` is a Django CRM whose primary application interface is the
**django-unfold admin** (no SPA is planned). It follows a metadata-driven
architecture inspired by EspoCRM: built-in entity definitions live in code,
while custom fields and layouts are stored in the database and layered on top.
Dependencies are managed with [uv](https://docs.astral.sh/uv/).

Runtime baseline: **Python 3.13**, **Django 5.2 LTS**, **django-unfold 0.105+**,
with DRF, django-filter, django-import-export, django-simple-history,
django-money, djangoql, django-hijack, django-constance and pygments.

See [ROADMAP.md](ROADMAP.md) for the agreed feature plan, phase status and the
resume checklist; this file documents the current architecture only.

## Essential Commands

Run everything from the repository root. `manage.py` is **not** at the root —
it lives at `src/omacrm/manage.py`.

```bash
uv sync                                          # install deps + editable install
uv run python src/omacrm/manage.py runserver     # dev server (default :8000)
uv run python src/omacrm/manage.py migrate       # apply migrations
uv run python src/omacrm/manage.py makemigrations
uv run python src/omacrm/manage.py check         # system checks
uv run python src/omacrm/manage.py test          # tests (discovers from src/)
uv run python src/omacrm/manage.py seed_demo     # rich demo dataset (--reset to rebuild)
uv run python src/omacrm/manage.py rebuild_metadata
uv run python src/omacrm/manage.py run_jobs [--loop] [--limit N] [--queue Q]
uv run python src/omacrm/manage.py run_cron [--process]
uv run python src/omacrm/manage.py createsuperuser
uv run python src/omacrm/manage.py shell
```

`seed_demo` is idempotent and refuses to run when business data already
exists; `--reset` hard-deletes demo business data (keeping the `admin`, `demo`
and `portal` logins) and rebuilds it. Other flags: `--rng-seed` (generated
values), `--base-url` (links in seeded data) and the password flags. The
seeders live in `core/services/demo/` and create demo users/teams, portal
access, currencies with dated rates, sales pipeline, cases/KB/documents,
activities/attendees, inbound email threads, marketing (campaigns with
consistent logs/counters, mass email, lead capture), stream notes/reactions/
notifications, webhooks, custom fields/layouts, formulas/workflows and a
`Project` custom entity (available in the sidebar and API immediately).

## Layout

```
src/omacrm/
  manage.py
  config/            # project package: settings, urls, wsgi/asgi, test_runner
  core/              # platform layer
    models/          # base.py (BaseEntity/CustomDataMixin), user.py, meta.py,
                     # collab.py (Attachment/Note/Notification/UserReaction),
                     # jobs.py, currency.py, webhooks.py, automation.py
                     # (Formula/Workflow), dynamic.py (CustomEntity/
                     # DynamicRecord), email.py (Email/EmailAccount)
    metadata/        # defs.py, registry.py, fields.py, entities.py, email.py
    services/        # acl, hooks, stream, notifications, duplicates, jobs,
                     # context, builtin_jobs, currency, webhooks, formula,
                     # workflows, custom_entities, phone, reactions, address,
                     # crypto, inbound_email, navigation, relations,
                     # custom_fields, demo/ (seed_demo)
    admin/           # base.py (MetadataModelAdmin/AclAdminMixin), users,
                     # metadata_admin, collab, jobs, currency, webhooks,
                     # automation, dynamic, email, dashboard, views.py
                     # (calendar + layout/ACL editors), datasets.py, inlines.py
    api/             # serializers.py, viewsets.py, router.py
    middleware.py    # CurrentUserMiddleware
    forms.py, managers.py
    management/commands/  # rebuild_metadata, run_jobs, run_cron, seed_demo
    tests/
  crm/               # CRM domain entities
    models/          # base.py (enums/event base), sales.py (Account/Contact/
                     # Lead/Opportunity), activities.py (Task/Call/Meeting/
                     # Reminder), cases.py, knowledge.py, documents.py, email.py,
                     # marketing.py (target lists, campaigns, mass email,
                     # lead capture)
    metadata.py      # EntityDefs for CRM entities
    hooks.py         # probability/lastStage/weighted amount, convertedAt,
                     # task dateCompleted, contact-account link, durations,
                     # reminder sync, case numbering, KB bodyPlain,
                     # base-currency converted amounts
    services/        # lead_convert.py, reminders.py (crm.send_reminders),
                     # knowledge.py (crm.control_kb_article_status), email.py,
                     # target_lists.py, mass_email.py, portal.py (PortalAcl)
    views.py         # public campaign tracking + lead capture endpoints
    portal_views.py, portal_urls.py   # customer portal (/portal/)
    admin.py, tests/
  templates/admin/
    index.html       # dashboard (KPIs, activity, notifications)
    crm/calendar.html
```

## Key Concepts

- **BaseEntity** (`core/models/base.py`): audit columns, `assigned_user`,
  `teams`, soft delete (`deleted`), `custom_data` JSON and simple-history.
  `objects` hides soft-deleted rows; `all_objects` includes them. Entity
  changelists can show deleted records (`?deleted=1`) and restore them via the
  bulk or row actions. `CustomDataMixin` adds just `custom_data` (used by
  User/Team/Role).
- **Metadata registry** (`core/metadata/`): `EntityDef`/`FieldDef` register from
  each app's `metadata` module; `CustomField`/`Layout` DB rows merge on top.
  Cache invalidates on metadata model save via signals; `rebuild_metadata`
  clears registry and API serializer caches.
- **Custom fields** live in `custom_data`; `MetadataModelAdmin` renders them in
  forms/lists/filters/searches from metadata (Enum/Bool get list filters).
  Types: varchar, text, enum, multiEnum, bool, int, float, decimal, number
  (per-entity sequence via `NextNumber`), date, datetime, email, phone
  (normalized to E.164), url, currency, address (composite), file, image,
  attachmentMultiple (stored as `Attachment` ids) and foreign (read-only value
  through a custom link); `core/services/custom_fields.py` keeps decimals
  JSON-safe. A model must have `custom_data` to support them.
- **ACL** (`core/services/acl.py`): `Role.data = {EntityType: {read|create|
  edit|delete: yes|all|team|own|no}}`, `field_data` for field level; roles come
  from users and their teams, highest wins. Users without roles get the
  entity's `acl_default` ("all" unless the entity sets otherwise; core
  User/Team/Role use "no"). Own/team scoping needs `assigned_user`,
  `created_by` or `teams` on the model.
- **Hooks/stream** (`core/services/hooks.py`, `stream.py`): before/after
  save/delete hooks wired through signals; creates `Note` stream entries on
  create/update/delete and assignment notifications.
- **Jobs** (`core/services/jobs.py`): DB-backed `Job`/`ScheduledJob`; handlers
  registered with `@jobs.register("key")`; `run_jobs` processes the queue,
  `run_cron` enqueues due scheduled jobs (croniter).
- **API**: `/api/v1/{entity}/` with metadata-driven serializers/viewset
  (`core/api/`), ACL-scoped, session + token + `X-Api-Key` auth (generate keys
  with the User admin action; `core/api/auth.py`). Supports django-filter,
  search, ordering, limit/offset pagination and an Espo-style `where` JSON
  filter (`core/api/filters.py`, e.g. `?where=[{"type":"equals","attribute":
  "stage","value":"Proposal"}]`, with `and`/`or`/`not` groups).
- **Import/export**: `MetadataImportExportMixin`
  (`core/admin/import_export.py`) gives entity admins CSV/XLSX import and
  export from metadata; `MetadataModelAdmin` also provides a CSV export action.
- **CRM**: lead conversion via `LeadConversionService` and the Unfold detail
  dialog action `Convert Lead`; opportunity stage rules (probability,
  last stage, weighted amount) run in `crm/hooks.py`.
- **Activities**: `/admin/calendar/` (`core/admin/views.py`) is a server-rendered
  month calendar + agenda over Call/Meeting/Task. `crm/services/reminders.py`
  syncs the `reminders` JSON of events/tasks into `Reminder` rows and the
  `crm.send_reminders` scheduled job turns due reminders into notifications.
  Call/Meeting attendees live in `Attendance` (user/contact/lead + acceptance
  status) with an admin inline and a **Send invitations** action; invitations
  carry signed accept/decline links handled by the public
  `event_confirmation` view (`crm/services/event_invitations.py`). Recurring
  Call/Meeting rules (`recurrence_rule` JSON) are materialized into occurrence
  records sharing a `recurrence_uid`
  (`crm/services/recurrence.py`, regenerated by hooks).
- **Stream & attachments**: stream-enabled entities get a Stream dataset tab
  and a `Post Note` dialog action (mentions `@user_name` create notifications);
  notes support emoji reactions (`UserReaction` + React row action, summaries
  in Notes/Stream); `AttachmentInline` adds file uploads to entity change pages.
- **Notifications**: unread count is shown as a sidebar badge and on the
  dashboard; `core.send_notification_emails` emails a digest of unread
  notifications (constance `notification_email_enabled` + per-user
  `Preferences.notifications_config.email`), and
  `/admin/notifications/stream/` is an SSE endpoint consumed by
  `core/static/core/js/notifications.js` (loaded via `UNFOLD["SCRIPTS"]`) for
  live badge updates and toasts. Admins can mark notifications read in bulk.
- **Live stream updates**: changing a stream-enabled record assigned to
  someone else queues a `StreamEvent`; the same SSE endpoint delivers it and
  the admin shows a toast (`core/services/stream.py`,
  `core.cleanup_stream_events` prunes old events).
- **Global search**: `/admin/global-search/` (`GlobalSearchView`) searches the
  `search_fields` + custom text fields of every registered entity, ACL-scoped,
  and groups results per entity with links to the change pages.
- **Cases/KB/Documents**: `Case` gets an auto number; `KnowledgeBaseArticle`
  derives `bodyPlain` and a scheduled job publishes/archives by date;
  `Document`/`DocumentFolder` support file uploads and related records.
- **Email**: `EmailTemplate` bodies use Django template syntax; the
  `Send Email` dialog action on Account/Contact/Lead renders a template,
  sends via Django mail and logs an `Email` note on the record stream.
  Dev uses the console email backend (`EMAIL_BACKEND` in settings).
  Inbound: `EmailAccount` rows (IMAP credentials encrypted via
  `core/services/crypto.py`) are polled by the `core.fetch_inbound_email`
  job across every comma-separated `folder`, which imports messages as
  `Email` records with Message-ID dedup, links senders to Contact/Lead/Account
  parents, threads replies via `In-Reply-To`/`References`
  (`Email.parent_email`/`thread_id`) and stores MIME attachments as
  `Attachment` rows (attachment inline on the Email admin).
- **Multi-currency**: `Currency.rate` is the value of one unit in the base
  currency (`base_currency` constance setting) and `CurrencyRate` rows hold
  dated history; `core/services/currency.py` converts using the effective
  date (Opportunity conversion uses its `close_date`) and the
  `core.sync_currency_rates` job loads today's rates from the constance
  `currency_rates_url`; hooks fill `amount_converted` on Opportunity/Lead.
- **Phone numbers**: `core/services/phone.py` (libphonenumber) provides
  `normalize_phone`/`is_valid_phone`/`format_phone`; CRM hooks normalize
  Account/Contact/Lead `phone_number` to E.164 on save using the
  `phone_default_region` constance setting. `core/services/address.py` formats
  `address_*`/`billing_address_*`/`shipping_address_*` blocks for display.
- **Marketing**: `TargetList` members are generic (`TargetListMember` with
  content type + `opted_out`); `MassEmail` queue is built from target lists
  (opted-out skipped) and processed by the `crm.process_mass_email` job, which
  appends a signed per-recipient unsubscribe link (`/unsubscribe/<token>/` →
  target-list opt-out + campaign Opted Out log); campaigns log
  Sent/Opened/Clicked/Bounced records (hard/soft bounces via
  `record_bounce` or the queue admin actions), track revenue from Closed Won
  opportunities automatically, and have public click/open endpoints in
  `crm/views.py`. `LeadCapture` exposes a public
  `POST /api/v1/lead-capture/<api_key>/` endpoint with optional double opt-in
  (signed confirmation link before the lead joins the target list).
- **Webhooks**: `Webhook`/`WebhookQueueItem` (`core/models/webhooks.py`);
  signals enqueue create/update/delete events (soft delete maps to `delete`)
  and the `core.process_webhooks` job delivers them (HMAC signature, retries).
- **Customization**: `Formula` scripts run before/after save through a
  sandboxed AST interpreter (`core/services/formula.py`) and can assign model
  fields or custom fields (`custom.<name> = value`), with string helpers
  (`lower`, `upper`, `substring`, `replace`, `coalesce`, `concat`, `split`,
  `join`, `capitalize`, `is_empty`), number helpers (`number_format`, `ceil`,
  `floor`, `sqrt`) and date helpers (`parse_date`, `date_format`, `date_add`);
  `Workflow` rules evaluate a condition and run actions
  (`set_field`, `notify`, `create_record`, templated `send_email`, `webhook`,
  `update_related`) in `core/services/workflows.py`, wired in
  `core/services/hooks.py`. Entity
  admins also provide a **Mass update** action (enum/bool fields + assigned
  user) through an intermediate page (`MassUpdateView`). Entity admins also
  offer a **Merge selected records** action (`MergeView` +
  `core/services/merge.py`): pick the master and per-field values; stream
  notes, attachments, emails and nullable reverse FKs are re-pointed and the
  duplicate is soft-deleted. `/admin/layout-editor/`
  edits `Layout` rows (list columns draggable for ordering, plus a
  drag-and-drop detail-section editor with a JSON fallback);
  `/admin/access/role/<id>/` edits a role's scope and field-level access
  matrix. Entity changelists offer per-user **saved filters** (`SavedFilter`).
  Caches invalidate on model saves. The Unfold command palette gets custom
  entries (`UNFOLD["COMMAND"]["search_callback"]` →
  `core/services/command_palette.py`): static commands, permission-filtered
  entity shortcuts (list/new) and the user's saved filters.
- **Entity Manager / custom entities**: `CustomEntity` rows are materialized
  at startup into proxy models, registry entries and admins backed by
  `DynamicRecord` (JSON `custom_data`) — see `core/services/custom_entities.py`.
  Create/edit them under Customization → Custom Entities; custom fields,
  layouts, formulas, workflows, stream and webhooks work on them. Entities
  expose icon/color, `show_in_menu`/`menu_order`, `stream`, sort, search and
  duplicate-check fields; the sidebar is built per request by
  `core/services/navigation.py`, saving an entity refreshes the URLconf and
  the catch-all `/api/v1/<Entity>/` routes resolve in runtime, so admin/API
  pages are available **without a restart**. The generated proxy models are
  marked `auto_created` so `makemigrations` never serializes them.
- **Custom relationships**: `CustomLink` rows describe a link from one entity
  to another (`belongsTo`/`hasMany`/`manyToMany`) and the reverse side is
  derived automatically; both directions are stored as mirrored `RecordLink`
  rows by `core/services/relations.py`. Admin forms render link/linkMultiple
  pickers (in the detail layout or a Relationships section), changelist columns
  show related names when the list layout includes the link, and the API
  reads/writes links by target ids (e.g. `{"account": 3}` / `{"contacts": [1,2]}`).
- **Portal**: customer-portal users are `User` records with `type=portal`
  linked to a `Contact` (`Contact.portal_user`) and granted `PortalRole`s;
  `/portal/` (server-rendered, no Unfold) exposes the user's own Cases and
  published Knowledge Base articles, active Documents linked to their contact
  or account (ACL-scoped downloads) and a profile page (edit contact info,
  change password). `crm/services/portal.py::PortalAcl`
  enforces `own`/`all`/`no` levels; the main `AclService` returns `no` for
  portal users, so they cannot use the admin or the REST API.
- **Admin**: every model admin should inherit `unfold.admin.ModelAdmin`;
  business entities use `MetadataModelAdmin` with `entity_type` set. Unfold
  integrations must be listed in `INSTALLED_APPS` before
  `django.contrib.admin` and before the package they restyle.

## Gotchas

- **App ordering**: `unfold` and its `unfold.contrib.*` apps must precede
  `django.contrib.admin`; `unfold.contrib.simple_history` before
  `simple_history`, `unfold.contrib.import_export` before `import_export`,
  `unfold.contrib.constance` before `constance`.
- **Custom fields** only work on models with `custom_data`
  (`BaseEntity`/`CustomDataMixin`). `CustomField.name` must be snake_case and
  must not collide with a built-in field.
- **Unfold styling**: project templates may only use CSS classes present in
  Unfold's compiled stylesheet; arbitrary Tailwind classes need a Tailwind
  build configured for the project (not set up).
- **Global settings** are edited with django-constance at
  `/admin/constance/config/` (base currency, formats, records per page, ...).
- **db.sqlite3** and `media/` are gitignored.
- **Tests** work from the repo root because of
  `omacrm.config.test_runner.OmacrmDiscoverRunner`, which discovers from `src/`.

## Conventions

- The Unfold admin is the primary, permanent UI; build features as admin pages,
  actions, datasets and custom Unfold views rather than a separate frontend.
- New entity types: define the Django model, register an `EntityDef` in the
  app's `metadata.py`, add the admin (MetadataModelAdmin) and it becomes
  available to the API router automatically.
- After any change run `uv run python src/omacrm/manage.py check` and
  `uv run python src/omacrm/manage.py test`.
