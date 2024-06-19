from django.contrib import admin
from .models import *

class PolygonInline(admin.TabularInline):
    model = PolygonModel
    extra = 0

class SENTINELDATASETValueInline(admin.TabularInline):
    model = SENTINELDATASETValue
    extra = 0

class LANDSAT8DATASETValueInline(admin.TabularInline):
    model = Landsat8DATASETValue
    extra = 0
    
class LANDSAT9DATASETValueInline(admin.TabularInline):
    model = Landsat9DATASETValue
    extra = 0
    
class MODISDATASETValueInline(admin.TabularInline):
    model = MODISDATASETValue
    extra = 0

class SENTINELImageInline(admin.TabularInline):
    model = SENTINELImage
    extra = 0
    
class LANDSATImageInline(admin.TabularInline):
    model = LANDSATImage
    extra = 0
    

    
class MODISImageInline(admin.TabularInline):
    model = MODISImage
    extra = 0    

class MetrologicalDataInline(admin.TabularInline):
    model = MetrologicalData
    extra = 0
    

class CustomerAdmin(admin.ModelAdmin):
    inlines = [PolygonInline, SENTINELDATASETValueInline, LANDSAT9DATASETValueInline, MODISDATASETValueInline, SENTINELImageInline, LANDSATImageInline, MODISImageInline, MetrologicalDataInline]

admin.site.register(Customer, CustomerAdmin)
admin.site.register(MetrologicalData)
admin.site.register(SENTINELDATASETValue)
admin.site.register(SENTINELImage)
