from django.urls import path
from .views import *
urlpatterns = [
    path('home/',home,name='home'),
    path('register/',register,name='register'),
    path('ndvi/',ndvi,name='ndvi'),
    path('save_polygon/',save_polygon,name='save_polygon'),
    path('get_user_polygons/',get_user_polygons, name='get_user_polygons'),
    path('download_csv/<str:value_type>/',download_csv, name='download_csv'),
    path('get_polygons/', get_polygons, name='get_polygons'),
    path('save_images/',save_images, name='save_images'),
    path('fetch-weather-data/', save_weather_data, name='save_weather_data'),
    path('',login_view,name="login"),
    path('update/',update_view,name="update"),
    path('changepassword/',change_password,name="changepassword"),
    path('logout/',user_logout,name="logout"),
    path('polygon/<str:polygon_id>/',polygon_details, name='polygon_details'),
]


