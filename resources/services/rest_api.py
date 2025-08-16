import requests
from resources.services.api_client import APIClient


class RestAPI(APIClient):
    def __init__(self, server: str, **kwargs):
        super().__init__(server=server, **kwargs)

    def get_candlestick(self, params: dict) -> requests.Response:
        return self.get("public/get-candlestick", params=params)

    def get_instruments(self) -> requests.Response:
        return self.get("public/get-instruments")
