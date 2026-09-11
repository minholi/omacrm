# OmaCRM — Roadmap & Development Log

> **Purpose:** record the agreed plan, current status and next steps so work can
> be resumed at any time by any developer/agent. Architecture conventions live
> in [AGENTS.md](AGENTS.md); run instructions live in [README.md](README.md).

_Last updated: 2026-09-11 — Phases A–F complete plus the Entity Manager,
notifications, mass update, the customer portal, automation extras and
phone/address utilities, stream reactions, layout drag-and-drop, the
workflow webhook action, inbound email and live stream updates
(177 tests passing). See the
[deferred backlog](#deferred-backlog-not-yet-implemented) for known gaps._

## Vision

Reimplement the main features of **EspoCRM** on Django, with the **django-unfold
admin as the permanent primary interface** (no SPA is planned; features are
built as admin pages, actions, datasets and custom Unfold views).

## Locked decisions

- **Runtime:** Python 3.13, Django 5.2 LTS, django-unfold 0.105, SQLite.
- **Background work:** DB-backed `Job`/`ScheduledJob` + `run_jobs`/`run_cron`
  management commands (no Redis/Celery). Swap to Celery later if needed.
- **Metadata-driven:** built-in entity definitions live in code (`EntityDef`/
  `FieldDef`); custom fields and layouts are DB rows layered on top. Custom
  fields are stored in each record's `custom_data` JSON.
- **ACL:** roles attached to users/teams with levels
  `yes|all|team|own|no`, plus field-level levels; enforced in admin, API and
  datasets.
- **Integrations:** DRF, django-filter, django-import-export,
  django-simple-history, django-money, djangoql, django-hijack,
  django-constance, pygments.
- **Soft delete** via `deleted` flag; audit + history via simple-history;
  stream/activity feed via `Note`.

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| A — Foundation | Runtime, core models, metadata registry, ACL, jobs, DRF API, Unfold base | ✅ done |
| B — Sales CRM | Accounts, Contacts, Leads + conversion, Opportunities, Tasks, rules, dashboard | ✅ done |
| C — Collaboration | Calendar, reminders, stream/mentions, attachments, notifications, avatars | ✅ done |
| D — Productivity | Cases, Knowledge Base, Documents, Email templates/send, multi-currency | ✅ done |
| E — Marketing | Target lists, campaigns, mass email, lead capture, webhooks | ✅ done |
| F — Customization | Formula engine, workflow rules, layout editor, role/ACL editor | ✅ done |
| G — Platform | Entity Manager, notifications, portal, utilities, inbound email and live stream updates done; saved filters next | 🚧 in progress |

## What was delivered (by phase)

### Phase A — Foundation
- Runtime upgrade to Python 3.13 / Django 5.2 LTS / Unfold 0.105 and all
  integrations; Unfold `SIDEBAR`, dashboard callback, constance settings.
- `core` models: custom `User`, `Team`/`TeamUser`/`Role`, `Preferences`,
  `Attachment`, `Note`, `Notification`, `Job`/`ScheduledJob`, `CustomField`,
  `Layout`, `CustomLink`, `Currency`; `BaseEntity`/`CustomDataMixin`.
- Metadata registry (`EntityDef`/`FieldDef`, DB merge + cache invalidation),
  metadata-driven `MetadataModelAdmin` (forms/lists/filters/search), ACL
  service, hook registry, stream/audit, notifications, duplicate finder,
  DB-backed job runner, DRF `RecordViewSet` + router at `/api/v1/{entity}/`.
- Commands: `rebuild_metadata`, `run_jobs`, `run_cron`, `seed_demo`.

### Phase B — Sales CRM
- `Account`, `Contact` (+`AccountContact`), `Lead`, `Opportunity`
  (+`OpportunityContact`), `Task`, `Call`, `Meeting`, `Reminder`.
- Business rules in `crm/hooks.py`: stage→probability, `last_stage`, weighted
  amount, `converted_at`, task `date_completed`, contact↔account link, event
  duration, base-currency converted amounts, case numbering, KB `body_plain`.
- `LeadConversionService` + Unfold **Convert Lead** dialog action.
- Unfold UX: status/stage badges, two-line name cells, price formatting,
  autocomplete FKs, inlines, duplicate checking, CSV/XLSX import/export.

### Phase C — Collaboration
- Server-rendered **Calendar** page (`/admin/calendar/`) + agenda over
  Call/Meeting/Task, ACL-scoped, sidebar entry.
- **Reminders**: `reminders` JSON → `Reminder` rows; `crm.send_reminders`
  scheduled job → notifications.
- **Stream**: per-record Stream dataset tab + **Post Note** dialog action;
  `@user_name` mentions create notifications.
- **Attachments** generic inline; **notifications** unread badge, dashboard
  card, bulk mark-as-read; Unfold **avatar** integration.

### Phase D — Productivity
- **Cases** with auto number, status/priority/type; **Knowledge Base**
  categories/articles with `body_plain` and publish/archive scheduled job;
  **Documents** + folders with file upload and related records.
- **Email**: `EmailTemplate` + Django-template rendering, `send_email()`
  service, **Send Email** dialog action on Account/Contact/Lead, `Email`
  stream note. Dev uses the console email backend.
- **Multi-currency**: `Currency` (rate = value of one unit in base currency,
  `base_currency` constance setting), conversion service, `amount_converted`
  on Opportunity/Lead, USD/EUR/BRL seeded.

## Phase E — Marketing (implemented)

**Delivered:** `TargetList`/`TargetListCategory`/`TargetListMember` (generic
members, opt-out, membership dialog actions on Account/Contact/Lead);
`Campaign` + tracking URLs + `CampaignLogRecord` with public click-redirect and
open-pixel endpoints; `MassEmail` + `EmailQueueItem` with queue builder and
`crm.process_mass_email` job (skips opted-out and missing emails, updates
campaign counters); `LeadCapture` web-to-lead public endpoint
(`POST /api/v1/lead-capture/<api_key>/`); `Webhook` + `WebhookQueueItem` with
signal bridge and `core.process_webhooks` delivery job (HMAC signing, retries).
See `crm/models/marketing.py`, `crm/services/{target_lists,mass_email}.py`,
`crm/views.py`, `core/services/webhooks.py`.

Remaining ideas for later (not blocking Phase F): per-recipient unsubscribe
links/opt-out from mass email, bounce/soft-bounce classification, campaign
revenue tracking, and web-to-lead double opt-in.

## Phase F — Customization engine (implemented)

**Delivered:**

- **Formula engine** (`core/services/formula.py`, `core/models/automation.py`):
  line-based scripts per entity/event (`before_save`/`after_save`) with a
  sandboxed AST evaluator (no imports, no private attributes, whitelisted
  functions such as `notify`, `update`, `set`, `days`). Editable in the admin
  under Customization → Formulas.
- **Workflow rules** (`core/services/workflows.py`, `Workflow` model):
  trigger (entity + create/update/delete) → optional condition expression →
  actions (`set_field`, `notify`, `create_record`); re-entrancy guarded.
  Editable under Customization → Workflows.
- **Layout editor** (`/admin/layout-editor/`): server-rendered page to pick
  list columns and edit the detail sections JSON per entity; writes `Layout`
  rows consumed by the metadata registry and admin.
- **Role/ACL editor** (`/admin/access/role/<id>/`): scope matrix
  (read/create/edit/delete × yes/all/team/own/no) plus field-level access;
  linked from the Role changelist.

## Phase G — Platform features (in progress)

**Delivered — Entity Manager (runtime custom entities):** `CustomEntity` rows
are materialized into per-entity proxy models, admins and registry entries
(`core/services/custom_entities.py`, `core/models/dynamic.py`,
`core/admin/dynamic.py`). Records are stored in `DynamicRecord` (JSON
`custom_data`), so no runtime schema changes are needed; `CustomField` rows
work on custom entities exactly like built-ins, and the Layout editor,
formulas, workflows, stream and webhooks apply to them too. Custom entities
appear in the admin under "All applications"; admin URLs and API endpoints are
built at startup, so **restart the server after creating a custom entity**.
Startup re-materializes all active entities automatically.

**Delivered — real-time + email notifications:**
`GET /admin/notifications/stream/` is a staff-only SSE endpoint
(`core/admin/views.py`) emitting unread counts and new notifications;
`core/static/core/js/notifications.js` (loaded via `UNFOLD["SCRIPTS"]`)
updates the sidebar badge live and shows toasts. The
`core.send_notification_emails` scheduled job emails a digest of unread
notifications — controlled by the `notification_email_enabled` constance
setting and the per-user `Preferences.notifications_config.email` flag.

**Delivered — mass update + automation extras:** entity admins expose a
"Mass update selected records" action (enum/bool fields and assigned user,
ACL-checked, session-backed selection) with an intermediate page; formulas can
write custom fields with `custom.<name> = value` and use string/date helpers
(`lower`, `upper`, `substring`, `replace`, `contains`, `coalesce`,
`parse_date`, `date_format`); workflows gained a `send_email` action
(record field or literal recipient, templated subject/body, stream note).

**Delivered — customer portal (MVP):** `PortalRole` + `User.portal_roles`
and `Contact.portal_user`; portal users (``type=portal``) sign in at
`/portal/`, see only their own cases (create/view) and published KB articles,
with access driven by `crm/services/portal.py::PortalAcl`. Portal users are
denied by the main admin/API ACL by design.

**Delivered — phone utilities:** `core/services/phone.py` normalizes,
validates and formats phone numbers with `phonenumbers`;
Account/Contact/Lead `phone_number` values are normalized to E.164 on save
using the `phone_default_region` constance setting (invalid values are kept
as typed).

**Delivered — stream reactions:** `UserReaction` (note + user + emoji)
with a toggle service, a per-note **React** row action in the admin (dialog
emoji picker) and reaction summaries in the Notes list and Stream tab.

**Delivered — live stream updates:** `StreamEvent` rows are queued when a
stream note is created on a record assigned to someone other than the actor;
the `/admin/notifications/stream/` SSE endpoint emits them and the admin JS
shows a toast. Old events are pruned by `core.cleanup_stream_events`.

**Delivered — inbound email:** `Email` + `EmailAccount` models; IMAP
accounts store passwords encrypted (Fernet key derived from `SECRET_KEY`).
`core/services/inbound_email.py` parses RFC822 messages (plain/HTML bodies,
addresses, date, Message-ID), deduplicates by Message-ID, links senders to
Contact/Lead/Account records and imports them as `Email` records; the
`core.fetch_inbound_email` job polls every active account. Manage accounts
under System → Email Accounts (with a "Fetch now" action) and messages under
Activities → Emails.

**Delivered — address utilities:** `core/services/address.py` formats
`address_*`/`billing_address_*`/`shipping_address_*` blocks into display
strings, skipping empty parts.

**Delivered — workflow webhook action:** an action like
`{"type": "webhook", "webhook_id": 1}` enqueues a `WebhookQueueItem` with the
record payload for a configured (active) webhook; missing/invalid webhooks are
ignored without breaking the save.

**Delivered — layout drag-and-drop:** the Layout Editor renders list
columns as draggable rows (native HTML5 drag and drop); the saved layout
keeps the on-screen order, which the admin list view honours.

**Next in Phase G:**

- Extra workflow actions (update related records) and more formula functions.
- Optional: saved filter presets.
The [deferred backlog](#deferred-backlog-not-yet-implemented) below is the full,
authoritative list of postponed work with origins and targets.

## Deferred backlog (not yet implemented)

Items intentionally postponed. "Origin" is the phase where they were scoped;
"Target" is when they are expected to land (Phase G above, or later backlog).
Nothing here is required for the current feature set to be usable.

### Platform & API

| Item | Origin | Notes / target |
| --- | --- | --- |
| API `where` filter DSL (Espo-style JSON) | A | API has text search, ordering and django-filter; no nested and/or translator. Target: backlog. |
| API key authentication (`X-Api-Key`) | A | `User.api_key` exists, but DRF only offers session/token auth. Target: backlog. |
| Soft-delete restore UI | A/B | `deleted` flag + `all_objects` exist; no admin action/filter to view and restore deleted records. Target: backlog. |
| Global search page across entity types | B | Unfold command palette searches registered models; no cross-entity results page. Target: backlog. |
| Saved filter presets; custom command palette entries | C | — Target: backlog. |
| Stream post attachments (file upload in Post Note) | C | `Note.attachments` M2M exists but the dialog has no upload. Target: backlog. |
| Sales-by-month chart on the dashboard | C | dashboard has KPI cards only. Target: backlog. |

### CRM / activities

| Item | Origin | Notes / target |
| --- | --- | --- |
| Call/Meeting attendees + invitations/acceptance statuses | B/C | Events are simple records: no `Attendance` model, no invite/confirm flow. Target: backlog. |
| Recurring events (RRULE) | C | Calendar is one-off events only. Target: backlog. |
| Duplicate merge UI | B | Duplicate detection exists; merging two records does not. Target: backlog. |
| Related-record datasets/panels beyond the Stream tab | B/C | Related lists are changelists/inlines only. Target: backlog. |

### Email & marketing

| Item | Origin | Notes / target |
| --- | --- | --- |
| Inbound email advanced features (folders, per-user accounts, reply threading, attachments) | D/G | Basic IMAP fetch/import is done; folders/threading/attachments are not. Target: backlog. |
| Per-recipient unsubscribe links / opt-out from mass email | E | Opt-out is currently managed via target-list actions. Target: Phase G. |
| Bounce classification (hard/soft) and campaign revenue tracking | E | `CampaignLogRecord` supports `Bounced` but nothing sets it. Target: backlog. |
| Web-to-lead double opt-in and hosted form page | E | Only the JSON endpoint exists. Target: backlog. |
| Multi-currency historical rate tables + rate sync job | D | Manual `Currency.rate` values; conversion uses the current rate only. Target: backlog. |

### Customization & platform (Phase G)

| Item | Origin | Notes / target |
| --- | --- | --- |
| Drag-and-drop layout manager for detail sections/tabs | F | List columns can be reordered by dragging; detail sections are still JSON. Target: backlog. |
| Workflow actions: update related records | F | Rules support `set_field`, `notify`, `create_record`, `send_email` and `webhook`. Target: backlog. |
| Portal beyond Cases/KB (documents, mass-update of profile) | G | Current portal exposes own cases + published KB only. Target: backlog. |

## Resume checklist

```bash
uv sync
uv run python src/omacrm/manage.py check     # must be clean
uv run python src/omacrm/manage.py test      # must be green (177 tests)
uv run python src/omacrm/manage.py seed_demo # admin/admin12345, demo/demo12345
uv run python src/omacrm/manage.py runserver
```

1. Read `AGENTS.md` for architecture and conventions.
2. Pick an item from **Phase G** or the **deferred backlog** above and follow
   the pattern used by the closest existing entity/model (model →
   `metadata.py` registration → `MetadataModelAdmin` → hooks/services →
   tests).
3. Run `check` and `test` after every change; keep the metadata registry and
   import/export/API caches in mind (`rebuild_metadata`).
4. Update `AGENTS.md` (layout/concepts) and this file (phase status + log)
   when a phase or significant feature lands.

## Change log

- **2026-09-11** — Live stream updates: `StreamEvent` queue, SSE delivery
  and admin toasts for changes on assigned records (177 tests).

- **2026-09-11** — Inbound email: `Email`/`EmailAccount`, encrypted IMAP
  credentials, message import with dedup and CRM parent linking, and the
  `core.fetch_inbound_email` job (172 tests).

- **2026-09-11** — Address formatting utilities for record address blocks
  (161 tests).

- **2026-09-11** — Workflow webhook action enqueues webhook payloads for
  configured webhooks (156 tests).

- **2026-09-11** — Layout Editor drag-and-drop for list column ordering
  (153 tests).

- **2026-09-11** — Stream reactions: `UserReaction`, toggle service and
  React row action; summaries in Notes/Stream (151 tests).

- **2026-09-11** — Phone utilities: `phonenumbers`-based
  normalize/validate/format service and automatic E.164 normalization for
  Account/Contact/Lead phone numbers (`phone_default_region` setting)
  (146 tests).

- **2026-09-11** — Automation extras: workflow `send_email` action and
  formula string/date helpers (138 tests).

- **2026-09-11** — Customer portal MVP: portal users/roles, own-case list,
  create and detail, published knowledge base, portal ACL (134 tests).

- **2026-09-11** — Mass update action (enum/bool/assigned user, ACL-checked)
  and formula custom-field support (`custom.<name> = value`) (125 tests).
- **2026-09-11** — Project published on GitHub under
  **AGPL-3.0-or-later** (same license as EspoCRM); it is an independent
  reimplementation and contains no EspoCRM code.
- **2026-09-11** — Real-time + email notifications: SSE endpoint with live
  sidebar badge/toasts and `core.send_notification_emails` digest job
  (constance toggle + per-user opt-out) (119 tests).
- **2026-09-11** — Fix: removing a custom entity now deletes its content type
  (cascading stream notes/attachments/notifications), clears the content-type
  cache, and purges stale content types at startup; dashboards/note lists no
  longer crash on dangling generic parents; layout editor returns 404 for
  unknown entities (111 tests).
- **2026-09-11** — Phase G started: Entity Manager (runtime custom entities,
  proxy admins, JSON-backed records) delivered (109 tests).
- **2026-09-11** — Documentation: added the deferred backlog table (platform,
  CRM, email/marketing, customization) and corrected stale notes.
- **2026-09-11** — Phase F implemented: formula engine, workflow rules,
  layout editor, role/ACL editor (103 tests).
- **2026-09-11** — Phase E implemented: target lists, campaigns + tracking,
  mass email queue/job, lead capture endpoint and webhooks (86 tests).
- **2026-09-11** — Phases A–D implemented (70 tests). Documented this roadmap.
