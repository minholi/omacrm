from unfold.admin import GenericTabularInline

from omacrm.core.models import Attachment


class AttachmentInline(GenericTabularInline):
    model = Attachment
    ct_field = "related_type"
    ct_fk_field = "related_id"
    extra = 0
    fields = ("file", "name", "created_at")
    readonly_fields = ("created_at",)
