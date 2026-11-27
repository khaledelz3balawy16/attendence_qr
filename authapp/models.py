from django.db import models
from django.utils import timezone


def current_local_time():
    return timezone.localtime().time().replace(microsecond=0)


class AttendanceQR(models.Model):
    kbc_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    group = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    time = models.TimeField(default=current_local_time)

    class Meta:
        db_table = 'attendance_QR'

    def __str__(self):
        return f"{self.name} - {self.email}"
