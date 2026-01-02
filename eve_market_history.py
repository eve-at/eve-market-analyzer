import flet as ft
import requests
import mysql.connector
from mysql.connector import Error
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from settings import DB_CONFIG, MARKETLOGS_DIR


class MarketLogHandler(FileSystemEventHandler):
    """File system event handler for market logs"""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.pattern = re.compile(r'^(.+)-(.+)-\d{4}\.\d{2}\.\d{2} \d{6}\.txt$')
    
    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return
        
        filename = Path(event.src_path).name
        match = self.pattern.match(filename)
        
        if match:
            region_name = match.group(1)
            item_name = match.group(2)
            print(f"New market log detected: {region_name} - {item_name}")
            self.callback(region_name, item_name)


class SuggestionItem:
    """Class for suggestion item with its own handler"""
    def __init__(self, name, item_id, callback):
        self.name = name
        self.item_id = item_id
        self.callback = callback
    
    def on_click(self, e):
        """Click handler"""
        self.callback(self.name, self.item_id)
    
    def build(self):
        """Create UI element"""
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
    """Field with autocomplete functionality"""
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
        
        # UI elements
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
        
        # Main container with field
        self.field_container = ft.Column([
            self.text_field,
            self.id_label,
        ], spacing=5)
        
        # Container for suggestions with absolute positioning
        self.suggestions_container = ft.Container(
            content=self.suggestions_column,
            visible=False,
        )
        
        # Use Column for simple layout
        self.container = ft.Column([
            self.field_container,
            self.suggestions_container,
        ], spacing=0)
    
    def on_text_change(self, e):
        """Handle text change"""
        query = self.text_field.value.strip()
        
        # Reset error on text change
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
        
        # Search for matches
        matches = self.search_matches(query)
        
        if matches:
            self.show_suggestions(matches[:5])  # Maximum 5 options
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
        """Search for matches in data"""
        query_lower = query.lower()
        matches = []
        
        for name, item_id in self.data_dict.items():
            if query_lower in name.lower():
                matches.append((name, item_id))
        
        # Sort: first those that start with query
        matches.sort(key=lambda x: (not x[0].lower().startswith(query_lower), x[0]))
        
        return matches
    
    def show_suggestions(self, matches):
        """Display list of suggestions"""
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
        """Select option from list"""
        self.text_field.value = name
        self.selected_name = name
        self.selected_id = item_id
        self.is_valid = True
        
        # Reset errors
        self.text_field.border_color = None
        self.text_field.error_text = None
        
        # Hide suggestions
        self.suggestions_column.visible = False
        self.suggestions_container.visible = False
        self.suggestions_column.controls.clear()
        
        # Show ID
        self.id_label.value = f"ID: {item_id}"
        self.id_label.color = ft.Colors.GREY_600
        self.id_label.visible = True
        
        # Update UI only if elements are already on page
        try:
            if self.text_field.page:
                self.text_field.update()
                self.suggestions_container.update()
                self.id_label.update()
                
                # Notify about validation change
                if self.on_validation_change:
                    self.on_validation_change()
        except:
            pass
        
        # Callback
        if self.on_select_callback:
            self.on_select_callback(name, item_id)
    
    def validate(self):
        """Validate that element is selected from list"""
        if self.text_field.value.strip() and self.selected_id is None:
            self.text_field.border_color = ft.Colors.RED
            self.text_field.error_text = "Select from list"
            self.is_valid = False
            self.id_label.value = "Not selected from list"
            self.id_label.color = ft.Colors.RED
            self.id_label.visible = True
            try:
                if self.text_field.page:
                    self.text_field.update()
                    self.id_label.update()
            except:
                pass
            return False
        elif not self.text_field.value.strip():
            self.text_field.border_color = ft.Colors.RED
            self.text_field.error_text = "Field cannot be empty"
            self.is_valid = False
            try:
                if self.text_field.page:
                    self.text_field.update()
            except:
                pass
            return False
        return True
    
    def get_selected_id(self):
        """Get selected ID"""
        return self.selected_id
    
    def get_selected_name(self):
        """Get selected name"""
        return self.selected_name


class EVEMarketApp:
    """Main application class"""
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "EVE Online Market History"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 1000
        self.page.window.height = 800
        
        # Flag to prevent parallel processing
        self.is_processing = False
        
        # Initialize file monitoring
        self.marketlogs_dir = Path(MARKETLOGS_DIR)
        self.observer = None
        
        # Load data from database
        self.regions_data = {}  # {regionName: regionID}
        self.items_data = {}    # {typeName: typeID}
        
        self.load_data_from_db()
        
        # Create UI
        self.create_ui()
        
        # Start file monitoring
        self.start_file_monitoring()
    
    def load_data_from_db(self):
        """Load regions and types data from MySQL database"""
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            
            if connection.is_connected():
                cursor = connection.cursor()
                
                # Load regions
                cursor.execute("SELECT regionName, regionID FROM regions ORDER BY regionName")
                regions = cursor.fetchall()
                self.regions_data = {name: region_id for name, region_id in regions}
                print(f"Loaded {len(self.regions_data)} regions from database")
                
                # Load types (only published items)
                cursor.execute("SELECT typeName, typeID FROM types WHERE published = 1 ORDER BY typeName")
                types = cursor.fetchall()
                self.items_data = {name: type_id for name, type_id in types}
                print(f"Loaded {len(self.items_data)} items from database")
                
        except Error as e:
            print(f"Database error: {e}")
            # Set empty dicts if database error
            self.regions_data = {}
            self.items_data = {}
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def create_ui(self):
        """Create user interface"""
        # Title
        title = ft.Text(
            "EVE Online Market History",
            size=24,
            weight=ft.FontWeight.BOLD
        )
        
        # Info text
        info_text = ft.Text(
            "Select region and item to view market history",
            size=14,
            color=ft.Colors.GREY_700
        )
        
        # Callback to check both fields
        def check_fields():
            if self.region_field.is_valid and self.item_field.is_valid:
                self.get_button.disabled = False
            else:
                self.get_button.disabled = True
            try:
                if self.get_button.page:
                    self.get_button.update()
            except:
                pass
        
        # Fields with autocomplete
        self.region_field = AutoCompleteField(
            label="Region",
            hint_text="Start typing region name...",
            default_value="",
            data_dict=self.regions_data,
            on_select_callback=lambda name, id: print(f"Selected region: {name} (ID: {id})"),
            on_validation_change=check_fields
        )
        
        self.item_field = AutoCompleteField(
            label="Item",
            hint_text="Start typing item name...",
            default_value="",
            data_dict=self.items_data,
            on_select_callback=lambda name, id: print(f"Selected item: {name} (ID: {id})"),
            on_validation_change=check_fields
        )
        
        # Button to load data
        self.get_button = ft.Button(
            "Get History",
            on_click=self.load_market_data,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )
        
        # Status text
        self.status_text = ft.Text("", size=14)
        
        # Column for table data
        self.data_column = ft.Column([
            ft.Text("Select region and item, then click 'Get History'", 
                   size=14, 
                   color=ft.Colors.GREY_600)
        ])
        
        # Container for table
        self.data_container = ft.Container(
            content=self.data_column,
            expand=True
        )
        
        # Loader
        self.loader = ft.ProgressRing(width=50, height=50)
        self.loader_container = ft.Container(
            content=ft.Column([
                self.loader,
                ft.Text("Loading data...", size=14)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER,
            visible=False,
            expand=True
        )
        
        # Input fields row
        input_row = ft.Row([
            self.region_field.container,
            self.item_field.container
        ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START)
        
        # Layout
        self.page.add(
            ft.Container(
                content=ft.Column([
                    title,
                    info_text,
                    input_row,
                    ft.Row([self.get_button], alignment=ft.MainAxisAlignment.START),
                    self.status_text,
                    ft.Divider(),
                    ft.Stack([
                        self.data_container,
                        self.loader_container
                    ], expand=True)
                ], spacing=10),
                padding=20
            )
        )
    
    async def load_market_data(self, e):
        """Load data from API"""
        # Set processing flag
        self.is_processing = True
        
        # Disable Get button and show loader (if not already shown)
        if not self.get_button.disabled:
            self.get_button.disabled = True
            self.loader_container.visible = True
            self.data_container.visible = False
            self.page.update()
        
        # Get selected IDs
        region_id = self.region_field.get_selected_id()
        type_id = self.item_field.get_selected_id()
        
        if not region_id or not type_id:
            self.status_text.value = "Error: select region and item from list"
            self.status_text.color = ft.Colors.RED
            self.get_button.disabled = False
            self.loader_container.visible = False
            self.data_container.visible = True
            self.page.update()
            self.is_processing = False  # Clear flag
            return
        
        self.status_text.value = "Loading data..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()
        
        try:
            # API request - execute in separate thread
            import asyncio
            loop = asyncio.get_event_loop()
            
            def fetch_data():
                url = f"https://esi.evetech.net/latest/markets/{region_id}/history/"
                params = {
                    "type_id": type_id,
                    "datasource": "tranquility"
                }
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            
            # Execute request asynchronously
            data = await loop.run_in_executor(None, fetch_data)
            
            if not data:
                self.status_text.value = "Data not found"
                self.status_text.color = ft.Colors.ORANGE
                self.get_button.disabled = False
                self.loader_container.visible = False
                self.data_container.visible = True
                self.page.update()
                self.is_processing = False  # Clear flag
                return
            
            # Sort by date descending
            data_sorted = sorted(data, key=lambda x: x['date'], reverse=True)
            
            self.display_data(data_sorted)
            self.status_text.value = f"Loaded records: {len(data_sorted)}"
            self.status_text.color = ft.Colors.GREEN
            
        except requests.exceptions.RequestException as ex:
            self.status_text.value = f"Loading error: {str(ex)}"
            self.status_text.color = ft.Colors.RED
        except Exception as ex:
            self.status_text.value = f"Error: {str(ex)}"
            self.status_text.color = ft.Colors.RED
        finally:
            # Clear processing flag in any case
            self.is_processing = False
            # Enable button back
            self.get_button.disabled = False
            # Hide loader, show table
            self.loader_container.visible = False
            self.data_container.visible = True
        
        self.page.update()
    
    def display_data(self, data):
        """Display data in table"""
        # Create table
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
        
        # Fill with data
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
        
        # Update data column
        self.data_column.controls.clear()
        # Wrap table in scrollable container
        scrollable_table = ft.Container(
            content=ft.Column([self.data_table], scroll=ft.ScrollMode.AUTO),
            height=500,  # Fixed height for scrolling
        )
        self.data_column.controls.append(scrollable_table)
        self.page.update()
    
    def start_file_monitoring(self):
        """Start market logs directory monitoring"""
        if not self.marketlogs_dir.exists():
            print(f"Directory {self.marketlogs_dir} does not exist. Monitoring not started.")
            return
        
        event_handler = MarketLogHandler(self.on_market_log_created)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.marketlogs_dir), recursive=False)
        self.observer.start()
        print(f"Started monitoring directory: {self.marketlogs_dir}")
    
    def stop_file_monitoring(self):
        """Stop monitoring"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("Monitoring stopped")
    
    def on_market_log_created(self, region_name, item_name):
        """Callback when new market log is created"""
        if self.is_processing:
            print(f"Processing already in progress, skipping: {region_name} - {item_name}")
            return
        
        print(f"Processing new log: {region_name} - {item_name}")
        
        # Set values in fields via UI thread
        async def update_fields():
            # Check that region and item exist in data
            if region_name in self.regions_data and item_name in self.items_data:
                region_id = self.regions_data[region_name]
                item_id = self.items_data[item_name]
                
                # Set values in fields
                self.region_field.select_suggestion(region_name, region_id)
                self.item_field.select_suggestion(item_name, item_id)
                
                # Show loader and disable button immediately
                self.get_button.disabled = True
                self.loader_container.visible = True
                self.data_container.visible = False
                self.page.update()
                
                # Start data loading (await since it's async function)
                await self.load_market_data(None)
            else:
                print(f"Region or item not found in database: {region_name}, {item_name}")
        
        # Execute update in UI thread
        self.page.run_task(update_fields)


def main(page: ft.Page):
    EVEMarketApp(page)


if __name__ == "__main__":
    ft.run(main)