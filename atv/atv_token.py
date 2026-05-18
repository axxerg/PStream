import requests
import re

js_url = "https://i.tmgrup.com.tr/aav/site/v1/j/live-broadcast.js?v=17809"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.atvavrupa.tv/canli-yayin"
}

response = requests.get(js_url, headers=headers)

content = response.text

print(content[:5000])

patterns = [
    r'https://[^"\']+\.m3u8[^"\']*',
    r'https:\/\/[^"\']+\.m3u8[^"\']*',
]

stream = None

for pattern in patterns:
    match = re.search(pattern, content)

    if match:
        stream = match.group(0)
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
