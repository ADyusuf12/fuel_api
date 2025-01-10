import pandas as pd
from dotenv import load_dotenv
import os
import requests

# Load environment variables from .env file
load_dotenv()

# Get Geoapify API key from environment variables
geoapify_api_key = os.getenv('GEOAPIFY_API_KEY')

# Load the CSV file
fuel_prices_path = 'static/data/fuel-prices-for-be-assessment.csv'
fuel_prices = pd.read_csv(fuel_prices_path)

# Function to get coordinates using Geoapify
def get_coordinates(address):
    url = f"https://api.geoapify.com/v1/geocode/search?text={address}&apiKey={geoapify_api_key}"
    response = requests.get(url)
    data = response.json()
    if data['features']:
        lat = data['features'][0]['geometry']['coordinates'][1]
        lng = data['features'][0]['geometry']['coordinates'][0]
        return lat, lng
    return None, None

# Add latitude and longitude columns
fuel_prices['Latitude'] = fuel_prices['Address'].apply(lambda x: get_coordinates(x)[0])
fuel_prices['Longitude'] = fuel_prices['Address'].apply(lambda x: get_coordinates(x)[1])

# Save the updated CSV file
fuel_prices.to_csv('static/data/fuel-prices-for-be-assessment-updated.csv', index=False)
