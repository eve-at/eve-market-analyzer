"""Character screen UI component"""
import flet as ft
from datetime import datetime
from threading import Thread
from src.auth.eve_sso import EVESSO
from src.auth.esi_api import ESIAPI
from src.database.models import (
    get_character, save_character, get_current_character_id,
    save_setting, create_character_history_table, save_character_order_history
)


class CharacterScreen:
    """Character screen with EVE Online account and trading settings"""

    def __init__(self, page: ft.Page, on_back_callback, on_logout_callback=None):
        self.page = page
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback
        self.current_character = None
        self.eve_sso = EVESSO()

        # Load current character if logged in
        character_id = get_current_character_id()
        if character_id:
            self.current_character = get_character(character_id)
            # Create history table for this character if it doesn't exist
            create_character_history_table(character_id)

        # Load settings from database or use defaults
        broker_fee_sell = "3.00"
        broker_fee_buy = "3.00"
        sales_tax = "7.50"

        if self.current_character:
            broker_fee_sell = str(self.current_character.get('broker_fee_sell', 3.00))
            broker_fee_buy = str(self.current_character.get('broker_fee_buy', 3.00))
            sales_tax = str(self.current_character.get('sales_tax', 7.50))

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

        # Logout button
        self.logout_button = ft.TextButton(
            "Logout",
            on_click=self.on_logout,
            visible=bool(self.current_character),
            margin=ft.Margin(left=-12)
        )

        if self.current_character:
            self.character_name_text.value = self.current_character.get('character_name')
            self.character_id_text.value = f"ID: {self.current_character.get('character_id')}"
            self.character_info_row.visible = True
            self.character_info_row.controls = [
                self.character_avatar,
                ft.Column([
                    self.character_name_text,
                    self.character_id_text,
                    self.logout_button
                ], spacing=2)
            ]

        # EVE Online login button
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

        # Trading settings fields
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

        # Save button
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

        # Update Historical Orders button
        self.update_orders_button = ft.ElevatedButton(
            "Update Historical Orders",
            on_click=self.on_update_orders,
            visible=bool(self.current_character),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )

        # Log container for import progress
        self.log_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            height=300
        )

        self.log_container = ft.Container(
            content=self.log_column,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10,
            visible=False
        )

        # EVE Online Account column
        eve_account_column = ft.Column([
            ft.Text(
                "EVE Online Account",
                size=18,
                weight=ft.FontWeight.W_500
            ),
            ft.Container(height=10),
            self.character_info_row,
            ft.Row([
                self.eve_login_button
            ], spacing=10)
        ], spacing=5)

        # Trading Settings column
        trading_settings_column = ft.Column([
            ft.Text(
                "Trading Settings",
                size=18,
                weight=ft.FontWeight.W_500
            ),
            ft.Row([
                self.broker_fee_sell_field,
                self.broker_fee_buy_field,
                self.sales_tax_field
            ]),
            ft.Row([
                self.save_button
            ], alignment=ft.MainAxisAlignment.START)
        ], spacing=5)

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                # EVE Account and Trading Settings side by side
                ft.Row([
                    eve_account_column,
                    ft.Container(width=50),
                    trading_settings_column
                ], spacing=0, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(height=10),
                self.status_text,
                ft.Container(height=20),
                # Update Historical Orders section
                ft.Row([
                    self.update_orders_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                self.log_container
            ], spacing=5, scroll=ft.ScrollMode.AUTO),
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

            # Create history table for this character if it doesn't exist
            create_character_history_table(character_data['character_id'])

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
                    self.logout_button
                ], spacing=2)
            ]
            self.eve_login_button.visible = False
            self.logout_button.visible = True
            self.update_orders_button.visible = True

            self.status_text.value = f"Successfully logged in as {character_data.get('character_name')}"
            self.status_text.color = ft.Colors.GREEN

            # Call logout callback to refresh app bar
            if self.on_logout_callback:
                self.on_logout_callback()

            self.page.update()

    def on_logout(self, e):
        """Handle logout button click"""
        # Clear current character
        save_setting('current_character_id', '')

        self.current_character = None
        self.character_info_row.visible = False
        self.eve_login_button.visible = True
        self.logout_button.visible = False
        self.update_orders_button.visible = False
        self.log_container.visible = False

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

                self.status_text.value = "Settings saved successfully!"
                self.status_text.color = ft.Colors.GREEN
            else:
                self.status_text.value = "Please log in first"
                self.status_text.color = ft.Colors.ORANGE

        except ValueError as e:
            self.status_text.value = "Error: Invalid number format"
            self.status_text.color = ft.Colors.RED
        except Exception as e:
            self.status_text.value = f"Error saving settings: {str(e)}"
            self.status_text.color = ft.Colors.RED

        self.page.update()

    def on_update_orders(self, e):
        """Handle Update Historical Orders button click"""
        if not self.current_character:
            self.status_text.value = "Please log in first"
            self.status_text.color = ft.Colors.ORANGE
            self.page.update()
            return

        # Disable button during update
        self.update_orders_button.disabled = True
        self.log_column.controls.clear()
        self.log_container.visible = True
        self.page.update()

        # Run import in background thread
        thread = Thread(target=self._run_orders_import, daemon=True)
        thread.start()

    def _run_orders_import(self):
        """Run orders import in background thread"""
        def log_callback(message):
            """Callback to display log messages"""
            async def add_log():
                self.log_column.controls.append(
                    ft.Text(
                        message,
                        size=12,
                        color=ft.Colors.BLACK,
                        selectable=True
                    )
                )
                self.page.update()

            self.page.run_task(add_log)

        try:
            character_id = self.current_character['character_id']
            access_token = self.current_character.get('access_token')
            refresh_token = self.current_character.get('refresh_token')
            token_expiry = self.current_character.get('token_expiry')

            log_callback(f"Starting orders import for character ID {character_id}...")

            # Check if token needs refresh
            esi_api = ESIAPI()
            if not access_token or not token_expiry or datetime.now() >= token_expiry:
                log_callback("Access token expired or missing, refreshing...")

                if not refresh_token:
                    log_callback("ERROR: No refresh token available. Please log in again.")
                    async def update_ui():
                        self.update_orders_button.disabled = False
                        self.page.update()
                    self.page.run_task(update_ui)
                    return

                token_data = esi_api.refresh_access_token(refresh_token)
                if not token_data:
                    log_callback("ERROR: Failed to refresh access token. Please log in again.")
                    async def update_ui():
                        self.update_orders_button.disabled = False
                        self.page.update()
                    self.page.run_task(update_ui)
                    return

                access_token = token_data['access_token']

                # Save updated token to database
                save_character({
                    'character_id': character_id,
                    'character_name': self.current_character['character_name'],
                    'access_token': access_token,
                    'token_expiry': token_data['token_expiry']
                })

                log_callback("Access token refreshed successfully")

            # Fetch orders with pagination
            log_callback("Fetching orders history from ESI API...")
            page = 1
            total_orders = 0
            total_inserted = 0
            total_skipped = 0

            while True:
                log_callback(f"Fetching page {page}...")

                orders, has_more = esi_api.get_character_orders_history(
                    character_id,
                    access_token,
                    page
                )

                if orders is None:
                    log_callback(f"ERROR: Failed to fetch page {page}")
                    break

                if not orders:
                    log_callback("No more orders to fetch")
                    break

                log_callback(f"Received {len(orders)} orders from page {page}")
                total_orders += len(orders)

                # Save orders to database
                log_callback(f"Saving orders to database...")
                inserted, skipped = save_character_order_history(character_id, orders)
                total_inserted += inserted
                total_skipped += skipped

                log_callback(f"Page {page}: Inserted {inserted} new orders, skipped {skipped} duplicates")

                if not has_more:
                    log_callback("All pages fetched")
                    break

                page += 1

            log_callback("=" * 50)
            log_callback(f"Import completed!")
            log_callback(f"Total orders fetched: {total_orders}")
            log_callback(f"New orders inserted: {total_inserted}")
            log_callback(f"Duplicates skipped: {total_skipped}")

        except Exception as e:
            log_callback(f"ERROR: {str(e)}")
            import traceback
            log_callback(traceback.format_exc())

        finally:
            # Re-enable button
            async def update_ui():
                self.update_orders_button.disabled = False
                self.page.update()
            self.page.run_task(update_ui)

    def build(self):
        """Build and return the UI container"""
        return self.container
