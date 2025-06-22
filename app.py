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




app = Flask(__name__)

HISTORY_FILE = "search_history.json"

# Define global results variable
last_results = []
last_search_name = "Job_Search"


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()


def load_saved_searches():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                searches = json.load(f)
                for s in searches:
                    if "schedule" not in s:
                        s["schedule"] = "none"
                return searches
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    return []

def check_excel_files_for_searches(searches):
    """Helper function to check which searches have Excel files"""
    for search in searches:
        safe_name = search["name"].replace(" ", "_")
        pattern = os.path.join("scheduled_results", f"{safe_name}_*.xlsx")
        matching_files = glob.glob(pattern)
        search["has_excel"] = len(matching_files) > 0
    return searches


def save_search(name, criteria):
    print(f"🔍 SAVE_SEARCH DEBUG: Attempting to save '{name}'")
    history = load_saved_searches()
    print(f"🔍 SAVE_SEARCH DEBUG: Loaded {len(history)} existing searches")
    entry = {
        "name": name,
        "timestamp": datetime.now().strftime("%d %B %Y"),
        "criteria": criteria,
        "schedule": "none"
    }
    history.insert(0, entry)
    history = history[:5]  # Keep only 5 most recent
    print(f"🔍 SAVE_SEARCH DEBUG: About to write {len(history)} searches to file")
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        print(f"✅ SAVE_SEARCH DEBUG: Successfully wrote to {HISTORY_FILE}")
    except Exception as e:
        print(f"❌ SAVE_SEARCH DEBUG: Failed to write file: {e}")

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


def run_scheduled_searches():
    print("🕓 Checking scheduled searches...")

    search_history = load_saved_searches()
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

            # 📧 Email the file if jobs exist
            subject = f"Scheduled Results for {search['name']} ({schedule})"
            body = f"Attached are the latest job search results for '{search['name']}' scheduled to run {schedule}."
            send_email_with_attachment(subject, body, output_path, config)

            search["last_run_date"] = datetime.now().strftime("%d %B %Y %H:%M")
            updated = True
            print(f"💾 Saved {len(results)} results to Excel for {search['name']}")

    if updated:
        with open("search_history.json", "w", encoding="utf-8") as f:
            json.dump(search_history, f, indent=2)


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
    index = int(request.form.get("index", -1))
    if index >= 0:
        searches = load_saved_searches()
        if 0 <= index < len(searches):
            deleted = searches.pop(index)
            with open("search_history.json", "w", encoding="utf-8") as f:
                json.dump(searches, f, indent=2)
            print(f"🗑️ Deleted saved search: {deleted['name']}")
    return redirect("/")

@app.route("/rename/<int:index>", methods=["POST"])
def rename_saved_search(index):
    new_name = request.form.get("new_name", "").strip()
    if not new_name:
        return redirect("/")

    try:
        with open("search_history.json", "r", encoding="utf-8") as f:
            saved_searches = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        saved_searches = []

    if 0 <= index < len(saved_searches):
        saved_searches[index]["name"] = new_name
        with open("search_history.json", "w", encoding="utf-8") as f:
            json.dump(saved_searches, f, indent=2)

        return render_template(
            "index.html",
            jobs=last_results,
            title="",
            location="",
            max_jobs=10,
            saved_searches=check_excel_files_for_searches(load_saved_searches()),
            active_search_name=f"{last_search_name} – {datetime.now().strftime('%d %B %Y')}",
            timestamp=datetime.now().strftime("%d %B %Y")
        )

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
        search_history[index]["schedule"] = frequency
        with open("search_history.json", "w", encoding="utf-8") as f:
            json.dump(search_history, f, indent=2)
        return '', 200
    else:
        return "Invalid search index", 400
    

@app.route("/download_scheduled/<search_name>")
def download_scheduled(search_name):
    import glob
    import os

    folder = "scheduled_results"
    pattern = os.path.join(folder, f"{search_name.replace(' ', '_')}_*.xlsx")
    matching_files = sorted(glob.glob(pattern), reverse=True)

    if not matching_files:
        return f"No file found for scheduled search: {search_name}", 404

    latest_file = matching_files[0]
    return send_file(latest_file, as_attachment=True)

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
        filename = f"{name}_{today_str}.xlsx"
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

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=run_scheduled_searches, trigger="interval", minutes=1)
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
