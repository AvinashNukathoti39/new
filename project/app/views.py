from django.shortcuts import render,redirect,get_object_or_404
from django.http import JsonResponse,HttpResponse
from .models import *
import tempfile
import json
from shapely.geometry import Polygon
import uuid
import datetime
from datetime import date, timedelta,datetime
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import auth
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import *
from .forms import *
from django.shortcuts import render
import plotly.graph_objects as go
import plotly.express as px
from shapely.geometry import Polygon
import numpy as np
from PIL import Image
from django.views.decorators.csrf import csrf_exempt
import openeo
import requests
import scipy.signal
import pandas as pd
from django.core.files.base import ContentFile
from pyproj import Transformer
from io import BytesIO
import csv
import cdsapi
import netCDF4 as nc
import os
from dateutil.relativedelta import relativedelta
from django.db.models import Prefetch
 
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
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user
    customer = user.customer

    # Use prefetch_related to reduce the number of database queries
    polygons = PolygonModel.objects.filter(customer=customer).prefetch_related(
        Prefetch('sentinel_images', queryset=SENTINELImage.objects.filter(customer=customer)),
        Prefetch('landsat_images', queryset=LANDSATImage.objects.filter(customer=customer)),
        Prefetch('modis_images', queryset=MODISImage.objects.filter(customer=customer)),
    )

    polygon_images = []

    for polygon in polygons:
        polygon_images.append({
            'polygon': polygon,
            'images': {
                'sentinel': {
                    'ndvi': [img for img in polygon.sentinel_images.all() if img.ndvi_image],
                    'evi': [img for img in polygon.sentinel_images.all() if img.evi_image],
                    'ndwi': [img for img in polygon.sentinel_images.all() if img.ndwi_image],
                    'ndmi': [img for img in polygon.sentinel_images.all() if img.ndmi_image]
                },
                'landsat': {
                    'ndvi': [img for img in polygon.landsat_images.all() if img.ndvi_image],
                    'evi': [img for img in polygon.landsat_images.all() if img.evi_image],
                    'ndwi': [img for img in polygon.landsat_images.all() if img.ndwi_image],
                    'ndmi': [img for img in polygon.landsat_images.all() if img.ndmi_image]
                },
                'modis': {
                    'ndvi': [img for img in polygon.modis_images.all() if img.ndvi_image],
                    'evi': [img for img in polygon.modis_images.all() if img.evi_image],
                    'ndwi': [img for img in polygon.modis_images.all() if img.ndwi_image],
                    'ndmi': [img for img in polygon.modis_images.all() if img.ndmi_image]
                }
            }
        })

    return render(request, 'ndvi.html', {'polygon_images': polygon_images})



@csrf_exempt
@login_required
def save_polygon(request):
    if request.method == 'POST':
        try:
            user = request.user
            customer, _ = Customer.objects.get_or_create(user=user)
            data = json.loads(request.body)
            coordinates = data.get('coordinates', [])

            # Generate polygon identifier like "area 1", "area 2", etc.
            existing_polygons_count = PolygonModel.objects.filter(customer=customer).count()
            polygon_id = f"area {existing_polygons_count + 1}"

            polygon_geom = Polygon([(coord['longitude'], coord['latitude']) for coord in coordinates])
            area_sq_meters = polygon_geom.area
            area_acres = area_sq_meters / 4046.86

            polygon = PolygonModel.objects.create(polygon_id=polygon_id, customer=customer, properties=json.dumps(coordinates), area_in_acres=area_acres)

            for coord in coordinates:
                PointModel.objects.create(polygon=polygon, longitude=coord['longitude'], latitude=coord['latitude'])
            start_date = datetime(2022, 1, 1)
            end_date = datetime.now()

            # Connect to the Copernicus API
            connection = openeo.connect(url="openeo.dataspace.copernicus.eu")
            connection.authenticate_oidc()

            # Define the fields for which you want to calculate the indices.
            fields = {
                "type": "Polygon",
                "coordinates": [[(coord['longitude'], coord['latitude']) for coord in coordinates]]
            }

            # Load the bands from the SENTINEL2_L2A collection for the desired time window.
            s2cube = connection.load_collection(
                "SENTINEL2_L2A",
                temporal_extent=[start_date, end_date],
                bands=["B02", "B03", "B04", "B08", "B11", "SCL"],
            )

            # Calculate NDVI from the red and NIR bands.
            red = s2cube.band("B04")
            nir = s2cube.band("B08")
            ndvi = (nir - red) / (nir + red)

            # Calculate NDMI from the NIR and SWIR bands.
            swir = s2cube.band("B11")
            ndmi = (nir - swir) / (nir + swir)

            # Calculate EVI from the red, NIR, and blue bands.
            blue = s2cube.band("B02")
            evi = 2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))

            # Calculate NDWI from the NIR and green bands.
            green = s2cube.band("B03")
            ndwi = (green - nir) / (green + nir)

            # Apply cloud masking
            scl = s2cube.band("SCL")
            mask = ~((scl == 4) | (scl == 5))
            g = scipy.signal.windows.gaussian(11, std=1.6)
            kernel = np.outer(g, g)
            kernel = kernel / kernel.sum()

            # Morphological dilation of mask: convolution + threshold
            mask = mask.apply_kernel(kernel)
            mask = mask > 0.1
            ndvi_masked = ndvi.mask(mask)
            ndmi_masked = ndmi.mask(mask)
            evi_masked = evi.mask(mask)
            ndwi_masked = ndwi.mask(mask)

            # Aggregate Spatially
            timeseries_masked_ndvi = ndvi_masked.aggregate_spatial(geometries=fields, reducer="mean")
            timeseries_masked_ndmi = ndmi_masked.aggregate_spatial(geometries=fields, reducer="mean")
            timeseries_masked_evi = evi_masked.aggregate_spatial(geometries=fields, reducer="mean")
            timeseries_masked_ndwi = ndwi_masked.aggregate_spatial(geometries=fields, reducer="mean")

            # Apply timeseries smoothing using the Savitzky-Golay filter.
            udf = openeo.UDF(
                code="""
                #!python
                from scipy.signal import savgol_filter
                from openeo.udf import XarrayDataCube
                
                def apply_datacube(cube: XarrayDataCube, context: dict) -> XarrayDataCube:
                    array = cube.get_array()
                    filled = array.interpolate_na(dim='t')
                    smoothed_array = savgol_filter(filled.values, 5, 2, axis=0)
                    return XarrayDataCube(smoothed_array)
                """,
                runtime="Python"
            )
            ndvi_smoothed = ndvi_masked.apply_dimension(code=udf, dimension="t")
            ndmi_smoothed = ndmi_masked.apply_dimension(code=udf, dimension="t")
            evi_smoothed = evi_masked.apply_dimension(code=udf, dimension="t")
            ndwi_smoothed = ndwi_masked.apply_dimension(code=udf, dimension="t")
            timeseries_smoothed_ndvi = ndvi_smoothed.aggregate_spatial(geometries=fields, reducer="mean")
            timeseries_smoothed_ndmi = ndmi_smoothed.aggregate_spatial(geometries=fields, reducer="mean")
            timeseries_smoothed_evi = evi_smoothed.aggregate_spatial(geometries=fields, reducer="mean")
            timeseries_smoothed_ndwi = ndwi_smoothed.aggregate_spatial(geometries=fields, reducer="mean")
            job_ndvi = timeseries_masked_ndvi.execute_batch(out_format="CSV", title="Masked NDVI timeseries")
            job_ndmi = timeseries_masked_ndmi.execute_batch(out_format="CSV", title="Masked NDMI timeseries")
            job_evi = timeseries_masked_evi.execute_batch(out_format="CSV", title="Masked EVI timeseries")
            job_ndwi = timeseries_masked_ndwi.execute_batch(out_format="CSV", title="Masked NDWI timeseries")

            # Create temporary files
            temp_file_ndvi = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            temp_file_ndmi = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            temp_file_evi = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            temp_file_ndwi = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            
            # Download the results to the temporary files
            job_ndvi.get_results().download_file(temp_file_ndvi.name)
            job_ndmi.get_results().download_file(temp_file_ndmi.name)
            job_evi.get_results().download_file(temp_file_evi.name)
            job_ndwi.get_results().download_file(temp_file_ndwi.name)

            # Open the temporary files and load the data
            def process_csv(temp_file, polygon, customer):
                with open(temp_file.name, 'r') as file:
                    data = pd.read_csv(file)
                    data.interpolate(method='linear', inplace=True)
                    data['date'] = pd.to_datetime(data['date'])
                    data['year'] = data['date'].dt.year
                    data['month'] = data['date'].dt.month

                    grouped_data = data.groupby(['year', 'month']).apply(lambda x: x.loc[x['avg(band_0)'].idxmax()]).reset_index(drop=True)

                    return grouped_data

            ndvi_data = process_csv(temp_file_ndvi, polygon, customer)
            ndmi_data = process_csv(temp_file_ndmi, polygon, customer)
            evi_data = process_csv(temp_file_evi, polygon, customer)
            ndwi_data = process_csv(temp_file_ndwi, polygon, customer)

            # Merge dataframes on date to consolidate values into one model
            merged_data = ndvi_data[['date', 'avg(band_0)']].rename(columns={'avg(band_0)': 'ndvi_value'})
            merged_data = merged_data.merge(ndmi_data[['date', 'avg(band_0)']].rename(columns={'avg(band_0)': 'ndmi_value'}), on='date', how='outer')
            merged_data = merged_data.merge(evi_data[['date', 'avg(band_0)']].rename(columns={'avg(band_0)': 'evi_value'}), on='date', how='outer')
            merged_data = merged_data.merge(ndwi_data[['date', 'avg(band_0)']].rename(columns={'avg(band_0)': 'ndwi_value'}), on='date', how='outer')

            # Create SENTINELDATASETValue instances
            for index, row in merged_data.iterrows():
                SENTINELDATASETValue.objects.create(
                    polygon=polygon,
                    date=row['date'],
                    ndvi_value=row['ndvi_value'],
                    ndmi_value=row['ndmi_value'],
                    evi_value=row['evi_value'],
                    ndwi_value=row['ndwi_value'],
                    customer=customer
                )

            # Create dataframe for plotting
            df = pd.DataFrame(list(SENTINELDATASETValue.objects.filter(polygon=polygon).values('date', 'ndvi_value', 'ndmi_value', 'evi_value', 'ndwi_value')))
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            def create_plot(df, title, y_label):
                return px.line(
                    df,
                    x=df.index,
                    y=df.columns,
                    title=title,
                    labels={'value': y_label},
                    template='plotly_dark'
                )

            fig_ndvi = create_plot(df[['ndvi_value']], f'NDVI by Date for Polygon {polygon_id}', 'NDVI')
            fig_ndmi = create_plot(df[['ndmi_value']], f'NDMI by Date for Polygon {polygon_id}', 'NDMI')
            fig_evi = create_plot(df[['evi_value']], f'EVI by Date for Polygon {polygon_id}', 'EVI')
            fig_ndwi = create_plot(df[['ndwi_value']], f'NDWI by Date for Polygon {polygon_id}', 'NDWI')

            graph_json_ndvi = fig_ndvi.to_json()
            graph_json_ndmi = fig_ndmi.to_json()
            graph_json_evi = fig_evi.to_json()
            graph_json_ndwi = fig_ndwi.to_json()

            response_data = {
                'status': 'success',
                'graph_json': {
                    'ndvi': graph_json_ndvi,
                    'ndmi': graph_json_ndmi,
                    'evi': graph_json_evi,
                    'ndwi': graph_json_ndwi
                },
                'polygon_id': polygon.polygon_id,
            }

            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        

        

@login_required
def get_user_polygons(request):
    user = request.user
    customer = Customer.objects.get(user=user)
    polygons = PolygonModel.objects.filter(customer=customer)
    data = []

    for polygon in polygons:
        coordinates = json.loads(polygon.properties)
        
        sentinel_values = SENTINELDATASETValue.objects.filter(polygon=polygon).order_by('date')
        
        dates = [value.date for value in sentinel_values]
        ndvi_scores = [value.ndvi_value for value in sentinel_values]
        ndmi_scores = [value.ndmi_value for value in sentinel_values]
        evi_scores = [value.evi_value for value in sentinel_values]
        ndwi_scores = [value.ndwi_value for value in sentinel_values]

        data.append({
            'coordinates': coordinates,
            'values': {
                'dates': dates,
                'ndvi_scores': ndvi_scores,
                'ndmi_scores': ndmi_scores,
                'evi_scores': evi_scores,
                'ndwi_scores': ndwi_scores,
            }
        })

    return JsonResponse({'polygons': data})






def save_images(request):
    user = request.user
    customer = Customer.objects.get(user=user)
    polygons = PolygonModel.objects.filter(customer=customer)

    # Base URL for the WMS service
    copernicus_base_url = "https://sh.dataspace.copernicus.eu/ogc/wms/851a9497-78ef-41e3-8990-9ede3d9c1b61"

    # Set up the transformer from EPSG:4326 to EPSG:3857
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857")

    layers = ['NDVI', 'NDMI', 'EVI', 'NDWI']
    image_fields = {
        'NDVI': 'ndvi_image',
        'NDMI': 'ndmi_image',
        'EVI': 'evi_image',
        'NDWI': 'ndwi_image'
    }

    for polygon in polygons:
        coordinates = json.loads(polygon.properties)
        lons = [coord['longitude'] for coord in coordinates]
        lats = [coord['latitude'] for coord in coordinates]
        min_lon, min_lat = transformer.transform(min(lats), min(lons))
        max_lon, max_lat = transformer.transform(max(lats), max(lons))

        BBOX = ','.join([str(min_lon), str(min_lat), str(max_lon), str(max_lat)])

        end_date = datetime.now() - timedelta(days=1)

        # Iterate over the past 6 years, one image per year on the same day
        for year_delta in range(1, 7):
            date_to_check = end_date - relativedelta(years=year_delta)

            for layer in layers:
                params = {
                    'SERVICE': 'WMS',
                    'VERSION': '1.3.0',
                    'REQUEST': 'GetMap',
                    'FORMAT': 'image/png',
                    'TRANSPARENT': 'true',
                    'LAYERS': layer,
                    'exceptions': 'application/vnd.ogc.se_inimage',
                    'CRS': 'EPSG:3857',
                    'TIME': date_to_check.strftime('%Y-%m-%d'),
                    'WIDTH': 2048,
                    'HEIGHT': 2048,
                    'BBOX': BBOX
                }
                response = requests.get(copernicus_base_url, params=params)
                image = Image.open(BytesIO(response.content))
                image_array = np.array(image)

                if not is_blank_image(image_array):
                    defaults = {image_fields[layer]: ContentFile(response.content, name=f"{layer.lower()}_{date_to_check.strftime('%Y%m%d')}.png")}
                    SENTINELImage.objects.update_or_create(
                        polygon=polygon,
                        date=date_to_check,
                        customer=customer,
                        defaults=defaults
                    )

        # Ensure only the latest 6 images are saved for each type
        for layer in layers:
            image_field = image_fields[layer]
            saved_images = SENTINELImage.objects.filter(polygon=polygon, customer=customer, **{f'{image_field}__isnull': False}).order_by('-date')
            if saved_images.count() > 6:
                for image in saved_images[6:]:
                    getattr(image, image_field).delete()
                    image.delete()

    return HttpResponse('Images saved successfully.')

def is_blank_image(image_array, std_dev_threshold=0.0):
    # Check if the standard deviation of the pixel values is below the threshold
    if np.std(image_array) <= std_dev_threshold:
        return True
    # Additional check: if the image has only one unique color
    unique_colors = np.unique(image_array.reshape(-1, image_array.shape[2]), axis=0)
    if len(unique_colors) == 1:
        return True
    # Additional check: if the image histogram is flat (indicating uniform color)
    hist = np.histogram(image_array, bins=256)[0]
    if np.max(hist) == np.sum(hist):
        return True
    return False



@login_required
def download_csv(request, value_type):
    polygon_id = request.GET.get('polygon_id')
    if not polygon_id:
        return HttpResponse("Polygon ID is required.", status=400)

    customer = request.user.customer
    try:
        polygon = PolygonModel.objects.get(customer=customer, polygon_id=polygon_id)
    except PolygonModel.DoesNotExist:
        return HttpResponse("Polygon not found.", status=404)

    value_fieldnames = {
        'ndvi': 'NDVI Value',
        'ndmi': 'NDMI Value',
        'evi': 'EVI Value',
        'ndwi': 'NDWI Value'
    }
    
    if value_type not in value_fieldnames:
        return HttpResponse("Invalid value_type. Must be one of 'ndvi', 'ndmi', 'evi', 'ndwi'.")

    value_fieldname = value_fieldnames[value_type]
    filename = f"{request.user.username}_{value_type}_values.csv"
    fieldnames = ['Polygon ID', 'Date', value_fieldname]

    values = SENTINELDATASETValue.objects.filter(polygon=polygon)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.DictWriter(response, fieldnames=fieldnames)
    writer.writeheader()
    for value in values:
        writer.writerow({
            'Polygon ID': polygon.polygon_id, 
            'Date': value.date, 
            value_fieldname: getattr(value, f'{value_type}_value')
        })
    
    return response

@login_required
def get_polygons(request):
    customer = request.user.customer
    polygons = PolygonModel.objects.filter(customer=customer)
    polygon_list = [{'name': polygon.polygon_id} for polygon in polygons]  # Modify to include only the 'name' property
    return JsonResponse(polygon_list, safe=False)



def save_weather_data(request):
    user = request.user
    customer = Customer.objects.get(user=user)
    polygons = PolygonModel.objects.filter(customer=customer)

    for polygon in polygons:
        coordinates = json.loads(polygon.properties)
        lons = [coord['longitude'] for coord in coordinates]
        lats = [coord['latitude'] for coord in coordinates]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        fetch_weather_data(polygon, min_lon, min_lat, max_lon, max_lat)

    return HttpResponse('Weather data saved successfully.')

def fetch_weather_data(polygon, min_lon, min_lat, max_lon, max_lat):
    c = cdsapi.Client()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    response = c.retrieve(
        'reanalysis-era5-single-levels',
        {
            'variable': ['2m_temperature', '2m_dewpoint_temperature', 'total_precipitation'],
            'area': [max_lat, min_lon, min_lat, max_lon],  # North, West, South, East
            'product_type': 'reanalysis',
            'date': f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}",
            'time': [
                '00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00', '07:00', '08:00', '09:00', '10:00', '11:00',
                '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00', '23:00',
            ],
            'format': 'netcdf'
        }
    )

    with tempfile.NamedTemporaryFile(suffix='.nc', delete=False) as tmp_file:
        response.download(tmp_file.name)
        tmp_file.close()

        # Extract data from the NetCDF file
        dataset = nc.Dataset(tmp_file.name)

        temperature = dataset.variables['t2m'][:]  # Temperature data
        dewpoint = dataset.variables['d2m'][:]  # Dewpoint temperature data
        precipitation = dataset.variables['tp'][:]  # Precipitation data
        times = dataset.variables['time'][:]  # Time data

        # Convert temperature from Kelvin to Celsius
        temperature_celsius = temperature - 273.15

        # Calculate relative humidity from temperature and dewpoint temperature
        humidity = 100 * (np.exp((17.625 * (dewpoint - 273.15)) / (243.04 + (dewpoint - 273.15))) / 
                          np.exp((17.625 * temperature_celsius) / (243.04 + temperature_celsius)))
        
        
        # Convert precipitation from meters to millimeters
        precipitation_mm = precipitation * 1000

        # Convert time units to datetime
        time_unit = dataset.variables['time'].units
        time_base_str = time_unit.split('since ')[1].split('.')[0]  # Extract the base time and ignore the fraction of a second
        time_base = datetime.strptime(time_base_str, '%Y-%m-%d %H:%M:%S')
        dates = [time_base + timedelta(hours=int(time)) for time in times]

        # Iterate over each time step and save data
        for i, date in enumerate(dates):
            MetrologicalData.objects.create(
                polygon=polygon,
                customer=polygon.customer,
                temperature_data=float(temperature_celsius[i]),
                humidity_data=float(humidity[i]),
                rainfall_data=float(precipitation_mm[i]),
                date=date
            )

        dataset.close()

    # Clean up the temporary file
    os.remove(tmp_file.name)

    return HttpResponse('Weather data saved successfully.')



@login_required
def update_view(request):
    customer=Customer.objects.get(user=request.user)
    if request.method=='POST':
        form=UpdateForm(request.POST,instance=customer)
        if form.is_valid():
            form.save()
            return redirect('ndvi')
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





def polygon_details(request, polygon_id):
    polygon = get_object_or_404(PolygonModel, polygon_id=polygon_id)
    sentinel_values = SENTINELDATASETValue.objects.filter(polygon=polygon).order_by('date')
    metrological_data = MetrologicalData.objects.filter(polygon=polygon)
    
    context = {
        'polygon': polygon,
        'sentinel_values': sentinel_values,
        'metrological_data': metrological_data
    }
    
    return render(request, 'data.html', context)