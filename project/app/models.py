from django.contrib.gis.db import models
from django.contrib.auth.models import User




class Customer(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    first_name=models.CharField(max_length=225,null=True,blank=True)
    last_name=models.CharField(max_length=225,null=True,blank=True)
    email=models.EmailField()
    phone=models.CharField(max_length=225,null=True,blank=True)
    def __str__(self):
        return self.user.username


class PolygonModel(models.Model):
    polygon_id = models.CharField(max_length=50)
    properties = models.JSONField()
    area_in_acres = models.FloatField(null=True, default=0.0)
    customer = models.ForeignKey(Customer, related_name='polygons', on_delete=models.CASCADE,null=True,blank=True)
    
    def __str__(self):
        return self.polygon_id
    
    

class PointModel(models.Model):
    polygon = models.ForeignKey(PolygonModel, related_name='points', on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    
    def __str__(self):
        return f"PointModel ({self.latitude}, {self.longitude})"
    
class SENTINELDATASETValue(models.Model):
    polygon = models.ForeignKey(PolygonModel, related_name='sentinel_dataset_values', on_delete=models.CASCADE)
    date = models.DateField()
    ndvi_value = models.FloatField(null=True)
    ndwi_value = models.FloatField(null=True)
    ndmi_value = models.FloatField(null=True)
    evi_value = models.FloatField(null=True)
    customer=models.ForeignKey(Customer,related_name='sentinel_dataset_values',on_delete=models.CASCADE,default=None)
    
class Landsat8DATASETValue(models.Model):
    polygon = models.ForeignKey(PolygonModel, related_name='landsat8_dataset_values', on_delete=models.CASCADE)
    date = models.DateField()
    ndvi_value = models.FloatField(null=True)
    ndwi_value = models.FloatField(null=True)
    ndmi_value = models.FloatField(null=True)
    evi_value = models.FloatField(null=True)
    customer=models.ForeignKey(Customer,related_name='landsat8_dataset_values',on_delete=models.CASCADE,default=None)
    

class Landsat9DATASETValue(models.Model):
    polygon = models.ForeignKey(PolygonModel, related_name='landsat9_dataset_values', on_delete=models.CASCADE)
    date = models.DateField()
    ndvi_value = models.FloatField(null=True)
    ndwi_value = models.FloatField(null=True)
    ndmi_value = models.FloatField(null=True)
    evi_value = models.FloatField(null=True)
    customer=models.ForeignKey(Customer,related_name='landsat9_dataset_values',on_delete=models.CASCADE,default=None)
    
    
class MODISDATASETValue(models.Model):
    polygon = models.ForeignKey(PolygonModel, related_name='modis_dataset_values', on_delete=models.CASCADE)
    date = models.DateField()
    ndvi_value = models.FloatField(null=True)
    ndwi_value = models.FloatField(null=True)
    ndmi_value = models.FloatField(null=True)
    evi_value = models.FloatField(null=True)
    customer=models.ForeignKey(Customer,related_name='modis_dataset_values',on_delete=models.CASCADE,default=None)
    

    
class SENTINELImage(models.Model):
    polygon=models.ForeignKey(PolygonModel,related_name='sentinel_images',on_delete=models.CASCADE)
    ndvi_image=models.ImageField(upload_to='sentinel/ndvi_images/')
    evi_image=models.ImageField(upload_to='sentinel/evi_images/')
    ndwi_image=models.ImageField(upload_to='sentinel/ndwi_images/')
    ndmi_image=models.ImageField(upload_to='sentinel/ndmi_images/')
    date=models.DateField()
    customer=models.ForeignKey(Customer,related_name='sentinel_images',on_delete=models.CASCADE)
    
    def __str__(self):
        return f"sentinel Image for Polygon {self.polygon.polygon_id} on {self.date}"
    
    
class LANDSATImage(models.Model):
    polygon=models.ForeignKey(PolygonModel,related_name='landsat_images',on_delete=models.CASCADE)
    ndvi_image=models.ImageField(upload_to='landsat/ndvi_images/')
    evi_image=models.ImageField(upload_to='landsat/evi_images/')
    ndwi_image=models.ImageField(upload_to='landsat/ndwi_images/')
    ndmi_image=models.ImageField(upload_to='landsat/ndmi_images/')
    date=models.DateField()
    customer=models.ForeignKey(Customer,related_name='landsat_images',on_delete=models.CASCADE)
    
    def __str__(self):
        return f"landsat Image for Polygon {self.polygon.polygon_id} on {self.date}"
    
class MODISImage(models.Model):
    polygon=models.ForeignKey(PolygonModel,related_name='modis_images',on_delete=models.CASCADE)
    ndvi_image=models.ImageField(upload_to='modis/ndvi_images/')
    evi_image=models.ImageField(upload_to='modis/evi_images/')
    ndwi_image=models.ImageField(upload_to='modis/ndwi_images/')
    ndmi_image=models.ImageField(upload_to='modis/ndmi_images/')
    date=models.DateField()
    customer=models.ForeignKey(Customer,related_name='modis_images',on_delete=models.CASCADE)
    
    def __str__(self):
        return f"modis Image for Polygon {self.polygon.polygon_id} on {self.date}"    

    
class MetrologicalData (models.Model):
    polygon=models.ForeignKey(PolygonModel,related_name='weather_data',on_delete=models.CASCADE)
    customer=models.ForeignKey(Customer,related_name='weather_data',on_delete=models.CASCADE)
    date=models.DateTimeField()
    temperature_data=models.FloatField(null=True)
    humidity_data=models.FloatField(null=True)
    rainfall_data=models.FloatField(null=True)
    
    def __str__(self):
        return f"Weather Data for Polygon {self.polygon.polygon_id} on {self.date}"

