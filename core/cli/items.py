"""handle_items_*: CLI items subcommand stubs (plan 09-03 fills the bodies).

Imports only sys and BotService -- never models/orchestrator/registry (MOD-02).
"""

import sys

from core.service import BotService


def handle_items_list(args, svc: BotService) -> int:
    """Print a text table of all tracked items. Stub -- plan 09-03 implements."""
    return 0


def handle_items_add(args, svc: BotService) -> int:
    """Add an item via BotService.add_item. Stub -- plan 09-03 implements."""
    return 0


def handle_items_remove(args, svc: BotService) -> int:
    """Remove an item by URL via BotService.remove_item. Stub -- plan 09-03."""
    return 0
