# MarketSentinel — iPad / Anywhere Access Setup
## Using GitHub Pages (free, permanent URL)

Total time: ~15 minutes. Once done, your dashboard lives at:
`https://YOUR-USERNAME.github.io/market-sentinel/dashboard.html`

---

## STEP 1 — Install Git on your PC (if not already installed)
1. Go to https://git-scm.com/download/win
2. Download and install (all defaults are fine)
3. Open Command Prompt and type `git --version` to confirm it worked

---

## STEP 2 — Create a GitHub account and repository
1. Go to https://github.com and sign up for a free account
2. Click the **+** button → **New repository**
3. Name it: `market-sentinel`
4. Set it to **Public** (required for free GitHub Pages)
5. Do NOT tick "Add README" — leave it empty
6. Click **Create repository**
7. Copy your repo URL — it will look like:
   `https://github.com/YOUR-USERNAME/market-sentinel.git`

---

## STEP 3 — Set up the local git repo on your PC
Open **Command Prompt** and run these commands one by one:

```
cd C:\Users\Think\OneDrive\Claude\market_sentinel

git init
git add .
git commit -m "Initial MarketSentinel setup"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/market-sentinel.git
git push -u origin main
```

When prompted, sign in with your GitHub username and password.
(GitHub may ask you to use a Personal Access Token instead of password —
if so, go to GitHub → Settings → Developer Settings → Personal Access Tokens → Generate new token,
tick "repo" scope, copy the token and use it as your password.)

---

## STEP 4 — Enable GitHub Pages
1. Go to your repo on GitHub: `https://github.com/YOUR-USERNAME/market-sentinel`
2. Click **Settings** (top menu)
3. Click **Pages** (left sidebar)
4. Under "Source", select **Deploy from a branch**
5. Branch: **main** / Folder: **/ (root)**
6. Click **Save**
7. Wait 2 minutes, then visit:
   `https://YOUR-USERNAME.github.io/market-sentinel/dashboard.html`
   Your dashboard should be live!

---

## STEP 5 — Set up auto-push (live data updates every hour)
This makes the dashboard update automatically on your iPad after each hourly scan.

### 5a. Test the push script first
In Command Prompt:
```
C:\Users\Think\OneDrive\Claude\market_sentinel\push_to_github.bat
```
It should say "No changes to push" (that's fine — means it's working).

### 5b. Add to Windows Task Scheduler
1. Press **Windows + S**, search for **Task Scheduler**, open it
2. Click **Create Basic Task** (right panel)
3. Name: `MarketSentinel Push`
4. Trigger: **Daily** → set start time, then change recurrence
5. After creating, right-click the task → **Properties**
6. Go to **Triggers** tab → Edit → change to **Repeat task every: 1 hour**
7. Action: **Start a program**
8. Program: `C:\Users\Think\OneDrive\Claude\market_sentinel\push_to_github.bat`
9. Click OK

Now every hour: Cowork scan runs → writes live_data.js → batch script pushes to GitHub → iPad dashboard updates on next refresh.

---

## STEP 6 — Bookmark on your iPad
1. Open Safari or Chrome on iPad
2. Go to `https://YOUR-USERNAME.github.io/market-sentinel/dashboard.html`
3. Tap the **Share** button → **Add to Home Screen**
4. It will appear as an app icon on your iPad home screen

---

## How the hourly update cycle works

```
Every hour:
  [Cowork Scan] → searches X/Truth Social for posts
       ↓
  writes data/live_data.js to your OneDrive folder
       ↓
  [push_to_github.bat] → pushes live_data.js to GitHub (1-2 min delay)
       ↓
  GitHub Pages serves the updated file
       ↓
  [iPad Safari] → refresh dashboard → sees live posts ✅
```

---

## Troubleshooting

**Dashboard shows demo data on iPad**
→ The live_data.js hasn't been pushed yet. Wait for next hourly scan + push cycle, then refresh.

**git push asks for password every time**
→ Run this to save credentials: `git config --global credential.helper wincred`

**GitHub Pages shows 404**
→ Wait 5 minutes after enabling — Pages takes a moment to activate.
→ Make sure the repo is set to Public, not Private.

**iPad shows old data even after refreshing**
→ Safari caches aggressively. Force-refresh: hold Shift and tap Refresh in Safari.
→ Or open the URL in a new tab.
