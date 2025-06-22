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
    if not title or not location:
        return [{"error": "Please enter both job title and location"}]
    
    try:
        print("🔧 Testing Fix #2: Selenium Connection Stability...")
        
        from selenium.webdriver.chrome.service import Service
        
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # NEW: Connection stability fixes
        options.add_argument("--remote-debugging-port=0")  # Let Chrome pick port
        options.add_argument("--disable-logging")
        options.add_argument("--disable-log-level")
        options.add_argument("--silent")
        options.add_argument("--disable-background-networking")
        
                
        print("🌐 Creating Chrome driver with stable connection...")
        driver = webdriver.Chrome(options=options)
        
        # NEW: Shorter timeout to avoid connection hanging
        driver.set_page_load_timeout(15)
        driver.implicitly_wait(5)
        
        print("🌐 Testing basic navigation...")
        driver.get("https://httpbin.org/get")  # Simple test endpoint
        time.sleep(2)
        
        page_source_length = len(driver.page_source)
        print(f"✅ Page loaded successfully. Content length: {page_source_length}")
        
        driver.quit()
        
        return [{
            "title": "Fix #2 Success",
            "company": "Connection Stable", 
            "location": location,
            "link": "#",
            "description": f"Selenium-Chrome connection working! Page content length: {page_source_length} characters"
        }]
        
    except Exception as e:
        print(f"❌ Fix #2 failed: {e}")
        try:
            driver.quit()
        except:
            pass
        return [{"title": "Fix #2 Failed", "company": "Error", "location": location, "link": "#", "description": f"Connection fix failed: {str(e)[:100]}"}]
