SAATHI CLOUD AI - UPDATED PROJECT

Included:
- Existing Flask + Groq assistant, browser login, PostgreSQL/SQLite, conversation history and personal memory.
- Persistent Notes and Tasks APIs with UI panels.
- Memory viewer.
- Groq model selection (only the listed Groq-hosted model IDs).
- TXT, MD, CSV, PDF, DOCX and XLSX text extraction (8 MB limit).
- Existing Hindi/Hinglish browser voice input/output.

SETUP:
1. Backup your current SaathiCloud folder.
2. Copy app.py, requirements.txt and templates folder from this package into your project.
3. Keep your existing .env locally; DO NOT replace or upload it.
4. Install dependencies: pip install -r requirements.txt
5. Run locally: python app.py
6. Test login, chat, notes, tasks, memory, model selection and file upload.
7. Only after local testing, commit and push to GitHub so Render redeploys.

ENVIRONMENT VARIABLES (keep existing values):
GROQ_API_KEY=your existing Groq key
GROQ_MODEL=openai/gpt-oss-120b
SAATHI_API_KEY=your existing login/API key
FLASK_SECRET_KEY=your existing long random secret
DATABASE_URL=your existing Render PostgreSQL URL (Render only)
Optional: SAATHI_CLOUD_URL for desktop client.

IMPORTANT LIMITS:
- This is a single-owner personal assistant, not a multi-user account system.
- Model switching currently switches among Groq model IDs only. OpenAI/Gemini providers are not wired yet.
- Reminders are stored as tasks, but background notifications/scheduler are not included yet.
- Browser speech uses the device/browser voices; premium neural voice is deferred.
- Uploaded document text is extracted and passed into the chat input; it is not permanently stored.
- Please test locally before deploying. Existing DB tables are preserved; new tables are created automatically.
