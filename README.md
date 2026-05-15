# TopDownShooter V.2

Initial runtime foundation for loading a generated TopDownMapGen map package.

## Current scope

Version `0.0.6` supports map package inspection, a minimal render window, camera foundation, and a runtime debug overlay:

- reads `_manifest.json`;
- reads `validation_report.json`;
- reads `tactical_map.json`;
- performs minimal runtime validation;
- builds an internal `RuntimeMap`;
- prints a concise inspection summary;
- opens a minimal raylib window;
- centers a clamped camera on the map start tile;
- toggles a debug overlay with runtime, map, camera, mouse, tactical, and validation data.

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

Window settings, debug overlay settings, and control bindings are stored in the packaged runtime config:

```text
src/topdown_shooter/config/default_runtime_config.json
```

Default controls:

```text
Esc: close runtime window
Ctrl+D: toggle debug overlay
```

## Camera foundation

The renderer uses a small camera rig that centers on the generated start tile and clamps the camera target to map bounds. Window size, zoom, camera flags, and control bindings are stored in the packaged runtime config instead of being hardcoded in rendering systems.

## Debug overlay

The debug overlay is a translucent runtime panel drawn above the map. It is disabled by default and can be toggled with the configured debug key chord. The overlay uses two aligned columns: labels are drawn in white and values in orange for readability. It shows FPS, window parameters, map package metadata, map dimensions, camera target, mouse screen/world/tile coordinates, tile data under the cursor, tactical entity counts, validation status, warning codes, and active controls.
