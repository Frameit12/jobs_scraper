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
    print(f"\n Visiting: {url}")

    try:
        title = WebDriverWait(driver, 60).until(
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
    print("🔍 BASIC DEBUG: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    
    print("🌐 Launching browser...")
    options = Options()
    
    # === CONVERT TO HEADLESS WITH ANTI-DETECTION ===
    options.add_argument("--headless")  # Changed from --start-maximized
    options.add_argument("--no-sandbox") 
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # === ADD PROVEN ANTI-DETECTION ===
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    options.add_argument(f"--user-agent={user_agent}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    
    driver = webdriver.Chrome(options=options)
    
    # === ADD ANTI-DETECTION SCRIPT ===
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # === REST OF YOUR EXACT WORKING LOGIC ===
    driver.get("https://www.efinancialcareers.com/")
    time.sleep(2)

    print("⌨️ Filling job title and location...")
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Job title, keyword or company']"))
    ).send_keys(title)

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Location']"))
    ).send_keys(location)

    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(5)

    # DEBUG: Check what we actually got after the search
    print("🔍 DEBUG: Checking search results after initial search...")
    try:
        # Look for the job count indicator
        result_text = driver.find_element(By.XPATH, "//*[contains(text(), 'job in')]").text
        print(f"📊 Results found on page: {result_text}")
    
        # Count actual job cards
        initial_cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
        print(f"📋 Job cards found: {len(initial_cards)}")
    
        # Check if "No more jobs!" exists immediately
        no_more_msg = driver.find_elements(By.XPATH, "//*[contains(text(), 'No more jobs!')]")
        print(f"🔚 'No more jobs!' message present: {len(no_more_msg) > 0}")
    
    except Exception as e:
        print(f"⚠️ DEBUG: Could not get initial search info: {e}")
    
    print(f"🔍 SENIORITY RECEIVED: '{seniority}' (type: {type(seniority)})")

    # Handle seniority filtering if specified
    if seniority:
        print(f"🎯 Applying seniority filter: {seniority}")
        try:
            print("⏳ Waiting for search results page to load...")
            WebDriverWait(driver, 65).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title"))
            )
            time.sleep(3)
        
            print("🔽 Opening seniority filter...")
            filter_buttons = driver.find_elements(By.CSS_SELECTOR, "efc-filter-button")
            seniority_btn = None
            for btn in filter_buttons:
                if "Seniority" in btn.text:
                    seniority_btn = btn.find_element(By.TAG_NAME, "button")
                    break
        
            if seniority_btn:
                seniority_btn.click()
                time.sleep(2)

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
                    checkbox = driver.find_element(By.ID, f"seniority{checkbox_value}")
        
                    if not checkbox.is_selected():
                        checkbox.click()
                        time.sleep(2)
                        print(f"✅ Clicked checkbox for {checkbox_value}")
            
                        print("⏳ Waiting for filtered results to reload...")
                        WebDriverWait(driver, 65).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title"))
                        )
                        time.sleep(3)
            else:
                raise Exception("Seniority button not found")
                
            print("✅ Seniority filter applied successfully")
        except Exception as e:
            print(f"⚠️ Could not apply seniority filter: {e}")

    print("🔄 Checking if more jobs are available...")
    # Get initial job count after filtering
    cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
    print(f"🔍 Jobs found after filtering: {len(cards)}")

    # Check if there are more jobs available before trying to load them
    attempts = 0
    while len(cards) < max_jobs and attempts < 3:
        try:
            # First check if "No more jobs!" message exists
            no_more_jobs = driver.find_elements(By.XPATH, "//*[contains(text(), 'No more jobs!')]")
            if no_more_jobs:
                print("🔚 'No more jobs!' message found - this is all the results available")
                break
            
            # Try to find "Show more" button
            show_more = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Show more')]"))
            )
            print(f"📄 Found 'Show more' button, clicking (attempt {attempts + 1})...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_more)
            show_more.click()
            time.sleep(3)
        
            # Check if we got more jobs
            new_cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
            if len(new_cards) == len(cards):  # No new jobs loaded
                print("🔚 No new jobs loaded after clicking 'Show more'")
                break
            cards = new_cards
            print(f"📈 Total jobs now: {len(cards)}")
            attempts += 1
        except TimeoutException:
            print("🔚 No 'Show more' button found - reached end of results")
            break
        except Exception as e:
            print(f"⚠️ Error while trying to load more jobs: {e}")
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


