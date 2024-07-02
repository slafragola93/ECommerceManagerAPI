class ECommerceApiService:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
#unserscore usato per indicare che il metodo è protetto e che non va usato fuori dalla classe

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def retrieve_live_price(self, product_id: int):
        url = f"{self.base_url}/products/{product_id}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()