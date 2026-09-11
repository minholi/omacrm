from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.datasets import BaseDataset
from unfold.decorators import display

from omacrm.core.models import Note


def note_dataset_for(parent_model):
    """Build a tabbed Stream dataset listing the notes of a parent record."""

    class _NoteDatasetAdmin(ModelAdmin):
        list_display = (
            "display_type",
            "display_post",
            "display_reactions",
            "display_author",
            "created_at",
            "is_internal",
        )
        list_per_page = 10
        search_fields = ("post",)
        ordering = ("-created_at",)

        def get_queryset(self, request):
            object_id = (self.extra_context or {}).get("object")
            if not object_id:
                return Note.objects.none()
            content_type = ContentType.objects.get_for_model(
                parent_model, for_concrete_model=False
            )
            return Note.objects.filter(
                parent_type=content_type, parent_id=object_id
            ).select_related("created_by")

        @display(description=_("Type"), ordering="type")
        def display_type(self, obj):
            return obj.get_type_display()

        @display(description=_("Message"), ordering="post")
        def display_post(self, obj):
            text = obj.post or ""
            if obj.data:
                fields = ", ".join(obj.data.keys())
                return f"{text} ({fields})" if text else fields
            return text[:160]

        @display(description=_("Author"), ordering="created_by")
        def display_author(self, obj):
            return obj.created_by.name if obj.created_by else "-"

        @display(description=_("Reactions"))
        def display_reactions(self, obj):
            return obj.reaction_summary or "-"

    return type(
        f"{parent_model.__name__}NoteDataset",
        (BaseDataset,),
        {
            "model": Note,
            "model_admin": _NoteDatasetAdmin,
            "tab": True,
            "title": _("Stream"),
        },
    )
