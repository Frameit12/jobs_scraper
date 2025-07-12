import nodriver as uc
import asyncio
import time
import random
import logging
from bs4 import BeautifulSoup
from bleach import clean
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def wait_for_turnstile_completion(driver, timeout=60):
    """Wait for Turnstile auto-verification using DOM-based approach"""
    print("🔍 Waiting for Turnstile auto-verification...")
    
    for i in range(timeout):
        try:
            # Check for the hidden input that Turnstile populates upon completion
            hidden_input = await driver.find("input[name='cf-turnstile-response']")
            if hidden_input:
                response_value = await hidden_input.get_attribute('value')
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
            
        await asyncio.sleep(1)
    
    print(f"❌ Turnstile verification timed out after {timeout} seconds")
    # Save page source for debugging
    page_source = await driver.get_content()
    with open("debug_nodriver_turnstile_timeout.html", "w", encoding="utf-8") as f:
        f.write(page_source)
    print("💾 Saved page source to debug_nodriver_turnstile_timeout.html for analysis")
    return False

async def extract_job_details(driver, url):
    await driver.get(url)
    print(f"\n Visiting: {url}")
    await asyncio.sleep(random.uniform(2, 4))

    # Extract job title
    try:
        title_element = await driver.find(".jobsearch-JobInfoHeader-title", timeout=10)
        if title_element:
            title = await title_element.get_text()
            title = title.strip()
            print(f"🔍 DEBUG: Successfully extracted title: '{title}'")
        else:
            title = "[Not Found]"
    except Exception as e:
        print(f"🔍 DEBUG: Title not found: {e}")
        title = "[Not Found]"

    # Extract company
    try:
        company_element = await driver.find("div[data-testid='inlineHeader-companyName']")
        if company_element:
            company = await company_element.get_text()
            company = company.strip()
        else:
            company = "[Not Found]"
    except Exception:
        company = "[Not Found]"

    # Extract location
    try:
        location_element = await driver.find("div[data-testid='inlineHeader-companyLocation']")
        if location_element:
            location = await location_element.get_text()
            location = location.strip()
        else:
            location = "[Not Found]"
    except Exception:
        location = "[Not Found]"

    # Extract job description
    try:
        desc_element = await driver.find("div[id='jobDescriptionText']")
        if desc_element:
            raw_html = await desc_element.get_attribute('innerHTML')
        else:
            raw_html = "[Not Found]"
    except Exception:
        raw_html = "[Not Found]"

    # Clean description
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

async def scrape_jobs_async(title, location, max_jobs=10, seniority=None, headless=True):
    """Nodriver implementation for Indeed scraping"""
    print("🔍 BASIC DEBUG: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    
    try:
        logger.info("🌐 Launching Nodriver browser...")
        
        # Configure browser options for stealth
        browser = await uc.start(
            headless=headless,
            user_data_dir=None,  # Use temporary profile
            browser_args=[
                '--no-sandbox',
                '--disable-dev-shm-usage', 
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor',
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',  # Faster loading
                '--disable-javascript',  # We'll enable selectively
            ]
        )
        
        # Get the main tab
        driver = await browser.get("about:blank")
        logger.info("✅ Nodriver initialized successfully")

        # Add anti-detection scripts
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        selected_ua = random.choice(user_agents)

        # Advanced anti-detection using Nodriver's evaluate method
        await driver.evaluate(f"Object.defineProperty(navigator, 'userAgent', {{get: () => '{selected_ua}'}});")
        await driver.evaluate("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        await driver.evaluate("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});")
        await driver.evaluate("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});")
        
        # Navigate to Indeed
        print("🔍 STEP 1: About to navigate to mobile Indeed...")
        await driver.get("https://www.m.indeed.com/")
        print("🔍 STEP 1: Navigation completed")
        
        print("🔍 STEP 2: Getting page info...")
        logger.info(f"🔍 Page loaded - URL: {driver.url}")
        logger.info(f"🔍 Page title: {driver.title}")
        print(f"🔍 STEP 2: Page info retrieved - Title: '{driver.title}', URL: '{driver.url}'")

        print("🔍 STEP 3: Starting post-load setup...")
        try:
            print(f"🔍 STEP 3a: Mobile site loaded successfully!")
            print(f"🔍 STEP 3b: Current title: '{driver.title}'")
            print(f"🔍 STEP 3c: Current URL: '{driver.url}'")
            
            # Check for Turnstile on homepage
            print("🔍 STEP 4: Checking for Turnstile...")
            current_title = driver.title
            if "Just a moment" in current_title:
                print("🔍 STEP 4a: Detected Cloudflare Turnstile challenge on homepage")
                await wait_for_turnstile_completion(driver)
            else:
                print("🔍 STEP 4b: No Turnstile detected")

            print("🔍 STEP 5: Starting initial delay...")
            await asyncio.sleep(2)
            print("🔍 STEP 5: Initial delay completed")

            # Add stealth page load simulation
            print("🔍 STEP 6: Starting stealth simulation...")
            await driver.evaluate("window.scrollTo(0, 100);")
            print("🔍 STEP 6a: First scroll completed")
            await asyncio.sleep(1)
            await driver.evaluate("window.scrollTo(0, 0);")
            print("🔍 STEP 6b: Stealth simulation completed")

        except Exception as e:
            print(f"❌ ERROR in STEP 3-6 setup: {e}")
            print(f"❌ ERROR TYPE: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise e

        # Human-like delay with randomization
        print("🔍 STEP 7: Starting human delay...")
        delay_time = random.uniform(3, 7)
        print(f"🔍 STEP 7: Waiting {delay_time:.1f} seconds...")
        await asyncio.sleep(delay_time)
        print("🔍 STEP 7: Human delay completed")

        print("🔍 STEP 8: Starting form filling...")
        print("⌨️ Filling job title and location...")
        
        # Fill job title
        print("🔍 STEP 8a: Looking for job title input...")
        title_input = await driver.find("input[name='q']", timeout=10)
        if title_input:
            print("🔍 STEP 8b: Job title input found, filling...")
            await title_input.send_keys(title)
            await asyncio.sleep(random.uniform(1, 2))
            print("🔍 STEP 8c: Job title filled")
        else:
            print("❌ STEP 8b: Job title input NOT found")

        # Clear and fill location
        print("🔍 STEP 9: Looking for location input...")
        location_input = await driver.find("input[name='l']", timeout=10)
        if location_input:
            print("🔍 STEP 9a: Location input found, clearing...")
            # Multiple clearing attempts
            for i in range(3):
                print(f"🔍 STEP 9b{i+1}: Clearing attempt {i+1}")
                await location_input.clear_input()
                await asyncio.sleep(0.5)
                await driver.evaluate("arguments[0].value = '';", location_input)
                await asyncio.sleep(0.5)

            # Verify it's cleared
            current_value = await location_input.get_attribute('value')
            print(f"🔍 STEP 9c: Location field after clearing: '{current_value}'")

            # Enter new location
            print(f"🔍 STEP 9d: Entering location: '{location}'")
            await location_input.send_keys(location)
            await asyncio.sleep(random.uniform(1.5, 3.0))
            print("🔍 STEP 9e: Location entered")
        else:
            print("❌ STEP 9a: Location input NOT found")

        # Submit search
        print("🔍 STEP 10: Looking for search button...")
        search_button = await driver.find("button[type='submit'], input[type='submit']", timeout=10)
        if search_button:
            print("🔍 STEP 10a: Search button found, clicking...")
            await search_button.click()
            search_delay = random.uniform(5, 8)
            print(f"🔍 STEP 10b: Search submitted, waiting {search_delay:.1f} seconds...")
            await asyncio.sleep(search_delay)
            print("🔍 STEP 10c: Search delay completed")
        else:
            print("❌ STEP 10a: Search button NOT found")

        # Check for Turnstile after search
        print("🔍 STEP 11: Checking for post-search Turnstile...")
        current_title = driver.title
        print(f"🔍 STEP 11a: Post-search page title: '{current_title}'")
        if "Just a moment" in current_title:
            print("🔍 STEP 11b: Detected Cloudflare Turnstile challenge after search")
            success = await wait_for_turnstile_completion(driver)
            if not success:
                print("❌ STEP 11c: Turnstile challenge not resolved, but continuing...")
        else:
            print("🔍 STEP 11b: No post-search Turnstile detected")

        # Handle seniority filtering if specified
        if seniority:
            print(f"🔍 STEP 12: Applying seniority filter: {seniority}")
            try:
                print("🔍 STEP 12a: Waiting for search results page to load...")
                await asyncio.sleep(3)

                print("🔍 STEP 12b: Opening Experience level filter...")
                experience_button = await driver.find("//button[contains(text(), 'Experience level')]", timeout=10)
                if experience_button:
                    await experience_button.click()
                    await asyncio.sleep(2)

                    # Save screenshot for debugging
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    await driver.save_screenshot(f"debug_nodriver_{timestamp}.png")
                    print(f"🔍 STEP 12c: Saved screenshot as debug_nodriver_{timestamp}.png")

                    # Look for seniority option
                    indeed_level = seniority
                    print(f"🔍 STEP 12d: Looking for experience level: {indeed_level}")

                    dropdown_option = await driver.find(f"//a[contains(text(), '{indeed_level}')]", timeout=5)
                    if dropdown_option:
                        await dropdown_option.click()
                        await asyncio.sleep(2)
                        print(f"✅ STEP 12e: Selected {indeed_level}")
                        await asyncio.sleep(5)
                    else:
                        print(f"🚫 STEP 12e: Could not find experience level '{indeed_level}'")

                print("✅ STEP 12f: Experience level filter applied successfully")

            except Exception as e:
                print(f"⚠️ STEP 12 ERROR: Could not apply experience level filter: {e}")
        else:
            print("🔍 STEP 12: No seniority filter specified, skipping")

        # Load more jobs
        print("🔍 STEP 13: Loading more jobs...")
        for i in range(5):
            try:
                print(f"🔍 STEP 13{i+1}: Looking for 'Show more' button...")
                show_more = await driver.find("//button[contains(., 'Show more')]", timeout=5)
                if show_more:
                    print(f"🔍 STEP 13{i+1}a: Found 'Show more', clicking...")
                    await driver.evaluate("arguments[0].scrollIntoView({block: 'center'});", show_more)
                    await show_more.click()
                    await asyncio.sleep(3)
                    print(f"🔍 STEP 13{i+1}b: 'Show more' clicked")
                else:
                    print(f"🔍 STEP 13{i+1}: No more 'Show more' buttons found")
                    break
            except Exception as e:
                print(f"🔍 STEP 13{i+1} ERROR: {e}")
                break

        # Save debug screenshot
        print("🔍 STEP 14: Saving debug screenshot...")
        await driver.save_screenshot("debug_nodriver_page.png")
        print("🔍 STEP 14a: Saved screenshot as debug_nodriver_page.png")
        print("🔍 STEP 14b: Current URL:", driver.url)
        print("🔍 STEP 14c: Page title:", driver.title)

        # Collect job links
        print("🔍 STEP 15: Collecting job links...")
        job_links = []
        
        try:
            print("🔍 STEP 15a: Looking for job cards...")
            job_cards = await driver.find_all("a[data-jk]", timeout=15)
            print(f"🔍 STEP 15b: Total cards found: {len(job_cards)}")

            print("🔍 STEP 15c: Extracting URLs from cards...")
            for i, card in enumerate(job_cards):
                try:
                    href = await card.get_attribute("href")
                    if href:
                        job_links.append(href)
                        if i < 3:  # Show first 3 URLs for debug
                            print(f"🔍 STEP 15c{i+1}: Found URL: {href}")
                except Exception as e:
                    print(f"🔍 STEP 15c{i+1} ERROR: {e}")
                    continue

            print(f"🔍 STEP 15d: Found {len(job_links)} job links total")

        except Exception as e:
            print(f"❌ STEP 15 ERROR: Error collecting job links: {e}")
            # Take screenshot for debugging
            await driver.save_screenshot("debug_nodriver_error.png")
            print("🔍 STEP 15 ERROR: Saved error screenshot")
            return [{
                "error_type": "collection_failed",
                "title": "Job Collection Failed",
                "company": "Error",
                "location": location,
                "link": "#",
                "description": f"Could not collect job links: {str(e)}",
                "formatted_description": f"Could not collect job links: {str(e)}"
            }]

        # Extract job details
        job_results = []
        for i, url in enumerate(job_links):
            if len(job_results) >= max_jobs:
                break
                
            try:
                job = await extract_job_details(driver, url)

                if (
                    job["title"] == "[Not Found]" or
                    job["location"] == "[Not Found]" or
                    job["description"] == "[Not Found]"
                ):
                    print("⛔ Skipping invalid job.")
                    continue

                job_results.append(job)
                print(f"✅ Collected: {len(job_results)} / {max_jobs}")
                await asyncio.sleep(2)

            except Exception as e:
                print(f"⚠️ Error extracting job {i+1}: {e}")
                continue

        # Close browser
        try:
            if browser:
                await browser.stop()
        except Exception as e:
            print(f"Browser cleanup error (non-critical): {e}")
        return job_results

    except Exception as e:
        print(f"❌ GENERAL ERROR: {e}")
        print(f"❌ ERROR TYPE: {type(e).__name__}")
        import traceback
        print(f"❌ FULL TRACEBACK:")
        traceback.print_exc()

        # Try to save a screenshot if browser is still available
        try:
            if 'driver' in locals():
                await driver.save_screenshot("debug_nodriver_error_fallback.png")
                print("💾 Saved error screenshot")
        except:
            print("💾 Could not save error screenshot")
        
        error_msg = f"Nodriver failed: {str(e)[:200]}..."
        
        return [{
            "error_type": "general",
            "title": "Nodriver Error",
            "company": "Error", 
            "location": location,
            "link": "#",
            "description": error_msg,
            "formatted_description": error_msg
        }]

def scrape_jobs(title, location, max_jobs=10, seniority=None, headless=True):
    """Synchronous wrapper for the async Nodriver scraper"""
    try:
        # Run the async function
        return asyncio.run(scrape_jobs_async(title, location, max_jobs, seniority, headless))
    except Exception as e:
        print(f"❌ ASYNCIO ERROR: {e}")
        return [{
            "error_type": "asyncio_failed",
            "title": "Async Runtime Error",
            "company": "Error",
            "location": location,
            "link": "#",
            "description": f"Async execution failed: {str(e)}",
            "formatted_description": f"Async execution failed: {str(e)}"
        }]

# Test the scraper
if __name__ == "__main__":
    jobs = scrape_jobs("Operational Risk", "New York", 3)
    print(f"\n🎯 FINAL RESULT: Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job['title']} at {job['company']}")
