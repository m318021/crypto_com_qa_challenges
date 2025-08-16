from resources.services.api_client import APIClient


class RestAPI(APIClient):
    def __init__(self, base_url: str):
        """
        base_url ex: https://api.crypto.com/exchange/v1/
        """
        super().__init__(server=base_url)
        self.headers = {"Content-Type": "application/json"}

    def get_candlestick(self, params):
        return self.get("public/get-candlestick", headers=self.headers, params=params)

    def get_instruments(self):
        return self.get("public/get-instruments", headers=self.headers)
