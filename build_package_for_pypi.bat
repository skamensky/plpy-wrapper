REM retrieve version number from setupfile
python ./setup.py --version > tmpFile
set /p VERSION= < tmpFile
del tmpFile

REM build locally
python setup.py build sdist bdist
REM upload to pypi
python -m twine upload --username %PYPI_USERNAME% --password %PYPI_PASS% dist/plpy-wrapper-%VERSION%.tar.gz