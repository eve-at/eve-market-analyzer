"""Initialization screen UI component"""
import flet as ft
import threading
from src.database import validate_database
from src.handlers.import_static_data import import_static_data


class InitScreen:
    """Initialization screen to check database and import data if needed"""

    def __init__(self, page: ft.Page, on_complete_callback):
        self.page = page
        self.on_complete_callback = on_complete_callback
        self.is_importing = False

        # UI elements
        self.status_text = ft.Text(
            "Checking database connection...",
            size=16,
            text_align=ft.TextAlign.CENTER
        )

        self.progress_ring = ft.ProgressRing(
            width=50,
            height=50,
            visible=True
        )

        self.import_button = ft.ElevatedButton(
            "Fill static data",
            on_click=self.start_import,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(30, 15, 30, 15)
            )
        )

        self.retry_button = ft.ElevatedButton(
            "Retry",
            on_click=self.check_database,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.ORANGE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(30, 15, 30, 15)
            )
        )

        # Log container for import progress
        self.log_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,  # Auto-scroll to bottom
            spacing=2,
        )

        self.log_container = ft.Container(
            content=self.log_column,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10,
            bgcolor=ft.Colors.BLACK,
            height=350,
            width=700,
            visible=False
        )

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Container(height=50),
                ft.Text(
                    "EVE Online Market History",
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=30),
                self.progress_ring,
                ft.Container(height=20),
                self.status_text,
                ft.Container(height=30),
                ft.Row([
                    self.import_button,
                    self.retry_button
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=20),
                self.log_container
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER,
            expand=True
        )

    def build(self):
        """Build and return the UI container"""
        return self.container

    def check_database(self, e=None):
        """Check database status"""
        self.status_text.value = "Checking database connection..."
        self.progress_ring.visible = True
        self.import_button.visible = False
        self.retry_button.visible = False
        self.log_container.visible = False
        self.page.update()

        # Run validation in background thread
        def validate():
            db_status = validate_database()

            # Update UI based on status
            async def update_ui():
                self.progress_ring.visible = False

                if not db_status.connected:
                    self.status_text.value = f"Database connection error:\n{db_status.error_message}\n\nPlease check your database configuration."
                    self.status_text.color = ft.Colors.RED
                    self.retry_button.visible = True
                elif not db_status.is_ready:
                    if not db_status.regions_exist or not db_status.types_exist:
                        self.status_text.value = "Database is empty. Please import static data."
                        self.status_text.color = ft.Colors.ORANGE
                        self.import_button.visible = True
                else:
                    self.status_text.value = f"Database ready!\n{db_status.regions_count} regions, {db_status.types_count} item types"
                    self.status_text.color = ft.Colors.GREEN

                    # Call completion callback after a short delay
                    import asyncio
                    await asyncio.sleep(1)
                    if self.on_complete_callback:
                        self.on_complete_callback()

                self.page.update()

            self.page.run_task(update_ui)

        threading.Thread(target=validate, daemon=True).start()

    def start_import(self, e):
        """Start static data import"""
        if self.is_importing:
            return

        self.is_importing = True
        self.import_button.disabled = True
        self.status_text.value = "Importing static data..."
        self.status_text.color = ft.Colors.BLUE
        self.progress_ring.visible = False  # Hide progress ring during import
        self.log_column.controls.clear()
        self.log_container.visible = True
        self.page.update()

        def import_data():
            """Run import in background thread"""

            def log_callback(message):
                """Callback to display log messages"""
                async def add_log():
                    self.log_column.controls.append(
                        ft.Text(
                            message,
                            size=11,
                            color=ft.Colors.GREEN_300,
                            font_family="Consolas",
                            selectable=True
                        )
                    )
                    self.page.update()

                self.page.run_task(add_log)

            # Run import
            success = import_static_data(callback=log_callback)

            # Update UI after import
            async def update_after_import():
                self.is_importing = False
                self.progress_ring.visible = False

                if success:
                    self.status_text.value = "Import completed successfully!\nStarting application..."
                    self.status_text.color = ft.Colors.GREEN
                    self.import_button.visible = False
                    self.page.update()

                    # Wait a bit then call completion callback
                    import asyncio
                    await asyncio.sleep(2)
                    if self.on_complete_callback:
                        self.on_complete_callback()
                else:
                    self.status_text.value = "Import failed. Please check the log above."
                    self.status_text.color = ft.Colors.RED
                    self.import_button.disabled = False
                    self.retry_button.visible = True

                self.page.update()

            self.page.run_task(update_after_import)

        threading.Thread(target=import_data, daemon=True).start()
