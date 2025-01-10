from django.db import models

class FuelPrice(models.Model):
    location = models.CharField(max_length=255)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)
