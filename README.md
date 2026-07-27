# Breville Bambino Plus deal search

Checks a list of US retailers daily for the price of the Breville Bambino
Plus espresso machine (model BES500BSS), applies any coupon codes you know
about, and emails you a digest with the best effective price found. Runs
automatically via a scheduled GitHub Action - nothing needs to stay running
on your machine.

## How it works

1. `.github/workflows/deal-search.yml` runs daily at 13:00 UTC (8 AM Panama
   time) and on manual trigger.
2. It calls `src/deal_finder/main.py`, which:
   - fetches each product page listed in `config/retailers.yaml` and pulls
     the price out of the page's schema.org JSON-LD data (falls back to a
     regex price match if that's missing),
   - applies any matching codes from `config/coupons.json` to compute an
     "effective price" per retailer,
   - compares today's best price to the historical low in
     `data/price_history.json`,
   - writes `reports/latest_deals.md` and commits it + the updated history
     back to the repo,
   - emails you the same report.
3. Failures (a retailer blocking the request, page layout changing, etc.)
   are logged in the report instead of crashing the run - you'll still get
   results for whichever retailers succeeded.

## Required setup (one-time)

### 1. Email secrets

The email step needs SMTP credentials. Add these under **Settings → Secrets
and variables → Actions** in this repo:

| Secret | Example | Notes |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | |
| `SMTP_PORT` | `587` | |
| `SMTP_USER` | `youraccount@gmail.com` | |
| `SMTP_PASS` | *(app password)* | For Gmail: create a 16-character [App Password](https://myaccount.google.com/apppasswords) - your normal password won't work. |
| `EMAIL_TO` | `luife.cupas@gmail.com` | where the digest goes |
| `EMAIL_FROM` | `youraccount@gmail.com` | optional, defaults to `SMTP_USER` |

If these secrets aren't set, the run still completes and updates
`reports/latest_deals.md` - it just skips sending the email (and says so in
the Action log).

### 2. Turn on the schedule

Scheduled workflows are disabled on repos with no recent activity and on
forks by default. Push this branch / merge it to the default branch, then
confirm the workflow shows as enabled under the **Actions** tab. You can
also trigger it manually any time via **Actions → Breville Bambino Plus deal
search → Run workflow**.

## Important limitations (read this)

**Not every retailer can be reliably scraped.** Amazon, Walmart, Target and
Best Buy all run bot-detection (Akamai/PerimeterX/Cloudflare-style
protection) that can block plain HTTP requests outright - this is
especially true for requests coming from datacenter IPs like GitHub
Actions runners, which are commonly blacklisted. When I tested this script,
even fetching a single Amazon page from this dev environment came back as
an immediate 403. Expect some retailers to fail most days; the report will
tell you which ones and why. If a retailer that used to work starts failing
every day, either the site changed its page layout (update the parser) or
it's decided to block the runner (nothing to fix - just rely on the other
sources for that retailer).

**Because of that, Amazon is best covered separately, not by this script.**
Amazon specifically is the hardest site to scrape reliably. Instead of
fighting it, set up a free, purpose-built watch that already handles this
well:
- **camelcamelcamel**: https://camelcamelcamel.com/product/B07JVD78TT -
  create a free account and set a price watch; it emails you when Amazon's
  price drops, and shows full price history so you can tell if a "deal" is
  actually good.

**Coupons are hand-maintained, not auto-discovered.** Coupon-code sites
change too often and too unreliably to scrape sensibly. `config/coupons.json`
currently seeds two codes found via search in July 2026 (`PRESOFFER`,
`BREVFUTURE10`, both ~10% off, both unverified) - test any code at checkout
before trusting it, and update the file whenever you find a working one or
one stops working. A browser coupon-autofill extension (Honey, Capital One
Shopping, PayPal Honey, etc.) is a good complement for catching codes at
checkout that this file doesn't know about.

**"Best price" here means effective price after coupon, before shipping,
duties, and forwarding fees.** For your specific situation (buying to a US
forwarding address, then on to Panama), also factor in:
- Freight-forwarder shipping cost + Panama import duties, which can easily
  be 15-20%+ of item value and can make a "cheaper" US retailer end up
  costlier than a nominally higher-priced one with a lighter/smaller box.
- Some retailers flag orders going to known freight-forwarder addresses for
  fraud review and may delay or cancel them - using an address/name that
  matches your card billing info, and retailers your forwarder has a good
  track record with, reduces that risk. Your forwarding service may
  already have guidance on which retailers work smoothly.

## Customizing

- **Change retailers / product page URLs**: edit `config/retailers.yaml`.
- **Add/remove coupon codes**: edit `config/coupons.json`.
- **Change how often it runs**: edit the `cron:` line in
  `.github/workflows/deal-search.yml` ([crontab.guru](https://crontab.guru/)
  is handy for this - times are UTC).
- **Track a different color/variant**: swap in that variant's product URL
  per retailer in `config/retailers.yaml`.

## Running locally

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m deal_finder.main --no-email   # skip email, just print + write the report
PYTHONPATH=src python -m deal_finder.main               # full run, needs SMTP_* / EMAIL_* env vars set
```
