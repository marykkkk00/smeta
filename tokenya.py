

import requests

YANDEX_TOKEN = "y0__xCL-arKBBjX7zkg6tWlnRSb7--t7VDUxs3VlnzPEAHmXD2fOQ"
headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
response = requests.get("https://cloud-api.yandex.net/v1/disk", headers=headers)
print(response.status_code, response.json())










