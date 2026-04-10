"""
MarketSentinel — Score Engine
==============================
Scores each post on four dimensions:
  1. Engagement Spike    (max 30 pts)  — views/reposts vs. author's rolling average
  2. Ticker Mention      (max 25 pts)  — stock/ETF tickers + directional language
  3. Dramatic Claim      (max 25 pts)  — NLP keyword matching for high-impact language
  4. Policy Signal       (max 20 pts)  — tariffs, Fed, executive orders, sanctions, etc.

Total max score = 100.
"""

import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Ticker regex: matches $TICKER or standalone UPPERCASE 2-5 char words ───
TICKER_PATTERN = re.compile(
    r'\$([A-Z]{1,5})\b'
    r'|(?<!\w)([A-Z]{2,5})(?!\w)(?=[\s,\.!?;:\(\)]|$)'
)

# Words that look like tickers but aren't
TICKER_EXCLUSIONS = {
    "I", "A", "THE", "AND", "OR", "NOT", "FOR", "IN", "ON", "AT", "TO",
    "US", "EU", "UK", "AI", "AT", "BE", "DO", "GO", "IF", "IS", "IT",
    "MY", "NO", "OF", "SO", "UP", "WE", "BY", "CEO", "CFO", "IPO",
    "ETF", "GDP", "CPI", "FED", "SEC", "DOJ", "IMF", "ECB", "BOJ",
    "DXY", "ATH", "NLP", "AI", "ESG", "EPS", "PE", "YTD", "QOQ", "YOY",
    "AM", "PM", "EST", "PST", "GMT", "UTC",
}

# Known tickers for disambiguation (major ones — expand as needed)
KNOWN_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "NFLX",
    "AMD", "INTC", "QCOM", "AVGO", "ARM", "SMCI", "PLTR", "SNOW", "CRM",
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "GLD", "SLV", "TLT", "HYG",
    "XLF", "XLE", "XLK", "XLV", "XLU", "XLI", "XLB", "XLRE",
    "FNMA", "FMCC", "KRE", "BAC", "JPM", "GS", "MS", "WFC", "C", "USB",
    "BTC", "ETH", "COIN", "MSTR", "MARA", "RIOT",
    "EWZ", "EFA", "VEA", "VWO", "FXI",
    "USO", "UNG", "DBO", "BNO",
}

DIRECTIONAL_BULLISH = [
    "buy", "long", "bullish", "upside", "underpriced", "undervalued",
    "upside", "rally", "breakout", "accumulate", "add", "initiat",
    "10x", "5x", "double", "triple", "outperform", "overweight"
]

DIRECTIONAL_BEARISH = [
    "short", "bearish", "overpriced", "overvalued", "downside", "put",
    "collapse", "crash", "fraud", "bankruptcy", "sell", "underperform",
    "underweight", "trap", "bubble", "zero", "worthless", "fade"
]


class ScoreEngine:

    def __init__(self, config: dict):
        self.cfg = config["scoring"]
        self.settings = config["settings"]

    # ────────────────────────────────────────
    # 1. ENGAGEMENT SPIKE SCORE
    # ────────────────────────────────────────
    def score_engagement(self, post_metrics: dict, author_averages: dict) -> tuple[int, float]:
        """
        Returns (score, spike_multiplier).

        post_metrics: {"views": int, "reposts": int, "likes": int, "replies": int}
        author_averages: {"avg_views": float, "avg_reposts": float, ...}
        """
        if not author_averages or author_averages.get("avg_views", 0) == 0:
            # No baseline data — use absolute thresholds
            views = post_metrics.get("views", 0)
            if views >= 1_000_000:  return (25, 0)
            if views >= 500_000:    return (18, 0)
            if views >= 100_000:    return (12, 0)
            if views >= 10_000:     return (6,  0)
            return (2, 0)

        # Calculate combined engagement multiplier (weighted average across metrics)
        weights = {"views": 0.5, "reposts": 0.3, "likes": 0.15, "replies": 0.05}
        multipliers = []
        for metric, weight in weights.items():
            avg_key = f"avg_{metric}"
            if author_averages.get(avg_key, 0) > 0:
                m = post_metrics.get(metric, 0) / author_averages[avg_key]
                multipliers.append((m, weight))

        if not multipliers:
            return (2, 0)

        total_weight = sum(w for _, w in multipliers)
        spike = sum(m * w for m, w in multipliers) / total_weight

        # Tier-based scoring
        tiers = self.cfg["engagement"]["spike_tiers"]
        max_pts = self.cfg["engagement"]["max_points"]
        for tier in tiers:
            if spike >= tier["multiplier"]:
                pts = min(tier["points"], max_pts)
                return (pts, round(spike, 1))

        return (2, round(spike, 1))

    # ────────────────────────────────────────
    # 2. TICKER MENTION SCORE
    # ────────────────────────────────────────
    def score_tickers(self, text: str) -> tuple[int, list[str]]:
        """
        Returns (score, list_of_tickers_found).
        """
        tickers_found = set()
        max_pts = self.cfg["ticker_mention"]["max_points"]

        # Match $TICKER pattern (high confidence)
        dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text.upper())
        tickers_found.update(t for t in dollar_tickers if t not in TICKER_EXCLUSIONS)

        # Match known tickers in plain text
        words = re.findall(r'\b[A-Z]{2,5}\b', text.upper())
        for w in words:
            if w in KNOWN_TICKERS and w not in TICKER_EXCLUSIONS:
                tickers_found.add(w)

        if not tickers_found:
            return (0, [])

        cfg_t = self.cfg["ticker_mention"]
        base = cfg_t["base_per_ticker"]
        score = min(len(tickers_found) * base, max_pts - cfg_t["directional_bonus"] - cfg_t["multiple_tickers_bonus"])

        # Bonus for directional language
        text_lower = text.lower()
        has_direction = any(k in text_lower for k in DIRECTIONAL_BULLISH + DIRECTIONAL_BEARISH)
        if has_direction:
            score += cfg_t["directional_bonus"]

        # Multiple tickers bonus
        if len(tickers_found) >= 3:
            score += cfg_t["multiple_tickers_bonus"]

        return (min(score, max_pts), sorted(tickers_found))

    # ────────────────────────────────────────
    # 3. DRAMATIC CLAIM SCORE
    # ────────────────────────────────────────
    def score_dramatic(self, text: str) -> tuple[int, list[str]]:
        """
        Returns (score, matched_keywords).
        Uses tiered keyword matching.
        """
        text_lower = text.lower()
        max_pts = self.cfg["dramatic_claim"]["max_points"]
        keywords_cfg = self.cfg["dramatic_claim"]["keywords"]

        matched = []
        score = 0

        # Extreme keywords (highest weight)
        for kw in keywords_cfg["extreme"]:
            if kw.lower() in text_lower:
                score += 6
                matched.append(kw)

        # High keywords
        for kw in keywords_cfg["high"]:
            if kw.lower() in text_lower:
                score += 3
                matched.append(kw)

        # Medium keywords
        for kw in keywords_cfg["medium"]:
            if kw.lower() in text_lower:
                score += 1
                matched.append(kw)

        # Percentage/multiplier patterns ("10x", "50%", etc.)
        pct_matches = re.findall(r'\b\d+(?:\.\d+)?[x×%]\b', text_lower)
        for m in pct_matches:
            val_str = re.findall(r'[\d.]+', m)
            if val_str:
                val = float(val_str[0])
                if '%' in m and val >= 30:   score += 4; matched.append(m)
                elif 'x' in m and val >= 3:  score += 5; matched.append(m)

        return (min(score, max_pts), list(set(matched)))

    # ────────────────────────────────────────
    # 4. POLICY SIGNAL SCORE
    # ────────────────────────────────────────
    def score_policy(self, text: str, author_category: str) -> tuple[int, list[str]]:
        """
        Returns (score, matched_policy_keywords).
        Policy figures (President, Treasury) get a multiplier.
        """
        text_lower = text.lower()
        max_pts = self.cfg["policy_signal"]["max_points"]
        keywords = self.cfg["policy_signal"]["keywords"]

        matched = []
        score = 0
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 3
                matched.append(kw)

        # Authoritative source multiplier
        if author_category in ("policy",):
            score = int(score * 1.5)

        return (min(score, max_pts), list(set(matched)))

    # ────────────────────────────────────────
    # COMBINED SCORE
    # ────────────────────────────────────────
    def score_post(
        self,
        text: str,
        author: dict,
        post_metrics: dict,
        author_averages: Optional[dict] = None,
    ) -> dict:
        """
        Master scoring function. Returns a full score breakdown dict.

        author: {"name": str, "category": str, "credibility_weight": float}
        post_metrics: {"views": int, "reposts": int, "likes": int, "replies": int}
        author_averages: rolling average metrics (optional)
        """
        eng_score, spike_mult = self.score_engagement(post_metrics, author_averages or {})
        tick_score, tickers = self.score_tickers(text)
        drama_score, drama_kws = self.score_dramatic(text)
        policy_score, policy_kws = self.score_policy(text, author.get("category", ""))

        raw_total = eng_score + tick_score + drama_score + policy_score

        # Apply author credibility weight (0.6 to 1.0)
        cred = author.get("credibility_weight", 0.8)
        final_score = min(int(raw_total * cred), 100)

        # Determine signal categories triggered
        signals = []
        if eng_score >= 8:    signals.append("engagement")
        if tick_score >= 8:   signals.append("ticker")
        if drama_score >= 6:  signals.append("dramatic")
        if policy_score >= 6: signals.append("policy")

        # Determine directional bias
        text_lower = text.lower()
        bullish_hits = sum(1 for k in DIRECTIONAL_BULLISH if k in text_lower)
        bearish_hits = sum(1 for k in DIRECTIONAL_BEARISH if k in text_lower)
        if bearish_hits > bullish_hits:     direction = "bearish"
        elif bullish_hits > bearish_hits:   direction = "bullish"
        else:                               direction = "neutral"

        if direction == "bearish": signals.append("short")
        if direction == "bullish": signals.append("bullish")

        return {
            "score": final_score,
            "score_class": (
                "critical" if final_score >= 80 else
                "high"     if final_score >= 60 else
                "medium"   if final_score >= 40 else "low"
            ),
            "breakdown": {
                "engagement": eng_score,
                "ticker":     tick_score,
                "dramatic":   drama_score,
                "policy":     policy_score,
            },
            "signals": signals,
            "tickers": tickers,
            "dramatic_keywords": drama_kws,
            "policy_keywords": policy_kws,
            "direction": direction,
            "engagement_spike": spike_mult,
        }


# ────────────────────────────────────────
# QUICK TEST
# ────────────────────────────────────────
if __name__ == "__main__":
    with open("config.json") as f:
        config = json.load(f)

    engine = ScoreEngine(config)

    test_text = (
        "I've studied FNMA and FMCC in detail. These stocks are massively underpriced. "
        "Under a conservatorship exit scenario, both could be worth 10x their current price. "
        "This is one of the best risk/reward setups I've seen in my career."
    )

    result = engine.score_post(
        text=test_text,
        author={"name": "Bill Ackman", "category": "hedge_fund", "credibility_weight": 1.0},
        post_metrics={"views": 8_400_000, "reposts": 41_200, "likes": 89_400, "replies": 12_100},
        author_averages={"avg_views": 178_723, "avg_reposts": 792, "avg_likes": 2352, "avg_replies": 417},
    )

    print("Score:", result["score"])
    print("Class:", result["score_class"])
    print("Breakdown:", result["breakdown"])
    print("Signals:", result["signals"])
    print("Tickers:", result["tickers"])
    print("Direction:", result["direction"])
    print("Dramatic KWs:", result["dramatic_keywords"])
