from enum import Enum
import random

class Suit(str, Enum):
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"
    SPADES = "S"

RANKS = ["A", "10", "K", "Q", "J", "9", "8", "7"]

def new_deck():
    return [{"suit": s, "rank": r} for s in Suit for r in RANKS]

def deal():
    deck = new_deck()
    random.shuffle(deck)

    hands = {
        "player": deck[:5],
        "opponent": deck[5:10],
    }

    trump_card = deck[10]
    talon = deck[11:]

    return {
        "hands": hands,
        "trump": trump_card,
        "talon_count": len(talon),
    }

