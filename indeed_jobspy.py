"""
Indeed integration using jobspy library
Official support for Indeed confirmed by Perplexity research
"""

def scrape_jobs(title, location, max_jobs=10, seniority=None, region="US"):
    print("🔍 JOBSPY INDEED DEBUG: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    print(f"  - region: '{region}'")
    
    try:
        # Import jobspy - try different import patterns
        try:
            from jobspy import scrape_jobs as jobspy_scrape
            print("✅ Import successful: from jobspy import scrape_jobs")
        except ImportError:
            try:
                import jobspy
                jobspy_scrape = jobspy.scrape_jobs
                print("✅ Import successful: import jobspy")
            except ImportError as e:
                print(f"❌ All import attempts failed: {e}")
                return [{
                    "error_type": "import_error",
                    "title": "jobspy Not Available",
                    "company": "Error",
                    "location": location,
                    "link": "#",
                    "description": "jobspy library not installed or accessible. Check Railway deployment logs.",
                    "formatted_description": "jobspy library not installed or accessible. Check Railway deployment logs."
                }]
        
        # Map region to country for jobspy
        country_mapping = {
            "US": "usa",
            "UK": "uk", 
            "SG": "singapore",
            "DE": "germany",
            "CA": "canada",
            "AU": "australia"
        }
        country = country_mapping.get(region, "usa")
        print(f"🌍 Using country: {country}")
        
        # Build search term with seniority
        search_term = title
        if seniority:
            seniority_keywords = {
                'intern': 'intern OR internship OR graduate',
                'junior': 'junior OR "entry level"',
                'analyst': 'analyst',
                'associate': 'associate OR "mid level"',
                'avp': 'senior OR AVP OR "assistant vice president"',
                'vp': '"vice president" OR VP OR principal',
                'svp': '"senior vice president" OR "head of"',
                'director': 'director',
                'md': '"managing director" OR MD',
                'csuite': 'CEO OR CTO OR CFO OR "chief executive"'
            }
            if seniority in seniority_keywords:
                search_term = f"{title} {seniority_keywords[seniority]}"
                print(f"🎯 Enhanced search term: {search_term}")
        
        # JobSpy parameters for Indeed
        search_params = {
            "site_name": ["indeed"],  # Focus only on Indeed
            "search_term": search_term,
            "location": location,
            "results_wanted": min(max_jobs, 50),  # jobspy max limit
            "hours_old": 168,  # Last week
            "country_indeed": country,  # Country-specific Indeed site
            "verbose": 1,  # Enable debug output
            "linkedin_fetch_description": False,  # Faster execution
            "offset": 0  # Start from first result
        }
        
        print(f"🔍 Calling jobspy with params: {search_params}")
        
        # Call jobspy scraper
        df = jobspy_scrape(**search_params)
        
        if df is None:
            print("❌ jobspy returned None")
            return [{
                "title": "JobSpy Returned None",
                "company": "jobspy",
                "location": location,
                "link": "#",
                "description": "JobSpy returned None. This could indicate Indeed blocking, rate limiting, or no results found.",
                "formatted_description": "JobSpy returned None. This could indicate Indeed blocking, rate limiting, or no results found."
            }]
        
        print(f"📊 jobspy returned DataFrame with shape: {df.shape}")
        print(f"📊 DataFrame columns: {list(df.columns)}")
        
        if df.empty:
            print("❌ jobspy returned empty DataFrame")
            return [{
                "title": "No Indeed Jobs Found",
                "company": "jobspy",
                "location": location,
                "link": "#",
                "description": f"No jobs found on Indeed for '{title}' in '{location}'. Try different keywords or check if Indeed is accessible.",
                "formatted_description": f"No jobs found on Indeed for '{title}' in '{location}'. Try different keywords or check if Indeed is accessible."
            }]
        
        # Debug: Show first few rows
        print("🔍 First 2 rows of data:")
        for i, row in df.head(2).iterrows():
            print(f"  Row {i}: {dict(row)}")
        
        # Convert DataFrame to job format
        job_results = []
        for index, row in df.iterrows():
            if len(job_results) >= max_jobs:
                break
                
            # Extract data with comprehensive fallbacks
            job_title = str(row.get('title', '[Not Found]')).strip()
            company = str(row.get('company', '[Not Found]')).strip()
            job_location = str(row.get('location', location)).strip()
            job_url = str(row.get('job_url', '#'))
            description = str(row.get('description', 'No description available')).strip()
            
            # Handle NaN/None values
            if job_title in ['nan', 'None', '']:
                job_title = '[Not Found]'
            if company in ['nan', 'None', '']:
                company = '[Not Found]'
            if description in ['nan', 'None', '']:
                description = 'No description available'
            
            # Clean description
            if description and description != 'No description available':
                # Remove HTML tags
                import re
                description = re.sub('<[^<]+?>', '', description)
                # Clean whitespace
                description = description.replace('\n', ' ').replace('\r', ' ')
                description = ' '.join(description.split())
                # Truncate if too long
                if len(description) > 2000:
                    description = description[:2000] + "..."
            
            # Build job object
            formatted_job = {
                'title': job_title,
                'company': company,
                'location': job_location,
                'link': job_url,
                'description': description,
                'formatted_description': description
            }
            
            job_results.append(formatted_job)
            print(f"✅ Processed job {len(job_results)}: {job_title} at {company}")
        
        print(f"🎯 FINAL RESULT: Successfully retrieved {len(job_results)} Indeed jobs using jobspy")
        return job_results
        
    except Exception as e:
        print(f"❌ JOBSPY INDEED ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Provide helpful error context
        error_msg = f"JobSpy Indeed integration error: {str(e)}"
        if "timeout" in str(e).lower():
            error_msg += " This might indicate Indeed is blocking requests or the service is slow."
        elif "403" in str(e) or "forbidden" in str(e).lower():
            error_msg += " This indicates Indeed is blocking the request."
        elif "rate" in str(e).lower():
            error_msg += " This indicates rate limiting is in effect."
        
        return [{
            "error_type": "jobspy_error",
            "title": "JobSpy Indeed Error",
            "company": "Error",
            "location": location,
            "link": "#",
            "description": error_msg,
            "formatted_description": error_msg
        }]

# Test function
if __name__ == "__main__":
    jobs = scrape_jobs("Software Engineer", "New York", 3)
    print(f"\n🎯 FINAL RESULT: Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job['title']} at {job['company']}")
