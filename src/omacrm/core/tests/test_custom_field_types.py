import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import (
    Attachment,
    CustomEntity,
    CustomField,
    CustomLink,
    DynamicRecord,
    Layout,
    User,
)
from omacrm.core.services import custom_entities, relations
from omacrm.crm.models import Account

MEDIA_ROOT = tempfile.mkdtemp()
ATTACHMENT_PREFIX = "core-attachment-related_type-related_id"


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CustomFieldTypeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "field-admin", "field@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for attachment in Attachment.objects.all():
            if attachment.file:
                attachment.file.delete(save=False)
        DynamicRecord.objects.filter(entity_type="Project").delete()
        Layout.objects.filter(entity_type="Project").delete()
        CustomLink.objects.filter(entity_type="Project").delete()
        CustomField.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def _field(self, name, field_type, **extra):
        field = CustomField.objects.create(
            entity_type="Project",
            name=name,
            label=name.replace("_", " ").title(),
            field_type=field_type,
            **extra,
        )
        registry.invalidate()
        return field

    def _form_data(self, **extra):
        data = {
            "name": "Apollo",
            "assigned_user": "",
            "teams": [],
            "_save": "Save",
            f"{ATTACHMENT_PREFIX}-TOTAL_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-INITIAL_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-MIN_NUM_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-MAX_NUM_FORMS": "1000",
        }
        data.update(extra)
        return data

    def _records(self):
        return custom_entities.get_proxy("Project").objects

    def test_number_field_autoincrements(self):
        self._field("code", "number", params={"prefix": "PRJ-", "padding": 4})
        for expected in ("PRJ-0001", "PRJ-0002"):
            response = self.client.post(
                reverse("admin:core_project_add"), self._form_data()
            )
            self.assertEqual(response.status_code, 302, response.content)
            record = self._records().order_by("-pk").first()
            self.assertEqual(record.custom_data["code"], expected)

        record = self._records().order_by("-pk").first()
        response = self.client.post(
            reverse("admin:core_project_change", args=[record.pk]),
            self._form_data(**{"custom__code": record.custom_data["code"]}),
        )
        self.assertEqual(response.status_code, 302, response.content)
        record.refresh_from_db()
        self.assertEqual(record.custom_data["code"], "PRJ-0002")

    def test_phone_field_is_normalized(self):
        self._field("contact_phone", "phone")
        response = self.client.post(
            reverse("admin:core_project_add"),
            self._form_data(**{"custom__contact_phone": "(415) 555-2671"}),
        )
        self.assertEqual(response.status_code, 302, response.content)
        record = self._records().get(name="Apollo")
        self.assertEqual(record.custom_data["contact_phone"], "+14155552671")

    def test_decimal_field_is_json_safe(self):
        self._field("score", "decimal")
        response = self.client.post(
            reverse("admin:core_project_add"),
            self._form_data(**{"custom__score": "12.345"}),
        )
        self.assertEqual(response.status_code, 302, response.content)
        record = self._records().get(name="Apollo")
        self.assertEqual(record.custom_data["score"], 12.345)

    def test_address_field_round_trip_and_display(self):
        self._field("site_address", "address")
        response = self.client.post(
            reverse("admin:core_project_add"),
            self._form_data(
                **{
                    "custom__site_address_0": "1 Main St",
                    "custom__site_address_1": "Springfield",
                    "custom__site_address_2": "IL",
                    "custom__site_address_3": "62701",
                    "custom__site_address_4": "United States",
                }
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        record = self._records().get(name="Apollo")
        self.assertEqual(
            record.custom_data["site_address"],
            {
                "street": "1 Main St",
                "city": "Springfield",
                "state": "IL",
                "postal_code": "62701",
                "country": "United States",
            },
        )

        Layout.objects.create(
            entity_type="Project",
            layout_name="list",
            data=["name", "site_address"],
            is_custom=True,
        )
        registry.invalidate()
        response = self.client.get(reverse("admin:core_project_changelist"))
        self.assertContains(response, "1 Main St, Springfield")

    def test_file_field_upload_and_clear(self):
        self._field("contract", "file")
        response = self.client.post(
            reverse("admin:core_project_add"),
            {
                **self._form_data(),
                "custom__contract": SimpleUploadedFile(
                    "contract.txt", b"hello", content_type="text/plain"
                ),
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        record = self._records().get(name="Apollo")
        attachment = Attachment.objects.get(pk=record.custom_data["contract"])
        self.assertEqual(attachment.name, "contract.txt")
        self.assertEqual(attachment.related, record)

        response = self.client.get(
            reverse("admin:core_project_change", args=[record.pk])
        )
        self.assertContains(response, "contract.txt")

        response = self.client.post(
            reverse("admin:core_project_change", args=[record.pk]),
            self._form_data(**{"custom__contract-clear": "on"}),
        )
        self.assertEqual(response.status_code, 302, response.content)
        record.refresh_from_db()
        self.assertNotIn("contract", record.custom_data)
        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())

    def test_attachment_multiple_appends(self):
        self._field("files", "attachmentMultiple")
        response = self.client.post(
            reverse("admin:core_project_add"),
            {
                **self._form_data(),
                "custom__files": [
                    SimpleUploadedFile("one.txt", b"1", content_type="text/plain"),
                    SimpleUploadedFile("two.txt", b"2", content_type="text/plain"),
                ],
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        record = self._records().get(name="Apollo")
        self.assertEqual(len(record.custom_data["files"]), 2)

        response = self.client.post(
            reverse("admin:core_project_change", args=[record.pk]),
            {
                **self._form_data(),
                "custom__files": [
                    SimpleUploadedFile("three.txt", b"3", content_type="text/plain"),
                ],
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        record.refresh_from_db()
        self.assertEqual(len(record.custom_data["files"]), 3)

    def test_foreign_field_reads_linked_record(self):
        CustomLink.objects.create(
            entity_type="Project",
            name="account",
            link_type="belongsTo",
            link_entity="Account",
            label="Account",
        )
        self._field(
            "account_name",
            "foreign",
            params={"link": "account", "field": "name"},
            read_only=True,
        )
        account = Account.objects.create(name="Acme")
        record = self._records().create(entity_type="Project", name="Apollo")
        relations.add_related(record, "account", account)

        response = self.client.get(
            reverse("admin:core_project_change", args=[record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Acme"')

        Layout.objects.create(
            entity_type="Project",
            layout_name="list",
            data=["name", "account_name"],
            is_custom=True,
        )
        registry.invalidate()
        response = self.client.get(reverse("admin:core_project_changelist"))
        self.assertContains(response, "Acme")

    def test_foreign_field_validation(self):
        from django.core.exceptions import ValidationError

        field = CustomField(
            entity_type="Project",
            name="bad_foreign",
            field_type="foreign",
            params={"link": "missing", "field": "name"},
        )
        with self.assertRaises(ValidationError):
            field.full_clean()
