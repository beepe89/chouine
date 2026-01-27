from __future__ import annotations

import uuid
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Literal, Set

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

Suit = Literal["H", "D", "C", "S"]
Rank = Literal["A", "10", "K", "Q", "J", "9", "8", "7"]
By = Literal["player", "opponent"]
AnnounceType = Literal["none", "mariage", "tierce", "quarteron", "quinte", "chouine"]

RANKS: List[str] = ["A", "10", "K", "Q", "J", "9", "8", "7"]
SUITS: List[str] = ["H", "D", "C", "S"]
RANK_STRENGTH: Dict[str, int] = {r: i for i, r in enumerate(RANKS)}  # smaller = stronger

CARD_POINTS: Dict[str, int] = {"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0, "8": 0, "7": 0}

ANNOUNCE_POINTS = {
    "mariage": (20, 40),     # non-trump / trump
    "tierce": (30, 60),
    "quarteron": (40, 80),
    "quinte": (50, 50),      # 5 brisques
}

def new_deck() -> List[Dict[str, str]]:
    return [{"suit": s, "rank": r} for s in SUITS for r in RANKS]

def card_eq(a: Dict[str, str], b: Dict[str, str]) -> bool:
    return a["suit"] == b["suit"] and a["rank"] == b["rank"]

def remove_card(hand: List[Dict[str, str]], card: Dict[str, str]) -> None:
    for i, c in enumerate(hand):
        if card_eq(c, card):
            hand.pop(i)
            return
    raise ValueError("Card not in hand")

def draw(talon: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    return talon.pop(0) if talon else None

def draw_from_stock(game: Game) -> Optional[Dict[str, str]]:
    # d'abord le talon
    if game.talon:
        return game.talon.pop(0)

    # puis la retourne (dernière carte du stock)
    if game.turnup_in_stock:
        game.turnup_in_stock = False
        return game.trump_card

    return None

def has_suit(hand: List[Dict[str, str]], suit: str) -> bool:
    return any(c["suit"] == suit for c in hand)

def trumps(hand: List[Dict[str, str]], trump_suit: str) -> List[Dict[str, str]]:
    return [c for c in hand if c["suit"] == trump_suit]

def overtrumps(hand: List[Dict[str, str]], trump_suit: str, target_trump: Dict[str, str]) -> List[Dict[str, str]]:
    return [
        c for c in hand
        if c["suit"] == trump_suit and RANK_STRENGTH[c["rank"]] < RANK_STRENGTH[target_trump["rank"]]
    ]

def talon_not_empty(game: "Game") -> bool:
    return len(game.talon) > 0

def au_sept_required(game: "Game") -> bool:
    # talon == 2 and exchange not done => leader must announce "au sept"
    return (len(game.talon) == 2) and (not game.exchange7_done)

def trick_winner(lead: Dict[str, str], reply: Dict[str, str], trump_suit: str, talon_is_not_empty: bool) -> int:
    """
    return 0 if leader wins, 1 if follower wins
    """
    lead_is_trump = lead["suit"] == trump_suit
    reply_is_trump = reply["suit"] == trump_suit

    # cut
    if reply_is_trump and not lead_is_trump:
        return 1
    if lead_is_trump and not reply_is_trump:
        return 0

    # same suit
    if reply["suit"] == lead["suit"]:
        return 0 if RANK_STRENGTH[lead["rank"]] < RANK_STRENGTH[reply["rank"]] else 1

    # different suits, no cut
    if talon_is_not_empty:
        return 0  # no obligation to follow
    return 0  # illegal should be prevented

def compute_legal_moves(hand: List[Dict[str, str]], lead_card: Optional[Dict[str, str]], trump_suit: str, talon_is_not_empty: bool) -> List[Dict[str, str]]:
    if not lead_card or talon_is_not_empty:
        return hand

    lead_suit = lead_card["suit"]

    # must follow if possible
    if has_suit(hand, lead_suit):
        return [c for c in hand if c["suit"] == lead_suit]

    # else must trump if possible
    t = trumps(hand, trump_suit)
    if t:
        if lead_suit == trump_suit:
            ot = overtrumps(hand, trump_suit, lead_card)
            return ot if ot else t
        return t

    return hand

def is_brisque(card: Dict[str, str]) -> bool:
    return card["rank"] in ("A", "10")

def count_brisques(hand: List[Dict[str, str]]) -> int:
    return sum(1 for c in hand if is_brisque(c))

def has_mariage(hand: List[Dict[str, str]], suit: str) -> bool:
    ranks = {c["rank"] for c in hand if c["suit"] == suit}
    return "K" in ranks and "Q" in ranks

def has_tierce(hand: List[Dict[str, str]], suit: str) -> bool:
    ranks = {c["rank"] for c in hand if c["suit"] == suit}
    return {"K", "Q", "J"}.issubset(ranks)

def has_quarteron(hand: List[Dict[str, str]], suit: str) -> bool:
    ranks = {c["rank"] for c in hand if c["suit"] == suit}
    return {"A", "K", "Q", "J"}.issubset(ranks)

def has_chouine(hand: List[Dict[str, str]], suit: str) -> bool:
    ranks = {c["rank"] for c in hand if c["suit"] == suit}
    return {"A", "10", "K", "Q", "J"}.issubset(ranks)

def announce_points(ann_type: AnnounceType, suit: Optional[str], trump_suit: str) -> int:
    if ann_type in ("none", "chouine"):
        return 0
    base = ANNOUNCE_POINTS[ann_type]
    if suit and suit == trump_suit:
        return base[1]
    return base[0]

def validate_announce(hand: List[Dict[str, str]], ann_type: AnnounceType, ann_suit: Optional[str]) -> bool:
    if ann_type == "none":
        return True
    if ann_type == "quinte":
        return count_brisques(hand) >= 5
    if ann_suit is None:
        return False
    if ann_type == "mariage":
        return has_mariage(hand, ann_suit)
    if ann_type == "tierce":
        return has_tierce(hand, ann_suit)
    if ann_type == "quarteron":
        return has_quarteron(hand, ann_suit)
    if ann_type == "chouine":
        return has_chouine(hand, ann_suit)
    return False

def is_seven_of_trump(card: Dict[str, str], trump_suit: str) -> bool:
    return card["suit"] == trump_suit and card["rank"] == "7"

def announce_key(ann_type: AnnounceType, suit: Optional[str]) -> str:
    # Unique key to prevent re-announcing
    if ann_type == "quinte":
        return "quinte"
    if suit is None:
        return f"{ann_type}:?"
    return f"{ann_type}:{suit}"

@dataclass
class Game:
    game_id: str
    trump_card: Dict[str, str]
    trump_suit: str
    talon: List[Dict[str, str]]

    player_hand: List[Dict[str, str]]
    opponent_hand: List[Dict[str, str]]

    leader: int  # 0 player, 1 opponent

    current_lead: Optional[Dict[str, str]] = None
    current_lead_by: Optional[By] = None
    turnup_in_stock: bool = True

    # trick piles for points
    player_tricks: List[List[Dict[str, str]]] = field(default_factory=list)
    opponent_tricks: List[List[Dict[str, str]]] = field(default_factory=list)
    last_trick_winner: Optional[By] = None

    # announces points + already announced
    player_ann_points: int = 0
    opponent_ann_points: int = 0
    announced_player: Set[str] = field(default_factory=set)
    announced_opponent: Set[str] = field(default_factory=set)

    # exchange/au sept
    exchange7_done: bool = False

    # end
    is_over: bool = False
    winner: Optional[Literal["player", "opponent", "draw"]] = None

    last_trick: Optional[Dict[str, Any]] = None
    last_announce: Optional[Dict[str, Any]] = None  # for UI feedback

def new_game() -> Game:
    deck = new_deck()
    random.shuffle(deck)

    player = deck[:5]
    opp = deck[5:10]
    trump = deck[10]
    talon = deck[11:]  # 21 cards

    return Game(
        game_id=str(uuid.uuid4()),
        trump_card=trump,
        trump_suit=trump["suit"],
        talon=talon,
        player_hand=player,
        opponent_hand=opp,
        leader=0,  # player starts
    )

def compute_cards_points(tricks: List[List[Dict[str, str]]]) -> int:
    return sum(CARD_POINTS[c["rank"]] for trick in tricks for c in trick)

def scores_so_far(game: Game) -> Dict[str, Any]:
    # during the game, we show cards + announces; dix de der only meaningful at end
    return {
        "player": {
            "cards": compute_cards_points(game.player_tricks),
            "announces": game.player_ann_points,
            "total": compute_cards_points(game.player_tricks) + game.player_ann_points,
        },
        "opponent": {
            "cards": compute_cards_points(game.opponent_tricks),
            "announces": game.opponent_ann_points,
            "total": compute_cards_points(game.opponent_tricks) + game.opponent_ann_points,
        },
        "dix_de_der_pending": True,
    }

def final_scores(game: Game) -> Dict[str, Any]:
    p = compute_cards_points(game.player_tricks) + game.player_ann_points
    o = compute_cards_points(game.opponent_tricks) + game.opponent_ann_points

    # dix de der
    if game.last_trick_winner == "player":
        p += 10
    elif game.last_trick_winner == "opponent":
        o += 10

    return {
        "player": {
            "cards": compute_cards_points(game.player_tricks),
            "announces": game.player_ann_points,
            "dix_de_der": 10 if game.last_trick_winner == "player" else 0,
            "total": p,
        },
        "opponent": {
            "cards": compute_cards_points(game.opponent_tricks),
            "announces": game.opponent_ann_points,
            "dix_de_der": 10 if game.last_trick_winner == "opponent" else 0,
            "total": o,
        },
    }

def maybe_finish_game(game: Game) -> None:
    if game.is_over:
        return
    if game.current_lead is not None:
        return
    if len(game.player_hand) != 0 or len(game.opponent_hand) != 0:
        return
    game.is_over = True
    fs = final_scores(game)
    if fs["player"]["total"] > fs["opponent"]["total"]:
        game.winner = "player"
    elif fs["opponent"]["total"] > fs["player"]["total"]:
        game.winner = "opponent"
    else:
        game.winner = "draw"

def invariant_warning(game: Game) -> Optional[str]:
    # pendant un pli: le leader a une carte de moins
    if game.current_lead is not None and game.current_lead_by:
        if game.current_lead_by == "player":
            if len(game.player_hand) != len(game.opponent_hand) - 1:
                return "invariant: during trick player should have one less card than opponent"
        else:
            if len(game.opponent_hand) != len(game.player_hand) - 1:
                return "invariant: during trick opponent should have one less card than player"
        return None

    # entre les plis: tailles égales
    if len(game.player_hand) != len(game.opponent_hand):
        return "invariant: between tricks hands should be same size"
    return None


def apply_announce(game: Game, by: By, ann_type: AnnounceType, ann_suit: Optional[str], show: bool, hand_snapshot: List[Dict[str, str]]) -> None:
    """
    Must be called at the moment the player plays a card (lead OR follow).
    - announce must be shown
    - must be valid for hand_snapshot (hand BEFORE removing the played card)
    - cannot be repeated
    - chouine ends immediately
    """
    if ann_type == "none":
        return

    if not show:
        raise ValueError("announce must be shown (show=true)")

    if not validate_announce(hand_snapshot, ann_type, ann_suit):
        raise ValueError("invalid announce for your hand")

    key = announce_key(ann_type, ann_suit)
    announced_set = game.announced_player if by == "player" else game.announced_opponent

    if key in announced_set:
        raise ValueError("announce already made earlier")

    # record
    announced_set.add(key)
    game.last_announce = {"by": by, "type": ann_type, "suit": ann_suit}

    if ann_type == "chouine":
        game.is_over = True
        game.winner = by
        return

    pts = announce_points(ann_type, ann_suit, game.trump_suit)
    if by == "player":
        game.player_ann_points += pts
    else:
        game.opponent_ann_points += pts

def resolve_trick(game: Game, lead_by: By, lead_card: Dict[str, str], follow_by: By, follow_card: Dict[str, str]) -> None:
    rel = trick_winner(lead_card, follow_card, game.trump_suit, talon_not_empty(game))
    winner: By = lead_by if rel == 0 else follow_by

    trick_cards = [lead_card, follow_card]
    if winner == "player":
        game.player_tricks.append(trick_cards)
    else:
        game.opponent_tricks.append(trick_cards)

    game.last_trick_winner = winner
    game.leader = 0 if winner == "player" else 1

    # draw if talon not empty
    # on pioche tant qu'il reste du stock (talon + retourne)
    if len(game.talon) > 0 or game.turnup_in_stock:
        if winner == "player":
            p = draw_from_stock(game); o = draw_from_stock(game)
        else:
            o = draw_from_stock(game); p = draw_from_stock(game)

        if p: game.player_hand.append(p)
        if o: game.opponent_hand.append(o)


    game.last_trick = {
        "lead": {"by": lead_by, "card": lead_card},
        "reply": {"by": follow_by, "card": follow_card},
        "winner": winner,
        "talon_count": len(game.talon),
    }

    game.current_lead = None
    game.current_lead_by = None


    maybe_finish_game(game)

# -------- AI (legal + strong enough) --------

def ai_choose_best_announce(game: Game, hand_snapshot: List[Dict[str, str]]) -> Tuple[AnnounceType, Optional[str], bool]:
    """
    Opponent announces optimally, but only if not repeated.
    Returns (type, suit, show)
    """
    possibles: List[Tuple[AnnounceType, Optional[str], int]] = []

    # chouine first
    for s in SUITS:
        if has_chouine(hand_snapshot, s):
            key = announce_key("chouine", s)
            if key not in game.announced_opponent:
                return "chouine", s, True

    # other announces
    for s in SUITS:
        if has_mariage(hand_snapshot, s):
            possibles.append(("mariage", s, announce_points("mariage", s, game.trump_suit)))
        if has_tierce(hand_snapshot, s):
            possibles.append(("tierce", s, announce_points("tierce", s, game.trump_suit)))
        if has_quarteron(hand_snapshot, s):
            possibles.append(("quarteron", s, announce_points("quarteron", s, game.trump_suit)))

    if count_brisques(hand_snapshot) >= 5:
        possibles.append(("quinte", None, 50))

    # pick max pts not already announced
    possibles.sort(key=lambda x: x[2], reverse=True)
    for t, s, _pts in possibles:
        key = announce_key(t, s)
        if key not in game.announced_opponent:
            return t, s, True

    return "none", None, False

def ai_choose_lead_card(game: Game) -> Dict[str, str]:
    # legal: any card if no current lead
    # heuristic: keep brisques, keep trumps if talon empty, etc.
    hand = game.opponent_hand
    if not hand:
        raise ValueError("opponent has no cards")

    if not talon_not_empty(game):
        # endgame: play strongest non-risky first (simple but effective)
        # prefer winning cards / trumps
        def score(c):
            s = 0
            if c["suit"] == game.trump_suit:
                s += 2
            if is_brisque(c):
                s += 3
            s += (7 - RANK_STRENGTH[c["rank"]]) * 0.1
            return s
        return max(hand, key=score)

    # with talon: try to win to draw first, but avoid burning trumps
    def score(c):
        s = 0.0
        if is_brisque(c):
            s += 2.0
        if c["suit"] == game.trump_suit:
            s += 0.5
        s += (7 - RANK_STRENGTH[c["rank"]]) * 0.05
        s += random.random() * 0.01
        return s

    return max(hand, key=score)

def ai_choose_follow_card(game: Game, lead_card: Dict[str, str]) -> Dict[str, str]:
    hand = game.opponent_hand
    if not hand:
        raise ValueError("opponent has no cards")

    legal = compute_legal_moves(hand, lead_card, game.trump_suit, talon_not_empty(game))

    # try to win cheaply if possible
    def follower_wins(c) -> bool:
        return trick_winner(lead_card, c, game.trump_suit, talon_not_empty(game)) == 1

    winning = [c for c in legal if follower_wins(c)]
    if winning:
        return min(winning, key=lambda c: (CARD_POINTS[c["rank"]], RANK_STRENGTH[c["rank"]]))

    # otherwise dump low value
    def dump_key(c):
        return (1 if is_brisque(c) else 0, 1 if c["suit"] == game.trump_suit else 0, CARD_POINTS[c["rank"]], RANK_STRENGTH[c["rank"]])
    return min(legal, key=dump_key)

# -------- Engine actions (lead/follow) --------

def leader_play(game: Game, by: By, card: Dict[str, str], au_sept_flag: bool, announce: Dict[str, Any], show: bool) -> None:
    if game.is_over:
        raise ValueError("game over")
    if game.current_lead is not None:
        raise ValueError("trick already started")



    if (game.leader == 0 and by != "player") or (game.leader == 1 and by != "opponent"):
        raise ValueError("not leader")

    if au_sept_required(game) and not au_sept_flag:
        raise ValueError("au sept required (talon=2 & exchange not done)")

    # snapshot for announces BEFORE removing
    if by == "player":
        hand_snapshot = [dict(c) for c in game.player_hand]
    else:
        hand_snapshot = [dict(c) for c in game.opponent_hand]

    ann_type: AnnounceType = (announce or {}).get("type", "none")
    ann_suit = (announce or {}).get("suit", None)

    # validate announce (may end the game)
    apply_announce(game, by, ann_type, ann_suit, show, hand_snapshot)
    if game.is_over:
        return

    # remove card
    if by == "player":
        remove_card(game.player_hand, card)
    else:
        remove_card(game.opponent_hand, card)

    game.current_lead = card
    game.current_lead_by = by

    #assert_invariants(game)

def follower_play(game: Game, by: By, card: Dict[str, str], announce: Dict[str, Any], show: bool) -> None:
    if game.is_over:
        raise ValueError("game over")
    if not game.current_lead or not game.current_lead_by:
        raise ValueError("no lead")
    if by == game.current_lead_by:
        raise ValueError("leader cannot follow")

    # legality if talon empty
    if not talon_not_empty(game):
        hand = game.player_hand if by == "player" else game.opponent_hand
        legal = compute_legal_moves(hand, game.current_lead, game.trump_suit, talon_is_not_empty=False)
        if not any(card_eq(c, card) for c in legal):
            raise ValueError("illegal move (must follow/cut/overtrump)")

    # snapshot for announces BEFORE removing
    hand_snapshot = [dict(c) for c in (game.player_hand if by == "player" else game.opponent_hand)]

    ann_type: AnnounceType = (announce or {}).get("type", "none")
    ann_suit = (announce or {}).get("suit", None)

    apply_announce(game, by, ann_type, ann_suit, show, hand_snapshot)
    if game.is_over:
        return

    # remove follower card
    if by == "player":
        remove_card(game.player_hand, card)
    else:
        remove_card(game.opponent_hand, card)

    lead_by = game.current_lead_by
    lead_card = game.current_lead

    assert lead_by and lead_card

    resolve_trick(game, lead_by, lead_card, by, card)

# -------- Exchange 7 --------

def exchange7(game: Game) -> None:
    if game.is_over:
        raise ValueError("game over")
    if game.exchange7_done:
        raise ValueError("exchange already done")
    if not talon_not_empty(game):
        raise ValueError("cannot exchange when talon empty")

    idx = None
    for i, c in enumerate(game.player_hand):
        if is_seven_of_trump(c, game.trump_suit):
            idx = i
            break
    if idx is None:
        raise ValueError("you don't have the 7 of trump")

    seven = game.player_hand[idx]
    game.player_hand[idx] = game.trump_card
    game.trump_card = seven
    game.exchange7_done = True

# -------- public state --------

def public_state(game: Game) -> Dict[str, Any]:
    fs = final_scores(game) if game.is_over else None
    return {
        "game_id": game.game_id,
        "trump": game.trump_card,
        "trump_suit": game.trump_suit,
        "talon_count": len(game.talon),
        "leader": "player" if game.leader == 0 else "opponent",
        "hands": {"player": game.player_hand, "opponent_count": len(game.opponent_hand)},
        "current_lead": {"by": game.current_lead_by, "card": game.current_lead} if game.current_lead else None,
        "last_trick": game.last_trick,
        "scores_so_far": scores_so_far(game),
        "final_score": fs,
        "is_over": game.is_over,
        "winner": game.winner,
        "can_exchange7": (not game.exchange7_done) and talon_not_empty(game) and any(is_seven_of_trump(c, game.trump_suit) for c in game.player_hand),
        "au_sept_required": au_sept_required(game),
        "stock_count": len(game.talon) + (1 if game.turnup_in_stock else 0),
        "turnup_in_stock": game.turnup_in_stock,

        "announced": {
            "player": sorted(list(game.announced_player)),
            "opponent": sorted(list(game.announced_opponent)),
        },
        "last_announce": game.last_announce,
        "warning": invariant_warning(game),
    }

# =========================
# FastAPI
# =========================

app = FastAPI(title="Chouine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GAMES: Dict[str, Game] = {}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/game/new")
def api_new_game():
    g = new_game()
    GAMES[g.game_id] = g
    return public_state(g)

@app.post("/game/{game_id}/exchange7")
def api_exchange7(game_id: str):
    g = GAMES.get(game_id)
    if not g:
        return {"error": "unknown game"}
    try:
        exchange7(g)
    except ValueError as e:
        return {"error": str(e), **public_state(g)}
    return public_state(g)

@app.post("/game/{game_id}/lead")
def api_lead(game_id: str, payload: dict):
    g = GAMES.get(game_id)
    if not g:
        return {"error": "unknown game"}

    if g.is_over:
        return public_state(g)

    by: By = payload.get("by")
    card = payload.get("card")
    au_sept_flag = bool(payload.get("au_sept", False))
    announce = payload.get("announce") or {}
    show = bool(payload.get("show", False))

    if by not in ("player", "opponent"):
        return {"error": "missing by", **public_state(g)}

    # opponent can lead without specifying card
    if by == "opponent" and not card:
        card = ai_choose_lead_card(g)

    if not card:
        return {"error": "missing card", **public_state(g)}

    try:
        leader_play(g, by, card, au_sept_flag, announce, show)
    except ValueError as e:
        maybe_finish_game(g)
        return {"error": str(e), **public_state(g)}

    if g.is_over:
        return public_state(g)

    # if player led, auto-follow opponent
    if by == "player":
        try:
            # opponent announces on its follow if it wants
            lead_card = g.current_lead
            if not lead_card:
                raise ValueError("internal: missing lead")

            opp_hand_snapshot = [dict(c) for c in g.opponent_hand]
            opp_card = ai_choose_follow_card(g, lead_card)
            ann_t, ann_s, ann_show = ai_choose_best_announce(g, opp_hand_snapshot)

            follower_play(g, "opponent", opp_card, {"type": ann_t, "suit": ann_s}, ann_show)
            # ✅ si l'adversaire gagne le pli, il entame tout de suite (UX solo)
            if g.leader == 1 and g.current_lead is None and len(g.opponent_hand) > 0:
                opp_hand_snapshot2 = [dict(c) for c in g.opponent_hand]
                ann_t2, ann_s2, ann_show2 = ai_choose_best_announce(g, opp_hand_snapshot2)
                opp_lead = ai_choose_lead_card(g)
                leader_play(
                    g,
                    "opponent",
                    opp_lead,
                    au_sept_flag=True,
                    announce={"type": ann_t2, "suit": ann_s2},
                    show=ann_show2,
                )

        except ValueError as e:
            maybe_finish_game(g)
            return {"error": str(e), **public_state(g)}

    return public_state(g)

@app.post("/game/{game_id}/follow")
def api_follow(game_id: str, payload: dict):
    g = GAMES.get(game_id)
    if not g:
        return {"error": "unknown game"}

    if g.is_over:
        return public_state(g)

    if not g.current_lead:
        return {"error": "no lead", **public_state(g)}

    by: By = payload.get("by")
    card = payload.get("card")
    announce = payload.get("announce") or {}
    show = bool(payload.get("show", False))

    if by not in ("player", "opponent"):
        return {"error": "missing by", **public_state(g)}
    if not card:
        return {"error": "missing card", **public_state(g)}

    try:
        follower_play(g, by, card, announce, show)
    except ValueError as e:
        maybe_finish_game(g)
        return {"error": str(e), **public_state(g)}

    if g.is_over:
        return public_state(g)

    # if opponent becomes leader, auto-lead immediately (single player UX)
    if g.leader == 1 and g.current_lead is None and len(g.opponent_hand) > 0:
        try:
            # opponent may announce on its lead
            opp_hand_snapshot = [dict(c) for c in g.opponent_hand]
            ann_t, ann_s, ann_show = ai_choose_best_announce(g, opp_hand_snapshot)

            opp_lead = ai_choose_lead_card(g)
            leader_play(g, "opponent", opp_lead, au_sept_flag=True, announce={"type": ann_t, "suit": ann_s}, show=ann_show)
        except ValueError as e:
            maybe_finish_game(g)
            return {"error": str(e), **public_state(g)}

    return public_state(g)
