PYTHONPATH=src python3 -m compileall src tests
PYTHONPATH=src python3 -m pytest -q
