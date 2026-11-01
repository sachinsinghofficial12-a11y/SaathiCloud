import os, re, hmac, uuid, hashlib, logging, secrets
from functools import wraps
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, UniqueConstraint
from groq import Groq
from ddgs import DDGS
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SaathiCloud")

app = Flask(__name__)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SAATHI_API_KEY = os.getenv("SAATHI_API_KEY", "").strip()
app.secret_key = os.getenv("FLASK_SECRET_KEY", "").strip() or SAATHI_API_KEY or os.urandom(32).hex()
app.config.update(
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.getenv("RENDER")),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///saathi.db"
db = SQLAlchemy(app)

ACTIVE_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
OWNER_ID = "owner"
SAATHI_OWNER_PASSWORD_HASH = os.getenv("SAATHI_OWNER_PASSWORD_HASH", "").strip()
SAATHI_OWNER_PIN_HASH = os.getenv("SAATHI_OWNER_PIN_HASH", "").strip()

SYSTEM_PROMPT = """
IDENTITY & RELATIONSHIP
Tum Saathi ho — Sachin Sir ke personal AI assistant aur friendly digital companion. Tumhara kaam sirf robotic answers dena nahi, balki user ki baat, mood, context aur actual intention samajhkar naturally conversation karna hai.

LANGUAGE & TONE
- User jis language/style mein baat kare, usi mein reply karo. Hindi Roman/Hinglish preferred hai jab user Hinglish use kare.
- Hamesha respectful raho; user ko 'aap' kaho, 'tu' mat kaho.
- 'Sachin Sir' ko har reply mein repeat mat karo. Kabhi-kabhi naturally use karo; har sentence mein naam lagana robotic lagta hai.
- Dost ki tarah warm, relaxed, clear aur genuine raho. Zarurat par halka humour/emojis use kar sakte ho, lekin overacting ya fake excitement nahi.
- User ki baat ko unnecessarily formal, lecture, motivational speech, ya long list mein convert mat karo.

UNDERSTAND INTENT & CONTEXT
- Sirf literal words nahi, poori baat ka matlab samjho. Previous messages ka context use karo aur follow-up ko usi context se jodo.
- Agar user short message, slang, typo, incomplete sentence, emoji ya reaction bheje, toh context se likely intent samajhne ki koshish karo. Jab meaning clear ho, seedha relevant reply do; baar-baar clarification mat maango.
- Agar ambiguity se answer materially change hota hai, toh ek chhota, natural clarification question poochho.
- Emoji ko context ke saath samjho. Example: 🙏 ka common Unicode/English name 'Folded Hands' hai; conversation mein iska matlab namaste, thanks, please/request, gratitude ya respect ho sakta hai. 😂 laughter, ❤️ love/affection, 🥺 pleading/tender emotion, 🤝 handshake/agreement. User emoji ka naam poochhe toh naam batao; sirf emoji bheje toh uske context ke hisaab se respond karo. Har emoji ko dictionary entry ki tarah explain mat karo.
- User agar 'haan', 'nahi', 'achha', 'kyun', 'same', 'isko', 'ye' jaise short follow-up bheje, toh conversation history se referent samjho.

ANSWER STYLE
- Pehle exact sawaal ka direct jawab do. Simple sawaal ka short, natural answer; detailed explanation sirf jab user maange ya zaroori ho.
- Ek hi baat ko repeat mat karo. Unsolicited numbered lists, headings aur generic closing offers avoid karo.
- User practical kaam maange toh usable output do; unnecessary theory mat do.
- Agar user casual chat kar raha hai, toh casual conversation karo — har baat ko task ya lesson mat banao.
- Agar user upset/confused ho, pehle calmly acknowledge karo aur phir useful next step do.

HONESTY & SAFETY
- Current facts ko live evidence ke bina confirmed mat batao. Uncertainty clearly batao; fake sources, dates, links, actions ya capabilities invent mat karo.
- User ka surname, company, designation, phone, email ya anya personal details kabhi invent mat karo. Missing ho toh poochho ya placeholder use karo.
- Private information ko bina zarurat repeat mat karo. User ke kehne par bhi passwords/API keys chat mein maangne ki zarurat nahi.
- Tumhara naam Saathi hai. Tum AI ho; apne aap ko insaan hone ka claim mat karo.
"""
VERIFIER_PROMPT = """
Available evidence ke saath draft answer check karo. Unsupported facts hatao ya qualify karo.
Evidence insufficient ho to uncertainty batao. Useful answer preserve karo.
Sirf corrected final answer return karo.
"""

class Conversation(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(36), db.ForeignKey("conversation.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PersonalMemory(db.Model):
    __tablename__ = "personal_memory"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.String(50), nullable=False, default=OWNER_ID)
    memory_key = db.Column(db.String(100), nullable=False)
    memory_value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("owner_id", "memory_key", name="unique_owner_memory"),)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.String(50), nullable=False, default=OWNER_ID, index=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DeviceToken(db.Model):
    __tablename__ = "device_tokens"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.String(50), nullable=False, default=OWNER_ID, index=True)
    device_name = db.Column(db.String(120), nullable=False, default="Android device")
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)

class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(64), nullable=False, unique=True)
    failed_count = db.Column(db.Integer, nullable=False, default=0)
    window_started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    locked_until = db.Column(db.DateTime, nullable=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.String(50), nullable=False, default=OWNER_ID, index=True)
    title = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text, default="")
    due_at = db.Column(db.String(80), default="")
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# Authentication: browser sessions, Android device tokens, or legacy Windows X-API-Key.
def _token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def require_api_key(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        if session.get("authenticated") is True:
            return function(*args, **kwargs)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            raw_token = auth[7:].strip()
            if raw_token:
                row = DeviceToken.query.filter_by(token_hash=_token_digest(raw_token), revoked_at=None).first()
                if row:
                    row.last_used_at = datetime.utcnow()
                    db.session.commit()
                    return function(*args, **kwargs)
            return jsonify({"error": "Device session expired or revoked. Please sign in again."}), 401
        if not SAATHI_API_KEY:
            return jsonify({"error": "Server API key is not configured."}), 500
        provided = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided, SAATHI_API_KEY):
            return jsonify({"error": "Unauthorized access."}), 401
        return function(*args, **kwargs)
    return decorated

@app.post("/api/auth/login")
def android_device_login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Valid JSON body required."}), 400
    password = data.get("password", "")
    pin = data.get("pin", "")
    device_name = str(data.get("device_name", "Android device")).strip()[:120] or "Android device"
    if not isinstance(password, str) or not isinstance(pin, str):
        return jsonify({"error": "Invalid credentials format."}), 400
    if not re.fullmatch(r"[0-9]{6}", pin):
        return jsonify({"error": "PIN exactly 6 digits ka hona chahiye."}), 400
    if not SAATHI_OWNER_PASSWORD_HASH or not SAATHI_OWNER_PIN_HASH:
        return jsonify({"error": "Android owner login abhi server par configure nahi hai."}), 503

    ip = (request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown")[:64]
    attempt = LoginAttempt.query.filter_by(ip_address=ip).first()
    now = datetime.utcnow()
    if attempt and attempt.locked_until and attempt.locked_until > now:
        seconds = max(1, int((attempt.locked_until - now).total_seconds()))
        return jsonify({"error": "Bahut zyada galat attempts. Kuch der baad try karein.", "retry_after_seconds": seconds}), 429
    if attempt and now - attempt.window_started_at > timedelta(minutes=15):
        attempt.failed_count = 0
        attempt.window_started_at = now
        attempt.locked_until = None

    valid_password = check_password_hash(SAATHI_OWNER_PASSWORD_HASH, password)
    valid_pin = check_password_hash(SAATHI_OWNER_PIN_HASH, pin)
    if not (valid_password and valid_pin):
        if not attempt:
            attempt = LoginAttempt(ip_address=ip, failed_count=0, window_started_at=now)
            db.session.add(attempt)
        attempt.failed_count += 1
        if attempt.failed_count >= 5:
            attempt.locked_until = now + timedelta(minutes=15)
        db.session.commit()
        return jsonify({"error": "Password ya PIN galat hai."}), 401

    if attempt:
        db.session.delete(attempt)
    raw_token = secrets.token_urlsafe(48)
    row = DeviceToken(device_name=device_name, token_hash=_token_digest(raw_token))
    db.session.add(row)
    db.session.commit()
    return jsonify({"success": True, "access_token": raw_token, "token_type": "Bearer", "device_name": device_name}), 200

@app.post("/api/auth/logout")
@require_api_key
def android_device_logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        row = DeviceToken.query.filter_by(token_hash=_token_digest(auth[7:].strip()), revoked_at=None).first()
        if row:
            row.revoked_at = datetime.utcnow()
            db.session.commit()
    return jsonify({"success": True})

@app.get("/")
def home():
    return redirect(url_for("assistant" if session.get("authenticated") else "login"))

@app.get("/login")
def login():
    if session.get("authenticated") is True:
        return redirect(url_for("assistant"))
    return render_template("login.html")

@app.post("/login")
def login_submit():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Valid JSON body required."}), 400
    password = data.get("password", "")
    if not isinstance(password, str):
        return jsonify({"error": "Invalid password format."}), 400
    if not SAATHI_API_KEY:
        return jsonify({"error": "Server login is not configured."}), 500
    if not hmac.compare_digest(password, SAATHI_API_KEY):
        return jsonify({"error": "Incorrect password."}), 401
    session.clear()
    session["authenticated"] = True
    session.permanent = True
    return jsonify({"success": True, "redirect": url_for("assistant")})

@app.get("/assistant")
def assistant():
    if session.get("authenticated") is not True:
        return redirect(url_for("login"))
    return render_template("index.html")

@app.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})

# Personal memory
def save_personal_memory(memory_key, memory_value):
    memory_value = memory_value.strip()
    if not memory_key or not memory_value:
        return False
    try:
        item = PersonalMemory.query.filter_by(owner_id=OWNER_ID, memory_key=memory_key).first()
        if item:
            item.memory_value = memory_value
            item.updated_at = datetime.utcnow()
        else:
            db.session.add(PersonalMemory(owner_id=OWNER_ID, memory_key=memory_key, memory_value=memory_value))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        logger.exception("Memory save failed")
        return False

def remember_user_information(command):
    command = command.strip()
    if re.search(r"^\s*mera\s+naam\s+(kya|kaun)\b", command, re.I):
        return False
    match = re.search(r"^\s*mera\s+naam\s+(?!kya\b|kaun\b)([A-Za-z][A-Za-z .'-]{0,49}?)\s+hai\b", command, re.I)
    if match:
        return save_personal_memory("name", match.group(1).strip())
    pattern = r"\b(?:yaad\s+rakh(?:o|na)?|remember\s+(?:this|that|it)|save\s+(?:this|that|it))\b"
    if not re.search(pattern, command, re.I):
        return False
    cleaned = re.sub(pattern, "", command, flags=re.I)
    cleaned = re.sub(r"\b(?:please|ise|isko|yeh|this|that)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^[\s,.:;-]+|[\s,.:;-]+$", "", cleaned)
    if not cleaned:
        return False
    key = hashlib.sha256(cleaned.lower().encode("utf-8")).hexdigest()[:24]
    return save_personal_memory("note_" + key, cleaned)

def build_memory_context():
    try:
        items = PersonalMemory.query.filter_by(owner_id=OWNER_ID).order_by(PersonalMemory.updated_at.desc()).limit(50).all()
        if not items:
            return None
        return "SAVED PERSONAL MEMORIES ABOUT THE USER:\n" + "\n".join(f"- {x.memory_value}" for x in items) + "\nUse only when relevant; do not invent details."
    except Exception:
        logger.exception("Memory read failed")
        return None

# Conversation history
def get_or_create_conversation(conversation_id=None):
    if conversation_id:
        try:
            cid = str(uuid.UUID(conversation_id))
            item = db.session.get(Conversation, cid)
            if item:
                return item
        except (ValueError, TypeError, AttributeError):
            pass
    item = Conversation(id=str(uuid.uuid4()))
    db.session.add(item)
    db.session.commit()
    return item

def get_conversation_history(conversation_id, limit=12):
    items = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at.desc()).limit(limit).all()
    items.reverse()
    return [{"role": x.role, "content": x.content} for x in items]

def save_exchange(conversation_id, user_message, assistant_message):
    try:
        db.session.add_all([
            Message(conversation_id=conversation_id, role="user", content=user_message),
            Message(conversation_id=conversation_id, role="assistant", content=assistant_message)
        ])
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Conversation save failed")

# Search and evidence
def search_web(query, max_results=8):
    """Search the web with DDGS. Try news search first for news queries, then text search."""
    results = []
    try:
        with DDGS() as ddgs:
            if re.search(r"\\b(news|samachar|khabar)\\b", query, re.I):
                try:
                    for item in ddgs.news(query, region="in-en", max_results=max_results):
                        url = item.get("url") or item.get("href") or ""
                        if url.startswith("https://"):
                            results.append({
                                "title": item.get("title", ""),
                                "url": url,
                                "snippet": item.get("body", "") or item.get("excerpt", ""),
                                "date": item.get("date", "") or item.get("published", "")
                            })
                except Exception:
                    logger.exception("DDGS news search failed; trying text search")

            if not results:
                for item in ddgs.text(query, region="in-en", max_results=max_results):
                    url = item.get("href", "") or item.get("url", "")
                    if url.startswith("https://"):
                        results.append({
                            "title": item.get("title", ""),
                            "url": url,
                            "snippet": item.get("body", "") or item.get("description", ""),
                            "date": item.get("date", "")
                        })
    except Exception:
        logger.exception("Web search failed")

    # Remove duplicate URLs while preserving search ranking.
    unique = []
    seen = set()
    for item in results:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    logger.info("Web search returned %s results for query: %s", len(unique), query[:160])
    return unique[:max_results]

def needs_live_search(command):
    patterns = [
        r"\b(latest|today|current|recent|live|now)\b",
        r"\b(weather|news|cricket|score|match|price)\b",
        r"\b(aaj|abhi|taaza|mausam|samachar)\b",
        r"\b(2026|2027)\b"
    ]
    return any(re.search(p, command, re.I) for p in patterns)

def fetch_bbc_article(url):
    try:
        host = urlparse(url).hostname
        if host not in ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"):
            return ""
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 SaathiCloud/1.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        return "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))[:7000]
    except Exception:
        logger.exception("BBC article fetch failed")
        return ""

def add_bbc_article_content(results):
    for item in results:
        host = urlparse(item["url"]).hostname or ""
        if host.endswith("bbc.com") or host.endswith("bbc.co.uk"):
            article = fetch_bbc_article(item["url"])
            if article:
                item["article_content"] = article
    return results

def verify_answer_with_evidence(question, answer, evidence):
    if not groq_client or not evidence:
        return answer
    try:
        result = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[
                {"role": "system", "content": VERIFIER_PROMPT},
                {"role": "user", "content": f"Question:\n{question}\n\nEvidence:\n{evidence}\n\nDraft answer:\n{answer}"}
            ],
            temperature=0.1,
            max_tokens=1500
        )
        corrected = result.choices[0].message.content
        return corrected.strip() if corrected else answer
    except Exception:
        logger.exception("Answer verification failed")
        return answer

def quick_reply(command):
    lower = command.lower()
    if any(w in lower for w in ["time", "samay", "kitne baje"]):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return "Abhi India mein " + now.strftime("%I:%M %p") + " baj rahe hain."
    if any(w in lower for w in ["date", "tarikh", "aaj ki date"]):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return "Aaj ki date " + now.strftime("%d %B %Y") + " hai."
    return None

@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "connected", "model": ACTIVE_MODEL}), 200
    except Exception:
        db.session.rollback()
        logger.exception("Health check failed")
        return jsonify({"status": "error", "database": "disconnected"}), 503

def process_ai_command(data):
    if not groq_client:
        return jsonify({"error": "Groq API key is not configured."}), 500
    if not isinstance(data, dict):
        return jsonify({"error": "Valid JSON body required."}), 400

    user_command = data.get("command", "")
    if not isinstance(user_command, str):
        return jsonify({"error": "Command must be text."}), 400
    user_command = user_command.strip()
    if not user_command:
        return jsonify({"error": "Command cannot be empty."}), 400
    if len(user_command) > 8000:
        return jsonify({"error": "Command is too long."}), 413

    try:
        conversation = get_or_create_conversation(data.get("conversation_id"))
        cid = conversation.id
        memory_saved = remember_user_information(user_command)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        memory_context = build_memory_context()
        if memory_context:
            messages.append({"role": "system", "content": memory_context})
        messages.extend(get_conversation_history(cid))

        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        messages.append({
            "role": "system",
            "content": (
                f"Current date in India: {now.strftime('%d %B %Y')}\\n"
                f"Current time in India: {now.strftime('%I:%M %p')}\\n"
                "Use this for date/time questions. Do not invent personal details."
            )
        })

        # IMPORTANT: perform live search before any quick date/time response.
        live_search_required = needs_live_search(user_command)
        instant = quick_reply(user_command)
        if instant and not live_search_required:
            save_exchange(cid, user_command, instant)
            return jsonify({
                "reply": instant,
                "conversation_id": cid,
                "model": ACTIVE_MODEL,
                "memory_saved": memory_saved
            }), 200

        results = []
        if live_search_required:
            search_query = user_command
            if re.search(r"\\b(news|samachar|khabar)\\b", user_command, re.I):
                search_query = (
                    "India latest news today national politics business technology"
                )

            results = add_bbc_article_content(search_web(search_query, max_results=8))
            if results:
                evidence = "\\n\\n".join(
                    f"Title: {x.get('title', '')}\\n"
                    f"URL: {x['url']}\\n"
                    f"Publication date (if provided by search): {x.get('date', '')}\\n"
                    f"Snippet: {x.get('snippet', '')}\\n"
                    f"Article: {x.get('article_content', '')}"
                    for x in results
                )
                messages.append({
                    "role": "system",
                    "content": (
                        "LIVE WEB SEARCH RESULTS follow. Answer current factual "
                        "questions using this evidence. For each news item give "
                        "headline, concise summary, publication date only when "
                        "the evidence provides one, and the exact source URL. "
                        "Never invent dates, headlines, facts, or URLs. If the "
                        "evidence is insufficient, say so.\\n\\n" + evidence
                    )
                })
            else:
                messages.append({
                    "role": "system",
                    "content": (
                        "Live web search failed or returned no results. Do not "
                        "pretend that current information was verified. Clearly "
                        "tell the user that the internet search did not return results."
                    )
                })

        messages.append({"role": "user", "content": user_command})
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=messages,
            temperature=0.65,
            max_tokens=3000
        )
        reply = response.choices[0].message.content or (
            "Maaf kijiye, response generate nahi ho paya."
        )

        if results:
            evidence = "\\n\\n".join(
                f"{x.get('title', '')}\\n{x['url']}\\n"
                f"{x.get('date', '')}\\n{x.get('snippet', '')}\\n"
                f"{x.get('article_content', '')}"
                for x in results
            )
            reply = verify_answer_with_evidence(user_command, reply, evidence)

            allowed_urls = {x["url"] for x in results}
            for url in re.findall(r"https?://[^\\s)\\]>\\\"']+", reply):
                clean = url.rstrip(".,;")
                if clean not in allowed_urls:
                    reply = reply.replace(url, "[Unverified source link removed]")

        save_exchange(cid, user_command, reply)
        return jsonify({
            "reply": reply,
            "conversation_id": cid,
            "model": ACTIVE_MODEL,
            "memory_saved": memory_saved
        }), 200

    except Exception:
        db.session.rollback()
        logger.exception("Command processing failed")
        return jsonify({
            "error": "Saathi ko request process karne mein dikkat hui. Please try again."
        }), 500

@app.post("/command")
@require_api_key
def command():
    return process_ai_command(request.get_json(silent=True))

@app.post("/web-command")
@require_api_key
def web_command():
    return process_ai_command(request.get_json(silent=True))


# ---------------- Saathi workspace APIs ----------------
def _owner_id():
    # Current deployment is single-owner. Authentication is enforced by decorators.
    return OWNER_ID

@app.get("/api/notes")
@require_api_key
def list_notes():
    rows = Note.query.filter_by(owner_id=_owner_id()).order_by(Note.updated_at.desc()).limit(200).all()
    return jsonify({"notes": [{"id": n.id, "title": n.title, "content": n.content,
        "updated_at": n.updated_at.isoformat() if n.updated_at else ""} for n in rows]})

@app.post("/api/notes")
@require_api_key
def create_note():
    data = request.get_json(silent=True) or {}
    title, content = str(data.get("title", "")).strip(), str(data.get("content", "")).strip()
    if not title or not content:
        return jsonify({"error": "Title aur content dono zaroori hain."}), 400
    if len(title) > 200 or len(content) > 20000:
        return jsonify({"error": "Note bahut lamba hai."}), 413
    row = Note(owner_id=_owner_id(), title=title, content=content)
    db.session.add(row); db.session.commit()
    return jsonify({"success": True, "id": row.id}), 201

@app.delete("/api/notes/<int:note_id>")
@require_api_key
def delete_note(note_id):
    row = Note.query.filter_by(id=note_id, owner_id=_owner_id()).first_or_404()
    db.session.delete(row); db.session.commit()
    return jsonify({"success": True})

@app.get("/api/tasks")
@require_api_key
def list_tasks():
    rows = Task.query.filter_by(owner_id=_owner_id()).order_by(Task.completed.asc(), Task.created_at.desc()).limit(300).all()
    return jsonify({"tasks": [{"id": t.id, "title": t.title, "details": t.details,
        "due_at": t.due_at, "completed": t.completed} for t in rows]})

@app.post("/api/tasks")
@require_api_key
def create_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify({"error": "Task title zaroori hai."}), 400
    if len(title) > 200:
        return jsonify({"error": "Task title 200 characters se chhota rakhein."}), 400
    row = Task(owner_id=_owner_id(), title=title,
        details=str(data.get("details", ""))[:5000], due_at=str(data.get("due_at", ""))[:80])
    db.session.add(row); db.session.commit()
    return jsonify({"success": True, "id": row.id}), 201

@app.patch("/api/tasks/<int:task_id>")
@require_api_key
def update_task(task_id):
    row = Task.query.filter_by(id=task_id, owner_id=_owner_id()).first_or_404()
    data = request.get_json(silent=True) or {}
    if "completed" in data:
        row.completed = bool(data["completed"])
    if "title" in data:
        title = str(data["title"]).strip()
        if not title: return jsonify({"error": "Title empty nahi ho sakta."}), 400
        row.title = title[:200]
    db.session.commit()
    return jsonify({"success": True})

@app.delete("/api/tasks/<int:task_id>")
@require_api_key
def delete_task(task_id):
    row = Task.query.filter_by(id=task_id, owner_id=_owner_id()).first_or_404()
    db.session.delete(row); db.session.commit()
    return jsonify({"success": True})

@app.get("/api/settings")
@require_api_key
def get_settings():
    return jsonify({"active_model": ACTIVE_MODEL, "available_models": [
        "openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"
    ], "provider": "Groq"})

@app.post("/api/settings/model")
@require_api_key
def set_model():
    global ACTIVE_MODEL
    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()
    allowed = {"openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"}
    if model not in allowed:
        return jsonify({"error": "Model allowed list mein nahi hai."}), 400
    ACTIVE_MODEL = model
    return jsonify({"success": True, "active_model": ACTIVE_MODEL})

@app.post("/api/upload")
@require_api_key
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "File select kijiye."}), 400
    f = request.files["file"]
    name = secure_filename(f.filename or "")
    ext = Path(name).suffix.lower()
    if not name or ext not in {".txt", ".md", ".csv", ".pdf", ".docx", ".xlsx"}:
        return jsonify({"error": "Supported files: TXT, MD, CSV, PDF, DOCX, XLSX."}), 400
    raw = f.read()
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"error": "File 8 MB se chhoti honi chahiye."}), 413
    try:
        if ext in {".txt", ".md", ".csv"}:
            content = raw.decode("utf-8-sig", errors="replace")
        elif ext == ".pdf":
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(raw))
            content = "\n".join(page.extract_text() or "" for page in reader.pages[:40])
        elif ext == ".docx":
            from docx import Document as DocxDocument
            import io
            doc = DocxDocument(io.BytesIO(raw))
            content = "\n".join(p.text for p in doc.paragraphs)
        else:
            from openpyxl import load_workbook
            import io
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            chunks = []
            for ws in wb.worksheets[:8]:
                chunks.append(f"Sheet: {ws.title}")
                for row in ws.iter_rows(max_row=300, values_only=True):
                    vals = [str(v) if v is not None else "" for v in row]
                    if any(vals): chunks.append(" | ".join(vals))
            content = "\n".join(chunks)
        content = content[:30000]
        if not content.strip():
            return jsonify({"error": "File se readable text nahi mila."}), 422
        return jsonify({"filename": name, "text": content,
            "message": "File read ho gayi. Is text ko chat mein question ke saath bhej sakte hain."})
    except ImportError as e:
        logger.exception("Document dependency missing")
        return jsonify({"error": "Document reader dependency missing. requirements install karein."}), 500
    except Exception:
        logger.exception("Document extraction failed")
        return jsonify({"error": "File read nahi ho payi. File format/password check karein."}), 422

@app.get("/api/memory")
@require_api_key
def list_memory():
    rows = PersonalMemory.query.filter_by(owner_id=OWNER_ID).order_by(PersonalMemory.updated_at.desc()).limit(100).all()
    return jsonify({"memories": [{"id": x.id, "key": x.memory_key, "value": x.memory_value} for x in rows]})

@app.delete("/api/memory/<int:memory_id>")
@require_api_key
def delete_memory(memory_id):
    row = PersonalMemory.query.filter_by(id=memory_id, owner_id=OWNER_ID).first_or_404()
    db.session.delete(row); db.session.commit()
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
