from django.shortcuts import render,redirect
from django.http import JsonResponse
from .models import PointModel, PolygonModel, NDVIValue
import os
import json
from shapely.geometry import Polygon
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import uuid
from datetime import date, timedelta,datetime
from django.conf import settings
import calendar
# import plotly.graph_objs as go
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import auth
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import *
from .forms import * 
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
# import plotly.io as pio
from sentinelhub import SentinelHubRequest,SHConfig, SentinelHubDownloadClient, DataCollection, MimeType, CRS, BBox, Geometry
from django.http import JsonResponse
from shapely.geometry import Polygon
import numpy as np



def home(request):
    return render(request, 'base.html')


#register a user
def register(request):
    if request.method=="POST":
        first_name=request.POST.get('first_name')
        last_name=request.POST.get('last_name')
        email=request.POST.get('email')
        phone=request.POST.get('phone')
        username=request.POST.get('username')
        password=request.POST.get('password')
        user=User.objects.create_user(username=username,password=password,email=email,first_name=first_name,last_name=last_name)
        Customer.objects.create(user=user,first_name=first_name,last_name=last_name,email=email,phone=phone)
        return redirect('login')
        
    
    return render(request,'register.html')

# login a user
def login_view(request):
    form = LoginForm()
    if request.method =="POST":
        form = LoginForm(request,data=request.POST)
        if form.is_valid():
            username=request.POST.get('username')
            password=request.POST.get('password')
            
            user=authenticate(request,username=username,password=password)
            
            if user is not None:
                auth.login(request, user)
                return redirect('ndvi')
               
    context={"form":form} 
    return render(request,'login.html',context=context)


def ndvi(request):
    return render(request, "ndvi.html")


@login_required
@csrf_exempt
def save_polygon(request):
    config = SHConfig()
    config.sh_client_id = 'b3d8532a-6268-465c-b54b-49b77c99bb92'
    config.sh_client_secret = 'ZaExFGcvVYERIGgPTbmc9Qjcdxfsdb41'
    # import pdb
    # pdb.set_trace()
    if request.method == 'POST':
        user = request.user
        data = json.loads(request.body)
        coordinates = data.get('coordinates', [])
        polygon_id = str(uuid.uuid4())
        
        # Create Polygon object for calculating area
        polygon_geom = Polygon([(coord['latitude'], coord['longitude']) for coord in coordinates])
        
        # Calculate area in square meters
        area_sq_meters = polygon_geom.area
        
        # Convert square meters to acres (1 acre = 4046.86 square meters)
        area_acres = area_sq_meters / 4046.86

        # Create PolygonModel instance with properties data
        polygon = PolygonModel.objects.create(polygon_id=polygon_id,customer=user.customer, properties=json.dumps(coordinates), area_in_acres=area_acres)
        
        # Save PointModel instances
        for coord in coordinates:
            PointModel.objects.create(polygon=polygon, latitude=coord['latitude'], longitude=coord['longitude'])

        # Define geometry using Shapely Polygon
        geometry = Geometry(polygon_geom, CRS.WGS84)

        # Define the evalscript to calculate NDVI
        evalscript = """
             //VERSION=3
function setup() {
  return {
    input: [{
      bands: [
        "B04",
        "B08",
        "dataMask"
      ]
    }],
    output: [
      {
        id: "data",
        bands: 1,
        sampleType: "FLOAT32"  //FLOAT32 is used in process API to get floating NDVI values for statistics
      },
      {
        id: "dataMask",
        bands: 1
      }]
  }
}

function evaluatePixel(samples) {
    return {
        data: [index(samples.B08, samples.B04)],
        dataMask: [samples.dataMask]
        };
}
        """

        # Loop through each month from 2020 till current month
        start_date = datetime(2023, 1, 1)
        end_date = datetime.now()

        current_date = start_date
        while current_date <= end_date:
            # Define time interval for the current month
            start_month = current_date.replace(day=1)
            end_month = current_date.replace(day=calendar.monthrange(current_date.year, current_date.month)[1])

            # Define the Sentinel Hub request
            request = SentinelHubRequest(
                evalscript=evalscript,
                input_data=[
                    SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(start_month.strftime('%Y-%m-%d'), end_month.strftime('%Y-%m-%d')),
                        maxcc=0
                    )
                ],
                responses=[
                    SentinelHubRequest.output_response('default', MimeType.TIFF)
                ],
                geometry=geometry,
                resolution=(20, 20),
                config=config
            )

            # Execute the Sentinel Hub request
            ndvi_image = request.get_data()

            # Calculate the mean NDVI
            mean_ndvi = np.mean(ndvi_image)
            print(mean_ndvi)

            # Save NDVI value for the polygon
            NDVIValue.objects.create(polygon=polygon, date=start_month, value=mean_ndvi, customer=user.customer)

            # Move to the next month
            current_date = end_month + timedelta(days=1)

        return JsonResponse({'message': 'Polygon saved successfully.', 'area_acres': area_acres})
    else:
        return JsonResponse({'error': 'Invalid request method.'}, status=405)


@login_required
def update_view(request):
    customer=Customer.objects.get(user=request.user)
    if request.method=='POST':
        form=UpdateForm(request.POST,instance=customer)
        if form.is_valid():
            form.save()
            return redirect('map')
    else:
        form=UpdateForm(instance=customer)
        
    return render(request, 'update.html',{'form':form})




#password change
def change_password(request):
    if request.method == 'POST':
        form=PasswordChangeForm(user=request.user,data=request.POST)
        if form.is_valid():
            user=form.save()
            update_session_auth_hash(request,user)
            messages.success(request,'sucessfully updated')
            return redirect('login')
        else:
            messages.error(request,'failed to change the password')
    else:
        form=PasswordChangeForm(user=request.user)
        
    return render(request,'changepassword.html',{'form':form})  



#logout
def user_logout(request):
    auth.logout(request)
    return redirect("login")




