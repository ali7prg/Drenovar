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
