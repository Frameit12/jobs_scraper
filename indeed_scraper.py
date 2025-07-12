from seleniumbase import SB
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from bleach import clean
import time
import random
import logging
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def wait_for_full_description(driver, selector, min_length=500, timeout=15):
   """Your original wait function - unchanged"""
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

def wait_for_turnstile_completion(driver, timeout=60):
    """Wait for Turnstile auto-verification using DOM-based approach"""
    print("🔍 Waiting for Turnstile auto-verification...")
    
    for i in range(timeout):
        try:
            # Check for the hidden input that Turnstile populates upon completion
            hidden_input = driver.find_element(By.CSS_SELECTOR, "input[name='cf-turnstile-response']")
            response_value = hidden_input.get_attribute('value')
            if response_value:
                print(f"✅ Turnstile auto-verified successfully! Response: {response_value[:20]}...")
                return True
            elif i % 10 == 0:  # Print status every 10 seconds
                print(f"🔍 Still waiting... ({i}/60 seconds) - Response field empty")
        except Exception as e:
            if i % 10 == 0:
                print(f"🔍 Still waiting... ({i}/60 seconds) - No response field found yet")
        
        # Also check if page title changes (indicates completion)
        current_title = driver.title
        if "Just a moment" not in current_title:
            print(f"✅ Page title changed to: '{current_title}'")
            return True
            
        time.sleep(1)
    
    print(f"❌ Turnstile verification timed out after {timeout} seconds")
    # Save page source for debugging
    with open("debug_turnstile_timeout.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("💾 Saved page source to debug_turnstile_timeout.html for analysis")
    return False
   
    """Wait for Turnstile auto-verification using DOM-based approach"""
    print("🔍 Waiting for Turnstile auto-verification...")
    
    for i in range(timeout):
        try:
            # Check for the hidden input that Turnstile populates upon completion
            hidden_input = driver.find_element(By.CSS_SELECTOR, "input[name='cf-turnstile-response']")
            if hidden_input.get_attribute('value'):
                print("✅ Turnstile auto-verified successfully!")
                return True
        except:
            pass
        
        # Also check if page title changes (indicates completion)
        if "Just a moment" not in driver.title:
            print("✅ Page title changed - challenge likely completed!")
            return True
            
        time.sleep(1)
    
    print("❌ Turnstile verification timed out")
    return False

def extract_job_details(driver, url):
   driver.get(url)
   print(f"\n Visiting: {url}")
   time.sleep(random.uniform(2, 4))

   # ✅ FIXED: Use the working selector that your debug shows is finding titles
   try:
       title = WebDriverWait(driver, 10).until(
           EC.presence_of_element_located((By.CSS_SELECTOR, ".jobsearch-JobInfoHeader-title"))
       ).text.strip()
       print(f"🔍 DEBUG: Successfully extracted title: '{title}'")
   except TimeoutException:
       print("🔍 DEBUG: Title not found with WebDriverWait")
       title = "[Not Found]"

   try:
       company = driver.find_element(By.CSS_SELECTOR, "div[data-testid='inlineHeader-companyName']").text.strip()
   except Exception:
       company = "[Not Found]"

   try:
       location = driver.find_element(By.CSS_SELECTOR, "div[data-testid='inlineHeader-companyLocation']").text.strip()
   except Exception:
       location = "[Not Found]"

   try:
       desc_element = driver.find_element(By.CSS_SELECTOR, "div[id='jobDescriptionText']")
       raw_html = desc_element.get_attribute('innerHTML')
   except Exception:
       raw_html = "[Not Found]"

   allowed_tags = ['p', 'br', 'ul', 'li', 'ol', 'strong', 'em', 'h2', 'h3', 'a', 'b']
   allowed_attrs = {'a': ['href', 'title']}
   if raw_html != "[Not Found]" and "<span" in raw_html:
       raw_html = raw_html.replace("<span>", "").replace("</span>", "")
   description = clean(raw_html, tags=allowed_tags, attributes=allowed_attrs)
   
   print("======== JOB DEBUG INFO ========")
   print("🔗 URL:", url)
   print("\n🔤 RAW HTML EXCERPT:\n", str(raw_html)[:1000])
   print("\n🧼 CLEANED HTML EXCERPT:\n", description[:1000])
   print("=================================\n")

   print("===== JOB DETAIL EXTRACTED =====")
   print("Title:", title)
   print("Company:", company)
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


def scrape_jobs(title, location, max_jobs=10, seniority=None, headless=False):
   """Your original logic with SeleniumBase browser initialization"""
   print("🔍 BASIC DEBUG: Function called with parameters:")
   print(f"  - title: '{title}'")
   print(f"  - location: '{location}'") 
   print(f"  - max_jobs: {max_jobs}")
   print(f"  - seniority: '{seniority}'")
   
   try:  # <-- ONLY CHANGE: Added this try statement
       logger.info("🌐 Launching SeleniumBase browser...")
       
       # Use your exact browser User-Agent
       user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
       
       logger.info("🌐 Trying minimal SeleniumBase UC Mode...")

       with SB(uc=True, headless=True) as sb:
           driver = sb.driver
           logger.info("✅ SeleniumBase UC Mode initialized successfully")

           # Test connection immediately and handle disconnection
           try:
               test_url = driver.current_url
               logger.info(f"🔍 Driver connection working: {test_url}")
           except Exception as conn_error:
               logger.error(f"❌ Driver connection failed: {conn_error}")
               # Try to reconnect
               driver = sb.driver
               logger.info("🔄 Attempted driver reconnection")

           # ADD ALL THE SCRAPING LOGIC HERE:
           # Add anti-detection scripts
           user_agents = [
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
           ]
           selected_ua = random.choice(user_agents)

           driver.execute_script(f"Object.defineProperty(navigator, 'userAgent', {{get: () => '{selected_ua}'}});")
           driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

           # Try UC navigation with tab switching
           print("🔄 Trying uc_open_with_tab navigation...")
           sb.uc_open_with_tab("https://www.indeed.com/")
           time.sleep(3)
           sb.uc_switch_to_tab(0)  # Switch to first tab
           logger.info(f"🔍 Page loaded - URL: {driver.current_url}")
           logger.info(f"🔍 Page title: {driver.title}")

           # DOM-based Turnstile handling for homepage
           if "Just a moment" in driver.title or "Additional Verification Required" in driver.page_source:
               print("🔍 Detected Cloudflare Turnstile challenge on homepage")
               print("🔄 Trying sb.solve_captcha() method...")
               try:
                 sb.solve_captcha(timeout=60)
                 print("✅ solve_captcha() completed")
                 time.sleep(5)                  
               except Exception as e:
                 print(f"❌ solve_captcha() failed: {e}")
                 print("🔄 Trying manual wait approach...")
                 # Extended wait to see if challenge resolves
                 for i in range(90):  # 90 seconds 
                    if "Just a moment" not in driver.title:
                       print("✅ Challenge appears to have resolved!")
                       break
                    time.sleep(1)
                 else:
                    print("❌ Challenge still blocking after 90 seconds")

           time.sleep(2)

           # Add stealth page load simulation
           driver.execute_script("window.scrollTo(0, 100);")
           time.sleep(1)
           driver.execute_script("window.scrollTo(0, 0);")

           # Human-like delay with randomization
           time.sleep(random.uniform(3, 7))

           print("⌨️ Filling job title and location...")
           WebDriverWait(driver, 10).until(
               EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='q']"))
           ).send_keys(title)

           # Ultra-aggressive location clearing
           location_input = WebDriverWait(driver, 10).until(
               EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='l']"))
           )

           # Multiple clearing attempts
           for _ in range(3):  # Try 3 times
               location_input.clear()
               location_input.send_keys("")
               driver.execute_script("arguments[0].value = '';", location_input)
               driver.execute_script("arguments[0].select();", location_input)
               driver.execute_script("document.execCommand('delete');")
               time.sleep(0.5)

           # Verify it's actually empty
           current_value = location_input.get_attribute('value')
           print(f"🔍 DEBUG: Location field after clearing: '{current_value}'")

           # If still not empty, try one more time
           if current_value.strip():
               location_input.clear()
               driver.execute_script("arguments[0].value = '';", location_input)
               time.sleep(1)

           time.sleep(1)  # Give it time to process

           # Now enter your desired location
           location_input.send_keys(location)
           # Random typing delay
           time.sleep(random.uniform(1.5, 3.0))

           # Try UC navigation for search submission instead of clicking
           print("🔄 Using UC navigation for search instead of button click...")
           search_url = f"https://www.indeed.com/jobs?q={title}&l={location}&sort=relevance"
           print(f"🔍 DEBUG: Direct UC navigation to: {search_url}")

           try:
               sb.uc_open_with_reconnect(search_url, reconnect_time=10)
               time.sleep(5)
               print("✅ UC navigation completed")
           except Exception as e:
               print(f"❌ UC navigation failed: {e}")
               # Fallback to original method
               driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
               time.sleep(random.uniform(7, 12))     


            # Try SeleniumBase solve_captcha for Turnstile  
            if "Just a moment" in driver.title or "Additional Verification Required" in driver.page_source:
                print("🔍 Detected Cloudflare Turnstile challenge after search")
                print("🔄 Trying sb.solve_captcha() method...")
                try:
                    sb.solve_captcha(timeout=60)
                    print("✅ solve_captcha() completed")
                    time.sleep(5)
                except Exception as e:
                    print(f"❌ solve_captcha() failed: {e}")
                    print("🔄 Trying manual wait approach...")
                    # Extended wait to see if challenge resolves
                    for i in range(90):  # 90 seconds
                        if "Just a moment" not in driver.title:
                            print("✅ Challenge appears to have resolved!")
                            break
                        time.sleep(1)
                    else:
                        print("❌ Challenge still blocking after 90 seconds")        

               else:
                   print("🔍 DEBUG: URL already has sort parameter")
           except Exception as e:
                print(f"⚠️ Could not set sorting: {e}")

           # Add this section after the relevance sorting and before collecting job links:

           # Handle seniority filtering if specified
           if seniority:
               print(f"🎯 Applying seniority filter: {seniority}")
               try:
                   print("⏳ Waiting for search results page to load...")
                   WebDriverWait(driver, 15).until(
                       EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-jk]"))
                   )
                   time.sleep(3)

                   print("🔽 Opening Experience level filter...")
                   # Look for the Experience level dropdown button
                   experience_button = WebDriverWait(driver, 10).until(
                       EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Experience level')]"))
                   )
                   experience_button.click()
                   time.sleep(2)

                   # Take screenshot to see what's available
                  
                   # Take screenshot and save with timestamp for easy identification
                   timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                   screenshot_filename = f"debug_indeed_{timestamp}.png"
                   driver.save_screenshot(screenshot_filename)
                   print(f"🔍 DEBUG: Saved screenshot as {screenshot_filename}")

                   # Also save page source for analysis
                   with open(f"debug_page_source_{timestamp}.html", "w", encoding="utf-8") as f:
                     f.write(driver.page_source)
                   print(f"🔍 DEBUG: Saved page source as debug_page_source_{timestamp}.html")
                   print("🔍 DEBUG: Saved dropdown screenshot as debug_experience_dropdown.png")

                   # Use seniority value directly (no mapping needed)
                   indeed_level = seniority
                   print(f"☑️ Looking for experience level: {indeed_level}")

                   try:
                       # Look for the dropdown option and click it
                       dropdown_option = WebDriverWait(driver, 5).until(
                           EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(), '{indeed_level}')]"))
                       )
                       dropdown_option.click()
                       time.sleep(2)
                       print(f"✅ Selected {indeed_level}")

                       print("⏳ Waiting for filtered results to reload...")
                       time.sleep(5)  # Give Indeed time to filter results

                   except Exception as e:
                       print(f"🚫 Could not find experience level '{indeed_level}': {e}")
                       # Try alternative selectors
                       try:
                           dropdown_option = driver.find_element(By.XPATH, f"//span[contains(text(), '{indeed_level}')]")
                           dropdown_option.click()
                           print(f"✅ Selected {indeed_level} using alternative selector")
                           time.sleep(5)
                       except:
                           print("Available options might be different. Continuing without filter...")

                   print("✅ Experience level filter applied successfully")

               except Exception as e:
                   print(f"⚠️ Could not apply experience level filter: {e}")
                   print("Continuing without seniority filtering...")

           print("🔄 Clicking 'Show more' to load up to max_jobs...")
           for _ in range(5):
               cards = driver.find_elements(By.CSS_SELECTOR, "a[data-jk]")
               if len(cards) >= max_jobs + 10:
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

           # Add this right before the WebDriverWait line that's failing:
           driver.save_screenshot("debug_indeed_page.png")
           print("🔍 DEBUG: Saved screenshot as debug_indeed_page.png")
           print("🔍 DEBUG: Current URL:", driver.current_url)
           print("🔍 DEBUG: Page title:", driver.title)

           # Handle potential pop-ups that might be blocking content
           print("🔍 Checking for Indeed pop-ups and overlays...")
           try:
               # Common Indeed pop-up selectors
               pop_up_selectors = [
                 ".popover-x-button-close",
                 "[data-testid='close-button']", 
                 ".icl-CloseButton",
                 ".pn-CloseButton",
                 "#onetrust-close-btn-container button"
               ]
     
               for selector in pop_up_selectors:
                 try:
                     pop_up = WebDriverWait(driver, 2).until(
                       EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                     )
                     pop_up.click()
                     print(f"✅ Closed pop-up with selector: {selector}")
                     time.sleep(1)
                     break
                 except:
                     continue
               
           except Exception as e:
             print("No pop-ups detected")

           print("⏳ Waiting for job cards to load...")
           WebDriverWait(driver, 15).until(
               EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-jk]"))
           )

           job_links = []
           cards = driver.find_elements(By.CSS_SELECTOR, "a[data-jk]")
           print(f"🔍 Total cards collected: {len(cards)}")

           # DEBUG: Print first 5 URLs to see the actual patterns
           print("🔍 DEBUG: First 5 job URLs found:")
           for i, card in enumerate(cards[:5]):
               try:
                   href = card.get_attribute("href")
                   if href:
                       print(f"  {i+1}. {href}")
               except Exception:
                   continue

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
                   job["description"] == "[Not Found]"
               ):
                   print("⛔ Skipping invalid job.")
                   continue

               job_results.append(job)
               print(f"✅ Collected: {len(job_results)} / {max_jobs}")
               time.sleep(2)

               if len(job_results) >= max_jobs:
                   break

           return job_results
           
   except TimeoutException as e:
       print(f"❌ TIMEOUT ERROR: {e}")
       return [{
           "error_type": "timeout",
           "title": "Search Timeout",
           "company": "Error",
           "location": location,
           "link": "#",
           "description": "The job site is taking longer than usual to respond. Please try again with fewer results (5-10 jobs) or try a different location. If this keeps happening, email us at frameitbot@gmail.com",
           "formatted_description": "The job site is taking longer than usual to respond. Please try again with fewer results (5-10 jobs) or try a different location. If this keeps happening, email us at frameitbot@gmail.com"
       }]
       
   except Exception as e:
       print(f"❌ GENERAL ERROR: {e}")
       error_msg = "We're experiencing technical difficulties. Please try again in a few minutes. If you continue seeing this error, email frameitbot@gmail.com with details about what you were searching for."
       
       return [{
           "error_type": "general",
           "title": "Technical Error",
           "company": "Error", 
           "location": location,
           "link": "#",
           "description": error_msg,
           "formatted_description": error_msg
       }]

# Test the scraper
if __name__ == "__main__":
   jobs = scrape_jobs("Operational Risk", "New York", 3)
   print(f"\n🎯 FINAL RESULT: Found {len(jobs)} jobs")
   for i, job in enumerate(jobs, 1):
       print(f"{i}. {job['title']} at {job['company']}")
