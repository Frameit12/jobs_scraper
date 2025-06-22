from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from bleach import clean
import time

def wait_for_full_description(driver, selector, min_length=500, timeout=15):
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, selector)
            if len(elem.text.strip()) >= min_length:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def extract_job_details(driver, url):
    driver.get(url)
    print(f"\n🌐 Visiting: {url}")

    try:
        title = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1.font-heading-3"))
        ).text.strip()
    except TimeoutException:
        title = "[Not Found]"

    try:
        location = driver.find_element(By.CSS_SELECTOR, "span.loc").text.strip()
    except Exception:
        location = "[Not Found]"

    
    try:
        try:
            company_elem = driver.find_element(By.CSS_SELECTOR, "a.companyInfo")
        except:
            company_elem = driver.find_element(By.CSS_SELECTOR, "span.companyInfo")
        company = company_elem.text.strip()
    except Exception:
        company = "[Not Found]"

   
    if wait_for_full_description(driver, "div.inner-content", min_length=500):
        soup = BeautifulSoup(driver.page_source, "html.parser")
        desc_container = soup.select_one("div.inner-content")
        with open("job_debug_raw.html", "w", encoding="utf-8") as f:
            f.write(desc_container.prettify() if desc_container else "")
        raw_html = desc_container.decode_contents() if desc_container else "[Not Found]"
    else:
        raw_html = "[Not Found or Incomplete]"

    allowed_tags = ['p', 'br', 'ul', 'li', 'ol', 'strong', 'em', 'h2', 'h3', 'a', 'b']
    allowed_attrs = {'a': ['href', 'title']}
    if "<span" in raw_html:
        raw_html = raw_html.replace("<span>", "").replace("</span>", "")
    description = clean(raw_html, tags=allowed_tags, attributes=allowed_attrs)

    print("======== JOB DEBUG INFO ========")
    print("🔗 URL:", url)
    print("\n🔤 RAW HTML EXCERPT:\n", raw_html[:1000])
    print("\n🧼 CLEANED HTML EXCERPT:\n", description[:1000])
    print("=================================\n")

    print("===== JOB DETAIL EXTRACTED =====")
    print("Title:", title)
    print("Location:", location)
    print("Link:", url)
    print("\nDescription Preview:\n", description[:400], "\n")

    return {
        "title": title,
        "company": company,
        "location": location,
        "link": url,
        "description": description
    }

def scrape_jobs(title, location, max_jobs=10, seniority=None):
    try:
        # Your existing debug prints...
        print("🔍 BASIC DEBUG: Function called with parameters:")
        print(f"  - title: '{title}'")
        print(f"  - location: '{location}'") 
        print(f"  - max_jobs: {max_jobs}")
        print(f"  - seniority: '{seniority}'")
        
        # Add basic error handling
        if not title or not location:
            return [{"error": "Please enter both job title and location"}]
        
        print("🌐 Launching browser...")
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        
        driver = webdriver.Chrome(options=options)
        
        # Set a longer timeout for cloud environments
        driver.set_page_load_timeout(30)
        
        # Your existing scraping code but with error handling...
        # [Continue with your existing code]
        
    except Exception as e:
        print(f"❌ Scraping error: {e}")
        return [{"error": f"Job search temporarily unavailable. Please try again later. ({str(e)[:50]}...)"}]
    finally:
        try:
            driver.quit()
        except:
            pass
    
    driver.get("https://www.efinancialcareers.com/")
    time.sleep(2)

    print("⌨️ Filling job title and location...")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Job title, keyword or company']"))
    ).send_keys(title)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Location']"))
    ).send_keys(location)

    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(5)

    # ADD THIS SINGLE DEBUG LINE:
    print(f"🔍 SENIORITY RECEIVED: '{seniority}' (type: {type(seniority)})")

    # Handle seniority filtering if specified
    if seniority:
        print(f"🎯 DEBUG Step 1: Seniority parameter received: '{seniority}'")
        print(f"🎯 DEBUG Step 1: Seniority type: {type(seniority)}")
        print(f"🎯 DEBUG Step 1: Seniority is truthy: {bool(seniority)}")
        print(f"🎯 Applying seniority filter: {seniority}")

        try:
            # Wait for search results page to fully load
            print("⏳ Waiting for search results page to load...")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title"))
            )
            time.sleep(3)  # Extra wait to ensure filters are loaded
        
            # Click the Seniority dropdown
            print("🔽 Opening seniority filter...")

            # Find the specific seniority button by looking for "Seniority" text
            filter_buttons = driver.find_elements(By.CSS_SELECTOR, "efc-filter-button")
            seniority_btn = None
            for btn in filter_buttons:
                if "Seniority" in btn.text:
                    seniority_btn = btn.find_element(By.TAG_NAME, "button")
                    break
        
            if seniority_btn:
                seniority_btn.click()
                time.sleep(2)

                # Map your UI values to eFinancialCareers VALUE attributes
                seniority_mapping = {
                    'intern': 'INTERN_GRADUATE',
                    'junior': 'JUNIOR', 
                    'analyst': 'ANALYST',
                    'associate': 'ASSOCIATE_MID_LEVEL',
                    'avp': 'AVP_SENIOR',
                    'vp': 'VP_PRINCIPAL',
                    'svp': 'SVP_HEAD_OF',
                    'director': 'DIRECTOR',
                    'md': 'MANAGING_DIRECTOR',
                    'csuite': 'C_SUITE'
                }

                checkbox_value = seniority_mapping.get(seniority)
                if checkbox_value:
                    print(f"☑️ Looking for checkbox with value: {checkbox_value}")
                    # Use the exact ID pattern from the HTML
                    checkbox = driver.find_element(By.ID, f"seniority{checkbox_value}")
        
                    if not checkbox.is_selected():
                        checkbox.click()
                        time.sleep(2)
                        print(f"✅ Clicked checkbox for {checkbox_value}")
            
                        # Wait for filtered results to load
                        print("⏳ Waiting for filtered results to reload...")
                        WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title"))
                        )
                        time.sleep(3)
            else:
                raise Exception("Seniority button not found")
                
            print("✅ Seniority filter applied successfully")
        except Exception as e:
            print(f"⚠️ Could not apply seniority filter: {e}")

    print("🔄 Clicking 'Show more' to load up to max_jobs...")
    for _ in range(5):
        cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
        if len(cards) >= max_jobs + 10:  # buffer in case some jobs are invalid
            break
        try:
            show_more = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Show more')]"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_more)
            show_more.click()
            time.sleep(3)
        except Exception:
            break

    print("⏳ Waiting for job cards to load...")
    job_links = []
    cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
    print(f"🔍 Total cards collected: {len(cards)}")

    for card in cards:
        try:
            href = card.get_attribute("href")
            if href:
                job_links.append(href)
        except Exception:
            continue

    print(f"🔍 Found {len(job_links)} job links.\n")

    # ✅ Collect only valid jobs until we reach max_jobs
    job_results = []
    for url in job_links:
        job = extract_job_details(driver, url)

        if (
            job["title"] == "[Not Found]" or
            job["location"] == "[Not Found]" or
            job["description"] == "[Not Found or Incomplete]"
        ):
            print("⛔ Skipping invalid job.")
            continue

        job_results.append(job)
        print(f"✅ Collected: {len(job_results)} / {max_jobs}")
        time.sleep(2)

        if len(job_results) >= max_jobs:
            break

    driver.quit()
    return job_results
