import re
from html.parser import HTMLParser

from constance import config
from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template
from django.utils.html import strip_tags
from premailer import Premailer

from omacrm.core.models import Note

MERGE_TAGS = [
    {"token": "{{ name }}", "label": "Full name"},
    {"token": "{{ first_name }}", "label": "First name"},
    {"token": "{{ last_name }}", "label": "Last name"},
    {"token": "{{ email_address }}", "label": "Email address"},
    {"token": "{{ phone_number }}", "label": "Phone number"},
    {"token": "{{ record.name }}", "label": "Record name"},
    {"token": "{{ record.email_address }}", "label": "Record email"},
    {"token": "{{ custom.field_name }}", "label": "Custom field"},
    {"token": "{{ company_name }}", "label": "Company name"},
]

_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_RELATIVE_ATTR = re.compile(r"""(?P<attr>\b(?:src|href)\s*=\s*["'])/(?!/)""")
_RELATIVE_URL_FUNC = re.compile(r"""(?P<prefix>url\(\s*["']?)/(?!/)""")


def render_email_template(template, record):
    """Render an EmailTemplate against a record using Django templates."""

    fields = {}
    for field in record._meta.fields:
        fields[field.name] = getattr(record, field.attname, "")
    context = Context(
        {
            "record": record,
            "object": record,
            "custom": getattr(record, "custom_data", None) or {},
            "company_name": config.company_name,
            **fields,
        }
    )

    subject = Template(template.subject).render(context)
    body = Template(template.body).render(context)
    return subject, body


def _absolutize_urls(html, base_url):
    if not base_url:
        return html
    base_url = base_url.rstrip("/")
    html = _RELATIVE_ATTR.sub(rf"\g<attr>{base_url}/", html)
    html = _RELATIVE_URL_FUNC.sub(rf"\g<prefix>{base_url}/", html)
    return html


class _EmailTextExtractor(HTMLParser):
    """Small stdlib HTML to plain-text converter for email alternatives."""

    SKIP_TAGS = {"script", "style", "head", "title"}
    BLOCK_TAGS = {
        "address",
        "blockquote",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ol",
        "p",
        "section",
        "table",
        "tr",
        "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip += 1
        elif tag in self.BLOCK_TAGS:
            self._parts.append("\n")
        if tag == "br":
            self._parts.append("\n")
        if tag == "li":
            self._parts.append(" - ")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def text(self):
        lines = ("".join(self._parts)).splitlines()
        cleaned = [line.strip() for line in lines]
        blocks = []
        for line in cleaned:
            if line or (blocks and blocks[-1]):
                blocks.append(line)
        return "\n".join(blocks).strip()


def html_to_text(html: str) -> str:
    if not html:
        return ""
    parser = _EmailTextExtractor()
    parser.feed(html)
    return parser.text()


def looks_like_html(value: str) -> bool:
    return bool(value and _HTML_TAG.search(value))


def prepare_email_html(html, base_url=None):
    """Inline CSS and absolutize URLs, returning (html, plain text)."""

    if base_url is None:
        base_url = config.public_base_url

    if not html:
        return html, ""

    if not _HTML_TAG.search(html):
        return html, strip_tags(html)

    html = _absolutize_urls(html, base_url)
    premailer = Premailer(
        html,
        allow_network=False,
        preserve_handlebar_syntax=True,
        remove_classes=False,
    )
    inlined = premailer.transform(pretty_print=False)
    return inlined, html_to_text(inlined)


def send_email(
    record,
    *,
    template=None,
    to_email: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    user=None,
):
    """Send an email related to a record and log it on the record stream."""

    to_email = to_email or getattr(record, "email_address", "") or ""
    if not to_email:
        raise ValueError("No recipient email address")

    if template is not None:
        rendered_subject, rendered_body = render_email_template(template, record)
        subject = subject or rendered_subject
        body = body or rendered_body

    if not subject:
        raise ValueError("Email subject is required")

    html_body, text_body = prepare_email_html(body or "")
    sent = send_mail(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        html_message=html_body or None,
        fail_silently=False,
    )

    note = Note.objects.create(
        type=Note.Type.EMAIL,
        parent=record,
        post=subject,
        data={"to": to_email, "subject": subject},
        created_by=user,
    )
    return note, sent
