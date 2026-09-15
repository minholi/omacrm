# OmaCRM — Roadmap & Development Log

> **Purpose:** record the agreed plan, current status and next steps so work can
> be resumed at any time by any developer/agent. Architecture conventions live
> in [AGENTS.md](AGENTS.md); run instructions live in [README.md](README.md).

_Last updated: 2026-09-15 — Phases A–G implemented (runtime, sales CRM,
collaboration, productivity, marketing, customization, entity manager, portal,
notifications, utilities, inbound email, saved filters, soft-delete restore,
email template code editor with MJML source, dynamic logic server side,
stars/favourites, record following, per-user kanban order, compact changelist
currency columns, sortable generated columns, metadata-owned entity names,
captcha on public lead forms, the hosted web-to-lead form, app secrets, the
OpenAPI specification and its Swagger UI, the staff-only metadata management
API, the custom-entity record API fixes, the workflow engine's wait and
branch steps and the authoring editors with their visual builders and flow
visualization). 674 tests
passing; see the
[deferred backlog](#deferred-backlog-not-yet-implemented) and the
[EspoCRM parity backlog](#espocrm-parity-backlog-surveyed-2026-09-12) for the
remaining optional work._

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
| G — Platform | Entity Manager, notifications, portal, utilities, inbound email, live stream updates, saved filters, soft-delete restore | ✅ done |

## Next priorities (ordered, decided 2026-09-11)

Phases A–G are implemented; the remaining work is the optional backlog. The
agreed order is:

| # | Priority | Why | Status |
| --- | --- | --- | --- |
| P1 | API completion: `X-Api-Key` auth + `where` filter DSL | Unblocks external integrations; small and self-contained | ✅ done |
| P2 | Call/Meeting attendees, invitations and acceptance statuses | Core CRM parity (events are currently simple records) | ✅ done |
| P3 | Recurring events | Calendar completeness | ✅ done |
| P4 | Campaign advanced: unsubscribe links, bounce classification, revenue tracking, double opt-in | Marketing completeness | ✅ done |
| P5 | Global search page across entity types | Complements the command palette | ✅ done |
| P6 | Duplicate merge UI | Data quality (detection already exists) | ✅ done |
| P7 | Portal profile + documents | Customer self-service | ✅ done |
| P8 | IMAP advanced: folders, threading, attachments | Inbound email completeness | ✅ done |
| P9 | Historical currency rates | Multi-currency completeness | ✅ done |
| P10 | Polish: custom command palette entries, more formula functions, drag-and-drop detail sections | Small UX items | ✅ done |

An authoring-UX program for the JSON/script declarations (AU1–AU3) is
recorded below; it does not displace the parity backlog order (Tier 1 #7/#8
are still next there).

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
  `base_currency` constance setting) plus dated `CurrencyRate` history,
  conversion service (`date=effective date`), `core.sync_currency_rates` job
  fed by the constance `currency_rates_url`, `amount_converted` on
  Opportunity/Lead with the Opportunity using its `close_date`, USD/EUR/BRL
  seeded.

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
  functions such as `notify`, `update`, `set`, `days`) plus string helpers
  (`concat`, `split`, `join`, `capitalize`, `is_empty`), number helpers
  (`number_format`, `ceil`, `floor`, `sqrt`) and date math (`date_add`).
  Editable in the admin under Customization → Formulas.
- **Workflow rules** (`core/services/workflows.py`, `Workflow` model):
  trigger (entity + create/update/delete) → optional condition expression →
  actions (`set_field`, `notify`, `create_record`); re-entrancy guarded.
  Editable under Customization → Workflows.
- **Layout editor** (`/admin/layout-editor/`): server-rendered page to pick
  and drag list columns plus a visual drag-and-drop editor for detail
  sections (with a JSON fallback); writes `Layout` rows consumed by the
  metadata registry and admin.
- **Role/ACL editor** (`/admin/access/role/<id>/`): scope matrix
  (read/create/edit/delete × yes/all/team/own/no) plus field-level access;
  linked from the Role changelist.

## Phase G — Platform features (implemented)

**Delivered — Entity Manager (runtime custom entities):** `CustomEntity` rows
are materialized into per-entity proxy models, admins and registry entries
(`core/services/custom_entities.py`, `core/models/dynamic.py`,
`core/admin/dynamic.py`). Records are stored in `DynamicRecord` (JSON
`custom_data`), so no runtime schema changes are needed; `CustomField` rows
work on custom entities exactly like built-ins, and the Layout editor,
formulas, workflows, stream and webhooks apply to them too. Custom entities
appear in the admin under "All applications"; admin URLs and the capitalized
`/api/v1/<Entity>/` record endpoints resolve without a restart (the metadata
API manages definitions at `/api/v1/metadata/`, staff-only).
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

**Delivered — customer portal:** `PortalRole` + `User.portal_roles`
and `Contact.portal_user`; portal users (``type=portal``) sign in at
`/portal/`, see only their own cases (create/view) and published KB articles,
active Documents linked to their contact or account (ACL-scoped downloads)
and a profile page (edit contact info, change password), with access driven
by `crm/services/portal.py::PortalAcl`. Portal users are denied by the main
admin/API ACL by design.

**Delivered — phone utilities:** `core/services/phone.py` normalizes,
validates and formats phone numbers with `phonenumbers`;
Account/Contact/Lead `phone_number` values are normalized to E.164 on save
using the `phone_default_region` constance setting (invalid values are kept
as typed).

**Delivered — stream reactions:** `UserReaction` (note + user + emoji)
with a toggle service, a per-note **React** row action in the admin (dialog
emoji picker) and reaction summaries in the Notes list and Stream tab.

**Delivered — soft-delete restore:** entity changelists have a "Show
deleted records" toggle (`?deleted=1`), a bulk **Restore selected records**
action and a per-row **Restore** action; the API keeps excluding deleted
records.

**Delivered — saved filters:** entity changelists render per-user filter
chips with a "save current filters" box (`SavedFilter` model); applying a chip
redirects with the stored query parameters. Filters are private per user.

**Delivered — update-related workflow action:** an action like
`{"type": "update_related", "relation": "opportunities", "fields": {"stage":
"Closed Lost"}}` updates the related records of the triggering record;
validation checks the relation and field names.

**Delivered — live stream updates:** `StreamEvent` rows are queued when a
stream note is created on a record assigned to someone other than the actor;
the `/admin/notifications/stream/` SSE endpoint emits them and the admin JS
shows a toast. Old events are pruned by `core.cleanup_stream_events`.

**Delivered — inbound email:** `Email` + `EmailAccount` models; IMAP
accounts store passwords encrypted (Fernet key derived from `SECRET_KEY`).
`core/services/inbound_email.py` parses RFC822 messages (plain/HTML bodies,
addresses, date, Message-ID), deduplicates by Message-ID, links senders to
Contact/Lead/Account records and imports them as `Email` records; the
`core.fetch_inbound_email` job polls every active account and every
comma-separated folder in `EmailAccount.folder`. Replies are threaded via
`In-Reply-To`/`References` (`Email.parent_email`, `Email.thread_id`) and
inherit the thread's CRM parent; MIME attachments are imported as
`Attachment` rows (shown in the Email admin inline). Manage accounts under
System → Email Accounts (with a "Fetch now" action) and messages under
Activities → Emails.

**Delivered — address utilities:** `core/services/address.py` formats
`address_*`/`billing_address_*`/`shipping_address_*` blocks into display
strings, skipping empty parts.

**Delivered — workflow webhook action:** an action like
`{"type": "webhook", "webhook_id": 1}` enqueues a `WebhookQueueItem` with the
record payload for a configured (active) webhook; missing/invalid webhooks are
ignored without breaking the save.

**Delivered — layout drag-and-drop:** the Layout Editor renders list
columns as draggable rows and has a visual detail-section editor (palette,
drag between sections, section reordering, remove chips) with a JSON
fallback when JavaScript is off.

**Delivered — command palette entries:** `UNFOLD["COMMAND"]`
`search_callback` (`core/services/command_palette.py`) adds static
commands (calendar, global search, layout editor, custom entities, roles),
entity shortcuts (list/new) filtered by admin permission and the user's
saved filters.

All planned priorities (P1–P10) are delivered. The
[deferred backlog](#deferred-backlog-not-yet-implemented) below is the full,
authoritative list of remaining postponed work with origins and targets.

## Deferred backlog (not yet implemented)

Items intentionally postponed. "Origin" is the phase where they were scoped;
"Target" is when they are expected to land (Phase G above, or later backlog).
Nothing here is required for the current feature set to be usable.

### Platform & API

| Item | Origin | Notes / target |
| --- | --- | --- |
| Stream post attachments (file upload in Post Note) | C | `Note.attachments` M2M exists but the dialog has no upload. Target: backlog. |
| Webhooks signed with an app secret / custom headers | #5 | App secrets are standalone (admin + formulas); `Webhook.secret` is still plaintext and requests carry no custom headers. Target: backlog. |

### CRM / activities

| Item | Origin | Notes / target |
| --- | --- | --- |
| Related-record datasets/panels beyond the Stream tab | B/C | Related lists are changelists/inlines only. Target: backlog. |

### Email & marketing

| Item | Origin | Notes / target |
| --- | --- | --- |
| Web-to-lead hosted form page | E | **✅ delivered 2026-09-15** (public `/lead-capture/<api_key>/form/`, captcha-aware, double opt-in acknowledged, shared helpers with the JSON endpoint) |

### Customization & platform (Phase G)

| Item | Origin | Notes / target |
| --- | --- | --- |

## EspoCRM parity backlog (surveyed 2026-09-12)

Gaps found by reading the upstream EspoCRM source (release 10.0.8, commit
`1effd3d`) and checking every candidate against this codebase by evidence.
False positives were discarded by inspecting context — `sla` was matching
"translate", `position` was the user's job title, `extension` an icon name and
`ImportError` the Python builtin, so all of those are real gaps, not parity.

Two caveats about the source: the EspoCRM repository is the **open-source core
only** (Advanced Pack and Sales Pack are commercial and not covered here), and
several Espo notions — `DataManager`, `Rebuild`, `Upgrades`, its own ORM —
exist to compensate for what Django provides natively, so they are deliberately
not treated as gaps.

### Tier 1 — quick wins (daily use, small)

| # | Item | EspoCRM source | Notes |
| --- | --- | --- | --- |
| 1 | Dynamic logic (show / hide / require fields from other values) | `Tools/DynamicLogic` | **✅ delivered 2026-09-12** (rules + server-side enforcement + JSON for the follow-up client-side show/hide) |
| 2 | Follow records + favourites (stars) | `StreamSubscription`, `StarSubscription`, `Tools/Stars` | **✅ delivered 2026-09-12** (stars, following, auto-follow, Starred/Following filters, follower notifications) |
| 3 | Persisted kanban order | `KanbanOrder` | **✅ delivered 2026-09-12** (per-user card order within a column, batched id-list endpoint) |
| 4 | Captcha on public forms | `Tools/Captcha` | **✅ delivered 2026-09-15** (per-capture `form_captcha`, switchable reCAPTCHA v3 / Turnstile, fail closed) |
| 5 | App secrets | `Tools/AppSecret` | **✅ delivered 2026-09-15** (encrypted `AppSecret` rows, admin under System, `secret("name")` in formulas) |
| 6 | OpenAPI specification | `Tools/OpenApi` | **✅ delivered 2026-09-15** (metadata-generated OpenAPI 3.1 at `/api/v1/openapi.json`, ACL-filtered, includes custom entities/fields and lead capture; staff-only Swagger UI at `/swagger/`) |
| 7 | Popup notifications | `Tools/PopupNotification` | Browser-level notice on top of badge/toasts |
| 8 | Rename labels from the UI | `Tools/LabelManager` | Rename entities/fields without code |

### Tier 2 — medium investments (high product value)

| # | Item | EspoCRM source |
| --- | --- | --- |
| 9 | PDF templates | `Tools/Pdf` |
| 10 | Multiple phones/emails per record, with per-address opt-out | `PhoneNumber`, `EmailAddress` |
| 11 | Configurable pipelines | `Pipeline`, `PipelineStage` |
| 12 | Email filters + group folders | `EmailFilter`, `GroupEmailFolder` |
| 13 | Data privacy (export / anonymise a data subject) | `Tools/DataPrivacy` |
| 14 | Working-time calendars / SLA | `WorkingTimeCalendar`, `WorkingTimeRange` |
| 15 | Generic category trees | `Tools/CategoryTree` |
| 16 | Dashboard templates | `DashboardTemplate` |
| 17 | Import history and errors | `ImportEntity`, `ImportError` |
| 18 | Action history (user activity audit) | `Tools/ActionHistory` |
| 19 | Two-factor authentication | `TwoFactorCode`, `Tools/UserSecurity` |
| 20 | Locale-aware name formatting | `Tools/Name` |

### Tier 3 — structural (large, or a product decision)

| # | Item | EspoCRM source |
| --- | --- | --- |
| 21 | OAuth/OIDC and LDAP sign-in | `Tools/OAuth`, `Tools/Oidc`, `Core/Authentication` |
| 22 | SMS channel | `Sms`, `Core/Sms` |
| 23 | Extension manager | `Tools/Extension` |
| 24 | Assisted upgrades | `Core/Upgrades` |
| 25 | External accounts hub | `Tools/ExternalAccount` |
| 26 | Pluggable file storage (S3) | `Core/FileStorage` |

Execution order agreed on 2026-09-12: work **Tier 1 top-down**. Dynamic logic
(#1), **follow/favourites** (#2), **persisted kanban order** (#3), **captcha on
public forms** (#4), **app secrets** (#5) and the **OpenAPI specification**
(#6) are delivered; the next item is **popup notifications** (#7). Tiers 2 and
3 are recorded here but not scheduled.

### Workflow engine — improvement to the existing `Workflow`

Not from the EspoCRM survey (its open-source core has **no** workflow at all; that
lives in the paid Advanced Pack). Motivated instead by Kestra/N8N/Mautic-style
automation.

**Scope decision (2026-09-12, revised):** the test is not "does Mautic do this
too?" but "does this CRM need it to work on its own?". The CRM already owns email
templates (with its own code editor), mass sending with scheduling and a queue,
per-recipient open/click/bounce tracking, campaigns, target lists, lead capture
and opt-out — so it must be able to *act* on that data without a second system.
Integration with Mautic stays available for installs that already run it, but it
is not a dependency: two-way contact sync has no clean owner for email, opt-out
or "do not contact", and getting that wrong means mailing someone who opted out.

The reason to build it here is not symmetry with Mautic. It is that this side also
holds what Mautic cannot see — the deal stage, the open case, the history — so a
rule like "opened the proposal twice *and* the deal has been idle for ten days" is
something only the CRM can run at all.

Today `Workflow` is trigger (`create`/`update`/`delete`) → condition → a list of
steps. The first two engine increments are delivered (see below); the trigger is
still always a record write — never an engagement event — and runs have no
step-level log yet.

**In scope — the engine, plus the automation this data enables**

| # | Item | Notes |
| --- | --- | --- |
| W1 | Steps with waits | **✅ delivered 2026-09-15** (duration / date-field / condition waits persisted as `WorkflowRun`, resumed by the `core.resume_workflow_runs` job; condition waits poll until true and fail after their timeout) |
| W2 | Branching / decision steps | **✅ delivered 2026-09-15** (`{"type": "branch", "condition", "then", "else"}`, nested; compiled to a jump-based program together with W1) |
| W3 | Engagement triggers | email opened / clicked / bounced, per recipient, on our own campaigns — the data already exists (`Campaign` counters and per-recipient tracking); only the trigger is missing |
| W4 | Execution history | per-run state, logs and retry; today a failed action is simply lost |
| W5 | Target lists that recompute | `TargetList` holds a static member list today; derive its members from a saved filter, reusing the existing filter infrastructure |
| W6 | Scoring | explainable and rule-based (field values plus engagement) so segments and routing can use it — not a black box |
| W7 | Email A/B tests | the send is ours (target list plus counters), so splitting and comparing is cheap |
| W8 | Page tracking | a tracked endpoint plus a small JS snippet, so "came back to the site" becomes an event. Needs a privacy decision on cookies and consent |
| W9 | SMS | already Tier 3 of the parity backlog; a notification channel for the CRM as much as for marketing |

**Deliberately left open — a different product, with a standing maintenance
commitment, to be decided on its own merits:** a landing-page builder and social
publishing. Hosted form pages (capture) stay in the deferred backlog.

Cost note: the expensive part of these is not the first version but keeping them
alive afterwards. Every external channel — SMS providers, social APIs that change
policy, tracking rules under cookie and consent law — is a permanent obligation.
That argues for ordering by maintenance cost, not for avoiding the work.

Suggested order: **W1 + W2** are delivered; next is **W3 + W4** — the engagement
triggers are what actually removes the dependency — then **W5 + W6**, then
**W7 + W8**.

### Integrations (desired, not scheduled)

The project should talk to the platforms that own the neighbouring concerns
instead of absorbing them. Both over the existing REST API and webhooks, with no
new front-end dependency.

| Platform | Owns | Notes |
| --- | --- | --- |
| **Mautic** | marketing automation, for installs that already run it | keep contacts and segments in step and hand campaigns over. Optional by design — the CRM must not need it to send, track or automate (see the scope decision above), because two-way contact sync has no clean owner for email, opt-out or "do not contact" |
| **Chatwoot** | conversations / support inbox | sync contacts and conversations so a case carries its conversation history. A WhatsApp campaign script already drives Chatwoot for the Artmed Experience event, so there is practical ground here |

## Authoring UX — JSON and visual editors (planned 2026-09-15)

The automation and metadata declarations are JSON in the database (workflow
steps, dynamic-logic conditions, custom-field params, lead-capture field
lists) and are edited today through raw textareas. EspoCRM never exposes JSON:
its Workflows tool is a typed form builder, its BPM tool a BPMN 2.0 flowchart
canvas, Formula is an in-app code editor with autocomplete, and Dynamic Logic
uses a row-based condition builder. The agreed approach is tiered: a visual
builder as the primary surface plus a CodeMirror JSON/script editor as the
always-available advanced tier, built into the existing admin change forms
(one save path; `full_clean()` stays the gate).

| # | Item | Notes |
| --- | --- | --- |
| AU1 | Editor foundation + JSON tier | **✅ delivered 2026-09-15** — staff-only `/admin/editor/metadata/<Entity>/` and `/admin/editor/validate/` endpoints reusing the existing validators (`workflows.validate_actions`, `dynamic_logic.condition_errors`, `formula`, `CustomField.clean`); the vendored CodeMirror bundle gains JSON + formula highlighting; completion and live lint (with a JSON fallback) on Workflow actions/condition, DynamicLogic condition, Formula script, CustomField params and LeadCapture field_list |
| AU2 | Visual builders | **✅ delivered 2026-09-15** — inline widgets with a Visual/JSON toggle: condition builder (field / operator / type-aware value, and-or-not groups) for DynamicLogic, typed step builder for Workflow actions (nested `then`/`else`, wait modes), per-`field_type` params form, LeadCapture field checklist; unknown keys/nodes are preserved |
| AU3 | Read-only flow & run visualization | **✅ delivered 2026-09-15** — `WorkflowRun.trace` (executed step indices, migration) and a diagram on Workflow and WorkflowRun detail pages: processed / waiting / pending / failed / timed-out, wait due dates |

Locked decisions: inline form widgets, no standalone pages; JSON stays the
storage format and escape hatch; workflow trigger/branch/`until` conditions
remain formula expressions handled by the code editor (the row builder serves
`DynamicLogic.condition`); the bundle is rebuilt with the existing
`tools/build-codemirror.sh` and committed, following the CodeMirror/Swagger
vendoring pattern. AU1, AU2 and AU3 are delivered (2026-09-15).

## Resume checklist

```bash
uv sync
uv run python src/omacrm/manage.py check            # must be clean
uv run python src/omacrm/manage.py test --parallel  # gate: full suite, ~1 min on 2 cores (was ~2 min serial)
uv run python src/omacrm/manage.py seed_demo        # rich demo dataset; --reset rebuilds it
uv run python src/omacrm/manage.py runserver
```

While working, a narrow target with `--keepdb` is enough to get feedback — the
~9s database setup dominates anything below the full suite, so without it even a
single module costs 20s:

```bash
uv run python src/omacrm/manage.py test --keepdb omacrm.core.tests.test_subscriptions
```

That is a loop, not a verdict: run the full suite before anything goes to `main`.
Regressions here have come from interactions rather than from single modules —
the MJML tag whitelist broke because of `base.mjml`, the shared admin form's
`full_clean` affects every metadata admin, and the merge now touches four
tables — so "the tests of the file I changed" would not have caught them.

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

- **2026-09-15** — Authoring UX AU3: workflow flows are now visual and
  read-only on the detail pages. `WorkflowRun.trace` (migration
  `core.0025`) records the compiled step indices each run executes, and
  `core/services/workflow_diagram.py` turns a compiled program into a nested
  display tree annotated with the run's state — processed, active, waiting
  (with the resume time), failed, cancelled or pending — resolving the paused
  wait from the trace (a duration wait advances the cursor past itself, a
  condition wait does not). The Workflow change page renders the declared
  flow (rule preview) and the Workflow Run change page the executed run,
  through `templates/admin/workflow_flow*.html` (branch rails, wait details
  and due dates) (674 tests).

- **2026-09-15** — Authoring UX AU2: the JSON editors gained a **Visual |
  JSON** toggle. `core/static/core/js/builders.js` renders type-aware
  builders that mutate the same parsed JSON and call back into the editor
  (which rewrites the document, keeping the textarea and CodeMirror in sync):
  a condition builder for `DynamicLogic.condition` (and/or/not groups,
  field/operator rows with type-aware value widgets, `in`/`notIn` lists),
  a step builder for `Workflow.actions` (typed action cards, move/remove,
  nested `then`/`else` branches, wait-mode switching, entity-type pickers)
  plus per-`field_type` param forms for `CustomField.params` (choices editor,
  number prefix/padding, foreign link/field) and an ordered checklist for
  `LeadCapture.field_list`. Unknown keys, action types and condition nodes
  are preserved as raw JSON cards; invalid JSON falls back to the JSON tab.
  The builders render with Unfold's own widget classes (fed to the editor
  config from `unfold.widgets`), and the now-redundant JSON declaration help
  texts on the Workflow, DynamicLogic, Formula, CustomField and LeadCapture
  forms were trimmed so the editors are the documentation. The editor
  metadata endpoint now also lists entity types for the create-record picker
  (663 tests).

- **2026-09-15** — Authoring UX AU1: the JSON/script declarations get a
  CodeMirror tier. Staff-only `GET /admin/editor/metadata/<Entity>/` serves
  fields (type, choices, links), action types, dynamic-logic operators and
  formula helpers for completion, and `POST /admin/editor/validate/` runs the
  declarations through the same validators save-time `full_clean()` uses:
  `workflow_actions` (now collecting every error with its action path),
  `dynamic_logic`, `formula` (new `formula.validate_script`), `custom_field`
  and `lead_capture`. The Textarea widgets for Workflow actions and
  condition, DynamicLogic condition, Formula script, CustomField params and
  LeadCapture field_list are enhanced by `core/static/core/js/editors.js`
  (completion, format button for JSON, debounced lint diagnostics, dark-mode
  aware) while the textarea remains the submitted value, so saving without
  JavaScript is unchanged. The vendored CodeMirror bundle gained
  `@codemirror/lang-json` and a formula `StreamLanguage` (rebuilt through
  `tools/build-codemirror.sh`, gzip 145 KB) (663 tests).

- **2026-09-15** — Workflow engine W1 + W2: workflow rules are now step lists
  that can pause and branch. A `{"type": "wait", "duration": "3d"}` step, a
  wait on a record date field (`until_date_field`, custom fields included) or
  a condition wait (`until_condition` with `poll_interval`/`timeout`, 30 days
  by default) stop the rule; a `{"type": "branch", "condition", "then",
  "else"}` step routes nested steps. `core/services/workflows.py` compiles the
  nested steps into a jump-based program and executes it with a cursor; when
  the executed path reaches a wait, a new `WorkflowRun` (migration
  `core.0023_workflowrun`) stores the compiled program, cursor and resume
  time. The `core.resume_workflow_runs` job advances due runs (seeded every
  minute), condition waits re-poll and fail on timeout, a vanished record
  cancels the run, and rules/paths without waits still run inline and create
  no rows. `Workflow.clean()` delegates to a recursive
  `core/services/workflows.py::validate_actions` that checks waits (exact
  mode, duration format, known date field, condition syntax) and branch
  bodies, the read-only Workflow Runs admin offers resume/retry/cancel, and
  the demo gains a wait+branch rule (640 tests).

- **2026-09-15** — Record API fixes + metadata management API. Custom entities
  are now served **only** by the capitalized `/api/v1/<Entity>/` catch-all:
  `build_api_router` skips runtime entities, so the accidental lowercase
  aliases (`/api/v1/project/`) are gone, the 500 that deactivating a
  startup-persisted entity produced on them is gone with them, and
  `RecordViewSet.initial` still 404s any unknown entity as defense in depth.
  `?search=` is now wired to the entity's metadata `search_fields` on every
  endpoint (it was a no-op on the catch-all despite being documented), and
  custom-entity lists default to the entity's `sort_field`/`sort_direction`
  instead of the proxy model's `-created_at`. `CustomEntity.name` is locked
  after creation (`clean()`), matching the template lock, because renaming
  would orphan the entity's records. New staff-only
  `/api/v1/metadata/{entities,fields,layouts,links}/` (`core/api/metadata.py`,
  `IsAdminUser`) CRUDs the definitions themselves; serializers run the model's
  `full_clean()` and writes reuse the admin signals (registry invalidation,
  materialize/unregister, URLconf refresh), so a new entity's record endpoint
  is live immediately. The OpenAPI document gains the Metadata section for
  staff users (618 tests).

- **2026-09-15** — Swagger UI at `/swagger/`: a staff-only standalone page
  (`SwaggerView`, deliberately without the admin chrome) renders the generated
  OpenAPI document using the vendored Swagger UI 5.32 dist — bundle, CSS and
  Apache-2.0 license under `core/static/vendor/swagger-ui/`, same pattern as
  the CodeMirror bundle, so there is no runtime CDN dependency and no new
  Python package. The page also hides the duplicate inline copy icon on the
  "Copy path to clipboard" button (5.32 draws a CSS background icon *and*
  renders an inline SVG on the same button), keeping the
  high-contrast-friendly background one. "Try it out" uses the admin session
  cookie automatically, or an `X-Api-Key`/token set through the Authorize
  dialog, and the command palette gains an "API docs" entry. The document
  served to the page is still the per-user ACL-filtered one (603 tests).

- **2026-09-15** — OpenAPI specification (Tier 1 #6): `GET /api/v1/openapi.json`
  (`core/api/openapi.py`) serves an OpenAPI 3.1 document generated from the
  metadata registry (`core/services/openapi.py`), always in step with built-in
  and runtime custom entities because it reads the same definitions the API
  uses. Per entity it documents the canonical paths (lowercase router paths
  for built-ins, the capitalized runtime catch-all for custom entities), the
  five CRUD operations with `limit`/`offset`/`search`/`ordering`/`where`
  parameters and the paginated response, field schemas from the `FieldDef`
  types (enums, formats, `required`, `readOnly`), audit fields, custom fields
  as properties of `custom_data`, custom relationship links as target ids and
  the `where` operator vocabulary. The document is filtered by the requesting
  user's ACL — whole entities without read access are omitted and so are
  fields they cannot read — and covers the public
  `POST /api/v1/lead-capture/{api_key}/` endpoint with its captcha responses.
  It is hand-built rather than generated by DRF's introspector or
  drf-spectacular because the serializer/viewset classes are dynamic and
  custom fields live in `custom_data`, which a generic introspector cannot
  describe (598 tests).

- **2026-09-15** — App secrets (Tier 1 #5): `AppSecret`
  (`core/models/secrets.py`) stores named credentials (API keys, passwords)
  Fernet-encrypted with a key derived from `SECRET_KEY`, like the IMAP
  passwords, so a database dump does not expose them;
  `core/services/secrets.py` provides `get`/`set`/`names` and returns `""` for
  a missing or undecryptable value. The admin (System → App Secrets) enters
  the value through a password widget, keeps the current value when left
  blank and never renders it back — the list shows only
  name/description/timestamps. Formulas gain a `secret("name")` helper, so
  scripts can use credentials without hardcoding them. Wiring webhooks to app
  secrets (and custom headers) is recorded as a follow-up (589 tests).

- **2026-09-15** — Hosted web-to-lead form (deferred backlog item pulled
  forward): each `LeadCapture` now gets a server-rendered public form at
  `/lead-capture/<api_key>/form/` with the fields its `field_list` allows
  (labels, choices and validation come from a dynamic Lead `ModelForm`), the
  reCAPTCHA v3 or Turnstile widget when `form_captcha` is on, CSRF protection,
  inline double opt-in acknowledgement ("check your inbox") and a 404 for an
  unknown or inactive key. `crm/services/lead_capture.py` now owns the shared
  helpers — allowed web fields, form building, captcha gating, lead storage
  (source, assignment, campaign log, opt-in email, target list) — and the JSON
  endpoint was refactored onto them with its responses unchanged. The admin's
  **Public form** field links to the page for copying/preview (578 tests).

- **2026-09-15** — Captcha on public forms (Tier 1 #4): `LeadCapture.form_captcha`
  makes the public lead-capture endpoint verify a token before creating the
  lead, so web-to-lead can be protected without API keys or IP rules.
  `core/services/captcha.py` is one switchable implementation for Google
  reCAPTCHA v3 and Cloudflare Turnstile — both post `secret`/`response` (+
  `remoteip`) to their siteverify endpoint, so the provider, keys, score
  threshold and verify URL (override for tests/self-hosted) are constance
  settings under "Captcha". reCAPTCHA requires a score at or above the
  threshold; Turnstile answers without one; a returned `action` must match
  `lead_capture` when present, and network/parse failures count as a failed
  verification, never a 500. Submissions may send the token as `captcha_token`
  or the provider's browser field (`g-recaptcha-response`,
  `cf-turnstile-response`); captcha required without a configured provider
  fails closed with a 503, and captures with the flag off are unchanged
  (562 tests).

- **2026-09-15** — Test flake fix: the mass-email unsubscribe test compared two
  independently timestamp-signed tokens, so it failed whenever a second
  boundary fell between the send and the assertion (always under parallel
  load). It now decodes the token from the sent body and checks that it points
  at the queue item.

- **2026-09-12** — Entity display names come from the metadata: on registration
  the registry mirrors `EntityDef.display_label`/`display_label_plural` onto the
  model's `_meta.verbose_name`/`verbose_name_plural`, bypassing
  `_meta.original_attrs` so the lazy labels survive and no phantom migration
  appears. The admin read Django's class-name-derived names instead, showing
  "Opportunitys" while the sidebar showed "Opportunities"; 13 of the 20 entities
  differed, twelve of them only in case (`accounts` vs `Accounts`). Labels belong
  in `metadata.py`, never in a model `Meta` (535 tests).

- **2026-09-12** — Sortable changelist columns: `get_list_display` is now
  memoised per request, so the columns it builds dynamically (custom fields, the
  compact currency displays, the star column) are clickable in the header again.
  Django calls `get_list_display` twice — once for the columns, once as the
  `get_sortable_by` fallback — and decides clickability with
  `field_name in cl.sortable_by`, which is identity for callables, so displays
  created fresh on every call were silently unsortable. The custom-field columns
  had never been sortable (532 tests).

- **2026-09-12** — Changelist currency columns: `format_compact` moved to
  `core/services/formatting.py` (still re-exported by
  `crm/services/analytics.py` for the dashboard) and
  `MetadataModelAdmin.get_list_display` now resolves metadata `currency`
  columns — built-in fields like Opportunity `amount`, custom currency fields
  and admin displays ordered by them — to a compact
  `<span title="€45,000.00">€ 45K</span>` cell, with empty values left to
  Django's default empty display and the column still sortable via
  `admin_order_field` (524 tests).

- **2026-09-12** — Persisted kanban order (Tier 1 #3): `KanbanOrder`
  (`core/models/collab.py`, one row per user, entity type and record, indexed
  by user/entity/type/column/order) stores where each user put a card inside a
  column. `core/services/kanban.py` gains `reorder()` (validates the ids
  against the column and the user's read ACL, then writes one batched
  `bulk_create` upsert) and `board()` now returns arranged cards first in the
  stored order with unarranged ones after them in metadata order, so a user
  with no saved rows sees the historical board unchanged; `move_record()`
  clears a record's saved order when its status changes so it lands at the end
  of its new column. Drops post the column's ids in DOM order to the new
  `/admin/kanban/<Entity>/order/` endpoint (`kanban_order`), and the Alpine
  board keeps the card in place only when both the status change and the order
  were accepted (514 tests).

- **2026-09-12** — Stars & following fixes: `merge_records` now moves
  `StarSubscription`/`StreamSubscription` rows from the duplicate to the master
  using the master's metadata entity type, dropping a duplicate's row when the
  user already subscribed to the master (so the star unique constraint holds)
  and reporting both under `moved["stars"]`/`moved["follows"]`; removing a
  custom entity purges the subscriptions keyed by its entity type next to the
  existing `CustomLink` cleanup; and `post_note()` makes the mention win over
  the follower notification, so a mentioned follower gets one `Mention`
  notification instead of a `Mention` plus a `Stream` (502 tests).

- **2026-09-12** — Stars & following (Tier 1 #2): `StarSubscription`/
  `StreamSubscription` (`core/models/collab.py`, unique star per user and
  record) and `core/services/subscriptions.py` (star/follow toggles, batch
  `Exists` annotations, active-only `followers_of`). Every metadata-driven
  admin gets a star column and **Starred**/**Following** list filters, the
  change form a star plus **Follow/Unfollow** control posting in place to
  `/admin/<app>/<model>/subscriptions/<kind>/<id>/`
  (`core/static/core/js/subscriptions.js`), and the per-user
  `Preferences.auto_follow_entity_types` preference follows new records of the
  selected types for every user who enabled them and auto-follows the author
  after a stream post.
  `post_note()` now sends a `Stream` notification to the record's active
  followers (author skipped, mentions unchanged). Runtime custom entities work
  through the metadata entity type + pk convention (493 tests).

- **2026-09-12** — Dynamic logic (Tier 1 #1): `DynamicLogic` rules
  (`core/services/dynamic_logic.py`, managed under Customization → Dynamic
  Logic) make a field visible/required/read-only while a JSON condition over
  other field values holds. The pure evaluator mirrors EspoCRM's vocabulary
  (nested `and`/`or`/`not`, equality, string, collection, number and date
  operators) with type-aware comparison and never raises on a malformed
  condition. `MetadataModelAdmin` applies the states against the submitted
  values — hidden/read-only values are ignored, a conditionally required
  field only blocks while its condition holds — and exposes the active rules
  plus metadata defaults to the change form as `json_script`
  `dynamic-logic-config` for the follow-up client-side show/hide (449 tests).

- **2026-09-12** — Email template code editor: the GrapesJS visual designer
  and its assets/endpoints were removed; `EmailTemplate.source` is now the
  source of truth (starter MJML default), `source_format` defaults to `mjml`,
  `body` is kept purely as the compiled cache and `clean()` rejects an empty
  source. Templates are edited only through the **Edit code** action at
  `/admin/email-template/<pk>/source/` — a vendored CodeMirror 6 page with
  live preview, MJML tag highlighting and test send (`crm/admin_views.py`)
  (404 tests).

- **2026-09-11** — Dashboard sales chart: KPI cards for Account/Contact/
  Lead/Opportunity now follow `AclService.scope_queryset` and a **Sales by
  month** card (last 12 months, zero-filled) plots Closed Won revenue as bars
  and weighted open pipeline as a line using Unfold's bundled Chart.js
  (`crm/services/analytics.py`); the demo seed gained six historical Closed
  Won deals and three future pipeline deals (364 tests).

- **2026-09-11** — GrapesJS visual email designer: vendored GrapesJS 0.23.6 +
  newsletter preset (BSD-3) under `core/static/vendor/grapesjs/`;
  `EmailTemplate.design` stores the project data and the **Design** detail
  action opens a standalone editor at `/admin/email-template/<pk>/design/`
  with merge-tag blocks, preview, test send and image uploads to
  `media/email-assets/`. Outgoing HTML is CSS-inlined with `premailer` and
  relative URLs are absolutized via the new `public_base_url` constance
  setting (`prepare_email_html`, shared by send/mass email); demo seeds
  include two table-based templates (354 tests).

- **2026-09-11** — Unfold adoption pass (R1–R9): link/linkMultiple pickers
  now use Unfold select2 autocomplete over a new ACL-scoped
  `/admin/link-autocomplete/` endpoint; enum/bool custom filters use
  `unfold.contrib.filters`; dialog forms and the attachment widget use Unfold
  widgets; custom admin templates use Unfold button components; site views
  use `UnfoldSiteViewMixin`; saved filters moved to `list_before_template`;
  Kanban and Layout Editor drag-and-drop migrated to Alpine `x-sort`;
  `MetadataModelAdmin` now inherits the import/export mixin (the duplicate
  `export_as_csv` action was removed) and the KB body uses the Trix WYSIWYG
  (327 tests).

- **2026-09-11** — E5 (Kanban): generic status-field boards for custom
  entities (`status_field`) and built-ins (Opportunity stage, Task status)
  at `/admin/kanban/<Entity>/` with ACL, drag-and-drop moves and a
  changelist link; `seed_demo` without `--reset` now refreshes platform
  access (roles/users) so stale role scopes pick up new entities (320
  tests).

- **2026-09-11** — Fix: custom entities are visible to users with roles
  again; when no role mentions a runtime entity, ACL falls back to its
  `acl_default` (an explicit `no` still hides it) (308 tests).

- **2026-09-11** — E4 (entity templates): `CustomEntity.template`
  (Base/Person/Company/Event, locked after creation) seeds initial custom
  fields and layouts; Person builds `name` from first/last; Event enables
  `show_in_calendar` and the calendar renders custom event records. The
  demo adds a Person-template `Candidate` entity (307 tests).

- **2026-09-11** — E2 (advanced field types): custom fields gained phone
  (E.164), decimal (JSON-safe; also fixes float/currency Decimal crashes),
  number/autoincrement (`NextNumber` sequences with prefix/padding),
  composite address, file/image/attachmentMultiple (stored as
  `Attachment` ids with upload/clear) and read-only foreign values through
  custom links; the demo Project showcases them (302 tests).

- **2026-09-11** — E3 (relationships): `CustomLink` now describes
  belongsTo/hasMany/manyToMany links with an automatic reverse side, stored
  as mirrored `RecordLink` rows; admin link/linkMultiple pickers, layout
  columns, cleanup on entity removal and API read/write by target ids
  (294 tests).

- **2026-09-11** — E1 (Entity Manager): custom entities gained icon/color,
  menu placement (`show_in_menu`/`menu_order`), stream/sort/search/
  duplicate-check properties, a dynamic sidebar built per request
  (`core/services/navigation.py`), immediate admin URLs (URLconf refresh on
  save) and a catch-all `/api/v1/<Entity>/` route, so custom entities work
  without a server restart (283 tests).

- **2026-09-11** — Rich demo dataset: `seed_demo` now populates every
  feature (sales pipeline, activities/attendees/recurrence, cases/KB/
  documents, email threads, marketing with consistent analytics, stream/
  notifications, webhooks, custom fields/layouts/formulas/workflows and a
  `Project` custom entity) with `--reset`, `--rng-seed` and `--base-url`
  flags (275 tests).

- **2026-09-11** — P10: command palette custom entries (static commands,
  permission-filtered entity shortcuts, saved filters), extra formula
  helpers (string/number/date) and a drag-and-drop detail-section editor
  with JSON fallback (272 tests). All planned priorities P1–P10 delivered.

- **2026-09-11** — P9: `CurrencyRate` history, dated `get_rate`/`convert`
  (Opportunity conversion uses `close_date`), admin inline + rate admin and
  the `core.sync_currency_rates` job driven by constance
  `currency_rates_url` (265 tests).

- **2026-09-11** — P8: inbound email advanced (multiple IMAP folders,
  reply threading with `parent_email`/`thread_id`, MIME attachments as
  `Attachment` records, Email admin attachment inline) (254 tests).

- **2026-09-11** — P7: customer portal profile (edit contact info, change
  password) and documents (active documents linked to the contact or their
  account, ACL-scoped downloads) (246 tests).

- **2026-09-11** — P6: duplicate merge (pick master + per-field values;
  notes/attachments/emails and nullable reverse FKs are re-pointed, the
  duplicate is soft-deleted) (240 tests).

- **2026-09-11** — P5: global search page (`/admin/global-search/`) across
  registered entities, ACL-scoped with per-entity result groups (236 tests).

- **2026-09-11** — P4: campaign advanced features — per-recipient unsubscribe
  links, hard/soft bounce recording (service + queue admin actions),
  automatic campaign revenue from Closed Won opportunities, and web-to-lead
  double opt-in with signed confirmation links (231 tests).

- **2026-09-11** — P3: recurring Call/Meeting rules materialized into
  occurrence records (daily/weekly/monthly, interval, count, until,
  weekly weekdays) with signed-series regeneration (221 tests).

- **2026-09-11** — P2: event attendees (`Attendance` with user/contact/lead,
  acceptance status), admin inline plus a Send invitations action and a
  public signed accept/decline page (210 tests).

- **2026-09-11** — P1: API keys (`X-Api-Key`) and the Espo-style `where`
  filter DSL for the REST API; admin action to generate API keys (202 tests).

- **2026-09-11** — Soft-delete restore UI: deleted-mode changelist toggle
  plus bulk and per-row restore actions (190 tests).

- **2026-09-11** — Saved filters: per-user changelist filter presets with
  save/apply/delete chips (184 tests).

- **2026-09-11** — Workflow `update_related` action (with relation/field
  validation) (179 tests).

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
