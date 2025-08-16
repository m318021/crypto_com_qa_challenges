from pathlib import Path

# ----- Set project root directory -----
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ----- Files in root directory -----
RUN_INI_PATH = PROJECT_ROOT / "run.ini"

# ----- Config Files -----
CONFIG_FILES_DIR = PROJECT_ROOT / "config_files"

# JSON
JSON_DIR = CONFIG_FILES_DIR / "json"
TEST_DATA_REST_CANDLESTICK_PATH = JSON_DIR / "test_data_rest_candlestick.json"

# INI
INI_DIR = CONFIG_FILES_DIR / "ini"
RUN_INI_PATH = INI_DIR / "run.ini"

# ----- Generated Files -----
GENERATED_FILES_DIR = PROJECT_ROOT / "generated_files"

# ----- Helpers directory -----
HELPERS = PROJECT_ROOT / "helpers"

# Helpers / st1_setup_ini

# ----- Reports directory -----
REPORTS = PROJECT_ROOT / "reports"
ALLURE_RESULTS_PATH = REPORTS / "allure_results"

# ----- Resources directory -----
RESOURCES = PROJECT_ROOT / "resources"

# Subdirectories under Resources
CONFIGS = RESOURCES / "configs"
SETTINGS = CONFIGS / "settings"
PS1_FILES = CONFIGS / "ps1_files"
COMPONENTS = RESOURCES / "components"
FUNCTIONS = RESOURCES / "functions"
PAGES = RESOURCES / "pages"
SERVICES = RESOURCES / "services"
UTILS = RESOURCES / "utils"
