"use client";

import { useEffect, useMemo, useState } from "react";
import { RANK_LABELS, SUIT_LABELS, cardImageSrc } from "@/lib/cards";

type Card = { suit: string; rank: string };
type AnnounceType = "none" | "mariage" | "tierce" | "quarteron" | "quinte" | "chouine";

export default function Home() {
  const [data, setData] = useState<any>(null);
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
  
  const [gameId, setGameId] = useState<string | null>(null);
  const [leader, setLeader] = useState<"player" | "opponent">("player");
  const [hand, setHand] = useState<Card[]>([]);
  const [currentLead, setCurrentLead] = useState<any>(null);
  const [lastTrick, setLastTrick] = useState<any>(null);

  const [announceType, setAnnounceType] = useState<AnnounceType>("none");
  const [announceSuit, setAnnounceSuit] = useState<string>(""); // H/D/C/S
  const [showAnnounce, setShowAnnounce] = useState<boolean>(false);

  const [auSept, setAuSept] = useState<boolean>(false);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  function sync(json: any) {
    setData(json);
    setLeader(json.leader);
    setHand(json.hands?.player ?? []);
    setCurrentLead(json.current_lead ?? null);
    setLastTrick(json.last_trick ?? null);

    // reset announce controls after each action (prevents accidental re-click)
    setAnnounceType("none");
    setAnnounceSuit("");
    setShowAnnounce(false);

    setAuSept(false);
  }

  async function loadNewGame() {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/game/new`, { method: "POST" });
      const json = await res.json();
      if (json?.error) {
        setError(String(json.error));
        return;
      }

      setGameId(json.game_id);
      sync(json);
    } catch (e: any) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadNewGame();
  }, []);

  const trump: Card | null = data?.trump ?? null;
  const talonCount: number | null = typeof data?.talon_count === "number" ? data.talon_count : null;

  const isOver: boolean = !!data?.is_over;
  const winner: string | null = data?.winner ?? null;
  const finalScore = data?.final_score ?? null;
  const scoreSoFar = data?.scores_so_far ?? null;

  const canExchange7 = !!data?.can_exchange7;
  const auSeptRequired = !!data?.au_sept_required;

  const announcedPlayer: string[] = useMemo(() => data?.announced?.player ?? [], [data]);
  const lastAnnounce = data?.last_announce ?? null;

  const waitingOpponentLead = !isOver && leader === "opponent" && !currentLead;
  const canPlay = !isOver && !loading && !waitingOpponentLead;

  async function exchange7() {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/game/${gameId}/exchange7`, { method: "POST" });
      const json = await res.json();
      if (json?.error) setError(String(json.error));
      sync(json);
    } catch (e: any) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function playCard(c: Card) {
    if (!gameId) return;
    if (!canPlay) return;

    setLoading(true);
    setError(null);

    try {
      const endpoint = currentLead ? "follow" : "lead";

      const body: any = { by: "player", card: c };

      // announcements are allowed on BOTH lead and follow
      body.announce = { type: announceType, suit: announceSuit || null };
      body.show = showAnnounce;

      if (endpoint === "lead") {
        body.au_sept = auSeptRequired ? auSept : false;
      }

      const res = await fetch(`${API_BASE}/game/${gameId}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const json = await res.json();

      if (json?.error) {
        setError(String(json.error));
        sync(json);
        return;
      }

      sync(json);
    } catch (e: any) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="p-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Chouine MVP</h1>

        <button
          className="ml-auto px-4 py-2 rounded border hover:bg-gray-50 disabled:opacity-50"
          onClick={loadNewGame}
          disabled={loading}
        >
          Nouvelle donne
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-4 text-sm text-gray-700 space-y-1">
        <div>
          <span className="font-semibold">Leader :</span> {leader === "player" ? "toi" : "adversaire"}
        </div>

        {talonCount !== null && (
          <div>
            <span className="font-semibold">Talon :</span> {talonCount} carte{talonCount > 1 ? "s" : ""}
          </div>
        )}

        {trump && (
          <div className="flex items-center gap-2">
            <span className="font-semibold">Atout :</span>
            <span>
              {RANK_LABELS[trump.rank]} de {SUIT_LABELS[trump.suit]}
            </span>
            <span className="inline-block w-[42px] h-[60px] rounded overflow-hidden align-middle">
              <img
                src={cardImageSrc(trump)}
                alt={`Atout: ${RANK_LABELS[trump.rank]} de ${SUIT_LABELS[trump.suit]}`}
                className="w-full h-full object-contain"
              />
            </span>

            {canExchange7 && (
              <button
                onClick={exchange7}
                disabled={loading}
                className="ml-3 px-3 py-1 rounded border hover:bg-gray-50 disabled:opacity-50"
                title="Échanger le 7 d’atout contre la retourne"
              >
                Échange 7 d’atout
              </button>
            )}
          </div>
        )}

        {auSeptRequired && !isOver && (
          <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <div className="font-semibold">“Au sept” requis (talon = 2 et échange non fait)</div>
            <label className="mt-2 flex items-center gap-2">
              <input type="checkbox" checked={auSept} onChange={(e) => setAuSept(e.target.checked)} />
              J’annonce “au sept”
            </label>
          </div>
        )}
      </div>

      {/* Score panel (always visible) */}
      {scoreSoFar && (
        <div className="mt-6 rounded border p-3 text-sm">
          <div className="font-semibold">Score (en cours — dix de der à la fin)</div>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <div className="font-semibold">Toi</div>
              <div>Cartes : {scoreSoFar.player.cards}</div>
              <div>Annonces : {scoreSoFar.player.announces}</div>
              <div>Total : {scoreSoFar.player.total}</div>
            </div>
            <div>
              <div className="font-semibold">Adversaire</div>
              <div>Cartes : {scoreSoFar.opponent.cards}</div>
              <div>Annonces : {scoreSoFar.opponent.announces}</div>
              <div>Total : {scoreSoFar.opponent.total}</div>
            </div>
          </div>

          {lastAnnounce && (
            <div className="mt-3 text-xs text-gray-600">
              Dernière annonce : {lastAnnounce.by} → {lastAnnounce.type}
              {lastAnnounce.suit ? `(${lastAnnounce.suit})` : ""}
            </div>
          )}
        </div>
      )}

      {isOver && (
        <div className="mt-6 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          🏁 Partie terminée —{" "}
          <strong>{winner === "player" ? "tu gagnes" : winner === "opponent" ? "tu perds" : "égalité"}</strong>
          {finalScore && (
            <div className="mt-2 text-sm text-green-900">
              <div>
                Toi : {finalScore.player.total} (cartes {finalScore.player.cards} + annonces{" "}
                {finalScore.player.announces} + dix de der {finalScore.player.dix_de_der})
              </div>
              <div>
                Adversaire : {finalScore.opponent.total} (cartes {finalScore.opponent.cards} + annonces{" "}
                {finalScore.opponent.announces} + dix de der {finalScore.opponent.dix_de_der})
              </div>
            </div>
          )}
        </div>
      )}

      {/* Announcement panel: available whenever YOU are about to play */}
      {!isOver && (
        <div className="mt-8 rounded border p-3 text-sm">
          <div className="font-semibold">Annoncer (au moment où tu poses ta carte)</div>

          <div className="mt-2 flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-600">Type</span>
              <select
                value={announceType}
                onChange={(e) => setAnnounceType(e.target.value as AnnounceType)}
                className="border rounded px-2 py-1"
                disabled={!canPlay}
              >
                <option value="none">Aucune</option>
                <option value="mariage">Mariage</option>
                <option value="tierce">Tierce</option>
                <option value="quarteron">Quarteron</option>
                <option value="quinte">Quinte (5 brisques)</option>
                <option value="chouine">Chouine</option>
              </select>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-600">Couleur (si applicable)</span>
              <select
                value={announceSuit}
                onChange={(e) => setAnnounceSuit(e.target.value)}
                className="border rounded px-2 py-1"
                disabled={!canPlay || announceType === "none" || announceType === "quinte"}
              >
                <option value="">—</option>
                <option value="H">Cœur</option>
                <option value="D">Carreau</option>
                <option value="C">Trèfle</option>
                <option value="S">Pique</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={showAnnounce}
                onChange={(e) => setShowAnnounce(e.target.checked)}
                disabled={!canPlay || announceType === "none"}
              />
              Je montre
            </label>
          </div>

          {announcedPlayer.length > 0 && (
            <div className="mt-3 text-xs text-gray-600">
              Déjà annoncées : {announcedPlayer.join(", ")}
            </div>
          )}
        </div>
      )}

      {/* Opponent lead card */}
      {currentLead && currentLead.by === "opponent" && currentLead.card && (
        <>
          <h2 className="mt-8 font-semibold">L’adversaire entame</h2>

          <div className="mt-2 w-[110px] h-[160px] rounded overflow-hidden">
            <img src={cardImageSrc(currentLead.card)} alt="Carte adverse" className="w-full h-full object-contain" />
          </div>

          <p className="mt-2 text-sm text-gray-600">À toi de répondre (clique une carte).</p>
        </>
      )}

      {/* Your hand */}
      <h2 className="mt-8 font-semibold">
        Ta main {loading ? <span className="text-sm text-gray-500">(…)</span> : null}
      </h2>

      {waitingOpponentLead && <p className="mt-2 text-sm text-gray-600">Attente de l’entame adverse…</p>}

      <div className="mt-3 flex flex-wrap gap-3">
        {hand.map((c: Card, i: number) => (
          <button
            key={`${c.suit}-${c.rank}-${i}`}
            onClick={() => playCard(c)}
            disabled={!canPlay}
            className="w-[110px] h-[160px] rounded overflow-hidden hover:-translate-y-1 hover:shadow-lg transition disabled:opacity-40"
            title={`${RANK_LABELS[c.rank]} de ${SUIT_LABELS[c.suit]}`}
          >
            <img src={cardImageSrc(c)} alt={`${RANK_LABELS[c.rank]} de ${SUIT_LABELS[c.suit]}`} className="w-full h-full object-contain" />
          </button>
        ))}
      </div>

      {/* Last trick */}
      {lastTrick && lastTrick.lead?.card && lastTrick.reply?.card && (
        <>
          <h2 className="mt-10 font-semibold">Dernier pli</h2>

          <div className="mt-3 flex flex-wrap items-start gap-6 text-sm text-gray-700">
            <div className="flex items-center gap-3">
              <div className="w-[70px] h-[100px] rounded overflow-hidden">
                <img src={cardImageSrc(lastTrick.lead.card)} alt="Entame" className="w-full h-full object-contain" />
              </div>
              <div>
                <div>
                  <span className="font-semibold">Entame :</span>{" "}
                  {RANK_LABELS[lastTrick.lead.card.rank]} de {SUIT_LABELS[lastTrick.lead.card.suit]} (
                  {lastTrick.lead.by === "player" ? "toi" : "adversaire"})
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-[70px] h-[100px] rounded overflow-hidden">
                <img src={cardImageSrc(lastTrick.reply.card)} alt="Réponse" className="w-full h-full object-contain" />
              </div>
              <div>
                <div>
                  <span className="font-semibold">Réponse :</span>{" "}
                  {RANK_LABELS[lastTrick.reply.card.rank]} de {SUIT_LABELS[lastTrick.reply.card.suit]} (
                  {lastTrick.reply.by === "player" ? "toi" : "adversaire"})
                </div>
              </div>
            </div>

            <div className="min-w-[180px]">
              <div>
                <span className="font-semibold">Gagnant :</span>{" "}
                <span className="font-semibold">{lastTrick.winner === "player" ? "toi" : "adversaire"}</span>
              </div>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
