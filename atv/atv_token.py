import requests
import re

url = "https://www.atvavrupa.tv/ajax/streaming"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.atvavrupa.tv/canli-yayin",
    "X-Requested-With": "XMLHttpRequest"
}

response = requests.get(
    url,
    headers=headers,
    params={
        "menuType": "CANLIYAYIN"
    }
)

data = response.text

match = re.search(r'https://[^"]+\.m3u8[^"]*', data)

if match:
    stream = match.group(0)

    with open("atv/stream.txt", "w") as f:
        f.write(stream)

    print(stream)

else:
    print(data)
    raise Exception("No m3u8 found")
