# Производительность: проверенный код и план измерения

Статус: выполнен статический аудит текущего доступного кода, подготовлен и протестирован автономный инструмент диагностики. Причина лагов на физическом iPhone 12 **не установлена**, лаги не объявляются исправленными. Скриншоты сами по себе не доказывают, какой backend, коммит и профиль качества работают на телефоне.

## Исходная база

2026-11-17 UTC повторно проверен `/workspace/drenovar-server`: ветка `work`, HEAD `56dce339b8adf527244c5d59fdc64a0f701ac64b`, рабочее дерево чистое. Репозиторий https://github.com/ali7prg/drenovar-server.git. Внутри `DRENOVAR-Server-v92/` оригинальный снимок `365276cc169943adc48847c0e9d86ae23e77fb3e`. Команда `python3 DEPLOYMENT/verify_current_sources.py` прошла:407 оригинальных файлов,407 неизменны. Ничего в исходном репозитории не редактировалось.

Изученный клиент — Three.js r170 с WebGL и Canvas fallback. Код включает две сцены: поселение `CityView` и общий мир `world.js`. Новый внешний лес вокруг поселения не следует автоматически делать отдельной сценой общего мира: сначала сопоставить показанный пользователем экран с актуальным живым клиентом. Если Claude Code получает другую/native ветку, повторить сопоставление, не переносить JS-хуки в выдуманную Godot/Unity сцену.

В компактной копии нет480 оригинальных графических файлов,349286870 байт; список в `cloudflare_transfer/REQUIRED_WEB_ASSETS_480.json` исходного репозитория. Полное визуальное сравнение до/после требует этих настоящих байтов, а не заглушек. Ни cloud CPU benchmark, ни красивый рендер не заменяют замер устройства.

Ниже пути относительно `DRENOVAR-Server-v92/`; номера строк — проверенный снимок.

## Что подтверждено исходным кодом

| Реальная точка | Наблюдаемый факт | Измерение и возможное действие после него |
|---|---|---|
| `dist/city/view.js:34,54`, constructor tick и `draw` | `premium.update`, landscape update, shadow scheduling идут до начала измерения `draw`. `recordFrame('city-webgl')` не включает весь update CPU | Измерять `renderClock.tick` целиком плюс этапы. Нельзя считать прежнюю метрику общей стоимостью кадра |
| `dist/world.js:127–133`, `render(time)` | Обновление камеры, groundCover, townLayer, солнца, environment идёт до `drawStarted`; label/minimap идут после `recordFrame` | Обернуть `worldLoop.tick` целиком. Сравнить CPU подготовки, submission, DOM отдельно |
| `dist/world.js:75`, `mobile` | Профиль один раз выбран через `(max-width:650px)`. Landscape-viewport шире650 получает `false`, даже если устройство iPhone | Записать реальные innerWidth/innerHeight и mobile. Проверить старт в обеих ориентациях и rotation. Классификатор качества должен быть согласован с устройством/измерениями; нельзя менять camera framing случайно вместе с profile |
| `dist/world.js:81,170` | DPR cap1.6 при mobile, иначе1.8; `CityView` cap1.5 (`view.js:36,50`) | При DPR1.8 площадь буфера на26.6% больше1.6, на44% больше1.5. Это арифметика, не измеренный FPS выигрыш. Не снижать DPR автоматически без сравнения читаемости |
| `dist/environment/models.js:65,67` | mobile выбирает3600/5500 forest placement attempts и600/1000 detail attempts | Измерить фактические instances, triangles и память. Попытки размещения не равны количеству видимых деревьев |
| `dist/environment/landscape.js:25`, `WorldGroundCover.update` | При близком расстоянии<65 и смещении target≥8 синхронно до9000 попыток; до1800 grass,100 fern,120 rock instances | Проверить пики pan/zoom в порогах; при доказанном пике строить чанки заранее/по бюджету с двойным буфером, не исчезновением поля |
| `dist/environment/scene.js:11`, `createEnvironment().update` | По quantized camera key запрашивает spatial grid, затем обходит type-lists, пакует near/far matrices/colors, пересчитывает bounds и shadows | Замерить cull/pack/upload. Spatial culling уже есть; не предлагать «добавить culling» как отсутствующую функцию |
| `dist/world.js:81,85,127` | autoUpdate теней=true, directional map1024², солнце следует target; при активных актёрах рендер идёт каждый RAF | Профиль shadow pass. Если подтверждена цена: разделить static/dynamic caster и update-on-change; не замораживать тени движущихся людей |
| `dist/city/view.js:34` | В городе `shadowMap.needsUpdate` выставляется примерно каждые100ms при активном кадре | Проверить CPU/GPU теней; authored foliage wind не обязан обновлять тяжёлую тень каждого листа |
| `dist/city/premium.js:50,89` | Tree LOD пересчитывается по ключу zoom/center/viewport, mixers имеют frustum visibility checks | Сохранить существующие guards. Локальные allocations Sphere/Vector3 и обходы сами по себе не доказательство проблемы; оптимизировать после GC profile |
| `dist/city/life.js:11–12` | CPU деформирует флаги; дым ограничен8 emitters×16 instances, но update вызывается каждый активный tick | Не размножать этот цикл на весь новый лес. Для ветра деревьев — shader uniforms, для дыма spatial visibility и фиксированный budget |
| `dist/city/muster.js:137` | Флаги обновляются каждый update; morph-позы строя ограничены шагом0.05s | Не добавлять отдельный RAF на каждого спасённого. Плавность root/camera отделять от частоты sampling костей вдали |
| `dist/city/terrain.js:65–70` | setCity строит terrain normals, yards, дороги, инстансы травы; это структурное обновление, не обязательная работа каждого кадра | Не вызывать setCity/rebuild для дыма, шага NPC или каждого сохранённого rescue-флага |
| `dist/environment/world-actors63.js:145–169` | Видимый зверь/армия поддерживает активный RAF; offscreen армия удаляется и создаётся при возвращении; loader кэширует GLB | Замерить mixer CPU и повторное создание/GC; pool только если доказана цена, с правильным lifecycle |
| `dist/environment/formation67.js:31–40` | Layout использует map/new member points; layout bag уже WeakMap-cache | Не вычислять длинный путь и formation всех36 спасённых каждый кадр; разделять событие маршрута и interpolation |
| `dist/environment/world-towns.js:22–24` | Quantized LOD переупаковывает batches/impostors, bounds; настоящие близкие GLB и дальние impostors уже есть | Сохранить силуэты; контролировать popping. Не заменять ближние здания плоскими картинками |
| `gameplay37/client/online.mjs:132–151` | Серверный poll650ms при active armies, иначе3000ms; UI/state применяются через общий connection | Новые персонажи не должны каждый получать отдельный poll или отправлять позу костей на сервер |

Эти пункты определяют, **что профилировать**, а не процент вины каждого участка. Шейдер terrain с несколькими текстурными выборками также заслуживает GPU capture, но отключение всех материалов без измерений не является исправлением.

## Уже существующие оптимизации, которые нельзя ломать

- `dist/runtime/world-build-client56.js`: Worker и transferable arrays; cooperative fallback. Подготовка raster1050×840 и field605×485 не происходит каждый кадр.
- `dist/runtime/spatial30.js`: grid32 и frustum; terrain делится `chunkGeometry`.
- `dist/runtime/assets.js`: общая очередь3 декодирований, кэш GLB/images/materials, retry после ошибки.
- `dist/runtime/gltf-retention28.js`: освобождает parser source buffers, сохраняет animation extras. Нельзя строить runtime на удалённом `parser.json.nodes`.
- `dist/runtime/scene-gpu-resources85.js`: освобождает буферы скрытой сцены, учитывает разделяемые ресурсы.
- `RenderClock` / `VisibleFrameLoop`: принадлежащий сцене clock и pause/wake. Новый контент использует его, а не собственные бесконечные loops.
- `scene.js`, `premium.js`, `world-towns.js`: уже существуют instancing, LOD и visibility. Новые чанки должны входить в эту архитектуру.

## Поставляемая диагностика

`tools/performance-probe.mjs` — готовый к подключению исходный ES module, **ещё не подключён к игре**. Без внешних зависимостей, запросов сети, собственного RAF и сохранений игрока. `tests/performance-probe.test.mjs`:8 тестов прошли на Node v24.22.1; лог `qa/performance-probe-tests.txt`.

Проверены: ограниченные гистограммы/число series, сохранение `this`/аргументов/return/исключения, длинные активные задержки, исключение background gap через boundary, точное восстановление своих wrappers, разделение shared-renderer сцен, полный tick. Это не браузерный/device benchmark и не тест влияния instrumentation на fps.

Времена синхронные и **включающие вложенные вызовы**: wholeTick, premiumUpdate, draw нельзя складывать. Wrap async-функции измеряет лишь запуск до Promise; не использовать это как сетевую задержку. `renderer.info.memory` даёт числа объектов, не мегабайты GPU. `submissionInterval` — интервал отправки кадров, не подтверждённый момент изображения на дисплее и не GPU timer. Гистограмма имеет0.25ms bins, p95 возвращает верхний край; overflow≥1000ms не отбрасывается.

Добавить QA-only импорт в реальные closure, где view/worldLoop уже доступны, после `EncounterLayer` и готовности объектов. Не предполагать `window.view` или другую несуществующую глобальную переменную:

```js
import {attachCityProbe, attachWorldProbe} from './PATH_TO_NEW_QA_MODULE.mjs';
// City: реальный openedView из installCity/open, после online37.attach.
const probe = attachCityProbe(openedView);
// ИЛИ World: локальные переменные dist/world.js после init.
const worldProbe = attachWorldProbe({
  worldLoop, renderer, scene, groundCover, townLayer, environmentLayer,
  nativeActors: nativeActors63
});
```

Показанные импорты/переменные probe — новый код диагностики, не готовый патч. Использовать один активный probe за прогон, не цеплять их обоих на общий renderer одновременно. Собирать10–60s сценарии, `probe.report()` сериализовать только при окончании сегмента. При hide/visibilitychange/смене сцены/старт-стоп сценария вызывать `probe.boundary()`. После окна замера `probe.dispose()`, снять свои DOM listeners. Не вызывать report/JSON.stringify на каждом кадре. Не включать probe в обычную игровую сессию по умолчанию.

Для world idle intervals на карте с отрисовкой по запросу не называть1 frame/120 callbacks «низким fps»: измерять FPS только внутри явно активного pan/zoom/animation сценария. Для motion взять одни и те же input gestures и seed/snapshot.

Патч «лаги исправлены» намеренно не подготовлен: отсутствуют полный графический baseline и device profile. Изменение mobile-width branch затрагивает и framing/placement, а теней — видимый результат; нельзя выдавать эти изменения за безопасно проверенную оптимизацию без фактической сцены.

## Целевая организация полного леса и толпы

Вся внешняя территория может выглядеть заполненной, хотя GPU обрабатывает видимые чанки. Сервер хранит всех спасённых и12 площадок независимо от видимости. Разрешённое художественное изменение ambient леса не даёт права удалить `city.progress.felled/sites`, здания, воинов или игроковые ресурсы. Разделить новые decorative tree IDs и существующие harvest IDs.

Атлас уже задаёт16 логических чанков56×56 world units. Внутри них допустимы более мелкие spatial cells16–24 единицы для culling/preload; это не другая сетка сохранения fog и не повод менять постоянные IDs. Размер rendering subcells подобрать по реальной камере; не закреплять screenshot-pixels как метры. Static foliage инстансировать по материалу/LOD/чанку, bounds консервативные. Использовать hysteresis и preload соседей до движения камеры. Не обходить все деревья карты каждый кадр: cull spatial index на смене camera cell/LOD/revision, обновлять лишь активный набор. Ветер — uniform времени/амплитуды и phase из seed, без JS-прохода по вершинам каждого дерева. Туман — несколько ограниченных mask/shell слоёв с контролем overdraw; избегать сотен полноэкранных прозрачных quads.

Персонажи: приоритет guide/current encounter/rescue group/boss. Для далёких людей допустимы настоящие авторские LOD и запечённые анимационные представления, после их производства; изображения-концепты этим не являются. Положение по маршруту интерполируется плавно каждый render; sampling дальнего skeletal pose может быть реже с interpolation. Нельзя экономить, заставляя близкого человека двигаться рывками или скользить. Перемещение групп по маршруту/событиям, не A* для каждого NPC на каждый tick. Смотрите `docs/ANIMATION_PRODUCTION_RU.md`.

## Измеряемые ворота приёмки iPhone 12

Числа ниже — стартовые ограничения производства, не фактические достижения. Если baseline сам превышает их, сначала отдельный отчёт baseline и исправление, затем новая кампания; не скрывать базовый лаг добавочными средними значениями.

| Показатель | Цель и метод |
|---|---|
| Активная камера/бой, после прогрева | Цель60fps, минимум стабильные30fps; p95 submission interval≤33.5ms, p99≤50ms; p99 извлечь из Safari trace, не приписывать нашему report |
| CPU всего render/update tick | p95≤12ms для возможности GPU уложиться в33.3ms; детализация phase logs обязательна |
| Добавочная CPU-работа rescue | p95≤3ms против того же baseline маршрута; single spike≤50ms при preload; без main-thread decode всех12 зон сразу |
| Взаимодействие | p95 input→first submitted feedback≤100ms локально; сетевой commit отдельно с длительностью/RTT, не прятать его в FPS |
| Крупные задержки | После прогрева нет повторяющихся>100ms stalls при движении; каждый зарегистрированный stall разобрать по trace |
| Дополнительная видимая геометрия | Начальная цель≤180k triangles и≤55 draw calls для rescue-набора в кадре; весь бюджет включает NPC, fog/gates/shadows отдельно измеряются |
| Персонажи | Стартовый лимит24 одновременно близких полноценных skinned актёра **добавки**, включая guide/escort/civilians/boss; итоговый cap вместе с существующими армиями определяется device profile. Сохранённые36 граждан не исчезают из истории из-за visibility |
| Добавочная texture residency | Начальная цель≤48MiB включая mipmaps; считать декодированные размеры и формат, а не размер PNG/ZIP. Это требует внешнего отчёта, renderer.info не даёт bytes |
| Длительный прогон |15min, одинаковая яркость/заряд/температура; median fps на15-й минуте ≥85% относительно3-й; нет reload, WebGL context loss или системного закрытия |
| Lifecycle |20 world↔city/arena переходов: числа textures/geometries после settling возвращаются в объяснимый cache plateau, без роста на каждом цикле; проверить background30s и возврат |

Сцены проверки: существующая база/центр; лесной pan с несколькими чанками; клетка с3 пленниками+охрана; отряд проводника; конвой после нескольких спасений; максимально населённый текущий вид; каждая из3 фаз босса; уменьшенный motion; muted audio; rotate/zoom; cold load и тёплая повторная загрузка. Обе ориентации запуска проверяются отдельно из-за mobile-width branch.

Записать iPhone модель, iOS/Safari/PWA, commit, backend WebGL/Canvas, viewport/DPR/drawingBuffer, save fixture без персональных данных, quality profile и список реально видимых актёров. Сравнение до/после по одному сохранению и одинаковому пути камеры. Не включать screen recording в основной замер без отдельного контрольного прогона: запись сама влияет на устройство.

Непроверено этим комплектом: реальные Safari GPU timings, hardware память/температура, генерация новых rig/clip, загрузка всех исходных480 assets, конечный streamed forest в игре. Эти работы остаются обязательными для Claude Code; отчёт об установке profiler не считается завершением оптимизации.
