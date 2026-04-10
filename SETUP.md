# MarketSentinel — Setup Guide

## What You Have

```
market_sentinel/
├── dashboard.html          ← Open this in your browser (works immediately in demo mode)
├── SETUP.md                ← This file
├── backend/
│   ├── config.json         ← Your API keys + watchlist + scoring weights
│   ├── fetch_posts.py      ← X API fetcher (runs every 5 min)
│   ├── score_engine.py     ← Scoring logic (no dependencies needed)
│   └── requirements.txt    ← Python packages
└── data/
    ├── posts.json          ← Live data (written by backend, read by dashboard)
    └── sentinel.log        ← Run log
```

---

## Step 1 — Open the Dashboard (Demo Mode, no setup needed)

Just double-click `dashboard.html`. It will open in your browser with sample data
showing the full UI: post cards, scoring breakdowns, watchlist, trending tickers.

---

## Step 2 — Connect Live X (Twitter) Data

### 2a. Get X API Access
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Create a project and app
3. Apply for **Basic** access ($100/month) — this gives you 10,000 tweets/month read access
4. Copy your **Bearer Token** (for read-only access, this is all you need)

### 2b. Add Your Keys
Edit `backend/config.json` and replace the placeholder values:
```json
"api_keys": {
  "x_bearer_token": "AAAAAAAAAAAAAAAAAAAAAxx..."
}
```

### 2c. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2d. Run the Fetcher
```bash
# Run once (good for testing)
python fetch_posts.py

# Run continuously every 5 minutes (recommended)
python fetch_posts.py --loop

# Dry run — no API calls, just checks everything is working
python fetch_posts.py --test
```

The fetcher writes scored posts to `data/posts.json`. Refresh `dashboard.html`
to see live data.

---

## Step 3 — Connect Truth Social (Donald Trump)

Truth Social has no official API. Options:
1. **Manual**: Paste Trump's Truth posts directly into a `data/truth_manual.json` file.
   The dashboard will pick them up on next refresh.
2. **Browser Extension**: Future versions of this tool may include a browser-based
   monitor that watches the Truth Social web app.

---

## Step 4 — Customise Your Watchlist

Edit `backend/config.json` → `"watchlist"` section.

Each person needs:
- `"name"`: Display name
- `"handle"`: X username (without @)
- `"platform"`: `"x"` or `"truth"`
- `"category"`: `"hedge_fund"`, `"short_seller"`, `"macro"`, `"policy"`, or `"commentator"`
- `"credibility_weight"`: 0.6 to 1.0 (higher = score multiplied up)

To find a user's numeric X ID: https://tweeterid.com

---

## Step 5 — Tune Scoring Weights

Edit `backend/config.json` → `"scoring"` section.

Key parameters:
- `engagement.spike_tiers`: How many points a 10×/20× engagement spike is worth
- `ticker_mention.base_per_ticker`: Points per ticker mentioned
- `dramatic_claim.keywords`: Add your own high-signal phrases here
- `policy_signal.keywords`: Add policy/regulatory keywords to watch

---

## Suggested Watchlist (24 accounts)

| Name | Handle | Category | Why Watch |
|---|---|---|---|
| Bill Ackman | @BillAckman | Hedge Fund | Activist, major market calls (FNMA case study) |
| Michael Burry | @michaeljburry | Hedge Fund | Famous for 2008 short, cryptic posts move markets |
| Ray Dalio | @RayDalio | Hedge Fund | Bridgewater macro views, debt cycle analysis |
| Stan Druckenmiller | — | Hedge Fund | Legendary macro trader, rarely posts but high signal |
| David Einhorn | @GreenLightCap | Hedge Fund | Value investor, known short positions |
| Dan Loeb | @DanLoeb | Hedge Fund | Third Point activist campaigns |
| Jeffrey Gundlach | @TruthGundlach | Hedge Fund | "Bond King", rates & macro forecasts |
| Carl Icahn | @Carl_C_Icahn | Hedge Fund | Aggressive activist investor |
| Michael Saylor | @saylor | Hedge Fund | Bitcoin maximalist, MicroStrategy moves |
| Muddy Waters | @muddywatersre | Short Seller | High-impact short reports, often 20-40% drops |
| Hindenburg Research | @HindenburgRes | Short Seller | Major fraud allegations, immediate price impact |
| Citron Research | @CitronResearch | Short Seller | Active short commentary |
| Spruce Point Capital | @SprucePointCap | Short Seller | Activist short seller |
| Gotham City Research | @GothamCityRes | Short Seller | Deep-dive short reports |
| Donald Trump | @realDonaldTrump | Policy | Presidential decisions: tariffs, sanctions, sector impacts |
| Scott Bessent | @ScottBessent | Policy | Treasury Secretary, fiscal/FX policy |
| Mohamed El-Erian | @elerianm | Macro | Allianz chief economist, rates/Fed commentary |
| Nouriel Roubini | @Nouriel | Macro | "Dr. Doom", macro risk warnings |
| Larry Summers | @LHSummers | Policy | Former Treasury, influential on Fed/fiscal |
| Elon Musk | @elonmusk | Policy/Markets | DOGE, Tesla, regulatory signals |
| David Rosenberg | @EconguyRosie | Commentator | Macro bear, detailed economic analysis |
| Dan Ives | @DanIvesWedbush | Commentator | Tech analyst, widely followed for AAPL/EV calls |
| Jim Cramer | @jimcramer | Commentator | CNBC host — watch as a CONTRARIAN indicator |
| Harris Kupperman | @hkuppy | Commentator | Praetorian Capital, commodity/macro trades |

---

## Running Automatically (Scheduled)

### macOS / Linux (cron)
```bash
# Edit crontab
crontab -e

# Add this line to run every 5 minutes:
*/5 * * * * /usr/bin/python3 /path/to/market_sentinel/backend/fetch_posts.py >> /path/to/market_sentinel/data/cron.log 2>&1
```

### Windows (Task Scheduler)
1. Open Task Scheduler → Create Basic Task
2. Trigger: Every 5 minutes
3. Action: Start a program → `python.exe`
4. Arguments: `C:\path\to\market_sentinel\backend\fetch_posts.py`

---

## FAQ

**Q: The dashboard shows demo data, not live data.**
A: Run the Python backend (`python fetch_posts.py`) first to generate `data/posts.json`.
   Then reload `dashboard.html` in your browser.

**Q: I'm getting rate limit errors.**
A: The Basic X API tier allows ~10,000 reads/month. With 24 accounts at 5-min intervals,
   you'd use ~207,000 reads/month. Consider upgrading to Pro, or increase the fetch
   interval to 30 minutes (`"fetch_interval_minutes": 30` in config.json).

**Q: How do I add more people to the watchlist?**
A: Edit `backend/config.json` and add entries under the relevant category array.
   The dashboard will automatically pick them up.

**Q: Can I get email/SMS alerts for critical posts?**
A: The fetcher logs CRITICAL alerts to the console and log file. To add email/SMS,
   integrate with SendGrid (email) or Twilio (SMS) in `fetch_posts.py` at the
   alert section near line 130.
