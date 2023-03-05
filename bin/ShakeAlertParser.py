import os
import json
import geojson
from typing import Any, Dict, List, NamedTuple, Optional, Union
import pytz
import EQCalculations
from PyCities import *
from configparser import ConfigParser
from datetime import datetime
from utils import get_intensity_color


BASE_DIR = os.path.dirname(os.path.dirname(__file__))

global config

config = ConfigParser()
config.read(os.path.join(BASE_DIR, 'params/PostEventSummaryProperties.cfg'))

# Mag where map where MMIAlert will be used as minimum MMI in place of MMISmall
MagMapChange =     float(config.get("THRESHOLDS",'MagMapChange'))

'''
mmi to show if available mmi>=MMItoUse.  e.g. if MMItoUse=4, use 4 if mmi goes up to 7, say.
For smaller events, we show the felt contour, THRESHOLDS::MMISmall.
Larger than MagMapChange, use THRESHOLDS::MMI
'''
MMISmall     = int(float(config.get("THRESHOLDS",'MMISmall')))  # on initial map
MMItoUse     = int(float(config.get("THRESHOLDS",'MMIAlert')))


def utc_to_local(utc_Obj):
    """
    :param utc_Obj:  UTC datetime Object
    :return: datetime Object in US/Pacific local time.
    :rtype: datetime Object
    """
    pac_tz = pytz.timezone('US/Pacific')
    pacific_Obj = utc_Obj.replace(tzinfo=pytz.utc).astimezone(pac_tz)

    return pacific_Obj


def ParseJSONStr(jsonStr):
    data = json.loads(jsonStr)
    ShakeAlertValues = ParseJSONContent(data)
    return finalizeShakeAlertValues(ShakeAlertValues)


def ParseJSONFile(JSONfile):
    with open(JSONfile) as f:
        data = json.load(f)
    ShakeAlertValues = ParseJSONContent(data)
    return finalizeShakeAlertValues(ShakeAlertValues)


def finalizeShakeAlertValues(ShakeAlertValues, isJSON=True):
    if isJSON is True:  # input is JSON
        ShakeAlertValues["isJSON"] = isJSON
        if ShakeAlertValues.get("ANSSorig_time"):
            ANSStimeObj = datetime.strptime(
                ShakeAlertValues.get("ANSSorig_time"),
                "%Y-%m-%dT%H:%M:%S.%f"
            )  # retain msec,
            ANSStimeUTC = ANSStimeObj.strftime("%Y-%m-%d %H:%M:%S.%f (UTC)")  # original

            ShakeAlertValues["ANSStimeObj"] = ANSStimeObj  # time object with ANSS origin time in it
            ShakeAlertValues["ANSSorig_time"] = ANSStimeUTC  # better to hand around the time object

        '''
        If ANSS origin and update time exist. Create and populate
        ANSStimetoorigin key with calculated time to origin.
        '''
        if(ShakeAlertValues.get("ANSSorig_time") and
                ShakeAlertValues.get("ANSSupdate_time")):
            ShakeAlertValues["ANSStimetoorigin"] = EQCalculations.getTimeDelta(
                ShakeAlertValues.get('ANSSupdate_time'),
                ShakeAlertValues.get('ANSSorig_time')
            )

        # ShakeAlert initial alert timestamp. This is the "sent" time of initial alert.
        SA_inittimeObj = datetime.strptime(
            ShakeAlertValues.get("initial_timestamp"),
            "%Y-%m-%dT%H:%M:%S.%f"
        )  # retain msec,
        SA_inittimeString = SA_inittimeObj.strftime("%Y-%m-%d %H:%M:%S.%f (UTC)")  # string format time of SA alert
        ShakeAlertValues['SA_inittimeObj'] = SA_inittimeObj
        ShakeAlertValues['SA_inittimeString'] = SA_inittimeString

        '''
        If ANSSorig_time exists, create the ShakeAlertValues (key, val) pairs:
            t_ANSSotime_SAalert_init: ANSS origin to inital ShakeAlert as a
                                      timedelta object.
            t_ANSSotime_SAalert_initString: ANSS origin to inital ShakeAlert
                                            as a formatted timedelta str.
            t_ANSSotime_SAalert_peakM: ANSS origin to max M ShakeAlert
                                       as a timedelta object.
            t_ANSSotime_SAalert_peakMString: ANSS origin to max M ShakeAlert
                                             as a formatted timedelta str.
            t_ANSSotime_SAalert_final: ANSS origin to final ShakeAlert
                                       as a timedelta object.
            t_ANSSotime_SAalert_finalString: ANSS origin to inital ShakeAlert
                                             as a formatted timedelta str.
        '''
        if ShakeAlertValues.get('ANSSorig_time'):
            ShakeAlertValues["t_ANSSotime_SAalert_init"] = EQCalculations.getTimeDelta(
                ShakeAlertValues.get('initial_timestamp'),
                ShakeAlertValues.get('ANSSorig_time'))
            ShakeAlertValues["t_ANSSotime_SAalert_initString"] = str(
                round(
                    float(ShakeAlertValues.get("t_ANSSotime_SAalert_init")),
                    ndigits=1
                )
            )

            ShakeAlertValues["t_ANSSotime_SAalert_peakM"] = EQCalculations.getTimeDelta(
                ShakeAlertValues.get('peak_mag_timestamp'),
                ShakeAlertValues.get('ANSSorig_time')
            )
            ShakeAlertValues["t_ANSSotime_SAalert_peakMString"] = str(
                round(
                    float(ShakeAlertValues.get("t_ANSSotime_SAalert_peakM")),
                    ndigits=1
                )
            )

            ShakeAlertValues["t_ANSSotime_SAalert_final"] = EQCalculations.getTimeDelta(
                ShakeAlertValues.get('timestamp'),
                ShakeAlertValues.get('ANSSorig_time')
            )
            ShakeAlertValues["t_ANSSotime_SAalert_finalString"] = str(
                round(
                    float(ShakeAlertValues.get("t_ANSSotime_SAalert_final")),
                    ndigits=1
                )
            )

    if ShakeAlertValues.get('ANSSorig_time'):
        ShakeAlertValues["sWaveRadius"] = EQCalculations.getSWaveRadius(
            ShakeAlertValues.get('initial_timestamp'),
            ShakeAlertValues.get('ANSSorig_time')
        )

    ANSSlat             =       ShakeAlertValues.get("ANSSlat")
    ANSSlon             =       ShakeAlertValues.get("ANSSlon")
    ANSSdepth           =       ShakeAlertValues.get("ANSSdepth")
    SALat_final         = float(ShakeAlertValues.get("lat"))    # secretly final SA lat, lon
    SALon_final         = float(ShakeAlertValues.get("lon"))
    SALat_peakM         = float(ShakeAlertValues.get("peak_mag_lat"))    #
    SALon_peakM         = float(ShakeAlertValues.get("peak_mag_lon"))
    SALat_init          = float(ShakeAlertValues.get("initial_lat"))
    SALon_init          = float(ShakeAlertValues.get("initial_lon"))
    SADepth             = float(ShakeAlertValues.get("depth"))     # initial vs. final depth seems not tracked (!)

    if ANSSlat and ANSSlon:

        initialAlertDistance = EQCalculations.getDistance(
            (ANSSlat, ANSSlon),
            (SALat_init, SALon_init)
        )
        ShakeAlertValues["initialAlertDistance"] = str(round(initialAlertDistance, 1))
        peakMAlertDistance = EQCalculations.getDistance(
            (ANSSlat, ANSSlon),
            (SALat_peakM, SALon_peakM)
        )
        ShakeAlertValues["peakMAlertDistance"] = str(round(peakMAlertDistance, 1))
        finalAlertDistance = EQCalculations.getDistance(
            (ANSSlat, ANSSlon),
            (SALat_final, SALon_final)
        )
        ShakeAlertValues["finalAlertDistance"] = str(round(finalAlertDistance, 1))

        initialAzimuthError = EQCalculations.calculate_initial_compass_bearing(
            (ANSSlat, ANSSlon),
            (SALat_init,SALon_init)
        )
        ShakeAlertValues["initialCompassDirection"] = EQCalculations.get_compass_direction(initialAzimuthError)
        peakMAzimuthError = EQCalculations.calculate_initial_compass_bearing(
            (ANSSlat, ANSSlon),
            (SALat_peakM, SALon_peakM)
        )
        ShakeAlertValues["peakMCompassDirection"] = EQCalculations.get_compass_direction(peakMAzimuthError)
        finalAzimuthError = EQCalculations.calculate_initial_compass_bearing(
            (ANSSlat, ANSSlon),
            (SALat_final, SALon_final)
        )
        ShakeAlertValues["finalCompassDirection"] = EQCalculations.get_compass_direction(finalAzimuthError)
        ShakeAlertValues["initialAzimuthError"] = initialAzimuthError
        ShakeAlertValues["peakMAzimuthError"] = peakMAzimuthError
        ShakeAlertValues["finalAzimuthError"] = finalAzimuthError

    stationFilePath = os.path.join(BASE_DIR, config.get("GENERAL",'stationFile'))
    stationDict = EQCalculations.parseStationFile(stationFilePath)

    if ANSSlat and ANSSlon:
        numStationsIn10KM = EQCalculations.getNumStationsInRange(
            stationDict=stationDict,
            point=(ANSSlat, ANSSlon),
            distanceKM=10
        )
        numStationsIn100KM = EQCalculations.getNumStationsInRange(
            stationDict=stationDict,
            point=(ANSSlat, ANSSlon),
            distanceKM=100
        )
    else:
        numStationsIn10KM = EQCalculations.getNumStationsInRange(
            stationDict=stationDict,
            point=(SALat_init, SALon_init),
            distanceKM = 10
        )
        numStationsIn100KM = EQCalculations.getNumStationsInRange(
            stationDict=stationDict,
            point=(SALat_init, SALon_init),
            distanceKM=100
        )

    ShakeAlertValues["numStationsIn10KM"] = numStationsIn10KM
    ShakeAlertValues["numStationsIn100KM"] = numStationsIn100KM

    cityListPath = os.path.join(BASE_DIR, config.get("GENERAL",'cityList'))

    cities = PyCities(cityListPath)
    city_types_requested = ["C", "B", "B", "A"]

    if ANSSlat and ANSSlon and ShakeAlertValues.get("t_ANSSotime_SAalert_init"):
        lat, lon, depth, types, delta = float(ANSSlat), float(ANSSlon), float(ANSSdepth), city_types_requested, ShakeAlertValues.get("t_ANSSotime_SAalert_init")
    else:
        lat, lon, depth, types, delta = float(SALat_init), float(SALon_init), float(SADepth), city_types_requested, 0.0

    # We get the C,B,B,A list
    closest_cities = cities.getCityList(lat, lon, depth, types, delta)

    # If the first B is closer than the C, ask for B,B,B,A
    c_city = list(closest_cities.keys())[0]
    b_city = list(closest_cities.keys())[1]
    if closest_cities[c_city]['distance'] > closest_cities[b_city]['distance']:
        closest_cities = cities.getCityList(lat, lon, depth, ["B", "B", "B", "A"], delta)

    # Now we reorder the distances to be on the safe side
    # A quick bubble sort to order the cities
    # This is all a bit long-winded, and could probably be optimised :-)
    city_keys = list(closest_cities.keys())

    while True:
        swap = False
        for i in range(len(city_keys)-1):
            for j in range(i+1, len(city_keys)):
                if closest_cities[city_keys[i]]['distance'] > closest_cities[city_keys[j]]['distance']:
                    city_temp = city_keys[i]
                    city_keys[i] = city_keys[j]
                    city_keys[j] = city_temp
                    swap = True
                    break
            if swap:
                break
        if not swap:
            break

    # Make new dict for the reordered cities
    new_closest_cities = {}
    for city in city_keys:
        new_closest_cities[city] = closest_cities[city]
        print ('Closest city', closest_cities[city])

    closest_cities = new_closest_cities


    ShakeAlertValues["closestCities"] = closest_cities

    timeCreatedPST = utc_to_local(datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S (Pacific)")
    ShakeAlertValues["timeCreatedPST"]          = timeCreatedPST

    return ShakeAlertValues


class Coord(NamedTuple):
    """
    An immutable container representing a single map coordinate in
    decimal degrees.
    """
    lat: float
    lon: float

    def __eq__(self, other):
        return self.lat == other.lat and self.lon == other.lon

    def __ne__(self, other):
        return self.lat != other.lat or self.lon != other.lon


class GMContour():
    """
    Container class to hold the contents of a single ground motion contour
    object extracted from a single ShakeAlert.
    :param mmi: The Modified Mercalli Intensity estimate for the map region
        inside contour polygon.
    :type mmi: int
    :param polygon: The contour polygon as a list of coordinates.
    :type polygon: List[VertexCoord]
    :param pga: Peak ground acceleration estimate.
    :type pga: Optional[float]
    :param pgv: Peak ground velocity estimate.
    :type pgv: Optional[float]
    """
    def __init__(
        self,
        mmi: int,
        polygon: List[Coord],
        pga: Optional[float],
        pgv: Optional[float]
    ):
        self.mmi = mmi

        # Check for well-formed closed polygon coord list.
        if polygon[0] != polygon[-1]:
            raise ValueError(
                'Polygon coordinate list is not closed. '
                'First and last coordinate should be the '
                'same to ensure polygon closure.'
            )

        self.polygon = polygon
        self.pga = pga
        self.pgv = pgv

    def get_intensity_color(self):
        return get_intensity_color(self.mmi)

    def to_geojson_polygon(self) -> geojson.Polygon:
        """
        Builds a new geojson.Polygon from the current GMContour's
        coordinate list.
        :rtype: geojson.Polygon
        """
        '''
        Note: geojson.Polygon accepts a list of polygon coord
        lists of size 1 or 2.  A single polygon coordinate list defines a
        simple polygon (what we want for a contour polygon), while size 2
        defines a polygon region with a hole defined by the second polygon
        coord list.
        '''
        polygon = geojson.Polygon([
            [(float(coord.lon), float(coord.lat)) for coord in self.polygon]
        ])

        if not polygon.is_valid:
            raise ValueError('GeoJSON Polygon contains invalid data.')
        return polygon

    def __lt__(self, other):
        return self.mmi < other.mmi

    def __le__(self, other):
        return self.mmi <= other.mmi

    def __eq__(self, other):
        return self.mmi == other.mmi

    def __ne__(self, other):
        return self.mmi != other.mmi

    def __gt__(self, other):
        return self.mmi > other.mmi

    def __ge__(self, other):
        return self.mmi >= other.mmi

    def __str__(self) -> str:
        """
        Returns gm contour object as human readable string.
        Called by print() to display object to stdout.
        :rtype: str
        """
        return repr(self)

    def __repr__(self) -> str:
        """
        Returns a GM contour object as str.
        Used by built-in functions repr(), str.format(), etc.
        :rtype: str
        """
        cls_attrs_buf: str = '('
        for idx, attr_tpl in enumerate(self.__dict__.items()):
            cls_attrs_buf += f'{attr_tpl[0]}={attr_tpl[1]}'
            if idx != len(self.__dict__):
                cls_attrs_buf += ', '
        cls_attrs_buf += ')'
        return f'{self.__class__.__name__}{cls_attrs_buf}'


def parse_gm_contours(
        gm_contours: List[Dict[str, Union[int, float, str]]],
    ) -> List[GMContour]:
    """
    Extracts MMI and corresponding gm-contour polygons from JSON dump dict.
    Performs parsing of the polygon string that consists of whitespace
    separated lat,lon pairs.
    :param gm_contours: A dictionary containing gm-contour elements dumped
    from ShakeAlert event JSON input.
    :type gm_contours: list[dict[str, Union[int, float, str]]]
    :return: A new list of GMContour objects.
    :rtype: list[GMContour]
    """
    contours: List[GMContour]  = []
    for contour_json_d in gm_contours:
        # Get MMI as integer by truncation.
        mmi: int = int(str(contour_json_d['mmi'])[:1])
        pga: float = contour_json_d['pga']
        pgv: float = contour_json_d['pgv']
        parsed_poly: List[tuple[float, float]] = []

        # Get the raw polygon str to be parsed ie. "lat0,lon0 lat1,lon1..."
        raw_polygon: str = contour_json_d.get('polygon')

        # Split into a list of "lat,lon" tokens
        coord_tokens: List[str] = raw_polygon.strip().split(' ')

        # Create (lat, lon) tuples from comma-delimited strings
        for coord_tok in coord_tokens:
            parsed_poly.append(Coord(*coord_tok.split(',')))

        '''
        Create a GMContour (from json data) and store it in our new
        dictionary using it's MMI as the key.
        '''
        contours.append(
            GMContour(
                mmi=mmi,
                polygon=parsed_poly,
                pga=pga,
                pgv=pgv
            )
        )
    return contours


def Get_polygons(
        gm_contours: List[Dict[str, Union[int, float, str]]],
        debug: bool = True
    ):
    """
    Extracts MMI and corresponding polygon values
    :param gm_contours: The list of gm_contour dicts parsed from JSON input
    :type gm_contours: list[dict[str, Any]]
    :return: List of lists, each element is [MMIval, polygon, [lat[], lon[]]]
                returns both polygon as string(?) and numerical values
                returns all MMI levels; no filter on MMItoUse
    :rtype: list.  Bizarrely, the mmi is the first output term
    """

    allMMIpolys = []
    for contour in gm_contours:
        # type(contour) -> dict[str, int|float|str]
        MMI    = contour.get('mmi')
        MMIval = str(MMI)[:1]   # why truncate?  so the int cast later will work

        polystr   = contour.get('polygon')          # get method returns "None" if not there.  polystr is a string

        allMMIpolys.append([int(MMIval), polystr])
        if debug:
            print("polystr: %s" % polystr)

    allMMIpolys = sorted(allMMIpolys, key=lambda x: x[0], reverse=True)
    return allMMIpolys


def ParseJSONContent(JSONdata) -> Dict[str, Any]:
    '''
    Parses an Event JSON structure provided by ARC's REST API.
    '''
    opt_v = True

    # Init the output json dictionary with values set to None.
    JSONValues = dict.fromkeys([
        "mag",  # Final alert mag.
        "depth",
        "lat",
        "lon",
        "orig_time",
        "timestamp",
        "anss_id",
        "polygon",
        "MMIlist",
        "polygonList",  # Final alert polygon list.
        "initial_mag",
        "initial_lat",
        "initial_lon",
        "initial_timestamp",
        "initial_polygonList",
        "peak_mag",  # Peak mag alert mag value.
        "peak_mag_depth",  # Peak mag alert depth.
        "peak_mag_lat",  # Peak mag alert lat.
        "peak_mag_lon",  # Peak mag alert lon.
        "peak_mag_timestamp",
        "peak_mag_polygonList",  # Peak mag alert polygon list.
        "review_announcement",
        "wea_report",
    ], None)
    parsed_json = JSONdata

    '''
    Get messages from shakealert_event_messages list. Sort by SA message
    version number to avoid issues if message list ordering found in JSON
    input changes later.
    '''
    initial_message = None
    final_message = None
    if parsed_json.get('shakealert_event_messages'):
        sorted_sa_messages = sorted(
            parsed_json.get('shakealert_event_messages'),
            key=lambda msg: int(msg.get('version'))
        )
        initial_message = sorted_sa_messages[0]
        final_message = sorted_sa_messages[-1]
    peak_mag_message = parsed_json.get('peak_mag_sa_message')

    if opt_v:
        print("FIRST MESSAGE: " + initial_message.get('version'))
        print("LAST MESSAGE: "  + final_message.get('version'))


    JSONValues['mag']                  = str(final_message.get('mag'))
    JSONValues['depth']                = str(final_message.get('depth'))
    JSONValues['lat']                  = str(final_message.get('lat'))
    JSONValues['lon']                  = str(final_message.get('lon'))
    JSONValues['num_stations']         = str(final_message.get('num_stations'))
    JSONValues['orig_time']            =     final_message.get('origin_time')                 # retains milliseconds now
    JSONValues['timestamp']            =     final_message.get('timestamp')

    if parsed_json.get('event_id'):
        JSONValues['anss_id']           =     parsed_json.get('event_id')  # ID obtained from ShakeAlert2PDL by ARC.
    else:
        '''
        Create an ANSS from the final SA core_info ID if SA2PDL ID
        is not found (for cases when SA2PDL ANSS Origin message is not
        received by ARC).
        '''
        JSONValues['anss_id'] = f'ew {final_message.get("message_id")}'

    JSONValues['initial_mag']          = str(initial_message.get('mag'))
    JSONValues['initial_lat']          = str(initial_message.get('lat'))
    JSONValues['initial_lon']          = str(initial_message.get('lon'))
    JSONValues['initial_num_stations'] = str(initial_message.get('num_stations'))
    JSONValues['initial_orig_time']    =     initial_message.get('origin_time')                 # Not okay to truncate.
    JSONValues['initial_timestamp']    =     initial_message.get('timestamp')

    JSONValues['peak_mag']             = str(peak_mag_message.get('mag'))
    JSONValues['peak_mag_depth']       = str(peak_mag_message.get('depth'))
    JSONValues['peak_mag_lat']         = str(peak_mag_message.get('lat'))
    JSONValues['peak_mag_lon']         = str(peak_mag_message.get('lon'))
    JSONValues['peak_mag_num_stations'] = str(peak_mag_message.get('num_stations'))
    JSONValues['peak_mag_timestamp']   = str(peak_mag_message.get('timestamp'))

    if parsed_json.get('review_text'):
        JSONValues['review_announcement'] = parsed_json.get('review_text')

    if parsed_json.get('wea_report'):
        JSONValues['wea_report'] = parsed_json.get('wea_report')
        if opt_v:
            print("WEA: " + JSONValues['wea_report'])

    # If ANSS data is available in ARC event json.
    if parsed_json.get('preferred_origin'):
        JSONValues["ANSSlat"] = parsed_json.get('preferred_origin').get('latitude')
        JSONValues["ANSSlon"] = parsed_json.get('preferred_origin').get('longitude')
        JSONValues["ANSSdepth"] = parsed_json.get('preferred_origin').get('depth')
        JSONValues["ANSSmag"] = str(parsed_json.get('preferred_origin').get('magnitude'))
        JSONValues["ANSSorig_time"] = str(parsed_json.get('preferred_origin').get('event_time'))  # Not okay to truncate
        JSONValues["ANSSupdate_time"] = parsed_json.get('preferred_origin').get('update_time')  # minutes to hours after event
    else:
        JSONValues["ANSSlat"] = None
        JSONValues["ANSSlon"] = None
        JSONValues["ANSSdepth"] = None
        JSONValues["ANSSmag"] = None
        JSONValues["ANSSorig_time"] = None
        JSONValues["ANSSupdate_time"] = None

    # Determine map mmi label based on ANSS mag. If no ANSS mag use init ShakeAlert mag.
    global MMItoUse
    if(JSONValues.get("ANSSmag") and float(JSONValues["ANSSmag"]) < MagMapChange):
        MMItoUse = MMISmall
    elif float(JSONValues.get('initial_mag')) < MagMapChange:
        MMItoUse = MMISmall

    # read all initial alert polygons and corresponding MMI levels
    initialGMcontours = initial_message.get('ground_motion_contours')
    if initialGMcontours is not None:

        MMIlist             = Get_polygons(initialGMcontours, opt_v)

        mmi_initial  = {}
        for m in MMIlist:
            mmi_initial[m[0]] = m[1]            # hash, key = mmi, value = poly as string

        # find one contour for initial map;
        mmis = mmi_initial.keys()
        if int(MMItoUse) in mmi_initial:        # alert boundary at MMI 4 for M>=MagMapChange
            MMItoShow = int(MMItoUse)
        else:
            MMItoShow = min(mmis)      # should be MMI 2

        print("MMItoShow %d" % MMItoShow)

        initial_polygonNumericList = latlon_list_to_numeric(mmi_initial[MMItoShow].split(), 1)   # return lat, lon float pairs

        latlon_list                = latlon_string_to_list(mmi_initial[MMItoShow], 0)        # return lat, lon string pairs

        initial_polygonList = []
        initial_polygonList.append([MMItoShow, latlon_list])    # polygon packaged for later Javascript.

        JSONValues['MMIlist']                    = MMIlist
        JSONValues['initial_polygonList']        = initial_polygonList            # list [[mmi, str(lat1,lon1)], [mmi, str(lat2, lon2], ...]
        JSONValues['initial_polygonNumericList'] = initial_polygonNumericList     # [ [lon1, lat1], [lon2, lat2] ...] floats
        JSONValues['initial_contours'] = parse_gm_contours(initialGMcontours)


    finalGMcontours = final_message.get('ground_motion_contours')
    if finalGMcontours is not None:

        print('fetch final GM contours')
        fMMIlist                 = Get_polygons(finalGMcontours, opt_v)

        min_mmi = MMItoUse    # smallest MMI contour to show for final alert

        final_polygonList           = []
        final_polygonNumericList    = []

        mmi_final  = {}
        for m in fMMIlist:
            mmi_final[m[0]] = m[1]            # hash, key = mmi, value = poly as string

            if m[0] >= min_mmi:
                use_this_polygon_string = m[1]
                use_this_MMI = m[0]
                print("Adding %s" % use_this_MMI)

                latlon_list                = latlon_string_to_list(use_this_polygon_string, 0)        # return lat, lon string pairs

                tmp_lonlat_list          = latlon_list_to_numeric(use_this_polygon_string.split(), 1)

                final_polygonList.append([ use_this_MMI, [latlon_list]])    # prepend MMI; list ref is wrapper for Javascript
                final_polygonNumericList.append( tmp_lonlat_list)             # no preprend MMI, lon, lat


        JSONValues['fMMIlist']             = fMMIlist    # maybe not needed
                                           # list all MMI's [[numeric_mmi1, str(full_poly1_for_that_MMI],[mmi2, strpoly2]...
        JSONValues['polygonList']          = final_polygonList
                                           # list [[mmi, str(lat1,lon1)], [mmi, str(lat2, lon2], ...]
        JSONValues['polygonNumericList']   = final_polygonNumericList
                                           # [[lon1, lat1], [lon2, lat2] ...] floats in lon,lat order
        JSONValues['final_contours'] = parse_gm_contours(finalGMcontours)
    # end finalGMcontours block

    # start peak mag gm contours block
    peak_mag_gm_contours = peak_mag_message.get('ground_motion_contours')
    if peak_mag_gm_contours is not None:

        print('fetch peak mag GM contours')
        pMMIlist                 = Get_polygons(peak_mag_gm_contours, opt_v)

        min_mmi = MMItoUse    # smallest MMI contour to show for peak alert

        peak_mag_polygonList           = []
        peak_mag_polygonNumericList    = []

        mmi_final  = {}
        for m in pMMIlist:
            mmi_final[m[0]] = m[1]            # hash, key = mmi, value = poly as string

            if m[0] >= min_mmi:
                use_this_polygon_string = m[1]
                use_this_MMI = m[0]
                print("Adding in max %s" % use_this_MMI)

                latlon_list                = latlon_string_to_list(use_this_polygon_string, 0)        # return lat, lon string pairs

                tmp_lonlat_list          = latlon_list_to_numeric(use_this_polygon_string.split(), 1)

                peak_mag_polygonList.append([ use_this_MMI, [latlon_list]])    # prepend MMI; list ref is wrapper for Javascript
                peak_mag_polygonNumericList.append( tmp_lonlat_list)             # no preprend MMI, lon, lat


        JSONValues['pMMIlist'] = pMMIlist  # list all MMI's [[numeric_mmi1, str(full_poly1_for_that_MMI],[mmi2, strpoly2]...
        JSONValues['peak_mag_polygonList'] = peak_mag_polygonList  # list [[mmi, str(lat1,lon1)], [mmi, str(lat2, lon2], ...]
        JSONValues['peak_mag_polygonNumericList'] = peak_mag_polygonNumericList  # [[lon1, lat1], [lon2, lat2] ...] floats in lon,lat order

        JSONValues['peak_contours'] = parse_gm_contours(peak_mag_gm_contours)

    # end peak mag gm contours block

    return JSONValues


def latlon_list_to_numeric(latlon_list, rev):
    """
    :param latlon_list: input a list of strings, each a "lat,lon" pair;
    :param rev:  flag to reverse input order; e.g. from lat,lon to lon,lat
    :return: NumericList, a list of float lon, lat pairs
    :rtype: list.
    """
    NumericList = []
    for k in latlon_list:
        la, lo = k.split(",")
        if rev:
            NumericList.append([float(lo), float(la)])      #lon, lat pairs
        else:
            NumericList.append([float(la), float(lo)])      #lon, lat pairs
    return NumericList


def latlon_string_to_list(latlon_list_string, rev):
    """
    :param latlon_list in a string: string of "lat,lon" pairs
    :param rev:  flag to reverse input order; e.g. from lat,lon to lon,lat
    :return:  a list of float lat, lon pairs
    :rtype: list.
    """
    foo = []
    for k in latlon_list_string.split():
        la, lo = k.split(",")
        if rev:
            kk = [ float(lo), float(la) ]
        else:
            kk = [ float(la), float(lo) ]
        foo.append(kk)
    return foo
