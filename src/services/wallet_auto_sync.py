"""Automatic wallet transaction sync service."""
import threading
from datetime import datetime, timedelta
from src.database.models import get_setting
from src.handlers.wallet_handler import pull_wallet_transactions, WALLET_CACHE_SECONDS


class WalletAutoSync:
    """Periodically pulls wallet transactions in the background.

    Usage::
        sync = WalletAutoSync()
        sync.start(character, page)          # call once on login / app start
        sync.set_status_callback(fn)         # call after every AppBar rebuild
        sync.stop()                          # call on logout
    """

    def __init__(self):
        self._timer = None
        self._character = None
        self._page = None
        self._status_callback = None
        self._running = False
        self._current_status = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_status_callback(self, callback):
        """Register (or replace) the callable that receives status text.

        Should be called after every AppBar rebuild so the new widget
        receives updates. Immediately applies the last known status.
        """
        self._status_callback = callback
        if self._running and self._current_status:
            callback(self._current_status)

    def start(self, character, page):
        """Start auto-sync for *character*. Safe to call multiple times."""
        self.stop()
        self._character = character
        self._page = page
        self._running = True
        self._schedule_or_run_now()

    def stop(self):
        """Cancel any pending timer and clear status."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._set_status("")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _schedule_or_run_now(self):
        """Check last pull timestamp and either run immediately or delay."""
        delay = self._seconds_until_next_pull()
        if delay > 1:
            next_time = datetime.now() + timedelta(seconds=delay)
            self._set_status(f"Next update at {next_time.strftime('%H:%M')}")
            self._arm_timer(delay)
        else:
            threading.Thread(target=self._run_pull, daemon=True).start()

    def _seconds_until_next_pull(self):
        """Return how many seconds until the next pull is due (0 = now)."""
        character_id = self._character['character_id']
        last_pull_str = get_setting(f"wallet_last_pull_{character_id}")
        if last_pull_str:
            try:
                last_pull = datetime.fromisoformat(last_pull_str)
                elapsed = (datetime.now() - last_pull).total_seconds()
                if elapsed < WALLET_CACHE_SECONDS:
                    return WALLET_CACHE_SECONDS - elapsed
            except ValueError:
                pass
        return 0

    def _arm_timer(self, delay):
        self._timer = threading.Timer(delay, self._run_pull)
        self._timer.daemon = True
        self._timer.start()

    def _run_pull(self):
        if not self._running:
            return

        # A manual pull from CharacterScreen may have happened while the
        # timer was counting down — check the timestamp before doing work.
        delay = self._seconds_until_next_pull()
        if delay > 1:
            next_time = datetime.now() + timedelta(seconds=delay)
            self._set_status(f"Next update at {next_time.strftime('%H:%M')}")
            self._arm_timer(delay)
            return

        self._set_status("Updating...")
        try:
            updated = pull_wallet_transactions(self._character)
            self._character = updated
        except Exception as e:
            print(f"WalletAutoSync: pull failed — {e}")

        if not self._running:
            return

        next_time = datetime.now() + timedelta(seconds=WALLET_CACHE_SECONDS)
        self._set_status(f"Next update at {next_time.strftime('%H:%M')}")
        self._arm_timer(WALLET_CACHE_SECONDS)

    def _set_status(self, text):
        self._current_status = text
        if self._status_callback and self._page:
            async def _update():
                self._status_callback(text)
                self._page.update()
            self._page.run_task(_update)
