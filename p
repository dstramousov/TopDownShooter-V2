rm -Rf ./prepared_map/*
PYTHONPATH=src python3 -m topdown_shooter --map ../TopDownMapGen/output --prepare-map --out ./prepared_map
