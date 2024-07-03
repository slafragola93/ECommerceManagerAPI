import requests


class ECommerceApiService:
    def __init__(self,
                 api_key: str,
                 base_url: str,
                 formatted_output: str = "JSON"):
        self.api_key = api_key
        self.base_url = base_url
        self.formatted_output = formatted_output

    # unserscore usato per indicare che il metodo è protetto e che non va usato fuori dalla classe

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def retrieve_live_price(self,
                            product_id: int,
                            price_field_name: str = "wholesale_price")-> float:
        url = f"{self.base_url}/api/products/?ws_key={self.api_key}&filter[id]=[{product_id}]&display=[{price_field_name}]&output_format={self.formatted_output}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        price = response.json()["products"][0][price_field_name]
        return float(price)
