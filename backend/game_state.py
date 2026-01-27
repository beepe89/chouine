import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

RANKS = ["A", "10", "K", "Q", "J", "9", "8", "7"]
SUITS = ["H", "D", "C", "S"]

# force (Chouine): A,10,K,Q,J,9,8,7
RANK_STRENGTH = {r: i for i, r in enumerate(RANKS)}  # 0 strongest

def new_deck() -> List[Dict[str, str]]:
    return [{"suit": s, "rank": r} for s in SUITS for r in RANKS]

def card_eq(a: Dict[str, str], b: Dict[str, str]) -> bool:
    return a["suit"] == b["suit"] and a["rank"] == b["rank"]

def draw(talon: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    return talon.pop(0) if talon else None


def compare_same_suit(a: Dict[str, str], b: Dict[str, str]) -> int:
    """Return -1 if a stronger, +1 if b stronger, 0 if equal (shouldn't happen)."""
    return -1 if RANK_STRENGTH[a["rank"]] < RANK_STRENGTH[b["rank"]] else 1

def trick_winner(
    lead: Dict[str, str],
    reply: Dict[str, str],
    trump_suit: str,
    talon_not_empty: bool,
) -> int:
    """
    Returns 0 if leader wins, 1 if follower wins.
    Rules (simplified but correct for this phase):
    - If follower plays trump and lead is not trump => follower wins (cut).
    - If both same suit => highest wins by chouine order.
    - If follower doesn't follow suit while talon_not_empty => leader wins (no obligation).
    - If talon empty, we'll enforce follow/cut later (next step).
    """
    lead_is_trump = lead["suit"] == trump_suit
    reply_is_trump = reply["suit"] == trump_suit

    if reply_is_trump and not lead_is_trump:
        return 1
    if lead_is_trump and not reply_is_trump:
        return 0

    if reply["suit"] == lead["suit"]:
        return 0 if compare_same_suit(lead, reply) == -1 else 1

    # different suits
    if talon_not_empty:
        return 0  # no obligation to follow => leader keeps trick unless cut already handled
    else:
        # we'll enforce obligations in next step; for now assume illegal never happens
        return 0

@dataclass
class Game:
    game_id: str
    trump: Dict[str, str]
    trump_suit: str
    talon: List[Dict[str, str]]
    player_hand: List[Dict[str, str]]
    opponent_hand: List[Dict[str, str]]
    leader: int  # 0 player leads, 1 opponent leads

    current_lead: Optional[Dict[str, str]] = None
    current_lead_by: Optional[str] = None  # "player" or "opponent"
    turnup_in_stock: bool = True

    last_trick: Optional[Dict[str, Any]] = None


def new_game(game_id: str) -> Game:
    deck = new_deck()
    random.shuffle(deck)

    player = deck[:5]
    opp = deck[5:10]
    trump = deck[10]
    talon = deck[11:]

    return Game(
        game_id=game_id,
        trump=trump,
        trump_suit=trump["suit"],
        talon=talon,
        player_hand=player,
        opponent_hand=opp,
        leader=0,  # player starts for MVP
    )

def opponent_choose_card(game: Game, lead_card: Optional[Dict[str, str]]) -> Dict[str, str]:
    if not game.opponent_hand:
        raise ValueError("opponent has no cards")
    hand = game.opponent_hand
    talon_not_empty = len(game.talon) > 0

    # Opponent leads: play random for MVP
    if lead_card is None:
        return random.choice(hand)

    lead_suit = lead_card["suit"]
    trump = game.trump_suit

    # WITH TALON: no obligation. Keep it a bit "human".
    if talon_not_empty:
        same = [c for c in hand if c["suit"] == lead_suit]
        if same and random.random() < 0.5:
            return random.choice(same)
        trumps = [c for c in hand if c["suit"] == trump]
        if trumps and random.random() < 0.2:
            return random.choice(trumps)
        return random.choice(hand)

    # NO TALON: obligations
    if has_suit(hand, lead_suit):
        # must follow suit
        candidates = [c for c in hand if c["suit"] == lead_suit]
        return random.choice(candidates)

    # can't follow => must trump if possible
    if has_trump(hand, trump):
        trumps = [c for c in hand if c["suit"] == trump]

        # if lead is trump, must overtrump if possible
        if lead_suit == trump and can_overtrump(hand, trump, lead_card):
            stronger = [c for c in trumps if RANK_STRENGTH[c["rank"]] < RANK_STRENGTH[lead_card["rank"]]]
            return random.choice(stronger)

        # otherwise play any trump (could be improved later)
        return random.choice(trumps)

    # no suit, no trump => discard anything
    return random.choice(hand)


def remove_card(hand: List[Dict[str, str]], card: Dict[str, str]) -> None:
    for i, c in enumerate(hand):
        if card_eq(c, card):
            hand.pop(i)
            return
    raise ValueError("Card not in hand")

def has_suit(hand, suit: str) -> bool:
    return any(c["suit"] == suit for c in hand)

def has_trump(hand, trump_suit: str) -> bool:
    return has_suit(hand, trump_suit)

def strongest_of_suit(cards, suit: str):
    suited = [c for c in cards if c["suit"] == suit]
    if not suited:
        return None
    # smaller index in RANK_STRENGTH is stronger
    return sorted(suited, key=lambda c: RANK_STRENGTH[c["rank"]])[0]

def can_overtrump(hand, trump_suit: str, current_trump: dict) -> bool:
    """Return True if hand has a trump stronger than current_trump."""
    trumps = [c for c in hand if c["suit"] == trump_suit]
    if not trumps:
        return False
    best = strongest_of_suit(trumps, trump_suit)
    return RANK_STRENGTH[best["rank"]] < RANK_STRENGTH[current_trump["rank"]]


def legal_moves(hand, lead_card, trump_suit, talon_not_empty: bool):
    # WITH TALON: no obligation
    if talon_not_empty or lead_card is None:
        return hand

    lead_suit = lead_card["suit"]
    if has_suit(hand, lead_suit):
        return [c for c in hand if c["suit"] == lead_suit]

    if has_trump(hand, trump_suit):
        trumps = [c for c in hand if c["suit"] == trump_suit]
        if lead_suit == trump_suit and can_overtrump(hand, trump_suit, lead_card):
            return [c for c in trumps if RANK_STRENGTH[c["rank"]] < RANK_STRENGTH[lead_card["rank"]]]
        return trumps

    return hand


def leader_play_card(game: Game, by: str, card: Dict[str, str]) -> None:
    # 🔒 garde-fous fin de manche
    if game.current_lead is not None:
        raise ValueError("Trick already started")

    if by == "player":
        if len(game.player_hand) == 0:
            raise ValueError("player has no cards left")
        remove_card(game.player_hand, card)

    elif by == "opponent":
        if len(game.opponent_hand) == 0:
            raise ValueError("opponent has no cards left")
        remove_card(game.opponent_hand, card)

    else:
        raise ValueError("invalid leader")

    # poser l’entame
    game.current_lead = card
    game.current_lead_by = by


def follower_play_and_resolve(game: Game, by: str, card: Dict[str, str]) -> None:
    if game.current_lead is None or game.current_lead_by is None:
        raise ValueError("No lead card to follow")

    lead = game.current_lead
    lead_by = game.current_lead_by
    talon_not_empty = len(game.talon) > 0

    # remove follower card
    if by == "player":
        remove_card(game.player_hand, card)
    else:
        remove_card(game.opponent_hand, card)

    # Determine who is leader (0/1) for winner calc
    leader_is_player = (lead_by == "player")

    # winner relative: 0 => leader wins, 1 => follower wins
    rel = trick_winner(lead, card, game.trump_suit, talon_not_empty)

    if rel == 0:
        winner = lead_by
    else:
        winner = by

    # draw if talon not empty (winner draws first)
    if talon_not_empty:
        if winner == "player":
            p = draw(game.talon); o = draw(game.talon)
        else:
            o = draw(game.talon); p = draw(game.talon)
        if p: game.player_hand.append(p)
        if o: game.opponent_hand.append(o)

    # update leader
    game.leader = 0 if winner == "player" else 1

    game.last_trick = {
        "lead": {"by": lead_by, "card": lead},
        "reply": {"by": by, "card": card},
        "winner": winner,
        "talon_count": len(game.talon),
    }

    # reset trick
    game.current_lead = None
    game.current_lead_by = None

def is_game_over(game: Game) -> bool:
    return len(game.player_hand) == 0 and len(game.opponent_hand) == 0 and game.current_lead is None
    

def public_state(game: Game) -> Dict[str, Any]:
    return {
        "game_id": game.game_id,
        "trump": game.trump,
        "talon_count": len(game.talon),
        "hands": {
            "player": game.player_hand,
            "opponent_count": len(game.opponent_hand),
        },
        "leader": "player" if game.leader == 0 else "opponent",
        "current_lead": {
            "by": game.current_lead_by,
            "card": game.current_lead,
        } if game.current_lead else None,
        "last_trick": game.last_trick,
    }



