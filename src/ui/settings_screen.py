"""Settings screen UI component"""
import flet as ft
from src.auth.eve_sso import EVESSO
from src.database.models import (
    get_character, save_character, get_current_character_id,
    save_setting, get_setting
)


class SettingsScreen:
    """Application settings screen"""

    def __init__(self, page: ft.Page, on_back_callback, on_logout_callback=None, marketlogs_dir=""):
        self.page = page
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback
        self.current_character = None
        self.eve_sso = EVESSO()

        # Load current character if logged in
        character_id = get_current_character_id()
        if character_id:
            self.current_character = get_character(character_id)

        # Load settings from database or use defaults
        broker_fee_sell = "3.00"
        broker_fee_buy = "3.00" # for structures it can be 0.5
        sales_tax = "7.50"

        if self.current_character:
            broker_fee_sell = str(self.current_character.get('broker_fee_sell', 3.00))
            broker_fee_buy = str(self.current_character.get('broker_fee_buy', 3.00))
            sales_tax = str(self.current_character.get('sales_tax', 7.50))

        # Load marketlogs directory from database or use provided default
        saved_marketlogs = get_setting('marketlogs_dir', marketlogs_dir)

        # Load CSV export path from database or use default
        saved_csv_export_path = get_setting('csv_export_path', 'data')

        # Character info display
        self.character_info_row = ft.Row(visible=False, spacing=15)

        # Set default avatar or character avatar
        avatar_src = "static/img/default_avatar.svg"
        if self.current_character:
            avatar_src = self.current_character.get('character_portrait_url', avatar_src)

        self.character_avatar = ft.Image(
            src=avatar_src,
            width=64,
            height=64,
            border_radius=32,
            fit=ft.BoxFit.COVER
        )
        self.character_name_text = ft.Text(size=16, weight=ft.FontWeight.W_500)
        self.character_id_text = ft.Text(size=12, color=ft.Colors.GREY_600)

        if self.current_character:
            self.character_name_text.value = self.current_character.get('character_name')
            self.character_id_text.value = f"ID: {self.current_character.get('character_id')}"
            self.character_info_row.visible = True
            self.character_info_row.controls = [
                self.character_avatar,
                ft.Column([
                    self.character_name_text,
                    self.character_id_text,
                    ft.Text("Logged in", size=12, color=ft.Colors.GREEN)
                ], spacing=2)
            ]

        # EVE Online login button (using official SSO button image)
        self.eve_login_button = ft.Container(
            content=ft.Image(
                src="static/img/ssologin.png",
                width=270,
                fit=ft.BoxFit.CONTAIN
            ),
            on_click=self.on_eve_login,
            visible=not bool(self.current_character),
            ink=True,
            border_radius=5
        )

        # Logout button
        self.logout_button = ft.TextButton(
            "Logout",
            on_click=self.on_logout,
            visible=bool(self.current_character)
        )

        # Settings fields
        self.broker_fee_sell_field = ft.TextField(
            label="Broker Fee (sell), %",
            value=broker_fee_sell,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.broker_fee_buy_field = ft.TextField(
            label="Broker Fee (buy), %",
            value=broker_fee_buy,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.sales_tax_field = ft.TextField(
            label="Sales Tax, %",
            value=sales_tax,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.marketlogs_dir_field = ft.TextField(
            label="Market Logs Directory",
            value=saved_marketlogs,
            width=500,
            hint_text="Path to EVE Online market logs folder"
        )

        self.csv_export_path_field = ft.TextField(
            label="CSV Export Directory",
            value=saved_csv_export_path,
            width=500,
            hint_text="Path to save exported CSV files (default: data)"
        )

        self.csv_browse_button = ft.ElevatedButton(
            "Browse",
            on_click=self.on_browse_csv_path,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREY_700,
                color=ft.Colors.WHITE,
                padding=ft.Padding(15, 10, 15, 10)
            )
        )

        # Buttons
        self.save_button = ft.ElevatedButton(
            "Save",
            on_click=self.on_save,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(30, 10, 30, 10)
            )
        )

        # Status text
        self.status_text = ft.Text("", size=14)

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Settings",
                    size=28,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),
                ft.Text(
                    "Configure application settings",
                    size=14,
                    color=ft.Colors.GREY_700
                ),
                ft.Container(height=30),

                # EVE Online Account section
                ft.Text(
                    "EVE Online Account",
                    size=18,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(height=10),
                self.character_info_row,
                ft.Row([
                    self.eve_login_button,
                    self.logout_button
                ], spacing=10),
                ft.Container(height=30),

                # Trading settings section
                ft.Text(
                    "Trading Settings",
                    size=18,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(height=10),
                ft.Row([
                    self.broker_fee_sell_field,
                    self.broker_fee_buy_field,
                    self.sales_tax_field
                ], spacing=20),
                ft.Container(height=30),

                # Application settings section
                ft.Text(
                    "Application Settings",
                    size=18,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(height=10),
                self.marketlogs_dir_field,
                ft.Container(height=10),
                ft.Row([
                    self.csv_export_path_field,
                    self.csv_browse_button
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.END),
                ft.Container(height=30),

                # Save button
                ft.Row([
                    self.save_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                self.status_text
            ], spacing=5),
            padding=20,
            expand=True
        )

    def on_eve_login(self, e):
        """Handle EVE Online login button click"""
        self.status_text.value = "Opening browser for EVE Online authentication..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()

        # Start SSO login flow
        self.eve_sso.start_login(callback_func=self.on_login_complete)

    def on_login_complete(self, character_data):
        """Called when EVE SSO login is complete"""
        if character_data:
            # Save character to database
            save_character(character_data)

            # Save as current character
            save_setting('current_character_id', str(character_data['character_id']))

            # Update UI
            self.current_character = character_data
            self.character_avatar.src = character_data.get('character_portrait_url')
            self.character_name_text.value = character_data.get('character_name')
            self.character_id_text.value = f"ID: {character_data.get('character_id')}"
            self.character_info_row.visible = True
            self.character_info_row.controls = [
                self.character_avatar,
                ft.Column([
                    self.character_name_text,
                    self.character_id_text,
                    ft.Text("Logged in", size=12, color=ft.Colors.GREEN)
                ], spacing=2)
            ]
            self.eve_login_button.visible = False
            self.logout_button.visible = True

            self.status_text.value = f"Successfully logged in as {character_data.get('character_name')}"
            self.status_text.color = ft.Colors.GREEN

            self.page.update()

    def on_logout(self, e):
        """Handle logout button click"""
        # Clear current character
        save_setting('current_character_id', '')

        self.current_character = None
        self.character_info_row.visible = False
        self.eve_login_button.visible = True
        self.logout_button.visible = False

        # Reset avatar to default
        self.character_avatar.src = "static/img/default_avatar.svg"

        # Reset broker fee and sales tax to defaults
        self.broker_fee_sell_field.value = "3.00"
        self.broker_fee_buy_field.value = "3.00"
        self.sales_tax_field.value = "7.50"

        self.status_text.value = "Logged out successfully"
        self.status_text.color = ft.Colors.ORANGE

        # Call logout callback to refresh app bar
        if self.on_logout_callback:
            self.on_logout_callback()

        self.page.update()

    def on_browse_csv_path(self, e):
        """Handle browse button click for CSV export path"""
        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                self.csv_export_path_field.value = result.path
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.get_directory_path(dialog_title="Select CSV Export Directory")

    def on_save(self, e):
        """Handle save button click"""
        try:
            # Save trading settings to character if logged in
            if self.current_character:
                broker_fee_sell = float(self.broker_fee_sell_field.value)
                broker_fee_buy = float(self.broker_fee_buy_field.value)
                sales_tax = float(self.sales_tax_field.value)

                save_character({
                    'character_id': self.current_character['character_id'],
                    'character_name': self.current_character['character_name'],
                    'broker_fee_sell': broker_fee_sell,
                    'broker_fee_buy': broker_fee_buy,
                    'sales_tax': sales_tax
                })

            # Save marketlogs directory to global settings
            save_setting('marketlogs_dir', self.marketlogs_dir_field.value)

            # Save CSV export path to global settings
            save_setting('csv_export_path', self.csv_export_path_field.value)

            self.status_text.value = "Settings saved successfully!"
            self.status_text.color = ft.Colors.GREEN

        except ValueError as e:
            self.status_text.value = "Error: Invalid number format"
            self.status_text.color = ft.Colors.RED
        except Exception as e:
            self.status_text.value = f"Error saving settings: {str(e)}"
            self.status_text.color = ft.Colors.RED

        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
