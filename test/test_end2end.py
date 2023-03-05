"""
Post Alert Summary End-2-End tests.
"""
import json
import pytest
import subprocess
from pathlib import Path

# Path to test input json files.
TEST_INPUT_DIR = Path(__file__).parent / 'test_files'
MAIN = Path(__file__).parent.parent / 'bin' / 'PDFCreate.py'

# Create test_data list containing all file paths found in input file dir.
test_data = [f.resolve() for f in TEST_INPUT_DIR.glob('*.json')]

@pytest.fixture
def noclean(request):
    """
    Pytest fixture function that requests the noclean CLI flag.
    """
    return request.config.getoption("--noclean")


def get_test_input_filename(path):
    """
    Returns a test input filename to be used as the id of
    a parameterized test case.
    """
    return path.name

def cleanup_output_files(outdir):
    """
    Warning: Deletes the given output directory recursively. Use case is the
    same as 'rm -rf outdir'.
    """
    if not outdir:
        raise ValueError(
            'Parameter "outdir" must be defined defined as a Pathlike object.'
        )
    if outdir.is_dir():
        for path in list(outdir.glob('**/*')):
            path.unlink(missing_ok=True)
        outdir.rmdir()  # Delete the empty test output dir.


@pytest.mark.parametrize('input_file', test_data, ids=get_test_input_filename)
def test_e2e(input_file, noclean):
    """
    End-2-End test case that runs the PDFCreate script in a subprocess.
    This test case will be run for each json file found in the test_files
    dir. Passes as long as the PDFCreate script returns 0 and produces the
    expected files. Files will be removed after run completes.
    """
    # Create output dir named after test case (minus its .json extension).
    outdir = Path(__file__).parent.joinpath(
        f"test_output_{input_file.name.split('.')[0]}"
    )

    # Clean-up any output files that might be left over from last run.
    cleanup_output_files(outdir)

    Path.mkdir(outdir)
    assert outdir.exists() == True, f'Unable to create output dir {outdir}.'

    # Run the process.
    pas_proc = subprocess.Popen(
        ['python3', MAIN.resolve(), '-f', input_file, '-o', outdir]
    )
    pas_proc.wait()

    # Check test results.
    assert pas_proc.returncode == 0

    # Expected output files.
    summary_pdf = outdir.joinpath('PostEventSummary.pdf')
    summary_geojson = outdir.joinpath('PostEventSummary.json')
    map_img_a = outdir.joinpath('EventImage_a.jpg')
    map_img_b = outdir.joinpath('EventImage_b.jpg')

    assert summary_pdf.exists() == True, f'{summary_pdf} not found.'
    assert map_img_a.exists() == True, f'{map_img_a} not found.'
    assert map_img_b.exists() == True, f'{map_img_b} not found.'

    if 'no_anss' in input_file.name:
        assert summary_pdf.exists() == True, f'{summary_geojson} not found.'

    json.loads(input_file.read_text())

    # Cleanup old test output.
    if noclean == False:
        cleanup_output_files(outdir)
