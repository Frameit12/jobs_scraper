import requests
import time
import random
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def scrape_jobs(title, location, max_jobs=10, seniority=None, region="US"):
    """
    CareerJet API implementation to replace Indeed scraping
    Uses legitimate API instead of scraping
    """
    print("🔍 CAREERJET API DEBUG: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    print(f"  - region: '{region}'")
    
    try:
        # CareerJet API endpoints by country
        api_endpoints = {
            "US": "http://public-api.careerjet.com/search",
            "UK": "http://public-api.careerjet.co.uk/search", 
            "CA": "http://public-api.careerjet.ca/search",
            "AU": "http://public-api.careerjet.com.au/search"
        }
        
        # Get appropriate endpoint
        api_url = api_endpoints.get(region, api_endpoints["US"])
        print(f"🌍 Using CareerJet endpoint: {api_url}")
        
        # API parameters
        params = {
            'keywords': title,
            'location': location,
            'affid': 'dbeb46864e3514ee44146b52e98c7e8e',  # Your real affiliate ID
            'user_ip': '127.0.0.1',
            'user_agent': 'FindMeAJob/1.0',
            'locale_code': 'en_US' if region == "US" else 'en_GB',
            'pagesize': min(max_jobs, 20),  # CareerJet max is 20 per request
            'page': 1
        }
        
        # Add seniority filtering if specified
        if seniority:
            # Map your seniority levels to CareerJet's expected format
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
            print(f"🔍 API Response keys: {data.keys()}")
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
        
        # Convert to your existing job format
        job_results = []
        for i, job in enumerate(jobs_data):
            if len(job_results) >= max_jobs:
                break
                
            # Clean and format job data
            job_title = job.get('title', '[Not Found]').strip()
            company = job.get('company', '[Not Found]').strip()
            job_location = job.get('locations', location).strip()
            job_url = job.get('url', '#')
            description = job.get('description', 'No description available').strip()
            
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
        
        print(f"🎯 FINAL RESULT: Successfully retrieved {len(job_results)} jobs from CareerJet API")
        return job_results
        
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT ERROR: CareerJet API request timed out")
        return [{
            "error_type": "timeout",
            "title": "API Timeout",
            "company": "Error",
            "location": location,
            "link": "#", 
            "description": "CareerJet API request timed out. Please try again with fewer results or try later.",
            "formatted_description": "CareerJet API request timed out. Please try again with fewer results or try later."
        }]
        
    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {e}")
        return [{
            "error_type": "request_error",
            "title": "Network Error", 
            "company": "Error",
            "location": location,
            "link": "#",
            "description": f"Network error connecting to CareerJet API: {str(e)}",
            "formatted_description": f"Network error connecting to CareerJet API: {str(e)}"
        }]
        
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

# Test function
if __name__ == "__main__":
    jobs = scrape_jobs("Risk Manager", "New York", 5)
    print(f"\n🎯 FINAL RESULT: Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job['title']} at {job['company']}")
