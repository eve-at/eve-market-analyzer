"""Courier Path Finder screen UI component"""
import flet as ft
from src.handlers.courier_path_handler import (
    search_solar_systems, search_stations, optimize_courier_route,
    get_character_location, refresh_access_token
)
from src.database.models import get_current_character_id, get_character, save_character
import threading
from datetime import datetime


class CourierPathFinderScreen:
    """Screen for finding optimal courier routes"""

    def __init__(self, page: ft.Page, on_back_callback):
        self.page = page
        self.on_back_callback = on_back_callback

        # Check if user is logged in
        self.character_id = get_current_character_id()
        self.is_logged_in = bool(self.character_id)
        self.character = None
        if self.is_logged_in:
            self.character = get_character(self.character_id)

        # Data storage
        self.start_system_id = None
        self.start_system_name = None
        self.destination_stations = []  # List of {'id': station_id, 'name': station_name, 'system_id': system_id}

        # Start System field
        self.start_system_field = ft.TextField(
            label="Start System",
            hint_text="Type at least 3 characters...",
            width=350,
            on_change=self.on_start_system_change
        )

        self.start_system_id_label = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_600,
            visible=False
        )

        self.start_system_suggestions = ft.Column(
            visible=False,
            spacing=2
        )

        # Detect button (only visible if logged in)
        self.detect_button = ft.ElevatedButton(
            "Detect",
            on_click=self.on_detect_location,
            visible=self.is_logged_in,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.ORANGE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(15, 10, 15, 10)
            ),
            tooltip="Detect current character location"
        )

        # Destination stations list
        self.destinations_column = ft.Column(spacing=10)

        # Add Destination button
        self.add_destination_button = ft.ElevatedButton(
            "Add Destination Station",
            on_click=self.on_add_destination,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )

        # Optimize Route button
        self.optimize_button = ft.ElevatedButton(
            "Optimize Route",
            on_click=self.on_optimize_route,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
                padding=ft.Padding(30, 10, 30, 10)
            )
        )

        # Results container
        self.results_container = ft.Container(
            visible=False,
            padding=10
        )

        # Add first destination station field
        self.add_destination_station_field()

        # Left column - input fields
        left_column = ft.Column([
            # Start System
            ft.Text("Start System", size=14, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Column([
                    self.start_system_field,
                    self.start_system_id_label,
                    self.start_system_suggestions
                ], spacing=5, expand=True),
                self.detect_button
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Container(height=15),

            # Destination Stations
            ft.Text("Destination Stations", size=14, weight=ft.FontWeight.BOLD),
            self.destinations_column,
            ft.Container(height=10),
            self.add_destination_button,
        ], spacing=5, scroll=ft.ScrollMode.AUTO, expand=True)

        # Right column - optimize button and results
        right_column = ft.Column([
            self.optimize_button,
            ft.Container(height=20),
            self.results_container
        ], spacing=5, scroll=ft.ScrollMode.AUTO, expand=True)

        # Two-column layout
        content = ft.Row([
            ft.Container(
                content=left_column,
                expand=1,
                padding=ft.padding.only(right=10)
            ),
            ft.VerticalDivider(width=1),
            ft.Container(
                content=right_column,
                expand=1,
                padding=ft.padding.only(left=10)
            )
        ], spacing=0, expand=True, vertical_alignment=ft.CrossAxisAlignment.START)

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Courier Path Finder",
                    size=18,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=5),
                ft.Text(
                    "Optimize delivery routes for multiple stations",
                    size=12,
                    color=ft.Colors.GREY_700
                ),
                ft.Divider(),
                content
            ], spacing=5, expand=True),
            padding=10,
            expand=True
        )

    def on_detect_location(self, e):
        """Handle detect location button click"""
        if not self.character:
            return

        # Disable button during detection
        self.detect_button.disabled = True
        self.detect_button.text = "Detecting..."
        self.page.update()

        # Run detection in background thread
        def detect_thread():
            try:
                character_id = self.character['character_id']
                access_token = self.character.get('access_token')
                refresh_token = self.character.get('refresh_token')
                token_expiry = self.character.get('token_expiry')

                # Check if token needs refresh
                if not access_token or not token_expiry or datetime.now() >= token_expiry:
                    if not refresh_token:
                        async def show_error():
                            self.detect_button.disabled = False
                            self.detect_button.text = "Detect"
                            self.page.snack_bar = ft.SnackBar(
                                content=ft.Text("Error: No refresh token available. Please log in again."),
                                duration=3000
                            )
                            self.page.snack_bar.open = True
                            self.page.update()
                        self.page.run_task(show_error)
                        return

                    # Refresh token
                    token_data = refresh_access_token(refresh_token)
                    if not token_data:
                        async def show_error():
                            self.detect_button.disabled = False
                            self.detect_button.text = "Detect"
                            self.page.snack_bar = ft.SnackBar(
                                content=ft.Text("Error: Failed to refresh access token. Please log in again."),
                                duration=3000
                            )
                            self.page.snack_bar.open = True
                            self.page.update()
                        self.page.run_task(show_error)
                        return

                    access_token = token_data['access_token']

                    # Save updated token to database
                    save_character({
                        'character_id': character_id,
                        'character_name': self.character['character_name'],
                        'access_token': access_token,
                        'token_expiry': token_data['token_expiry']
                    })

                    # Update local character data
                    self.character['access_token'] = access_token
                    self.character['token_expiry'] = token_data['token_expiry']

                # Get character location
                location = get_character_location(character_id, access_token)

                if location:
                    async def update_location():
                        self.select_start_system(
                            location['solar_system_name'],
                            location['solar_system_id']
                        )
                        self.detect_button.disabled = False
                        self.detect_button.text = "Detect"
                        self.page.snack_bar = ft.SnackBar(
                            content=ft.Text(f"Location detected: {location['solar_system_name']}"),
                            duration=2000
                        )
                        self.page.snack_bar.open = True
                        self.page.update()
                    self.page.run_task(update_location)
                else:
                    async def show_error():
                        self.detect_button.disabled = False
                        self.detect_button.text = "Detect"
                        self.page.snack_bar = ft.SnackBar(
                            content=ft.Text("Error: Failed to get character location"),
                            duration=3000
                        )
                        self.page.snack_bar.open = True
                        self.page.update()
                    self.page.run_task(show_error)

            except Exception as ex:
                async def show_error():
                    self.detect_button.disabled = False
                    self.detect_button.text = "Detect"
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Error: {str(ex)}"),
                        duration=3000
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                self.page.run_task(show_error)

        thread = threading.Thread(target=detect_thread, daemon=True)
        thread.start()

    def on_start_system_change(self, e):
        """Handle start system text field change"""
        query = self.start_system_field.value.strip()

        # Reset
        if len(query) < 3:
            self.start_system_suggestions.visible = False
            self.start_system_suggestions.controls.clear()
            self.start_system_id_label.visible = False
            self.start_system_id = None
            self.start_system_name = None
            self.validate_form()
            self.page.update()
            return

        # Search for systems
        systems = search_solar_systems(query)

        if systems:
            self.show_start_system_suggestions(systems)
        else:
            self.start_system_suggestions.visible = False
            self.start_system_suggestions.controls.clear()
            self.page.update()

    def show_start_system_suggestions(self, systems):
        """Show suggestions for start system"""
        self.start_system_suggestions.controls.clear()

        for name, system_id in systems.items():
            suggestion = ft.Container(
                content=ft.Text(name, size=12),
                padding=8,
                border=ft.border.all(1, ft.Colors.GREY_400),
                border_radius=3,
                bgcolor=ft.Colors.WHITE,
                on_click=lambda e, n=name, sid=system_id: self.select_start_system(n, sid),
                ink=True
            )
            self.start_system_suggestions.controls.append(suggestion)

        self.start_system_suggestions.visible = True
        self.page.update()

    def select_start_system(self, name, system_id):
        """Select start system from suggestions"""
        self.start_system_field.value = name
        self.start_system_id = system_id
        self.start_system_name = name

        self.start_system_suggestions.visible = False
        self.start_system_suggestions.controls.clear()

        self.start_system_id_label.value = f"System ID: {system_id}"
        self.start_system_id_label.visible = True

        self.validate_form()
        self.page.update()

    def add_destination_station_field(self):
        """Add a new destination station field"""
        index = len(self.destination_stations)

        # Create destination data dict first
        dest_data = {
            'id': None,
            'name': None,
            'system_id': None,
            'text_field': None,
            'id_label': None,
            'suggestions': None,
            'remove_button': None,
            'container': None
        }

        # Create text field with reference to dest_data
        text_field = ft.TextField(
            label=f"Destination Station {index + 1}",
            hint_text="Type at least 3 characters...",
            width=350,
            on_change=lambda e, dest=dest_data: self.on_destination_change(e, dest)
        )

        # ID label
        id_label = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_600,
            visible=False
        )

        # Suggestions
        suggestions = ft.Column(
            visible=False,
            spacing=2
        )

        # Remove button (only if more than one destination)
        remove_button = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_color=ft.Colors.RED,
            on_click=lambda e, dest=dest_data: self.on_remove_destination(dest),
            visible=len(self.destination_stations) > 0
        )

        # Container for this destination (removed drag handle)
        destination_row = ft.Row([
            ft.Column([
                text_field,
                id_label,
                suggestions
            ], spacing=5, expand=True),
            remove_button
        ], spacing=10, alignment=ft.MainAxisAlignment.START)

        # Update destination data
        dest_data['text_field'] = text_field
        dest_data['id_label'] = id_label
        dest_data['suggestions'] = suggestions
        dest_data['remove_button'] = remove_button
        dest_data['container'] = destination_row

        # Add to list
        self.destination_stations.append(dest_data)
        self.destinations_column.controls.append(destination_row)

        # Update remove button visibility and labels
        self.update_destination_labels()
        self.update_remove_buttons_visibility()
        self.validate_form()
        self.page.update()

    def update_destination_labels(self):
        """Update labels for all destination stations"""
        for i, dest in enumerate(self.destination_stations):
            dest['text_field'].label = f"Destination Station {i + 1}"

    def update_remove_buttons_visibility(self):
        """Update visibility of remove buttons"""
        show_remove = len(self.destination_stations) > 1
        for dest in self.destination_stations:
            dest['remove_button'].visible = show_remove

    def on_destination_change(self, e, dest):
        """Handle destination text field change"""
        query = dest['text_field'].value.strip()

        # Reset
        if len(query) < 3:
            dest['suggestions'].visible = False
            dest['suggestions'].controls.clear()
            dest['id_label'].visible = False
            dest['id'] = None
            dest['name'] = None
            dest['system_id'] = None
            self.validate_form()
            self.page.update()
            return

        # Search for stations
        stations = search_stations(query)

        if stations:
            self.show_destination_suggestions(dest, stations)
        else:
            dest['suggestions'].visible = False
            dest['suggestions'].controls.clear()
            self.page.update()

    def show_destination_suggestions(self, dest, stations):
        """Show suggestions for destination station"""
        dest['suggestions'].controls.clear()

        for name, (station_id, system_id) in stations.items():
            suggestion = ft.Container(
                content=ft.Text(name, size=12),
                padding=8,
                border=ft.border.all(1, ft.Colors.GREY_400),
                border_radius=3,
                bgcolor=ft.Colors.WHITE,
                on_click=lambda e, n=name, sid=station_id, sysid=system_id, d=dest: self.select_destination_station(d, n, sid, sysid),
                ink=True
            )
            dest['suggestions'].controls.append(suggestion)

        dest['suggestions'].visible = True
        self.page.update()

    def select_destination_station(self, dest, name, station_id, system_id):
        """Select destination station from suggestions"""
        dest['text_field'].value = name
        dest['id'] = station_id
        dest['name'] = name
        dest['system_id'] = system_id

        dest['suggestions'].visible = False
        dest['suggestions'].controls.clear()

        dest['id_label'].value = f"Station ID: {station_id}"
        dest['id_label'].visible = True

        self.validate_form()
        self.page.update()

    def on_add_destination(self, e):
        """Handle add destination button click"""
        self.add_destination_station_field()

    def on_remove_destination(self, dest_to_remove):
        """Handle remove destination button click"""
        if len(self.destination_stations) <= 1:
            return

        # Remove from UI
        self.destinations_column.controls.remove(dest_to_remove['container'])

        # Remove from data
        self.destination_stations.remove(dest_to_remove)

        # Update labels for all remaining destinations
        self.update_destination_labels()

        # Update remove button visibility
        self.update_remove_buttons_visibility()
        self.validate_form()
        self.page.update()

    def validate_form(self):
        """Validate form and enable/disable optimize button"""
        # Check if start system is selected
        if not self.start_system_id:
            self.optimize_button.disabled = True
            self.page.update()
            return

        # Check if all destinations are selected
        all_valid = all(dest['id'] is not None for dest in self.destination_stations)

        self.optimize_button.disabled = not all_valid
        self.page.update()

    def on_optimize_route(self, e):
        """Handle optimize route button click"""
        if not self.start_system_id:
            return

        # Get destination station IDs
        destination_ids = [dest['id'] for dest in self.destination_stations if dest['id']]

        if not destination_ids:
            return

        # Disable button during optimization
        self.optimize_button.disabled = True
        self.optimize_button.text = "Optimizing..."
        self.results_container.visible = False
        self.page.update()

        # Run optimization in background thread
        def optimize_thread():
            result = optimize_courier_route(self.start_system_id, destination_ids)

            # Update UI after completion
            async def update_ui():
                self.optimize_button.disabled = False
                self.optimize_button.text = "Optimize Route"

                if result['success']:
                    self.display_results(result)
                else:
                    self.show_error(result.get('error', 'Unknown error'))

                self.page.update()

            self.page.run_task(update_ui)

        thread = threading.Thread(target=optimize_thread, daemon=True)
        thread.start()

    def get_security_color(self, security):
        """Get color for security status based on EVE Online standards

        Args:
            security: Security status value (0.0 to 1.0, or negative for null-sec)

        Returns:
            str: Color string for the security indicator
        """
        # Ensure security is a float for proper comparison
        try:
            security = float(security)
        except (TypeError, ValueError):
            security = 0.0

        # Round to 1 decimal place to avoid floating point comparison issues
        security = round(security, 1)

        if security >= 0.5:
            # High-sec: Green/Blue shades
            if security >= 0.9:
                return ft.Colors.BLUE_400
            elif security >= 0.7:
                return ft.Colors.GREEN_400
            else:
                return ft.Colors.LIGHT_GREEN_400
        elif security > 0.0:
            # Low-sec: Yellow/Orange shades
            if security >= 0.3:
                return ft.Colors.YELLOW_700
            else:
                return ft.Colors.ORANGE_700
        else:
            # Null-sec: Red/Purple shades
            if security >= -0.3:
                return ft.Colors.RED_700
            else:
                return ft.Colors.DEEP_PURPLE_700

    def display_results(self, result):
        """Display optimization results"""
        total_jumps = result['total_jumps']
        route = result['route']
        full_path = result.get('full_path', [])

        # Build results UI
        results_items = []

        # Header with route visualization
        header_column = ft.Column([
            ft.Text(
                f"Optimized Route - Total Jumps: {total_jumps}",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREEN
            )
        ], spacing=5)

        # Create route visualization with colored squares
        if full_path:
            route_squares = []
            for system in full_path:
                security = system.get('security', 0.0)
                security_color = self.get_security_color(security)
                is_destination = system.get('is_destination', False)

                # Create square - filled for transit, hollow for destinations
                if is_destination:
                    # Hollow square (border only) for destination systems
                    square = ft.Container(
                        width=18,
                        height=18,
                        border=ft.border.all(3, security_color),
                        border_radius=2,
                        tooltip=system.get('system_name', '')
                    )
                else:
                    # Filled square for transit systems
                    square = ft.Container(
                        width=18,
                        height=18,
                        bgcolor=security_color,
                        border_radius=2,
                        tooltip=system.get('system_name', '')
                    )

                route_squares.append(square)

            # Add route visualization below header
            route_visual = ft.Row(
                route_squares,
                spacing=2,
                wrap=True
            )
            header_column.controls.append(route_visual)

        results_items.append(header_column)
        results_items.append(ft.Container(height=15))

        # Route list (without security squares now)
        for i, stop in enumerate(route):
            # Station name (clickable to copy)
            station_text = ft.Text(
                f"{i + 1}. {stop['station_name']}",
                size=14,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.BLUE
            )

            station_container = ft.Container(
                content=station_text,
                on_click=lambda e, name=stop['station_name']: self.page.run_task(self.copy_to_clipboard, name),
                ink=True,
                padding=5,
                border_radius=3
            )

            # System name
            system_text = ft.Text(
                f"   System: {stop['system_name']}",
                size=12,
                color=ft.Colors.GREY_700
            )

            # Jumps info (without security square)
            jumps_text_value = f"Jumps: {stop['jumps_from_previous']}" if stop['jumps_from_previous'] > 0 else "(Starting location)"

            jumps_text = ft.Text(
                f"   {jumps_text_value}",
                size=12,
                color=ft.Colors.GREY_600,
                italic=True
            )

            results_items.append(
                ft.Column([
                    station_container,
                    system_text,
                    jumps_text,
                    ft.Container(height=5)
                ], spacing=2)
            )

        self.results_container.content = ft.Column(
            results_items,
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )
        self.results_container.visible = True

    def show_error(self, error_message):
        """Show error message"""
        self.results_container.content = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.ERROR, size=48, color=ft.Colors.RED),
                ft.Container(height=10),
                ft.Text(
                    "Optimization Failed",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.RED
                ),
                ft.Container(height=5),
                ft.Text(
                    error_message,
                    size=12,
                    color=ft.Colors.GREY_600
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20
        )
        self.results_container.visible = True

    async def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        await ft.Clipboard().set(text)

        # Show snackbar notification
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Copied: {text}"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
