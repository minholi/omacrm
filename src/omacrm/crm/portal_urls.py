from django.urls import path

from omacrm.crm import portal_views as views

app_name = "portal"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", views.portal_logout, name="logout"),
    path("cases/", views.case_list, name="case_list"),
    path("cases/new/", views.case_create, name="case_create"),
    path("cases/<int:pk>/", views.case_detail, name="case_detail"),
    path("kb/", views.kb_list, name="kb_list"),
    path("kb/<int:pk>/", views.kb_detail, name="kb_detail"),
]
