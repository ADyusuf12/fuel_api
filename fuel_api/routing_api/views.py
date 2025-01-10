from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from .models import FuelPrice
import requests
from opencage.geocoder import OpenCageGeocode
import pandas as pd
import os

def decode_polyline(encoded):
    import polyline
    return polyline.decode(encoded)

def load_fuel_prices():
    fuel_prices_path = os.path.join(settings.BASE_DIR, 'static/data/fuel-prices-for-be-assessment-updated.csv')
    fuel_prices = pd.read_csv(fuel_prices_path)
    fuel_prices['Retail Price'] = pd.to_numeric(fuel_prices['Retail Price'], errors='coerce')
    fuel_prices_dict = {}
    for _, row in fuel_prices.iterrows():
        location = (row['Latitude'], row['Longitude'])
        price = row['Retail Price']
        fuel_prices_dict[location] = price
    return fuel_prices_dict

class RouteView(View):
    def get(self, request):
        start_location = request.GET.get('start_location')
        finish_location = request.GET.get('finish_location')
        start_coords = self.get_coordinates(start_location)
        finish_coords = self.get_coordinates(finish_location)
        if not start_coords or not finish_coords:
            return JsonResponse({'error': 'Invalid start or finish location'}, status=400)
        route = self.get_route(start_coords, finish_coords)
        if 'error' in route:
            return JsonResponse({'error': route['error']}, status=400)
        fuel_stops = self.get_fuel_stops(route)
        total_cost = self.calculate_total_cost(fuel_stops)
        map_url = self.generate_map_url(start_coords, finish_coords, fuel_stops)
        return JsonResponse({
            'route': route,
            'fuel_stops': fuel_stops,
            'total_cost': total_cost,
            'map_url': map_url
        })

    def get_coordinates(self, location):
        # Check cache/database first
        cached_coords = FuelPrice.objects.filter(location=location).first()
        if cached_coords:
            return cached_coords.latitude, cached_coords.longitude
        
        # Fallback to API call if not in cache
        geocoder = OpenCageGeocode(settings.OPENCAGE_API_KEY)
        result = geocoder.geocode(location)
        if result and len(result):
            lat, lng = result[0]['geometry']['lat'], result[0]['geometry']['lng']
            # Cache the results in the database
            FuelPrice.objects.create(location=location, latitude=lat, longitude=lng, price=None)  # Assuming price can be updated later
            return lat, lng
        return None, None

    def get_route(self, start_coords, finish_coords):
        response = requests.get(
            'https://api.geoapify.com/v1/routing',
            params={
                'waypoints': f"{start_coords[0]},{start_coords[1]}|{finish_coords[0]},{finish_coords[1]}",
                'mode': 'drive',
                'apiKey': settings.GEOAPIFY_API_KEY
            }
        )
        
        # Print the raw response content for debugging
        print("Raw route response content:", response.content)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return {'error': 'Failed to get route from Geoapify'}
        
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError as e:
            print("JSONDecodeError:", e)
            return {'error': 'Failed to decode JSON response from Geoapify'}
        
        # Print the entire response for debugging
        print("Route response data:", data)

        # Check for errors in the response
        if 'features' not in data or len(data['features']) == 0:
            return {'error': 'Routes not found'}
        return data['features'][0]

    def get_fuel_stops(self, route):
        try:
            coordinates = route['geometry']['coordinates']
        except KeyError as e:
            print("KeyError:", e)
            return {'error': 'Error decoding route geometry'}

        # Print the coordinates structure for debugging
        print("Coordinates structure:", coordinates)

        fuel_prices = load_fuel_prices()
        fuel_stops = []
        total_distance = 0

        for i in range(0, len(coordinates), 50):
            # Correctly unpack coordinates
            if len(coordinates[i]) >= 2:
                lng, lat = coordinates[i][:2]
                if isinstance(lat, list):
                    lat = lat[0]
                if isinstance(lng, list):
                    lng = lng[0]
                location = (lat, lng)
                
                # Ensure that closest_location calculation is correct
                closest_location = min(
                    fuel_prices.keys(),
                    key=lambda loc: ((loc[0] - lat) ** 2 + (loc[1] - lng) ** 2)
                )
                price = fuel_prices[closest_location]
                fuel_stops.append({
                    'location': f"{lat},{lng}",
                    'price': price
                })
            
            total_distance += 500
            if total_distance >= 500:
                break

        # Print the fuel stops for debugging
        print("Fuel stops:", fuel_stops)
        
        return fuel_stops

    def calculate_total_cost(self, fuel_stops):
        total_cost = 0
        for stop in fuel_stops:
            print("Processing stop:", stop)  # Debugging statement
            if isinstance(stop, dict) and 'price' in stop:
                price = stop['price']
                if isinstance(price, str):
                    try:
                        price = float(price)
                    except ValueError:
                        continue
                total_cost += price * (500 / 10)
            else:
                print("Invalid stop structure:", stop)  # Debugging statement
        return total_cost

    def generate_map_url(self, start_coords, finish_coords, fuel_stops):
        base_url = 'https://www.openstreetmap.org/directions?'
        start = f"{start_coords[0]},{start_coords[1]}"
        end = f"{finish_coords[0]},{finish_coords[1]}"
        
        # Correctly format waypoints for OpenStreetMap
        if fuel_stops and isinstance(fuel_stops[0], dict) and 'location' in fuel_stops[0]:
            waypoints = ';'.join([stop['location'] for stop in fuel_stops])
            map_url = f"{base_url}engine=mapquest_car&route={start};{waypoints};{end}"
        else:
            waypoints = 'None'
            map_url = f"{base_url}engine=mapquest_car&route={start};{end}"
        
        # Print the waypoints for debugging
        print(f"Start: {start}, Waypoints: {waypoints}, End: {end}")
        
        return map_url
