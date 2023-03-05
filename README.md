#### Requirements ####
Python 3
Python libraries (See "Installing pip Packages" below):  reportlab, imgkit, shapely, folium, obspy
Linux packages:  wkhtmltopdf, xvfb (yum recommended for install on RHEL/CentOS)

**Installing pip Packages:**
Packages installed via pip are tracked by the requirements.txt file included with the code.
To install all pip packages listed in requirements.txt use the command from the top level dir:
```bash
$ pip install -r requirements.txt
```

#### Run Instructions ####
To create a report run PDFCreate.py and use option "-f" with a file path to the JSON or XML SA message you would like to parse.  Execute from the "bin" folder as so:  
```bash
python3 PDFCreate.py -f $PATHTOFILE.xml -o $OUTPUT_DIR
```
6/4/2021 example: `python3 bin/PDFCreate.py -f test_files/WEA_sent.json -o output`

Will produce a PDF with a file name like PostAlertSummary_EVENTID_DATE&TIME.pdf in the "bin" folder

To test an event, run the above at a command prompt with a valid path to either a JSON adhering to our specifications or a SA XML message.  The SA message will require the appropriate ANSS values taken from the ORIGIN section of the corresponding event pages at earthquake.usgs.gov updated in the PostEventSummaryProperties.cfg.  Examples of both file types have been provided.  For instance:  test/SA_LaVerneEvent08282018.xml and test/2014_LaHabra.json

Note:  If you are getting the "PermissionError: [Errno 13] Permission denied: b" error, try adding
xvfb-run to the python3 execution


#### Running Test Cases ####
The pytest pypi package is required for running test cases.
A pytest installation is only required for testing, and can be skipped for production deployments.

Note: Make sure all requirements are installed before running tests. Missing requirements will cause test cases to fail.

**Installing pytest:**
```bash
$ pip install pytest
```
**Upgrading an existing pytest install:**
```bash
$ pip install --upgrade pytest
```

From the project top level directory (the one that contains the bin dir):
```bash
$ pytest -v test/*.py
```

**Passing tests will produce the following output:**
```bash
==================================================== test session starts ====================================================
platform linux -- Python 3.8.5, pytest-6.2.4, py-1.10.0, pluggy-0.13.1 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/ghartman/workspace/PostEventSummary
collected 9 items

test/test_end2end.py::test_e2e[20200911_M4.2_lonepine.json] PASSED                                                           [ 11%]
test/test_end2end.py::test_e2e[peak_mag_w_anss.json] PASSED                                                                  [ 22%]
test/test_end2end.py::test_e2e[WEA_sent.json] PASSED                                                                         [ 33%]
test/test_end2end.py::test_e2e[rounding_test.json] PASSED                                                                    [ 44%]
test/test_end2end.py::test_e2e[SYN_SaltonSea_M7.8_contour.json] PASSED                                                       [ 55%]
test/test_end2end.py::test_e2e[event_1635.json] PASSED                                                                       [ 66%]
test/test_end2end.py::test_e2e[20201001_M4.9_westmorland.json] PASSED                                                        [ 77%]
test/test_end2end.py::test_e2e[WEA_no_anss.json] PASSED                                                                      [ 88%]
test/test_end2end.py::test_e2e[peak_mag_no_anss.json] PASSED                                                                 [100%]

==================================================== 9 passed in 16.29s =====================================================
```


**Failing tests will produce output similar to the following:**
```bash
============================= test session starts ==============================
platform linux -- Python 3.8.5, pytest-6.2.4, py-1.10.0, pluggy-0.13.1 -- /home/aturing/workspace/sa_work/PostEventSummary/venv/bin/python
cachedir: .pytest_cache
rootdir: /home/aturing/workspace/sa_work/PostEventSummary
plugins: parallel-0.1.0
collecting ... collected 9 items

test/test_end2end.py::test_e2e[20200911_M4.2_lonepine.json] FAILED              [ 11%]
test/test_end2end.py::test_e2e[peak_mag_w_anss.json] PASSED                     [ 22%]
test/test_end2end.py::test_e2e[WEA_sent.json] PASSED                            [ 33%]
test/test_end2end.py::test_e2e[rounding_test.json] PASSED                       [ 44%]
test/test_end2end.py::test_e2e[SYN_SaltonSea_M7.8_contour.json] PASSED          [ 55%]
test/test_end2end.py::test_e2e[event_1635.json] PASSED                          [ 66%]
test/test_end2end.py::test_e2e[20201001_M4.9_westmorland.json] PASSED           [ 77%]
test/test_end2end.py::test_e2e[WEA_no_anss.json] PASSED                         [ 88%]
test/test_end2end.py::test_e2e[peak_mag_no_anss.json] PASSED                    [100%]

=================================== FAILURES ===================================
____________________ test_e2e[20200911_M4.2_lonepine.json] _____________________

input_file = PosixPath('/home/aturing/workspace/sa_work/PostEventSummary/test/test_files/20200911_M4.2_lonepine.json')

    @pytest.mark.parametrize('input_file', test_data, ids=get_test_input_filename)
    def test_e2e(input_file):
        # Create output dir named after test case (minus its .json extension).
        outdir = Path(__file__).parent.joinpath(
            f"test_output_{input_file.name.split('.')[0]}"
        )
        if outdir.is_dir():
            for path in list(outdir.glob('**/*')):  # Delete all files in test output dir.
                path.unlink(missing_ok=True)
            outdir.rmdir()  # Delete the empty test output dir.
        Path.mkdir(outdir)
        assert outdir.exists() == True, f'Unable to create output dir {outdir}.'
    
        # Run the process.
        pas_proc = subprocess.Popen(
            ['python3', MAIN.resolve(), '-f', input_file, '-o', outdir]
        )
        pas_proc.wait()
    
        # Check test results.
>       assert pas_proc.returncode == 0
E       assert 1 == 0
E         +1
E         -0

test/tests.py:37: AssertionError
----------------------------- Captured stderr call -----------------------------
Traceback (most recent call last):
  File "/home/aturing/workspace/sa_work/PostEventSummary/bin/PDFCreate.py", line 1197, in <module>
    SAMessageValues = ShakeAlertParser.ParseJSONFile(filename)  # source is JSON file
  File "/home/aturing/workspace/sa_work/PostEventSummary/bin/ShakeAlertParser.py", line 55, in ParseJSONFile
    data = json.load(f)
  File "/usr/lib/python3.8/json/__init__.py", line 293, in load
    return loads(fp.read(),
  File "/usr/lib/python3.8/json/__init__.py", line 357, in loads
    return _default_decoder.decode(s)
  File "/usr/lib/python3.8/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/usr/lib/python3.8/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 2 column 1 (char 2)
=========================== short test summary info ============================
FAILED test/tests.py::test_e2e[20200911_M4.2_lonepine.json] - assert 1 == 0
========================= 1 failed, 8 passed in 14.97s =========================
```
