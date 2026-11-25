# Mudika PO website

A pre-order form for Mudika fundraising food sales. Customers choose items and submit an order. Admins manage pickup dates, menus and settings at `/admin`.

- **Database:** every order is saved in a database. It's a SQLite file on your computer, and Cloudflare D1 when the site is online.
- **Google Sheet:** each order is also copied to a Google Sheet so admins can work with it there.

## Folder guide

| Path | What's in it |
| --- | --- |
| `app.py` | Starts the site on your computer (`python app.py`) |
| `src/worker.py` | Starts the site on Cloudflare |
| `src/mudika/` | The app's code. Each file starts with a short description. |
| `src/mudika/templates/` | The HTML pages |
| `public/static/` | CSS, JavaScript and the logo |
| `google-apps-script/Code.gs` | The small script that adds orders to the Google Sheet |
| `wrangler.jsonc` | Cloudflare settings |

## Run it on your computer

1. Install the two packages the app needs (one time only):

   ```
   python -m pip install flask requests
   ```

2. Copy `.env.example` to a new file called `.env`, then set `ADMIN_PASSWORD` to a password of your choice.
3. Start the site:

   ```
   python app.py
   ```

4. Open http://127.0.0.1:5000 to see the customer page, and http://127.0.0.1:5000/admin to see the admin page.

Your local data is saved in `instance/mudika.sqlite3`. To start fresh, stop the app and delete that file. The `instance/` folder is never uploaded to GitHub.

## First-time admin setup

1. Go to `/admin` and log in.
2. Under **Site settings**, fill in the **E-transfer email** and **Contact info**.
3. Create a pickup date, then open it with **Manage**. Set the close date and the location, and add menu items.
4. Click **Set as customer pickup date** to show that menu to customers.

Customers can order until the end of the close date (Toronto time). After that, the order page says orders are closed.

## Connect the Google Sheet

The website sends each new order to a small Google Apps Script attached to your spreadsheet. The script adds the rows. You don't need Google Cloud keys for this.

**Columns:**

| Columns | What goes there |
| --- | --- |
| A–G | Same layout as before: name, item, quantity, (blank), (blank), "Web form - MM DD", line total |
| H | Phone |
| I | Payment |
| J | Additional info |
| K | Pickup date |
| L | Order reference |

**Steps:**

1. Open the spreadsheet and go to **Extensions → Apps Script**.
2. Delete what's there, paste in everything from `google-apps-script/Code.gs`, and change `SECRET` to a long random phrase. Save.
3. Click **Deploy → New deployment**. Choose the type **Web app** and set:
   - **Execute as:** Me
   - **Who has access:** Anyone

   Then click **Deploy** and allow access when Google asks.
4. Copy the **Web app URL**. It ends in `/exec`.
5. In `.env` (on your computer) and in your Cloudflare secrets (online), set:
   - `SHEETS_WEBHOOK_URL` to the Web app URL
   - `SHEETS_WEBHOOK_SECRET` to the same phrase you used in the script

If the sheet is ever unreachable, orders are still saved in the database. The admin page then shows **Copy missing orders to Google Sheet**, which sends them over later. Orders that are already in the sheet are skipped, so pressing it twice is safe.

If you edit the script later, update the existing deployment: **Deploy → Manage deployments → Edit → New version**. That way the URL stays the same.

## Deploy to Cloudflare (one-time setup)

1. **Create the database.** In the Cloudflare dashboard, go to **Storage & Databases → D1 → Create**. Name it `mudika-po`, then copy its **Database ID** into `wrangler.jsonc`, replacing `REPLACE-WITH-YOUR-D1-DATABASE-ID`. Commit and push that change. The tables are created automatically the first time the site runs.
2. **Connect GitHub.** Go to **Workers & Pages → Create → Import a repository** and pick this repo. Set:
   - **Deploy command:** `pip install uv && uv run pywrangler deploy`
   - **Non-production branch deploy command:** `pip install uv && uv run pywrangler versions upload`

     This gives every branch its own preview link.
3. **Add the secrets.** Open the Worker and go to **Settings → Variables and Secrets**. Add each of these as a **Secret**:
   - `ADMIN_PASSWORD`
   - `FLASK_SECRET_KEY` (any long random text, 40+ characters)
   - `SHEETS_WEBHOOK_URL`
   - `SHEETS_WEBHOOK_SECRET`
4. Push to `main` (or merge a pull request), and Cloudflare deploys automatically. If a build fails, the log is under the Worker's **Deployments** tab.

### Testing the Cloudflare version on your computer (optional)

This needs [uv](https://docs.astral.sh/uv/) and [Node.js](https://nodejs.org/) installed. Put your secrets in a `.dev.vars` file, which uses the same format as `.env`. Then run:

```
uv run pywrangler dev
```
