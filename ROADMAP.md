# OmaCRM — Roadmap & Development Log

> **Purpose:** record the agreed plan, current status and next steps so work can
> be resumed at any time by any developer/agent. Architecture conventions live
> in [AGENTS.md](AGENTS.md); run instructions live in [README.md](README.md).

_Last updated: 2026-09-12 — Phases A–G implemented (runtime, sales CRM,
collaboration, productivity, marketing, customization, entity manager, portal,
notifications, utilities, inbound email, saved filters, soft-delete restore,
email template code editor with MJML source, dynamic logic server side,
stars/favourites and record following). 493 tests passing; see the
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

### CRM / activities

| Item | Origin | Notes / target |
| --- | --- | --- |
| Related-record datasets/panels beyond the Stream tab | B/C | Related lists are changelists/inlines only. Target: backlog. |

### Email & marketing

| Item | Origin | Notes / target |
| --- | --- | --- |
| Web-to-lead hosted form page | E | JSON endpoint + double opt-in exist; no hosted HTML form page. Target: backlog; can reuse the email template code editor. |

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
| 3 | Persisted kanban order | `KanbanOrder` | The board exists; only the ordering is not stored |
| 4 | Captcha on public forms | `Tools/Captcha` | Lead capture is public and currently unprotected |
| 5 | App secrets | `Tools/AppSecret` | Named credentials for webhooks/integrations |
| 6 | OpenAPI specification | `Tools/OpenApi` | Contract for integrators |
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
(#1) and **follow/favourites** (#2) are delivered; the next item is
**persisted kanban order** (#3). Tiers 2 and 3 are recorded here but not
scheduled.

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

Today `Workflow` is trigger (`create`/`update`/`delete`) → condition → a
**linear** list of actions. There are no steps, waits, branching or execution
history, and the trigger is always a record write — never an engagement event.

**In scope — the engine, plus the automation this data enables**

| # | Item | Notes |
| --- | --- | --- |
| W1 | Steps with waits | "wait 3 days", "wait until a date", "wait until a condition" — needs a scheduler |
| W2 | Branching / decision steps | route by condition instead of running one linear list |
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

Suggested order: **W1 + W2 + W3 + W4** first — the engine together with the
engagement triggers is what actually removes the dependency — then **W5 + W6**,
then **W7 + W8**.

### Integrations (desired, not scheduled)

The project should talk to the platforms that own the neighbouring concerns
instead of absorbing them. Both over the existing REST API and webhooks, with no
new front-end dependency.

| Platform | Owns | Notes |
| --- | --- | --- |
| **Mautic** | marketing automation, for installs that already run it | keep contacts and segments in step and hand campaigns over. Optional by design — the CRM must not need it to send, track or automate (see the scope decision above), because two-way contact sync has no clean owner for email, opt-out or "do not contact" |
| **Chatwoot** | conversations / support inbox | sync contacts and conversations so a case carries its conversation history. A WhatsApp campaign script already drives Chatwoot for the Artmed Experience event, so there is practical ground here |

## Resume checklist

```bash
uv sync
uv run python src/omacrm/manage.py check     # must be clean
uv run python src/omacrm/manage.py test      # must be green (493 tests)
uv run python src/omacrm/manage.py seed_demo # rich demo dataset; --reset rebuilds it
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
