# creatures-world-v1 — Камнеклык и Горный Драгор на общей карте (предложение, не применено)

**Статус:** патч подготовлен и проверен локально, **в `ali7prg/drenovar-server` не внесён и никуда не
выложен**. Он меняет оригинальный файл v92 `gameplay37/server/world62.mjs`; по правилам репозитория
сервера такую правку одобряет владелец (новый SHA-256 вносится в
`PATCHES/approved-original-modifications.json` только после ревью). Клиент из этой же ветки работает
и без патча: на карте тогда, как и сейчас, только `velkor-1..3`.

База: `drenovar-server` ветка `codex/combat-live-repair-20261116`, коммит `c6dbdb4`
(в ней работающий сейчас V6 runtime `e5062aa`). Патч применяется без конфликтов (`git apply --check`).

## Что меняется

| Файл | Изменение |
|---|---|
| `DRENOVAR-Server-v92/gameplay37/server/world62.mjs` (оригинал v92) | `velkorSites` прежние, байт в байт те же позиции и id. Добавлены `worldCreatureSites` = `velkor-1..3` + `kamneklyk-1..3` (холмы, высота 9–20 м, уклон ≤ 0,75 на 2,6 м) + `dragor-1..3` (высокогорье, 21–34 м, уклон ≤ 0,5 на 3,4 м). Точки детерминированы, на суше, ≥ 16 м от каждого места поселения, ≥ 22 м друг от друга, у каждой патруль 2,4 м. `worldKind` = вид существа; прежний `velkor` принимается для любого существа и записывается видом цели. Бой — тот же `simulate()` с каталожным spec вида, награды и откат — правила Велькора. |
| `v6/marches.mjs` | Цель похода — любое мировое существо (`worldSite`), проверка вида, `worldKind` нормализуется. |
| `v6/timeline.mjs` | Начало и итог боя ищут цель через `worldSite` (вместо `velkorSites`). |
| `v6/tests/world-creatures.test.mjs` (новый) | 5 тестов: неизменность `velkor-1..3`; размещение и спецификации новых точек; поход и бой Камнеклыка III (с `tusk_sweep`) и Драгора I (с `shockwave`); награда ровно один раз при повторных опросах и повторе той же команды; резерв цели против второго игрока; поражение без награды и возврат выживших; восстановление после отката; старый `worldKind: velkor` на точке Камнеклыка. |

Точки (x, z): kamneklyk-1 (102.5, 20), kamneklyk-2 (−77.5, 75), kamneklyk-3 (92.5, 57.5),
dragor-1 (−72.5, −87.5), dragor-2 (70, −95), dragor-3 (−102.5, −97.5).

## Проверено (Node 24.22.1, с применённым патчем)

* `node --test v6/tests/*.test.mjs` — **75/75** (включая 5 новых).
* `python3 tools/run_original_tests.py` — **12/12** оригинальных файлов тестов.
* `node cloudflare_transfer/tests/*.mjs` — **4/4**.
* `python3 DEPLOYMENT/verify_current_sources.py` ожидаемо отметит изменённый `world62.mjs`, пока владелец
  не одобрит и не закрепит его хеш.

## Как применить после ревью

```bash
cd drenovar-server && git checkout -b feature/creatures-world-v1 c6dbdb4
git apply ../Drenovar/server-patches/creatures-world-v1/creatures-world-v1.patch
sha256sum DRENOVAR-Server-v92/gameplay37/server/world62.mjs   # ожидается 5130268e9f3ae797244234bac030e04d72078341bff30cf5e128ef5a88a85745
# после одобрения: внести этот хеш в PATCHES/approved-original-modifications.json, затем полный набор проверок
```

SHA-256 файла патча: `a83129e7adbff537982399f1f115241bce445764958c43a8e0b0b0510155a9ec`.
Выкладка на Worker не выполнялась и этим документом не разрешается.
