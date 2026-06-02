#!/usr/bin/env bash
PYTHONPATH=src python3 -m topdown_shooter --map prepared_map --run --renderer 2d --visual-render auto

#PYTHONPATH=src python3 -m topdown_shooter --map ../TopDownMapGen/output --run
#PYTHONPATH=src python3 -m topdown_shooter --map prepared_map --run --renderer 2d --visual-render legacy