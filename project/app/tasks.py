from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.core.files.base import ContentFile
from django.http import HttpResponse
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO
import numpy as np
import requests
import json
from pyproj import Transformer
import scipy.signal
from .models import Customer, PolygonModel, NDVIImage
from .models import PolygonModel, NDVIValue,NDMIValue
import openeo
import json
import pandas as pd
from datetime import datetime
import tempfile


@shared_task
def save_images_task():
    customers = Customer.objects.all()
    for customer in customers:
        polygons = PolygonModel.objects.filter(customer=customer)

        base_url = "https://sh.dataspace.copernicus.eu/ogc/wms/42198960-5491-4d3e-bcf0-a7d415745f0f"
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857")

        for polygon in polygons:
            coordinates = json.loads(polygon.properties)
            lons = [coord['longitude'] for coord in coordinates]
            lats = [coord['latitude'] for coord in coordinates]
            min_lon, min_lat = transformer.transform(min(lats), min(lons))
            max_lon, max_lat = transformer.transform(max(lats), max(lons))

            BBOX = ','.join([str(min_lon), str(min_lat), str(max_lon), str(max_lat)])

            end_date = datetime.now()
            start_date = end_date

            saved_images = 0
            while saved_images < 8:
                params = {
                    'SERVICE': 'WMS',
                    'VERSION': '1.3.0',
                    'REQUEST': 'GetMap',
                    'FORMAT': 'image/png',
                    'TRANSPARENT': 'true',
                    'LAYERS': 'NDVI',
                    'exceptions': 'application/vnd.ogc.se_inimage',
                    'CRS': 'EPSG:3857',
                    'TIME': f"{start_date.strftime('%Y-%m-%d')}/{(start_date + timedelta(days=7)).strftime('%Y-%m-%d')}",
                    'WIDTH': 2048,
                    'HEIGHT': 2048,
                    'BBOX': BBOX
                }
                response = requests.get(base_url, params=params)
                image = Image.open(BytesIO(response.content))
                image_array = np.array(image)

                if not is_blank_image(image_array):
                    NDVIImage.objects.update_or_create(
                        polygon=polygon,
                        date=start_date,
                        customer=customer,
                        defaults={'image': ContentFile(response.content, name=f"image_{start_date.strftime('%Y%m%d')}.png")}
                    )
                    saved_images += 1
                    start_date -= timedelta(days=7)
                else:
                    start_date -= timedelta(days=1)

            saved_images = NDVIImage.objects.filter(polygon=polygon, customer=customer).order_by('-date')
            if saved_images.count() > 8:
                for image in saved_images[8:]:
                    image.delete()

    return HttpResponse('Images saved successfully.')

def is_blank_image(image_array, std_dev_threshold=0.0):
    if np.std(image_array) <= std_dev_threshold:
        return True
    unique_colors = np.unique(image_array.reshape(-1, image_array.shape[2]), axis=0)
    if len(unique_colors) == 1:
        return True
    hist = np.histogram(image_array, bins=256)[0]
    if np.max(hist) == np.sum(hist):
        return True
    return False


@shared_task
def update_ndvi_values(request):
    customers = Customer.objects.all()
    end_date = datetime.now()
    start_date = end_date - timedelta(weeks=3)

    for customer in customers:
        polygons = PolygonModel.objects.all()
        
        for polygon in polygons:
            coordinates = json.loads(polygon.properties)
            fields = {
                "type": "Polygon",
                "coordinates": [[(coord['longitude'], coord['latitude']) for coord in coordinates]]
            }

        connection = openeo.connect(url="openeo.dataspace.copernicus.eu")
        connection.authenticate_oidc()

        # Load the "B04" (red) and "B08" (NIR) bands from the SENTINEL2_L2A collection for the desired time window.
        s2cube = connection.load_collection(
                "SENTINEL2_L2A",
                temporal_extent=[start_date, end_date],
                bands=["B04", "B08", "SCL"],
            )

            # Calculate NDVI from the red and NIR bands.
        red = s2cube.band("B04")
        nir = s2cube.band("B08")
        ndvi = (nir - red) / (nir + red)

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

        # Aggregate Spatially
        timeseries_masked = ndvi_masked.aggregate_spatial(geometries=fields, reducer="mean")

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
        timeseries_smoothed = ndvi_smoothed.aggregate_spatial(geometries=fields, reducer="mean")
        job = timeseries_smoothed.execute_batch(out_format="CSV", title="Masked NDVI timeseries")

        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        
        # Download the results to the temporary file
        job.get_results().download_file(temp_file.name)

        # Open the temporary file and load the data
        with open(temp_file.name, 'r') as file:
            data = pd.read_csv(file)
            data.interpolate(method='linear', inplace=True)
            data['date'] = pd.to_datetime(data['date'])
            data['year'] = data['date'].dt.year
            data['month'] = data['date'].dt.month

            # Group by year and month and get the maximum value
            grouped = data.groupby(['year', 'month'])['avg(band_0)'].max().reset_index()
            grouped.fillna(0, inplace=True)

            # Create a new 'date' column
            grouped['date'] = pd.to_datetime(grouped[['year', 'month']].assign(day=1))

            for index, row in grouped.iterrows():
                # Create a new NDVIValue instance and save it to the database
                NDVIValue.objects.create(
                    polygon=polygon,
                    date=row['date'],
                    value=row['avg(band_0)'],
                    customer=customer
                )
            # Load the “B04” (red) and “B08” (NIR) bands from the SENTINEL2_L2A collection for the desired time window.
        s2cube = connection.load_collection(
            "SENTINEL2_L2A",
            temporal_extent=[start_date, end_date],
            bands=["B08", "B11", "SCL"],
        )

        # Calculate NDVI from the red and NIR bands.
        nir = s2cube.band("B08")
        swir = s2cube.band("B11")
        ndmi = (nir - swir) / (nir + swir)

        # Apply cloud masking
        scl = s2cube.band("SCL")
        mask = ~((scl == 4) | (scl == 5))
        g = scipy.signal.windows.gaussian(11, std=1.6)
        kernel = np.outer(g, g)
        kernel = kernel / kernel.sum()

        # Morphological dilation of mask: convolution + threshold
        mask = mask.apply_kernel(kernel)
        mask = mask > 0.1
        ndmi_masked = ndmi.mask(mask)

        # Aggregate Spatially
        timeseries_masked = ndmi_masked.aggregate_spatial(geometries=fields, reducer="mean")

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
        ndmi_smoothed = ndmi_masked.apply_dimension(code=udf, dimension="t")
        timeseries_smoothed = ndmi_smoothed.aggregate_spatial(geometries=fields, reducer="mean")
        job = timeseries_masked.execute_batch(out_format="CSV", title="Masked NDMI timeseries")
        
        # Create a temporary file for SMI
        temp_file_ndmi = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        
        # Download the results to the temporary file
        job.get_results().download_file(temp_file_ndmi.name)

        # Open the temporary file and load the data
        with open(temp_file_ndmi.name, 'r') as file:
            data_ndmi = pd.read_csv(file)
            data_ndmi.interpolate(method='linear', inplace=True)
            data_ndmi['date'] = pd.to_datetime(data_ndmi['date'])
            data_ndmi['year'] = data_ndmi['date'].dt.year
            data_ndmi['month'] = data_ndmi['date'].dt.month

            # Group by year and month and get the maximum value
            grouped_ndmi = data_ndmi.groupby(['year', 'month'])['avg(band_0)'].max().reset_index()
            grouped_ndmi.fillna(0, inplace=True)

            # Create a new 'date' column
            grouped_ndmi['date'] = pd.to_datetime(grouped_ndmi[['year', 'month']].assign(day=1))

            for index, row in grouped_ndmi.iterrows():
                # Create a new SMIValue instance and save it to the database
                NDMIValue.objects.create(
                    polygon=polygon,
                    date=row['date'],
                    value=row['avg(band_0)'],
                    customer=customer
                )

    return HttpResponse('values updated successfully.')