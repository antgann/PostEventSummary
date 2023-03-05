import argparse
import getopt, os, sys
import pathlib
from typing import Dict, List, Optional
from pathlib import Path
from configparser import ConfigParser

import geojson
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph  # Implements abstract class Flowable.
from reportlab.platypus import Table      # Implements abstract class Flowable.
from reportlab.platypus import TableStyle

import PyEventImage
import EQCalculations
import ShakeAlertParser
from ShakeAlertParser import GMContour, MagMapChange
from EQCalculations import round_half_up


BASE_DIR = Path(os.path.realpath(__file__)).parent.parent
config = ConfigParser()
config.read(os.path.join(BASE_DIR, 'params/PostEventSummaryProperties.cfg'))


def has_anss_origin_data(event_data):
    """
    Returns true if the event_data Dict has all of the following ANSS values:
        ANSSlat, ANSSlon, ANSSdepth, ANSSmag, ANSSupdate_time,
        ANSStimeObj, t_ANSSotime_SAalert_init, t_ANSSotime_SAalert_initString,
        t_ANSSotime_SAalert_final, t_ANSSotime_SAalert_finalString.
    """
    anss_keys = ['ANSSlat', 'ANSSlon', 'ANSSdepth', 'ANSSmag',
                 'ANSSupdate_time', 'ANSStimeObj', 't_ANSSotime_SAalert_init',
                 't_ANSSotime_SAalert_initString', 't_ANSSotime_SAalert_final',
                 't_ANSSotime_SAalert_finalString']
    for key in anss_keys:
        if not event_data.get(key):
            return False
    return True


def get_rounded_str(num, precision: int = 0):
    return str(round_half_up(num, precision))


def get_pprint_mag(mag):
    """
    Returns the given magnitude value as a 'pretty print' string
    that will be shown in the report PDF. Applies rounding defined
    by get_rounded_mag_str().
    :rtype: str
    """
    return 'M ' + str(round_half_up(mag, 1))


def km_to_mi(distance_km):
    """
    Convert distance value in km to mi.
    :rtype: float
    """
    return 0.621371 * float(distance_km)


class GMContourFilter():
    """
    Defines a filter object implementing GMContour filtering business logic
    based on event magnitude and contour MMI.
    """
    def __init__(
        self,
        mag_threshold: float,
        min_mmi_small_event: float,
        min_mmi_large_event: float
    ):
        self.mag_threshold = mag_threshold
        self.min_mmi_small_event = min_mmi_small_event
        self.min_mmi_large_event = min_mmi_large_event

    def meets_contour_criteria(
            self,
            gm_contour: GMContour,
            event_mag: float,
        ) -> bool:
        """
        Evaluates a GMContour object against the configured contour MMI limits.
        GMContours meet criteria if their MMI exceeds the min threshold for both
        large and small Magnitude events.  The mag value used to define a "large
        event" is also provided by a config value.
        :param gm_contour: The contour object to be evaluated.
        :type gm_contour: GMContour
        :return: True if the contour meets min criteria.
        :rtype: bool
        """
        if event_mag >= self.mag_threshold:
            return gm_contour.mmi >= self.min_mmi_large_event
        return gm_contour.mmi >= self.min_mmi_small_event

    def filter_gm_contours(
            self,
            gm_contours: List[GMContour],
            event_mag: float,
        ) -> List[GMContour]:
        """
        Filters a list of GMContour objects based on magnitude configuration params.
        Contour polygons will be excluded from the returned list if they do not
        meet the base magnitude or the min magnitude for large events.
        Both the base min mag and large event min mag threshold are defined
        via config file.
        :param gm_contours: The list of event ground motion contour objects to
            be evaluated. This list will not be modified.
        :type gm_contours: List[GMContour]
        :return: A new list containing the passing GMContour objects.
        :rtype: List[GMContour]
        """
        temp: List[GMContour] = []
        for contour in gm_contours:
            if self.meets_contour_criteria(contour, event_mag):
                temp.append(contour)
        return temp

    def __call__(
            self,
            gm_contours: List[GMContour],
            event_mag: float
        ) -> List[GMContour]:
        """
        Convenience method for filter_gm_contours when a GMContourFilter object
        is called directly.
        """
        return self.filter_gm_contours(gm_contours, event_mag)


def initializeFonts() -> None:
    calibriFile = os.path.join(BASE_DIR, "fonts/Calibri.ttf")
    calibriBoldFile = os.path.join(BASE_DIR, "fonts/CALIBRIB.TTF")
    calibriItalicFile = os.path.join(BASE_DIR, "fonts/CALIBRII.TTF")
    calibriBoldItalicFile = os.path.join(BASE_DIR, "fonts/CALIBRIZ.TTF")
    registerFont(TTFont("Calibri", calibriFile))
    registerFont(TTFont("CalibriB", calibriBoldFile))
    registerFont(TTFont("CalibriI", calibriItalicFile))
    registerFont(TTFont("CalibriZ", calibriBoldItalicFile))


def build_epicenter_feature(feature_id, lon, lat):
    """
    :param id: GeoJSON feature ID.
    :type id: str
    :param lon: Epicenter latitude in decimal degrees
    :type lon: float or str
    :param lat: Epicenter latitude in decimal degrees
    :type lat: float or str
    :return: Returns a new GeoJSON Feature object.
    :rtype: Feature
    """
    return geojson.Feature(
        id=feature_id,
        geometry=geojson.Point((float(lon), float(lat))),
        properties={
            "title": "Earthquake Epicenter",
            "icon": "epicenter"
        }
    )


def build_init_FeatureCollection(SAMessageValues, contours, to_jsi):
    """
    Creates a FeatureCollection object for the initial alert
    with parameterized feature IDs to aid with json structure migration.
    :param SAMessageValues: Data parsed from ARC json input.
    :type SAMessageValues: Dict
    :param contours: Initial ShakeAlert ground motion contours.
    :type contours: List[GMContour]
    :param to_jsi: Data used in leaflet.js maps (Alert Circles).
    :type to_jsi: Dict
    :return: Initial alert GeoJSON FeatureCollection.
    :rtype: geojson.FeatureCollection
    """
    initialEpicenterFeature = build_epicenter_feature(
        "Epicenter",
        SAMessageValues.get("ANSSlon"),
        SAMessageValues.get("ANSSlat")
    )

    init_poly_coords = [SAMessageValues.get('initial_polygonNumericList')]
    initialPolygon = geojson.Polygon(init_poly_coords)  # one poly

    initial_poly_names = [f'Initial MMI {gm_contour.mmi}' for gm_contour in contours]
    if len(initial_poly_names) > 0:
        polyname = initial_poly_names[0] # We assume only one is in this list
    else:
        print(
            'ERROR: Undefined init poly name. Dict value '
            'to_jsf["initialpolynames"] must be a list with len >= 1.'
        )

    initialPolygonFeature = geojson.Feature(
        id="Polygon",
        geometry=initialPolygon,
        properties={
            "name": polyname,
            "stroke": "blue",
            "fill": "transparent"
        }
    )

    alertCircleFeature = geojson.Feature(
        id='SAinitloc',
        geometry=geojson.Point(
            (
                float(SAMessageValues.get("initial_lon")),
                float(SAMessageValues.get("initial_lat"))
            )
        ),
        properties={
            'title': 'Initial SA Loc',
            "radius": 5000.0,  # 5 km
            "radiusunits": 'm',
            "circletime": 0.0,
            "tunits": 's',
            "color": '#000000',
            "fill-opacity": 1,
        }
    )

    FCi = [alertCircleFeature, initialEpicenterFeature, initialPolygonFeature]
    for k in to_jsi['alertcircles']:
        circleid     = k[0]
        cPoint       = geojson.Point((float(k[2]), float(k[1])))
        cradius      = k[3]
        cradiusunits = k[4]
        t            = k[5]
        tunits       = k[6]
        ccolor       = k[7]
        cfill        = k[8]
        cname        = k[9]

        if cfill == "transparent":
            cfill = 0.0
        else:
            cfill = 1.0

        if '\"' in ccolor:
            ccolor = ccolor.replace('\"','')

        caption = SAMessageValues.get("txt_caption1").replace("\n"," ")

        circleFeature = geojson.Feature(
            id=circleid,
            geometry=cPoint,
            properties={
                "name": cname,
                "radius": cradius,
                "radiusunits": cradiusunits,
                "circletime": t,
                "tunits": tunits,
                "color": ccolor,
                "fill-opacity": cfill
            }
        )
        FCi.append(circleFeature)

    return geojson.FeatureCollection(
        FCi,
        id="initialAlertCollection",
        properties={
            "elapsed": float(SAMessageValues.get("t_ANSSotime_SAalert_init")),
            "magnitude": round(float(SAMessageValues.get("initial_mag")), ndigits=1),
            "num_stations": int(SAMessageValues.get("initial_num_stations")),
            "location_azimuth_error": round(SAMessageValues.get("initialAzimuthError")),
            "location_distance_error": float(SAMessageValues.get("initialAlertDistance")),
            "caption": caption
        }
    )


def build_peak_mag_FeatureCollection(SAMessageValues, contours):
    maxMEpicenterFeature = build_epicenter_feature(
        "Epicenter",
        SAMessageValues.get("ANSSlon"),
        SAMessageValues.get("ANSSlat")
    )

    FC = [maxMEpicenterFeature]

    for idx, contour in enumerate(contours):
        polycolor = contour.get_intensity_color()
        polyname = f'MMI {contour.mmi}'
        polygon = contour.to_geojson_polygon()
        polygon_feature = geojson.Feature(
            id=f'poly_{idx}',
            geometry=polygon,
            properties={
                "name": polyname,
                "stroke": polycolor,
                "fill": "transparent"
            }
        )
        FC.append(polygon_feature)

    caption = SAMessageValues.get("txt_caption2").replace("\n"," ")

    return geojson.FeatureCollection(
        FC,
        id="maxMAlertCollection",
        properties={
            "elapsed": float(SAMessageValues.get("t_ANSSotime_SAalert_peakMString")),
            "magnitude": round(float(SAMessageValues.get("peak_mag")), ndigits=1),
            "num_stations": int(SAMessageValues.get("peak_mag_num_stations")),
            "location_azimuth_error": round(SAMessageValues.get("peakMAzimuthError")),
            "location_distance_error": float(SAMessageValues.get('peakMAlertDistance')),
            "caption": caption
        }
    )


def build_final_FeatureCollection(SAMessageValues, contours):
    finalEpicenterFeature = build_epicenter_feature(
        "Epicenter",
        SAMessageValues.get("ANSSlon"),
        SAMessageValues.get("ANSSlat")
    )

    FC = [finalEpicenterFeature]

    for idx, contour in enumerate(contours):
        polycolor = contour.get_intensity_color()
        polyname = f'MMI {contour.mmi}'
        polygon = contour.to_geojson_polygon()
        polygon_feature = geojson.Feature(
            id=f'poly_{idx}',
            geometry=polygon,
            properties={
                "name": polyname,
                "stroke": polycolor,
                "fill": "transparent"
            }
        )
        FC.append(polygon_feature)

    caption = SAMessageValues.get("txt_final_caption2").replace("\n"," ")

    return geojson.FeatureCollection(
        FC,
        id="finalAlertCollection",
        properties={
            "elapsed": float(SAMessageValues.get("t_ANSSotime_SAalert_final")),
            "magnitude": round(float(SAMessageValues.get("mag")), ndigits=1),
            "num_stations": int(SAMessageValues.get("num_stations")),
            "location_azimuth_error": round(SAMessageValues.get("finalAzimuthError")),
            "location_distance_error": float(SAMessageValues.get("finalAlertDistance")),
            "caption": caption
        }
    )


def export_to_geojson(to_jsi: Dict, json_indent: Optional[int] = None) -> str:
    """
    Builds Post ShakeAlert Summary GeoJSON output.
    TODO: Refactoring needed: SAMessageValues dict should be passed
        into this function as a function param. Alert circle data from to_jsi
        should be unified with the rest of the data contained in
        the SAMessageValues struct.
    :param to_jsi: Dict containing alert circle data used in alert time map.
    :param json_indent: Sets json pretty print indentation to an integer
        number of spaces.  Set to None to disable pretty printing.
    :type json_indent: Optional[int]
    :return: The summary GeoJSON string.
    :rtype: str
    """

    # Create a new dictionary that will define our GeoJSON data structure.
    geojson_struct = {}

    geojson_struct["type"] = "USGSEarlyWarningSummary"
    geojson_struct["version"] = "1.0"

    ANSStimeObj = SAMessageValues.get("ANSStimeObj")  # GB added
    anss_orig_timeZuluFmt = ANSStimeObj.strftime("%Y-%m-%d %H:%M:%S.%fZ")   # Z keeps browser from mis-interpreting
    anss_epicenter_point = geojson.Point(
        (float(SAMessageValues.get("ANSSlon")), float(SAMessageValues.get("ANSSlat")))
    )

    geojson_struct["properties"] = {
        "id": SAMessageValues.get('anss_id'),
        "time": anss_orig_timeZuluFmt,
        "elapsed": SAMessageValues.get('ANSStimetoorigin'),
        "epicenter": anss_epicenter_point,
        "depth": float(SAMessageValues.get("ANSSdepth")),
        "magnitude": round_half_up(float(SAMessageValues.get("ANSSmag")), precision=1),
        "title": SAMessageValues.get('title'),
        "num_stations_10km": SAMessageValues.get("numStationsIn10KM"),
        "num_stations_100km": SAMessageValues.get("numStationsIn100KM"),
        "created": SAMessageValues.get('timeCreatedPST'),
        "announcement": SAMessageValues.get('review_announcement'),
        "wea_report": SAMessageValues.get('wea_report')
    }

    closest_cities = SAMessageValues.get("closestCities")

    mmi_list = SAMessageValues.get("fMMIlist")

    city_list = []
    for city in closest_cities.keys():
        point = geojson.Point(
            (closest_cities[city]['lon'], closest_cities[city]['lat'])
        )
        intensity_level = EQCalculations.getIntensityLevel(
            mmi_list,
            lat=closest_cities[city]['lat'],
            lon=closest_cities[city]['lon']
        )
        city_list.append(
            geojson.Feature(
                id=city,
                geometry=point,
                properties={
                    "name": city,
                    "citydist": closest_cities[city]['distance'],
                    "warning_time": closest_cities[city]['time'],
                    "mmi": intensity_level
                }
            )
        )

    cities = geojson.FeatureCollection(city_list, id="cityCollection")
    geojson_struct["cities"] = cities
    '''
    # BEGIN TEMPORARY PATCH
    # TODO: CLEANUP: Remove initial_alert and final_alert once downstream
    # bug is patched.  Elements "initial_alert" and "final_alert" were
    # removed from the resulting geojson. Based on testing carried out on
    # 2023-02-04, it was discovered their removal causes an error sometime
    # after receipt by ComCat which results in a failure to update GHSC's
    # earthquake event page. The elements have been added back as
    # placeholders containing a deprecation message until the downstream
    # bug can be patched.
    geojson_struct['initial_alert'] = {
        'api_note': (
            'Element initial_alert has been moved. '
            'See json path .alerts for alert list that includes this object.'
        )
    }
    geojson_struct['final_alert'] = {
        'api_note': (
            'Element final_alert has been moved. '
            'See json path .alerts for alert list that includes this object.'
        )
    }
    # END TEMPORARY PATCH
    '''
    geojson_struct["alerts"] = [
        build_init_FeatureCollection(
            SAMessageValues=SAMessageValues,
            contours=SAMessageValues.get('initial_contours'),
            to_jsi=to_jsi
        ),
        build_peak_mag_FeatureCollection(
            SAMessageValues=SAMessageValues,
            contours=SAMessageValues.get('peak_contours')
        ),
        build_final_FeatureCollection(
            SAMessageValues=SAMessageValues,
            contours=SAMessageValues.get('final_contours')
        )
    ]

    # Return the GeoJSON string.
    return geojson.dumps(geojson_struct, sort_keys=False, indent=json_indent)


def drawEarthquakeSection(pdf, tx):
    """
    Draw PDF "Earthquake" section to the given PDF canvas object.
    :param pdf: A reportlab pdf canvas to be updated.
    :param tx: Dictionary of PDF formatting info.
    :return: None
    :rtype: NoneType
    """
    title = 'Earthquake:'
    anss_def = 'Advanced National Seismic System (ANSS):'

    # crude fix to retain tenths of seconds
    anss_origin_avail = has_anss_origin_data(SAMessageValues)
    if anss_origin_avail:
        ANSStimeObj = SAMessageValues.get('ANSStimeObj')

        # ANSS UTC origin time line (rounded to nearest tenth of a second).
        ANSStimetenths = int(round((float(ANSStimeObj.microsecond)/1e5), 0))
        ANSStimeUTCString = ANSStimeObj.strftime('%Y-%m-%d %H:%M:%S.') + str(ANSStimetenths)

        # ANSS local origin time line (rounded to nearest tenth of a second).
        localANSStimeObj = ShakeAlertParser.utc_to_local(ANSStimeObj)
        ANSStimePSTString = localANSStimeObj.strftime('%Y-%m-%d %H:%M:%S.') + str(ANSStimetenths)

        # ANSS location line to 3 decimal places.
        ANSS_lat_lon_coord_str='{:.3f}, {:.3f}'.format(
            SAMessageValues.get('ANSSlat'),
            SAMessageValues.get('ANSSlon')
        )

        # ANSS depth line.
        ANSS_depth_km = get_rounded_str(
            SAMessageValues.get('ANSSdepth'),
            precision=1
        )
        ANSS_depth_mi = get_rounded_str(
            km_to_mi(SAMessageValues.get('ANSSdepth')),
            precision=1
        )
        ANSS_depth_str = f'{ANSS_depth_km} km  ({ANSS_depth_mi} mi)'

    else:
        ANSStimeUTCString = 'Not available at report time'
        ANSStimePSTString = 'Not available at report time'
        ANSS_depth_str = 'Not available at report time'
        ANSS_lat_lon_coord_str = 'Not available at report time'

    SA_inittimeObj = SAMessageValues['SA_inittimeObj']
    SA_atimetenths = int(round((float(SA_inittimeObj.microsecond)/1e5), 0))
    SA_inittimeString = SA_inittimeObj.strftime('%Y-%m-%d %H:%M:%S.')

    # ShakeAlert initial alert "message sent" timestamp str.
    txt_SAalert_time = SA_inittimeString + str(SA_atimetenths)

    # Get closest city info.
    closest_cities = SAMessageValues['closestCities']
    closest_city = list(closest_cities.keys())[0]
    closest_city_dist_km = closest_cities[closest_city]['distance']
    closest_city_dist_mi = km_to_mi(closest_city_dist_km)
    closest_city_bearing = closest_cities[closest_city]['bearing']

    # Title entry used in both PDF and NEIC post alert summary geojson.
    SAMessageValues['title'] = '{:.1f} mi {!s} of {!s}'.format(
        closest_city_dist_mi,
        closest_city_bearing,
        closest_city
    )

    if has_anss_origin_data(event_data=SAMessageValues):
        title_mag = get_pprint_mag(SAMessageValues['ANSSmag'])
    else:
        title_mag = get_pprint_mag(SAMessageValues['mag'])

    # Line str containing mag and distance to nearest city.
    mag_dist_text = '{!s} - {:.1f} km ({:.1f} mi) {!s} of {!s}'.format(
        title_mag,
        closest_city_dist_km,
        closest_city_dist_mi,
        closest_city_bearing,
        closest_city
    )

    txt_event_id = SAMessageValues.get('anss_id')

    # Begin drawing to pdf canvas.
    xnow = tx['x0']
    ynow = tx['y0']

    # Data to be passed into a reportlab Table. Must be a 2D List.
    eq_table_data = [
        [title, ''],
        [anss_def, ''],
        [mag_dist_text, ''],
        ['ANSS location:', ANSS_lat_lon_coord_str],
        ['ANSS depth:', ANSS_depth_str],
        ['ANSS origin (Local):', ANSStimePSTString],
        ['ANSS origin (UTC):', ANSStimeUTCString],
        ['ShakeAlert first Message (UTC):', txt_SAalert_time],
        ['ShakeAlert Event ID:', txt_event_id]
    ]


    '''
    Earthquake section table style command list.
    Command Notes:
        * The table style range indices (0, 0) to (-1, -1) include all cells.
        * LEFTPADDING defaults to 6.
        * RIGHTPADDING defaults to 6.
        * TOPPADDING defaults to 3.
        * BOTTOMPADDING defaults to 3.
    '''
    eq_table_style = TableStyle(
        cmds=[
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('SPAN', (0, 0), (-1, 0)),                      # Span title.
            ('FONTNAME', (0, 0), (-1, 0), tx['titlfont']),  # Title font.
            ('FONTSIZE', (0, 0), (-1, 0), tx['titlsize']),  # Title font size.
            ('LEFTPADDING', (0, 0), (-1, 0), 0),            # Title indent 0.
            ('TOPPADDING', (0, 0), (-1, 0), 0),             # Title top pad 0.
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),          # Title btm pad 0.
            ('FONTNAME', (0, 1), (-1, -1), tx['txt1font']),
            ('FONTSIZE', (0, 1), (-1, -1), tx['txt1size']),
            ('LEFTPADDING', (0, 1), (0, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
            ('SPAN', (0, 1), (-1, 1)),                       # Span row 2.
            ('SPAN', (0, 2), (-1, 2)),                       # Span row 3.
        ],
        parent=None
    )

    # Create reportlab Table object to represent eathquake section data.
    eq_table = Table(
        eq_table_data,
        colWidths=None,
        rowHeights=None,
        style=eq_table_style,
        splitByRow=1,
        repeatRows=0,
        repeatCols=0,
        rowSplitRange=None,
        spaceBefore=None,
        spaceAfter=None
    )

    # Define table max height and width scalars.
    table_max_width = 4.0
    table_max_height = 1.25

    # Set table height and width in inches.
    eq_table.wrap(
        availWidth=table_max_width * inch,
        availHeight=table_max_height * inch
    )

    # Decrement the y-axis cursor by the height table.
    ynow -= (eq_table._height / inch) - tx['txt1_dy']

    # Draw earthquake section table to canvas.
    eq_table.drawOn(canvas=pdf, x=(xnow * inch), y=(ynow * inch))


def drawSummaryReportSection(pdf, tx):
    '''
    Draw summary report section to the given reportlab canvas. This section
    containes separate tables for time to alert (alert speed), magnitude
    accuracy, location accuracy, and number of reporting stations.
    :param pdf: The target reportlab pdf canvas object.
    :param tx: A Dict containing text formatting info like font sizes.
    '''
    anss_orig_avail = has_anss_origin_data(SAMessageValues)

    subtitle_speed = "ShakeAlert Messages Issued (after origin time):"

    speed_table_data = [
        [subtitle_speed, ''],
    ]

    if anss_orig_avail:
        speed_table_data.append(
            ['Initial:', f'{SAMessageValues["t_ANSSotime_SAalert_initString"]} sec']
        )
        speed_table_data.append(
            ['Peak magnitude:', f'{SAMessageValues["t_ANSSotime_SAalert_peakMString"]} sec']
        )
        speed_table_data.append(
            ['Final:', f'{SAMessageValues["t_ANSSotime_SAalert_finalString"]} sec']
        )
    else:
        speed_table_data.append(
            ['Initial:', 'Not available']
        )
        speed_table_data.append(
            ['Peak magnitude:', 'Not available']
        )
        speed_table_data.append(
            ['Final:', 'Not available']
        )

    subtitle_mag = "ShakeAlert System Magnitude Estimates:"
    mag_accuracy_table_data = [
        [subtitle_mag, ''],
        ['Initial:', get_pprint_mag(SAMessageValues.get('initial_mag'))],
        ['Peak:', get_pprint_mag(SAMessageValues.get('peak_mag'))],
        ['Final:', get_pprint_mag(SAMessageValues.get('mag'))],
    ]
    #
    # ANSS mag out, 8/1/2021
    #if anss_orig_avail:
    #   mag_accuracy_table_data.append([
    #       'ANSS at report time:', get_pprint_mag(SAMessageValues.get('ANSSmag'))
    #   ])
    #else:
    #   mag_accuracy_table_data.append([
    #       'ANSS at report time:', 'Not available at report time'
    #   ])

    subtitle_loc = "ShakeAlert System Location Accuracy:"
    if anss_orig_avail:
        # Get final and initial alert distance in mi and km.
        alert_di_mi = SAMessageValues.get('initialAlertDistance')
        alert_dp_mi = SAMessageValues.get('peakMAlertDistance')
        alert_df_mi = SAMessageValues.get('finalAlertDistance')
        alert_di_km = round((float(alert_di_mi) * 1.60934), 1)
        alert_dp_km = round((float(alert_dp_mi) * 1.60934), 1)
        alert_df_km = round((float(alert_df_mi) * 1.60934), 1)

        # Get final and initial alert compass bearing.
        alert_bearing_i = SAMessageValues.get('initialCompassDirection')
        alert_bearing_p = SAMessageValues.get('peakMCompassDirection')
        alert_bearing_f = SAMessageValues.get('finalCompassDirection')

        # Load dist and bearing values into table array.
        loc_accuracy_table_data = [
            [subtitle_loc, ''],
            ['Initial:', f'{alert_di_km!s} km ({alert_di_mi!s} mi) {alert_bearing_i!s}'],
            ['At peak mag.:', f'{alert_dp_km!s} km ({alert_dp_mi!s} mi) {alert_bearing_p!s}'],
            ['Final:', f'{alert_df_km!s} km ({alert_df_mi!s} mi) {alert_bearing_f!s}'],
        ]
    else:
        # No SA message data found. Load table with "unavailable" message.
        loc_accuracy_table_data = [
            [subtitle_loc, ''],
            ['Initial:', 'Not available at report time'],
            ['Peak M:', 'Not available at report time'],
            ['Final:', 'Not available at report time'],
        ]

    subtitle_nsta = 'Number of Stations Reporting:'
    n_stations_table_data = [
        [subtitle_nsta, ''],
        [str(SAMessageValues.get('numStationsIn10KM')) + ' within 10 km of epicenter'],
        [str(SAMessageValues.get('numStationsIn100KM')) + ' within 100 km of epicenter'],
        [str(SAMessageValues.get('num_stations')) + ' used in final ShakeAlert Message'],
    ]

    # Indent levels
    xind0 = tx['x0'] + tx['titlindent']  # x0, y0 are section top-left anchor pts, inches from bottom
    xind1 = tx['x0'] + tx['txt1indent']  # indent 1   Indent indices do not track with fonts

    # Set initial y axis position.
    ynow = tx['y0']

    # Reportlab TableStyle object used for all tables in this section.
    table_style = TableStyle(
        cmds=[
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('SPAN', (0, 0), (-1, 0)),                      # Span title.
            ('FONTNAME', (0, 0), (-1, 0), tx['txt2font']),  # Title font.
            ('FONTSIZE', (0, 0), (-1, 0), tx['txt2size']),  # Title font size.
            ('LEFTPADDING', (0, 0), (-1, 0), 0),            # Title indent 0.
            ('TOPPADDING', (0, 0), (-1, 0), 0),             # Title top pad 0.
            ('BOTTOMPADDING', (0, 0), (-1, 0), 1),          # Title btm pad 0.
            ('FONTNAME', (0, 1), (-1, -1), tx['txt1font']),
            ('FONTSIZE', (0, 1), (-1, -1), tx['txt1size']),
            ('LEFTPADDING', (0, 1), (0, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
        ],
        parent=None
    )

    ###### Time To Alert Table #####
    xnow = xind0  # Set current pdf canvas x-axis cursor.

    # Create reportlab Table obj for time to alert (alert speed) data.
    speed_table = Table(
        speed_table_data,
        colWidths=None,
        rowHeights=None,
        style=table_style,
        splitByRow=1,
        repeatRows=0,
        repeatCols=0,
        rowSplitRange=None,
        spaceBefore=None,
        spaceAfter=None
    )

    # Define table max height and width scalars.
    table_max_width = 4.0
    table_max_height = 0.25

    # Set table height and width in inches.
    speed_table.wrap(
        availWidth=table_max_width * inch,
        availHeight=table_max_height * inch
    )

    # Decrement the y-axis cursor by the height table.
    ynow -= speed_table._height / inch - tx['txt1_dy']

    # Draw table to canvas.
    speed_table.drawOn(canvas=pdf, x=(xnow * inch), y=(ynow * inch))

    ###### End Time To Alert Table.

    ###### Mag Accuracy Table.
    mag_accuracy_table = Table(
        mag_accuracy_table_data,
        colWidths=None,
        rowHeights=None,
        style=table_style,
        splitByRow=1,
        repeatRows=0,
        repeatCols=0,
        rowSplitRange=None,
        spaceBefore=None,
        spaceAfter=None
    )

    # Define table max height and width scalars.
    table_max_width = 4.0
    table_max_height = 1.0

    # Set table height and width in inches.
    mag_accuracy_table.wrap(
        availWidth=table_max_width * inch,
        availHeight=table_max_height * inch
    )

    # Decrement the y-axis cursor by the height table.
    ynow -= mag_accuracy_table._height / inch

    # Draw table to canvas.
    mag_accuracy_table.drawOn(canvas=pdf, x=(xnow * inch), y=(ynow * inch))

    ###### End Mag Accuracy Table.

    ###### Location Accuracy Table.
    loc_accuracy_table = Table(
        loc_accuracy_table_data,
        colWidths=None,
        rowHeights=None,
        style=table_style,
        splitByRow=1,
        repeatRows=0,
        repeatCols=0,
        rowSplitRange=None,
        spaceBefore=None,
        spaceAfter=None
    )

    # Define table max height and width scalars.
    table_max_width = 4.0
    table_max_height = 0.50

    # Set table height and width in inches.
    loc_accuracy_table.wrap(
        availWidth=table_max_width * inch,
        availHeight=table_max_height * inch
    )

    # Decrement the y-axis cursor by the height table.
    ynow -= loc_accuracy_table._height / inch

    # Draw table to canvas.
    loc_accuracy_table.drawOn(canvas=pdf, x=(xnow * inch), y=(ynow * inch))

    ###### End Location Accuracy Table.

    ##### start WEA block #####
    # Get WEA report text from json. Set to empty string if null or undef.
    txt_wea_report_line = SAMessageValues.get('wea_report')
    txt_wea_standards_line = 'WEA alerts are distributed to the MMI 4+ area if ShakeAlert Peak M>=5.0'
    if not txt_wea_report_line:
        txt_wea_report_line = None

    wea_table_data = [
        ['Wireless Emergency Alert:', ''],
        [txt_wea_report_line, ''],
        [txt_wea_standards_line, ''],
    ]

    wea_table_style = TableStyle(
        cmds=[
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('SPAN', (0, 0), (-1, 0)),                      # Span title.
            ('FONTNAME', (0, 0), (-1, 0), tx['txt2font']),  # Title font.
            ('FONTSIZE', (0, 0), (-1, 0), tx['txt2size']),  # Title font size.
            ('LEFTPADDING', (0, 0), (-1, 0), 0),            # Title indent 0.
            ('TOPPADDING', (0, 0), (-1, 0), 0),             # Title top pad 0.
            ('BOTTOMPADDING', (0, 0), (-1, 0), 0),          # Title btm pad 0.    was 4
            ('FONTNAME', (0, 1), (-1, -1), tx['txt1font']),
            ('FONTSIZE', (0, 1), (-1, -1), tx['txt1size']),
            ('FONTNAME', (0, 2), (-1, -1), tx['txt3font']),
            ('FONTSIZE', (0, 2), (-1, -1), tx['txt3size']),
            ('LEFTPADDING', (0, 1), (0, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
            ('SPAN', (0, 1), (-1, 1)),                       # Span row 2.
            ('SPAN', (0, 2), (-1, 2)),                       # Span row 3.
        ],
        parent=None
    )

    # Create wea section table that reuses earthquake section format.
    wea_table = Table(
        wea_table_data,
        colWidths=None,
        rowHeights=None,
        style=wea_table_style,
        splitByRow=1,
        repeatRows=0,
        repeatCols=0,
        rowSplitRange=None,
        spaceBefore=None,
        spaceAfter=None
    )

    # Set table height and width in inches.
    wea_table.wrap(
        availWidth=table_max_width * inch,
        availHeight=table_max_height * inch
    )

    # Decrement the y-axis cursor by the height table.
    ynow -= (wea_table._height / inch)  # - tx['txt1_dy']

    # Draw wea report section table to canvas.
    wea_table.drawOn(canvas=pdf, x=(xnow * inch), y=(ynow * inch))

    ##### end WEA block #####

    ###### Number of Reporting Stations Table.
    n_stations_table = Table(
        n_stations_table_data,
        colWidths=None,
        rowHeights=None,
        style=table_style,
        splitByRow=1,
        repeatRows=0,
        repeatCols=0,
        rowSplitRange=None,
        spaceBefore=None,
        spaceAfter=None
    )

    # Define table max height and width scalars.
    table_max_width = 4.0
    table_max_height = 0.75

    # Set table height and width in inches.
    n_stations_table.wrap(
        availWidth=table_max_width * inch,
        availHeight=table_max_height * inch
    )

    # Decrement the y-axis cursor by the height table.
    ynow -= n_stations_table._height / inch

    # Draw table to canvas.
    n_stations_table.drawOn(canvas=pdf, x=(xnow * inch), y=(ynow * inch))

    ###### End Number of Reporting Stations Table.


def drawPerformanceSection(pdf, tx):
    title_performance = 'Nearby Cities:'
    if SAMessageValues.get('sWaveRadius'):
      s_wave_radius_str_km = str(round(SAMessageValues.get('sWaveRadius')))
      s_wave_radius_str_mi = str(round(SAMessageValues.get('sWaveRadius')/1.60934))
      s_wave_zone_str = f'{s_wave_radius_str_km} km ({s_wave_radius_str_mi} mi)'
    else:  # if s-wave radius data is not found (in case of missing ANSS origin).
      s_wave_zone_str = 'Not available'

    txt_zone_shaken = f'Radius shaken before message release: {s_wave_zone_str}'

    # Three indent levels
    xind0 = tx['x0'] + tx['titlindent']     # x0, y0 are section top-left anchor pts, inches from bottom
    xind1 = tx['x0'] + tx['txt1indent']     # indent 1   Indent indices do not track with fonts
    xind2 = tx['x0'] + tx['txt2indent']     # indent 2

    # hack for 3 columns of table
    xcol0 = xind1   # warning time column   values here are hacks until a cleaner way suggests itself
    xcol1 = xcol0 + 1.5     # distance column
    xcol2 = xcol1 + 1.0     # warning time column
    xcol3 = xcol2 + 0.75    # MMI intensity column

    xnow = xind0
    ynow = tx['y0']

    # Nearest cities data to be added to a reportlab Table object.
    nearby_city_table_data = [
        [title_performance, '', '', '']
    ]

    # Add column heading row to table.
    nearby_city_table_data.append([
        'City',
        'Distance',
        'Time*',
        'MMI**',
    ])

    closest_cities = SAMessageValues.get("closestCities")

    mmi_list = SAMessageValues.get("fMMIlist")

    for city in closest_cities.keys():
        intensity_level = EQCalculations.getIntensityLevel(
            mmi_list,
            lat=closest_cities[city]['lat'],
            lon=closest_cities[city]['lon']
        )
        txt_city_intensity = EQCalculations.intensityNumberString(intensity_level)
        txt_city_name = city
        txt_city_ttoalert = f'~{closest_cities[city]["time"]:.0f} sec'
        city_d_km = closest_cities[city]['distance']
        city_d_mi = km_to_mi(city_d_km)
        txt_city_dist = f'{city_d_km:.0f} km ({city_d_mi:.0f} mi)'

        # Append new city row to table data.
        nearby_city_table_data.append([
            Paragraph(txt_city_name, style=getSampleStyleSheet()['Normal']),
            txt_city_dist,
            txt_city_ttoalert,
            txt_city_intensity,
        ])

    '''
    Nearby cities table reportlab TableStyle object.
    Note: The table style range indices (0, 0) to (-1, -1) include all cells.
          The table style range indices (0, 0) to (-1, 0) select the header row.
    '''
    nearby_cities_table_style = TableStyle(
        cmds=[
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('SPAN', (0, 0), (-1, 0)),                      # Span title.
            ('FONTNAME', (0, 0), (-1, 0), tx['txt2font']),  # Title font.
            ('FONTSIZE', (0, 0), (-1, 0), tx['txt2size']),  # Title font size.
            ('LEFTPADDING', (0, 0), (-1, 0), 0),            # Title indent 0.
            ('TOPPADDING', (0, 0), (-1, 0), 0),             # Title top pad 0.
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),          # Title btm pad 0.
            ('LEFTPADDING', (0, 1), (0, -1), 10),
            ('FONTNAME', (0, 1), (-1, 1), tx['txt2font']),
            ('FONTSIZE', (0, 1), (-1, 1), tx['txt2size']),
            ('FONTNAME', (0, 2), (-1, -1), tx['txt1font']),
            ('FONTSIZE', (0, 2), (-1, -1), tx['txt1size']),
            ('ALIGN', (-3, 0), (-1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
            ('TOPPADDING', (0, 1), (-1, -1), 1),
        ],
        parent=None,
    )

    # Define table max height and width scalars.
    table_max_width = 4.0 * inch
    table_max_height = 1.5 * inch

    # Define nearby city table column widths.
    # Note: Column widths should add up to the table_max_idth be < 4 inches.
    col_widths = [
        1.750 * inch,
        1.250 * inch,
        0.750 * inch,
        0.625 * inch
    ]

    # Create reportlab Table obj. Table implements abstract class Flowable.
    nearby_city_table = Table(
        nearby_city_table_data,
        colWidths=col_widths,
        rowHeights=None,
        style=nearby_cities_table_style,
        splitByRow=1,
        repeatRows=0,
        repeatCols=0,
        rowSplitRange=None,
        spaceBefore=None,
        spaceAfter=None
    )

    # Set table height and width in inches.
    nearby_city_table.wrap(
        availWidth=table_max_width,
        availHeight=table_max_height
    )

    # Decrement the y-axis cursor by the height table.
    ynow -= nearby_city_table._height / inch

    # Draw table to canvas.
    nearby_city_table.drawOn(canvas=pdf, x=(xnow * inch), y=(ynow * inch))

    ynow -= tx['txt1_dy']
    pdf.setFont(tx["txt2font"], tx["txt2size"])
    pdf.drawString(xcol0*inch, ynow*inch, txt_zone_shaken)


def drawFootnotesSection(pdf, tx):
    """
    Draw PDF footnotes section.
    :param pdf: reportlab PDF canvas object.
    :param tx: reportlab PDF cursor position Dict.
    """
    # Declare footnote section text.
    title_foot = 'Footnotes:'
    foot_line_1 = '* Time -- Time between message release and '
    foot_line_2 = 'arrival of the S-wave at the location.'
    foot_line_3 = '** MMI -- Modified Mercalli Intensity: a scale to measure'
    foot_line_4 = 'ground shaking severity.'
    foot_line_5 = '*** For earthquakes deeper than ~15 km, the ShakeAlert Message may'
    foot_line_6 = 'be sent before peak shaking reaches the surface.'

    # Set title position.
    xnow = tx['x0'] + tx['titlindent']  # x0, y0 are section top-left anchor pts, inches from bottom.
    xind4 = xnow + tx['txt4indent']
    ynow = tx['y0']

    # Move it down a tad.
    ynow -= 2 * tx['txt1_dy']

    # Set font and draw footnotes section title.
    pdf.setFont(tx['txt5font'], tx['txt5size'])
    pdf.drawString(xnow*inch, ynow*inch, title_foot)

    # Set font and draw footnotes section body.
    ynow = ynow - tx['txt4_dy']
    pdf.setFont(tx['txt4font'], tx['txt4size'])
    pdf.drawString(xnow*inch,  ynow*inch, foot_line_1)
    ynow = ynow - tx['txt4_dy']
    pdf.drawString(xind4*inch, ynow*inch, foot_line_2)
    ynow = ynow - tx['txt4_dy']
    pdf.drawString(xnow*inch,  ynow*inch, foot_line_3)
    ynow = ynow - tx['txt4_dy']
    pdf.drawString(xind4*inch, ynow*inch, foot_line_4)
    ynow = ynow - tx['txt4_dy']
    pdf.drawString(xnow*inch,  ynow*inch, foot_line_5)
    ynow = ynow - tx['txt4_dy']
    pdf.drawString(xind4*inch, ynow*inch, foot_line_6)


def drawQualificationsSection(pdf, tx):

    # Qualifications
    title_qualifs = 'Disclaimer:'
    txt_qualifs   = """This information is provisional and subject to revision.
It is being provided to meet the need for timely best science.
The information has not received final approval by the U.S.
Geological Survey (USGS) and is provided on the condition that
neither the USGS nor the U.S. Government shall be held liable for
any damages resulting from the authorized or unauthorized use of
the information."""

    # Set Title
    xnow = tx['x0'] + tx['titlindent']   # x0, y0 are section top-left anchor pts, inches from bottom
    ynow = tx['y0']

    pdf.setFont(tx['txt5font'], tx['txt5size'])
    pdf.drawString(xnow*inch, ynow*inch, title_qualifs)
    ynow = ynow - tx['txt4_dy']

    pdf.setFont(tx['txt4font'], tx['txt4size'])

    for txt in txt_qualifs.split("\n"):
        pdf.drawString(xnow*inch, ynow*inch, txt)
        ynow = ynow - tx['txt4_dy']


def drawFAQLine(pdf, tx):
    # Qualifications
    txt_FAQ = "To learn more about ShakeAlert\u00AE, visit www.shakealert.org/FAQ"

    # --------  text placement only below here -------------------
    xnow = tx['x0'] + tx['titlindent']  # x0, y0 are section top-left anchor pts, inches from bottom
    ynow = tx['y0']

    pdf.setFont(tx['txt4font'], tx['txt4size'])
    pdf.drawString(xnow*inch, ynow*inch, txt_FAQ)


def drawReportTimeLine(pdf, tx):           # Report Generation Time footnote
    reportString = "Report created " + SAMessageValues.get('timeCreatedPST')

    # --------  text placement only below here -------------------
    xnow = tx['x0'] + tx['titlindent']     # x0, in this case is the right extreme
    ynow = tx['y0']

    pdf.setFont(tx['txt3font'], tx['txt3size'])
    pdf.drawRightString(xnow*inch, ynow*inch, reportString)


def drawEarthquakeImagesSection(pdf, output_path, tx):
  xnow = tx['x0']

  anss_origin_avail = has_anss_origin_data(SAMessageValues)

  if anss_origin_avail:
    txt_caption2 = """Figure 2. Polygons show shaking intensity contours for
the peak magnitude estimate.  Shaking of MMI 3 or less
is often not felt.  Star shows the ANSS earthquake
epicenter."""
  else:
    txt_caption2 = """Figure 2. Polygons show shaking intensity contours for
the peak magnitude estimate.  Shaking of MMI 3 or less
is often not felt.  ANSS earthquake epicenter
not available."""

  if anss_origin_avail:
    txt_final_caption2 = """Figure 2. Polygons show shaking intensity contours for
the final ShakeAlert estimate.  Shaking of MMI 3 or less
is often not felt.  Star shows the ANSS earthquake
epicenter."""
  else:
    txt_final_caption2 = """Figure 2. Polygons show shaking intensity contours for
the final ShakeAlert estimate.  Shaking of MMI 3 or less
is often not felt.  ANSS earthquake epicenter
not available."""

  SAMessageValues["txt_caption2"] = txt_caption2
  SAMessageValues["txt_final_caption2"] = txt_final_caption2

  if SAMessageValues.get('isJSON'):

# -- DEBUG
    for k in SAMessageValues.get('initial_polygonList'):
        print("initial_polygon %s" % k)           # one line
# --

    if anss_origin_avail:
        print('ANSS origin available.')
    else:
        print('ANSS origin NOT available.')

    # Get gm_contour filter configs and cast to floats.
    mag_threshold=float(config.get('THRESHOLDS', 'MagMapChange'))
    min_mmi_small_event=float(config.get('THRESHOLDS', 'MMISmall'))
    min_mmi_large_event=float(config.get('THRESHOLDS', 'MMIAlert'))

    # Create new Callable GMContourFilter instance.
    gmc_filter = GMContourFilter(
        mag_threshold,
        min_mmi_small_event,
        min_mmi_large_event
    )

    # Filter GMContours that will be used to draw our map.
    initial_gm_contours: List[GMContour] = gmc_filter(
        SAMessageValues.get('initial_contours'),
        event_mag=float(SAMessageValues.get('initial_mag'))
    )
    peak_gm_contours: List[GMContour] = gmc_filter(
        SAMessageValues.get('peak_contours'),
        event_mag=float(SAMessageValues.get('peak_mag'))
    )
    final_gm_contours: List[GMContour] = gmc_filter(
        SAMessageValues.get('final_contours'),
        event_mag=float(SAMessageValues.get('mag'))
    )

    alertmap = None
    to_jsi = None
    if anss_origin_avail:
        alertmap, to_jsi = PyEventImage.buildAlertMap(
            mag=SAMessageValues.get('initial_mag'),
            anss_lat=SAMessageValues.get('ANSSlat'),
            anss_lon=SAMessageValues.get('ANSSlon'),
            anss_depth=SAMessageValues.get('ANSSdepth'),
            init_sa_lat=SAMessageValues.get('initial_lat'),
            init_sa_lon=SAMessageValues.get('initial_lon'),
            init_sa_to_anss_dt=SAMessageValues.get("t_ANSSotime_SAalert_init"),
            s_wave_velocity=config.get("GENERAL", 'vs'),
            map_change_mag_threshold=MagMapChange,
            initial_contours=initial_gm_contours,
            draw_anss_marker=True,
            output_dir=output_path
        )
    else:
        # Handle case where ANSS event data is not provided
        alertmap, to_jsi = PyEventImage.buildAlertMap(
            mag=SAMessageValues.get('initial_mag'),
            anss_lat=SAMessageValues.get('initial_lat'),
            anss_lon=SAMessageValues.get('initial_lon'),
            anss_depth=SAMessageValues.get('depth'),
            init_sa_lat=SAMessageValues.get('initial_lat'),
            init_sa_lon=SAMessageValues.get('initial_lon'),
            init_sa_to_anss_dt=0.0,
            s_wave_velocity=config.get("GENERAL", 'vs'),
            map_change_mag_threshold=MagMapChange,
            draw_anss_marker=False,
            initial_contours=initial_gm_contours,
            output_dir=output_path
        )

    # tried width 238; circles not round
    pdf.drawInlineImage( alertmap,
      xnow*inch,
      5.95*inch,
      width=208,
      height=308,
    )

# -- DEBUG bPM --
    for k in SAMessageValues.get('polygonList'):
        print("buildPolygonMap poly input  final_pL %s" % k)           #
# --
    global to_jsf
    print(SAMessageValues.get('final_contours'))


    # Draw MMI contour polygon map (lower map) and create symmetrical geojson
    if anss_origin_avail:
        imageFile, to_jsf = PyEventImage.buildPolygonMap(
            mag=SAMessageValues.get('initial_mag'),
            ANSSlat=SAMessageValues.get('ANSSlat'),
            ANSSlon=SAMessageValues.get('ANSSlon'),
            map_change_mag_threshold=MagMapChange,
            initial_contours=initial_gm_contours,
            peak_contours=peak_gm_contours,
            final_contours=final_gm_contours,
            outputDir=output_path
        )
    else:
        # Handling for case where there's no ANSS solution (ie. false alert).
        imageFile, to_jsf = PyEventImage.buildPolygonMap(
            mag=SAMessageValues.get('initial_mag'),
            ANSSlat=SAMessageValues.get('lat'),  # Using SA final lat since ANSS lat not available.
            ANSSlon=SAMessageValues.get('lon'),  # Using SA final lon since ANSS lon not available.
            map_change_mag_threshold=MagMapChange,
            initial_contours=initial_gm_contours,
            peak_contours=SAMessageValues.get('peak_contours'),
            final_contours=SAMessageValues.get('final_contours'),
            drawANSSMarker=False,
            outputDir=output_path
        )

    # tried 235; circles not round
    pdf.drawInlineImage(
      imageFile,
      x=xnow*inch,
      y=1.00*inch,
      width=205,
      height=309
    )
         # repeat (1) initial poly, (2) add final poly from polygonList (final) (3) add finite fault

    print("js PyEventImage buildPolygonMap call done")
    print('--debug----MMIlist-------')
    lmmi = len(SAMessageValues.get('MMIlist'))
    print("length SAMessageValues.get('MMIlist') %d" % lmmi)
    print('--debug----initial_polygonList-------')
    print(SAMessageValues.get('initial_polygonList'))
    print('--debug----polygonList-------')
    print(SAMessageValues.get('polygonList'))

    captionfont     = tx['txt6font']
    captionfontsize = tx['txt6size']
    xnow = tx['x0'] - tx['txt6indent']
    y0              = 0.85
    dy              = tx['txt6_dy']
    ynow            = y0

    # pdf.setFont(captionfont, captionfontsize)
    for tc in txt_caption2.split("\n"):
        pdf.drawString(xnow*inch,ynow*inch, tc)
        ynow-=dy

  else:  # endif SAMessage.get('isJSON')
    imageFile, to_jsf = PyEventImage.buildAlertMap(
        SAMessageValues.get('initial_mag'),
        SAMessageValues.get('lat'),
        SAMessageValues.get('lon'),
        SAMessageValues.get('depth'),
        SAMessageValues.get("t_ANSSotime_SAalert_init"),
        config.get("GENERAL",'vs'),
        map_change_mag_threshold=MagMapChange,
        initialPolygonList=SAMessageValues.get('polygonList'),
        output_dir=output_path
    )
    pdf.drawInlineImage(
      imageFile,
      x=xnow*inch,
      y=5.95*inch,
      width=208,
      height=308,
    )

  # magnitude-dependent caption, figure 1
  if anss_origin_avail and float(SAMessageValues.get('initial_mag')) >= 5.0:
    txt_caption1 = """Figure 1. ShakeAlert initial earthquake location (black dot).
Star is ANSS earthquake epicenter.  Polygon shows estimated
MMI 4 shaking intensity area.  If shown, red circle is front
of peak shaking when the message was released***.
Shaking takes 10 s to expand from circle to circle."""
  elif (not anss_origin_avail) and float(SAMessageValues.get('initial_mag')) >= 5.0:
    txt_caption1 = """Figure 1. ShakeAlert initial earthquake location (black dot).
ANSS earthquake epicenter not available.  Polygon shows estimated
MMI 4 shaking intensity area.  If shown, red circle is front
of peak shaking when the message was released***.
Shaking takes 10 s to expand from circle to circle."""
  elif anss_origin_avail and float(SAMessageValues.get('initial_mag')) < 5.0:
    txt_caption1 = """Figure 1. ShakeAlert initial earthquake location (black dot).
Star is ANSS earthquake epicenter.  Polygon approximates the
outer range for felt ground motion.  If shown, red circle is
front of peak shaking when the message was released***.
Shaking takes 10 s to expand from circle to circle."""
  else:
    txt_caption1 = """Figure 1. ShakeAlert initial earthquake location (black dot).
ANSS earthquake epicenter not available.  Polygon approximates
outer range for felt ground motion.  If shown, red circle is
front of peak shaking when the message was released***.
Shaking takes 10 s to expand from circle to circle."""

  SAMessageValues["txt_caption1"] = txt_caption1

  captionfont     = tx['txt6font']
  captionfontsize = tx['txt6size']
  xnow            = tx['x0'] - tx['txt6indent']
  y0              = 5.8
  dy              = tx['txt6_dy']
  ynow            = y0

  pdf.setFont(captionfont, captionfontsize)
  for tc in txt_caption1.split("\n"):
      pdf.drawString(xnow*inch, ynow*inch, tc)
      ynow-=dy

  return to_jsi, to_jsf


def parse_cli_args() -> argparse.Namespace:
    """
    Parse command line arguments using argparse library.
    """
    # Parse and validate command line args.
    arg_parser = argparse.ArgumentParser(
        prog='Post ShakeAlert Message Summary',
        description=(
            'Generates Post ShakeAlert Message Summary reports from event '
            'ShakeAlert and ANSS data.'
        )
    )

    # Create mutex group to allow json input as file OR string (not both).
    input_arg_group = arg_parser.add_mutually_exclusive_group()
    input_arg_group.add_argument(
        '-f', '--input-file',
        type=str,
        help='Input ShakeAlert/ANSS event data json file.'
    )
    input_arg_group.add_argument(
        '-s', '--input-str',
        type=str,
        help='Input ShakeAlert/ANSS event data json string.'
    )

    arg_parser.add_argument(
        '-p', '--pprint-geojson',
        action='store_true',
        help='Output formatted GeoJSON indented for easy readability.')

    arg_parser.add_argument(
        '-o', '--output-dir',
        type=pathlib.Path,
        default=BASE_DIR / "output",
        help='Destination path for generated summary output files.'
    )

    arg_parser.add_argument(
        '-i', '--event-id',
        type=str,
        default='',
        help=(
            'DEPRECATED: This options functionality has been removed'
            'and will no effect on the generated output.'
        )
    )

    return arg_parser.parse_args()


if __name__ == "__main__":

    # Parse command line arguments.
    args = parse_cli_args()

    output_path = args.output_dir

    # Create output dir if needed (and make sure it doesn't point to a file).
    if os.path.isfile(output_path):
        print(f'ERROR: File exists at output dir path: {output_path}.')
        sys.exit(2)
    if not os.path.isdir(output_path):
        print(f'Creating output dir: {output_path}.')
        try:
            os.mkdir(output_path)
        except OSError as path_error:
            print(f'ERROR: Unable to create directory at path: {output_path}')
            print(path_error)
            sys.exit(2)

    # Note: Missing input source case handled by argparse.
    if args.input_file:  # source is JSON file
        SAMessageValues = ShakeAlertParser.ParseJSONFile(args.input_file)
    elif args.input_str:  # source is JSON string
        SAMessageValues = ShakeAlertParser.ParseJSONStr(args.input_str)

    # Begin main pdf creation logic.
    initializeFonts()

    filename = 'PostEventSummary'

    pdf_out_path = os.path.join(output_path, str(filename + ".pdf"))
    pdf = canvas.Canvas(pdf_out_path, pagesize=letter)

    left_margin = 0.5
    timeline_margin = 8.0
    images_margin = 5.0

    tx = {'x0': left_margin, 'y0': 10.0,
          'titlfont': "CalibriB",  'titlsize': 16, 'titl_dy': 0.25, 'titlindent': 0.00,
          'txt1font': "Calibri",   'txt1size': 12, 'txt1_dy': 0.20, 'txt1indent': 0.15,
          'txt2font': "CalibriB",  'txt2size': 12, 'txt2_dy': 0.25, 'txt2indent': 0.25,
          'txt3font': "Calibri",   'txt3size': 10, 'txt3_dy': 0.15, 'txt3indent': 0.15,
          'txt4font': "CalibriI",  'txt4size': 10, 'txt4_dy': 0.15, 'txt4indent': 0.15,
          'txt5font': "CalibriB",  'txt5size': 10, 'txt5_dy': 0.15, 'txt5indent': 0.00,
          'txt6font': "CalibriI",  'txt6size':  9, 'txt6_dy': 0.12, 'txt6indent': 0.00 }   # for Qualifications

    # Title
    pdf.setFont("CalibriB", 22)
    width,height = letter
#    pdf.drawString(tx['x0']*inch, 10.55*inch, 'Post-ShakeAlert\u00AE Message Summary')
    pdf.drawString(1.9375*inch, 10.55*inch, 'Post-ShakeAlert\u00AE Message Summary')

    # Earthquake
    drawEarthquakeSection(pdf, tx)        # Top-left text, mag, alert time

    # Summary Report
    tx['y0'] = 8.18
    drawSummaryReportSection(pdf, tx)     # Alert time, ANSS time, mag

    # Performance
    tx['y0'] = 4.80
    tx['titlsize'] = 18
    drawPerformanceSection(pdf, tx)       # Cities, warning times

    tx['x0'] = left_margin
    tx['y0'] = 3.25
    drawFootnotesSection(pdf, tx)         # Footnotes

    tx['y0'] = 1.60
    drawQualificationsSection(pdf, tx)    # Qualifications

    tx['x0'] = left_margin
    tx['y0'] = 0.25
    drawFAQLine(pdf, tx)                  # FAQ Line

    tx['x0'] = timeline_margin
    tx['y0'] = 0.25
    tx['txt3size'] = 9
    drawReportTimeLine(pdf, tx)           # Report Generation Time footnote

    tx['x0'] = images_margin
    to_jsi, to_jsf = drawEarthquakeImagesSection(pdf, output_path, tx)  # Maps

    pdf.save()

    json_out_path = os.path.join(output_path, str(filename + '.json'))
    if has_anss_origin_data(SAMessageValues):
        json_indent_spaces = None
        if args.pprint_geojson:
            json_indent_spaces = 2
        summary_geojson: str = export_to_geojson(
            to_jsi,
            json_indent=json_indent_spaces
        )
        with open(json_out_path, 'w') as f:
            f.write(summary_geojson)
    else:
        print('GeoJSON will not be created due to missing ANSS data.')
