import requests
import time
import random
import logging
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_full_careerjet_description(job_url):
    """Extract full description from individual CareerJet job page"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
        }
        
        response = requests.get(job_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the content section (from your HTML analysis)
        content_section = soup.find('section', class_='content')
        if content_section:
            # Get all text content
            full_description = content_section.get_text(separator=' ', strip=True)
            print(f"🔍 Extracted full description: {len(full_description)} chars")
            return full_description
            
    except Exception as e:
        print(f"⚠️ Could not extract full description from {job_url}: {e}")
        
    return None

def scrape_jobs(title, location, max_jobs=10, seniority=None, region="US"):
    """
    Enhanced CareerJet API: Get URLs from API, then extract full descriptions
    """
    print("🚨 CAREERJET ENHANCED VERSION - FULL DESCRIPTIONS")
    print("🔍 CAREERJET API DEBUG: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    print(f"  - region: '{region}'")
    
    try:
        # STEP 1: Get job URLs from CareerJet API (your existing code)
        api_url = "http://public.api.careerjet.net/search"
        
        # Enhanced regional mapping for CareerJet
        region_mapping = {
            "US": "en_US",
            "UK": "en_GB", 
            "CA": "en_CA",
            "AU": "en_AU",
            "DE": "de_DE",
            "SG": "en_SG",
            "IN": "en_IN"
        }

        locale_code = region_mapping.get(region, "en_US")  # Default to US
        print(f"🌍 Using CareerJet locale: {locale_code} for region: {region}")        
        
        # API parameters
        params = {
            'keywords': title,
            'location': location,
            'affid': 'dbeb46864e3514ee44146b52e98c7e8e',
            'user_ip': '127.0.0.1',
            'user_agent': 'FindMeAJob/1.0',
            'locale_code': locale_code,
            'pagesize': min(max_jobs, 20),
            'page': 1
        }
        
        # Add seniority filtering if specified
        if seniority:
            seniority_mapping = {
                'intern': 'internship',
                'junior': 'entry level',
                'analyst': 'entry level',
                'associate': 'experienced', 
                'avp': 'experienced',
                'vp': 'manager',
                'svp': 'executive',
                'director': 'executive',
                'md': 'executive',
                'csuite': 'executive'
            }
            mapped_seniority = seniority_mapping.get(seniority, '')
            if mapped_seniority:
                params['keywords'] = f"{title} {mapped_seniority}"
                print(f"🎯 Applied seniority filter: {mapped_seniority}")
        
        print(f"🔍 API Request params: {params}")
        
        # Make API request
        response = requests.get(api_url, params=params, timeout=30)
        print(f"🔍 API Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API Error: Status {response.status_code}")
            return [{
                "error_type": "api_error",
                "title": "CareerJet API Error",
                "company": "Error",
                "location": location,
                "link": "#",
                "description": f"CareerJet API returned status {response.status_code}. Please try again later.",
                "formatted_description": f"CareerJet API returned status {response.status_code}. Please try again later."
            }]
        
        # Parse JSON response
        try:
            data = response.json()
            # STEP 1 DEBUG: Save raw API response
            print("🔍 STEP 1 DEBUG: Raw API response structure")
            print(f"Response keys: {data.keys()}")
            print(f"Response type field: {data.get('type', 'NO_TYPE_FIELD')}")
            print(f"Number of jobs: {len(data.get('jobs', []))}")

            # Save first job for analysis
            if data.get('jobs'):
                first_job = data.get('jobs')[0]
                print("🔍 STEP 1 DEBUG: First job structure:")
                for key, value in first_job.items():
                    print(f"  {key}: {str(value)[:100]}...")
    
                # Save to file for detailed analysis
                import json
                with open("debug_careerjet_response.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("💾 Saved full response to debug_careerjet_response.json")
            
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}")
            return [{
                "error_type": "json_error", 
                "title": "API Response Error",
                "company": "Error",
                "location": location,
                "link": "#",
                "description": "Could not parse CareerJet API response. Please try again later.",
                "formatted_description": "Could not parse CareerJet API response. Please try again later."
            }]
        
        # Check for API errors
        if data.get('type') == 'JOBS':
            jobs_data = data.get('jobs', [])
            print(f"🔍 Found {len(jobs_data)} jobs from CareerJet API")
        else:
            print(f"❌ API Error: {data.get('type', 'Unknown error')}")
            return [{
                "error_type": "api_response_error",
                "title": "No Jobs Found",
                "company": "CareerJet",
                "location": location, 
                "link": "#",
                "description": f"CareerJet API error: {data.get('type', 'Unknown error')}",
                "formatted_description": f"CareerJet API error: {data.get('type', 'Unknown error')}"
            }]
        
        # STEP 2: Extract full descriptions (NEW PART)
        job_results = []
        for i, job in enumerate(jobs_data):
            if len(job_results) >= max_jobs:
                break
                
            # Get basic job data from API
            job_title = job.get('title', '[Not Found]').strip()
            company = job.get('company', '[Not Found]').strip()
            job_location = job.get('locations', location).strip()
            job_url = job.get('url', '#')
            short_description = job.get('description', 'No description available').strip()

            print(f"🔍 STEP 2 DEBUG: Processing job {i+1}")
            print(f"  Raw URL from API: {job.get('url', 'NO_URL')}")
            print(f"  URL type: {type(job.get('url'))}")
            print(f"  URL length: {len(str(job.get('url', '')))}")
            print(f"  Contains 'clk/': {'clk/' in str(job.get('url', ''))}")
            print(f"  Contains 'jobviewtrack': {'jobviewtrack' in str(job.get('url', ''))}")            
            
            print(f"🔍 Processing job {i+1}: {job_title}")
            print(f"🔍 Short description length: {len(short_description)} chars")
            
            # STEP 3: Get full description from individual job page
            full_description = extract_full_careerjet_description(job_url)
            
            # Use full description if available, otherwise use short one
            if full_description and len(full_description) > len(short_description):
                description = full_description
                print(f"✅ Using full description: {len(description)} chars")
            else:
                description = short_description
                print(f"⚠️ Using short description: {len(description)} chars")
            
            # Basic description cleanup
            import html
            description = html.unescape(description)
            description = description.replace('\n', ' ').replace('\r', ' ')
            
            formatted_job = {
                'title': job_title,
                'company': company,
                'location': job_location,
                'link': job_url,
                'description': description,
                'formatted_description': description
            }
            
            job_results.append(formatted_job)
            print(f"✅ Processed job {i+1}: {job_title} at {company}")
            
            # Add delay to be respectful
            time.sleep(2)
        
        print(f"🎯 FINAL RESULT: Successfully retrieved {len(job_results)} jobs from CareerJet")
        return job_results
        
    except Exception as e:
        print(f"❌ GENERAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        return [{
            "error_type": "general",
            "title": "CareerJet API Error",
            "company": "Error",
            "location": location,
            "link": "#", 
            "description": f"CareerJet API integration error: {str(e)}",
            "formatted_description": f"CareerJet API integration error: {str(e)}"
        }]

def test_url_patterns():
    """Test different URL patterns we're seeing"""
    import requests
    
    test_urls = [
        "https://www.careerjet.co.uk/",
        "https://jobviewtrack.com/",
        "Your actual problematic URL here"  # Replace with real URL
    ]
    
    for url in test_urls:
        try:
            response = requests.get(url, timeout=10)
            print(f"✅ {url}: Status {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"⏰ {url}: TIMEOUT")
        except Exception as e:
            print(f"❌ {url}: ERROR {e}")

# Run this test
test_url_patterns()

# Test function
if __name__ == "__main__":
    jobs = scrape_jobs("Risk Manager", "New York", 3)
    print(f"\n🎯 FINAL RESULT: Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job['title']} at {job['company']}")
