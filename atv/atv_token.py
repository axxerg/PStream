import requests
import re

url = "https://www.atvavrupa.tv/canli-yayin"

headers = {
    "User-Agent": "Mozilla/5.0"
}

html = requests.get(url, headers=headers).text

match = re.search(r'https://.*?\.m3u8\?st=.*?&e=\d+', html)

if match:
    stream = match.group(0)

    with open("atv/stream.txt", "w") as f:
        f.write(stream)

    print(stream)

else:
    print("No stream found")
