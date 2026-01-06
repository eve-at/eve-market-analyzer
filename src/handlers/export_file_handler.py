"""File system event handler for export files"""
import re
from pathlib import Path
from watchdog.events import FileSystemEventHandler


class ExportFileHandler(FileSystemEventHandler):
    """File system event handler for exported market files"""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        # Pattern: <region_name>-<type_name>-<datetime>.txt
        # Use non-greedy match and extract everything between first and last dash before datetime
        self.pattern = re.compile(r'^(.+?)-(.+)-(\d{4}\.\d{2}\.\d{2} \d{6})\.txt$')

    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return

        filename = Path(event.src_path).name
        match = self.pattern.match(filename)

        if match:
            region_name = match.group(1)
            # Item name is everything between first dash and last dash (before datetime)
            item_name = match.group(2)
            print(f"New export file detected: {region_name} - {item_name}")
            self.callback(event.src_path, region_name, item_name)
