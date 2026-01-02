"""File system event handler for market logs"""
import re
from pathlib import Path
from watchdog.events import FileSystemEventHandler


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
