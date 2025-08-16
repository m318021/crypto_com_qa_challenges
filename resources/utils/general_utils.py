import json
import logging

logger = logging.getLogger(__name__)


class GeneralUtils:
    """Handles JSON, YAML, and time processing"""

    @staticmethod
    def pretty_print_json(json_obj, mode="info") -> None:
        """Format and print JSON data"""
        json_parser = json.dumps(json_obj, indent=4)
        if mode.lower() == "info":
            logger.info("\n" + json_parser)
        elif mode.lower() == "debug":
            logger.debug("\n" + json_parser)
        else:
            print("\n" + json_parser)
