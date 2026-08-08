from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.shortcuts import redirect, render

from discovery.home_assistant import HomeAssistantError, HomeAssistantProvider

from .models import DiscoveredDevice, Incident, MonitoredEndpoint


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get("next") or "dashboard:home")
        error = "Invalid username or password."
    return render(request, "dashboard/login.html", {"error": error})


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("dashboard:login")


@login_required
def home(request):
    endpoints = MonitoredEndpoint.objects.all()
    context = {
        "endpoints": endpoints,
        "device_count": DiscoveredDevice.objects.filter(is_online=True).count(),
        "open_incidents": Incident.objects.filter(resolved_at__isnull=True).count(),
        "endpoint_counts": endpoints.aggregate(
            up=Count("id", filter=Q(status=MonitoredEndpoint.Status.UP)),
            down=Count("id", filter=Q(status=MonitoredEndpoint.Status.DOWN)),
        ),
    }
    return render(request, "dashboard/home.html", context)


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_portal(request):
    return render(
        request,
        "dashboard/admin_portal.html",
        {"home_assistant_configured": bool(settings.HOME_ASSISTANT_URL and settings.HOME_ASSISTANT_TOKEN)},
    )


@login_required
@user_passes_test(lambda user: user.is_staff)
def home_assistant_sync(request):
    if request.method != "POST":
        return redirect("dashboard:admin_portal")
    try:
        summary = HomeAssistantProvider().sync()
    except HomeAssistantError as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            f"Home Assistant sync complete: {summary.discovered} imported, "
            f"{summary.updated} updated, {summary.skipped} skipped without a valid IP.",
        )
    return redirect("dashboard:admin_portal")
