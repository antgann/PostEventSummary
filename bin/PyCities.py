'''
Created on Jul 31, 2019

@author: jjbun
'''
import math

class PyCities(object):

    def __init__(self, city_file):
        self.cities = {}
        
        city_file_list = [city_file]
        
        for f in city_file_list:
            print ('PyCities: Reading', f)
            lines = open(f, encoding='utf-8').readlines()
            for line in lines:
                if "Category" in line:
                    continue
                try:
                    city, lat, lon, pop, category = line.strip().split(',')              
                    self.cities[city] = {'lat':float(lat), 'lon':float(lon), 'population':int(pop), 'category':category}
                except:
                    print ('Bad line', line)
                    continue
        

    def getCityList(self, lat, lon, depth, categories=["C", "B", "B", "A"], time_delta=0.0):
        # Returns the closest cities to the given lat, lon drawing from the provided categories
        # Return is zip of cities, distances, times to alert, and compass bearings
        # For each city, calculates and returns the time to alert, based on Glenn's code in the old "getClosestCityInfo"
        nearest_cities = []
        distances = []

        for _ in categories:
            nearest_cities.append(None)
            distances.append(1.0e6)

        for city, values in self.cities.items():
            index = 0
            for category, nearest_city, distance in zip(categories, nearest_cities, distances):
                if category == values['category']:
                    dist_to_city = self.distanceBetween(lat, lon, values['lat'], values['lon'])
                    if dist_to_city < distance:
                        # exclude if already in the list at a previous index
                        exclude = False
                        for i in range(index):
                            if categories[i] == category and nearest_cities[i] == city:
                                exclude = True
                                break
                        if not exclude:
                            nearest_cities[index] = city
                            distances[index] = dist_to_city
                    
                index += 1                
        
        # calculate time to alert for each selected city
        ## Hadley/Kanamori Model of P and S wave velocities with depth
        ## fairly constant ration of P/S of about 1.73
        ps_ratio = 1.73
        s_near_source = 3.55
        ## Now use the P/S ratio and the near source S wave velocity to
        ## calculate the near source P wave velocity
        p_near_source = ps_ratio * s_near_source
        
        cities = {}
        
        for category, nearest_city, distance in zip(categories, nearest_cities, distances):
            slant_dist      = math.sqrt(depth**2 + distance**2)  # Slant Distance
            #p_tt            = slant_dist/p_near_source                # P-wave TT
            s_tt            = slant_dist/s_near_source                # S-wave TT
            city_time_delta = max((s_tt - time_delta), 0) # either 0 or the s_wave alert time 
            
            city_lat = self.cities[nearest_city]['lat']
            city_lon = self.cities[nearest_city]['lon']
            
            initial_bearing = self.calculate_initial_compass_bearing( (city_lat,city_lon), (lat,lon) )
            compass_bearing = self.get_compass_direction(initial_bearing)
            
            cities[nearest_city] = {'lat': city_lat, 'lon': city_lon, 'category': category, 'distance': distance, 'time': city_time_delta, 'bearing': compass_bearing}
       
            
            #print ('Category', category, 'Nearest', nearest_city, 'Distance', distance, 'km Time', city_time_delta, 'bearing', compass_bearing)            
            
        return cities
    

    def get_compass_direction(self, compass_bearing_degrees):
        #print("compass_bearing_degrees: " + str(compass_bearing_degrees))
        bearings = ["NE", "E", "SE", "S", "SW", "W", "NW", "N"]
        
        index = compass_bearing_degrees - 22.5
        if index < 0:
            index += 360
        index = int(index / 45)
        
        return bearings[index]
    
    def calculate_initial_compass_bearing(self, pointA, pointB):
        """
        Calculates the bearing between two points.
        The formulae used is the following:
            θ = atan2(sin(Δlong).cos(lat2),
                      cos(lat1).sin(lat2) − sin(lat1).cos(lat2).cos(Δlong))
        :Parameters:
          - `pointA: The tuple representing the latitude/longitude for the
            first point. Latitude and longitude must be in decimal degrees
          - `pointB: The tuple representing the latitude/longitude for the
            second point. Latitude and longitude must be in decimal degrees
        :Returns:
          The bearing in degrees
        :Returns Type:
          float
        """
        if (type(pointA) != tuple) or (type(pointB) != tuple):
          raise TypeError("Only tuples are supported as arguments")
        
        lat1     = math.radians(pointA[0])
        lat2     = math.radians(pointB[0])
        
        diffLong = math.radians(pointB[1] - pointA[1])
        
        x        = math.sin(diffLong) * math.cos(lat2)
        y        = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diffLong))
        
        initial_bearing = math.atan2(x, y)
        
        # Now we have the initial bearing but math.atan2 return values
        # from -180° to + 180° which is not what we want for a compass bearing
        # The solution is to normalize the initial bearing as shown below
        initial_bearing = math.degrees(initial_bearing)
        compass_bearing = (initial_bearing + 360) % 360
        
        return compass_bearing

    
    def distanceBetween(self, lat1, lon1, lat2, lon2):
        # Results in kilometers.
        EARTH_RADIUS = 6371.009        
        """Haversine distance formula for inputs in degrees"""
        lat1 = math.radians(lat1)
        lat2 = math.radians(lat2)
        lon1 = math.radians(lon1)
        lon2 = math.radians(lon2)
        delta_lat = lat1 - lat2
        delta_lon = lon1 - lon2
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1) * math.cos(lat2) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return EARTH_RADIUS * c
