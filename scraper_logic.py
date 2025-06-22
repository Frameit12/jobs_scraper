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
    print("🔍 REAL SCRAPING TEST: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    
    if not title or not location:
        return [{"error": "Please enter both job title and location"}]
    
    try:
        print("🌐 Launching browser...")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        
        print("🌐 Navigating to efinancialcareers...")
        driver.get("https://www.efinancialcareers.com/")
        time.sleep(5)
        
        print("📝 Filling search form...")
        title_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Job title, keyword or company']"))
        )
        title_input.send_keys(title)
        
        location_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Location']"))
        )
        location_input.send_keys(location)
        
        search_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        search_button.click()
        
        print("⏳ Waiting for search results...")
        time.sleep(8)
        
        # Get job cards
        job_cards = driver.find_elements(By.CSS_SELECTOR, "a.font-subtitle-3-medium.job-title")
        print(f"🔍 Found {len(job_cards)} job cards")
        
        # Take just first 2 jobs for testing
        results = []
        for i, card in enumerate(job_cards[:2]):
            try:
                job_title = card.text.strip()
                job_link = card.get_attribute("href")
                
                print(f"📋 Processing job {i+1}: {job_title}")
                
                # For now, create basic job data (we'll add description extraction later)
                job = {
                    "title": job_title if job_title else f"Job {i+1}",
                    "company": "Company Name", # We'll extract this later
                    "location": location,
                    "link": job_link if job_link else "#",
                    "description": f"Job description for {job_title}" # Placeholder for now
                }
                
                results.append(job)
                print(f"✅ Added job {i+1}")
                
            except Exception as e:
                print(f"❌ Error processing job {i+1}: {e}")
                continue
                
        driver.quit()
        print(f"🎉 Successfully scraped {len(results)} jobs")
        return results
        
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        try:
            driver.quit()
        except:
            pass
        return [{"title": "Error", "company": "System", "location": location, "link": "#", "description": f"Scraping failed: {str(e)[:100]}"}]
