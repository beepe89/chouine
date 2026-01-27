export const RANK_LABELS: Record<string, string> = {
  "A": "As",
  "10": "10",
  "K": "Roi",
  "Q": "Dame",
  "J": "Valet",
  "9": "9",
  "8": "8",
  "7": "7",
};

export const SUIT_LABELS: Record<string, string> = {
  "H": "Cœur",
  "D": "Carreau",
  "C": "Trèfle",
  "S": "Pique",
};


// mapping des rangs
const RANK_FILE: Record<string, string> = {
  A: "as",
  K: "roi",
  Q: "dame",
  J: "valet",
  "10": "dix",
  "9": "neuf",
  "8": "huit",
  "7": "sept",
};

const SUIT_FILE: Record<string, string> = {
  H: "coeur",
  D: "carreaux",
  C: "trefle",
  S: "pique",
};

export function cardImageSrc(card: { rank: string; suit: string }) {
  const rank = RANK_FILE[card.rank];
  const suit = SUIT_FILE[card.suit];

  if (!rank || !suit) {
    console.warn("Carte inconnue", card);
    return "";
  }

  return `/cartes/${rank}_${suit}.png`;
}