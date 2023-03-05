import os
import datetime
import math
from obspy import core
from collections import OrderedDict
from operator import itemgetter
from matplotlib import pyplot as plt


def round_half_up(num: float, precision: int = 0):
    """
    Rounds a float to the given precision using the "round half up" tie-breaking rule.
    :param num: The float value to be rounded.
    :param precision: The precision of the resulting value in numer of digits after
        the decimal eg. a num=2.3591 and precision=1 will return 2.4.
    """
    multiplier = 10 ** precision
    return math.floor(float(num) * multiplier + 0.5) / multiplier


def point_in_poly(x,y,poly):
# Determine if a point is inside a given polygon or not
# Polygon is a list of (x,y) pairs. This function
# returns True or False.  The algorithm is called
# the "Ray Casting Method".

# Does it matter what order the vertexes for the polygon are in?
# Yes - point order matters in a polygon. Points should be clockwise
#   and polygon holes are counterclockwise according to the spec.

    n = len(poly)
    inside = False

    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x,p1y = p2x,p2y

    return inside



def getClosestCityInfo(city_file, numCities, event_lat, event_lon, event_depth, time_delta):
  ## Hadley/Kanamori Model of P and S wave velocities with depth
  ## fairly constant ration of P/S of about 1.73
  ps_ratio = 1.73
  s_near_source = 3.55
  ## Now use the P/S ratio and the near source S wave velocity to
  ## calculate the near source P wave velocity
  p_near_source = ps_ratio * s_near_source

  cityInfo = []
  ## Make sure this file exists
  cities = []
  if os.path.isfile(city_file):
    with open(city_file, encoding='utf-8') as cin:
      cities = cin.readlines()
    cin.close()

  # Then read in the values of the city_map
  city_map = OrderedDict()
  for i in range(0, len(cities)):
    city_components = cities[i].split('=')
    if(len(city_components) >=2 ):
      city_name   = city_components[0]
      city_latlon = city_components[1].split()
      if (len(city_latlon) == 2):
        city_lat        = city_latlon[0]
        city_lon        = city_latlon[1]
        dist_km         = float('nan')  #default values
        dist_miles      = float('nan')
        city_time_delta = float('nan')
        slant_dist      = float('nan')
        p_tt            = float('nan')
        s_tt            = float('nan')
        s_p             = float('nan')
        city_info       = (dist_km, dist_miles, slant_dist, p_tt, s_tt, s_p, city_time_delta)
        city_map[(city_name, city_lat, city_lon)] = city_info

  # Calculate the distances for each city in the list
  for k, v in iter(city_map.items()):
    city_lat   = float(k[1])
    city_lon   = float(k[2])

    dist_miles      = getDistance((event_lat,event_lon),(city_lat,city_lon))
    dist_km         = getDistance((event_lat,event_lon),(city_lat,city_lon), miles=False)
    slant_dist      = math.sqrt(event_depth**2 + dist_km**2)  # Slant Distance
    p_tt            = slant_dist/p_near_source                # P-wave TT
    s_tt            = slant_dist/s_near_source                # S-wave TT
    s_p             = s_tt - p_tt                             # S-P (seconds)
    city_time_delta = max((s_tt - time_delta), 0) # either 0 or the s_wave alert time
    city_map[k]     = (dist_km, dist_miles, slant_dist, p_tt, s_tt, s_p, city_time_delta)

  # Now sort the city list by distance to the hypocenter
  city_map_sorted = OrderedDict(sorted(list(city_map.items()), key = itemgetter(1)))
  cityIter = 0
  for k, v in iter(city_map_sorted.items()):
    compassDirection = get_compass_direction(calculate_initial_compass_bearing((float(k[1]),float(k[2])),(event_lat,event_lon)))
    cityInfo = cityInfo + [{'cityLat': k[1], 'cityLon': k[2], 'cityName': k[0], 'cityDist': int(v[0]), 'compassDirection' : compassDirection, 'timeToAlert' : str(round(v[6],1))}]
    cityIter += 1
    if cityIter == numCities:
      return cityInfo    # look for some number of cities, and return a populated list of dicts
      break



def getDistance(pointA, pointB, miles=True):

  theta1     = math.radians(90.0 - pointA[0])
  theta2     = math.radians(90.0 - pointB[0])
  theta3     = math.radians(pointA[1] - pointB[1])
  term1      = math.cos(theta1) * math.cos(theta2)
  term2      = math.sin(theta1) * math.sin(theta2) * math.cos(theta3)

  dist_km    = math.acos(term1 + term2)*6371.0   # Distance in km
  dist_miles = dist_km/1.60934                # Distance in miles

  if miles:
    return dist_miles
  else:
    return dist_km

def getIntensityLevel(MMIlist, lat, lon, getRomanNum=False):
  # MMIlist contains polygons for each MMI value
  # This function returns the intensity at the given lat/lon by determining if the point
  # is within any of the polygons
  #  will return garbage if MMIlist is not in greatest to least intensity
  intensity       = None
  #point           = Point(float(lon), float(lat))           # Point in GeoJSON elsewhere is a lon, lat thing
  #newPolygonList  = []

  polygon = []
  for MMIval, polygon_coords in MMIlist:
    polygon = []
    for latlon in polygon_coords.split(' '):
        latp,lonp = latlon.split(',')
        polygon.append( (float(lonp), float(latp)) )

    """
    # Optional plotting of points and polygons as sanity check
    x = [x for x,y in polygon]
    y = [y for x,y in polygon]
    plt.scatter(x,y,color='g',marker='.',label='P')
    plt.scatter([float(lon)],[float(lat)],color='r',marker='.')
    plt.xlim(-124.0,-120.0)
    plt.ylim(37.0,39.0)
    plt.show()
    """

    if point_in_poly(float(lon), float(lat), polygon):
      if getRomanNum:
        return intensityRomanNumeral(MMIval)
      else:
        return MMIval

  if intensity is None:
      if getRomanNum:
        return "<II"
      else:
        return "1"    # GB freelance   MMI<2, numerically.

  print("intensity = " + intensity)
  return intensity

def intensityRomanNumeral(MMI):
  # fails silently if MMI input as a string
  foo = type(MMI)
  # print("MMI MMI MMI MMI  %d %s" % (MMI, foo))
  if MMI == 1: return "<II"
  if MMI == 2: return "II"
  if MMI == 3: return "III"
  if MMI == 4: return "IV"
  if MMI == 5: return "V"
  if MMI == 6: return "VI"
  if MMI == 7: return "VII"
  if MMI == 8: return "VIII"
  if MMI == 9: return "IX"
  if MMI == 10: return "X"

  return MMI

def intensityNumberString(MMI):
    mmi = int(MMI)
    if mmi > 1:
        num_string = "%d" % mmi
    else:
        num_string = "<2"
    return num_string



def getTimeDelta(alert_time, origin_time):
  if '.' not in alert_time:
      print("alert_time input was whole seconds: %s", alert_time)
      alert_time = alert_time  + ".000"
  if '.' not in origin_time:
      print("origin_time input was whole seconds: %s", origin_time)
      origin_time = origin_time  + ".000"

  #GB: no FMT = '%Y-%m-%dT%H:%M:%S'        found msec getting removed

  FMT1 = '%Y-%m-%dT%H:%M:%S.%f'         # better FMT  retain milliseconds
  FMT2 = '%Y-%m-%d %H:%M:%S.%f'         # retain milliseconds
  FMT3 = "%Y-%m-%d %H:%M:%S.%f (UTC)"   # disaster in time handling.
  if "UTC" in alert_time:
      atime = datetime.datetime.strptime(alert_time, FMT3)
  elif "T" in alert_time:
      atime = datetime.datetime.strptime(alert_time, FMT1)
  elif " " in alert_time:
      atime = datetime.datetime.strptime(alert_time, FMT2)
  else:
      print('time is an adisaster')
      print(alert_time)

  if "UTC" in origin_time:
      otime = datetime.datetime.strptime(origin_time, FMT3)
  elif "T" in origin_time:
      otime = datetime.datetime.strptime(origin_time, FMT1)
  elif " " in origin_time:
      otime = datetime.datetime.strptime(origin_time, FMT2)
  else:
      print('time is an odisaster')
      print(origin_time)

  # was  time_deltadt = datetime.datetime.strptime(alert_time, FMT) - datetime.datetime.strptime(origin_time, FMT) (whole seconds)
  time_deltadt = atime - otime
  time_delta = time_deltadt.total_seconds()  # this converts it to a float
  print("Time difference = %f" % time_delta)
  return time_delta

def getSWaveRadius(alert_time, origin_time):

  ## near source S wave velocity from Brad Aagard
  s_near_source = 3.55  # also in config file; reconcile

  time_delta = getTimeDelta(alert_time, origin_time)
  # Equitorial S-wave radius at alert time
  radius_s = s_near_source*time_delta
  print("Equitorial S-wave radius at alert time = " + str(radius_s) + " km")
  # Equitorial S-wave radius (ignoring event depth)
  # should there be a difference between the two?
  #  radius_s0 = s_near_source*time_delta
  return radius_s

def calculate_initial_compass_bearing(pointA, pointB):
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

def get_compass_direction(compass_bearing_degrees):
    print("compass_bearing_degrees: " + str(compass_bearing_degrees))
    bearings = ["NE", "E", "SE", "S", "SW", "W", "NW", "N"]

    index = compass_bearing_degrees - 22.5
    if index < 0:
        index += 360
    index = int(index / 45)

    return bearings[index]


def parseStationFile(stationFileLoc) -> dict:
  with open(stationFileLoc) as f:
    stationDict = {}
    for line in f:
      if ("#" not in line and line != '\n'):
        stationLine          = line.split()
        station              = stationLine[0] + stationLine[1]
        stationDict[station] = (float(stationLine[4]), float(stationLine[5]))
    return stationDict


def getNumStationsInRange(stationDict, point, distanceKM):
  numStations = 0
  for station in stationDict:
    if getDistance(point, stationDict[station], miles=False) <= distanceKM:
      numStations += 1
  return numStations
