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


def scrape_jobs(title, location, max_jobs=10, seniority=None, region="US"):
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
    base_url = "https://www.efinancialcareers.com/" if region == "US" else "https://www.efinancialcareers.co.uk/"
    print(f"🌍 REGION DEBUG: Using region '{region}' -> URL: {base_url}")
    driver.get(base_url)
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

            # DEBUG: Wait and check if job count updates
            print("🔍 DEBUG: Checking job count after filter...")
            time.sleep(5)
            try:
                result_text = driver.find_element(By.XPATH, "//*[contains(text(), 'job in')]").text
                print(f"📊 Updated job count: {result_text}")
            except:
                print("📊 Could not find job count text")
            
            # DEBUG: Check what jobs are visible immediately after filtering
            print("🔍 DEBUG: Checking jobs immediately after seniority filter...")
            immediate_cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
            print(f"Jobs found immediately: {len(immediate_cards)}")
            for i, card in enumerate(immediate_cards):
                try:
                    title = card.text.strip()
                    print(f"  Immediate Job {i+1}: '{title}'")
                except:
                    print(f"  Immediate Job {i+1}: Could not read title")
         
            
            # DEBUG: Save the actual page we're on after filtering
            print("🔍 DEBUG: Saving filtered page source...")
            with open("filtered_results_debug.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)

            # DEBUG: Check current URL
            print(f"🌐 Current URL after filtering: {driver.current_url}")

            # DEBUG: Look for the specific job count text
            try:
                job_count_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Operational Risk job in New York')]")
                for elem in job_count_elements:
                    print(f"📊 Found job count text: '{elem.text}'")
            except Exception as e:
                print(f"⚠️ Could not find job count text: {e}")

      
        except Exception as e:
            print(f"⚠️ Could not apply seniority filter: {e}")

    job_links = []
    
    # Get the expected number of jobs from the page indicator
    try:
        job_count_text = driver.find_element(By.XPATH, "//*[contains(text(), 'job in')]").text
        # Extract number from text like "Operational Risk job in New York (1)"
        import re
        count_match = re.search(r'\((\d+)\)', job_count_text)
        if count_match:
            expected_jobs = int(count_match.group(1))
            print(f"🎯 Successfully extracted job count: {expected_jobs}")
        else:
            expected_jobs = 999
            print(f"❌ Regex failed to extract number from: '{job_count_text}'")
    except:
        expected_jobs = 999  # Fallback if we can't find the count
        print("⚠️ Could not find job count, collecting all")

    # Collect only the expected number of jobs
    cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
    print(f"🔍 Total cards found: {len(cards)}")

    for i, card in enumerate(cards):
        if i >= expected_jobs:  # Stop when we reach the expected count
            print(f"🛑 Reached expected job count ({expected_jobs}), stopping collection")
            break
        
        try:
            href = card.get_attribute("href")
            if href:
                job_links.append(href)
                print(f"✅ Collected job {i+1}: '{card.text.strip()}'")
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


