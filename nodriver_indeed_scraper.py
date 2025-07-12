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
        await driver.get("https://www.indeed.com/")
        logger.info(f"🔍 Page loaded - URL: {driver.url}")
        logger.info(f"🔍 Page title: {driver.title}")

        # Check for Turnstile on homepage
        current_title = driver.title
        if "Just a moment" in current_title:
            print("🔍 Detected Cloudflare Turnstile challenge on homepage")
            await wait_for_turnstile_completion(driver)

        await asyncio.sleep(2)

        # Add stealth page load simulation
        await driver.evaluate("window.scrollTo(0, 100);")
        await asyncio.sleep(1)
        await driver.evaluate("window.scrollTo(0, 0);")

        # Human-like delay with randomization
        await asyncio.sleep(random.uniform(3, 7))

        print("⌨️ Filling job title and location...")
        
        # Fill job title
        title_input = await driver.find("input[name='q']", timeout=10)
        if title_input:
            await title_input.send_keys(title)
            await asyncio.sleep(random.uniform(1, 2))

        # Clear and fill location
        location_input = await driver.find("input[name='l']", timeout=10)
        if location_input:
            # Multiple clearing attempts
            for _ in range(3):
                await location_input.clear_input()
                await asyncio.sleep(0.5)
                await driver.evaluate("arguments[0].value = '';", location_input)
                await asyncio.sleep(0.5)

            # Verify it's cleared
            current_value = await location_input.get_attribute('value')
            print(f"🔍 DEBUG: Location field after clearing: '{current_value}'")

            # Enter new location
            await location_input.send_keys(location)
            await asyncio.sleep(random.uniform(1.5, 3.0))

        # Submit search
        search_button = await driver.find("button[type='submit']", timeout=10)
        if search_button:
            await search_button.click()
            await asyncio.sleep(random.uniform(5, 8))

        # Check for Turnstile after search
        current_title = driver.title
        if "Just a moment" in current_title:
            print("🔍 Detected Cloudflare Turnstile challenge after search")
            success = await wait_for_turnstile_completion(driver)
            if not success:
                print("❌ Turnstile challenge not resolved, but continuing...")

        # Handle seniority filtering if specified
        if seniority:
            print(f"🎯 Applying seniority filter: {seniority}")
            try:
                print("⏳ Waiting for search results page to load...")
                await asyncio.sleep(3)

                print("🔽 Opening Experience level filter...")
                experience_button = await driver.find("//button[contains(text(), 'Experience level')]", timeout=10)
                if experience_button:
                    await experience_button.click()
                    await asyncio.sleep(2)

                    # Save screenshot for debugging
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    await driver.save_screenshot(f"debug_nodriver_{timestamp}.png")
                    print(f"🔍 DEBUG: Saved screenshot as debug_nodriver_{timestamp}.png")

                    # Look for seniority option
                    indeed_level = seniority
                    print(f"☑️ Looking for experience level: {indeed_level}")

                    dropdown_option = await driver.find(f"//a[contains(text(), '{indeed_level}')]", timeout=5)
                    if dropdown_option:
                        await dropdown_option.click()
                        await asyncio.sleep(2)
                        print(f"✅ Selected {indeed_level}")
                        await asyncio.sleep(5)
                    else:
                        print(f"🚫 Could not find experience level '{indeed_level}'")

                print("✅ Experience level filter applied successfully")

            except Exception as e:
                print(f"⚠️ Could not apply experience level filter: {e}")

        # Load more jobs
        print("🔄 Loading more jobs...")
        for _ in range(5):
            try:
                show_more = await driver.find("//button[contains(., 'Show more')]", timeout=5)
                if show_more:
                    await driver.evaluate("arguments[0].scrollIntoView({block: 'center'});", show_more)
                    await show_more.click()
                    await asyncio.sleep(3)
                else:
                    break
            except Exception:
                break

        # Save debug screenshot
        await driver.save_screenshot("debug_nodriver_page.png")
        print("🔍 DEBUG: Saved screenshot as debug_nodriver_page.png")
        print("🔍 DEBUG: Current URL:", driver.url)
        print("🔍 DEBUG: Page title:", driver.title)

        # Collect job links
        print("⏳ Collecting job links...")
        job_links = []
        
        try:
            job_cards = await driver.find_all("a[data-jk]", timeout=15)
            print(f"🔍 Total cards found: {len(job_cards)}")

            for card in job_cards:
                try:
                    href = await card.get_attribute("href")
                    if href:
                        job_links.append(href)
                except Exception:
                    continue

            print(f"🔍 Found {len(job_links)} job links.\n")

        except Exception as e:
            print(f"❌ Error collecting job links: {e}")
            # Take screenshot for debugging
            await driver.save_screenshot("debug_nodriver_error.png")
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
        await browser.stop()
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
