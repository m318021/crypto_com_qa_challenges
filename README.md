# Crypto.com QA Challenges

This repository provides automated test cases for **Crypto.com Exchange APIs**,  
covering both **REST** and **WebSocket** endpoints.  

The goal is to validate the correctness, stability, and error handling of  
candlestick data (`public/get-candlestick`) and order book subscriptions (`book` channel).  

---

## Features

- **REST API Testing**
  - Validate candlestick data structure (OHLCV format).
  - Verify timeframe normalization and data alignment.
  - Test parameter boundaries (`count`, `start_ts`, `end_ts`).
  - Include negative test cases (invalid timeframe, count=0, invalid instrument, etc.).

- **WebSocket API Testing**
  - Verify connection to `market` WebSocket endpoint.
  - Subscribe/unsubscribe to order book channels.
  - Validate snapshot and delta update consistency.
  - Handle heartbeat/respond-heartbeat mechanism.

- **Configurable Environment**
  - Support both `prod` and `uat` environments.
  - Command-line options for overriding instrument, depth, server URL, and TLS settings.
  - Configurable via `run.ini` or CLI flags.

---

## Project Structure
```
crypto_com_qa_challenges/
├── config_files/                           # Project configuration files
│   ├── ini/                                # Default ini files
│   │   └── run.ini                         # Config for env / instrument / depth / etc.
│   └── json/                               # Default JSON test data
│       └── test_data_rest_candlestick.json # REST candlestick test parameters (JSON format)
│
├── helpers/                                # Shared utilities and config loaders
│   ├── config_manager.py                   # Load configs (ini / json / ...)
│   ├── format_check.py                     # Run Black & Flake8 to check syntax/format
│   ├── project_path.py                     # Centralized file & folder path management
│   └── test_data_loader.py                 # Provide VALID_CASES / TIME_RANGE_CASES
│
├── logs/                                   # Pytest logs (ignored by .gitignore)
├── reports/                                # Allure reports (ignored by .gitignore)
│
├── resources/                              # API services & utility modules
│   ├── services/                           # API-related services
│   │   ├── api_client.py                   # Base REST API client (retry & error handling)
│   │   ├── rest_api.py                     # REST API wrapper (candlestick, instruments)
│   │   └── ws_client.py                    # Async WebSocket client
│   └── utils/                              # Common utility modules
│       ├── candlestick_utils.py            # Utilities for candlestick validation
│       ├── general_utils.py                # Pretty-print & helper functions
│       └── ws_book_utils.py                # WebSocket utilities (book snapshot/delta handling)
│
├── tests/                                  # Test cases
│   ├── conftest.py                         # Pytest shared config & fixtures
│   ├── test_rest_candlestick.py            # REST candlestick tests (positive & negative)
│   └── test_ws_book.py                     # WebSocket tests (book snapshot & delta)
│
├── README.md                               # Project introduction
└── pytest.ini                              # Pytest configuration (markers, options, logging)
```
---

## Installation


# Clone repository
```
git clone https://github.com/yourname/crypto_com_qa_challenges.git
cd crypto_com_qa_challenges
```

# Install dependencies
```
pip install -r requirements.txt
```
### Updating library versions in `requirements.txt`
```
pip install pip-review
pip-review --auto
pip freeze > requirements.txt
```
## Execution

This project uses **pytest** for test execution.  
You can run either **REST API tests** or **WebSocket tests**,  
and pass parameters through **CLI options** or **run.ini**.

---

### CLI Options

| Option           | Description                                                                 | Default         | Example                                    |
|------------------|-----------------------------------------------------------------------------|-----------------|--------------------------------------------|
| `--env`          | Target environment: `prod` or `uat`                                         | `prod`          | `--env=uat`                                |
| `--instrument`   | Instrument/symbol name                                                      | `BTCUSD-PERP`   | `--instrument=ETHUSD-PERP`                 |
| `--depth`        | Order book depth for WS subscription                                        | `50`            | `--depth=10`                               |
| `--book-type`    | Order book subscription type: `SNAPSHOT` or `SNAPSHOT_AND_UPDATE`           | `SNAPSHOT_AND_UPDATE` | `--book-type=SNAPSHOT`             |
| `--book-freq`    | WebSocket delta frequency in ms                                             | `10`            | `--book-freq=100`                          |
| `--server`       | Override REST/WS base URL. Use `http(s)://` for REST, `ws(s)://` for WS     | *none*          | `--server=https://uat-api.3ona.co/exchange/v1/`<br>`--server=wss://uat-stream.3ona.co/exchange/v1/market` |
| `--cafile`       | Path to custom CA bundle (PEM)                                              | `certifi` bundle | `--cafile=/path/to/custom-ca.pem`          |
| `--insecure`     | Disable TLS verification (⚠️ do not use in prod)                            | `False`         | `--insecure`                               |

---

### Run All Tests
```
pytest -v
```

### Run REST Tests
```
pytest tests/test_rest_candlestick.py -v
```

Examples:
# Use prod (default)
```
pytest tests/test_rest_candlestick.py -v
```

# Use UAT environment
```
pytest tests/test_rest_candlestick.py -v --env=uat
```

# Change instrument
```
pytest tests/test_rest_candlestick.py -v --instrument=ETHUSD-PERP
```

### Run WebSocket Tests
```
pytest tests/test_ws_book.py -v
```

Examples:
# Subscribe to BTCUSD-PERP book.50 (default)
```
pytest tests/test_ws_book.py -v
```

# UAT environment, ETHUSD-PERP, depth=10
```
pytest tests/test_ws_book.py -v --env=uat --instrument=ETHUSD-PERP --depth=10
```

# Force SNAPSHOT only
```
pytest tests/test_ws_book.py -v --book-type=SNAPSHOT
```
# Set book update frequency to 100ms
```
pytest tests/test_ws_book.py -v --book-freq=100
```