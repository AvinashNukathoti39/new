import schedule
import time
import requests
 
def fetch_and_store_data():
    url = "http://localhost:8000/save_images/"
   
    # Make an HTTP GET request to the store_data view
    response = requests.get(url)
    print(f"HTTP GET to {url} - Status Code: {response.status_code}")
 
# Schedule the task to run every 6 hours
schedule.every(1).minutes.do(fetch_and_store_data)
 
while True:
    schedule.run_pending()
    time.sleep(1)