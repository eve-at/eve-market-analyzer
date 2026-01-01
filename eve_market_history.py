import flet as ft
import requests
import csv
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class MarketLogHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы для логов маркета"""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.pattern = re.compile(r'^(.+)-(.+)-\d{4}\.\d{2}\.\d{2} \d{6}\.txt$')
    
    def on_created(self, event):
        """Обработка создания нового файла"""
        if event.is_directory:
            return
        
        filename = Path(event.src_path).name
        match = self.pattern.match(filename)
        
        if match:
            region_name = match.group(1)
            item_name = match.group(2)
            print(f"Обнаружен новый лог маркета: {region_name} - {item_name}")
            self.callback(region_name, item_name)


class SuggestionItem:
    """Класс для элемента подсказки с собственным обработчиком"""
    def __init__(self, name, item_id, callback):
        self.name = name
        self.item_id = item_id
        self.callback = callback
    
    def on_click(self, e):
        """Обработчик клика"""
        self.callback(self.name, self.item_id)
    
    def build(self):
        """Создание UI элемента"""
        btn = ft.Button(
            content=ft.Container(
                content=ft.Text(self.name, size=13),
                alignment=ft.Alignment.CENTER_LEFT
            ),
            width=300,
            style=ft.ButtonStyle(
                padding=ft.Padding(10, 10, 10, 10),
                bgcolor=ft.Colors.WHITE,
                side=ft.BorderSide(1, ft.Colors.GREY_300)
            ),
        )
        btn.on_click = self.on_click
        return btn


class AutoCompleteField:
    """Класс для поля с автозаполнением"""
    def __init__(self, label, hint_text, default_value, data_dict, on_select_callback, on_validation_change=None):
        self.label = label
        self.hint_text = hint_text
        self.default_value = default_value
        self.data_dict = data_dict  # {name: id}
        self.on_select_callback = on_select_callback
        self.on_validation_change = on_validation_change
        
        self.selected_id = None
        self.selected_name = None
        self.is_valid = True
        
        # UI элементы
        self.text_field = ft.TextField(
            label=label,
            hint_text=hint_text,
            width=300,
            on_change=self.on_text_change,
            dense=True
        )
        
        self.id_label = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_600,
            visible=False
        )
        
        self.suggestions_column = ft.Column(
            visible=False,
            spacing=2,
        )
        
        # Основной контейнер с полем
        self.field_container = ft.Column([
            self.text_field,
            self.id_label,
        ], spacing=5)
        
        # Контейнер для подсказок с абсолютным позиционированием
        self.suggestions_container = ft.Container(
            content=self.suggestions_column,
            visible=False,
        )
        
        # Используем Column для простого размещения
        self.container = ft.Column([
            self.field_container,
            self.suggestions_container,
        ], spacing=0)
    
    def on_text_change(self, e):
        """Обработка изменения текста"""
        query = self.text_field.value.strip()
        
        # Сбрасываем ошибку при изменении текста
        if self.text_field.border_color == ft.Colors.RED:
            self.text_field.border_color = None
            self.text_field.error_text = None
            try:
                if self.text_field.page:
                    self.text_field.update()
            except:
                pass
        
        if len(query) < 3:
            self.suggestions_column.visible = False
            self.suggestions_container.visible = False
            self.suggestions_column.controls.clear()
            self.id_label.visible = False
            try:
                if self.text_field.page:
                    self.suggestions_container.update()
                    self.id_label.update()
            except:
                pass
            return
        
        # Поиск совпадений
        matches = self.search_matches(query)
        
        if matches:
            self.show_suggestions(matches[:5])  # Максимум 5 вариантов
        else:
            self.suggestions_column.visible = False
            self.suggestions_container.visible = False
            self.suggestions_column.controls.clear()
            try:
                if self.suggestions_container.page:
                    self.suggestions_container.update()
            except:
                pass
    
    def search_matches(self, query):
        """Поиск совпадений в данных"""
        query_lower = query.lower()
        matches = []
        
        for name, item_id in self.data_dict.items():
            if query_lower in name.lower():
                matches.append((name, item_id))
        
        # Сортировка: сначала те, что начинаются с запроса
        matches.sort(key=lambda x: (not x[0].lower().startswith(query_lower), x[0]))
        
        return matches
    
    def show_suggestions(self, matches):
        """Отображение списка подсказок"""
        self.suggestions_column.controls.clear()
        
        for name, item_id in matches:
            suggestion_item = SuggestionItem(name, item_id, self.select_suggestion)
            self.suggestions_column.controls.append(suggestion_item.build())
        
        self.suggestions_column.visible = True
        self.suggestions_container.visible = True
        try:
            if self.suggestions_container.page:
                self.suggestions_container.update()
        except:
            pass
    
    def select_suggestion(self, name, item_id):
        """Выбор варианта из списка"""
        self.text_field.value = name
        self.selected_name = name
        self.selected_id = item_id
        self.is_valid = True
        
        # Сбрасываем ошибки
        self.text_field.border_color = None
        self.text_field.error_text = None
        
        # Скрыть подсказки
        self.suggestions_column.visible = False
        self.suggestions_container.visible = False
        self.suggestions_column.controls.clear()
        
        # Показать ID
        self.id_label.value = f"ID: {item_id}"
        self.id_label.color = ft.Colors.GREY_600
        self.id_label.visible = True
        
        # Обновить UI только если элементы уже на странице
        try:
            if self.text_field.page:
                self.text_field.update()
                self.suggestions_container.update()
                self.id_label.update()
                
                # Уведомляем о изменении валидности
                if self.on_validation_change:
                    self.on_validation_change(True)
        except:
            pass
        
        # Вызвать callback
        if self.on_select_callback:
            self.on_select_callback(name, item_id)
    
    def get_selected_id(self):
        """Получить выбранный ID"""
        return self.selected_id
    
    def get_value(self):
        """Получить текущее значение поля"""
        return self.text_field.value


class EVEMarketApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "EVE Online - Market History"
        self.page.window_width = 1100
        self.page.window_height = 700
        
        # Загрузка статических данных
        self.regions_data = {}  # {name: id}
        self.items_data = {}    # {name: id}
        self.load_static_data()
        
        # UI элементы
        self.status_text = ft.Text("Введите название региона и предмета", size=14)
        self.data_table = None
        self.data_container = ft.Column(expand=True)
        
        # Кнопка Get
        self.get_button = ft.Button(
            "Get",
            icon=ft.Icons.DOWNLOAD,
            on_click=self.load_market_data,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE_700
            )
        )
        
        # Поля с автозаполнением
        self.region_field = AutoCompleteField(
            label="Region",
            hint_text="The Forge",
            default_value="The Forge",
            data_dict=self.regions_data,
            on_select_callback=self.on_region_selected,
            on_validation_change=self.on_field_validation_change
        )
        
        self.item_field = AutoCompleteField(
            label="Item Type",
            hint_text="Retriever",
            default_value="Retriever",
            data_dict=self.items_data,
            on_select_callback=self.on_item_selected,
            on_validation_change=self.on_field_validation_change
        )
        
        self.setup_ui()
        
        # Устанавливаем значения по умолчанию после добавления UI на страницу
        self.set_default_values()
        
        # Мониторинг директории с логами маркета
        self.is_processing = False  # Флаг обработки запроса
        self.observer = None
        self.marketlogs_dir = Path.home() / "Documents" / "EVE" / "logs" / "Marketlogs"
        self.start_file_monitoring()
    
    def load_static_data(self):
        """Загрузка статических данных из CSV файлов"""
        # Определяем путь к папке data
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        
        # Загрузка регионов
        regions_file = os.path.join(data_dir, 'mapRegions.csv')
        try:
            with open(regions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    region_id = row.get('regionID', '')
                    region_name = row.get('regionName', '')
                    if region_id and region_name:
                        self.regions_data[region_name] = region_id
            print(f"Загружено регионов: {len(self.regions_data)}")
        except Exception as e:
            print(f"Ошибка загрузки регионов: {e}")
        
        # Загрузка типов предметов (только опубликованные)
        items_file = os.path.join(data_dir, 'invTypes.csv')
        try:
            with open(items_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    type_id = row.get('typeID', '')
                    type_name = row.get('typeName', '')
                    published = row.get('published', '0')
                    
                    # Загружаем только опубликованные предметы
                    if type_id and type_name and published == '1':
                        self.items_data[type_name] = type_id
            print(f"Загружено предметов: {len(self.items_data)}")
        except Exception as e:
            print(f"Ошибка загрузки предметов: {e}")
    
    def set_default_values(self):
        """Установка значений по умолчанию"""
        # The Forge
        if "The Forge" in self.regions_data:
            self.region_field.select_suggestion("The Forge", self.regions_data["The Forge"])
        
        # Retriever
        if "Retriever" in self.items_data:
            self.item_field.select_suggestion("Retriever", self.items_data["Retriever"])
    
    def on_region_selected(self, name, region_id):
        """Callback при выборе региона"""
        print(f"Выбран регион: {name} (ID: {region_id})")
    
    def on_item_selected(self, name, item_id):
        """Callback при выборе предмета"""
        print(f"Выбран предмет: {name} (ID: {item_id})")
    
    def on_field_validation_change(self, is_valid):
        """Callback при изменении валидности полей"""
        # Проверяем валидность обоих полей
        both_valid = self.region_field.is_valid and self.item_field.is_valid
        self.get_button.disabled = not both_valid
        
        try:
            if self.get_button.page:
                self.get_button.update()
        except:
            pass
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        # Заголовок
        title = ft.Text(
            "EVE Online Market History",
            size=24,
            weight=ft.FontWeight.BOLD
        )
        
        # Информация
        info_text = ft.Text(
            "Начните вводить название (минимум 3 символа) для поиска",
            size=12,
            color=ft.Colors.GREY_700
        )
        
        # Поля ввода в ряд
        input_row = ft.Row([
            self.region_field.container,
            self.item_field.container
        ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START)
        
        # Компоновка
        self.page.add(
            ft.Container(
                content=ft.Column([
                    title,
                    info_text,
                    input_row,
                    ft.Row([self.get_button], alignment=ft.MainAxisAlignment.START),
                    self.status_text,
                    ft.Divider(),
                    self.data_container
                ], spacing=10),
                padding=20
            )
        )
    
    def load_market_data(self, e):
        """Загрузка данных из API"""
        # Устанавливаем флаг обработки
        self.is_processing = True
        
        # Получаем выбранные ID
        region_id = self.region_field.get_selected_id()
        type_id = self.item_field.get_selected_id()
        
        if not region_id or not type_id:
            self.status_text.value = "Ошибка: выберите регион и предмет из списка"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            self.is_processing = False  # Снимаем флаг
            return
        
        self.status_text.value = "Загрузка данных..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()
        
        try:
            # Запрос к API
            url = f"https://esi.evetech.net/latest/markets/{region_id}/history/"
            params = {
                "type_id": type_id,
                "datasource": "tranquility"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                self.status_text.value = "Данные не найдены"
                self.status_text.color = ft.Colors.ORANGE
                self.page.update()
                self.is_processing = False  # Снимаем флаг
                return
            
            # Сортировка по убыванию даты
            data_sorted = sorted(data, key=lambda x: x['date'], reverse=True)
            
            self.display_data(data_sorted)
            self.status_text.value = f"Загружено записей: {len(data_sorted)}"
            self.status_text.color = ft.Colors.GREEN
            
        except requests.exceptions.RequestException as ex:
            self.status_text.value = f"Ошибка загрузки: {str(ex)}"
            self.status_text.color = ft.Colors.RED
        except Exception as ex:
            self.status_text.value = f"Ошибка: {str(ex)}"
            self.status_text.color = ft.Colors.RED
        finally:
            # Снимаем флаг обработки в любом случае
            self.is_processing = False
        
        self.page.update()
    
    def display_data(self, data):
        """Отображение данных в таблице"""
        # Создание таблицы
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Orders", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Quantity", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Low", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("High", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Avg", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            border=ft.Border.all(1, ft.Colors.GREY_400),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
            horizontal_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
            heading_row_color=ft.Colors.GREY_200,
            heading_row_height=50,
            data_row_max_height=45,
        )
        
        # Заполнение данными
        for item in data:
            date_str = item.get('date', 'N/A')
            order_count = str(item.get('order_count', 0))
            volume = f"{item.get('volume', 0):,}"
            lowest = f"{item.get('lowest', 0):,.2f} ISK"
            highest = f"{item.get('highest', 0):,.2f} ISK"
            average = f"{item.get('average', 0):,.2f} ISK"
            
            self.data_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(date_str)),
                        ft.DataCell(ft.Text(order_count)),
                        ft.DataCell(ft.Text(volume)),
                        ft.DataCell(ft.Text(lowest)),
                        ft.DataCell(ft.Text(highest)),
                        ft.DataCell(ft.Text(average)),
                    ]
                )
            )
        
        # Обновление контейнера с данными
        self.data_container.controls.clear()
        # Оборачиваем таблицу в контейнер с прокруткой
        scrollable_table = ft.Container(
            content=ft.Column([self.data_table], scroll=ft.ScrollMode.AUTO),
            height=500,  # Фиксированная высота для включения прокрутки
        )
        self.data_container.controls.append(scrollable_table)
        self.page.update()
    
    def start_file_monitoring(self):
        """Запуск мониторинга директории с логами маркета"""
        if not self.marketlogs_dir.exists():
            print(f"Директория {self.marketlogs_dir} не существует. Мониторинг не запущен.")
            return
        
        event_handler = MarketLogHandler(self.on_market_log_created)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.marketlogs_dir), recursive=False)
        self.observer.start()
        print(f"Запущен мониторинг директории: {self.marketlogs_dir}")
    
    def stop_file_monitoring(self):
        """Остановка мониторинга"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("Мониторинг остановлен")
    
    def on_market_log_created(self, region_name, item_name):
        """Callback при создании нового лога маркета"""
        if self.is_processing:
            print(f"Обработка уже выполняется, пропускаем: {region_name} - {item_name}")
            return
        
        print(f"Обработка нового лога: {region_name} - {item_name}")
        
        # Устанавливаем значения в поля через UI поток
        async def update_fields():
            # Проверяем что регион и предмет существуют в данных
            if region_name in self.regions_data and item_name in self.items_data:
                region_id = self.regions_data[region_name]
                item_id = self.items_data[item_name]
                
                # Устанавливаем значения
                self.region_field.select_suggestion(region_name, region_id)
                self.item_field.select_suggestion(item_name, item_id)
                
                # Запускаем загрузку данных
                self.load_market_data(None)
            else:
                print(f"Регион или предмет не найдены в базе данных: {region_name}, {item_name}")
        
        # Выполняем обновление в UI потоке
        self.page.run_task(update_fields)


def main(page: ft.Page):
    EVEMarketApp(page)


if __name__ == "__main__":
    ft.run(main)