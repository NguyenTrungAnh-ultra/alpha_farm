import os
from bs4 import BeautifulSoup

html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "details.html")

with open(html_path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

for word in ["Overview", "Performance", "Analysis"]:
    print(f"\n--- Searching for: {word} ---")
    elements = soup.find_all(string=lambda text: text and word in text)
    for el in elements:
        parent = el.parent
        print(f"Tag: {parent.name}, Attributes: {parent.attrs}, Text: {parent.get_text().strip()}")
        # Print parent's parent
        if parent.parent:
            print(f"  Parent Tag: {parent.parent.name}, Attributes: {parent.parent.attrs}")
