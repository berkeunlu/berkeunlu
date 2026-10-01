import base64
import os
import re
import sys
from html import escape
from urllib.parse import quote

import yaml

README = sys.argv[1] if len(sys.argv) > 1 else "README.md"
SRC = sys.argv[2] if len(sys.argv) > 2 else "toolbox.yaml"
LOGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "logos")
START, END = "<!-- TOOLBOX:START -->", "<!-- TOOLBOX:END -->"
LIGHT_BG = {"FCC624", "F7DF1E", "A8B9CC"}


def shield(item, default):
    label = quote(item["name"].replace("-", "--").replace("_", "__"), safe="")
    color = str(item.get("color", default))
    url = f"https://img.shields.io/badge/{label}-{color}?style=flat-square"
    if item.get("icon"):
        url += f"&logo={item['icon']}&logoColor={'black' if color.upper() in LIGHT_BG else 'white'}"
    elif item.get("logo"):
        data = base64.b64encode(open(os.path.join(LOGO_DIR, item["logo"] + ".png"), "rb").read()).decode()
        url += f"&logo=data:image/png;base64,{quote(data, safe='')}"
    return f'<img src="{url}" alt="{escape(item["name"])}">'


def build():
    blocks = []
    for cat in yaml.safe_load(open(SRC))["categories"]:
        items = cat.get("items") or []
        if items:
            blocks.append(f"<p><b>{escape(cat['title'])}</b><br>\n" + "\n".join(shield(i, str(cat.get("color", "30363d"))) for i in items) + "\n</p>")
    return "\n".join(blocks)


def main():
    text = open(README).read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit("toolbox markers missing in README")
    open(README, "w").write(pattern.sub(lambda _: f"{START}\n{build()}\n{END}", text))


main()
