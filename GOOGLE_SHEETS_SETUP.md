# Google Sheets order integration

Customer orders are appended to spreadsheet `1BBk_33lKRMkxpFKyY3-lx-mpGxGWiPG7kBVqNNoNnoA`, one row per menu item with a nonzero quantity:

- A: customer name
- B: menu name
- C: quantity
- D-E: blank (reserved; no mapping was specified)
- F: `Web form - MM DD`, using the date the order is submitted
- G: unit price multiplied by quantity

## Configure access

1. In Google Cloud Console, create or select a project and enable the Google Sheets API.
2. Create a service account and download its JSON key.
3. Share the spreadsheet with the service account's `client_email` and grant Editor access.
4. Save the JSON key as `instance/google-service-account.json`. The `instance/` directory is git-ignored; do not commit or share the key.
5. In the same PowerShell session used to start Flask, set the credential path:

   ```powershell
   $env:GOOGLE_APPLICATION_CREDENTIALS = (Resolve-Path "instance/google-service-account.json").Path
   ```

6. Optionally set the worksheet tab name if the target tab is not the first tab:

   ```powershell
   $env:GOOGLE_SHEETS_WORKSHEET = "Orders"
   ```

7. Install dependencies and start the app:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

If `GOOGLE_SHEETS_WORKSHEET` is not set, the first worksheet tab is used. An order is only counted in the website's local stock data after the append request succeeds. Keep service-account keys out of source control and use your hosting provider's secret manager in production.
