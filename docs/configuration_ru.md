# Конфигурация TopDownShooter V2

Документ описывает конфигурационные файлы проекта и смысл их параметров.
Формат специально сделан без широких Markdown-таблиц, чтобы файл нормально читался в терминале.

## Где лежат конфиги

Все JSON-конфиги проекта лежат в одной директории:

```text
res/config/
  default_runtime_config.json
  weapons.json
```

`src/topdown_shooter/config/` остаётся Python-пакетом для кода загрузки и валидации. JSON-файлы там хранить не нужно.

---

# res/config/default_runtime_config.json

Основной runtime-конфиг приложения. Он управляет окном, камерой, HUD, debug-интерфейсом, управлением, игроком, врагами, pathfinding и тактическим позиционированием.

## window

### title
Заголовок окна приложения.

### width
Ширина окна в пикселях.

### height
Высота окна в пикселях.

### target_fps
Целевой FPS основного raylib-цикла.

---

## camera

### zoom
Начальный масштаб камеры.

### clamp_to_map
Ограничивает камеру границами карты.

### smooth_time
Время сглаживания следящей камеры. Чем выше значение, тем мягче и инерционнее движение камеры.

### lookahead_tiles
Смещение камеры по направлению движения игрока в тайлах.

### min_zoom
Минимальный интерактивный zoom.

### max_zoom
Максимальный интерактивный zoom.

### zoom_step
Шаг изменения zoom клавишами.

### move_speed_px_per_second
Скорость ручного перемещения камеры в режиме map viewer.

### follow_player_by_default
Если `true`, камера стартует в режиме следования за игроком.

### max_speed_px_per_second
Максимальная скорость инерционного движения камеры.

### dead_zone_tiles
Радиус dead zone вокруг игрока в тайлах.

### aim_lookahead_enabled
Включает смещение камеры в сторону прицеливания.

### aim_lookahead_tiles
Сила aim-lookahead в тайлах.

---

## player

### marker_radius_px
Радиус маркера игрока.

### movement_speed_px_per_second
Базовая скорость движения игрока.

Фактическая скорость дополнительно зависит от:

- `movement_cost` текущего тайла;
- `active_movement_speed_multiplier` активного оружия.

### collision_radius_px
Радиус коллизии игрока.

### max_health
Максимальное и стартовое здоровье игрока.

---

## debug_overlay

### enabled_by_default
Показывать debug-интерфейс при старте.

### layout
Режим отображения debug-информации.

Поддерживаемые значения:

- `right_panel` — правая debug-панель внутри основного окна;
- `overlay` — старый overlay поверх карты.

### panel_width
Ширина старой overlay-панели в режиме `overlay`.

### side_panel_width
Ширина правой debug-панели в режиме `right_panel`.

### scroll_step_px
Шаг скролла debug-панели колесом мыши.

### padding
Внутренний отступ панели.

### font_size
Размер шрифта debug-текста.

### line_spacing
Вертикальный интервал между строками.

### section_spacing
Вертикальный интервал между секциями.

### column_gap
Расстояние между колонками debug-вывода.

### label_width
Ширина колонки label-ов.

### background_alpha
Прозрачность фона debug-панели. Значение находится в диапазоне `0..255`.

### font_path
Путь к TTF-шрифту.

Сейчас используется:

```text
res/fonts/PressStart2P-Regular.ttf
```

### font_spacing
Дополнительный spacing между символами для raylib font rendering.

---

## controls

### quit
Клавиша выхода из приложения.

### debug_overlay.key
Основная клавиша переключения debug overlay.

### debug_overlay.modifiers
Модификаторы для переключения debug overlay.

### camera_up / camera_down / camera_left / camera_right
Клавиши ручного перемещения камеры.

### camera_zoom_in
Zoom-in клавишей.

### camera_zoom_out
Zoom-out клавишей.

### camera_reset
Сброс камеры.

### camera_zoom_mouse_wheel
Если `true`, колесо мыши управляет zoom камеры, когда курсор не находится над debug-панелью.

### player_up / player_down / player_left / player_right
Клавиши движения игрока.

### camera_toggle_follow
Переключение между follow-камерой и map-viewer режимом.

### fire_primary
Основной огонь.

### reload
Перезарядка.

### weapon_slot_1 / weapon_slot_2 / weapon_slot_3
Клавиши выбора оружия по слотам.

---

## aim_debug

### enabled
Включает debug-линию и маркер направления прицеливания.

### line_length_px
Длина aim-линии.

### marker_radius_px
Радиус aim-маркера.

### line_thickness_px
Толщина aim-линии.

---

## fps_counter

### enabled
Включает отдельный FPS-счётчик вне debug overlay.

### position
Позиция счётчика. Сейчас используется `top_right`.

### margin_x
Горизонтальный отступ.

### margin_y
Вертикальный отступ.

### font_size
Размер шрифта FPS-счётчика.

---

## weapons

### database_path
Путь к базе оружия.

По умолчанию:

```text
res/config/weapons.json
```

---

## projectile_impacts

### enabled
Создавать impact-маркеры при попадании снаряда в blocked tile.

### lifetime_seconds
Время жизни impact-маркера.

### radius_px
Радиус impact-маркера.

---

## hud

### enabled
Включает HUD игрока.

### position
Позиция HUD.

Поддерживаемые значения:

- `top`;
- `bottom`;
- `left`;
- `right`.

### margin_x
Горизонтальный отступ HUD.

### margin_y
Вертикальный отступ HUD.

### padding
Внутренний отступ HUD-плашки.

### font_size
Размер HUD-шрифта.

### background_alpha
Прозрачность фона HUD.

---

## enemies

Секция `enemies` управляет отрисовкой врагов, здоровьем, восприятием, спавном отрядов, движением, pathfinding и тактическим позиционированием.

### Визуал и здоровье

#### marker_radius_px
Радиус маркера врага.

#### max_health
Максимальное здоровье врага.

#### hit_marker_lifetime_seconds
Время жизни маркера попадания по врагу.

#### hit_marker_radius_px
Радиус маркера попадания.

#### health_bar_visible_seconds
Сколько секунд показывать health bar после попадания.

#### hit_flash_seconds
Длительность hit-flash эффекта.

### Обзор и обнаружение игрока

#### draw_view_cones
Рисовать debug-конусы обзора.

#### max_debug_view_cones
Максимальное количество debug-конусов обзора, которое можно рисовать за кадр.

`0` полностью запрещает отрисовку конусов даже при включённом `draw_view_cones`.

#### vision_range_px
Дальность обзора врага.

#### vision_angle_degrees
Полный угол конуса обзора.

#### line_of_sight_sample_step_px
Шаг проверки line of sight через blocked tiles.

#### smart_initial_facing
Автоматически выбирать стартовый угол обзора по открытости пространства.

#### facing_candidate_step_degrees
Шаг перебора кандидатных углов стартового обзора.

#### facing_probe_side_angle_degrees
Боковой угол probe-лучей при оценке стартового обзора.

#### facing_wall_penalty_distance_px
Дистанция, на которой стена перед врагом сильно штрафует направление.

#### facing_probe_step_px
Шаг семплирования probe-лучей.

### Начальный спавн отрядов

#### min_squad_size
Минимальный размер отряда из одной `enemy_spawn_zone`.

#### max_squad_size
Максимальный размер отряда из одной `enemy_spawn_zone`.

#### squad_radius_px
Радиус расстановки отряда вокруг spawn anchor.

#### min_enemy_spacing_px
Минимальная дистанция между врагами при начальном размещении.

#### max_initial_enemies
Глобальный лимит стартовых врагов.

#### placement_attempts_per_enemy
Количество попыток найти валидную позицию для каждого врага.

#### squad_alert_broadcast_delay_seconds
Задержка перед передачей тревоги другим членам отряда или близкой группы.

Если один враг увидел игрока или получил попадание, тревога передаётся
не мгновенно, а после этой задержки.

#### squad_alert_broadcast_radius_px
Радиус дополнительной передачи тревоги ближайшим врагам.

Основной критерий отряда — общий `spawn_id`. Но визуально близкие враги могут
быть созданы из соседних spawn-точек. Этот радиус нужен как fallback: если враг
рядом с источником тревоги, он тоже получает тревогу после задержки.

### Боевой steering

#### chase_speed_px_per_second
Скорость движения врагов.

#### preferred_combat_distance_px
Желаемая дистанция боя.

#### minimum_combat_distance_px
Минимальная дистанция. Если враг оказывается ближе, он активнее отходит.

#### combat_distance_tolerance_px
Допуск вокруг желаемой дистанции.

#### movement_direction_smoothing
Сглаживание направления движения.

#### approach_weight
Вес сближения с игроком.

#### strafe_weight
Вес бокового движения.

#### retreat_weight
Вес отхода при слишком близкой дистанции.

#### strafe_switch_min_seconds
Минимальное время до смены стороны страйфа.

#### strafe_switch_max_seconds
Максимальное время до смены стороны страйфа.

### Pathfinding

#### pathfinding_enabled
Включает A* pathfinding для alerted-врагов.

#### path_rebuild_interval_seconds
Минимальная задержка между перестроениями пути.

#### path_target_rebuild_distance_px
Насколько должна сместиться цель, чтобы путь перестроился.

#### path_max_iterations
Максимальное число итераций A* на один запрос.

#### path_waypoint_reach_distance_px
Дистанция, на которой waypoint считается достигнутым.

#### draw_enemy_paths
Рисовать debug-пути врагов.

#### max_debug_enemy_paths
Максимальное количество A* debug-путей врагов, которое можно рисовать за кадр.

`0` полностью запрещает отрисовку путей даже при включённом `draw_enemy_paths`.

#### debug_enemy_render_distance_px
Максимальная дистанция от игрока, на которой тяжёлые enemy debug-слои рисуются.

К тяжёлым слоям относятся:

- view cones;
- enemy paths;
- tactical slots.

Если значение равно `0`, дистанционный фильтр отключён, и работает только лимит по количеству.

### Тактическое окружение игрока

#### tactical_positioning_enabled
Включает выбор огневых позиций вокруг стоящего игрока.

#### player_stationary_speed_threshold_px_per_second
Скорость, ниже которой игрок считается почти неподвижным.

#### player_stationary_time_seconds
Сколько времени игрок должен быть почти неподвижным, чтобы включилось тактическое позиционирование.

#### tactical_slot_count
Базовое количество кандидатных слотов вокруг игрока.

#### tactical_surround_distance_px
Радиус кольца огневых позиций.

#### tactical_reassign_interval_seconds
Минимальная задержка между переназначениями tactical slots.

#### tactical_slot_reached_distance_px
Дистанция, на которой враг считается занявшим tactical slot.

#### tactical_min_slot_spacing_px
Минимальная дистанция между назначенными слотами.

#### tactical_min_slot_angle_degrees
Минимальный угловой разнос между секторами.

#### tactical_slot_commitment_seconds
Минимальное время удержания назначенного слота.

#### tactical_player_reposition_distance_px
Смещение игрока, после которого tactical slots пересчитываются.

#### draw_tactical_slots
Рисовать debug tactical slots.

#### max_debug_tactical_slots
Максимальное количество tactical slot markers, которое можно рисовать за кадр.

`0` полностью запрещает отрисовку слотов даже при включённом `draw_tactical_slots`.

---

# res/config/weapons.json

База оружия. Содержит версию схемы, оружие по умолчанию и список оружия.

## Верхний уровень

### schema_version
Версия схемы базы оружия. Сейчас используется `weapons-v1`.

### default_weapon_id
Оружие, выдаваемое игроку по умолчанию.

### weapons
Список описаний оружия.

## Поля оружия

### id
Уникальный ID оружия.

### display_name
Имя для HUD и debug-вывода.

### slot
Номер слота выбора оружия.

### fire_rate_rpm
Темп стрельбы в выстрелах в минуту.

### projectile_speed_px_per_second
Скорость снаряда.

### projectile_range_px
Максимальная дистанция полёта снаряда.

### projectile_lifetime_seconds
Максимальное время жизни снаряда.

### projectile_radius_px
Радиус снаряда для отрисовки и коллизий.

### spread_degrees
Разброс выстрела в градусах.

### shots_per_fire
Количество снарядов за одно срабатывание огня.

### magazine_size
Размер магазина.

### initial_reserve_ammo
Стартовый резерв патронов.

Значение может быть:

- числом;
- строкой `infinite` для бесконечного резерва.

### reload_time_seconds
Время перезарядки конкретного оружия.

### active_movement_speed_multiplier
Множитель скорости игрока, когда оружие активно.

Примеры смысла:

- `1.0` — оружие не замедляет игрока;
- `0.96` — лёгкое замедление;
- `0.75` — заметное замедление.

### damage
Урон одного снаряда по врагу.

## Текущее оружие

### pistol
Базовое точное оружие с бесконечным резервом.

Ключевые особенности:

- слот `1`;
- магазин на `8` патронов;
- резерв `infinite`;
- быстрый reload;
- без штрафа к скорости игрока.

### ak47
Автомат со средним уроном, разбросом и конечным резервом.

Ключевые особенности:

- слот `2`;
- магазин на `30` патронов;
- резерв `90`;
- небольшой штраф к скорости игрока.

### minigun_m134
Стресс-тест огневой системы: большой магазин, высокий RPM, сильный штраф к скорости игрока.

Ключевые особенности:

- слот `3`;
- магазин на `1000` патронов;
- резерв `2000`;
- очень высокий темп стрельбы;
- заметное замедление игрока.

## Дополнение: enemy awareness

### `enemies.lost_sight_timeout_seconds`

Сколько секунд противник может находиться в состоянии поиска после потери прямой видимости игрока.

Если таймер истёк, противник переходит в состояние `returning` и начинает возвращаться к своей стартовой позиции.

### `enemies.return_home_reached_distance_px`

Дистанция в пикселях, на которой противник считается вернувшимся домой.

Когда противник в состоянии `returning` оказывается ближе этого расстояния к своей `home_position`, он сбрасывает тревогу и снова становится `idle`.
