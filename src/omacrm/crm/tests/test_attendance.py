from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from omacrm.core.models import User
from omacrm.crm.models import AcceptanceStatus, Attendance, Call, Contact, Lead
from omacrm.crm.services.event_invitations import (
    confirm_attendance,
    make_token,
    send_invitations,
)


class AttendanceModelTests(TestCase):
    def setUp(self):
        self.call = Call.objects.create(name="Kickoff")
        self.contact = Contact.objects.create(
            first_name="Ana", last_name="Silva", email_address="ana@example.com"
        )

    def test_requires_exactly_one_target(self):
        with self.assertRaises(ValidationError):
            Attendance(event=self.call).full_clean()

        lead = Lead.objects.create(first_name="Two", last_name="Targets")
        with self.assertRaises(ValidationError):
            Attendance(event=self.call, contact=self.contact, lead=lead).full_clean()

    def test_email_and_display_name(self):
        attendance = Attendance(event=self.call, contact=self.contact)
        self.assertEqual(attendance.email, "ana@example.com")
        self.assertEqual(attendance.display_name, "Ana Silva")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InvitationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("invitee", "invitee@example.com", "pw")
        self.contact = Contact.objects.create(
            first_name="Con", last_name="Tact", email_address="contact@example.com"
        )
        self.call = Call.objects.create(name="Planning", date_start=timezone.now())
        self.attendance_user = Attendance.objects.create(
            event=self.call, user=self.user
        )
        self.attendance_contact = Attendance.objects.create(
            event=self.call, contact=self.contact
        )
        Attendance.objects.create(
            event=self.call,
            lead=Lead.objects.create(first_name="No", last_name="Mail"),
        )

    def test_send_invitations_emails_attendees_with_address(self):
        sent = send_invitations(self.call, base_url="https://crm.example.com")
        self.assertEqual(sent, 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("/events/confirm/", mail.outbox[0].body)
        self.assertIn("https://crm.example.com", mail.outbox[0].body)
        self.attendance_user.refresh_from_db()
        self.assertIsNotNone(self.attendance_user.invitation_sent_at)

    def test_confirm_accept_and_decline(self):
        token = make_token(self.attendance_contact)
        attendance = confirm_attendance(
            self.attendance_contact.pk, "accept", token
        )
        self.assertEqual(attendance.status, AcceptanceStatus.ACCEPTED)

        attendance = confirm_attendance(
            self.attendance_contact.pk, "decline", token
        )
        self.assertEqual(attendance.status, AcceptanceStatus.DECLINED)

    def test_invalid_token_action_or_id(self):
        self.assertIsNone(
            confirm_attendance(self.attendance_contact.pk, "accept", "bad-token")
        )
        self.assertIsNone(
            confirm_attendance(
                self.attendance_contact.pk,
                "cancel",
                make_token(self.attendance_contact),
            )
        )
        self.assertIsNone(
            confirm_attendance(999999, "accept", make_token(self.attendance_contact))
        )

    def test_public_confirmation_view(self):
        url = reverse(
            "event_confirmation",
            args=[self.attendance_contact.pk, "accept", make_token(self.attendance_contact)],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.attendance_contact.refresh_from_db()
        self.assertEqual(self.attendance_contact.status, AcceptanceStatus.ACCEPTED)

        bad = self.client.get(
            reverse(
                "event_confirmation",
                args=[self.attendance_contact.pk, "accept", "invalid"],
            )
        )
        self.assertEqual(bad.status_code, 400)


class AttendanceAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("att-admin", "att@example.com", "pw")
        self.client.force_login(self.admin)
        self.user = User.objects.create_user("guest", "guest@example.com", "pw")
        self.call = Call.objects.create(name="Admin Call")
        Attendance.objects.create(event=self.call, user=self.user)

    def test_change_page_renders_attendance_inline(self):
        response = self.client.get(
            reverse("admin:crm_call_change", args=[self.call.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "crm-attendance-event_type-event_id-TOTAL_FORMS")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_invitations_admin_action(self):
        response = self.client.post(
            reverse("admin:crm_call_changelist"),
            {
                "action": "send_invitations_action",
                "_selected_action": [self.call.pk],
                "index": "0",
                "select_across": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["guest@example.com"])
