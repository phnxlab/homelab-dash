from django.conf import settings
from django.db import models


class MonitoredEndpoint(models.Model):
    class Status(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        UP = "up", "Up"
        DOWN = "down", "Down"

    name = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    enabled = models.BooleanField(default=True)
    interval_seconds = models.PositiveIntegerField(default=60)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UNKNOWN)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    last_status_code = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class HealthCheckResult(models.Model):
    endpoint = models.ForeignKey(MonitoredEndpoint, on_delete=models.CASCADE, related_name="checks")
    checked_at = models.DateTimeField(auto_now_add=True)
    is_up = models.BooleanField()
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-checked_at"]


class DiscoveredDevice(models.Model):
    class Source(models.TextChoices):
        HOME_ASSISTANT = "home_assistant", "Home Assistant"
        ARP = "arp", "ARP"
        MANUAL = "manual", "Manual"

    hostname = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField()
    mac_address = models.CharField(max_length=17, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    is_online = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ip_address", "source"], name="unique_device_source")]
        ordering = ["ip_address"]

    def __str__(self):
        return self.hostname or self.ip_address


class ScanTarget(models.Model):
    name = models.CharField(max_length=120)
    cidr = models.CharField(max_length=43, help_text="Explicit IPv4/IPv6 network or host target.")
    enabled = models.BooleanField(default=True)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.name} ({self.cidr})"


class Incident(models.Model):
    endpoint = models.ForeignKey(MonitoredEndpoint, on_delete=models.CASCADE, related_name="incidents")
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    @property
    def is_open(self):
        return self.resolved_at is None
