"""Sales demo data: accounts, contacts, leads, opportunities."""

from djmoney.money import Money

from omacrm.crm.models import (
    Account,
    Contact,
    Lead,
    Opportunity,
    OpportunityContact,
)
from omacrm.crm.services.lead_convert import LeadConversionService

from .common import date_in

ACCOUNTS = (
    ("Northwind Traders", "Wholesale", "Customer", "100 Wacker Dr", "Chicago", "IL", "60601", "United States", "+13125550101", "info@northwind.example", "https://northwind.example"),
    ("TechBrasil Sistemas", "Software", "Customer", "Av. Paulista 1000", "São Paulo", "SP", "01310-100", "Brazil", "+551155501020", "contato@techbrasil.example", "https://techbrasil.example"),
    ("Rheinland Maschinenbau GmbH", "Manufacturing", "Partner", "Königsallee 12", "Düsseldorf", "NRW", "40212", "Germany", "+492115550103", "info@rheinland.example", "https://rheinland.example"),
    ("BlueWave Analytics", "Computer", "Customer", "500 Congress Ave", "Austin", "TX", "78701", "United States", "+15125550104", "hello@bluewave.example", "https://bluewave.example"),
    ("Copacabana Turismo", "Travel", "Customer", "Av. Atlântica 1500", "Rio de Janeiro", "RJ", "22010-000", "Brazil", "+552155501050", "vendas@copacabana.example", "https://copacabana.example"),
    ("Novo Banco Digital", "Banking", "Customer", "Av. Faria Lima 3500", "São Paulo", "SP", "04538-133", "Brazil", "+551155501060", "contato@novobanco.example", "https://novobanco.example"),
    ("GreenLeaf Organic Foods", "Food & Beverage", "Customer", "700 SE Hawthorne Blvd", "Portland", "OR", "97214", "United States", "+15035550107", "office@greenleaf.example", "https://greenleaf.example"),
    ("Summit Legal Partners", "Legal", "Partner", "1700 Broadway", "Denver", "CO", "80290", "United States", "+13035550108", "contact@summitlegal.example", "https://summitlegal.example"),
    ("Atlas Logistics", "Transportation", "Customer", "Waalhaven 25", "Rotterdam", "ZH", "3087", "Netherlands", "+31105550109", "ops@atlaslog.example", "https://atlaslog.example"),
    ("Pixel & Co. Studio", "Creative", "Reseller", "Rua Augusta 900", "Lisbon", "LX", "1100-053", "Portugal", "+351215501100", "studio@pixelco.example", "https://pixelco.example"),
    ("Horizonte Energia", "Energy", "Investor", "SQS 308 Bloco C", "Brasília", "DF", "70355-030", "Brazil", "+556155501110", "invest@horizonte.example", "https://horizonte.example"),
    ("Acme Corp", "Technology", "Customer", "350 Fifth Ave", "New York", "NY", "10118", "United States", "+121255501120", "info@acme.example", "https://acme.example"),
)

CONTACTS = (
    ("Mr.", "John", "Carter", "CTO", "Northwind Traders", "john.carter@northwind.example", "+13125550201", "Chicago", "United States"),
    ("Ms.", "Mariana", "Silva", "CFO", "TechBrasil Sistemas", "mariana.silva@techbrasil.example", "+551155502020", "São Paulo", "Brazil"),
    ("Mr.", "Klaus", "Weber", "Procurement Manager", "Rheinland Maschinenbau GmbH", "klaus.weber@rheinland.example", "+49211550203", "Düsseldorf", "Germany"),
    ("Ms.", "Emily", "Zhang", "Head of Data", "BlueWave Analytics", "emily.zhang@bluewave.example", "+15125550204", "Austin", "United States"),
    ("Mr.", "Rafael", "Costa", "Operations Director", "Copacabana Turismo", "rafael.costa@copacabana.example", "+552155502050", "Rio de Janeiro", "Brazil"),
    ("Ms.", "Camila", "Rocha", "Product Owner", "Novo Banco Digital", "camila.rocha@novobanco.example", "+551155502060", "São Paulo", "Brazil"),
    ("Mr.", "Michael", "Green", "Plant Manager", "GreenLeaf Organic Foods", "michael.green@greenleaf.example", "+15035550207", "Portland", "United States"),
    ("Ms.", "Sarah", "Bennett", "Partner", "Summit Legal Partners", "sarah.bennett@summitlegal.example", "+13035550208", "Denver", "United States"),
    ("Mr.", "Lars", "de Vries", "Logistics Lead", "Atlas Logistics", "lars.devries@atlaslog.example", "+31105550209", "Rotterdam", "Netherlands"),
    ("Ms.", "Inês", "Martins", "Creative Director", "Pixel & Co. Studio", "ines.martins@pixelco.example", "+351215502100", "Lisbon", "Portugal"),
    ("Mr.", "Gustavo", "Pereira", "Energy Analyst", "Horizonte Energia", "gustavo.pereira@horizonte.example", "+556155502110", "Brasília", "Brazil"),
    ("Ms.", "Olivia", "Brown", "VP Sales", "Acme Corp", "olivia.brown@acme.example", "+121255502120", "New York", "United States"),
    ("Mr.", "Pedro", "Alves", "IT Support", "TechBrasil Sistemas", "pedro.alves@techbrasil.example", "+551155502031", "São Paulo", "Brazil"),
    ("Ms.", "Julia", "Nogueira", "Marketing Manager", "Novo Banco Digital", "julia.nogueira@novobanco.example", "+551155502061", "São Paulo", "Brazil"),
    ("Mr.", "Thomas", "Müller", "Engineer", "Rheinland Maschinenbau GmbH", "thomas.mueller@rheinland.example", "+492115502032", "Düsseldorf", "Germany"),
    ("Ms.", "Amanda", "Clark", "Buyer", "Northwind Traders", "amanda.clark@northwind.example", "+131255502021", "Chicago", "United States"),
    ("Mr.", "Bruno", "Tavares", "Consultant", "Atlas Logistics", "bruno.tavares@atlaslog.example", "+311055502091", "Rotterdam", "Netherlands"),
    ("Ms.", "Sofia", "Ribeiro", "Account Manager", "Copacabana Turismo", "sofia.ribeiro@copacabana.example", "+552155502051", "Rio de Janeiro", "Brazil"),
    ("Mr.", "Daniel", "King", "COO", "BlueWave Analytics", "daniel.king@bluewave.example", "+151255502041", "Austin", "United States"),
    ("Ms.", "Laura", "Prado", "Finance", "Horizonte Energia", "laura.prado@horizonte.example", "+556155502111", "Brasília", "Brazil"),
)

LEADS = (
    ("Aisha", "Rahman", "New", "Web Site", "Marketing Manager", "aisha.rahman@example.com", "Brooklyn", "United States", None),
    ("Carlos", "Mendes", "New", "Campaign", "Owner", "carlos.mendes@example.com", "Belo Horizonte", "Brazil", None),
    ("Felipe", "Duarte", "Assigned", "Partner", "CTO", "felipe.duarte@example.com", "Curitiba", "Brazil", None),
    ("Grace", "Lee", "In Process", "Email", "Head of Ops", "grace.lee@example.com", "Seattle", "United States", None),
    ("Hugo", "Santana", "In Process", "Existing Customer", "Director", "hugo.santana@example.com", "Recife", "Brazil", None),
    ("Isabela", "Moreira", "New", "Web Site", "Founder", "isabela.moreira@example.com", "Florianópolis", "Brazil", Money(45000, "BRL")),
    ("Jack", "Thompson", "Assigned", "Call", "VP Engineering", "jack.thompson@example.com", "Boston", "United States", None),
    ("Karen", "Oliveira", "New", "Public Relations", "Marketing Lead", "karen.oliveira@example.com", "Porto Alegre", "Brazil", None),
    ("Lucas", "Ferraz", "Recycled", "Other", "Analyst", "lucas.ferraz@example.com", "Campinas", "Brazil", None),
    ("Mia", "Johnson", "Dead", "Other", "Consultant", "mia.johnson@example.com", "Miami", "United States", None),
    ("Eduardo", "Lima", "In Process", "Web Site", "Partner", "eduardo.lima@limaconsulting.example", "São Paulo", "Brazil", Money(25000, "EUR")),
    ("Henrik", "Larsen", "Assigned", "Partner", "CEO", "henrik.larsen@nordicsystems.example", "Oslo", "Norway", Money(80000, "USD")),
)

OPPORTUNITIES = (
    ("Northwind ERP rollout", "Prospecting", Money(120000, "USD"), "Northwind Traders", "john.carter@northwind.example", 45, "Web Site"),
    ("TechBrasil cloud migration", "Qualification", Money(85000, "USD"), "TechBrasil Sistemas", "mariana.silva@techbrasil.example", 30, "Existing Customer"),
    ("Rheinland maintenance renewal", "Proposal", Money(60000, "EUR"), "Rheinland Maschinenbau GmbH", "klaus.weber@rheinland.example", 20, "Partner"),
    ("BlueWave analytics platform", "Negotiation", Money(150000, "USD"), "BlueWave Analytics", "emily.zhang@bluewave.example", 15, "Campaign"),
    ("Copacabana travel portal", "Closed Won", Money(40000, "BRL"), "Copacabana Turismo", "rafael.costa@copacabana.example", -30, "Web Site"),
    ("GreenLeaf supply chain", "Closed Won", Money(90000, "USD"), "GreenLeaf Organic Foods", "michael.green@greenleaf.example", -60, "Partner"),
    ("Summit Legal case management", "Closed Lost", Money(35000, "USD"), "Summit Legal Partners", "sarah.bennett@summitlegal.example", -20, "Other"),
    ("Atlas fleet tracking", "Proposal", Money(110000, "EUR"), "Atlas Logistics", "lars.devries@atlaslog.example", 40, "Email"),
    ("Meridian onboarding", "Closed Won", Money(55000, "USD"), "BlueWave Analytics", "emily.zhang@bluewave.example", -300, "Partner"),
    ("Harbor CRM rollout", "Closed Won", Money(72000, "EUR"), "Rheinland Maschinenbau GmbH", "klaus.weber@rheinland.example", -250, "Existing Customer"),
    ("Nimbus support renewal", "Closed Won", Money(38000, "USD"), "Northwind Traders", "john.carter@northwind.example", -195, "Existing Customer"),
    ("Vertex data migration", "Closed Won", Money(64000, "USD"), "TechBrasil Sistemas", "mariana.silva@techbrasil.example", -150, "Campaign"),
    ("Orchid retail suite", "Closed Won", Money(47000, "BRL"), "Copacabana Turismo", "rafael.costa@copacabana.example", -110, "Web Site"),
    ("Pioneer field service", "Closed Won", Money(83000, "USD"), "GreenLeaf Organic Foods", "michael.green@greenleaf.example", -75, "Partner"),
    ("Acme CRM expansion", "Qualification", Money(95000, "USD"), "Acme Corp", "olivia.brown@acme.example", 75, "Existing Customer"),
    ("Rheinland IoT add-on", "Prospecting", Money(45000, "EUR"), "Rheinland Maschinenbau GmbH", "klaus.weber@rheinland.example", 105, "Partner"),
    ("Atlas warehouse module", "Negotiation", Money(125000, "USD"), "Atlas Logistics", "lars.devries@atlaslog.example", 140, "Email"),
)


def _account(name, industry, account_type, street, city, state, postal, country, phone, email, website):
    account, _ = Account.objects.get_or_create(
        name=name,
        defaults={
            "industry": industry,
            "type": account_type,
            "billing_address_street": street,
            "billing_address_city": city,
            "billing_address_state": state,
            "billing_address_postal_code": postal,
            "billing_address_country": country,
            "shipping_address_street": street,
            "shipping_address_city": city,
            "shipping_address_state": state,
            "shipping_address_postal_code": postal,
            "shipping_address_country": country,
            "phone_number": phone,
            "email_address": email,
            "website": website,
        },
    )
    return account


def seed_sales(context):
    accounts = {}
    for data in ACCOUNTS:
        account = _account(*data)
        accounts[account.name] = account

    contacts = {}
    for salutation, first, last, title, account_name, email, phone, city, country in CONTACTS:
        contact, _ = Contact.objects.get_or_create(
            email_address=email,
            defaults={
                "salutation": salutation,
                "first_name": first,
                "last_name": last,
                "title": title,
                "account": accounts.get(account_name),
                "phone_number": phone,
                "address_city": city,
                "address_country": country,
                "assigned_user": context["ana"] if len(contacts) % 2 else context["bruno"],
            },
        )
        contacts[email] = contact

    portal_contact = context["portal_contact"]
    portal_account = accounts["TechBrasil Sistemas"]
    portal_contact.account = portal_account
    portal_contact.title = "IT Manager"
    portal_contact.phone_number = "+551155509900"
    portal_contact.address_city = "São Paulo"
    portal_contact.address_country = "Brazil"
    portal_contact.assigned_user = context["carla"]
    portal_contact.save()

    leads = []
    for first, last, status, source, title, email, city, country, amount in LEADS:
        lead, _ = Lead.objects.get_or_create(
            email_address=email,
            defaults={
                "first_name": first,
                "last_name": last,
                "status": status,
                "source": source,
                "title": title,
                "phone_number": "+15550000000",
                "address_city": city,
                "address_country": country,
                "assigned_user": context["demo"] if status != "New" else None,
                "opportunity_amount": amount,
                "description": f"Inbound lead from {source}.",
            },
        )
        leads.append(lead)

    converted = []
    service = LeadConversionService(user=context["demo"], skip_duplicate_check=True)
    conversions = (
        ("eduardo.lima@limaconsulting.example", "Lima Consulting", "São Paulo", "Brazil"),
        ("henrik.larsen@nordicsystems.example", "Nordic Systems AS", "Oslo", "Norway"),
    )
    for email, account_name, city, country in conversions:
        lead = next((item for item in leads if item.email_address == email), None)
        if lead is None or lead.status == Lead.Status.CONVERTED:
            continue
        lead.account_name = account_name
        lead.address_city = city
        lead.address_country = country
        lead.save()
        data = service.get_convert_data(lead)
        data["Account"].update(
            {
                "billing_address_city": city,
                "billing_address_country": country,
                "phone_number": lead.phone_number,
            }
        )
        result = service.convert(lead, data)
        converted.append(result)
        if result.get("Account") is not None:
            accounts[account_name] = result["Account"]
        if result.get("Contact") is not None:
            contacts[lead.email_address] = result["Contact"]

    opportunities = []
    for name, stage, amount, account_name, contact_email, due, source in OPPORTUNITIES:
        opportunity, _ = Opportunity.objects.get_or_create(
            name=name,
            defaults={
                "stage": stage,
                "amount": amount,
                "account": accounts.get(account_name),
                "contact": contacts.get(contact_email),
                "close_date": date_in(due),
                "lead_source": source,
                "assigned_user": context["ana"] if due % 2 else context["bruno"],
                "description": f"{stage} stage deal for {account_name}.",
                "custom_data": {
                    "tier": "Gold" if amount.amount >= 100000 else "Silver",
                    "is_strategic": amount.amount >= 90000,
                },
            },
        )
        opportunities.append(opportunity)

    for result in converted:
        opportunity = result.get("Opportunity")
        if opportunity is not None:
            opportunities.append(opportunity)

    for opportunity in opportunities:
        if opportunity.contact_id:
            OpportunityContact.objects.get_or_create(
                opportunity=opportunity,
                contact=opportunity.contact,
                defaults={"role": "Decision Maker"},
            )

    accounts["Acme Corp"].custom_data = {"tier": "Gold", "is_strategic": True}
    accounts["Acme Corp"].save(update_fields=["custom_data"])

    duplicate_account = None
    if Account.objects.filter(name="Acme Corp").count() < 2:
        duplicate_account = Account.objects.create(
            name="Acme Corp",
            email_address="info@acme.example",
            industry="Technology",
            type="Customer",
        )
    else:
        duplicate_account = (
            Account.objects.filter(name="Acme Corp").order_by("pk").last()
        )

    duplicate_contact = None
    if (
        Contact.objects.filter(
            first_name="John",
            last_name="Carter",
            email_address="john.carter@northwind.example",
        ).count()
        < 2
    ):
        duplicate_contact = Contact.objects.create(
            first_name="John",
            last_name="Carter",
            email_address="john.carter@northwind.example",
            title="CTO",
            account=accounts["Northwind Traders"],
        )
    else:
        duplicate_contact = (
            Contact.objects.filter(
                first_name="John",
                last_name="Carter",
                email_address="john.carter@northwind.example",
            )
            .order_by("-pk")
            .first()
        )

    context.update(
        {
            "accounts": accounts,
            "contacts": contacts,
            "leads": leads,
            "opportunities": opportunities,
            "converted": converted,
            "portal_account": portal_account,
            "duplicate_account": duplicate_account,
            "duplicate_contact": duplicate_contact,
        }
    )
