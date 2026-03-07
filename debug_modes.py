#!/usr/bin/env python3
"""Debug scraper pour voir le texte exact des modes"""

from scrape_cookomix import scrape_recipe

url = "https://www.cookomix.com/recettes/quiche-poivrons-chorizo-thermomix/"
recipe = scrape_recipe(url)

print("=" * 80)
print(f"🔍 ANALYSER LES INSTRUCTIONS - {recipe.title}")
print("=" * 80)

for i, instruction in enumerate(recipe.instructions, 1):
    print(f"\n{i}. {instruction}")
    
    # Chercher les mots-clés des modes
    lower_instr = instruction.lower()
    if any(keyword in lower_instr for keyword in ['pétrin', 'turbo', 'mixage', 'réchauffer', 'rice cooker', 'mode']):
        print("   ⚠️  CONTIENT UN MODE!")
