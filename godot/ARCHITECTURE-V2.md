# DRENOVAR — архитектура зданий v2 (Godot 4.6.3, Mobile)

Правки 40 уровней из CHANGES.md (20 серий). Утверждённые серии B02, B04, B10, B12, B20, B22 и B27,
а также уровни вне CHANGES.md не изменены.

## Как игра выбирает визуал

`landscape.gd → present()` строит здания из состояния города. Этот путь общий для строительства,
улучшения и загрузки сохранения (`restore_account` / `sync_account` → `state` → `present`).

1. Для пары «тип + уровень» из таблицы `levelModels` в `assets/game.json` загружается готовая
   сцена уровня `assets/city/architecture-v2/levels/<ТИП>-<У>.tscn` (масштаб 1, точка установки — центр участка).
2. Для остальных пар — прежняя логика: общая GLB типа × `1 + 0.055·(У−1)` и оверлей
   `city-details/<ТИП>-<У>.glb`.

Общие GLB (`lumber`, `quarry27`, `warehouse` и др.) и оверлеи не изменялись: сцены уровней
используют их как неизменяемый ресурс или хранят собственную копию с вырезанными объёмами
(`*-base.res`). Поэтому правка уровня не влияет на другие уровни и на типы с общей моделью
(например, ALT-02 «Лесопилка» и RES-01 «Лагерь лесорубов» оба используют `lumber`).
Идентификаторы зданий, правила улучшения, участки и формат сохранений не менялись.
Сцена уровня может задать точку рабочего (`worker_offset`), чтобы рабочий не стоял на новых лестницах и стойках.

## Сопоставление позиций

| Серия | Тип | Уровень | Сцена |
|---|---|---|---|
| B01_TownHall | ECO-05 (Ратуша/главное здание) | I | `godot/project/assets/city/architecture-v2/levels/ECO-05-1.tscn` |
| B01_TownHall | ECO-05 (Ратуша/главное здание) | II | `godot/project/assets/city/architecture-v2/levels/ECO-05-2.tscn` |
| B01_TownHall | ECO-05 (Ратуша/главное здание) | V | `godot/project/assets/city/architecture-v2/levels/ECO-05-5.tscn` |
| B03_Warehouse | ECO-01 (Склад) | V | `godot/project/assets/city/architecture-v2/levels/ECO-01-5.tscn` |
| B05_Marketplace | ECO-03 (Рынок) | V | `godot/project/assets/city/architecture-v2/levels/ECO-03-5.tscn` |
| B06_LumberCamp | RES-01 (Лагерь лесорубов) | V | `godot/project/assets/city/architecture-v2/levels/RES-01-5.tscn` |
| B07_StoneQuarry | RES-02 (Каменоломня) | V | `godot/project/assets/city/architecture-v2/levels/RES-02-5.tscn` |
| B08_IronMine | RES-03 (Железная шахта) | V | `godot/project/assets/city/architecture-v2/levels/RES-03-5.tscn` |
| B09_Farm | RES-04 (Ферма) | III | `godot/project/assets/city/architecture-v2/levels/RES-04-3.tscn` |
| B09_Farm | RES-04 (Ферма) | V | `godot/project/assets/city/architecture-v2/levels/RES-04-5.tscn` |
| B11_InfantryBarracks | MIL-01 (Казармы) | IV | `godot/project/assets/city/architecture-v2/levels/MIL-01-4.tscn` |
| B11_InfantryBarracks | MIL-01 (Казармы) | V | `godot/project/assets/city/architecture-v2/levels/MIL-01-5.tscn` |
| B13_Stables | MIL-03 (Конюшня) | III | `godot/project/assets/city/architecture-v2/levels/MIL-03-3.tscn` |
| B14_Blacksmith | MIL-04 (Кузница) | III | `godot/project/assets/city/architecture-v2/levels/MIL-04-3.tscn` |
| B14_Blacksmith | MIL-04 (Кузница) | IV | `godot/project/assets/city/architecture-v2/levels/MIL-04-4.tscn` |
| B14_Blacksmith | MIL-04 (Кузница) | V | `godot/project/assets/city/architecture-v2/levels/MIL-04-5.tscn` |
| B15_MilitaryAcademy | MIL-05 (Военная академия) | I | `godot/project/assets/city/architecture-v2/levels/MIL-05-1.tscn` |
| B15_MilitaryAcademy | MIL-05 (Военная академия) | II | `godot/project/assets/city/architecture-v2/levels/MIL-05-2.tscn` |
| B15_MilitaryAcademy | MIL-05 (Военная академия) | III | `godot/project/assets/city/architecture-v2/levels/MIL-05-3.tscn` |
| B15_MilitaryAcademy | MIL-05 (Военная академия) | IV | `godot/project/assets/city/architecture-v2/levels/MIL-05-4.tscn` |
| B16_Infirmary | SUP-01 (Лазарет) | V | `godot/project/assets/city/architecture-v2/levels/SUP-01-5.tscn` |
| B17_SiegeWorkshop | SUP-02 (Осадная мастерская) | I | `godot/project/assets/city/architecture-v2/levels/SUP-02-1.tscn` |
| B17_SiegeWorkshop | SUP-02 (Осадная мастерская) | IV | `godot/project/assets/city/architecture-v2/levels/SUP-02-4.tscn` |
| B17_SiegeWorkshop | SUP-02 (Осадная мастерская) | V | `godot/project/assets/city/architecture-v2/levels/SUP-02-5.tscn` |
| B18_WallsAndGate | SUP-03 (Стены и ворота) | I | `godot/project/assets/city/architecture-v2/levels/SUP-03-1.tscn` |
| B18_WallsAndGate | SUP-03 (Стены и ворота) | II | `godot/project/assets/city/architecture-v2/levels/SUP-03-2.tscn` |
| B18_WallsAndGate | SUP-03 (Стены и ворота) | III | `godot/project/assets/city/architecture-v2/levels/SUP-03-3.tscn` |
| B18_WallsAndGate | SUP-03 (Стены и ворота) | IV | `godot/project/assets/city/architecture-v2/levels/SUP-03-4.tscn` |
| B18_WallsAndGate | SUP-03 (Стены и ворота) | V | `godot/project/assets/city/architecture-v2/levels/SUP-03-5.tscn` |
| B19_Watchtower | SUP-04 (Сторожевая башня) | V | `godot/project/assets/city/architecture-v2/levels/SUP-04-5.tscn` |
| B21_Sawmill | ALT-02 (Лесопилка) | I | `godot/project/assets/city/architecture-v2/levels/ALT-02-1.tscn` |
| B21_Sawmill | ALT-02 (Лесопилка) | IV | `godot/project/assets/city/architecture-v2/levels/ALT-02-4.tscn` |
| B21_Sawmill | ALT-02 (Лесопилка) | V | `godot/project/assets/city/architecture-v2/levels/ALT-02-5.tscn` |
| B23_HuntingLodge | ALT-06 (Дом охотника) | V | `godot/project/assets/city/architecture-v2/levels/ALT-06-5.tscn` |
| B24_FishingHut | ALT-07 (Рыбацкая хижина) | II | `godot/project/assets/city/architecture-v2/levels/ALT-07-2.tscn` |
| B24_FishingHut | ALT-07 (Рыбацкая хижина) | III | `godot/project/assets/city/architecture-v2/levels/ALT-07-3.tscn` |
| B24_FishingHut | ALT-07 (Рыбацкая хижина) | IV | `godot/project/assets/city/architecture-v2/levels/ALT-07-4.tscn` |
| B24_FishingHut | ALT-07 (Рыбацкая хижина) | V | `godot/project/assets/city/architecture-v2/levels/ALT-07-5.tscn` |
| B25_HerbalGarden | ALT-08 (Сад травника) | V | `godot/project/assets/city/architecture-v2/levels/ALT-08-5.tscn` |
| B26_StoneWorkshop | ALT-09 (Мастерская каменщика) | I | `godot/project/assets/city/architecture-v2/levels/ALT-09-1.tscn` |

## Сборка

Сцены собираются в самом Godot из рецептов (`project/tools/architecture/`, исключено из экспорта):

```bash
godot --headless --path project -s tools/architecture/build.gd            # все 40
godot --headless --path project -s tools/architecture/build.gd -- only=SUP-03-5
```

- `arch_kit.gd` — кит: черепица рядами, фахверк, кладка с угловыми камнями, арки, лестницы,
  пандусы, настилы, частоколы, инвентарь. Затенение у земли запекается в вершины; геометрия
  объединяется по материалам (одна поверхность на материал).
- `materials.gd` — общие материалы `architecture-v2/materials/*.tres` на текстурах `surfaces07`
  проекта (albedo/normal/ORM, трипланарная проекция).
- `recipes.gd` — 40 рецептов по референсам; проходы описаны полосами (`lanes`) в метаданных сцены.

## Проверка

```bash
godot --headless --path project -s qa_architecture.gd
```

Проверяет загрузку и габарит всех 40 сцен, выбор визуала для 36 типов × 5 уровней при строительстве,
пошаговом улучшении и после сохранения (JSON round-trip), побайтную неизменность 126 общих моделей и оверлеев
по `docs/02_FILE_MANIFEST.json`, проходы (габарит юнита или повозки протягивается через trimesh-коллизию
геометрии; ступень ≤ 7 см, уклон ≤ 1:5) и точки рабочих.
В городе нет навигационной сетки и коллизий зданий: юниты и рабочие ходят по рельефу (`sample_city`),
поэтому проходимость проверяется по геометрии.

## Версия 0.6.0 (build 38)

Изменения перенесены в код мобильного приложения 0.6.0 (ветка сборок для SideStore):

- `present_city()` берёт сцену уровня из `levelModels`; точка рабочего задаётся полем `worker`.
- «Стены и ворота» в 0.6.0 — стена вокруг двора. Её главные ворота теперь — сцена B18 текущего уровня
  «Стен и ворот» (I, пока здание не построено), в масштабе 1,6, чтобы проезд и башни соответствовали
  высоте кольца. Проём стены расширяется под сцену, сгенерированный надвратный узел у главных ворот
  не рисуется; боковые ворота и вид стены по уровням остаются прежними.
- При строительстве с нуля в лесах «растёт» сцена уровня I, если он переделан.
- `qa_city_parity.gd` сравнивает с 0.5.9 всё, кроме узлов переделанных уровней (как и леса стройки).

IPA: `tools/repack_engine_capsule.py` на капсуле движка 0.5.9 (байт-в-байт), пакет игры экспортирован из этого коммита.

## Build 39: изменения не теряются на следующих уровнях

Уровни вне CHANGES.md, идущие после изменённого, раньше показывали прежнюю модель без новых элементов,
и при улучшении здание «теряло» их. Теперь такие уровни остаются прежней моделью со своей исходной
надстройкой и сохраняют элементы предыдущего изменённого уровня (`"carried": true` в `levelModels`):
ратуша III–IV (портал и лестница II), ферма IV (амбар и проход III), конюшня IV–V (решётчатые створки,
левада, седельная III), академия V (павильон с картой и галерея IV; навес исходной надстройки V на месте
павильона вырезан из копии), мастерская каменщика II–V (рабочий навес I рядом со скалой).
Утверждённые серии B02, B04, B10, B12, B20, B22, B27 не затронуты.

## Build 52: план города — дворы, улицы, единое оформление уровней

- `src/town_plan.gd` строит по зданиям на их участках дворы (габарит здания по самому большому из
  пяти уровней из `assets/city/town_lots.json` + поля и площадка перед входом) и сеть прямых улиц:
  проспект от площади перед ратушей к главным воротам, улицы к остальным воротам, переулки ко всем
  дворам. Маршрут — дешевейшая из L/Z-форм вдоль промежутков между участками, при необходимости
  обход здания; проход под зданием стоит очень дорого, через край чужого двора — дороже обычного.
- `src/town_ground.gd` + `town_ground.gdshader` рисуют землю города одной сеткой по маске 0,25 м
  (земля дворов, брусчатка улиц, площади и площадок) и оформление уровней, одинаковое у всех зданий:
  II деревянный бортик, III мощёная площадка у входа, IV каменный бортик и столбы, V мощёный двор и фонари.
- Общие оверлеи уровней `city-details/<тип>-<уровень>.glb` городом больше не используются (файлы не
  изменены); переделанные сцены уровней (architecture-v2) и модели зданий — без изменений.
- Таблица габаритов: `godot --headless --path project -s tools/measure_footprints.gd -- --check`.
- Проверка: `qa_town_plan.gd`.

## Build 53: узнаваемые склад, амбар, рынок, каменоломня и шахта (QA 0.6.0 test 5, VIS-01…03)

Добавлены 19 уровней (всего 59 переделанных позиций + 10 перенесённых), переписаны рецепты V этих серий,
чтобы элементы предыдущих уровней не терялись при улучшении:

| Серия | Тип | Уровни | Узнаваемые признаки |
|---|---|---|---|
| B03_Warehouse | ECO-01 (Склад) | I–V | низкий длинный корпус, широкие откатные ворота, погрузочная платформа и пандус; III+ слуховое окно с крюком, IV кран, V кладовая |
| B04_Granary | ECO-02 (Амбар) | I–V | высокий корпус на каменных опорах, наружная лестница, жалюзи и вентиляционные башенки на коньке; V боковое крыло |
| B05_Marketplace | ECO-03 (Рынок) | III–V | круглая площадь, прилавки вокруг центра, шатёр; IV галерея; V фонтан с обходом и арка |
| B07_StoneQuarry | RES-02 (Каменоломня) | I–V | открытый забой со светлыми уступами, обращёнными к камере, скальный борт, площадка с блоками |
| B08_IronMine | RES-03 (Железная шахта) | I–V | тёмный холм, портал штольни (крепь → каменная арка), рельсы к улице, вагонетка |

Склад и амбар больше не используют общую модель `warehouse` (файл не изменён), каменоломня и шахта — `quarry27`/`ironmine27`,
рынок III–V — `market27`. Утверждённая ранее серия B04 переделана по замечанию VIS-01.

```bash
godot --headless --path project -s tools/architecture/build.gd -- only=ECO-01-1,ECO-02-1   # пересборка
godot --headless --path project -s tools/measure_footprints.gd -- --write                   # дворы
godot --headless --path project -s qa_architecture.gd
godot --headless --path project -s qa_building_looks.gd && godot --headless --path project -s qa_building_looks.gd -- --restart
xvfb-run -s "-screen 0 1100x760x24" godot --rendering-driver opengl3 --path project -s profile_building_levels.gd -- --out=/abs/dir --tag=after --pairs
```

## Build 54: все 27 зданий по рисункам, стройка по частям (test 8)

- `recipes.gd`: 135 позиций (27 типов × I–V), каждый уровень — своя сцена по рисунку `DRENOVAR-Bxx_*_L0y.png`.
  Общие части соседних уровней строятся одинаково (кит засеян по типу), поэтому при улучшении видно, что меняется.
- `arch_kit.gd`: каждая деталь (брус, короб, ряд гонта…) — «кусок»; `bake()` пишет время появления при стройке с нуля
  в альфу цвета вершины (земля → фундамент → каркас → обшивка → кровля от свеса → детали и товары).
  `build.gd → link_upgrades()` сравнивает уровни L−1 и L по треугольникам: UV2.x — когда новая часть появляется
  при улучшении (0 — часть уже стоит), UV2.y — когда заменяемая часть снимается (2 — остаётся).
- `src/build_reveal.gd(.gdshader)`: материалы стройки повторяют материалы кита (трипланарные карты, цвет вершин)
  и показывают части по часам заказа; модели без этих данных поднимаются/снимаются по высоте.
- `src/city_works.gd`: доставка и леса (0–8 % заказа), сборка (8–90 %), разборка лесов (90–100 %), подъёмник с грузом типа,
  носильщик; при улучшении — сцены уровней L и L+1 на участке, городское здание скрыто на время работ.
- Съёмка: `profile_building_levels.gd -- --all` (все 135 вариантов), `profile_build_steps.gd -- --type=ECO-02 --from=2`
  (кадры стройки/улучшения с неподвижной камерой).

## Build 1024: жители города вместо «рабочих на месте»

Прежние фоновые рабочие (жёсткие модели `Worker_*`, все клипы конечностей слиты в один цикл, «носильщик»
у ратуши на эллипсе 1,65×0,42 м, остальные — на смещении от здания, высота по `static_height`)
заменены жителями `src/townsfolk.gd`:

- Модели — гражданские персонажи «Леса потерянных» (`assets/forest_rescue/humans/lf_civilian_*.glb`, общий
  риг) через `ActorRig` (фоновая загрузка, расписной материал, оттенки одежды/волос по маске, сумка `Bag`
  скрыта у части людей); LOD2 на обычных зумах, LOD1 при зуме < 40. Шаг клипа совпадает со скоростью:
  ходьба 1,193 м/с, с грузом 0,944 м/с (скорость опорной стопы, `qa_townsfolk.gd`), скорость
  воспроизведения = пройденный за кадр путь / шаг клипа. Смена клипов 0,25 с, поворот не быстрее 5 рад/с.
- Ходят только по плану города: осевые линии улиц с разбиением на перекрёстках, площадь у ратуши как
  открытое место, путь по двору от выхода улицы к двери. Каждый участок проверяется один раз на
  план (фоном, ≤ 2,5 мс за кадр): стволы ≥ 1,1 м, реальная занятость зданий (`assets/city/town_solids.json`,
  `tools/measure_town_solids.gd`: геометрия от 0,15 до 2,0 м над участком на сетке 0,25 м, плюс «нижняя»
  маска от −0,6 м для участков на склоне и ворота стены от −3 м), столбы ворот, вода, стена, плац,
  стройки, нераскрашенная земля. Люди держатся правой стороны улицы, углы скруглены.
- Распорядок: у каждого здание и маршрут (лесоруб → склад с бревном, фермер → амбар с мешком, носильщик
  склад → рынок с ящиком, кузнец, каменотёс, травница, гонец из казарм, управляющий ратуши, гуляющие
  по площади и местам во дворах). Остановка у двери (у двери три места, у задней — одно), жест или
  осмотр 2–6 с, вход в дверь с исчезновением и выход позже. Всё — функция часов сервера с личным
  сдвигом; за кадром человек только считается по часам (без AnimationPlayer). Догнавший идущего
  впереди замедляется, выходящий пропускает проходящего. Число: 6 при ратуше I, до 14 при V
  (сколько позволяют места у дверей и во дворах; в тестовом городе V — 12).
- Ноги — на видимой земле: сетка 1 м + 0,08 м земли города (`town_ground.gd`) или узлы террейна там,
  где он выше. `landscape.walk_ground()` даёт ту же высоту рабочим `city_works.gd`; лесоруб выбирает
  подход к дереву, свободный от других стволов и зданий.
- Тени: под каждым — контактное пятно (один MultiMesh на всех), солнечная тень от модели — только при
  зуме < 50 (на обычном зуме 70 она в 1–2 пикселя и не читается, а проход теней стоит дорого на телефоне).
- Запуск не дольше прежнего: `townsfolk.gd` и скрипты `ActorRig` грузятся фоном после показа города
  (`landscape.attach_townsfolk()` из `present_workers`, около 0,5 с), модели — тоже фоном; план улиц —
  в первых кадрах после этого. До того город пуст, а `walk_ground()` — прежняя `ground_point()`.
- Проверка: `qa_townsfolk.gd` (ратуша I/III/V, по 120 с); съёмка: `qa_townsfolk_shots.gd`,
  `godot/tools/townsfolk_sheets.py`, карта сверху: `godot/tools/townsfolk_map.py`.
