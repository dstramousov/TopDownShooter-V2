# TopDownShooter V.2

Initial runtime foundation for loading a generated TopDownMapGen map package.

## Current scope

Version `0.0.4` supports map package inspection and a minimal render window:

- reads `_manifest.json`;
- reads `validation_report.json`;
- reads `tactical_map.json`;
- performs minimal runtime validation;
- builds an internal `RuntimeMap`;
- prints a concise inspection summary;
- opens a minimal raylib window;
- centers a clamped camera on the map start tile.

The shooter runtime does not import or call TopDownMapGen. The map generator remains a separate project.

## Usage

```bash
python3 -m topdown_shooter --map ./maps/current --inspect-map
```

or, after installing the package:

```bash
topdown-shooter --map ./maps/current --inspect-map
```


## Run map renderer

The minimal renderer opens a raylib window and draws the loaded map package:

```bash
PYTHONPATH=src python3 -m topdown_shooter --map ../TopDownMapGen/out --run
```

Window settings and control bindings are stored in the packaged runtime config:

```text
src/topdown_shooter/config/default_runtime_config.json
```

## Camera foundation

The renderer uses a small camera rig that centers on the generated start tile and clamps the camera target to map bounds. Window size, zoom, camera flags, and control bindings are stored in the packaged runtime config instead of being hardcoded in rendering systems.
