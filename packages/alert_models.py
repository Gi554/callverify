from django.db import models


class Review(models.Model):
    signature = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=40)
    actor_id = models.PositiveBigIntegerField()
    note = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
