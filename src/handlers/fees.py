"""Market fee calculations for NPC stations (https://wiki.eveuniversity.org/Trading)"""

BROKER_RELATIONS_SKILL_ID = 3446
ADVANCED_BROKER_RELATIONS_SKILL_ID = 16597
ACCOUNTING_SKILL_ID = 16622

TRADE_SKILL_IDS = (BROKER_RELATIONS_SKILL_ID, ADVANCED_BROKER_RELATIONS_SKILL_ID, ACCOUNTING_SKILL_ID)

MIN_BROKER_FEE_ISK = 100


def broker_fee_percent(broker_relations, faction_standing, corp_standing):
    """
    Broker fee for placing an order in an NPC station, %

    Standings are base (unmodified) standings of the character towards the
    station owner corporation and its faction.
    """
    fee = 3.0 - 0.3 * broker_relations - 0.03 * (faction_standing or 0) - 0.02 * (corp_standing or 0)
    return max(fee, 0.0)


def sales_tax_percent(accounting):
    """Sales tax, %"""
    return 7.5 * (1 - 0.11 * accounting)


def relist_rate(broker_fee_pct, advanced_broker_relations):
    """
    Fraction of the new order value paid when lowering the price of an order once

    Raising the price additionally costs the full broker fee on the value increase,
    which is not relevant for undercutting.
    """
    return (1 - (0.5 + 0.06 * advanced_broker_relations)) * broker_fee_pct / 100.0


def get_trade_skills(character_id):
    """
    Trade skill levels synced from ESI

    Returns:
    tuple ({skill_id: level}, fetched_at) - fetched_at is None if never synced
    """
    from src.database.models import get_character_skill_levels
    return get_character_skill_levels(character_id, TRADE_SKILL_IDS)


def get_hub_broker_fee(character_id, corporation_id, fallback_percent):
    """
    Broker fee for a hub station owned by corporation_id, from synced standings and skills

    Returns:
    dict with fee_percent and source ('esi' or 'manual'); for 'esi' also
    broker_relations, corp_name, corp_standing, faction_name, faction_standing
    """
    from src.database.models import get_corporation_standings

    manual = {'fee_percent': float(fallback_percent), 'source': 'manual'}
    if not character_id or not corporation_id:
        return manual

    levels, fetched_at = get_trade_skills(character_id)
    standings = get_corporation_standings(character_id, corporation_id)
    if not fetched_at or not standings:
        return manual

    broker_relations = levels[BROKER_RELATIONS_SKILL_ID]
    return {
        'fee_percent': broker_fee_percent(broker_relations, standings['faction_standing'], standings['corp_standing']),
        'source': 'esi',
        'broker_relations': broker_relations,
        'corp_name': standings['corp_name'],
        'corp_standing': standings['corp_standing'],
        'faction_name': standings['faction_name'],
        'faction_standing': standings['faction_standing'],
    }
