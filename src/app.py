"""Main application class"""
import flet as ft
import requests
from pathlib import Path
from watchdog.observers import Observer
from settings import MARKETLOGS_DIR
from .handlers import MarketLogHandler
from .ui import AutoCompleteField
from .database import load_regions_and_items


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
        self.regions_data, self.items_data = load_regions_and_items()

        # Create UI
        self.create_ui()

        # Start file monitoring
        self.start_file_monitoring()

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
