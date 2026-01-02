"""Autocomplete field UI component"""
import flet as ft
from .suggestion_item import SuggestionItem


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
