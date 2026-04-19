from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

import requests

DAILYMED_BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

# DailyMed SPL XML namespace
SPL_NS = "urn:hl7-org:v3"


def search_drug(drug_name: str) -> Optional[str]:
    """Return the first set_id for drug_name from the DailyMed search API."""
    url = f"{DAILYMED_BASE}/spls.json"
    params = {"drug_name": drug_name, "pagesize": 1}
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = data.get("data", [])
    if not results:
        return None
    return results[0].get("setid")


def fetch_leaflet_text(set_id: str) -> str:
    """Download the SPL XML for set_id and extract plain text from section narratives."""
    url = f"{DAILYMED_BASE}/spls/{set_id}.xml"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"v3": SPL_NS}

    text_parts: list[str] = []
    for section in root.findall(".//v3:section", ns):
        title_el = section.find("v3:title", ns)
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        paragraphs: list[str] = []
        for text_el in section.findall(".//v3:text", ns):
            raw = "".join(text_el.itertext()).strip()
            if raw:
                paragraphs.append(raw)

        if title or paragraphs:
            block = f"### {title}\n" + "\n".join(paragraphs) if title else "\n".join(paragraphs)
            text_parts.append(block)

    return "\n\n".join(text_parts)


def get_drug_leaflet(drug_name: str) -> str:
    """Convenience wrapper: search for drug_name and return its leaflet text."""
    set_id = search_drug(drug_name)
    if set_id is None:
        raise ValueError(f"No DailyMed entry found for '{drug_name}'")
    return fetch_leaflet_text(set_id)
