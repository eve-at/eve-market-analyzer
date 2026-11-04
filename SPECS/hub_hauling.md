# ТЗ: раздел «Hub Hauling» — перевозка товаров между торговыми хабами

## 1. Цель

Найти товары, которые можно **мгновенно купить** в одном торговом хабе (выкупив чужие sell-ордера), перевезти на корабле в другой хаб и **мгновенно продать** там (в чужие buy-ордера) с прибылью.

Количество считается с учётом:
- реального объёма в стакане с каждой стороны (не покупать больше, чем можно сразу продать с прибылью);
- грузоподъёмности корабля;
- бюджета и допустимой стоимости груза на борту (риск);
- налогов персонажа.

Результат: таблица выгодных товаров по обоим направлениям и автоматически собранный план загрузки трюма на каждое направление.

## 2. Точка входа

- На главной странице ([src/ui/main_menu.py](../src/ui/main_menu.py)) появляется седьмая карточка:
  - title: `Hub Hauling`
  - icon: `ft.Icons.LOCAL_SHIPPING`
  - description: `Buy in one hub, haul and sell instantly in another`
  - key: `hub_hauling`
- Раскладка карточек: третья строка по центру с одной карточкой (стиль и размеры как у остальных).
- В [main.py](../main.py): ветка `elif menu_key == "hub_hauling"` в `on_menu_select` и метод `show_hub_hauling()` по образцу `show_trade_opportunities()` (AppBar с кнопкой Back, `_connect_sync_to_appbar()`).

## 3. Торговые хабы

Источник: https://wiki.eveuniversity.org/Trade_hubs

| Хаб | Станция | Регион |
|---|---|---|
| Jita | Jita IV - Moon 4 - Caldari Navy Assembly Plant | The Forge |
| Amarr | Amarr VIII (Oris) - Emperor Family Academy | Domain |
| Dodixie | Dodixie IX - Moon 20 - Federation Navy Assembly Plant | Sinq Laison |
| Rens | Rens VI - Moon 8 - Brutor Tribe Treasury | Heimatar |
| Hek | Hek VIII - Moon 12 - Boundless Creation Factory | Metropolis |
| Oursulaert | Oursulaert III - Federation Navy Testing Facilities | Essence |
| Tash-Murkon Prime | Tash-Murkon Prime II - Moon 1 - Kaalakiota Corporation Factory | Tash-Murkon |
| Agil | Agil VI - Moon 2 - CONCORD Logistic Support | Khanid |

- Список хранится константой `TRADE_HUBS` (имя хаба + `stationID`) в новом хендлере.
- `solarSystemID`, `regionID`, `corporationID` и текущее название станции при открытии экрана берутся из таблицы `stations` по `stationID`. Изначально поиск шёл по точному `stationName`, но в статике 2026 года CCP переименовал станции («Jita IV - Moon 4» → «Jita 4 - Moon 4»), и находился только Amarr; ID при переименованиях не меняются. Если станция не найдена (статика не загружена), хаб показывается неактивным с подсказкой «Update Static Data».
- Player-структуры (Perimeter: Tranquility Trading Tower и др.) **не входят в первую версию**: их рынки требуют авторизованного эндпоинта `/markets/structures/{id}/`.

## 4. Интерфейс экрана

Новый файл `src/ui/hub_hauling_screen.py`, класс `HubHaulingScreen(page, on_back_callback)`. Стиль, размеры полей, лог прогресса, пагинация и сортировка таблицы как в [trade_opportunities_screen.py](../src/ui/trade_opportunities_screen.py).

### 4.1. Панель параметров

| Поле | Тип | По умолчанию | Примечание |
|---|---|---|---|
| Hub A | Dropdown (хабы из §3) | Jita | |
| Hub B | Dropdown | Amarr | Нельзя выбрать тот же хаб, что в A |
| ⇄ | IconButton | — | Меняет A и B местами |
| Cargo capacity, m³ | TextField, число > 0 | 60 000 | Обязательное |
| Budget, ISK | TextField | пусто | Пусто = без ограничения |
| Max cargo value, ISK | TextField | пусто | Лимит риска: суммарная стоимость закупки на борту. Пусто = без ограничения |
| Min profit per item, ISK | TextField | 1 000 000 | Порог для строки таблицы |
| Min margin, % | TextField | 5 | Profit / Investment × 100 |
| Market groups | Чекбоксы топ-групп | ничего не выбрано = все | Как на Trade Opportunities (`load_top_market_groups()`) |

- Все значения сохраняются через `save_setting()` (ключи `hub_hauling_*`) и восстанавливаются при следующем открытии.
- Под панелью строка с налогом: `Sales tax: 7.50% (from EVE Online Account)`. Если персонаж не залогинен, показывается значение по умолчанию 7.50% и предупреждение.

### 4.2. Статус данных и кнопки

- Для каждого из двух выбранных хабов показывается строка статуса: регион, количество ордеров в `orders_{region_id}`, возраст данных по `fetched_at` (например, `The Forge: 412 380 orders, updated 12 min ago`). Если данным больше 30 минут, возраст подсвечивается оранжевым, если таблицы нет, красным.
- Кнопка **Update Orders** обновляет регионы обоих выбранных хабов через существующий `update_orders(region_id, callback)` из [trade_opportunities_handler.py](../src/handlers/trade_opportunities_handler.py). Если оба хаба в одном регионе, регион обновляется один раз. Работает в фоновом потоке, прогресс пишется в лог, на время работы кнопки неактивны.
- Кнопка **Find Deals** запускает расчёт (§5) в фоновом потоке. Неактивна, пока у одного из регионов нет ордеров.
- Кнопка **Export CSV** выгружает таблицу результатов в `csv_export_path` (как `export_opportunities_to_csv`).

### 4.3. Результаты

Две вкладки (Tabs):

**Вкладка «Deals»**: таблица всех найденных сделок по обоим направлениям, по одной строке на пару (товар, направление).

| Колонка | Описание |
|---|---|
| Direction | `Jita → Amarr` или `Amarr → Jita` |
| Item | typeName |
| Qty | Количество к покупке (с учётом всех ограничений, §5.3) |
| Volume, m³ | Qty × packaged volume |
| Max buy price | Самая дорогая цена sell-ордера, до которой выкупаем в хабе-источнике. Это потолок цены при покупке в игре |
| Avg buy price | Investment / Qty |
| Min sell price | Самая дешёвая цена buy-ордера, в который продаём в хабе-назначении |
| Investment, ISK | Сумма закупки |
| Revenue, ISK | Выручка после sales tax |
| Profit, ISK | Revenue − Investment |
| Margin, % | Profit / Investment × 100 |
| Profit / m³ | Profit / Volume |
| Limited by | Что ограничило Qty: `market`, `cargo`, `budget`, `risk` |

- Сортировка по любой колонке, по умолчанию Profit по убыванию. Пагинация по 50 строк.
- Фильтр-переключатель направления: `All` / `A → B` / `B → A`.
- Клик по строке подсвечивает её, как на Trade Opportunities.

**Вкладка «Cargo plan»**: два блока, `A → B` и `B → A`. В каждом:
- список товаров плана (Item, Qty, Volume, Max buy price, Investment, Profit);
- итог: `Cargo: 58 940 / 60 000 m³ (98%)`, `Investment`, `Profit`, `Margin`;
- кнопка **Copy for Multibuy**: копирует в буфер список в формате EVE Multibuy (`<typeName> <qty>` построчно).

## 5. Алгоритм расчёта

Новый файл `src/handlers/hub_hauling_handler.py`. Основная функция:

```python
find_hub_deals(hub_a, hub_b, cargo_m3, budget, max_cargo_value,
               min_profit, min_margin, market_group_ids, sales_tax_percent,
               callback=None) -> dict  # {"deals": [...], "plans": {"A->B": {...}, "B->A": {...}}}
```

Расчёт выполняется для каждого направления (Source → Destination) отдельно.

### 5.1. Выборка ордеров

- **Asks в источнике**: `orders_{src_region}` с условиями `is_buy_order = 0 AND location_id = src_station_id`, сортировка по `price ASC`.
- **Bids в назначении**: `orders_{dst_region}` с условиями `is_buy_order = 1 AND location_id = dst_station_id`, сортировка по `price DESC`.
  - Buy-ордера других станций с `range`, покрывающим станцию назначения, в первой версии **не учитываются** (упрощение: продаём только в ордера, выставленные на самой станции хаба).
  - Если у buy-ордера `min_volume` > 1, он учитывается только тогда, когда на него приходится не меньше `min_volume` единиц, иначе пропускается.
- Отбираются только `type_id`, которые есть с обеих сторон, и только товары выбранных топ-групп рынка, если они выбраны (тот же JOIN `types` → `market_groups`, что в `find_opportunities`).
- Предварительный отсев в SQL: `MIN(ask_price) < MAX(bid_price) × (1 − tax)`. Дальше обрабатываются только эти кандидаты.

### 5.2. Сопоставление стаканов (сколько можно продать с прибылью)

`tax = sales_tax_percent / 100`. Мгновенная покупка broker fee не платит, мгновенная продажа платит только sales tax.

Для каждого товара два указателя проходят по asks (дешёвые вперёд) и bids (дорогие вперёд):

```
while ask and bid:
    net_bid = bid.price * (1 - tax)
    if net_bid <= ask.price: break
    q = min(ask.remain, bid.remain)
    записать чанк (q, ask.price, net_bid)
    уменьшить остатки, сдвинуть исчерпанный указатель
```

Результат: список чанков с убывающей маржинальной прибылью на единицу. Сумма `q` даёт `Q_market`, максимальное количество, которое можно купить и **сразу же** продать с прибылью. Больше этого не покупаем.

### 5.3. Ограничения для строки таблицы (Deals)

Чанки берутся по порядку, пока не сработает первое ограничение (последний чанк режется частично):

- `Qty × volume ≤ cargo_m3`, ограничение `cargo`;
- `Investment ≤ budget`, ограничение `budget`;
- `Investment ≤ max_cargo_value`, ограничение `risk`;
- чанки закончились, ограничение `market`.

В `Limited by` записывается сработавшее ограничение. После этого строка отсеивается, если `Profit < min_profit` или `Margin < min_margin`, а также если `Qty = 0` (единица товара не помещается в трюм).

### 5.4. План загрузки (Cargo plan)

Задача рюкзака с двумя ресурсами (объём и ISK), решается жадно по чанкам:

1. Собрать чанки всех прошедших фильтр товаров данного направления.
2. `isk_cap = min(budget, max_cargo_value)` (пустые поля считаются бесконечностью).
3. Для чанка: `density = profit_per_unit / max(volume / cargo_m3, ask_price / isk_cap)`. Если `isk_cap` бесконечен, это `profit_per_unit / volume`, то есть Profit/m³.
4. Сортировать чанки по `density` по убыванию и добавлять, пока есть место и деньги. Чанк, который влезает не целиком, режется до целого количества. Внутри товара чанки и так идут по убыванию прибыли, поэтому порядок покупки не нарушается.
5. Количества по одному товару суммируются в одну строку плана, `Max buy price` равен максимальной цене ask среди взятых чанков.

### 5.5. Объём товара

- `types.volume` из Fuzzwork равен **неупакованному** объёму (у кораблей, контейнеров и т.п. он сильно больше упакованного).
- Для кандидатов из §5.1 используется `packaged_volume` из ESI `GET /universe/types/{type_id}/`, кэшируемый в новой таблице:

```sql
CREATE TABLE IF NOT EXISTS type_packaged_volume (
    type_id INTEGER PRIMARY KEY,
    packaged_volume REAL NOT NULL,
    fetched_at TEXT NOT NULL
)
```

- Кэш не протухает (объёмы почти не меняются) и сбрасывается при `Update Static Data`. Если ESI недоступен, используется `types.volume`, а в лог пишется предупреждение.
- Товары с объёмом 0 или NULL пропускаются.

### 5.6. Налоги персонажа

`get_current_character_id()` → `get_character(id)` → `sales_tax`. `broker_fee_buy` и `broker_fee_sell` в этом режиме не используются (обе сделки мгновенные). Это нужно явно отметить в UI подсказкой у строки налога.

## 6. Контрольный пример (для тестов)

Sales tax 7.5%, товар объёмом 10 m³.

- Asks в источнике: 100 шт. по 1 000, 50 шт. по 1 050.
- Bids в назначении: 80 шт. по 1 200, 100 шт. по 1 100.

Сопоставление:
1. 1 000 против 1 200 × 0.925 = 1 110: берём 80 шт., +110/шт., прибыль 8 800.
2. 1 000 (осталось 20) против 1 100 × 0.925 = 1 017.5: берём 20 шт., +17.5/шт., прибыль 350.
3. 1 050 против 1 017.5: невыгодно, стоп.

Ожидаемый результат без ограничений: Qty 100, Investment 100 000, Revenue 109 150, Profit 9 150, Max buy price 1 000, Min sell price 1 100, Limited by `market`. Оставшиеся 50 шт. по 1 050 **не покупаются**.

С трюмом 500 m³: Qty 50, Investment 50 000, Profit 5 500, Limited by `cargo`.

С бюджетом 30 000: Qty 30, Profit 3 300, Limited by `budget`.

## 7. Файлы

| Файл | Изменение |
|---|---|
| `src/handlers/hub_hauling_handler.py` | Новый: `TRADE_HUBS`, резолв станций, `find_hub_deals`, сопоставление стаканов, план, packaged volume, экспорт CSV |
| `src/ui/hub_hauling_screen.py` | Новый: экран §4 |
| `src/ui/__init__.py` | Экспорт `HubHaulingScreen` |
| `src/ui/main_menu.py` | Седьмая карточка |
| `main.py` | Роутинг и `show_hub_hauling()` |
| `src/handlers/import_static_data.py` | Очистка `type_packaged_volume` при обновлении статики |
| `README.md` | Строка в Features |

Логику сопоставления (§5.2–5.4) вынести в чистые функции без БД, чтобы их можно было покрыть тестами на примере §6.

## 8. Нефункциональные требования

- Загрузка ордеров и расчёт выполняются в фоновом потоке, UI не блокируется, обновление UI идёт через тот же механизм, что на Trade Opportunities.
- Расчёт по уже загруженным ордерам Jita ↔ Amarr должен занимать не больше нескольких секунд, не считая первичной подгрузки packaged volume. Индексы на `orders_{region}` (`location_id`, `type_id`, `is_buy_order`) создаются при необходимости через `CREATE INDEX IF NOT EXISTS`.
- Ошибки сети и БД пишутся в лог экрана, приложение не падает.

## 9. Критерии приёмки

1. На главной странице есть карточка «Hub Hauling», она открывает экран, Back возвращает в меню.
2. По умолчанию выбраны Jita и Amarr. ⇄ меняет хабы местами, выбрать один хаб дважды нельзя.
3. Update Orders обновляет нужные регионы, статус показывает количество ордеров и возраст данных.
4. Find Deals показывает сделки по обоим направлениям, каждая строка соответствует §5.2–5.3. Ни одна строка не предполагает покупку больше, чем можно сразу продать с прибылью.
5. Для каждого направления план не превышает трюм, бюджет и лимит риска.
6. Пример §6 воспроизводится точно (unit-тест).
7. Учитывается sales tax текущего персонажа, при его изменении на странице EVE Online Account результат пересчёта меняется.
8. Copy for Multibuy вставляется в окно Multibuy игры без правок.
9. Параметры формы сохраняются между запусками.

## 10. Вне рамок первой версии

- Рынки player-структур (Perimeter и др.).
- Buy-ордера с `range`, выставленные на других станциях региона.
- Отложенная продажа через собственные sell-ордера и закупка через собственные buy-ордера.
- Расчёт маршрута, количества прыжков и времени в пути (можно взять из `courier_path_handler.build_jump_graph`).
- Учёт объёмов исторических продаж (`history_{region}`).

## 11. Этапы реализации

Агент отмечает этап `[x]`, когда тот полностью готов и проверен.

- [x] 1. Хендлер: константа `TRADE_HUBS` и резолв `stationID` / `solarSystemID` / `regionID` из таблицы `stations` (§3)
- [x] 2. Чистые функции сопоставления стаканов, ограничений строки и плана загрузки (§5.2–5.4)
- [x] 3. Unit-тесты на контрольный пример §6 (без ограничений, с трюмом 500 m³, с бюджетом 30 000)
- [x] 4. Таблица `type_packaged_volume`, загрузка из ESI с fallback на `types.volume`, очистка при Update Static Data (§5.5)
- [x] 5. `find_hub_deals`: SQL-выборка кандидатов, фильтр по группам рынка, индексы, sales tax персонажа (§5.1, §5.6)
- [x] 6. Экспорт результатов в CSV
- [x] 7. Карточка на главной странице и роутинг в `main.py` (§2)
- [x] 8. Экран: панель параметров, ⇄, сохранение и восстановление настроек (§4.1)
- [x] 9. Экран: статус данных по хабам, Update Orders, Find Deals в фоновом потоке, лог (§4.2)
- [x] 10. Вкладка Deals: таблица, сортировка, пагинация, фильтр направления, подсветка строк (§4.3)
- [x] 11. Вкладка Cargo plan: итоги по обоим направлениям и Copy for Multibuy (§4.3)
- [x] 12. README: строка в Features
- [x] 13. Ручная проверка по критериям приёмки §9
