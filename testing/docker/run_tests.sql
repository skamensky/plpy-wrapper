do
$$
from plpy_wrapper import PLPYWrapper
#testing is loaded as a package during docker run
import tests
import io
from contextlib import redirect_stdout,redirect_stderr
import coverage
import unittest
import traceback
from pathlib import Path
import os

tests.PLPY_WRAPPER = PLPYWrapper(globals())

runner = unittest.TextTestRunner()
suite = unittest.defaultTestLoader.loadTestsFromModule(tests)

coverage_config_file_path = Path(os.environ['DOCKER_DIR_FROM_HOST'],'.coveragerc')

cov = coverage.Coverage(config_file=coverage_config_file_path)
cov.start()
stderr_file = io.StringIO()
stdout_file = io.StringIO()
with redirect_stderr(stderr_file):
    with redirect_stdout(stdout_file):
        unittest.TextTestRunner().run(suite)
cov.stop()

stderr_data = stderr_file.getvalue()
stdout_data = stdout_file.getvalue()
if stderr_data or stdout_data:
    unitest_output = '\nunittest stderr and/or stdout:\n'
    if stderr_data:
        unitest_output+='unittest stderr:\n'+stderr_data
    if stdout_data:
        unitest_output+='unittest stdout:\n'+stdout_data
    plpy.info(unitest_output)

cov.save()
report_file ='/tmp/coverage.json'
coverage_output = 'TEST COVERAGE RESULTS:\n'
try:
    cov.xml_report(outfile=report_file)
    coverage_output+=open(report_file).read()
except coverage.misc.NoSource:
    coverage_output+=traceback.format_exc()
plpy.info(coverage_output)
$$ language plpython3u;
