from functools import wraps

from django import forms
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from omacrm.crm.models import Case, KnowledgeBaseArticle
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
