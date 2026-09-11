"""Support demo data: cases, knowledge base, documents."""

from omacrm.crm.models import (
    Case,
    Document,
    DocumentFolder,
    KnowledgeBaseArticle,
    KnowledgeBaseCategory,
)

from .common import date_in, text_file

CASES = (
    ("Login failure on the customer portal", "Assigned", "High", "Incident", "mariana.silva@techbrasil.example", "TechBrasil Sistemas", "carla"),
    ("Invoice 2041 is duplicated", "Pending", "Normal", "Question", None, "TechBrasil Sistemas", "carla"),
    ("Cannot download the signed contract", "New", "Normal", "Problem", None, "TechBrasil Sistemas", "carla"),
    ("API rate limit questions", "Closed", "Low", "Question", "john.carter@northwind.example", "Northwind Traders", "demo"),
    ("Data import mapping issue", "Assigned", "Urgent", "Incident", "emily.zhang@bluewave.example", "BlueWave Analytics", "demo"),
    ("Feature request: custom fields on invoices", "Rejected", "Low", "Question", "gustavo.pereira@horizonte.example", "Horizonte Energia", "demo"),
    ("Password reset did not arrive", "Duplicate", "Low", "Question", None, "TechBrasil Sistemas", "carla"),
)

KB_CATEGORIES = (
    ("Getting Started", None),
    ("Billing", None),
    ("Troubleshooting", None),
    ("Account & Access", "Getting Started"),
)

KB_ARTICLES = (
    ("Welcome to the customer portal", "Published", "Getting Started", -60, None, "<h2>Welcome</h2><p>Use the portal to open cases, download documents and read guides.</p>"),
    ("How to reset your password", "Published", "Account & Access", -45, None, "<h2>Reset password</h2><ol><li>Open the portal login.</li><li>Click <em>Forgot password</em>.</li><li>Follow the email link.</li></ol>"),
    ("Understanding your invoice", "Published", "Billing", -30, None, "<h2>Invoice fields</h2><p>Each invoice lists the contract, period and taxes.</p>"),
    ("Troubleshooting email delivery", "Published", "Troubleshooting", -20, date_in(120), "<h2>Email delivery</h2><p>Check the SPF and DKIM records before contacting support.</p>"),
    ("Custom fields guide (draft)", "Draft", "Getting Started", None, None, "<p>Work in progress.</p>"),
    ("SSO configuration", "In Review", "Account & Access", None, None, "<p>Pending technical review.</p>"),
    ("Legacy import instructions", "Archived", "Getting Started", -200, date_in(-60), "<p>Only applies to legacy migrations.</p>"),
)

DOCUMENTS = (
    ("Acme Master Services Agreement", "Contract", "Active", "Contracts", -90, None, "Acme Corp", None),
    ("TechBrasil NDA", "NDA", "Active", "NDAs", -75, None, "TechBrasil Sistemas", "mariana.silva@techbrasil.example"),
    ("TechBrasil Cloud Statement of Work", "Contract", "Active", "Contracts", -40, None, "TechBrasil Sistemas", None),
    ("GreenLeaf Supply Agreement", "Contract", "Expired", "Contracts", -300, date_in(-30), "GreenLeaf Organic Foods", None),
    ("Northwind EULA", "EULA", "Draft", "Contracts", None, None, "Northwind Traders", None),
    ("Billing FAQ", "", "Active", "Guides", -20, None, None, None),
    ("Portal onboarding guide", "", "Active", "Guides", -15, None, "TechBrasil Sistemas", None),
)

FOLDERS = (
    ("Contracts", None),
    ("NDAs", "Contracts"),
    ("Invoices", None),
    ("Guides", None),
)


def seed_support(context):
    accounts = context["accounts"]
    contacts = context["contacts"]
    portal_contact = context["portal_contact"]
    portal_account = context["portal_account"]

    cases = []
    for name, status, priority, case_type, contact_email, account_name, owner in CASES:
        contact = portal_contact if contact_email is None and account_name == "TechBrasil Sistemas" else contacts.get(contact_email)
        case, _ = Case.objects.get_or_create(
            name=name,
            defaults={
                "status": status,
                "priority": priority,
                "type": case_type,
                "contact": contact,
                "account": accounts.get(account_name),
                "assigned_user": context[owner],
                "description": f"Demo case: {name}.",
            },
        )
        cases.append(case)

    categories = {}
    for name, parent_name in KB_CATEGORIES:
        parent = categories.get(parent_name) if parent_name else None
        category, _ = KnowledgeBaseCategory.objects.get_or_create(
            name=name, defaults={"parent": parent}
        )
        categories[name] = category

    articles = []
    for name, status, category_name, published_days, expires, body in KB_ARTICLES:
        article, _ = KnowledgeBaseArticle.objects.get_or_create(
            name=name,
            defaults={
                "status": status,
                "language": "en",
                "type": "Article",
                "publish_date": date_in(published_days) if published_days is not None else None,
                "expiration_date": expires,
                "description": name,
                "body": body,
                "order": len(articles) * 10,
                "assigned_user": context["carla"],
            },
        )
        article.categories.add(categories[category_name])
        articles.append(article)

    folders = {}
    for name, parent_name in FOLDERS:
        parent = folders.get(parent_name) if parent_name else None
        folder, _ = DocumentFolder.objects.get_or_create(
            name=name, defaults={"parent": parent}
        )
        folders[name] = folder

    documents = []
    for name, doc_type, status, folder_name, published_days, expires, account_name, contact_name in DOCUMENTS:
        document, _ = Document.objects.get_or_create(
            name=name,
            defaults={
                "type": doc_type,
                "status": status,
                "folder": folders.get(folder_name),
                "publish_date": date_in(published_days) if published_days is not None else None,
                "expiration_date": expires,
                "description": f"Demo document: {name}.",
                "assigned_user": context["demo"],
            },
        )
        if not document.file:
            document.file.save(
                f"{name.lower().replace(' ', '-')}.txt",
                text_file(
                    f"{name}.txt",
                    f"{name}\n\nDemo document generated by seed_demo.\n",
                ),
                save=True,
            )
        if account_name:
            document.accounts.add(accounts[account_name])
        if contact_name:
            document.contacts.add(contacts[contact_name])
        documents.append(document)

    for document in documents:
        if document.accounts.filter(pk=portal_account.pk).exists():
            document.contacts.add(portal_contact)

    context.update(
        {
            "cases": cases,
            "kb_categories": categories,
            "kb_articles": articles,
            "documents": documents,
            "document_folders": folders,
            "portal_documents": [
                document
                for document in documents
                if document.accounts.filter(pk=portal_account.pk).exists()
            ],
        }
    )
