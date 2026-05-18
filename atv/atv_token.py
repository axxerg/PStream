import requests
import re

url = "https://www.atvavrupa.tv/canli-yayin"

headers = {
    "User-Agent": "Mozilla/5.0"
}

html = requests.get(url, headers=headers).text

scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)

output = []

for script in scripts:
    if script.startswith("/"):
        script = "https://www.atvavrupa.tv" + script

    try:
        r = requests.get(script, headers=headers, timeout=10)

        content = r.text

        if "m3u8" in content or "jwplayer" in content or "playlist" in content:
            output.append("\n==== SCRIPT ====\n")
            output.append(script)
            output.append("\n")
            output.append(content[:10000])

    except Exception as e:
        output.append(str(e))

with open("atv/debug.txt", "w") as f:
    f.write("\n".join(output))

print("DONE")
