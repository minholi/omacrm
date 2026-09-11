from django.utils import timezone

from omacrm.core.services.jobs import jobs
from omacrm.crm.models import KnowledgeBaseArticle


@jobs.register(
    "crm.control_kb_article_status",
    name="Publish/archive knowledge base articles by date",
)
def control_kb_article_status(job):
    today = timezone.localdate()

    published = KnowledgeBaseArticle.objects.filter(
        status__in=[
            KnowledgeBaseArticle.Status.DRAFT,
            KnowledgeBaseArticle.Status.IN_REVIEW,
        ],
        publish_date__isnull=False,
        publish_date__lte=today,
    ).update(status=KnowledgeBaseArticle.Status.PUBLISHED)

    archived = KnowledgeBaseArticle.objects.filter(
        status=KnowledgeBaseArticle.Status.PUBLISHED,
        expiration_date__isnull=False,
        expiration_date__lt=today,
    ).update(status=KnowledgeBaseArticle.Status.ARCHIVED)

    return published + archived
