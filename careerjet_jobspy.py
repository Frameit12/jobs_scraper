"""
CareerJet integration using python-jobspy library
Based on research finding: "95% success rate, actively maintained, updated March 2025"
"""

def scrape_jobs(title, location, max_jobs=10, seniority=None, region="US"):
    print("🔍 PYTHON-JOBSPY DEBUG: Function called with parameters:")
    print(f"  - title: '{title}'")
    print(f"  - location: '{location}'") 
    print(f"  - max_jobs: {max_jobs}")
    print(f"  - seniority: '{seniority}'")
    print(f"  - region: '{region}'")
    
    try:
        # Import jobspy (this will tell us if it's properly installed)
        
        try:
            from jobspy import scrape_jobs as jobspy_scrape
            print("✅ Import successful: from jobspy import scrape_jobs")
        except ImportError:
            try:
                from python_jobspy import scrape_jobs as jobspy_scrape
                print("✅ Import successful: from python_jobspy import scrape_jobs")
            except ImportError:
                try:
                    import jobspy
                    jobspy_scrape = jobspy.scrape_jobs
                    print("✅ Import successful: import jobspy")
                except ImportError as e:
                    print(f"❌ All import attempts failed: {e}")
                    raise ImportError("python-jobspy not found - tried all import methods")        
                
        # Map your regions to jobspy country codes
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
        
        # Build search parameters
        search_params = {
            "site_name": ["careerjet"],  # Focus on CareerJet specifically
            "search_term": title,
            "location": location,
            "results_wanted": min(max_jobs, 50),  # jobspy limit
            "hours_old": 72,  # Last 3 days
            "country_indeed": country,
            "verbose": 1  # Debug output
        }
        
        # Add seniority to search term if specified
        if seniority:
            seniority_keywords = {
                'intern': 'intern OR internship OR graduate',
                'junior': 'junior OR entry level',
                'analyst': 'analyst OR entry level', 
                'associate': 'associate OR mid level',
                'avp': 'senior OR AVP',
                'vp': 'vice president OR VP OR principal',
                'svp': 'senior vice president OR head of',
                'director': 'director',
                'md': 'managing director OR MD',
                'csuite': 'CEO OR CTO OR CFO OR chief'
            }
            if seniority in seniority_keywords:
                search_params["search_term"] = f"{title} {seniority_keywords[seniority]}"
                print(f"🎯 Enhanced search term: {search_params['search_term']}")
        
        print(f"🔍 Calling jobspy with params: {search_params}")
        
        # Call python-jobspy
        df = jobspy_scrape(**search_params)
        print(f"📊 jobspy returned DataFrame with shape: {df.shape if df is not None else 'None'}")
        
        if df is None or df.empty:
            print("❌ jobspy returned empty results")
            return [{
                "title": "No CareerJet Jobs Found",
                "company": "python-jobspy",
                "location": location,
                "link": "#",
                "description": f"No jobs found on CareerJet for '{title}' in '{location}'. Try different keywords or location.",
                "formatted_description": f"No jobs found on CareerJet for '{title}' in '{location}'. Try different keywords or location."
            }]
        
        # Convert DataFrame to your job format
        job_results = []
        for index, row in df.iterrows():
            if len(job_results) >= max_jobs:
                break
                
            # Extract data with fallbacks
            job_title = str(row.get('title', '[Not Found]')).strip()
            company = str(row.get('company', '[Not Found]')).strip()
            job_location = str(row.get('location', location)).strip()
            job_url = str(row.get('job_url', '#'))
            description = str(row.get('description', 'No description available')).strip()
            
            # Clean description
            if description and description != 'nan':
                # Remove HTML tags and clean up
                import re
                description = re.sub('<[^<]+?>', '', description)
                description = description.replace('\n', ' ').replace('\r', ' ')
                description = ' '.join(description.split())  # Remove extra whitespace
            else:
                description = 'No description available'
            
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
        
        print(f"🎯 FINAL RESULT: Successfully retrieved {len(job_results)} jobs using python-jobspy")
        return job_results
        
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        print("💡 Need to install: pip install python-jobspy")
        return [{
            "error_type": "import_error",
            "title": "python-jobspy Not Installed",
            "company": "Error",
            "location": location,
            "link": "#",
            "description": "python-jobspy library not installed. Run: pip install python-jobspy",
            "formatted_description": "python-jobspy library not installed. Run: pip install python-jobspy"
        }]
        
    except Exception as e:
        print(f"❌ PYTHON-JOBSPY ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        return [{
            "error_type": "jobspy_error",
            "title": "python-jobspy Error",
            "company": "Error",
            "location": location,
            "link": "#",
            "description": f"python-jobspy error: {str(e)}",
            "formatted_description": f"python-jobspy error: {str(e)}"
        }]

# Test function
if __name__ == "__main__":
    jobs = scrape_jobs("Risk Manager", "New York", 5)
    print(f"\n🎯 FINAL RESULT: Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job['title']} at {job['company']}")
