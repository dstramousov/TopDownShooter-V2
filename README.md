# TopDownShooter V.2

Initial runtime foundation for loading a generated TopDownMapGen map package.

## Current scope

Version `0.0.1` supports only map package inspection:

- reads `_manifest.json`;
- reads `validation_report.json`;
- reads `tactical_map.json`;
- performs minimal runtime validation;
- builds an internal `RuntimeMap`;
- prints a concise inspection summary.

The shooter runtime does not import or call TopDownMapGen. The map generator remains a separate project.

## Usage

```bash
python3 -m topdown_shooter --map ./maps/current --inspect-map
```

or, after installing the package:

```bash
topdown-shooter --map ./maps/current --inspect-map
```
