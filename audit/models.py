from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.TextField()
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    target_model = models.CharField(max_length=255, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        actor = self.user.get_full_name if self.user else "System"
        return f"{actor} - {self.action[:50]}"
