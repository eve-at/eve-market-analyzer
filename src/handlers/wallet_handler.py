"""Wallet transaction fetch + process — shared logic."""
from datetime import datetime
from src.auth.esi_api import ESIAPI
from src.database.models import (
    save_character, get_max_wallet_transaction_id,
    save_wallet_transactions, clear_character_profit_data,
    process_wallet_transactions, save_setting,
)

WALLET_CACHE_SECONDS = 3605
_ESI_PAGE_SIZE = 2500


def pull_wallet_transactions(character, log=None):
    """Fetch new wallet transactions from ESI and update profit tables.

    Saves ``wallet_last_pull_{character_id}`` setting on success so both
    WalletAutoSync and the manual button share the same timestamp.

    Args:
        character: dict with character data (access_token, refresh_token, …)
        log:       optional callable(str) for progress messages

    Returns:
        Updated character dict (token may have been refreshed).

    Raises:
        RuntimeError on unrecoverable errors (no refresh token, ESI failure).
    """
    def _log(msg):
        if log:
            log(msg)

    character_id = character['character_id']
    access_token = character.get('access_token')
    refresh_token = character.get('refresh_token')
    token_expiry = character.get('token_expiry')

    esi_api = ESIAPI()

    # Refresh token if needed
    if token_expiry and isinstance(token_expiry, str):
        try:
            token_expiry = datetime.fromisoformat(token_expiry)
        except ValueError:
            token_expiry = None
    if not access_token or not token_expiry or datetime.now() >= token_expiry:
        _log("Access token expired, refreshing...")
        if not refresh_token:
            raise RuntimeError("No refresh token. Please log in again.")
        token_data = esi_api.refresh_access_token(refresh_token)
        if not token_data:
            raise RuntimeError("Failed to refresh token. Please log in again.")
        access_token = token_data['access_token']
        save_character({
            'character_id': character_id,
            'character_name': character['character_name'],
            'access_token': access_token,
            'token_expiry': token_data['token_expiry'],
        })
        character = dict(character)
        character['access_token'] = access_token
        character['token_expiry'] = token_data['token_expiry']
        _log("Token refreshed.")

    # Determine import mode
    max_known_id = get_max_wallet_transaction_id(character_id)
    is_first_import = max_known_id is None

    if is_first_import:
        _log("First import - fetching full transaction history...")
    else:
        _log(f"Incremental import - fetching transactions newer than ID {max_known_id}...")

    all_new = []
    from_id = None

    while True:
        transactions = esi_api.get_character_wallet_transactions(character_id, access_token, from_id)

        if transactions is None:
            raise RuntimeError("Failed to fetch transactions from ESI.")

        if not transactions:
            _log("No more transactions returned.")
            break

        if is_first_import:
            all_new.extend(transactions)
            _log(f"Fetched {len(transactions)} transactions (total so far: {len(all_new)})")
        else:
            new_in_page = [t for t in transactions if t['transaction_id'] > max_known_id]
            all_new.extend(new_in_page)
            _log(f"Fetched {len(transactions)} from ESI, {len(new_in_page)} are new")
            if len(new_in_page) < len(transactions):
                break

        if len(transactions) < _ESI_PAGE_SIZE:
            break

        from_id = min(t['transaction_id'] for t in transactions)

    if all_new:
        _log(f"Saving {len(all_new)} new transactions to database...")
        inserted, skipped = save_wallet_transactions(character_id, all_new)
        _log(f"Saved: {inserted} new, {skipped} duplicates skipped")
    else:
        _log("No new transactions to save.")

    if is_first_import and all_new:
        _log("")
        _log("First import: rebuilding profit data from all wallet transactions...")
        _log("Clearing existing inventory and profit tables...")
        clear_character_profit_data(character_id)

    broker_fee_buy = float(character.get('broker_fee_buy', 3.00))
    broker_fee_sell = float(character.get('broker_fee_sell', 3.00))
    sales_tax = float(character.get('sales_tax', 7.50))

    _log("Processing transactions (FIFO profit calculation)...")
    stats = process_wallet_transactions(character_id, broker_fee_buy, broker_fee_sell, sales_tax)

    if stats:
        _log("=" * 50)
        _log("Processing complete!")
        _log(f"Buy transactions processed: {stats['buy_transactions_processed']}")
        _log(f"Sell transactions processed: {stats['sell_transactions_processed']}")
        _log(f"Items added to inventory: {stats['items_added_to_inventory']}")
        _log(f"Items sold: {stats['items_sold']}")
        if stats['items_sold_without_purchase'] > 0:
            _log(f"Items sold without purchase record: {stats['items_sold_without_purchase']} (profit = 0)")
    else:
        raise RuntimeError("Failed to process transactions.")

    # Persist pull timestamp so WalletAutoSync can calculate the next delay
    save_setting(f"wallet_last_pull_{character_id}", datetime.now().isoformat())

    return character
