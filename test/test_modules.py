"""
Post Alert Summary unit test module module containing all unittest.Test*
classes used when testing python modules found in the PAS bin directory.

Run Instructions (python unittest):
    # If running from project top level dir, run the following command:
    python -m unittest discover bin

Run Instructions (pytest):
    pytest -v test/tests.py
"""
import os
import sys
import importlib
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, List
from unittest import TestCase

import pytest


BASE_DIR = Path(os.path.realpath(__file__)).parent.parent
config = ConfigParser()
config.read(os.path.join(BASE_DIR, 'params/PostEventSummaryProperties.cfg'))


def load_modules(module_names, src_dir='.'):
    '''
    Loads a list of python modules by name from a specified directory so
    they can be imported into the current runtime context.
    :param module_names: List of python module names
    :type src_dir: Path to dir containing python module files (.py)
    :type src_dir: str or Path
    '''
    if not isinstance(src_dir, Path):
        src_dir = Path(src_dir)

    # Load all modules specified in module names list from the bin dir.
    for mod_name in module_names:
        # Create new module object from .py file.
        spec = importlib.util.spec_from_file_location(
            mod_name,
            src_dir.joinpath(mod_name + '.py'),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Add new module to system modules for the current runtime context.
        sys.modules[mod_name] = module


# Load modules (required to workaround illegal directory name "bin")
load_modules(
    module_names=[
        'utils',
        'PyCities',
        'EQCalculations',
        'ShakeAlertParser',
        'PyEventImage',
        'PDFCreate'
    ],
    src_dir=Path(__file__).parent.parent.joinpath('bin')
)


# Import modules loaded by call to load_modules()
import EQCalculations
from ShakeAlertParser import GMContour, Coord
from PDFCreate import GMContourFilter
from PyEventImage import get_alert_circle_params


@pytest.fixture
def contours():
    contours: List[GMContour] = [
        GMContour(
            mmi=6,
            polygon=[
                Coord(lat='40.4423', lon='-123.9823'),
                Coord(lat='40.4284', lon='-123.9383'),
                Coord(lat='40.3949', lon='-123.9200'),
                Coord(lat='40.3614', lon='-123.9383'),
                Coord(lat='40.3475', lon='-123.9823'),
                Coord(lat='40.3614', lon='-124.0263'),
                Coord(lat='40.3949', lon='-124.0446'),
                Coord(lat='40.4284', lon='-124.0263'),
                Coord(lat='40.4423', lon='-123.9823')],
            pga=82.9696,
            pgv=6.6981
        ),
        GMContour(
            mmi=5,
            polygon=[
                Coord(lat='40.5082', lon='-123.9823'),
                Coord(lat='40.4749', lon='-123.8770'),
                Coord(lat='40.3948', lon='-123.8336'),
                Coord(lat='40.3148', lon='-123.8773'),
                Coord(lat='40.2816', lon='-123.9823'),
                Coord(lat='40.3148', lon='-124.0873'),
                Coord(lat='40.3948', lon='-124.1310'),
                Coord(lat='40.4749', lon='-124.0876'),
                Coord(lat='40.5082', lon='-123.9823')
            ],
            pga=44.5296,
            pgv=3.0888
        ),
        GMContour(
            mmi=4,
            polygon=[
                Coord(lat='40.8430', lon='-123.9823'),
                Coord(lat='40.7110', lon='-123.5643'),
                Coord(lat='40.3934', lon='-123.3940'),
                Coord(lat='40.0773', lon='-123.5682'),
                Coord(lat='39.9468', lon='-123.9823'),
                Coord(lat='40.0773', lon='-124.3964'),
                Coord(lat='40.3934', lon='-124.5706'),
                Coord(lat='40.7110', lon='-124.4003'),
                Coord(lat='40.8430', lon='-123.9823')
            ],
            pga=12.8729,
            pgv=0.6449
        ),
        GMContour(
            mmi=3,
            polygon=[
                Coord(lat='41.6717', lon='-123.9823'),
                Coord(lat='41.2916', lon='-122.7807'),
                Coord(lat='40.3828', lon='-122.3060'),
                Coord(lat='39.4861', lon='-122.8125'),
                Coord(lat='39.1181', lon='-123.9823'),
                Coord(lat='39.4861', lon='-125.1521'),
                Coord(lat='40.3828', lon='-125.6586'),
                Coord(lat='41.2916', lon='-125.1839'),
                Coord(lat='41.6717', lon='-123.9823')
            ],
            pga=2.9142,
            pgv=0.1347),
        GMContour(
            mmi=2,
            polygon=[Coord(lat='42.8078', lon='-123.9823'),
                     Coord(lat='42.0786', lon='-121.6837'),
                     Coord(lat='40.3517', lon='-120.8155'),
                     Coord(lat='38.6679', lon='-121.7972'),
                     Coord(lat='37.9820', lon='-123.9823'),
                     Coord(lat='38.6679', lon='-126.1674'),
                     Coord(lat='40.3517', lon='-127.1491'),
                     Coord(lat='42.0786', lon='-126.2809'),
                     Coord(lat='42.8078', lon='-123.9823')
            ],
            pga=0.7926,
            pgv=0.0365
        )
    ]
    return contours


def test_high_mag_GMContourFilter(contours):
    # Setup filter to be tested
    mag_threshold=float(config.get('THRESHOLDS', 'MagMapChange'))
    min_mmi_small_event=float(config.get('THRESHOLDS', 'MMISmall'))
    min_mmi_large_event=float(config.get('THRESHOLDS', 'MMIAlert'))
    gmc_filter = GMContourFilter(
        mag_threshold,
        min_mmi_small_event,
        min_mmi_large_event
    )

    # Define high mag (mag where an alert will be sent to pubic)
    event_mag = 5.0
    expected_min_mmi = 4
    filtered_contours: List[GMContour] = gmc_filter(contours, event_mag)
    for contour in filtered_contours:
        assert contour.mmi >= expected_min_mmi


def test_low_mag_GMContourFilter(contours):
    # Setup filter to be tested
    mag_threshold=float(config.get('THRESHOLDS', 'MagMapChange'))
    min_mmi_small_event=float(config.get('THRESHOLDS', 'MMISmall'))
    min_mmi_large_event=float(config.get('THRESHOLDS', 'MMIAlert'))
    gmc_filter = GMContourFilter(
        mag_threshold,
        min_mmi_small_event,
        min_mmi_large_event
    )

    # Define high mag (mag where an alert will be sent to pubic)
    event_mag = 4.9
    expected_min_mmi = 3
    filtered_contours: List[GMContour] = gmc_filter(contours, event_mag)
    for contour in filtered_contours:
        assert contour.mmi >= expected_min_mmi


def test_get_alert_circle_params():

    # Args taken from M5 event on 20230101
    alert_t_radii = get_alert_circle_params(
        init_sa_mag=5.3,
        init_sa_to_anss_dt=7.971,
        s_wave_velocity=3.55,
        anss_depth=27.77,
    )

    expected_radii: Dict[float, int] = {
        0.0: 5436,
        10.0: 57435,
        20.0: 95334
    }

    assert alert_t_radii.keys() == expected_radii.keys()
    rounded_radii = [int(r) for r in alert_t_radii.values()]
    assert rounded_radii == list(expected_radii.values())


class TestEQCalculations(TestCase):
    """
    Test functions found in EQCalculations module.
    """
    def test_round_half_up_whole_number(self):
        """
        Test rounding up to whole number using "half up" strategy
        for tie breaking. Uses default precision value of 0 when
        no precision value given.
        """
        self.assertEqual(
            str(EQCalculations.round_half_up(4.35)),
            '4.0'
        )

    def test_round_half_up_tenths(self):
        """
        Test rounding using "half up" strategy and precision value of 1.
        """

        precision: int = 1

        # Check int values.
        self.assertEqual(
            str(EQCalculations.round_half_up(0, precision)),
            '0.0'
        )
        self.assertEqual(
            str(EQCalculations.round_half_up(1, precision)),
            '1.0'
        )

        # Check rounding of positive numbers
        self.assertEqual(
            str(EQCalculations.round_half_up(4.35, precision)),
            '4.4'
        )
        self.assertEqual(
            str(EQCalculations.round_half_up(4.25, precision)),
            '4.3'
        )

        # Check negative number rounding
        self.assertEqual(
            str(EQCalculations.round_half_up(-4.35, precision)),
            '-4.3'
        )
        self.assertEqual(
            str(EQCalculations.round_half_up(-4.45, precision)),
            '-4.4'
        )
        self.assertEqual(
            str(EQCalculations.round_half_up(-4.25, precision)),
            '-4.2'
        )

    def test_round_half_up_ten_thousandths(self):
        """
        Test rounding using "half up" strategy and precision value of 4.
        """
        precision: int = 4
        self.assertEqual(
            str(EQCalculations.round_half_up(0, precision)),
            '0.0'
        )
        self.assertEqual(
            str(EQCalculations.round_half_up(1, precision)),
            '1.0'
        )
        self.assertEqual(
            str(EQCalculations.round_half_up(-31.12345, precision)),
            '-31.1234'
        )
        self.assertEqual(
            str(EQCalculations.round_half_up(100.12345, precision)),
            '100.1235'
        )
