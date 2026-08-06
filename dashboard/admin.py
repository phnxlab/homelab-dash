from django.contrib import admin

from .models import DiscoveredDevice, HealthCheckResult, Incident, MonitoredEndpoint, ScanTarget


@admin.register(MonitoredEndpoint)
class MonitoredEndpointAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "status", "enabled", "last_checked_at", "last_latency_ms")
    list_filter = ("status", "enabled")
    search_fields = ("name", "url")


@admin.register(HealthCheckResult)
class HealthCheckResultAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "checked_at", "is_up", "latency_ms", "status_code")
    list_filter = ("is_up",)
    readonly_fields = ("checked_at",)


@admin.register(DiscoveredDevice)
class DiscoveredDeviceAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "mac_address", "source", "is_online", "last_seen_at")
    list_filter = ("source", "is_online")
    search_fields = ("hostname", "ip_address", "mac_address")


@admin.register(ScanTarget)
class ScanTargetAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "enabled", "last_scanned_at", "last_error")
    list_filter = ("enabled",)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "opened_at", "resolved_at", "last_error")
    list_filter = ("resolved_at",)
