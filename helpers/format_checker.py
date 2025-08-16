import os
import logging
import argparse
import subprocess

# Configure logging format
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Directories to be ignored
SKIP_FOLDERS = {"venv", ".git", ".tox", ".vscode", ".pytest_cache"}

# Maximum line length for flake8 and black
MAX_LINE_LENGTH = 148


def get_target_folders() -> list:
    """Retrieve target folders for format checking"""
    return sorted([item for item in os.listdir() if os.path.isdir(item) and item not in SKIP_FOLDERS])


def run_command(command: list, allow_fail: bool = False):
    """Execute a shell command"""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logging.warning(f"Command failed: {' '.join(command)}")
            logging.warning(result.stdout + result.stderr)
            if not allow_fail:
                exit(1)
        else:
            logging.info(result.stdout)
    except Exception as e:
        logging.error(f"Error executing command: {e}")
        exit(1)


def format_check(fix: bool = False):
    """Run format checks using Flake8 and Black"""
    folders = get_target_folders()
    if not folders:
        logging.warning("No folders found for format checking. Please check your project structure.")
        return

    logging.info(f"Target folders for format checking: {folders}")

    cmd_flake = ["flake8", "--count", f"--max-line-length={MAX_LINE_LENGTH}", "--ignore=W503"] + folders
    cmd_black = ["black", f"--line-length={MAX_LINE_LENGTH}"] + folders

    if fix:
        logging.info("Running Black auto-formatting...")
        run_command(cmd_black)

    logging.info("Running Flake8 format check...")
    run_command(cmd_flake, allow_fail=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code format checker (Flake8 + Black)")
    parser.add_argument("--fix", action="store_true", help="Automatically fix formatting issues")
    args = parser.parse_args()

    format_check(fix=True)
