# WhatsApp Delegation App — Setup Guide

## 1. Run the Database Migration

Connect to the MariaDB server and run:

```
mysql -h 87.106.200.69 -P 3306 -u emarket_bot -p emarketing_bot < database/migrations.sql
```

Or paste the contents of `database/migrations.sql` into the Adminer UI at
http://87.106.200.69/adminer/?server=87.106.200.69%3A3306 (use MySQL/MariaDB, port 3306 — not 5433).

---

## 2. Backend (FastAPI)

### Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your real values (OpenAI key, Google Drive folder ID, etc.)

uvicorn app.main:app --reload --port 8080
```

### Google Service Account (for Drive uploads)

1. Go to Google Cloud Console → IAM → Service Accounts → Create
2. Grant it the **"Google Drive API"** scope
3. Download the JSON key → save as `backend/google_service_account.json`
4. Share your target Drive folder with the service account email

### Deploy to Google Cloud Run

```bash
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT/wa-delegation-api
gcloud run deploy wa-delegation-api \
  --image gcr.io/YOUR_PROJECT/wa-delegation-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "$(cat .env | tr '\n' ',')"
```

### Set WhatsApp Webhook

In your whapi.cloud dashboard, set the webhook URL to:
```
https://YOUR_CLOUD_RUN_URL/webhook
```

---

## 3. Frontend (Next.js)

### Local development

```bash
cd frontend
npm install

cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8080

npm run dev
# Open http://localhost:3000
```

### Deploy to Vercel

```bash
npx vercel
# Set environment variable:
# NEXT_PUBLIC_API_URL = https://YOUR_CLOUD_RUN_URL
```

---

## 4. How It Works

### Text task via WhatsApp
Send a message starting with `/task`:
```
/task Assign website redesign to John by Friday, high priority, client: Acme Corp
```
→ OpenAI extracts all fields → saved to `tasks` table

### Voice message
Send any voice note
→ Downloaded from WhatsApp → Whisper transcribes → OpenAI extracts fields
→ Audio uploaded to Google Drive → Drive link saved in `source_link` column

### Frontend
- Opens at your Vercel URL
- Shows all tasks in a filterable table
- Auto-refreshes every 30 seconds

---

## 5. Columns Reference

| Column | Source |
|---|---|
| Timestamp | When webhook received the message |
| Task ID | Auto-generated `TASK-0001` |
| Task Description | OpenAI extracted |
| Assigned By | WhatsApp sender name |
| Assignee Contact | WhatsApp sender number |
| Assigned To | OpenAI extracted |
| Employee Email ID | OpenAI extracted |
| Target Date | OpenAI extracted |
| Priority | OpenAI classified |
| Approval Needed | OpenAI detected |
| Client Name | OpenAI extracted |
| Department | OpenAI extracted |
| Assigned Name | OpenAI extracted |
| Assigned Email ID | OpenAI extracted |
| Comments | OpenAI extracted |
| Source Link | Google Drive URL (voice) or empty (text) |
