"""Activity demo data: tasks, calls, meetings, attendees."""

from omacrm.crm.models import Attendance, Call, Meeting, Task

from .common import date_in, moment_in

POPUP_REMINDER = [
    {"seconds": 900, "type": "Popup"},
    {"seconds": 86400, "type": "Email"},
]

TASKS = (
    ("Call John about ERP rollout", "Started", "High", -3, "Northwind Traders", "john.carter@northwind.example", "ana"),
    ("Send cloud migration proposal", "Not Started", "Urgent", 2, "TechBrasil Sistemas", "mariana.silva@techbrasil.example", "bruno"),
    ("Prepare Rheinland renewal quote", "Not Started", "Normal", 5, "Rheinland Maschinenbau GmbH", "klaus.weber@rheinland.example", "ana"),
    ("Schedule analytics demo", "Completed", "High", -7, "BlueWave Analytics", "emily.zhang@bluewave.example", "bruno"),
    ("Follow up Copacabana feedback", "Completed", "Normal", -10, "Copacabana Turismo", "rafael.costa@copacabana.example", "ana"),
    ("GreenLeaf contract signature", "Started", "Urgent", 1, "GreenLeaf Organic Foods", "michael.green@greenleaf.example", "bruno"),
    ("Summit Legal lost deal review", "Completed", "Low", -15, "Summit Legal Partners", "sarah.bennett@summitlegal.example", "ana"),
    ("Atlas fleet tracking questionnaire", "Not Started", "Normal", 7, "Atlas Logistics", "lars.devries@atlaslog.example", "bruno"),
    ("Pixel & Co. partner onboarding", "Deferred", "Low", 21, "Pixel & Co. Studio", "ines.martins@pixelco.example", "ana"),
    ("Horizonte quarterly review", "Not Started", "High", 10, "Horizonte Energia", "gustavo.pereira@horizonte.example", "bruno"),
    ("Prepare Q4 forecast deck", "Started", "High", 4, None, None, "ana"),
    ("Update lead scoring rules", "Not Started", "Low", 14, None, None, "bruno"),
    ("Review inbound emails", "Completed", "Normal", -2, None, None, "demo"),
    ("Plan customer webinar", "Not Started", "Normal", 12, None, None, "demo"),
    ("Reimbursement approval", "Canceled", "Low", -4, None, None, "demo"),
    ("Renew SSL certificates", "Completed", "Urgent", -5, None, None, "demo"),
)

CALLS = (
    ("Discovery call with Northwind", -12, 10, 1, "Outbound", "Northwind Traders", "john.carter@northwind.example", "Held"),
    ("TechBrasil technical scoping", -5, 14, 1, "Outbound", "TechBrasil Sistemas", "mariana.silva@techbrasil.example", "Held"),
    ("Rheinland renewal check-in", -2, 9, 1, "Inbound", "Rheinland Maschinenbau GmbH", "klaus.weber@rheinland.example", "Held"),
    ("BlueWave security questions", 1, 11, 1, "Outbound", "BlueWave Analytics", "emily.zhang@bluewave.example", "Planned"),
    ("Copacabana support escalation", 2, 16, 1, "Inbound", "Copacabana Turismo", "rafael.costa@copacabana.example", "Planned"),
    ("Atlas logistics integration", 3, 10, 1, "Outbound", "Atlas Logistics", "lars.devries@atlaslog.example", "Planned"),
    ("Summit Legal follow-up", -8, 15, 1, "Outbound", "Summit Legal Partners", "sarah.bennett@summitlegal.example", "Held"),
    ("Quarterly pipeline review call", 6, 9, 1, "Outbound", None, None, "Planned"),
)

MEETINGS = (
    ("Northwind implementation kickoff", -20, 10, 2, "Northwind Traders", "john.carter@northwind.example", "Held"),
    ("TechBrasil cloud workshop", -10, 9, 3, "TechBrasil Sistemas", "mariana.silva@techbrasil.example", "Held"),
    ("BlueWave quarterly business review", 4, 14, 2, "BlueWave Analytics", "emily.zhang@bluewave.example", "Planned"),
    ("GreenLeaf onboarding planning", 8, 10, 2, "GreenLeaf Organic Foods", "michael.green@greenleaf.example", "Planned"),
    ("Horizonte investor briefing", 12, 11, 2, "Horizonte Energia", "gustavo.pereira@horizonte.example", "Planned"),
    ("Sales weekly sync", 1, 8, 1, None, None, "Planned"),
    ("Customer success roundtable", 15, 16, 2, None, None, "Planned"),
)


def _add_attendance(event, *, user=None, contact=None, lead=None, status="None", invited=False):
    from django.contrib.contenttypes.models import ContentType

    event_type = ContentType.objects.get_for_model(
        type(event), for_concrete_model=False
    )
    Attendance.objects.get_or_create(
        event_type=event_type,
        event_id=event.pk,
        user=user,
        contact=contact,
        lead=lead,
        defaults={
            "status": status,
            "invitation_sent_at": moment_in(-1, 9) if invited else None,
        },
    )


def seed_activities(context):
    accounts = context["accounts"]
    contacts = context["contacts"]
    demo, ana, bruno, carla = context["demo"], context["ana"], context["bruno"], context["carla"]

    tasks = []
    for name, status, priority, due, account_name, contact_email, owner in TASKS:
        task, _ = Task.objects.get_or_create(
            name=name,
            defaults={
                "status": status,
                "priority": priority,
                "date_start": moment_in(due - 1, 9),
                "date_end": moment_in(due, 17),
                "assigned_user": context[owner],
                "account": accounts.get(account_name),
                "contact": contacts.get(contact_email),
                "description": f"Demo task for {account_name or 'internal use'}.",
                "reminders": POPUP_REMINDER if priority in {"High", "Urgent"} else [],
            },
        )
        tasks.append(task)

    calls = []
    for name, day, hour, hours, direction, account_name, contact_email, status in CALLS:
        call, _ = Call.objects.get_or_create(
            name=name,
            defaults={
                "status": status,
                "direction": direction,
                "date_start": moment_in(day, hour),
                "date_end": moment_in(day, hour + hours),
                "assigned_user": ana if day % 2 else bruno,
                "account": accounts.get(account_name),
                "parent": contacts.get(contact_email),
                "description": "Demo call.",
                "reminders": POPUP_REMINDER,
            },
        )
        calls.append(call)

    meetings = []
    for name, day, hour, hours, account_name, contact_email, status in MEETINGS:
        meeting, _ = Meeting.objects.get_or_create(
            name=name,
            defaults={
                "status": status,
                "date_start": moment_in(day, hour),
                "date_end": moment_in(day, hour + hours),
                "assigned_user": demo if day % 2 else ana,
                "account": accounts.get(account_name),
                "parent": contacts.get(contact_email),
                "description": "Demo meeting.",
                "join_url": "https://meet.example.com/omacrm-demo",
                "reminders": POPUP_REMINDER,
            },
        )
        meetings.append(meeting)

    _add_attendance(calls[0], user=demo, status="Accepted", invited=True)
    _add_attendance(calls[0], contact=contacts["john.carter@northwind.example"], status="Tentative", invited=True)
    _add_attendance(calls[1], user=ana, status="Accepted", invited=True)
    _add_attendance(calls[1], contact=contacts["mariana.silva@techbrasil.example"], status="Declined")
    _add_attendance(calls[3], user=bruno, status="Accepted", invited=True)
    _add_attendance(calls[3], contact=contacts["emily.zhang@bluewave.example"], status="None")
    _add_attendance(calls[5], user=ana, status="Tentative")
    _add_attendance(calls[6], user=demo, status="Declined")

    _add_attendance(meetings[0], user=demo, status="Accepted", invited=True)
    _add_attendance(meetings[0], user=ana, status="Accepted", invited=True)
    _add_attendance(meetings[0], contact=contacts["john.carter@northwind.example"], status="Accepted", invited=True)
    _add_attendance(meetings[1], user=ana, status="Accepted", invited=True)
    _add_attendance(meetings[1], contact=contacts["mariana.silva@techbrasil.example"], status="Tentative")
    _add_attendance(meetings[2], user=demo, status="None", invited=True)
    _add_attendance(meetings[2], user=carla, status="Declined")
    _add_attendance(meetings[3], user=bruno, status="Accepted", invited=True)
    _add_attendance(meetings[5], user=demo, status="Accepted")
    _add_attendance(meetings[5], user=ana, status="Accepted")
    _add_attendance(meetings[5], user=bruno, status="Tentative")
    _add_attendance(meetings[5], user=carla, status="Accepted")

    recurring_meeting, _ = Meeting.objects.get_or_create(
        name="Weekly customer success sync",
        defaults={
            "status": "Planned",
            "date_start": moment_in(2, 9),
            "date_end": moment_in(2, 10),
            "assigned_user": demo,
            "description": "Recurring team sync (weekly).",
            "recurrence_rule": {
                "frequency": "weekly",
                "interval": 1,
                "weekdays": [moment_in(2).weekday()],
                "count": 4,
            },
        },
    )
    _add_attendance(recurring_meeting, user=demo, status="Accepted")
    _add_attendance(recurring_meeting, user=ana, status="Accepted")

    recurring_call, _ = Call.objects.get_or_create(
        name="Monthly partner call",
        defaults={
            "status": "Planned",
            "direction": "Outbound",
            "date_start": moment_in(5, 15),
            "date_end": moment_in(5, 16),
            "assigned_user": ana,
            "description": "Recurring partner call (monthly).",
            "recurrence_rule": {
                "frequency": "monthly",
                "interval": 1,
                "count": 3,
            },
        },
    )
    _add_attendance(recurring_call, user=bruno, status="Tentative")

    overdue = [task for task in tasks if task.date_end and task.date_end.date() < date_in(0) and task.status == "Started"]
    context.update(
        {
            "tasks": tasks,
            "calls": calls,
            "meetings": meetings,
            "recurring_meeting": recurring_meeting,
            "recurring_call": recurring_call,
            "overdue_tasks": overdue,
        }
    )
