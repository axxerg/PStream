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

content = response.text

print(content)

patterns = [
    r'https://[^"]+\.m3u8[^"]*',
    r'https:\/\/[^"]+\.m3u8[^"]*',
    r'src="([^"]+)"',
    r'file:\s*"([^"]+)"',
]

stream = None

for pattern in patterns:
    match = re.search(pattern, content)

    if match:
        stream = match.group(1) if match.lastindex else match.group(0)
        stream = stream.replace("\\/", "/")
        break

if stream:
    with open("atv/stream.txt", "w") as f:
        f.write(stream)

    print("FOUND:", stream)

else:
    with open("atv/debug.txt", "w") as f:
        f.write(content)

    print("No stream found")
