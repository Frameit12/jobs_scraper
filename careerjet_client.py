from careerjet_api import CareerjetAPIClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def scrape_jobs(title, location, max_jobs=10, seniority=None, region="US"):
    """
    CareerJet official client library implementation
    Much more reliable than manual API calls
    """
    print("🔍 CAREERJET CLIENT DEBUG: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    print(f"  - region: '{region}'")
    
    try:
        # Initialize CareerJet client
        cj = CareerjetAPIClient("en_US")  # or "en_GB" for UK
        print("✅ CareerJet client initialized successfully")
        
        # Build search parameters
        search_params = {
            'keywords': title,
            'location': location,
            'affid': 'dbeb46864e3514ee44146b52e98c7e8e',  # Your affiliate ID
            'user_ip': '127.0.0.1',
            'user_agent': 'FindMeAJob/1.0',
            'pagesize': min(max_jobs, 20),  # Max 20 per request
            'page': 1,
            'sort': 'relevance'
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
                search_params['keywords'] = f"{title} {mapped_seniority}"
                print(f"🎯 Applied seniority filter: {mapped_seniority}")
        
        print(f"🔍 Search parameters: {search_params}")
        
        # Make API call using official client
        result = cj.search(search_params)
        print(f"🔍 API call completed")
        print(f"🔍 Result type: {type(result)}")
        print(f"🔍 Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        
        # Check if search was successful
        if result.get('type') != 'JOBS':
            error_msg = result.get('type', 'Unknown error')
            print(f"❌ CareerJet API error: {error_msg}")
            return [{
                "error_type": "api_error",
                "title": "CareerJet Search Error",
                "company": "Error",
                "location": location,
                "link": "#",
                "description": f"CareerJet API error: {error_msg}",
                "formatted_description": f"CareerJet API error: {error_msg}"
            }]
        
        # Extract jobs from response
        jobs_data = result.get('jobs', [])
        total_jobs = result.get('hits', 0)
        print(f"🔍 Found {len(jobs_data)} jobs (total available: {total_jobs})")
        
        if not jobs_data:
            return [{
                "title": "No Jobs Found",
                "company": "CareerJet",
                "location": location,
                "link": "#",
                "description": f"No jobs found for '{title}' in '{location}'. Try different keywords or location.",
                "formatted_description": f"No jobs found for '{title}' in '{location}'. Try different keywords or location."
            }]
        
        # Convert to your app's job format
        job_results = []
        for i, job in enumerate(jobs_data):
            if len(job_results) >= max_jobs:
                break
                
            # Extract job data with fallbacks
            job_title = job.get('title', '[Not Found]').strip()
            company = job.get('company', '[Not Found]').strip()
            job_location = job.get('locations', location).strip()
            job_url = job.get('url', '#')
            description = job.get('description', 'No description available').strip()
            
            # Clean description
            import html
            description = html.unescape(description)
            # Remove excessive whitespace
            description = ' '.join(description.split())
            
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
        
        print(f"🎯 FINAL RESULT: Successfully retrieved {len(job_results)} jobs using CareerJet client")
        return job_results
        
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        return [{
            "error_type": "import_error",
            "title": "CareerJet Client Missing",
            "company": "Error",
            "location": location,
            "link": "#",
            "description": "CareerJet API client not installed. Run: pip install careerjet-api-client",
            "formatted_description": "CareerJet API client not installed. Run: pip install careerjet-api-client"
        }]
        
    except Exception as e:
        print(f"❌ CAREERJET CLIENT ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        return [{
            "error_type": "client_error",
            "title": "CareerJet Client Error",
            "company": "Error",
            "location": location,
            "link": "#",
            "description": f"CareerJet client error: {str(e)}",
            "formatted_description": f"CareerJet client error: {str(e)}"
        }]

# Test function
if __name__ == "__main__":
    jobs = scrape_jobs("Risk Manager", "New York", 5)
    print(f"\n🎯 FINAL RESULT: Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job['title']} at {job['company']}")
