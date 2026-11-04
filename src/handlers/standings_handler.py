"""Sync character standings and trade skills from ESI (used for broker fee and sales tax)"""
import csv
import io
import importlib
import requests
from src.auth.esi_api import ESIAPI
from src.database.models import (
    save_character,
    save_character_standings_and_skills,
    count_npc_corporations,
    save_npc_corporations_and_factions,
)
from src.handlers.wallet_handler import ensure_valid_access_token
from src.handlers.fees import sales_tax_percent, ACCOUNTING_SKILL_ID

_DEFAULT_NPC_CORPORATIONS_DF = 'https://www.fuzzwork.co.uk/dump/latest/csv/crpNPCCorporations.csv'
_DEFAULT_FACTIONS_DF = 'https://www.fuzzwork.co.uk/dump/latest/csv/chrFactions.csv'

PERMISSIONS_MESSAGE = "Log in again on EVE Online Account to grant new permissions (standings and skills)"


def _get_settings():
    """Reload and get settings from settings module"""
    import settings
    importlib.reload(settings)
    return settings


def _download_csv_rows(url):
    """Download a CSV file and return its rows as dicts"""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))


def load_npc_corporations(log=None):
    """Download NPC corporations and factions from Fuzzwork into the database"""
    settings = _get_settings()
    corporations_url = getattr(settings, 'NPC_CORPORATIONS_DF', _DEFAULT_NPC_CORPORATIONS_DF)
    factions_url = getattr(settings, 'FACTIONS_DF', _DEFAULT_FACTIONS_DF)

    if log:
        log("Downloading NPC corporations and factions...")
    corporations = [
        (int(r['corporationID']), r['corporationName'], int(r['factionID']) if r['factionID'] else None)
        for r in _download_csv_rows(corporations_url)
    ]
    factions = [(int(r['factionID']), r['factionName']) for r in _download_csv_rows(factions_url)]

    if not save_npc_corporations_and_factions(corporations, factions):
        raise RuntimeError("Failed to save NPC corporations")
    if log:
        log(f"Loaded {len(corporations)} NPC corporations and {len(factions)} factions")


def sync_standings_and_skills(character, log=None):
    """
    Fetch standings and skills from ESI, store them and update the character's sales tax

    Returns:
        Updated character dict.

    Raises:
        RuntimeError with a user-facing message on failure.
    """
    esi_api = ESIAPI()
    character = ensure_valid_access_token(character, esi_api, log)
    character_id = character['character_id']

    if log:
        log("Fetching standings...")
    standings, status = esi_api.get_character_standings(character_id, character['access_token'])
    if standings is None:
        raise RuntimeError(PERMISSIONS_MESSAGE if status in (401, 403) else f"Failed to fetch standings (HTTP {status})")

    if log:
        log("Fetching skills...")
    skills, status = esi_api.get_character_skills(character_id, character['access_token'])
    if skills is None:
        raise RuntimeError(PERMISSIONS_MESSAGE if status in (401, 403) else f"Failed to fetch skills (HTTP {status})")

    if not save_character_standings_and_skills(character_id, standings, skills):
        raise RuntimeError("Failed to save standings and skills")
    if log:
        log(f"Saved {len(standings)} standings and {len(skills)} skills")

    if count_npc_corporations() == 0:
        load_npc_corporations(log)

    accounting = next((s['active_skill_level'] for s in skills if s['skill_id'] == ACCOUNTING_SKILL_ID), 0)
    sales_tax = round(sales_tax_percent(accounting), 3)
    save_character({
        'character_id': character_id,
        'character_name': character['character_name'],
        'sales_tax': sales_tax,
    })
    character = dict(character)
    character['sales_tax'] = sales_tax
    if log:
        log(f"Sales tax set to {sales_tax}% (Accounting {accounting})")

    return character
