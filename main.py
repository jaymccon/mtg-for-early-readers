import json
import re
from pathlib import Path
import urllib.request
import shutil
from sys import argv
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

character_count = 50
word_length = 8
max_cost = 3.0
format = "pioneer"

price_url = "https://mtgjson.com/api/v5/AllPrices.json"
price_file = Path("AllPrices.json")
card_url = "https://mtgjson.com/api/v5/AllPrintings.json"
card_file = Path("AllPrintings.json")
filtered_cards_file = Path("filtered_cards.json")

md_header = """
# Magic: The Gathering cards suitable for early readers.

> NOTE: Magic: The Gathering is rated for ages 13+. While this list aims to 
provide a list of cards that are easy to read for early readers, it does not 
filter out any potentially violent, gory or otherwise mature content in cards. 
If you are under 13 you should seek consent from a parent/guardian. 


"""
color_mapping = {"B": "Black", "U":"Blue", "G": "Green", "R": "Red", "W": "White"}

# manually created list of cards that could be frigtening, gory or somehow 
# innapropriate for small children. Most of this list is black cards
innapropriate_cards = [
    "Liturgy of Blood",
    "Undead Minotaur",
    "Assasinate",
    "Zombie Goliath",
    "Scathe Zombies",
    "Bog Rats",
    "Murder",
    "Human Frailty",
    "Hand or Death",
    "Kelinore Bat",
    "Warpath Ghoul",
    "Insatiable Harpy",
    "Mournful Zombie",
    "Hunted Ghoul",
    "Succumb to Temptation",
    "Carrion Screecher",
    "Azure Mage",
    "Hill Giant"
]
def download_file(url, path):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla'})) as response, open(path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)


def is_easy_to_read(card):
    if not card.get('text'):
        return True
    if len(card['text']) > character_count:
        return False
    for word in re.sub(r'[^0-9a-zA-Z]+', ' ', card['text']).split(' '):
        if len(word) > word_length:
            return False
    return True

def get_price(uuid, prices):
    prices = prices.get(uuid, {}).get('paper',{}).get('tcgplayer',{}).get('retail',{}).get('normal',{})
    if not prices:
        return None
    return prices[sorted(prices)[-1]]


def only_cheapest_printings(cards):
    cheapest_cards = {}
    for card_name in cards:
        cheapest = cards[card_name][0]
        if len(cards[card_name]) > 1:
            for card in cards[card_name]:
                if card['price'] < cheapest['price']:
                    cheapest = card
        cheapest_cards[card['name']] = cheapest
    return cheapest_cards
    

def download_data_sets():
    print(f"downloading {card_url}...")
    download_file(card_url, card_file)
    print(f"downloading {price_url}...")
    download_file(price_url, price_file)


def filter_data_sets():
    if not card_file.exists() or not price_file.exists():
        download_data_sets()

    with open(price_file) as fh:
        print("loading prices...")
        prices_raw = json.loads(fh.read())['data']

    with open(card_file) as fh:
        cards_raw = json.loads(fh.read())['data']
        print("loading cards...")

    cards = {}    
    print("filtering suitable cards...")
    for set_name in cards_raw:
        for card in cards_raw[set_name]['cards']:
            del card['foreignData']
            # English cards
            if card.get('language') != 'English':
                continue
            # Available in paper format
            if 'paper' not in card.get("availability", []):
                continue
            # add empty text is there is none
            if card.get('text') is None:
                card['text'] = ""
            # get price
            price = get_price(card['uuid'], prices_raw)
            # must be purchasable
            if not price:
                continue
            # Within price limit
            if price > max_cost:
                continue
            card['price'] = price
            # Easy to read
            if not is_easy_to_read(card):
                continue
            # Add 0 mana cost if there is none
            if not card.get('manaCost'):
                card['manaCost'] = 0
            # Not a land
            if "Land" in card.get('types', []):
                continue
            # Single sided cards
            if card.get('layout') == 'split':
                continue
            # No adventure cards
            if card.get('layout') == 'adventure':
                continue
            # Only cards with multiverseIds
            if not card.get('identifiers', {}).get('multiverseId'):
                continue
            # No innapropriate art
            if card['name'] in innapropriate_cards:
                continue
            # Only cards legal in selected format
            if card.get("legalities", {}).get(format, "") != "Legal":
                continue
            # Cards without // in the name
            if ' // ' in card['name']:
                continue
            if not cards.get(card['name']):
                cards[card['name']] = []
            cards[card['name']].append(card)
    del cards_raw
    del prices_raw

    print("filtering cheapest printings...")
    cards = only_cheapest_printings(cards)
    with open(str(filtered_cards_file), "w") as fp:
        json.dump(cards, fp)


def filter_colors(colors, cards):
    filtered = {}
    for name, card in cards.items():
        if colors == card['colors']:
            filtered[name] = card
    return filtered


def main():
    if len(argv) < 2:
        if not filtered_cards_file.exists():
            filter_data_sets()
        with open(str(filtered_cards_file)) as fp:
            cards = json.load(fp)
        for name, card in cards.items():
            print(f"{card.get('setCode')} :: {card['type']} :: {name} :: ${card.get('price')} :: {card['manaCost']} :: {card['text']}")
    elif argv[1] == 'download':
        download_data_sets()
        return
    if argv[1] == 'filter':
        filter_data_sets()
        return
    if not filtered_cards_file.exists():
        filter_data_sets()
    with open(str(filtered_cards_file)) as fp:
        cards = json.load(fp)
    if argv[1] == 'mass-entry':
        for name, card in cards.items():
            print(f"4 {name}")
        return
    if argv[1] == 'gallery':
        md_content = md_header + "\n\n"
        for c in [["B"],["U"],["G"],["R"],["W"]]:
            md_content += f"\n## {color_mapping[c[0]]}\n\n"
            filtered = filter_colors(c, cards)
            for name, card in filtered.items():
                mv_id = card.get('identifiers', {}).get('multiverseId', '')
                mv_url = f"https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid={card.get('identifiers', {}).get('multiverseId', '')}&type=card"
                image_path = f"images/{mv_id}.jfif"
                if not Path(image_path).exists():
                    download_file(mv_url, image_path)
                md_content += f'<a href="{card.get("purchaseUrls", {}).get("tcgplayer")}"><img src="{image_path}" alt="{name}" title="${round(card["price"], 2)}" width="223" /></a> '
        print(md_content)
        return

if __name__ == '__main__':
    main()
