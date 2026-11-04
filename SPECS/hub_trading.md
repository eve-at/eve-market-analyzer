# ТЗ: режим «Hub Trading» в разделе Hub Hauling — перевозка под выставление sell-ордеров

Доработка раздела из [hub_hauling.md](hub_hauling.md). Всё, что там описано, продолжает работать без изменений как режим **Instant**.

## 1. Цель

Найти товары, которые можно **мгновенно купить** в хабе-источнике (выкупив чужие sell-ордера), перевезти в хаб-назначение и **выставить там свой sell-ордер** на один тик дешевле лучшего.

В отличие от режима Instant:
- выручка приходит не сразу, а по мере продаж; срок нужно оценивать;
- при выставлении ордера в хабе-назначении платится **Broker Fee**, своя для каждой станции (зависит от standings персонажа к корпорации-владельцу станции и её фракции), а при каждом изменении цены платится relist fee;
- количество ограничено не стаканом buy-ордеров, а **спросом** в назначении: сколько товара реально продаётся за разумный срок.

Дополнительно в обоих режимах считается **ISK/час ходки**: прибыль за рейс, делённая на время рейса. Для Hub Trading доход при этом отложен во времени, и это показывается отдельно (срок продажи).

## 2. Переключение режимов

- На экране Hub Hauling над панелью параметров появляется RadioGroup **Mode**:
  - `Instant (sell to buy orders)`: текущий режим, по умолчанию.
  - `Trading (place sell orders)`: новый режим.
- Выбранный режим сохраняется в `save_setting('hub_hauling_mode', ...)`.
- При переключении:
  - показываются поля и колонки нужного режима и скрываются нерелевантные (§5.1);
  - результаты предыдущего поиска очищаются, потому что их колонки другие;
  - заголовок под названием экрана меняется на описание режима.
- Карточка на главной странице и роутинг не меняются.

## 3. Этап 0: проверка API (до основной разработки)

Цель: подтвердить на реальном персонаже, что Broker Fee можно считать автоматически, и зафиксировать результат в этом файле (§3.4).

### 3.1. Что нужно получить

| Данные | Эндпоинт ESI | Scope | Примечание |
|---|---|---|---|
| Standings персонажа | `GET /characters/{character_id}/standings/` | `esi-characters.read_standings.v1` | Список `{from_id, from_type, standing}`, `from_type` ∈ `agent`, `npc_corp`, `faction`. Фильтр по типу на клиенте |
| Навыки | `GET /characters/{character_id}/skills/` | `esi-skills.read_skills.v1` | Берётся `active_skill_level` для Broker Relations (3446), Advanced Broker Relations (16597), Accounting (16622) |
| Фракция корпорации станции | Fuzzwork `crpNPCCorporations.csv` | не нужен | Колонка `factionID`. Корпорация станции берётся из `stations.corporationID`. ESI `/corporations/{id}/` поля `faction_id` для NPC-корпораций не отдаёт (проверено, §3.4) |
| Названия фракций | Fuzzwork `chrFactions.csv` | не нужен | `factionID`, `factionName` |

Корпорации-владельцы станций хабов (из таблицы `stations`):

| Хаб | corporationID |
|---|---|
| Jita | 1000035 |
| Amarr | 1000086 |
| Dodixie | 1000120 |
| Rens | 1000049 |
| Hek | 1000057 |
| Oursulaert | 1000120 |
| Tash-Murkon Prime | 1000010 |
| Agil | 1000125 |

### 3.2. Шаги проверки

1. Добавить оба scope в `EVE_SCOPES` в `settings.py.example` и локальном `settings.py`.
2. Перелогиниться персонажем на странице EVE Online Account: старые токены новых прав не имеют.
3. Скриптом (вне UI) получить standings, навыки и `faction_id` для корпораций из таблицы выше. Посчитать Broker Fee по §4.1 для каждого хаба.
4. Сравнить с Broker Fee, который игра показывает в окне выставления sell-ордера на соответствующей станции (в Jita и Amarr как минимум). Допустимое расхождение 0.01 п.п.
5. Сравнить посчитанный sales tax (§4.2) с тем, что показывает игра.

### 3.3. Решение по результату

- **Совпадает:** автоматический расчёт (§4) является основным, ручные поля на EVE Online Account остаются как fallback.
- **Не совпадает или данных нет:** выяснить причину (другая формула, нужны effective standings, есть надбавка и т.п.), обновить §4.1 и повторить. Если автоматически посчитать нельзя, в режиме Trading показывается ручное поле Broker Fee, % для хаба-назначения, а значение по умолчанию берётся из `characters.broker_fee_sell`.

### 3.4. Результат проверки

Проверено 2026-11-04 на персонаже Marcelo Panacan (2113841915).

- `GET /characters/{id}/standings/`: HTTP 200, 283 записи, `from_type` = `agent`, `faction`, `npc_corp`.
- `GET /characters/{id}/skills/`: HTTP 200. Broker Relations 5, Advanced Broker Relations 5, Accounting 5.
- `GET /corporations/{id}/` для NPC-корпораций **не содержит `faction_id`** (ключи: `ceo_id, creator_id, description, home_station_id, member_count, name, shares, tax_rate, ticker, url, war_eligible`). Фракция берётся из Fuzzwork `crpNPCCorporations.csv` (283 корпорации).
- Sales tax по формуле §4.2: 3.375%. На EVE Online Account вписано 3.37, совпадает.

Посчитанный Broker Fee (BR 5):

| Хаб | Корпорация | Фракция | Corp standing | Faction standing | Broker fee |
|---|---|---|---|---|---|
| Jita | Caldari Navy | Caldari State | 9.89 | 8.58 | 1.0448% |
| Amarr | Emperor Family | Amarr Empire | 0.00 | 4.83 | 1.3550% |
| Dodixie | Federation Navy | Gallente Federation | 7.68 | −1.99 | 1.4060% |
| Rens | Brutor Tribe | Minmatar Republic | 1.03 | 5.85 | 1.3040% |
| Hek | Boundless Creation | Minmatar Republic | 0.00 | 5.85 | 1.3245% |
| Oursulaert | Federation Navy | Gallente Federation | 7.68 | −1.99 | 1.4060% |
| Tash-Murkon Prime | Kaalakiota Corporation | Caldari State | 0.04 | 8.58 | 1.2419% |
| Agil | CONCORD | CONCORD Assembly | 0.00 | 3.00 | 1.4100% |

Сверка с игрой:
- Jita: на EVE Online Account вписано 1.04%, расчёт 1.0448%. Совпадает с точностью до округления.
- Amarr: **ожидает сверки** с окном выставления ордера в игре (расчёт 1.355%).

Вывод: автоматический расчёт работоспособен и используется как основной (§3.3, первый вариант).

Побочная находка: Fuzzwork перенёс CSV в `/dump/latest/csv/`, старые адреса отдают 404, а в новых файлах `invTypes` и `mapSolarSystems` есть новые колонки. Адреса в `settings.py(.example)` обновлены, импорт статики теперь пропускает неизвестные колонки.

## 4. Комиссии

### 4.1. Broker Fee (NPC-станция)

Источник: https://wiki.eveuniversity.org/Trading

```
broker_fee_% = 3.0 − 0.3 × BrokerRelations − 0.03 × faction_standing − 0.02 × corp_standing
```

- Standings **базовые** (как их отдаёт ESI), без учёта навыков Connections и Diplomacy. Могут быть отрицательными, тогда комиссия растёт.
- Нет standing к корпорации или фракции означает 0.
- Минимальная комиссия за ордер 100 ISK.
- При BR 5 и максимальных standings получается ровно 1.0%.
- Считается для **станции хаба-назначения** (там выставляется ордер). В источнике покупка мгновенная, broker fee нет.

### 4.2. Sales tax

```
sales_tax_% = 7.5 × (1 − 0.11 × Accounting)
```

Платится с каждой продажи. Если навыки получены из ESI, используется расчётное значение; иначе `characters.sales_tax`, как сейчас.

### 4.3. Relist fee

Изменение цены ордера (обычно снижение, чтобы оставаться первым в стакане):

```
relist_fee = (1 − (0.5 + 0.06 × AdvancedBrokerRelations)) × broker_fee_% × new_order_value
           + broker_fee_% × max(new_order_value − old_order_value, 0)
```

При снижении цены вторая часть равна 0. В расчёте используется параметр **Expected relists** (сколько раз в среднем придётся менять цену). Стоимость одной перестановки на единицу товара:

```
relist_rate = (1 − (0.5 + 0.06 × ABR)) × broker_fee_rate
```

### 4.4. Где хранить и показывать

- Новая таблица `character_standings (character_id, from_id, from_type, standing, fetched_at)` и `character_skills (character_id, skill_id, level, fetched_at)`; PK `(character_id, from_id)` и `(character_id, skill_id)` соответственно.
- Таблицы `npc_corporations (corporation_id PK, name, faction_id)` и `factions (faction_id PK, name)`: загружаются из Fuzzwork (`crpNPCCorporations.csv`, `chrFactions.csv`) при Sync, если пусты.
- На странице EVE Online Account кнопка **Sync Standings & Skills**: загружает standings и навыки, пересчитывает sales tax и показывает таблицу Broker Fee по всем хабам. Если не хватает scope (ESI вернул 403), появляется сообщение «Log in again to grant new permissions».
- В режиме Trading на экране Hub Hauling под хабами показывается строка, например: `Broker fee in Amarr: 1.38% (BR 5, Amarr Empire 2.00, Emperor Family 3.00)`. Если данные не синхронизированы, строка оранжевая с подсказкой про Sync.

## 5. Интерфейс режима Trading

### 5.1. Поля

| Поле | Instant | Trading | По умолчанию | Примечание |
|---|---|---|---|---|
| Hub A / Hub B, ⇄, Update Orders | ✓ | ✓ | | Без изменений |
| Cargo capacity, Budget, Max cargo value | ✓ | ✓ | | Без изменений |
| Min profit per item, Min margin | ✓ | ✓ | | Профит и маржа уже за вычетом всех комиссий режима |
| Market groups | ✓ | ✓ | | |
| Route | ✓ | ✓ | Safest | Radio `Safest (high-sec only)` / `Shortest` |
| Time per jump, sec | ✓ | ✓ | 60 | Зависит от корабля, задаёт пользователь |
| Overhead per trip, min | ✓ | ✓ | 10 | Доки, андоки, покупка, выставление |
| Max days to sell | | ✓ | 7 | Сколько дней готов ждать продажи партии |
| Market share, % | | ✓ | 20 | Какую долю ежедневного объёма продаж реально забрать с учётом конкурентов |
| Expected relists | | ✓ | 2 | Сколько раз придётся менять цену ордера |

Все значения сохраняются через `save_setting('hub_hauling_*')`, как остальные параметры.

### 5.2. Вкладка Deals (Trading)

| Колонка | Описание |
|---|---|
| Direction | Как в Instant |
| Item | typeName |
| Qty | Количество к покупке (§6.3) |
| Volume, m³ | |
| Max buy price | Потолок цены при покупке в источнике |
| Sell price | Цена нашего ордера в назначении (лучший sell минус один тик) |
| Investment | Сумма закупки |
| Fees | Broker fee + relists + sales tax за всю партию |
| Profit | Выручка после всех комиссий − Investment |
| Margin, % | Profit / Investment × 100 |
| Daily volume | Средний объём продаж в день в регионе назначения за 30 дней |
| Days to sell | Qty / (Daily volume × Market share) |
| Competitors | Sell-ордера в назначении, обновлённые за последние 2 дня (как на Trade Opportunities) |
| Profit / m³ | |
| Limited by | `market`, `cargo`, `budget`, `risk`, **`demand`** |

### 5.3. Вкладка Cargo plan (оба режима)

К итоговой строке каждого направления добавляется:

```
Route: 45 jumps (safest) · Trip: 55 min · ISK/h: 120,000,000
```

В режиме Trading ещё `Sell-through: up to 6.8 days` (максимальный Days to sell среди товаров плана).

Под двумя направлениями строка для рейса туда-обратно:

```
Round trip (Jita → Amarr → Jita): profit 230,000,000 · 1 h 50 min · ISK/h 125,000,000
```

ISK/час в Trading подписывается как «ISK/h of hauling time, income delayed» с тултипом, что деньги приходят по мере продаж.

## 6. Алгоритм режима Trading

Новый файл `src/handlers/hub_trading_handler.py`. Используются функции из `hub_hauling_handler.py`: `resolve_hubs`, `get_packaged_volumes`, `_load_order_books`, `apply_limits`, `build_cargo_plan`.

### 6.1. Цена продажи

Для каждого товара в назначении:
- `best_ask_dst`: минимальная цена sell-ордеров на станции назначения;
- `sell_price = get_next_sell_tick(best_ask_dst)` из [price_calculator.py](../src/utils/price_calculator.py);
- **защита от ордеров с абсурдной ценой:** если `sell_price > 1.5 × avg_price` (средневзвешенная цена сделок в регионе назначения за 30 дней, §6.3), используется `avg_price`, округлённая вниз до допустимого тика. Такая цена помечается `*` в таблице (`price_capped`). Без этой проверки одиночный ордер «на дурака» (например, патроны за 189 800 000 ISK) давал прибыль в десятки миллиардов. Порог задаёт константа `MAX_PRICE_OVER_AVERAGE`.

Товар пропускается, если:
- в назначении нет sell-ордеров (нет ориентира цены; см. §10);
- за 30 дней в регионе назначения не было сделок;
- `best_bid_dst × (1 − tax) ≥ net_sell_price` (§6.2): мгновенная продажа даёт не меньше, это сделка режима Instant.

### 6.2. Чанки

Asks источника берутся по возрастанию цены. Для каждого ask-уровня:

```
net_sell_price = sell_price × (1 − tax_rate − broker_fee_rate − relists × relist_rate)
unit_profit    = net_sell_price − ask_price
```

Чанки добавляются, пока `unit_profit > 0`. Формат чанка такой же, как в Instant (`qty, buy_price, sell_price, net_sell_price, unit_profit`), поэтому `apply_limits` и `build_cargo_plan` используются без переписывания.

Минимальная комиссия 100 ISK на ордер не учитывается в чанках, но вычитается из итоговой прибыли строки.

### 6.3. Ограничение спросом

```
demand_qty = floor(daily_volume × market_share × max_days)
```

- `daily_volume`: средний объём сделок в регионе назначения за **календарный** день за последние 30 дней (сумма объёмов / число загруженных дней; дни без сделок считаются нулём, поэтому редко продаваемые товары не завышаются).
- **Источник истории — EVE Ref** (`https://data.everef.net/market-history/{year}/market-history-{date}.csv.bz2`): один файл в день на все регионы и товары, ~600 КБ. Модуль [market_history_handler.py](../src/handlers/market_history_handler.py) докачивает недостающие дни для регионов выбранных хабов в таблицу `market_history_daily` (учёт загруженных дней — `market_history_loaded`) и удаляет дни старше окна.
- Изначально планировалось брать историю из ESI `/markets/{region_id}/history/` через `get_daily_history` (этап 4 её вынес). На реальных данных Jita → Amarr после отсева оставалось ~6300 товаров, а ESI отдаёт один товар за запрос при лимите ~300 запросов в минуту: первый поиск занял бы 20+ минут. С EVE Ref первый поиск с загрузкой 30 дней занимает ~35 с.
- Если сделок за 30 дней не было, товар пропускается.

`apply_limits` и `build_cargo_plan` получают необязательный лимит количества на товар (`max_qty`). При его срабатывании `limited_by = "demand"` (новая константа `LIMIT_DEMAND`). Режим Instant передаёт `None`, его поведение не меняется.

### 6.4. Фильтры и итоги

- Фильтры Min profit и Min margin применяются как в Instant, после вычета всех комиссий.
- `days_to_sell = qty / (daily_volume × market_share)`.
- План загрузки строится тем же жадным алгоритмом по `density`, с учётом `max_qty` на товар.

## 7. Маршрут и ISK/час (оба режима)

- Прыжки между системами хабов: `build_jump_graph()` и `dijkstra_shortest_path()` из [courier_path_handler.py](../src/handlers/courier_path_handler.py).
- `Safest`: из графа исключаются системы с `solar_systems.security < 0.45` (в игре они отображаются как 0.4 и ниже). `Shortest`: весь граф.
- Проверено на текущих данных: Jita → Amarr 45 прыжков по хайсеку и 11 по кратчайшему (через лоусек); Jita → Dodixie 15 и 12; Jita → Rens 25 и 15; Jita → Hek 19 и 9.
- Граф строится один раз за поиск, а расстояния кэшируются по паре систем и режиму маршрута на время жизни экрана.
- `trip_hours = (jumps × time_per_jump_sec / 3600) + overhead_min / 60`
- `isk_per_hour = plan_profit / trip_hours`
- Round trip: `(profit_AB + profit_BA) / (2 × trip_hours)`.
- Если маршрута нет (например, Safest невозможен), показывается `No route` и ISK/h не считается.

## 8. Контрольные примеры (для тестов)

### 8.1. Комиссии

| Входные данные | Ожидаемо |
|---|---|
| BR 5, faction 2.00, corp 3.00 | broker fee 1.38% |
| BR 4, faction −1.00, corp 0 | broker fee 1.83% |
| BR 5, faction 10, corp 10 | broker fee 1.00% |
| Accounting 5 | sales tax 3.375% |
| Broker fee 2%, ABR 4 | relist_rate 0.0052 (0.52% от стоимости ордера за одну перестановку) |

### 8.2. Сделка

Broker fee 2%, sales tax 4%, Expected relists 0. Asks в источнике: 100 шт. по 1 000, 50 шт. по 1 050. Лучший sell в назначении 1 300, значит `sell_price = 1 299`.

- `net_sell_price = 1 299 × 0.94 = 1 221.06`
- Чанк 1: 100 шт. × 221.06 = 22 106
- Чанк 2: 50 шт. × 171.06 = 8 553
- Без ограничений: Qty 150, Investment 152 500, Profit 30 659, Limited by `market`.

С `daily_volume = 20`, Market share 25%, Max days 7: `demand_qty = 35`, Qty 35, Profit 7 737.10, Days to sell 7.0, Limited by `demand`.

С Expected relists 2 и ABR 4: `net_sell_price = 1 299 × (1 − 0.04 − 0.02 − 2 × 0.0052) = 1 207.5504`.

### 8.3. ISK/час

45 прыжков, 60 с на прыжок, 10 мин накладных: `trip_hours = 0.75 + 0.1667 = 0.9167`. При прибыли плана 100 000 000 ISK/h ≈ 109 090 909.

## 9. Файлы

| Файл | Изменение |
|---|---|
| `settings.py.example` | Scope `esi-characters.read_standings.v1`, `esi-skills.read_skills.v1` |
| `src/auth/esi_api.py` | `get_character_standings`, `get_character_skills`, `get_corporation` |
| `src/database/models.py` | Таблицы `character_standings`, `character_skills`, `npc_corporations` и функции чтения/записи |
| `src/handlers/fees.py` | Новый: чистые функции `broker_fee_percent`, `sales_tax_percent`, `relist_rate`, расчёт комиссии для хаба по сохранённым данным |
| `src/ui/character_screen.py` | Кнопка Sync Standings & Skills и таблица Broker Fee по хабам |
| `src/handlers/trade_opportunities_handler.py` | Вынести `get_daily_history` из `find_opportunities` |
| `src/handlers/hub_hauling_handler.py` | `max_qty` и `LIMIT_DEMAND` в `apply_limits` / `build_cargo_plan`; маршрут и ISK/h для плана |
| `src/handlers/hub_trading_handler.py` | Новый: `find_hub_trading_deals` (§6) |
| `src/handlers/market_history_handler.py` | Новый: загрузка истории рынка из EVE Ref и статистика спроса (§6.3) |
| `src/handlers/standings_handler.py` | Новый: Sync Standings & Skills, загрузка NPC-корпораций и фракций из Fuzzwork (§4.4) |
| `src/handlers/wallet_handler.py` | Обновление токена вынесено в `ensure_valid_access_token` и используется также при Sync |
| `src/handlers/import_static_data.py` | Импорт пропускает новые колонки CSV Fuzzwork (§3.4) |
| `src/ui/hub_hauling_screen.py` | Mode, показ и скрытие полей, колонки Trading, маршрут и ISK/h на Cargo plan |
| `tests/test_fees.py`, `tests/test_hub_trading.py` | Тесты по §8 |
| `README.md` | Обновить строку Hub Hauling |

## 10. Вне рамок первой версии

- Товары, которых в назначении нет на продаже (цена по истории).
- Покупка через свои buy-ордера в источнике (broker fee источника, время на набор).
- Рынки player-структур и их собственные комиссии.
- Учёт глубины стакана sell-ордеров в назначении (ниже какой цены уйдёт рынок, когда партия выставлена).
- Отдельные standings разных персонажей одновременно: используется текущий персонаж.

## 11. Критерии приёмки

1. Этап 0 выполнен, §3.4 заполнен, расчётный Broker Fee для Jita и Amarr совпадает с игровым.
2. На экране переключается Mode, нерелевантные поля и колонки скрываются, режим сохраняется между запусками.
3. Режим Instant даёт те же результаты, что до доработки (существующие тесты проходят).
4. В режиме Trading цена продажи на тик ниже лучшего sell в назначении, комиссии считаются по §4, количество не превышает `demand_qty`.
5. Примеры §8 воспроизводятся unit-тестами.
6. На Cargo plan в обоих режимах показаны прыжки, время рейса, ISK/h по направлениям и для рейса туда-обратно; режим маршрута меняет число прыжков.
7. Если scope не выдан, пользователь видит понятное сообщение, а режим Trading работает на ручных значениях.

## 12. Этапы реализации

Агент отмечает этап `[x]`, когда тот полностью готов и проверен.

- [ ] 0. Проверка API на реальном персонаже: scope, standings, навыки, фракции корпораций, сверка Broker Fee с игрой; заполнить §3.4 (§3) — API проверен, Jita сверена; ждёт сверки Amarr в игре (§3.4)
- [x] 1. Чистые функции комиссий `fees.py` и тесты §8.1 (§4)
- [x] 2. ESI-методы и таблицы standings, навыков, NPC-корпораций (§4.4)
- [x] 3. Кнопка Sync Standings & Skills и таблица Broker Fee на EVE Online Account (§4.4)
- [x] 4. Вынести `get_daily_history` из `find_opportunities` без изменения поведения Trade Opportunities (§6.3)
- [x] 5. `max_qty` / `LIMIT_DEMAND` в `apply_limits` и `build_cargo_plan`; существующие тесты проходят (§6.3)
- [x] 6. `find_hub_trading_deals` и тесты §8.2 (§6)
- [x] 7. Маршрут, время рейса и ISK/h, тесты §8.3 (§7)
- [x] 8. Экран: Mode, показ и скрытие полей, сохранение режима и новых параметров (§2, §5.1)
- [x] 9. Экран: колонки Deals для Trading, строка Broker Fee под хабами (§5.2, §4.4)
- [x] 10. Экран: маршрут, ISK/h и Sell-through на Cargo plan в обоих режимах (§5.3)
- [x] 11. README
- [ ] 12. Ручная проверка по критериям приёмки §11

## 13. Доработки после первой проверки (2026-11-04)

1. **Минимальные вложения на позицию** (оба режима, поле `Min investment per item, ISK`, по умолчанию 1 000 000). Строка Deals отсеивается, если после всех ограничений вложения меньше минимума. В плане загрузки позиция, которая по итогу заполнения получила меньше минимума (не хватило трюма, денег, спроса или предложения), удаляется, а освободившиеся трюм и ISK перераспределяются: план пересобирается без таких позиций, пока они не кончатся (`build_cargo_plan(min_investment=...)`).
2. **Лимит позиций в плане** (оба режима, поле `Max items in cargo plan`, по умолчанию 50, пусто = без лимита). Новая позиция не добавляется в план, когда лимит достигнут (`build_cargo_plan(max_items=...)`).
3. **Конкуренция и спрос** (Trading):
   - Разбор Large Projectile Metastasis Adjuster II: в Domain он продаётся по ~90–130 млн (около 3 шт./день, данные EVE Ref и ESI совпадают); 29 млн — это история The Forge. Сделка выглядела выгодной из-за разницы цен между регионами, но в Amarr 15 sell-ордеров, а цена за 2 недели упала со 148 до 98 млн.
   - **Справедливая доля рынка:** `share = min(Market share, 100 / (competitors + 1))`. Спрос, срок продажи и количество считаются от неё. В Deals добавлена колонка `Share %`.
   - **Фильтр `Max competitors`** (по умолчанию 10, пусто = без лимита): товары с большим числом конкурентов в назначении пропускаются.
   - **Исправлен подсчёт конкурентов:** ордера, обновлённые за 2 дня до момента загрузки ордеров (`fetched_at`), а не до текущего момента. Раньше при данных двухдневной давности почти все конкуренты «пропадали». Логика та же, что в Accounting Tool (`count_competitors`), но по станции хаба, а не по региону.
4. **Таблица Deals компактнее:** короткие заголовки с подсказками, шрифт 11, `column_spacing=12`, имя товара обрезается до 200 px с подсказкой, 20 строк на страницу.

- [x] 13.1. Min investment per item в Deals и плане, тест на перераспределение
- [x] 13.2. Max items in cargo plan, тест
- [x] 13.3. Справедливая доля рынка, Max competitors, подсчёт конкурентов от времени снимка ордеров
- [x] 13.4. Компактная таблица Deals, 20 строк на страницу
5. **Фильтр `Max margin, %`** (оба режима, по умолчанию 100, пусто = без лимита). Строка Deals отсеивается, если её маржа (та же, что в колонке Margin) выше порога: очень высокая маржа обычно означает тонкий рынок или раздутые цены в назначении. На Jita → Amarr без фильтра план набирал 50 позиций с маржой до 963% и тратил 176 млн из 2 млрд бюджета; при 100% он тратит 585 млн, при 50% — 1.26 млрд.

- [x] 13.5. Фильтр Max margin в обоих режимах
- [ ] 13.6. Ручная проверка в приложении
