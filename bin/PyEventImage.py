'''
Post ShakeAlert Message Summary map image creation module.
Created on Jul 17, 2018 by jjbun
'''
import os
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import imgkit
import sys

# import jinja2

from ShakeAlertParser import GMContour
from utils import get_intensity_color


MAP_PROVIDER = "'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'"

'''
J2_TEMPLATE_PATH = Path(__file__).parent.parent / 'templates'


# Create jinja2 environment object (used to load j2 templates).
j2_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        searchpath=str(J2_TEMPLATE_PATH)
    )
)


def get_w_time_map_template(j2_env: jinja2.Environment) -> jinja2.Template:
    return j2_env.get_template('EventSummary_a.html.j2')


def get_intensity_map_template(j2_env: jinja2.Environment) -> jinja2.Template:
    return j2_env.get_template('EventSummary_b.html.j2')
'''


def time_to_grey(duration_s: float) -> str:
    """
    The returned grey hue is darker when alert warning duration is closer to
    0 and lightest at its max of 40s.
    :param time_to_grey: S-wave travel duration in seconds. Duration input
        has a max of 40s. The lightest hue will be returned for any value
        exceeding the max.
    :type time_to_grey: float or int
    :return: A hex color string.
    :rtype: str
    """
    v = int(min(duration_s, 40.0) * 255.0 / 40.0)
    greystring = '#%02x%02x%02x' % (v,v,v)
    return greystring


def get_alert_circle_params(
        init_sa_mag: float,
        init_sa_to_anss_dt: float,
        s_wave_velocity: float,
        anss_depth) -> Dict[float, float]:
    """
    Creates the alert circle radii param dict.
    """
    # List of alert to s-wave arrival durations from which we will find radii.
    radii_show: List[float] = [0.0, 10.0, 20.0, 30.0]
    if float(init_sa_mag) < 6.0:
        radii_show = [0.0, 10.0, 20.0]

    #  Dict of arrival duration in s to radii in m. Default value = 0.0s
    alert_t_radii: Dict[float, float] = dict.fromkeys(radii_show, 0.0)
    for circle_radii_m in radii_show:
        if ((init_sa_to_anss_dt + circle_radii_m) * s_wave_velocity) > anss_depth:
            alert_t_radii[circle_radii_m] = (
                math.sqrt(((init_sa_to_anss_dt + circle_radii_m) * s_wave_velocity)**2 - anss_depth**2) * 1000
            )
        else:
            alert_t_radii[circle_radii_m] = 0.0
    return alert_t_radii


def buildAlertMap(
        mag: float,
        anss_lat: float,
        anss_lon: float,
        anss_depth: float,
        init_sa_lat: float,
        init_sa_lon: float,
        init_sa_to_anss_dt: float,
        s_wave_velocity: float,
        map_change_mag_threshold: float,
        initial_contours: List[GMContour],
        draw_anss_marker: bool = True,
        output_dir: str = ".") -> Tuple[Any, Any]:
    """
    Create alert warning time map and json params.
    """
    filename = os.path.join(output_dir, 'EventSummary_a.html')

    # Params for GeoJSON we will build later
    to_jsi = {}

    title = "Event Summary"

    if initial_contours is None:
        initial_contours = []

    print("alert_t: %f" % init_sa_to_anss_dt)

    alert_t_radii = get_alert_circle_params(
        init_sa_mag=float(mag),
        init_sa_to_anss_dt=float(init_sa_to_anss_dt),
        s_wave_velocity=float(s_wave_velocity),
        anss_depth=float(anss_depth)
    )

    print('Radii: Alert time 0 10 15 20...  (time to S) as Radii, km')
    print(alert_t_radii)

    f = open(filename,'w')

    preamble = """<!DOCTYPE html>
<html>
<head>
<title>%s</title>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0">
 <link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.2/dist/leaflet.css"
   integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ=="
   crossorigin=""/>
 <script src="https://unpkg.com/leaflet@1.3.2/dist/leaflet.js"
   integrity="sha512-2fA79E27MOeBgLjmBrtAgM/20clVSV8vJERaW/EcnnWCVGwQRazzKtQS1kIusCZv1PtaQxosDZZ0F1Oastl55w=="
   crossorigin=""></script>
 <style type="text/css">
 #map { width: 400px; height: 600px; }
 .tooltip {
  all: revert;
  font-size: 16px;
  font-weight: 700;
  background-color: none;
  border-color: none;
  background: none;
  box-shadow: none;
  fillColor: none;
  fillOpacity: 0;
  border: none;
  margin: 0px;
  fill: false;

 }
 .info {
    padding: 6px 8px;
    font: 14px/16px Arial, Helvetica, sans-serif;
    background: white;
    background: rgba(255,255,255,0.8);
    box-shadow: 0 0 15px rgba(0,0,0,0.2);
    border-radius: 5px;
}
 </style>

</head>
<body>
<div id='map' ></div>
<script type=\"text/javascript\">
    var map = L.map('map', {
        center: [%s, %s],
        zoom: %s,
        zoomAnimation: false,
        zoomSnap: 0.1,
    });

    L.tileLayer(%s, {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

"""

    # If ANSS origin data exists this will be set to true to draw its location as a star icon on the map.
    if draw_anss_marker:
        preamble = preamble + """
    var starIcon = L.icon( {
       iconSize:     [16, 16],
       iconUrl: 'https://raw.githubusercontent.com/usgs/earthquake-eventpages/master/src/assets/star.png'});
    L.marker([%s, %s], {icon: starIcon, title:'Earthquake Epicenter'}).addTo(map);
"""

    preamble = preamble + """
    L.circleMarker([%s, %s], {radius: 10, color: 'black', fillColor: 'black', fillOpacity: 1, opacity: 1}).addTo(map);
    L.control.scale({position: 'bottomright'}).addTo(map);
"""

    # Set zoom level of map based on magnitude
    zoom = 7
    if float(mag) < map_change_mag_threshold:
        zoom = 9

    # Fill Javascript string with the proper values.
    if draw_anss_marker:
        f.write(preamble % (title, anss_lat, anss_lon, zoom, MAP_PROVIDER, anss_lat, anss_lon, init_sa_lat, init_sa_lon))
    else:
        f.write(preamble % (title, anss_lat, anss_lon, zoom, MAP_PROVIDER, init_sa_lat, init_sa_lon))

    to_jsi = {
        'marker':'Earthquake Epicenter',
        'marker_lat': anss_lat,
        'marker_lon': anss_lon,
        'circle_lat': init_sa_lat,
        'circle_lon': init_sa_lon,
        'circle_color': 'black',
        'circlefillColor': 'black',
        'opacity': 1,
        'dashArray': '10,6'
    }

    # Get min contour to be displayed (assumes prior contour filtering based on mmi)
    min_mmi_contour = min(initial_contours)

    latlons: str = str([[point.lat, point.lon] for point in min_mmi_contour.polygon])

    preamble = """
    var polygon = L.polygon(%s, {color: '%s', weight: 7, fillColor: 'transparent'}).addTo(map);

    var marker = new L.marker(L.latLng(polygon.getBounds().getSouth(), 0.5*(polygon.getBounds().getEast()+polygon.getBounds().getWest())), {opacity:0.01});

    marker.bindTooltip("MMI %s", {direction: "bottom", permanent: true, sticky: false, className: "tooltip"}).addTo(map);

    """
    f.write(preamble % (latlons, min_mmi_contour.get_intensity_color(), str(min_mmi_contour.mmi)))

    for time_to_s_wave_sec, circle_radii_m in alert_t_radii.items():
        circle_color = time_to_grey(time_to_s_wave_sec)
        fill_color = "transparent"
        if time_to_s_wave_sec == 0.0:
            circle_color = "crimson"
            fill_color = "transparent"
        f.write("var circle = L.circle([%s, %s], {radius: '%s', color: '%s', fillColor: '%s'}); circle.addTo(map);\n" % (anss_lat, anss_lon, circle_radii_m, circle_color, fill_color))

        # label only inner and outer circle
        if time_to_s_wave_sec == 0.0 or time_to_s_wave_sec == list(alert_t_radii.keys())[-1]:
            f.write("var marker = new L.marker([circle.getBounds()._northEast['lat'], %s], { opacity: 0.01 });\n" % anss_lon)
            f.write("marker.bindTooltip('%s s', {direction: 'bottom', permanent: true, sticky: false, className: 'tooltip'}).addTo(map);\n" % time_to_s_wave_sec)

    # Second pass for Summary GeoJSON aka JSON2
    alertcircles = []
    for time_to_s_wave_sec, circle_radii_m in alert_t_radii.items():
        circle_color = time_to_grey(time_to_s_wave_sec)
        fill_color = "transparent"
        if time_to_s_wave_sec == 0.0:
            circle_color = "crimson"
            fill_color = "transparent"
        circle_name = f'{time_to_s_wave_sec} s'
        arrival_time_circle = f'acircle_{time_to_s_wave_sec}'
        runits = "m"
        tunits = "s"
        alertcircles.append(
            [arrival_time_circle, anss_lat, anss_lon, circle_radii_m, runits, time_to_s_wave_sec, tunits, circle_color, fill_color, circle_name]
        )

    # for Summary GeoJSON aka JSON2
    to_jsi[ 'alertcircles' ] =  alertcircles

    postamble = """
    // Zoom animation disabled to avoid imgkit rendering part way through the animation.
    map.fitBounds(circle.getBounds(), options={'animate': false});
</script>
</body>
</html>
    """

    f.write(postamble)
    f.close()


    options = {
        'crop-h': '1024',
        'crop-w': '415',
        'crop-x': '0',
        'crop-y': '0',
        'javascript-delay': '2000',
        'debug-javascript': ''
    }

    '''
    If running in a headless Linux environment where there is no configured
    xserver, enable xvfb (X Virtual Frame Buffer) to simulate a display for
    rendering. Note: This can still fail if a DISPLAY env var is configured,
    but the xserver process is not running.
    '''
    if sys.platform == 'linux' and not os.environ.get('DISPLAY', None):
        print('Headless Linux environment detected. Rendering image via xvfb in absence of a configured xserver.')
        options['xvfb'] = '' # USE xvfb-run to execute the report creation instead   # GB


    imageFile = os.path.join(output_dir, "EventImage_a.jpg")

    print(f'imgkit.from_file args {filename} {imageFile} {options}')
    imgkit.from_file(filename, imageFile, options=options)

    return imageFile, to_jsi


def buildPolygonMap(
        mag: float,
        ANSSlat: float,
        ANSSlon: float,
        map_change_mag_threshold: float,
        initial_contours: GMContour,
        peak_contours: GMContour,
        final_contours: GMContour,
        drawANSSMarker: bool = True,
        outputDir: str = "."
    ):
    """
    :param mag: ShakeAlert initial message magnitude
    :param ANSSlat: ANSS regional network lat
    :param ANSSlon: ANSS regional network lon
    :param map_change_mag_threshold: Mag threshold where map zoom will be increased.
    :param drawANSSMarker: Set to false if ANSS data is not given.
    :param outputDir: Output directory path-like object
                      where html output is stored.
    :return: Path to created image file created from html intermediate and JSON polygon values.
    :rtype: tuple[str, dict[str, Any]]
    """
    filename = os.path.join(outputDir, str('EventSummary_b.html'))
    to_jsf = {}      # dict to return bits for the JSON2

    title = "Event Summary"

    # Open html file to start writing our Intensity Polygon Map.
    f = open(filename,'w')

    preamble = """
<!DOCTYPE html>
<html>
<head>
<title>%s</title>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0">
 <link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.2/dist/leaflet.css"
   integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ=="
   crossorigin=""/>
 <script src="https://unpkg.com/leaflet@1.3.2/dist/leaflet.js"
   integrity="sha512-2fA79E27MOeBgLjmBrtAgM/20clVSV8vJERaW/EcnnWCVGwQRazzKtQS1kIusCZv1PtaQxosDZZ0F1Oastl55w=="
   crossorigin=""></script>
 <style type="text/css">
 #map { width: 400px; height: 600px; }
 .tooltip {
  all: revert;
  font-size: 16px;
  font-weight: 700;
  background-color: none;
  border-color: none;
  background: none;
  box-shadow: none;
  fillColor: none;
  fillOpacity: 0;
  border: none;
  margin: 0px;
  fill: false;

 }
 .info {
    padding: 6px 8px;
    font: 14px/16px Arial, Helvetica, sans-serif;
    background: white;
    background: rgba(255,255,255,0.8);
    box-shadow: 0 0 15px rgba(0,0,0,0.2);
    border-radius: 5px;
}
 </style>

</head>
<body>
<div id='map' ></div>
<script type=\"text/javascript\">
    var map = L.map('map', {
        center: [%s, %s],
        zoom: %s,
        zoomAnimation: false,
        zoomSnap: 0.1,
    });

    L.tileLayer(%s, {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Get bounding box of largest polygon on map.
    function getLargestPolyBounds() {
        var max_poly_bounds = null;
        var max_poly_width = 0;

        // Nested function to check if a polygon layer has the running max bounding box size.
        // Updates vars max_poly_width and max_poly_bounds if greater than their current values.
        function check_layer_bounds(layer) {
            if(layer instanceof(L.Polygon)) {
                var bounds = layer.getBounds();
                var w_point = new L.LatLng(bounds.getNorth(), bounds.getWest());
                var e_point = new L.LatLng(bounds.getNorth(), bounds.getEast());

                var poly_width = w_point.distanceTo(e_point);
                if(poly_width > max_poly_width) {
                    max_poly_width = poly_width;
                    max_poly_bounds = bounds;
                }
            }
        }

        // Run layer bounds check on each layer in the map.
        map.eachLayer(check_layer_bounds);

        return max_poly_bounds;
    }

"""
    if drawANSSMarker:
        preamble = preamble + """
    var starIcon = L.icon( {
       iconSize:     [16, 16],
       iconUrl: 'https://raw.githubusercontent.com/usgs/earthquake-eventpages/master/src/assets/star.png'});

    L.marker([%s, %s], {icon: starIcon, title:'Earthquake Epicenter'}).addTo(map);

"""

    preamble = preamble + """
	L.control.scale({position: 'bottomright'}).addTo(map);
"""

    # Set zoom level based on mag.
    zoom = 7.5
    if float(mag) < map_change_mag_threshold:
        zoom = 9

    # Begin init alert poly processing
    if drawANSSMarker:
        f.write(preamble % (title, ANSSlat, ANSSlon, zoom, MAP_PROVIDER, ANSSlat, ANSSlon))
    else:
        f.write(preamble % (title, ANSSlat, ANSSlon, zoom, MAP_PROVIDER))

    # Add ANSS marker to dict that will feed the Summary JSON output
    to_jsf = {'marker':'Earthquake Epicenter', 'marker_lat': ANSSlat, 'marker_lon': ANSSlon,
             'dashArray': '10,6'}

    # dashed lines are too tricky for our readers
    # dashedLineOption = ", dashArray: '10,6'"
    dashedLineOption = ""

    #--- DEBUG ---
    for gm_contour in initial_contours:
        yy = len(gm_contour.polygon)
        print("DEBUG2 PyEvent octagon check %d poly: %s" % (yy, gm_contour.polygon))
    #--- DEBUG ---

    # Iterate through polygons sorted ascending MMI
    for gm_contour in initial_contours:
        # Get latlon string used by leaflet
        latlons: str = str([[point.lat, point.lon] for point in gm_contour.polygon])
        preamble = """
    var polygon = L.polygon(%s, {color: '%s', weight: 7, fillColor: 'transparent'%s}).addTo(map);

    var marker = new L.marker(L.latLng(polygon.getBounds().getSouth(), 0.5*(polygon.getBounds().getEast()+polygon.getBounds().getWest())), {opacity:0.01});

    marker.bindTooltip("Initial MMI %s", {direction: "bottom", permanent: true, sticky: false, className: "tooltip"}).addTo(map);

    """
    # End init alert poly processing


    # Begin final alert poly processing
    # CLEANUP: k1, k2 = mmiToShow(len(final_octagon_coords))
    final_names = []
    for gm_contour in final_contours:
        final_names.append("MMI "+ str(gm_contour.mmi))
    # End final alert poly processing


    # Begin peak mag alert poly processing
    peak_names = []

    peak_sa_contour_mmi_ls: List[int] = [contour.mmi for contour in peak_contours]

    # Minimum/outermost MMI contour that will be labeled on intensity map.
    outer_contour_label_mmi: int = min(peak_sa_contour_mmi_ls)

    # Maximum/innermost MMI contour that will be labeled on intensity map.
    inner_contour_label_mmi: Optional[int] = None
    if len(peak_contours) >= 2 and len(peak_contours) < 4:
        inner_contour_label_mmi = outer_contour_label_mmi + 1
    elif len(peak_contours) >= 4:
        inner_contour_label_mmi: Optional[int] = max(peak_sa_contour_mmi_ls)
        inner_contour_label_mmi = outer_contour_label_mmi + 2

    for gm_contour in peak_contours:
        latlons: str = str([[point.lat, point.lon] for point in gm_contour.polygon])
        preamble = """
    var polygon = L.polygon(%s, {color: '%s', weight: 7, fillColor: 'transparent'}).addTo(map);
    """
        f.write(preamble % (latlons, gm_contour.get_intensity_color()))

        if gm_contour.mmi == outer_contour_label_mmi or gm_contour.mmi == inner_contour_label_mmi:
            preamble = """
    var marker = new L.marker(L.latLng(polygon.getBounds().getSouth(), 0.5*(polygon.getBounds().getEast()+polygon.getBounds().getWest())), {opacity:0.01});
    marker.bindTooltip("MMI %s", {direction: "bottom", permanent: true, sticky: false, className: "tooltip"}).addTo(map);
    """
            f.write(preamble % (gm_contour.mmi))

        peak_names.append("MMI "+ str(gm_contour.mmi))
    # End peak alert polygon processing

    postamble = """
    // Zoom animation disabled to avoid imgkit rendering part way through a zoom animation.
    map.fitBounds(getLargestPolyBounds(), options={'animate': false});
</script>
</body>
</html>
    """

    # Write postamble to Intensity Polygon Map HTML to file and close it.
    f.write(postamble)
    f.close()

    options = {
        'crop-h': '1024',
        'crop-w': '415',
        'crop-x': '0',
        'crop-y': '0',
        'javascript-delay': '2000',
        'debug-javascript': ''
    }

    # If running in headless linux environment use xvfb instead of xserver.
    if sys.platform == 'linux' and not os.environ.get('DISPLAY', None):
        print('Headless Linux environment detected. Rendering image via xvfb in absence of a configured xserver.')
        options['xvfb'] = '' # USE xvfb-run to execute the report creation instead   # GB

    imageFile = os.path.join(outputDir, "EventImage_b.jpg")

    imgkit.from_file(filename, imageFile, options=options)

    return imageFile, to_jsf
