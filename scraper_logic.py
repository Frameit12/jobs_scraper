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
    print("🔍 Debugging element selectors...")
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox") 
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    
    try:
        print("🧪 Loading efinancialcareers.com...")
        driver.get("https://www.efinancialcareers.com/")
        print("✅ SUCCESS: Page loaded!")
        
        # Wait for page to fully load
        time.sleep(5)
        
        # DEBUG: Check what input elements exist
        print("🔍 Debugging: Looking for all input elements...")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        print(f"Found {len(inputs)} input elements:")
        for i, inp in enumerate(inputs):
            placeholder = inp.get_attribute("placeholder") or "No placeholder"
            inp_type = inp.get_attribute("type") or "No type"
            print(f"  Input {i}: placeholder='{placeholder}', type='{inp_type}'")
        
        # Try different selectors
        selectors_to_try = [
            "input[placeholder='Job title, keyword or company']",
            "input[placeholder*='Job title']",
            "input[placeholder*='keyword']",
            "input[name*='title']",
            "input[name*='search']",
            "#search-title",
            ".search-input"
        ]
        
        found_selector = None
        for selector in selectors_to_try:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                found_selector = selector
                print(f"✅ Found element with selector: {selector}")
                break
            except:
                print(f"❌ Selector failed: {selector}")
        
        driver.quit()
        
        if found_selector:
            return [{"title": "Selector Found", "company": "Success", "location": location, "link": "#", "description": f"Working selector: {found_selector}"}]
        else:
            return [{"title": "No Selector Found", "company": "Debug Needed", "location": location, "link": "#", "description": f"Found {len(inputs)} inputs total. Check debug output in logs."}]
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        try:
            driver.quit()
        except:
            pass
        return [{"title": "Debug Failed", "company": "Error", "location": location, "link": "#", "description": f"Error: {str(e)}"}]
