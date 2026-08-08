from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("admin-portal/", views.admin_portal, name="admin_portal"),
    path("admin-portal/home-assistant-sync/", views.home_assistant_sync, name="home_assistant_sync"),
]
