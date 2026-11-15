# Серверный патч move-building-v2 (перенос зданий) к DRENOVAR Server v92

**Статус: подготовлен и проверен локально, на боевой сервер (`drenovar-game`) не установлен.**
Установка на боевой Worker требует отдельного подтверждения владельца.

## Что это

`move-building-v1` (SHA-256 `2899bced…ab25c`, см. `../move-building-v1/README_RU.md`), перенесённый на
текущий набор патчей боевого сервера: route-approach-v2, route-depart-v1, combat-reach-v1,
workers-v1, receipts-v1, world-battle-v1 (deploy commit `91560da`).

Отличия от v1:

- `kingdom29.js`: нумерация id новой постройки (`freeBuildingId`) встроена в ветку `build`,
  изменённую workers-v1.
- `move-building.mjs`: здание нельзя перенести, пока над ним или на целевом участке работает
  **любой** строитель — `order` и `order2` (второй рабочий workers-v1), рубка `job`/`job2`.
- Тест `move-building.mjs` дополнен: при двух рабочих здание во втором заказе не переносится,
  соседнее свободное здание переносится.

## Где патч

Частный репозиторий сервера: `cloudflare_transfer/incoming/move-building-v2.patch`,
SHA-256 `03fe915fa0780f83132d9301344211f3b006bb491fd7b7a8f3de17d1faec13f0`
(в этот публичный репозиторий не добавлен: в нём фрагменты серверного кода).

## Проверки (Node 24.22.1)

- `node gameplay37/tests/move-building.mjs` — ok.
- 12/12 оригинальных тестов v92, тесты патчей route-approach, route-wall, route-depart,
  combat-reach, workers-v1, receipts-v1, world-battle-v1 — без изменений проходят.
- Тесты Worker: test_game_worker (15), test_settlement_transfer (19), test_player_auth (31),
  test_staging_worker (14).
- Клиент (сборка 52): `qa_move_building.gd` против локального сервера с патчем — все проверки
  переноса проходят (две проверки city-defence-v1 относятся к другому, не установленному патчу).
