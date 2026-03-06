#!/usr/bin/env python3
"""Scrape ingredients and instructions from Cookomix recipe pages.

Usage:
  python scrape_cookomix.py <url1> <url2> ...
  python scrape_cookomix.py --output recipes.json <url1> <url2>
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from typing import Any

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
INGREDIENT_HREF_PATTERN = re.compile(r"/recettes/ingredients/", re.IGNORECASE)
STEP_PATTERN = re.compile(r"^(\\d{1,3})\\s*(.+)$")


@dataclass
class RecipeData:
    url: str
    title: str
    ingredients: list[str]
    instructions: list[str]
    source: str


def normalize_spaces(text: str) -> str:
    """Collapse whitespace into a single space."""
    return re.sub(r"\\s+", " ", text).strip()


def iter_json_candidates(payload: Any) -> list[dict[str, Any]]:
    """Flatten possible JSON-LD shapes and return candidate dicts."""
    candidates: list[dict[str, Any]] = []

    if isinstance(payload, dict):
        if "@graph" in payload and isinstance(payload["@graph"], list):
            for item in payload["@graph"]:
                if isinstance(item, dict):
                    candidates.append(item)
        candidates.append(payload)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                candidates.extend(iter_json_candidates(item))

    return candidates


def is_recipe_type(type_field: Any) -> bool:
    """Return True when a JSON-LD @type indicates a recipe object."""
    if isinstance(type_field, str):
        return type_field.lower() == "recipe"
    if isinstance(type_field, list):
        return any(str(t).lower() == "recipe" for t in type_field)
    return False


def parse_recipe_instructions(value: Any) -> list[str]:
    """Parse recipeInstructions from JSON-LD in its common formats."""
    result: list[str] = []

    if isinstance(value, str):
        return [normalize_spaces(value)] if normalize_spaces(value) else []

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                txt = normalize_spaces(item)
                if txt:
                    result.append(txt)
                continue

            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    txt = normalize_spaces(item["text"])
                    if txt:
                        result.append(txt)
                    continue

                # Some pages nest steps inside itemListElement.
                nested = item.get("itemListElement")
                if isinstance(nested, list):
                    result.extend(parse_recipe_instructions(nested))

    return result


def extract_from_json_ld(soup: BeautifulSoup, url: str) -> RecipeData | None:
    """Extract recipe data from JSON-LD if present."""
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

    for script in scripts:
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for candidate in iter_json_candidates(payload):
            if not is_recipe_type(candidate.get("@type")):
                continue

            title = normalize_spaces(str(candidate.get("name", "")))
            ingredients = [
                normalize_spaces(str(i))
                for i in candidate.get("recipeIngredient", [])
                if normalize_spaces(str(i))
            ]
            instructions = parse_recipe_instructions(
                candidate.get("recipeInstructions", [])
            )

            if title and ingredients and instructions:
                return RecipeData(
                    url=url,
                    title=title,
                    ingredients=ingredients,
                    instructions=instructions,
                    source="json-ld",
                )

    return None


def extract_from_html(soup: BeautifulSoup, url: str) -> RecipeData:
    """Fallback extraction based on Cookomix page structure."""
    article = soup.find("article") or soup

    title_node = article.find("h1") or soup.find("h1")
    title = normalize_spaces(title_node.get_text(" ", strip=True)) if title_node else ""

    ingredients: list[str] = []
    seen_ingredients: set[str] = set()
    for li in article.find_all("li"):
        link = li.find("a", href=INGREDIENT_HREF_PATTERN)
        if not link:
            continue

        txt = normalize_spaces(li.get_text(" ", strip=True))
        if not txt:
            continue

        if txt not in seen_ingredients:
            seen_ingredients.add(txt)
            ingredients.append(txt)

    instructions: list[str] = []
    seen_steps: set[str] = set()

    # Cookomix often renders steps as lines like "1Prechauffer...".
    for node in article.find_all(["p", "li", "div"]):
        txt = normalize_spaces(node.get_text(" ", strip=True))
        if len(txt) < 10:
            continue

        match = STEP_PATTERN.match(txt)
        if not match:
            continue

        step_number = match.group(1)
        step_text = normalize_spaces(match.group(2))

        # Filter obvious non-step noise.
        if "notes" in step_text.lower():
            continue
        if "facebook" in step_text.lower() or "tweet" in step_text.lower():
            continue

        line = f"{step_number}. {step_text}"
        if line not in seen_steps:
            seen_steps.add(line)
            instructions.append(line)

    return RecipeData(
        url=url,
        title=title,
        ingredients=ingredients,
        instructions=instructions,
        source="html",
    )


def scrape_recipe(url: str, timeout: int = 25) -> RecipeData:
    """Scrape one Cookomix recipe page."""
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    structured = extract_from_json_ld(soup, url)
    if structured:
        return structured

    return extract_from_html(soup, url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape ingredients and instructions from Cookomix recipe pages"
    )
    parser.add_argument("urls", nargs="+", help="Cookomix recipe URL(s)")
    parser.add_argument(
        "--output",
        help="Optional path to write JSON output (default: print to stdout)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    all_recipes: list[dict[str, Any]] = []
    for url in args.urls:
        recipe = scrape_recipe(url)
        all_recipes.append(asdict(recipe))

    output_text = json.dumps(all_recipes, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
            f.write("\n")
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
