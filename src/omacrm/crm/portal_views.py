from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator

from omacrm.crm.models import Case, Contact, Document, KnowledgeBaseArticle
from omacrm.crm.services.portal import PortalAcl


class PortalLoginView(LoginView):
    template_name = "portal/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("portal:dashboard")


def portal_required(view):
    @wraps(view)
    @login_required(login_url="/portal/login/")
    def wrapper(request, *args, **kwargs):
        if not PortalAcl.is_portal_user(request.user):
            raise PermissionDenied("Portal access required")
        return view(request, *args, **kwargs)

    return wrapper


def portal_logout(request):
    logout(request)
    return redirect("portal:login")


class PortalCaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ("name", "description", "priority", "type")


class PortalProfileForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = (
            "salutation",
            "first_name",
            "last_name",
            "email_address",
            "phone_number",
            "title",
            "address_street",
            "address_city",
            "address_state",
            "address_postal_code",
            "address_country",
        )


@portal_required
def dashboard(request):
    cases = PortalAcl.scope(request.user, "Case", Case.objects.all(), "read")
    open_cases = [case for case in cases.order_by("-created_at") if case.is_open][:5]
    articles = KnowledgeBaseArticle.objects.filter(
        status=KnowledgeBaseArticle.Status.PUBLISHED
    ).order_by("order", "name")[:5]
    return render(
        request,
        "portal/dashboard.html",
        {
            "open_cases": open_cases,
            "case_count": cases.count(),
            "articles": articles,
        },
    )


@portal_required
def case_list(request):
    cases = PortalAcl.scope(
        request.user, "Case", Case.objects.all(), "read"
    ).order_by("-created_at")
    return render(request, "portal/case_list.html", {"cases": cases})


@portal_required
def case_detail(request, pk):
    case = get_object_or_404(Case, pk=pk)
    if not PortalAcl.check(request.user, "Case", "read", case):
        raise PermissionDenied("You cannot view this case")
    return render(request, "portal/case_detail.html", {"case": case})


@portal_required
def case_create(request):
    if not PortalAcl.check(request.user, "Case", "create"):
        raise PermissionDenied("You cannot create cases")

    form = PortalCaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        case = form.save(commit=False)
        case.contact = getattr(request.user, "portal_contact", None)
        case.status = Case.Status.NEW
        case.created_by = request.user
        case.modified_by = request.user
        case.save()
        return redirect("portal:case_detail", pk=case.pk)

    return render(request, "portal/case_form.html", {"form": form})


@portal_required
def kb_list(request):
    articles = PortalAcl.scope(
        request.user,
        "KnowledgeBaseArticle",
        KnowledgeBaseArticle.objects.all(),
        "read",
    ).order_by("order", "name")
    return render(request, "portal/kb_list.html", {"articles": articles})


@portal_required
def kb_detail(request, pk):
    article = get_object_or_404(KnowledgeBaseArticle, pk=pk)
    if not PortalAcl.check(request.user, "KnowledgeBaseArticle", "read", article):
        raise PermissionDenied("You cannot view this article")
    return render(request, "portal/kb_detail.html", {"article": article})


@portal_required
def documents(request):
    queryset = PortalAcl.scope(
        request.user, "Document", Document.objects.select_related("folder"), "read"
    ).order_by("-created_at")
    return render(request, "portal/documents.html", {"documents": queryset})


@portal_required
def document_download(request, pk):
    document = get_object_or_404(Document, pk=pk)
    if not PortalAcl.check(request.user, "Document", "read", document):
        raise PermissionDenied("You cannot download this document")
    if not document.file:
        raise PermissionDenied("This document has no file")
    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.file.name.rsplit("/", 1)[-1],
    )


@portal_required
def profile(request):
    contact = get_object_or_404(Contact, portal_user=request.user)
    form = PortalProfileForm(request.POST or None, instance=contact)
    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.name = contact.build_name() or contact.name
        contact.save()
        if contact.email_address and contact.email_address != request.user.email:
            request.user.email = contact.email_address
            request.user.save(update_fields=["email"])
        messages.success(request, "Profile updated.")
        return redirect("portal:profile")
    return render(request, "portal/profile.html", {"form": form, "contact": contact})


@method_decorator(portal_required, name="dispatch")
class PortalPasswordChangeView(PasswordChangeView):
    template_name = "portal/password_change.html"
    success_url = reverse_lazy("portal:profile")

    def form_valid(self, form):
        messages.success(self.request, "Password changed.")
        return super().form_valid(form)
