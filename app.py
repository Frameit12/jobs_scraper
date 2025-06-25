from flask import Flask, render_template, request, send_file, make_response, redirect
import pandas as pd
from io import BytesIO
from flask import Response
from scraper_logic import scrape_jobs
import json
from datetime import datetime
import os
import glob
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import smtplib
from email.message import EmailMessage
from zipfile import ZipFile
from openpyxl import Workbook
import os
import psycopg2
from sqlalchemy import create_engine, text
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session

# Database setup
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        engine = create_engine(database_url)
        return engine
    return None

def init_database():
    engine = get_db_connection()
    if engine:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    timestamp VARCHAR(50) NOT NULL,
                    criteria JSONB NOT NULL,
                    schedule VARCHAR(50) DEFAULT 'none',
                    last_run_date VARCHAR(50) DEFAULT ''
                )
            """))
            conn.commit()

def init_users_table():
    engine = get_db_connection()
    if engine:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Add email column to existing users table if it doesn't exist
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE
            """))
            
            # Add user_id column to saved_searches table
            conn.execute(text("""
                ALTER TABLE saved_searches 
                ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)
            """))
            conn.commit()

init_users_table()

def init_files_table():
    engine = get_db_connection()
    if engine:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS scheduled_files (
                    id SERIAL PRIMARY KEY,
                    search_name VARCHAR(255) NOT NULL,
                    user_id INTEGER REFERENCES users(id),
                    file_data BYTEA NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(search_name, user_id)
                )
            """))
            conn.commit()

init_files_table()


def init_password_reset_table():
    engine = get_db_connection()
    if engine:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

init_password_reset_table()

def generate_reset_token():
    import secrets
    return secrets.token_urlsafe(32)

def create_password_reset_token(user_id):
    engine = get_db_connection()
    if not engine:
        return None
    
    token = generate_reset_token()
    # Token expires in 1 hour
    from datetime import datetime, timedelta
    expires_at = datetime.now() + timedelta(hours=1)
    
    try:
        with engine.connect() as conn:
            # First, invalidate any existing tokens for this user
            conn.execute(text("""
                UPDATE password_reset_tokens 
                SET used = TRUE 
                WHERE user_id = :user_id AND used = FALSE
            """), {"user_id": user_id})
            
            # Create new token
            conn.execute(text("""
                INSERT INTO password_reset_tokens (user_id, token, expires_at)
                VALUES (:user_id, :token, :expires_at)
            """), {
                "user_id": user_id,
                "token": token,
                "expires_at": expires_at
            })
            conn.commit()
        return token
    except Exception as e:
        print(f"Error creating reset token: {e}")
        return None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-for-development')


HISTORY_FILE = "search_history.json"

# Define global results variable
last_results = []
last_search_name = "Job_Search"


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()
init_database()

def load_saved_searches():
    engine = get_db_connection()
    if not engine:
        return []
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name, timestamp, criteria, schedule, last_run_date 
                FROM saved_searches 
                WHERE user_id= :user_id
                ORDER BY id DESC 
                LIMIT 5
            """), {"user_id": get_current_user_id()})
            
            searches = []
            for row in result:
                search = {
                    "name": row[0],
                    "timestamp": row[1], 
                    "criteria": row[2],
                    "schedule": row[3] or "none",
                    "last_run_date": row[4] or ""
                }
                searches.append(search)
            return searches
    except Exception as e:
        print(f"Database error in load_saved_searches: {e}")
        return []

def check_excel_files_for_searches(searches):
    """Helper function to check which searches have Excel files"""
    engine = get_db_connection()
    
    for search in searches:
        schedule = search.get("schedule", "none")
        
        # For scheduled searches, check database
        if schedule != "none" and engine:
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM scheduled_files 
                        WHERE search_name = :search_name AND user_id = :user_id
                    """), {
                        "search_name": search["name"],
                        "user_id": get_current_user_id()
                    })
                    count = result.fetchone()[0]
                    search["has_excel"] = count > 0
            except Exception as e:
                print(f"Database error checking files: {e}")
                search["has_excel"] = False
        else:
            # For non-scheduled searches, check filesystem (fallback)
            safe_name = search["name"].replace(" ", "_")
            pattern = os.path.join("scheduled_results", f"{safe_name}_*.xlsx")
            matching_files = glob.glob(pattern)
            search["has_excel"] = len(matching_files) > 0
    
    return searches

def create_user(username, email, password):
    engine = get_db_connection()
    if not engine:
        return False
    
    try:
        password_hash = generate_password_hash(password)
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO users (username, email, password_hash)
                VALUES (:username, :email, :password_hash)
            """), {
                "username": username,
                "email": email,
                "password_hash": password_hash
            })
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating user: {e}")
        return False
        

def verify_user(username, password):
    engine = get_db_connection()
    if not engine:
        return None
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, password_hash FROM users WHERE username = :username
            """), {"username": username})
            
            user = result.fetchone()
            if user and check_password_hash(user[1], password):
                return user[0]  # Return user_id
        return None
    except Exception as e:
        print(f"Error verifying user: {e}")
        return None

def get_current_user_id():
    return session.get('user_id')

def require_login():
    if not get_current_user_id():
        return redirect('/login')
    return None

def save_search(name, criteria):
    print(f"🔍 SAVE_SEARCH DEBUG: Attempting to save '{name}'")
    print(f"🔍 SAVE_SEARCH DEBUG: Criteria: {criteria}")
    
    engine = get_db_connection()
    print(f"🔍 SAVE_SEARCH DEBUG: Engine: {engine}")
    
    if not engine:
        print("❌ SAVE_SEARCH DEBUG: No database connection")
        return
    
    print("🔍 SAVE_SEARCH DEBUG: About to execute SQL")
    try:
        with engine.connect() as conn:
            print("🔍 SAVE_SEARCH DEBUG: Connection established")
            conn.execute(text("""
                INSERT INTO saved_searches (name, timestamp, criteria, schedule, last_run_date, user_id)
                VALUES (:name, :timestamp, :criteria, :schedule, :last_run_date, :user_id)
            """), {
                "name": name,
                "timestamp": datetime.now().strftime("%d %B %Y"),
                "criteria": json.dumps(criteria),
                "schedule": "none",
                "last_run_date": "",
                "user_id" : get_current_user_id()
            })
            conn.commit()
            print("🔍 SAVE_SEARCH DEBUG: SQL executed successfully")
        print(f"✅ SAVE_SEARCH DEBUG: Successfully saved to database")
    except Exception as e:
        print(f"❌ SAVE_SEARCH DEBUG: Database error: {e}")


def save_results_for_search(name, results):
    # Create folder if not exists
    os.makedirs("scheduled_results", exist_ok=True)

    filename = f"scheduled_results/{name.replace(' ', '_')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

from datetime import datetime

def save_results_to_excel(search_name, results):
    import pandas as pd
    from io import BytesIO
    import os
    from datetime import datetime

    os.makedirs("scheduled_results", exist_ok=True)

    safe_name = search_name.replace(" ", "_")
    date_str = datetime.now().strftime("%d_%B_%Y")
    filename = f"scheduled_results/{safe_name}_{date_str}.xlsx"

    df = pd.DataFrame(results)
    df["description"] = df["description"].apply(clean_description_for_excel)

    # Reorder columns so 'link' comes before 'description'
    cols = df.columns.tolist()
    if "link" in cols and "description" in cols:
        cols.remove("link")
        link_index = cols.index("description")
        cols.insert(link_index, "link")
    df = df[cols]

    df.insert(0, '#', range(1, len(df) + 1))

    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        temp_df = df.drop(columns=["link"])
        temp_df.to_excel(writer, index=False, sheet_name='Jobs', startcol=0)

        workbook = writer.book
        worksheet = writer.sheets['Jobs']

        header_format = workbook.add_format({
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 12,
            'text_wrap': True,
            'align': 'center',
            'valign': 'vcenter'
        })

        default_format = workbook.add_format({
            'text_wrap': True,
            'align': 'left',
            'valign': 'vcenter'
        })

        description_format = workbook.add_format({
            'text_wrap': True,
            'align': 'left',
            'valign': 'top'
        })

        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter'
        })

        for col_num, value in enumerate(df.drop(columns=["link"]).columns.values):
            formatted_value = str(value).replace("_", " ").title()
            worksheet.write(0, col_num, formatted_value, header_format)

            if value == "#":
                worksheet.set_column(col_num, col_num, 5, number_format)
            elif value.lower() in ["title", "company", "location"]:
                worksheet.set_column(col_num, col_num, 23, default_format)
            elif value.lower() == "description":
                worksheet.set_column(col_num, col_num, 80, description_format)

        link_col_index = df.columns.get_loc("link") + 1
        worksheet.write(0, link_col_index, "Link", header_format)
        worksheet.set_column(link_col_index, link_col_index, 55, default_format)

        link_format = workbook.add_format({
            'text_wrap': True,
            'align': 'left',
            'valign': 'vcenter',
            'font_color': 'blue',
            'underline': 1
        })

        for row_num in range(len(df)):
            url = df.iloc[row_num]["link"]
            if isinstance(url, str) and url.startswith("http"):
                worksheet.write_url(row_num + 1, link_col_index, url, link_format, url)
            else:
                worksheet.write(row_num + 1, link_col_index, url, link_format)

        worksheet.set_row(0, 25)
        for row_num in range(1, len(df) + 1):
            worksheet.set_row(row_num, 130)
        worksheet.autofilter(0, 0, len(df), len(df.columns))


    print(f"💾 Saved results to: {filename}")

def store_excel_in_database(search_name, file_path,user_id):
    """Store Excel file in database for scheduled searches"""
    engine = get_db_connection()
    if not engine:
        print("❌ No database connection for file storage")
        return
    
    try:
        # Read the Excel file as binary data
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        filename = os.path.basename(file_path)
       
        with engine.connect() as conn:
            # Delete old file if exists, then insert new one
            conn.execute(text("""
                DELETE FROM scheduled_files 
                WHERE search_name = :search_name AND user_id = :user_id
            """), {"search_name": search_name, "user_id": user_id})
            
            # Insert new file
            conn.execute(text("""
                INSERT INTO scheduled_files (search_name, user_id, file_data, filename)
                VALUES (:search_name, :user_id, :file_data, :filename)
            """), {
                "search_name": search_name,
                "user_id": user_id, 
                "file_data": file_data,
                "filename": filename
            })
            conn.commit()
        
        print(f"✅ Stored Excel file in database for: {search_name}")
        
    except Exception as e:
        print(f"❌ Error storing file in database: {e}")

def run_scheduled_searches():
    print("🕓 Checking scheduled searches...")

    search_history = []
    engine = get_db_connection()
    if not engine:
        print("❌ No database connection in scheduler")
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name, timestamp, criteria, schedule, last_run_date, user_id
                FROM saved_searches 
                WHERE schedule != 'none'
                ORDER BY id DESC
            """))
        
            for row in result:
                search = {
                    "name": row[0],
                    "timestamp": row[1], 
                    "criteria": row[2],
                    "schedule": row[3] or "none",
                    "last_run_date": row[4] or "",
                    "user_id": row[5]
                }
                search_history.append(search)
    except Exception as e:
        print(f"❌ Database error in scheduler: {e}")
        return
    today_str = datetime.now().strftime("%d %B %Y")
    weekday = datetime.now().weekday()
    day = datetime.now().day

    updated = False

    for index, search in enumerate(search_history):
        schedule = search.get("schedule", "none")
        last_run_raw = search.get("last_run_date", "") #e.g., 21 June 2025 07:03
        last_run_date_only = " ".join(last_run_raw.split(" ")[:3]) # 21 June 2025

        # skip if already ran today
        if last_run_date_only ==today_str:
            continue

        criteria = search.get("criteria", {})
        title = criteria.get("title", "")
        location = criteria.get("location", "")
        max_jobs = int(criteria.get("max_jobs", 10))

        should_run = (
            (schedule == "daily") or
            (schedule == "weekly" and weekday == 0) or
            (schedule == "monthly" and day == 1)
        )

        if should_run:
            print(f"🔁 Running {schedule} search: {search['name']}")
            results = scrape_jobs(title, location, max_jobs)
            save_results_to_excel(search["name"], results)
            
            # Build the same filename used in save_results_to_excel()
            safe_name = search["name"].replace(" ", "_")
            date_str = datetime.now().strftime("%d_%B_%Y")
            output_path = os.path.join("scheduled_results", f"{safe_name}_{date_str}.xlsx")
            store_excel_in_database(search["name"], output_path, search["user_id"])

            # 📧 Email the file if jobs exist
            subject = f"Scheduled Results for {search['name']} ({schedule})"
            body = f"Attached are the latest job search results for '{search['name']}' scheduled to run {schedule}."
            send_email_with_attachment(subject, body, output_path, config)

            search["last_run_date"] = datetime.now().strftime("%d %B %Y %H:%M")
            updated = True
            print(f"💾 Saved {len(results)} results to Excel for {search['name']}")

            # Update database immediately for this search
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE saved_searches 
                    SET last_run_date = :last_run_date 
                    WHERE name = :name AND user_id = :user_id
                """), {
                    "last_run_date": search["last_run_date"],
                    "name": search["name"],
                    "user_id": search["user_id"]
                })
                conn.commit()


# Add scheduler initialization right after the function
print("🚀 SCHEDULER DEBUG: About to initialize scheduler...")
try:
    scheduler = BackgroundScheduler()
    print("🚀 SCHEDULER DEBUG: BackgroundScheduler created")
    def test_scheduler():
        print("🧪 TEST: Scheduler called a function!")
    scheduler.add_job(func=run_scheduled_searches, trigger="cron", hour=5, minute=0) # Runs daily at 9am
    print("🚀 SCHEDULER DEBUG: Job added to scheduler")
    scheduler.start()
    print("🚀 SCHEDULER DEBUG: Scheduler started successfully!") 
    atexit.register(lambda: scheduler.shutdown())
    print("🚀 SCHEDULER DEBUG: Exit handler registered")
except Exception as e:
    print(f"❌ SCHEDULER DEBUG: Failed to start scheduler: {e}")
    import traceback
    traceback.print_exc()


def format_description(desc):
    import re
    lines = desc.splitlines()
    html = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        elif line.lower() in ["overview", "responsibilities", "qualifications", "pay range"]:
            html += f"<h4>{line}</h4>"
        elif re.match(r"^[A-Z][a-z]+.*:$", line):
            html += f"<p><strong>{line}</strong></p>"
        elif re.match(r"^[-\u2022\*]\s+", line):
            html += f"<ul><li>{line[1:].strip()}</li></ul>"
        else:
            html += f"<p>{line}</p>"
    return html


def clean_description_for_excel(html):
    import re
    cleaned = (
        html.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("<br />", "\n")
            .replace("</li>", "\n")
            .replace("<li>", "• ")
            .replace("&amp;", "&")
            .replace("<strong>", "")
            .replace("</strong>", "")
            .replace("<ul>", "")
            .replace("</ul>", "")
            .replace("<b>", "")
            .replace("</b>", "")
            .replace("&nbsp;", " ")
    )
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

def send_email_with_attachment(subject, body, attachment_path, config):
    try:
        smtp_server = config["email_settings"]["smtp_server"]
        smtp_port = config["email_settings"]["smtp_port"]
        sender_email = config["email_settings"]["sender_email"]
        sender_password = config["email_settings"]["sender_password"]
        recipients = config["email_settings"]["recipients"]

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)

        # Attach the Excel file
        with open(attachment_path, "rb") as f:
            file_data = f.read()
            file_name = os.path.basename(attachment_path)
        msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=file_name)

        with smtplib.SMTP(smtp_server, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)

        print(f"✅ Email sent to {recipients} with: {file_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False



@app.route("/", methods=["GET", "POST"])
def index():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
        
    global last_results
    jobs = []
    if request.method == "POST":
        title = request.form.get("title", "")
        location = request.form.get("location", "")
        seniority = request.form.get("seniority", "")
        raw_max_jobs = request.form.get("max_jobs", "")
        try:
            max_jobs = int(raw_max_jobs)
            if max_jobs <= 0 or max_jobs > 50:
                max_jobs = 50
        except (ValueError, TypeError):
            max_jobs = 50

        if request.form.get("action") == "save":
            search_name = request.form.get("search_name", "").strip()
            if not search_name:
                info = "⚠️ Please enter a name for your saved search."
            else:
                form_location = request.form.get("location", "").strip()
                criteria = {
                    "title": request.form.get("title", ""),
                    "location": form_location,
                    "max_jobs": max_jobs,
                    "seniority": request.form.get("seniority", "")
                }
                if form_location:
                    formatted_name = f"{search_name} - {form_location}"
                else:
                    formatted_name = search_name
                save_search(formatted_name, criteria)                
                info = f"✅ Search saved as: {formatted_name}"
            
            saved_searches = check_excel_files_for_searches(load_saved_searches())
            return render_template("index.html", info=info, jobs=last_results, title=title, location=location, max_jobs=max_jobs, saved_searches=saved_searches)
            
        print(f"🔍 FLASK DEBUG: About to call scraper with seniority='{seniority}', type={type(seniority)}")
        
        try:
            jobs = scrape_jobs(title, location, max_jobs, seniority=seniority)
        except Exception as e:
            print(f"❌ SCRAPING ERROR: {str(e)}")
            print(f"❌ ERROR TYPE: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            jobs = [{"title": "Scraping Failed", "company": "Error", "location": location, "link": "#", "description": f"Error: {str(e)}"}]
        
       
        for job in jobs:
            print("🔍 RAW job keys:", list(job.keys()))
            print("📌 Raw company before any changes:", job.get("company", "❌ MISSING"))

            # Ensure the company name is included for rendering
            if not job.get("company"):
                job["company"] = "[Not Found]"

            job["formatted_description"] = job.get("description", "Description not available")

            print("✅ Final company value:", job["company"])
            print("📦 FORMATTED DESCRIPTION SENT TO TEMPLATE:\n", job["formatted_description"][:500])

        
        last_results = jobs
        global last_search_name
        last_search_name = title if title else "Job_Search"
        return render_template("index.html", jobs=jobs, title=title, location=location, max_jobs=max_jobs, saved_searches=load_saved_searches())
    
    saved_searches = check_excel_files_for_searches(load_saved_searches())
    print("✅ Saved searches and their Excel status:")
    for s in saved_searches:
        print(f"- {s['name']}: has_excel = {s.get('has_excel')}")

    return render_template("index.html", title="", location="", max_jobs=10, saved_searches=saved_searches)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            return render_template("login.html", error="Please enter both username and password")
        
        user_id = verify_user(username, password)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            return redirect("/")
        else:
            return render_template("login.html", error="Invalid username or password")
    
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not username or not email or not password:
            return render_template("signup.html", error="Please fill in all fields")
        
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters")
        
        if create_user(username, email, password):
            return render_template("login.html", success="Account created! Please log in.")
        else:
            return render_template("signup.html", error="Username or email already exists")
    
    return render_template("signup.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email:
            return render_template("forgot_password.html", error="Please enter your email address")
        
        # Look up user by email
        engine = get_db_connection()
        if not engine:
            return render_template("forgot_password.html", error="Database connection error")
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT id, username FROM users WHERE email = :email
                """), {"email": email})
                user = result.fetchone()
                
                if user:
                    user_id = user[0]
                    username = user[1]
                    
                    # Create reset token
                    token = create_password_reset_token(user_id)
                    
                    if token:
                        # Send reset email
                        reset_url = f"{request.host_url}reset-password/{token}"
                        subject = "Password Reset - Find Me A Job"
                        body = f"""Hello {username},

You requested a password reset for your Find Me A Job account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request this password reset, please ignore this email.

Best regards,
Find Me A Job Team"""
                        
                        # Use existing email configuration
                        try:
                            smtp_server = config["email_settings"]["smtp_server"]
                            smtp_port = config["email_settings"]["smtp_port"]
                            sender_email = config["email_settings"]["sender_email"]
                            sender_password = config["email_settings"]["sender_password"]
                            
                            import smtplib
                            from email.message import EmailMessage
                            
                            msg = EmailMessage()
                            msg["Subject"] = subject
                            msg["From"] = sender_email
                            msg["To"] = email
                            msg.set_content(body)
                            
                            with smtplib.SMTP(smtp_server, smtp_port) as smtp:
                                smtp.starttls()
                                smtp.login(sender_email, sender_password)
                                smtp.send_message(msg)
                                
                            return render_template("forgot_password.html", 
                                success="Password reset instructions have been sent to your email")
                                
                        except Exception as e:
                            print(f"Error sending email: {e}")
                            return render_template("forgot_password.html", 
                                error="Error sending email. Please try again later.")
                    else:
                        return render_template("forgot_password.html", 
                            error="Error creating reset token. Please try again later.")
                else:
                    # Don't reveal whether email exists or not (security)
                    return render_template("forgot_password.html", 
                        success="If an account with that email exists, password reset instructions have been sent")
                        
        except Exception as e:
            print(f"Database error: {e}")
            return render_template("forgot_password.html", error="Database error. Please try again later.")
    
    return render_template("forgot_password.html")
@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    engine = get_db_connection()
    if not engine:
        return render_template("reset_password.html", error="Database connection error", token=token)
    
    # Validate token
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT r.id, r.user_id, r.expires_at, r.used, u.username 
                FROM password_reset_tokens r
                JOIN users u ON r.user_id = u.id
                WHERE r.token = :token
            """), {"token": token})
            token_data = result.fetchone()
            
            if not token_data:
                return render_template("reset_password.html", 
                    error="Invalid reset link. Please request a new password reset.", token=token)
            
            token_id, user_id, expires_at, used, username = token_data
            
            # Check if token is expired or used
            from datetime import datetime
            if used:
                return render_template("reset_password.html", 
                    error="This reset link has already been used. Please request a new password reset.", token=token)
            
            if datetime.now() > expires_at:
                return render_template("reset_password.html", 
                    error="This reset link has expired. Please request a new password reset.", token=token)
            
            # Token is valid, process password reset
            if request.method == "POST":
                new_password = request.form.get("new_password", "")
                confirm_password = request.form.get("confirm_password", "")
                
                if not new_password or not confirm_password:
                    return render_template("reset_password.html", 
                        error="Please fill in both password fields", token=token, username=username)
                
                if new_password != confirm_password:
                    return render_template("reset_password.html", 
                        error="Passwords do not match", token=token, username=username)
                
                if len(new_password) < 6:
                    return render_template("reset_password.html", 
                        error="Password must be at least 6 characters", token=token, username=username)
                
                # Update password and mark token as used
                try:
                    password_hash = generate_password_hash(new_password)
                    
                    # Update password
                    conn.execute(text("""
                        UPDATE users SET password_hash = :password_hash WHERE id = :user_id
                    """), {"password_hash": password_hash, "user_id": user_id})
                    
                    # Mark token as used
                    conn.execute(text("""
                        UPDATE password_reset_tokens SET used = TRUE WHERE id = :token_id
                    """), {"token_id": token_id})
                    
                    conn.commit()
                    
                    return render_template("reset_password.html", 
                        success="Password successfully reset! You can now log in with your new password.",
                        token=token, username=username)
                        
                except Exception as e:
                    print(f"Error updating password: {e}")
                    return render_template("reset_password.html", 
                        error="Error updating password. Please try again.", token=token, username=username)
            
            # GET request - show reset form
            return render_template("reset_password.html", token=token, username=username)
            
    except Exception as e:
        print(f"Database error: {e}")
        return render_template("reset_password.html", error="Database error. Please try again later.", token=token)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    
    engine = get_db_connection()
    if not engine:
        return "Database connection error", 500
    
    # Get current user info
    user_id = get_current_user_id()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT username, email FROM users WHERE id = :user_id
            """), {"user_id": user_id})
            user = result.fetchone()
            
            if not user:
                return redirect("/logout")
                
            current_username = user[0]
            current_email = user[1]
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return "Error loading settings", 500
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_profile":
            # Handle profile updates
            new_username = request.form.get("username", "").strip()
            new_email = request.form.get("email", "").strip()
            
            if not new_username or not new_email:
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="Please fill in all fields")
            
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE users SET username = :username, email = :email 
                        WHERE id = :user_id
                    """), {
                        "username": new_username,
                        "email": new_email,
                        "user_id": user_id
                    })
                    conn.commit()
                    
                    # Update session
                    session['username'] = new_username
                    
                return render_template("settings.html", 
                    username=new_username, email=new_email,
                    success="Profile updated successfully!")
            except Exception as e:
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="Username or email already exists")
        
        elif action == "change_password":
            # Handle password change
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            
            if not current_password or not new_password or not confirm_password:
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="Please fill in all password fields")
            
            if new_password != confirm_password:
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="New passwords don't match")
            
            if len(new_password) < 6:
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="Password must be at least 6 characters")
            
            # Verify current password
            if not verify_user(current_username, current_password):
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="Current password is incorrect")
            
            try:
                password_hash = generate_password_hash(new_password)
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE users SET password_hash = :password_hash 
                        WHERE id = :user_id
                    """), {
                        "password_hash": password_hash,
                        "user_id": user_id
                    })
                    conn.commit()
                    
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    success="Password changed successfully!")
            except Exception as e:
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="Error changing password")
    
   
        elif action == "delete_account":
            # Handle account deletion
            try:
                with engine.connect() as conn:
                    # Start a transaction to ensure all deletions succeed together
                    trans = conn.begin()
                    
                    try:
                        # Delete user's saved searches
                        conn.execute(text("""
                            DELETE FROM saved_searches WHERE user_id = :user_id
                        """), {"user_id": user_id})
                        
                        # Delete user's scheduled files
                        conn.execute(text("""
                            DELETE FROM scheduled_files WHERE user_id = :user_id
                        """), {"user_id": user_id})
                        
                        # Delete user's password reset tokens
                        conn.execute(text("""
                            DELETE FROM password_reset_tokens WHERE user_id = :user_id
                        """), {"user_id": user_id})
                        
                        # Finally, delete the user account
                        conn.execute(text("""
                            DELETE FROM users WHERE id = :user_id
                        """), {"user_id": user_id})
                        
                        # Commit the transaction
                        trans.commit()
                        
                        # Clear the session
                        session.clear()
                        
                        # Redirect to a confirmation page
                        return render_template("account_deleted.html")
                        
                    except Exception as e:
                        # If any deletion fails, roll back the transaction
                        trans.rollback()
                        print(f"Error during account deletion: {e}")
                        return render_template("settings.html", 
                            username=current_username, email=current_email,
                            error="Error deleting account. Please try again later.")
                            
            except Exception as e:
                print(f"Database error during account deletion: {e}")
                return render_template("settings.html", 
                    username=current_username, email=current_email,
                    error="Database error. Please try again later.")   
    
    
    return render_template("settings.html", username=current_username, email=current_email)




@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/load_search/<int:index>")
def load_saved_search(index):
    searches = check_excel_files_for_searches(load_saved_searches())

    if 0 <= index < len(searches):
        criteria = searches[index]["criteria"]
        title = criteria.get("title", "")
        location = criteria.get("location", "")
        seniority=criteria.get("seniority", "")
        raw_max_jobs = request.form.get("max_jobs", "")
        try:
            max_jobs = int(raw_max_jobs)
            if max_jobs <= 0 or max_jobs > 50:
                max_jobs = 50
        except (ValueError, TypeError):
            max_jobs = 50

        try:
            jobs = scrape_jobs(title, location, max_jobs, seniority=seniority)
        except Exception as e:
            print(f"❌ LOAD SEARCH ERROR: {str(e)}")
            print(f"❌ ERROR TYPE: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            jobs = [{"title": "Scraping Failed", "company": "Error", "location": location, "link": "#", "description": f"Error: {str(e)}"}]
        
        global last_results
        last_results = jobs

        global last_search_name
        last_search_name = searches[index]['name']

        return render_template(
            "index.html",
            jobs=jobs,
            title=title,
            location=location,
            max_jobs=max_jobs,
            saved_searches=searches,
            criteria = searches[index]["criteria"],
            name = searches[index]["name"],
            timestamp = datetime.now().strftime("%d %B %Y"),
            active_search_name = f"{searches[index]['name']} – {location} – {datetime.now().strftime('%d %B %Y')}"
        )
    else:
        return redirect("/")

@app.route('/download', methods=['POST'])
def download():
    global last_results
    if not last_results:
        return "No results to export", 400

    df = pd.DataFrame(last_results).drop(columns=["formatted_description"], errors="ignore")
    df["description"] = df["description"].apply(clean_description_for_excel)

    # Reorder columns so 'link' comes before 'description'
    cols = df.columns.tolist()
    if "link" in cols and "description" in cols:
        cols.remove("link")
        link_index = cols.index("description")
        cols.insert(link_index, "link")
    df = df[cols]

    # Add the '#' column at the beginning
    df.insert(0, '#', range(1, len(df) + 1))

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Write all columns except 'link'
        temp_df = df.drop(columns=["link"])
        temp_df.to_excel(writer, index=False, sheet_name='Jobs', startcol=0)

        workbook = writer.book
        worksheet = writer.sheets['Jobs']

        # Header format
        header_format = workbook.add_format({
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 12,
            'text_wrap': True,
            'align': 'center',
            'valign': 'vcenter'
        })

        # Column format templates
        default_format = workbook.add_format({
            'text_wrap': True,
            'align': 'left',
            'valign': 'vcenter'
        })

        description_format = workbook.add_format({
            'text_wrap': True,
            'align': 'left',
            'valign': 'top'
        })

        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter'
        })

        # Write headers and set column widths/formats
        for col_num, value in enumerate(df.drop(columns=["link"]).columns.values):
            formatted_value = str(value).replace("_", " ").title()
            worksheet.write(0, col_num, formatted_value, header_format)

            if value == "#":
                worksheet.set_column(col_num, col_num, 5, number_format)
            elif value.lower() in ["title", "company", "location"]:
                worksheet.set_column(col_num, col_num, 23, default_format)
            elif value.lower() == "description":
                worksheet.set_column(col_num, col_num, 80, description_format)

        # Write "Link" header and column manually
        link_col_index = df.columns.get_loc("link") + 1
        worksheet.write(0, link_col_index, "Link", header_format)
        worksheet.set_column(link_col_index, link_col_index, 55, default_format)

        # Format and write links row by row
        link_format = workbook.add_format({
            'text_wrap': True,
            'align': 'left',
            'valign': 'vcenter',
            'font_color': 'blue',
            'underline': 1
        })

        for row_num in range(len(df)):
            url = df.iloc[row_num]["link"]
            if isinstance(url, str) and url.startswith("http"):
                worksheet.write_url(row_num + 1, link_col_index, url, link_format, url)
            else:
                worksheet.write(row_num + 1, link_col_index, url, link_format)

        # Set row height: header and data rows
        worksheet.set_row(0, 25)
        for row_num in range(1, len(df) + 1):
            worksheet.set_row(row_num, 130)
        worksheet.autofilter(0, 0, len(df), len(df.columns))


    global last_search_name
    title_from_form = request.form.get("title", "").strip()
    if last_search_name and last_search_name != "Job_Search":
        name_for_export = last_search_name
    elif title_from_form:
        name_for_export = title_from_form
    else:
        name_for_export = "Job_Search"
    
     
    filename = f"{name_for_export.replace(' – ', '_')}_{datetime.now().strftime('%d_%B_%Y')}.xlsx"

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name=filename,
        as_attachment=True
    )

@app.route("/delete_saved_search", methods=["POST"])
def delete_saved_search():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
        
    index = int(request.form.get("index", -1))
    if index >= 0:
        # Get current saved searches from database
        searches = load_saved_searches()
        
        if 0 <= index < len(searches):
            search_to_delete = searches[index]
            
            engine = get_db_connection()
            if engine:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            DELETE FROM saved_searches 
                            WHERE name = :name AND user_id = :user_id
                        """), {
                            "name": search_to_delete["name"],
                            "user_id": get_current_user_id()
                        })
                        conn.commit()
                        
                    print(f"🗑️ Deleted saved search: {search_to_delete['name']}")
                    
                except Exception as e:
                    print(f"❌ Error deleting search: {e}")
                    
    return redirect("/")

@app.route("/rename/<int:index>", methods=["POST"])
def rename_saved_search(index):
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
        
    new_name = request.form.get("new_name", "").strip()
    if not new_name:
        return redirect("/")

    # Get current saved searches from database
    searches = load_saved_searches()
    
    if 0 <= index < len(searches):
        old_search = searches[index]
        
        engine = get_db_connection()
        if engine:
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE saved_searches 
                        SET name = :new_name 
                        WHERE name = :old_name AND user_id = :user_id
                    """), {
                        "new_name": new_name,
                        "old_name": old_search["name"],
                        "user_id": get_current_user_id()
                    })
                    conn.commit()
                    
                print(f"✅ Renamed search from '{old_search['name']}' to '{new_name}'")
                
            except Exception as e:
                print(f"❌ Error renaming search: {e}")
                
    return redirect("/")


@app.route("/schedule", methods=["POST"])
def schedule():
    index = int(request.form.get("search_index"))
    saved_searches = load_saved_searches()

    if 0 <= index < len(saved_searches):
        selected_search = saved_searches[index]
        return render_template("schedule.html", search=selected_search, index=index)
    else:
        return "Invalid search index", 400
 

@app.route("/save_schedule", methods=["POST"])
def save_schedule():
    index = int(request.form.get("search_index"))
    frequency = request.form.get("frequency")

    search_history = load_saved_searches()

    if 0 <= index < len(search_history):
        search = search_history[index]
        engine = get_db_connection()
        
        if engine:
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE saved_searches 
                        SET schedule = :schedule 
                        WHERE name = :name AND user_id = :user_id
                    """), {
                        "schedule": frequency,
                        "name": search["name"],
                        "user_id": get_current_user_id()
                    })
                    conn.commit()
                return '', 200
            except Exception as e:
                print(f"Error updating schedule: {e}")
                return "Database error", 500
        return "No database connection", 500
    else:
        return "Invalid search index", 400

@app.route("/download_scheduled/<search_name>")
def download_scheduled(search_name):
    engine = get_db_connection()
    if not engine:
        return "Database connection error", 500
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT file_data, filename FROM scheduled_files 
                WHERE search_name = :search_name AND user_id = :user_id
            """), {
                "search_name": search_name,
                "user_id": get_current_user_id()
            })
            
            row = result.fetchone()
            if not row:
                return f"No file found for scheduled search: {search_name}", 404
            
            file_data, filename = row
            
            # Create BytesIO object from database binary data
            file_buffer = BytesIO(file_data)
            file_buffer.seek(0)
            
            return send_file(
                file_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                download_name=filename,
                as_attachment=True
            )
            
    except Exception as e:
        print(f"Error downloading scheduled file: {e}")
        return "Error downloading file", 500

@app.route("/api/saved_searches")
def api_saved_searches():
    searches = load_saved_searches()
    return json.dumps(searches), 200, {'Content-Type': 'application/json'}

@app.route("/saved_searches_partial")
def saved_searches_partial():
    searches = check_excel_files_for_searches(load_saved_searches())
    return render_template("partials/saved_searches.html", saved_searches=searches)

from flask import send_file
import zipfile
import io

@app.route("/download_selected", methods=["POST"])
def download_selected():
    print("🚨 FLASK ROUTE HIT!! /download_selected was called!")
    selected = request.form.getlist("selected_files")
    print("✅ /download_selected triggered!")
    print("🧾 Selected files:", selected) 

    today_str = datetime.now().strftime("%d_%B_%Y")

    if not selected:
        print("❌ No files selected.")
        return redirect("/")
     
     # Case B: Zip selected results
    files_to_zip = []
    for name in selected:
        # Convert spaces to underscores to match filename format
        safe_name = name.replace(" ", "_")
        filename = f"{safe_name}_{today_str}.xlsx"
        filepath = os.path.join("scheduled_results", filename)
        if os.path.exists(filepath):
            files_to_zip.append(filepath)
     
    if not files_to_zip:
        print("❌ No matching files found on disk.")
        return redirect("/")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
        for f in files_to_zip:
            zipf.write(f, arcname=os.path.basename(f))

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name="Selected_Results.zip", mimetype="application/zip")


@app.route("/create_test_files")
def create_test_files():
    import os
    import pandas as pd
    from datetime import datetime
    
    # Create the folder
    os.makedirs("scheduled_results", exist_ok=True)
    
    # Get saved searches and create test Excel files for each
    searches = load_saved_searches()
    created_files = []
    
    for search in searches:
        safe_name = search["name"].replace(" ", "_")
        date_str = datetime.now().strftime("%d_%B_%Y")
        filename = f"scheduled_results/{safe_name}_{date_str}.xlsx"
        
        # Create a simple test Excel file
        test_data = [{"title": "Test Job", "company": "Test Company", "location": "Test Location", "link": "http://test.com", "description": "Test description"}]
        df = pd.DataFrame(test_data)
        df.to_excel(filename, index=False)
        created_files.append(filename)
    
    return f"Created test files: {created_files}<br><br><a href='/debug'>Check debug again</a><br><a href='/'>Go back to main page</a>"

@app.route("/clean_test_files")
def clean_test_files():
    import os, glob
    files = glob.glob("scheduled_results/*.xlsx")
    deleted_count = 0
    for f in files:
        try:
            os.remove(f)
            deleted_count += 1
        except:
            pass
    return f"Deleted {deleted_count} test files. <br><br><a href='/debug'>Check debug again</a><br><a href='/'>Go back to main page</a>"


@app.route("/debug_files")
def debug_files():
    import os
    import stat
    
    file_info = {}
    
    if os.path.exists(HISTORY_FILE):
        file_stats = os.stat(HISTORY_FILE)
        file_info = {
            "exists": True,
            "size": file_stats.st_size,
            "permissions": oct(file_stats.st_mode),
            "modified": datetime.fromtimestamp(file_stats.st_mtime).strftime("%d %B %Y %H:%M:%S")
        }
        
        # Try to read the current content
        try:
            with open(HISTORY_FILE, "r") as f:
                content = f.read()
                file_info["content_preview"] = content[:500]
        except Exception as e:
            file_info["read_error"] = str(e)
    else:
        file_info = {"exists": False}
    
    return f"<pre>{json.dumps(file_info, indent=2)}</pre>"

@app.route("/debug_full_file")
def debug_full_file():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        return f"<pre>{content}</pre>"
    except Exception as e:
        return f"Error reading file: {e}"

@app.route("/test_db")
def test_db():
    try:
        engine = get_db_connection()
        print(f"Engine result: {engine}")
        if engine:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return "Database connection works!"
        else:
            return "No database engine created"
    except Exception as e:
        return f"Database error: {e}"

@app.route("/debug_env")
def debug_env():
    import os
    db_vars = {}
    for key, value in os.environ.items():
        if any(word in key.upper() for word in ['DATABASE', 'POSTGRES', 'PG']):
            db_vars[key] = value[:20] + "..." if len(value) > 20 else value
    return f"<pre>{json.dumps(db_vars, indent=2)}</pre>"

@app.route("/check_files")
def check_files():
    import os, glob
    files = glob.glob("scheduled_results/*.xlsx")
    return f"Excel files found: {files}"


@app.route("/test_manual_run")
def test_manual_run():
    try:
        run_scheduled_searches()
        return "Manual test completed - check logs and /check_files"
    except Exception as e:
        return f"Error: {e}"

@app.route("/debug_excel_detection")
def debug_excel_detection():
    searches = load_saved_searches()
    searches_with_files = check_excel_files_for_searches(searches)
    
    # Check what files actually exist
    all_files = glob.glob("scheduled_results/*.xlsx")
    
    debug_info = {
        "files_on_disk": all_files,
        "search_results": []
    }
    
    for search in searches_with_files:
        safe_name = search["name"].replace(" ", "_")
        pattern = f"scheduled_results/{safe_name}_*.xlsx"
        matching_files = glob.glob(pattern)
        
        debug_info["search_results"].append({
            "original_name": search["name"],
            "safe_name": safe_name,
            "pattern": pattern,
            "files_found": matching_files,
            "has_excel": search.get("has_excel", False)
        })
    
    return f"<pre>{json.dumps(debug_info, indent=2)}</pre>"

@app.route("/debug_database_files")
def debug_database_files():
    engine = get_db_connection()
    if not engine:
        return "No database connection"
    
    try:
        with engine.connect() as conn:
            # Check what files exist in database
            result = conn.execute(text("SELECT search_name, user_id, filename, created_at FROM scheduled_files"))
            files = []
            for row in result:
                files.append({
                    "search_name": row[0],
                    "user_id": row[1], 
                    "filename": row[2],
                    "created_at": str(row[3])
                })
            
            # Check current user ID
            current_user = get_current_user_id()
            
            return f"<pre>Current User ID: {current_user}\n\nFiles in database:\n{json.dumps(files, indent=2)}</pre>"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
