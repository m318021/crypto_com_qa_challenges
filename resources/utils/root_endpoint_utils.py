# utils/rest_config.py
import logging
from configparser import ConfigParser
from typing import Optional
from helpers.config_manager import CONFIGS
from helpers.project_paths import RUN_INI_PATH

# from your_module_where_get_config_is import get_config  # 改成實際匯入路徑

logger = logging.getLogger(__name__)


def get_rest_base(env: Optional[str] = None, run_ini_path: str = RUN_INI_PATH) -> str:
    """
    從 run.ini 的 [REST] 讀取 base URL。
    env: 'uat' 或 'prod'（大小寫不拘）。None 則交由呼叫端決定預設值。
    """
    cfg: Optional[ConfigParser] = CONFIGS["RUN_INI"]()
    if cfg is None or not cfg.has_section("REST"):
        raise RuntimeError(f"[REST] section not found in {run_ini_path}")

    # ConfigParser 會把 key 轉成小寫：'UAT' -> 'uat'
    options = dict(cfg.items("REST"))  # e.g. {'uat': 'https://...', 'prod': 'https://...'}

    if env is None:
        env_key = "prod"
    else:
        env_key = env.strip().lower()

    if env_key not in options:
        raise KeyError(f"Environment '{env}' not found in [REST]. Available: {list(options.keys())}")

    base = options[env_key].strip()
    if not base.endswith("/"):
        base += "/"
    return base
