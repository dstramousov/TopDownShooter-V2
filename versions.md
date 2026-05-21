# Versions

## v0.0.0 -> v0.0.1

- Added initial project skeleton for TopDownShooter V.2.
- Added CLI entry point with `--map <package_dir>` and `--inspect-map`.
- Added map package loading for `_manifest.json`, `validation_report.json`, and `tactical_map.json`.
- Added minimal runtime validation and `RuntimeMap` construction.
- Added inspection summary output.


## v0.0.1 -> v0.0.2

- Improved human-readable CLI diagnostics for invalid map package paths.
- Added clear recovery hints when required map package files are missing.
- Added validation for missing `--map` paths and file paths passed instead of directories.


## v0.0.2 -> v0.0.3

- Added `--run` CLI mode for a minimal raylib map render window.
- Added packaged runtime configuration for window settings and control bindings.
- Rendered generated maps from `RuntimeMap` with simple tile colors.
- Centered the initial camera on the map start tile.


## v0.0.3 -> v0.0.4

- Added a camera foundation with `CameraRig` and typed camera state.
- Centered the runtime camera on the generated start tile through coordinate helpers.
- Added camera clamping against map bounds.
- Extended runtime config with camera clamp and reserved inertia/lookahead settings.
- Reduced raylib INFO log noise before window initialization.


## v0.0.4 -> v0.0.5

- Added a configurable runtime debug overlay toggled with `Ctrl+D`.
- Added overlay diagnostics for FPS, window, map package metadata, camera, mouse, tactical counts, validation status, and controls.
- Added configurable debug overlay panel settings and key chord bindings.
- Kept debug overlay separate from map rendering and camera logic.


## v0.0.5 -> v0.0.6

- Reworked the debug overlay into two aligned columns.
- Drew overlay labels in white and values in orange for better readability.
- Expanded configurable overlay layout settings for panel width, section spacing, column gap, and label width.
- Kept the overlay as a debug-only layer without changing gameplay, camera behavior, or map rendering.


## v0.0.6 -> v0.0.7

- Added configurable map-viewer camera controls for panning, zooming, and reset-to-start.
- Added camera zoom limits, zoom step, and movement speed to runtime config.
- Rebuilt the raylib camera each frame from `CameraRig` state so debug overlay mouse/world/tile coordinates follow camera changes.
- Updated debug overlay controls output to include pan, zoom, and reset bindings.


## v0.0.7 -> v0.0.8

- Added an initial player runtime state spawned at the generated start tile.
- Added a simple player marker renderer drawn above the map.
- Added player position and marker diagnostics to the debug overlay.
- Added player marker display settings to the packaged runtime config.


## v0.0.8 -> v0.0.9

- Reserved `WASD` for future player movement by removing it from map-viewer camera pan bindings.
- Kept map-viewer camera panning on arrow keys through runtime config.
- Added configurable mouse wheel zoom alongside existing `Q`/`E` zoom keys.
- Updated debug overlay and README control descriptions to match the new bindings.


## v0.0.9 -> v0.0.10

- Added configurable WASD player movement.
- Added delta-time based player movement speed to runtime config.
- Added basic tile collision for the player with separate X/Y axis resolution.
- Added player movement and collision diagnostics to the debug overlay.
- Kept camera follow, shooting, enemies, and tactical overlays out of scope.



## v0.0.10 -> v0.0.11

- Added player-follow camera mode enabled by default at runtime.
- Added configurable follow toggle binding to switch between follow and map-viewer camera modes.
- Kept manual pan as a map-viewer action while zoom remains available in both modes.
- Surfaced camera mode and debug overlay font size in the debug overlay diagnostics.
- Documented debug overlay font size as a runtime config setting.


## v0.0.11 -> v0.0.12

- Added smooth/inertial player-follow camera movement.
- Added configurable camera max speed, movement lookahead, and dead-zone radius.
- Added camera diagnostics for desired target, velocity, lookahead offset, and dead-zone size.
- Kept mouse aim, shooting, enemies, tactical overlays, and cinematic camera out of scope.


## v0.0.12 -> v0.0.13

- Removed the obsolete `ANN101` Ruff ignore rule from project configuration.
- Replaced `typing.Any` annotations at the raylib rendering/debug boundary with explicit `object` annotations.
- Replaced the quoted `PlayerState` return annotation with `Self`.
- Kept gameplay, camera behavior, rendering behavior, and map loading unchanged.


## v0.0.13 -> v0.0.14

- Added mouse aim direction state calculated from player position to the world-space cursor.
- Added a configurable aim debug line and marker rendered above the player.
- Added aim direction, angle, and target diagnostics to the debug overlay.
- Kept shooting, projectiles, recoil, enemies, and camera aim-lookahead out of scope.

## v0.0.14 -> v0.0.15

- Increased the default debug overlay panel width so long value strings have more room.
- Increased the default debug overlay label width for cleaner two-column alignment.
- Documented and adjusted the configurable debug overlay background alpha value.
- Kept gameplay, camera, aim, and rendering behavior otherwise unchanged.


## v0.0.15 -> v0.0.16

- Added a `res/fonts/` resource directory for runtime font assets.
- Added configurable debug overlay font path and glyph spacing settings.
- Made the debug overlay load a custom TTF font when available and fall back to the default raylib font otherwise.
- Documented `res/fonts/IBMPlexMono-Regular.ttf` as the expected overlay font path without changing gameplay behavior.

## v0.0.16 -> v0.0.17

- Added configurable aim-direction camera lookahead to player-follow camera mode.
- Added aim camera offset diagnostics to the debug overlay.
- Split current FPS and target FPS into separate debug overlay rows.
- Updated font resource documentation to match `res/fonts/PressStart2P-Regular.ttf`.
- Kept shooting, projectiles, enemies, tactical overlays, and cinematic camera out of scope.

## v0.0.17 -> v0.0.18

- Added a standalone FPS counter that remains visible when the debug overlay is disabled.
- Added visible-tile culling to the map renderer so only camera-visible tiles are drawn each frame.
- Added render diagnostics for visible, drawn, and total tile counts to the debug overlay.
- Added runtime config settings for the standalone FPS counter.
- Kept gameplay, camera behavior, shooting, enemies, and tactical overlays unchanged.

## v0.0.18 -> v0.0.19

- Added a minimal projectile shooting foundation using the existing mouse aim direction.
- Added configurable projectile speed, range, lifetime, radius, and primary fire mouse binding.
- Added projectile update, map collision removal, rendering, and debug overlay projectile statistics.
- Kept enemies, damage, fire rate, recoil, particles, sound, and tactical overlays out of scope.


## v0.0.19 -> v0.0.20

- Added a data-driven weapon database at `res/config/weapons.json`.
- Added default `pistol` weapon settings for fire rate, spread, shots per fire, and projectile parameters.
- Added continuous primary fire while LMB is held, limited by current weapon fire rate.
- Moved projectile spawn parameters from runtime projectile config to current weapon definitions.
- Added weapon diagnostics to the debug overlay while keeping enemies, damage, recoil, ammo, reloads, and sound out of scope.


## v0.0.20 -> v0.0.21

- Added short-lived projectile impact markers when projectiles hit blocked map tiles.
- Added configurable projectile impact marker lifetime and radius.
- Added impact marker rendering and projectile impact diagnostics in the debug overlay.
- Updated the runtime config test to match the current aim debug marker length.
- Kept enemies, damage, particles, sound, recoil, weapon switching, and tactical overlays out of scope.

## v0.0.21 -> v0.0.22

- Added AK-47 as a second data-driven weapon in `res/config/weapons.json`.
- Added weapon slot switching for pistol and AK-47.
- Added magazine ammo, finite/infinite reserve ammo, and reload support.
- Added a configurable player HUD showing health, active weapon, and magazine/reserve ammo.
- Updated debug overlay weapon, ammo, health, and control diagnostics.
- Kept enemies, damage, pickups, recoil, sound, weapon wheel, and tactical overlays out of scope.


## v0.0.22 -> v0.0.23

- Added the missing `src/topdown_shooter/rendering/player_hud.py` module required by the v0.0.22 HUD import.
- Restored runtime startup after the weapon/HUD patch without changing weapon, projectile, camera, or movement behavior.

## v0.0.23 -> v0.0.24

- Added static enemy markers spawned from tactical `enemy_spawn_zones`.
- Added enemy marker rendering above the map and below the player marker.
- Added configurable enemy marker radius through `enemies.marker_radius_px`.
- Added enemy diagnostics to the debug overlay.
- Kept enemy AI, movement, damage, health, and projectile hits out of scope.


## v0.0.24 -> v0.0.25

- Added movement speed modifiers based on walkable tile movement costs.
- Updated the player HUD to use the same configured custom font as the debug overlay.
- Added per-weapon reload durations to `res/config/weapons.json` and runtime reload timing.
- Kept enemy hits, enemy AI, player damage, pickups, recoil, sound, and tactical overlays out of scope.

## v0.0.25 -> v0.0.26

- Added the M134 Minigun as weapon slot 3 with a 1000-round magazine and 2000 reserve rounds.
- Added per-weapon active movement speed multipliers and applied them to player movement.
- Added a compact HUD reload progress bar while a reload is in progress.
- Updated weapon diagnostics to expose reload progress and active weapon movement multipliers.
- Kept enemy hits, enemy AI, player damage, recoil, sound, overheating, and pickups out of scope.


## v0.0.26 -> v0.0.27

- Moved the reload progress bar under the active weapon label in the top/bottom HUD layout.
- Kept reload timing, weapon stats, movement speed modifiers, and combat behavior unchanged.


## v0.0.27 -> v0.0.28

- Added per-weapon projectile damage loaded from `res/config/weapons.json`.
- Added enemy health, projectile-enemy collision, enemy death, and consumed projectiles on hit.
- Added short-lived enemy hit feedback markers distinct from wall impacts.
- Updated enemy and weapon diagnostics with hit, kill, damage, and hit-marker counters.
- Kept enemy AI, enemy movement, player damage, score, pickups, sound, particles, recoil, and overheating out of scope.

## v0.0.28 -> v0.0.29

- Added short enemy hit flash feedback when projectile damage is applied.
- Added temporary enemy health bars for recently damaged enemies.
- Added configurable enemy feedback durations to the runtime config and debug overlay.
- Kept enemy AI, movement, player damage, score, pickups, sound, particles, recoil, and overheating out of scope.


## v0.0.29 -> v0.0.30

- Added enemy facing angles and deterministic fallback directions for spawned enemies.
- Added configurable debug enemy view cones with vision range, angle, and line-of-sight sampling.
- Added enemy perception state: enemies become alerted when they see the player or get hit.
- Updated enemy diagnostics to show alerted enemies and vision settings.
- Kept enemy movement, chase AI, attacks, player damage, sound, and pathfinding out of scope.

## v0.0.30 -> v0.0.31

- Fixed the enemy perception runtime crash caused by passing an out-of-scope collision service variable from the raylib loop.
- Kept enemy behavior, perception rules, weapon behavior, rendering, and gameplay balance unchanged.

## v0.0.31 -> v0.0.32

- Added map-aware smart initial facing for enemies without explicit tactical facing angles.
- Scored candidate facing directions by open walkable space and penalized near-wall directions.
- Added runtime config and debug overlay fields for smart facing probe parameters.
- Kept enemy count, squad spawning, movement, chase AI, patrol routes, and player damage out of scope.

## v0.0.32 -> v0.0.33

- Spawn zones now create deterministic enemy squads instead of a single enemy.
- Added enemy squad placement config: squad size, radius, spacing, global cap, and placement attempts.
- Squad members are placed only on walkable positions with minimum spacing and keep smart initial facing.
- Debug overlay now reports spawned squads and squad placement settings.

## v0.0.33 -> v0.0.34

- Added basic chase movement for alerted enemies.
- Alerted enemies now face and move toward the player with blocked-tile collision.
- Added runtime config and debug overlay values for enemy chase speed and moving enemy count.

## v0.0.34 -> v0.0.35

- Added combat steering for alerted enemies: approach, strafe, and retreat distance bands.
- Added enemy movement tuning values to runtime config and debug overlay.
- Preserved simple blocked-tile collision without adding pathfinding, attacks, or player damage.

## v0.0.35 -> v0.0.36

- Improved alerted enemy combat movement with distance-aware approach/strafe/retreat weights.
- Added smoothed enemy movement direction to reduce abrupt steering changes.
- Added aggressive minimum-distance retreat and local anti-stuck fallback directions.
- Added movement diagnostics for approaching and stuck enemies.

## v0.0.36 -> v0.0.37

- Added grid A* pathfinding for alerted enemies when direct line of sight is blocked.
- Enemies now follow tile waypoints around blocked map areas before returning to combat steering.
- Added pathfinding runtime config values and debug overlay diagnostics for pathing/rebuild failures.
- Kept attacks, player damage, squad tactics, and flanking out of scope.


## v0.0.37 -> v0.0.38

- Added configurable debug rendering for active enemy A* paths.
- Smoothed enemy path-following movement direction and increased waypoint reach distance to reduce tile-center jitter.
- Added path waypoint diagnostics to the debug overlay.
- Kept attacks, player damage, squad tactics, flanking, and bullet dodging out of scope.

## v0.0.38 -> v0.0.39

- Added tactical surround positioning for alerted enemies when the player stays nearly stationary.
- Enemies now assign reachable combat slots around the player and path toward those positions.
- Added player stationary tracking, tactical slot config values, debug slot rendering, and overlay diagnostics.
- Kept attacks, player damage, flanking tactics, cover logic, and bullet dodging out of scope.

## v0.0.39 -> v0.0.40

- Reduced tactical slot churn by keeping assigned firing positions until the player meaningfully repositions.
- Added tactical slot commitment timing so enemies do not constantly swap positions while surrounding a stationary player.
- Improved tactical slot assignment with wider slot generation, angular sector spacing, stronger position separation, and firing-position scoring.
- Added runtime config and debug overlay values for tactical sector angle, commitment time, and player reposition distance.

## v0.0.40 -> v0.0.41

- Reworked tactical surround slot assignment to distribute alerted enemies across dedicated sectors around the player.
- Expanded tactical slot generation to use multiple concentric rings and denser angular candidates for better surround coverage.
- Added stronger tactical slot scoring that prefers sector coverage and separation over clustering.
- Added aggressive surround pressure fallback so alerted enemies keep orbiting and pressing when they do not yet hold a tactical slot.
- Added an enemy test that checks open-ground surround assignments spread across multiple quadrants.

## v0.0.41 -> v0.0.42

- Added a configurable right-side debug panel layout inside the main raylib window.
- Enabled the debug panel by default and added side panel width and mouse-wheel scroll settings to runtime config.
- Routed mouse wheel input over the debug panel to scroll diagnostics instead of zooming the camera.
- Kept the classic overlay layout available through the debug overlay layout setting.

## v0.0.42 -> v0.0.43

- Moved the default runtime JSON config from `src/topdown_shooter/config/` to `res/config/` so project configs live in one resource directory.
- Updated runtime config loading to read `res/config/default_runtime_config.json` through a project-root relative path.
- Added Russian documentation for all config files and their parameters under `docs/`.
- Added Russian documentation for enemy pursuit, pathfinding, combat steering, and tactical surround positioning.
- Updated README references to the new runtime config location.

## v0.0.43 -> v0.0.44

- Reworked Russian documentation formatting to avoid wide Markdown tables that are hard to read in terminals.
- Reformatted `docs/configuration_ru.md` into section-based parameter descriptions.
- Reformatted `docs/enemy_tactics_ru.md` into numbered, readable sections without wide tables.
- Kept gameplay, config values, and runtime behavior unchanged.

## v0.0.44 -> v0.0.45

- Added delayed squad alert propagation for enemies spawned from the same tactical spawn zone.
- Added `squad_alert_broadcast_delay_seconds` to the enemy runtime config.
- Updated debug overlay enemy diagnostics with pending and triggered squad alerts.
- Updated Russian documentation for the new squad alert behavior.
- Added a test for delayed squadmate alert propagation.

## v0.0.45 -> v0.0.46

- Added a nearby-radius fallback for delayed squad alert propagation.
- Squad alert broadcasts now notify same-spawn squadmates and nearby alive enemies from adjacent spawn anchors.
- Added `squad_alert_broadcast_radius_px` to enemy runtime config and debug overlay.
- Updated Russian configuration/tactics documentation for squad alert radius behavior.
- Added a regression test for nearby fallback alert propagation.

## v0.0.46 -> v0.0.47

- Fixed delayed squad alert propagation being cleared by enemy chase movement before it could trigger.
- Kept vision-triggered and hit-triggered squad alerts queued until the enemy system update applies them.
- Added a regression test that verifies chase movement does not discard pending squad alerts.

## v0.0.47 -> v0.0.48

- Added configurable budgets for heavy enemy debug rendering layers.
- Added per-frame limits for debug view cones, enemy A* paths, and tactical slot markers.
- Added distance culling for heavy enemy debug layers around the player.
- Updated the default runtime config to keep costly path and tactical-slot debug drawing disabled by default.
- Updated Russian configuration and enemy tactics documentation for the new debug rendering budget settings.

## v0.0.48 -> v0.0.49

- Added per-weapon `noise_radius_px` values to `res/config/weapons.json`.
- Weapon updates now report fire events from the current frame.
- Enemies now become alerted when they hear a player gunshot inside the active weapon noise radius.
- Gunshot hearing alerts also trigger the existing delayed squad alert propagation.
- Updated debug overlay diagnostics and Russian documentation for gunshot hearing.
- Added tests for weapon noise configuration and sound-triggered enemy alerts.

## v0.0.49 -> v0.0.50

- Added enemy awareness states: `idle`, `engaged`, `searching`, and `returning`.
- Enemies now mark direct vision as `engaged`, switch to `searching` after losing line of sight, and return home after the configured timeout.
- Added `lost_sight_timeout_seconds` and `return_home_reached_distance_px` to enemy runtime config.
- Updated enemy debug colors so cones/markers communicate idle, engaged, searching, and returning states.
- Updated debug overlay diagnostics with engaged/searching/returning counts.
- Added regression tests for vision loss, searching, return-home, and idle reset behavior.

## v0.0.50 -> v0.0.51

- Улучшен возврат противников домой после потери игрока.
- В состоянии `returning` противники идут к индивидуальной `home_position`, а не удерживают боевую дистанцию от неё.
- При доступном pathfinding используется A* путь домой; при неудаче есть прямой fallback.
- После достижения дома противник сбрасывается в `idle`, очищает path/tactical slot и восстанавливает стартовый угол обзора.
- Debug overlay показывает количество противников, завершивших возврат домой за последний update.
- Добавлены regression-тесты для движения домой и восстановления стартового facing.

## v0.0.51 -> v0.0.52

- Added `res/map_3d_viewer.py`, a standalone pyray-based 3D flyover viewer for generated `tactical_map.json` files.
- The viewer renders ASCII map tiles as simple 3D primitives and shows start, goal, and enemy spawn markers.
- Added free-fly camera controls and an on-screen help overlay for map inspection.

## v0.0.52 -> v0.0.53

- Added an FPS counter to the top-right corner of `res/map_3d_viewer.py`.
- The counter uses pyray frame statistics and follows the current window size.

## v0.0.53 -> v0.0.54

- Optimized `res/map_3d_viewer.py` by rendering base grass as one ground slab instead of thousands of individual tiles.
- Added horizontal run merging for same-type tiles to cut the sample map from thousands of tile draw calls to far fewer primitives.
- Added a `G` toggle for the expensive 3D debug grid and wire overlays, disabled by default.
- Added HUD render statistics for primitive count, skipped base grass tiles, and grid state.


## v0.0.54 -> v0.0.55

- Fixed inverted A/D strafing in `res/map_3d_viewer.py` so A moves left and D moves right.
- Added Q/E vertical camera controls alongside Ctrl/Space.
- Added mouse wheel height control for quick approach/retreat during 3D map flyover.
- Updated the viewer HUD controls hint.

## v0.0.55 -> v0.0.56

- Added `res/map_3d_viewer_config.json` for 3D viewer window, camera, and render settings.
- Added camera-centered render radius culling to `res/map_3d_viewer.py`.
- Added `F` to toggle render radius and `[` / `]` to change radius size at runtime.
- Updated the HUD with visible/total primitive counts and render radius state.

## v0.0.56 -> v0.0.57

- Added camera navigation presets to `res/map_3d_viewer.py`.
- Added `R` reset, `1` top-down view, and `2` low fly view hotkeys.
- Added quick camera focus hotkeys for start, goal, and enemy spawn markers.
- Updated the viewer HUD controls hint.

## v0.0.57 -> v0.0.58

- Added a toggleable per-tile render mode to `res/map_3d_viewer.py`.
- Kept optimized render mode as the default viewer mode.
- Added `T` hotkey and HUD/config support for `optimized` / `per_tile` render modes.
- Limited per-tile rendering to the camera render radius to avoid full-map draw call spikes.

## v0.0.58 -> v0.0.59

- Added the experimental `render3d` runtime config section for the 3D system branch.
- Added `--renderer 2d|3d` to select the runtime renderer backend while keeping 2D as the default.
- Added an isolated `topdown_shooter.experimental.render3d` scaffold with follow camera, scene culling, and a minimal 3D preview renderer.
- Kept the existing 2D runtime path unchanged unless `--renderer 3d` is explicitly requested.

## v0.0.59 -> v0.0.60

- Reworked the experimental 3D runtime from a static preview into an interactive player-follow preview.
- Added smoothed 3D camera modes: `1` for top-down view, `2` for low follow view, and `R` to reset smoothing.
- Added player movement in the 3D experiment with WASD and arrow-key aliases while preserving the 2D runtime path.
- Improved the 3D player marker with a facing line and added `H` to toggle the 3D debug HUD.
- Extended the `render3d.camera` config section with top-down camera settings and tuned the default low-follow camera closer to the player.

## v0.0.60 -> v0.0.61

- Changed experimental 3D scene culling to prioritize tiles nearest to the player before applying the visible primitive cap.
- Limited the 3D ground plane to the current player-centered view bounds instead of drawing one full-map ground slab.
- Drew the 3D player marker from the continuous world position rather than the integer tile center for smooth movement.
- Updated the 3D HUD with the player-centered radius tile coordinate.

## v0.0.61 -> v0.0.62

- Added camera-relative movement for the experimental 3D runtime.
- Added smooth acceleration, deceleration, and visual facing turns for the 3D player marker.
- Added render3d player movement tuning to the runtime config.
- Updated the 3D debug HUD to show the new movement mode.

## v0.0.62 -> v0.0.63

- Added smoothed 3D camera look-ahead for the experimental follow view.
- Shifted the 3D camera anchor toward the player movement direction so the player is not locked to the exact screen center.
- Added render3d camera tuning for movement look-ahead distance and smoothing.
- Updated the experimental 3D debug HUD to show the configured camera look-ahead.

## v0.0.63 -> v0.0.64

- Stabilized experimental 3D backpedal handling so backward input keeps the current visual facing instead of forcing a 180-degree turn.
- Added configurable backpedal-facing settings to the `render3d.player_movement` section.
- Updated the 3D debug HUD to show stable backpedal behavior.

## v0.0.64 -> v0.0.65

- Добавлен mouse yaw для направления взгляда в экспериментальном 3D-режиме.
- WASD/стрелки теперь двигают игрока относительно направления взгляда: W/S вперед/назад, A/D strafe.
- Настройки mouse aim и movement basis вынесены в секцию render3d.player_movement.

## v0.0.65 -> v0.0.66

- Добавлены 3D-маркеры врагов в экспериментальный `--renderer 3d` режим.
- Враги отрисовываются только внутри player-centered view radius и ограничены отдельным safety cap.
- Настройки enemy-маркеров вынесены в секцию `render3d.enemies`.
- HUD экспериментального 3D-режима показывает количество видимых врагов.

## v0.0.66 -> v0.0.67

- Добавлена визуализация aim line в экспериментальном `--renderer 3d` режиме.
- Добавлены 3D-маркеры projectiles и projectile impact markers внутри player-centered view radius.
- Подключены существующие `ProjectileSystem` и `WeaponController` к изолированному 3D experiment runtime без изменения 2D-runtime.
- Настройки projectile/aim-маркеров вынесены в секцию `render3d.projectiles`.
- HUD экспериментального 3D-режима показывает видимые projectiles, impacts и текущий weapon/ammo.

## v0.0.67 -> v0.0.68

- Улучшена читаемость боя в экспериментальном `--renderer 3d` режиме.
- Добавлены настраиваемые 3D projectile tracers, impact rings и enemy hit markers.
- Враги получают короткий hit flash при попадании без изменения AI, урона и 2D-runtime.
- Настройки вынесены в секцию `render3d.combat_visuals`.

## v0.0.68 -> v0.0.69

- Перенесён reset camera в экспериментальном 3D-режиме с `R` на `C`.
- `R` оставлена только для reload в экспериментальном 3D renderer-е.
- Добавлена настройка `render3d.controls.camera_reset` и обновлена подсказка в 3D HUD.

## v0.0.69 -> v0.0.70

- Добавлены режимы отображения экспериментального 3D renderer-а: clean, gameplay и debug.
- Клавиша `V` переключает view mode без перезапуска 3D-режима.
- Clean скрывает боевые маркеры и оставляет карту с игроком, Gameplay показывает боевые объекты с компактным HUD, Debug оставляет полный технический HUD.
- Добавлены настройки `render3d.view_mode` и `render3d.controls.view_mode_toggle`.

## v0.0.70 -> v0.0.71

- Добавлен fake distance fade / псевдоосвещение в экспериментальный 3D-режим.
- Добавлено переключение distance fade по клавише L.
- Настройки distance fade вынесены в секцию render3d.distance_fade.
- HUD показывает состояние distance fade.


## v0.0.71 -> v0.0.72

- Добавлена настройка `render3d.distance_fade.fog_density` для управления густотой distance fog в экспериментальном 3D-режиме.
- Distance fade сделан мягче по умолчанию: дальние тайлы меньше проваливаются в темноту.
- Формула затемнения теперь использует density-curve, чтобы менять характер нарастания тумана из конфига.
- HUD экспериментального 3D-режима показывает состояние fog и текущую density.

## v0.0.72 -> v0.0.73

- Добавлен общий combat runtime update pipeline для 2D runtime и экспериментального 3D renderer-а.
- Экспериментальный `--renderer 3d` теперь использует существующие enemy perception, sound alert, chase movement, pathfinding и tactical positioning update-шаги.
- Удалено дублирование урезанного projectile/enemy update loop в 3D-режиме без добавления нового AI.
- 2D runtime переведён на тот же общий helper без изменения поведения рендера.

## v0.0.73 -> v0.0.74

- Добавлены углы обзора противников в экспериментальный 3D renderer.
- Добавлено переключение enemy vision cones по клавише O.
- Настройки визуализации вынесены в секцию `render3d.enemy_vision`.
- Конусы используют существующие параметры enemy perception range/angle и не меняют AI, агр или баланс.

## v0.0.74 -> v0.0.75

- Улучшена читаемость врагов в экспериментальном 3D renderer-е: состояние врага теперь видно по body color, ground-ring, status marker и facing tip.
- Разделены визуальные состояния idle, alerted/searching, returning и engaged без изменения AI, pathfinding, агра или баланса.
- 2D runtime и существующая gameplay-логика не изменялись.

## v0.0.75 -> v0.0.76

- Улучшена читаемость окружения в экспериментальном 3D renderer-е: стены, деревья, укрытия и особые walkable-тайлы получили более различимые 3D-силуэты.
- 3D gameplay HUD переведён на общий 2D-style `PlayerHud`, включая отображение HP, оружия, боезапаса и reload state.
- HUD/overlay текст в 3D renderer-е теперь использует `res/fonts/PressStart2P-Regular.ttf` через общий `RaylibTextRenderer` с безопасным fallback-ом.
- AI, pathfinding, collision, генератор карты, combat balance и 2D runtime не изменялись.

## v0.0.76 -> v0.0.77

- Добавлена общая enemy fire интеграция: engaged-враги теперь стреляют hostile projectiles через существующий combat runtime pipeline.
- ProjectileState получил owner-tag, чтобы player/enemy projectiles корректно маршрутизировались и не наносили friendly fire по врагам.
- Вражеские projectiles наносят урон игроку через общий runtime helper и визуально отличаются в 3D renderer-е красно-оранжевыми трассерами.
- AI, pathfinding, tactical positioning, collision и генератор карты не изменялись.

## v0.0.77 -> v0.0.78

- Стартовый размер 2D и экспериментального 3D окна теперь вычисляется по текущему монитору: по 100 px свободного поля с каждой стороны.
- Окно автоматически центрируется после создания, а runtime `WindowConfig` обновляется до фактического размера, чтобы HUD, FPS, камера и debug overlay считали координаты от нового окна.
- Добавлен безопасный fallback на старый config-размер, если raylib не отдаёт корректные параметры монитора.

## v0.0.78 -> v0.0.79

- Исправлен сломанный импорт `topdown_shooter.rendering.window_layout` после изменения логики стартового окна.
- Настройка рамки окна перенесена в `window.screen_margin_px`; старые config-поля `window.width` и `window.height` удалены из runtime config.
- 2D runtime и экспериментальный 3D renderer используют общий расчёт окна от текущего монитора с одинаковым отступом со всех сторон и без fallback-а на старый config-размер.

## v0.0.79 -> v0.0.80

- Исправлена регрессия auto-sized window layout: 2D HUD, FPS, camera и debug overlay теперь создаются с resolved runtime `WindowConfig`, а не с пустым размером из config.
- Расчёт размера экрана больше не вызывает `get_current_monitor()` до создания окна, чтобы избежать GLFW selected-monitor warnings и аварийного маленького fallback-окна.
- Добавлен fallback через tkinter для окружений, где raylib не отдаёт размер монитора до `init_window`.
- Gameplay, AI, projectiles, HUD-логика и баланс не изменялись.

## v0.0.80 -> v0.0.81

- Исправлено позиционирование auto-sized окна: стартовая позиция теперь повторно применяется в первые кадры после `init_window`, чтобы оконный менеджер Linux не оставлял окно в левом верхнем углу.
- Расчёт геометрии экрана стал надёжнее: для X11 используется `xrandr --current` с учётом primary-монитора и его origin, затем fallback-и без возврата старых `window.width/window.height` в конфиг.
- Добавлены тесты для `screen_margin_px`, multi-monitor origin, parsing `xrandr` и применения resolved window position.
- Gameplay, AI, projectiles, HUD-логика и баланс не изменялись.

## v0.0.81 -> v0.0.82

- Оптимизирована подготовка 3D-сцены: `Render3DSceneBuilder` кэширует snapshot для текущего player tile и не пересобирает видимые тайлы каждый кадр, пока центр culling-а не изменился.
- Ограничена стоимость 3D-сцены по умолчанию: `view_radius_tiles` снижен до 35, `max_visible_primitives` — до 1400.
- Enemy vision cones оставлены доступными через `O`, но выключены по умолчанию; дефолтные лимиты снижены до 24 cones и 8 segments.
- Дальние тайлы больше не рисуют дополнительные outline/detail draw calls, а distance fade для тайлов использует уже посчитанную дистанцию snapshot-а.
- Gameplay, AI, projectiles, damage, HUD-логика и 2D runtime не изменялись.


## v0.0.82 -> v0.0.83

- HUD закреплён как always-on верхняя игровая статусная панель: клавиша `H` больше не управляет HUD, а 2D и 3D используют общий `PlayerHud` с одинаковым layout/config.
- Debug overlay переведён на единый right-side panel для 2D и 3D, выключен по умолчанию и переключается общей клавишей `F12`.
- 3D renderer больше не рисует отдельный debug HUD текстом слева; вместо этого он использует общий `DebugOverlay` и добавляет только renderer-specific 3D sections.
- Настройки HUD/debug overlay оставлены в общих config-блоках, а устаревшие `hud.enabled` и `render3d.show_debug_hud` удалены из runtime config.
- Standalone FPS counter выключен по умолчанию, чтобы техническая информация жила в debug overlay, а не поверх игрового HUD.


## v0.0.83 -> v0.0.84

- Добавлен общий modal UI layer для 2D и 3D: F1 открывает центрированный help overlay и ставит gameplay на паузу.
- Esc больше не закрывает игру сразу: открывается общее окно подтверждения выхода, повторный Esc или No возвращают в игру, Yes/Enter закрывает приложение.
- В 3D добавлен F10 для capture/release мыши; F1/Esc автоматически освобождают мышь на время модального overlay и возвращают capture после закрытия.
- Общие UI-клавиши вынесены в runtime config: `controls.help` и `controls.mouse_capture_toggle`; gameplay, AI, projectiles и баланс не изменялись.

## v0.0.84 -> v0.0.85

- Добавлен отсутствующий общий пакет `src/topdown_shooter/ui`, из-за которого `v0.0.84` падал на импорте `topdown_shooter.ui.runtime_ui`.
- Восстановлены shared modal UI-компоненты для F1 help overlay, Esc exit confirmation и F12 debug overlay toggle без изменения gameplay-логики.
- Gameplay, AI, projectiles, HUD-layout и баланс не изменялись.

## v0.0.85 -> v0.0.86

- Отключено стандартное закрытие окна через `Esc` в raylib для 2D и 3D runtime.
- `Esc` теперь проходит в общий `RuntimeUi` и открывает окно подтверждения выхода вместо мгновенного завершения приложения.
- Gameplay, AI, projectiles, HUD-layout и баланс не изменялись.

## v0.0.86 -> v0.0.87

- Удалены runtime/cache-файлы из архива проекта: `__pycache__`, `.pyc` и `.pytest_cache`.
- Удалён устаревший standalone FPS counter и связанный config-блок `fps_counter`; FPS остаётся в общем debug overlay по `F12`.
- Общая логика разрешения raylib-клавиш/кнопок вынесена в `src/topdown_shooter/rendering/raylib_input.py` и используется 2D, 3D и shared UI.
- Убран конфликт 3D hotkeys: клавиши `1/2/3` остаются только выбором оружия, старое переключение 3D camera modes через `1/2` удалено.
- Удалены мёртвые методы и config-поля старой 3D movement-схемы, а также устаревший `run_static_preview()`.
- Gameplay, AI, projectiles, HUD-layout, баллистика и баланс не изменялись.

## v0.0.87 -> v0.0.88

- Добавлен общий config-блок `ui` для shared UI-шрифта и glyph spacing.
- `PlayerHud`, `DebugOverlay`, `RuntimeUi`, 2D runtime и 3D renderer больше не берут общий UI-шрифт из `debug_overlay`.
- Из `debug_overlay` удалены поля `font_path` и `font_spacing`; блок теперь отвечает только за layout/debug-panel параметры.
- Внешний вид HUD/debug/help/exit overlays и gameplay-логика не изменялись.


## v0.0.88 -> v0.0.89

- Правый debug overlay получил фиксированный header с текущей клавишей toggle и положением scroll offset.
- Скроллируемая область debug overlay теперь начинается ниже header-а, имеет явную высоту viewport-а и не рисует строки поверх заголовка.
- Добавлен компактный scrollbar для длинного debug overlay; поведение едино для 2D и 3D, настройки продолжают жить в общем `debug_overlay` config-блоке.
- Убрана дублирующаяся строка `Camera/Target` в debug overlay и исправлено отображение всех трёх weapon slots.
- Gameplay, AI, projectiles, HUD-layout, баллистика и баланс не изменялись.


## v0.0.89 -> v0.0.90

- Добавлены `ProjectileOwner`, `ProjectileEventType` и `ProjectileEvent` как общий фундамент для feedback-событий выстрелов.
- `ProjectileSystem` теперь накапливает события `SPAWNED`, `HIT_WALL`, `HIT_PLAYER`, `HIT_ENEMY` и `EXPIRED`; события можно забирать через `consume_events()`.
- Попадания enemy projectile по игроку и player projectile по врагам теперь записываются как projectile feedback events без изменения урона, скорости, cooldown, spread или баланса.
- 2D renderer теперь визуально различает projectiles игрока и врагов по owner; 3D renderer переведён на общий `ProjectileOwner`.
- Баллистика, полёт пуль, AI, HUD-layout и gameplay-баланс не изменялись.

## v0.0.90 -> v0.0.91

- Добавлен общий helper расчёта muzzle origin для выстрелов игрока и врагов.
- Выстрел игрока теперь создаёт projectile из точки перед персонажем через `player.fire_muzzle_offset_px`, а не из центра тела; enemy fire использует тот же helper с существующим `enemies.fire_muzzle_offset_px`.
- Projectile feedback events дополнены направлением projectile для будущих эффектов выстрелов/попаданий.
- 2D и 3D renderer теперь используют событие `SPAWNED` для коротких muzzle flash эффектов player/enemy projectiles.
- Урон, скорость, дальность, spread, fire rate, cooldown, AI, баллистика и баланс не изменялись.

## v0.0.91 -> v0.0.92

- Added shared incoming-hit combat feedback for 2D and 3D.
- Added player damage screen flash and directional hit indicators from projectile HIT_PLAYER events.
- Added HUD HP damage pulse without changing weapon or damage balance.

## v0.0.92 -> v0.0.93

- Improved projectile flight visuals without changing projectile mechanics or balance.
- 2D projectiles now draw owner-colored previous-to-current tracers, fading trail afterimages, and core outlines.
- 3D projectiles now draw real previous-to-current tracer segments instead of fixed fake tails, plus short fading trail afterimages.
- Player/enemy projectile colors stay visually distinct in both renderers.


## v0.0.93 -> v0.0.94

- Replaced moving bullet projectiles with immediate hitscan shot traces for player and enemy fire.
- `ProjectileSystem` now resolves rays instantly, keeps short-lived visual traces, and finalizes deferred wall/range events after hit tests.
- Removed old projectile speed/lifetime config fields from weapon and enemy fire configs; weapons now use `shot_range_px`, `tracer_lifetime_seconds`, and `shot_radius_px`.
- Existing muzzle flash, hit feedback, impact markers, and 2D/3D tracer rendering now use hitscan traces without changing damage, fire rate, spread, reload, AI, or balance.


## v0.0.94 -> v0.0.95

- Added renderer-facing weapon visual profiles for hitscan shot traces.
- Pistol, AK-47, minigun, and enemy fire now use distinct tracer, trail, and muzzle-flash profiles in 2D and 3D.
- Added visual profile tags to shot events/traces without changing damage, fire rate, spread, reload, AI, pathfinding, or hit detection.


## v0.0.95 -> v0.0.96

- Added runtime map object models for generator-provided gameplay objects and sparse elevation data.
- RuntimeMapBuilder now parses `runtime_objects`, `runtime_objects_summary`-style counters, and `elevation` from tactical maps without requiring debug PNG layers.
- Movement collision, pathfinding, and hitscan wall resolution now respect runtime object movement/projectile blockers where the generator marks them as blocking.
- Added simple 2D and 3D gameplay placeholders for runtime objects without adding AI cover logic, loot pickups, trench stance mechanics, explosions, or balance changes.


## v0.0.96 -> v0.0.97

- Runtime object collision now treats generator `collision_profile` as the primary movement/projectile/vision rule source, with legacy boolean fields used as fallback.
- Runtime maps now index objects by occupied tile and expose movement/projectile blocker queries for gameplay systems.
- Hitscan wall events now distinguish runtime object blockers via stable `object:<type>:<id>` reasons while keeping the existing HIT_WALL event type.
- 2D runtime object placeholders now draw more type-specific shapes/colors for caches, trenches, cover props, barrels, and landmarks without adding loot, explosions, crouching, or AI cover logic.

## v0.0.97 -> v0.0.98

- Improved runtime object presence in 2D and 3D with more distinct gameplay placeholders for caches, trenches, logs, barrels, landmarks, stone and scrap cover.
- Added runtime object interaction baseline queries for nearby interactive objects without enabling loot pickup yet.
- Extended runtime object diagnostics with interactive, loot and explosive object counters plus nearest interactive object debug info.
- Kept AI cover logic, crouching, loot pickups, explosions and balance changes out of this patch.
## v0.0.98 -> v0.0.99

- Added runtime object pickup MVP for `ammo_cache` and `medkit_cache` using the existing interactive object lookup.
- Added a shared interaction system that consumes used caches, heals the player, and adds reserve ammo to finite-reserve weapons.
- Added `KEY_SPACE` interaction binding in 2D and 3D plus HUD feedback messages and dimmed consumed cache placeholders.
- Kept inventory, loot tables, barrel explosions, AI cover logic, crouching, trench protection, and balance changes out of this patch.



## v0.0.99 -> v0.1.0

- Added a clearer runtime object icon style pass for 2D map rendering: medkit crosses, ammo ticks, barrel warning marks, hatched trenches, bush blobs, log rings and scrap fragments.
- Improved 3D runtime object readability with semantic markers for medkit caches, ammo caches and risky barrels while keeping cover objects readable through primitive silhouettes.
- Kept the pass visual-only: no loot value changes, barrel explosions, crouching, trench protection, AI cover logic or balance changes.

## v0.1.0 -> v0.1.1

- Added material-aware projectile impact metadata for hitscan blockers, including runtime object surface material inference.
- 2D and 3D impact markers now use distinct feedback for stone, wood, metal, foliage, dirt and risky barrel hits.
- Runtime object blocker hit events keep their stable reason tags while also exposing impact material for renderers and diagnostics.
- Kept the pass feedback-only: no barrel explosions, damage changes, penetration changes, AI cover logic, crouching or loot value changes.

## v0.1.1 -> v0.1.2

- Added MVP explosions for `rusted_barrel` runtime objects hit by hitscan shots.
- Added radial explosion damage for player and enemies with one-shot destroyed barrel state.
- Added material-aware explosion impact markers in 2D and 3D without chain reactions or object destruction propagation.
