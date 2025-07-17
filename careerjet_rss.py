import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import html

def scrape_jobs_rss(title, location, max_jobs=10, seniority=None, region="US"):
    """Simple Indeed RSS implementation"""
    try:
        # Build search query
        search_query = title
        if seniority:
            search_query = f"{title} {seniority}"
        
        # Indeed RSS URL
        url = f"https://www.indeed.com/rss?q={quote(search_query)}&l={quote(location)}&limit={min(max_jobs, 25)}"
      
        
        # Get RSS feed
        print(f"🔍 Trying URL: {url}")
        response = requests.get(url, timeout=30)
        print(f"🔍 Response status: {response.status_code}")
        if response.status_code != 200:
            return [{"title": "RSS Error", "company": "Error", "location": location, "link": "#", "description": f"RSS returned status {response.status_code}"}]
        
        # Parse XML
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        
        # Convert to jobs
        jobs = []
        for item in items[:max_jobs]:
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            
            job_title = title_elem.text if title_elem is not None else 'No title'
            job_link = link_elem.text if link_elem is not None else '#'
            job_desc = desc_elem.text if desc_elem is not None else 'No description'
            
            if ' - ' in job_title:
                parts = job_title.split(' - ', 1)
                clean_title = parts[0].strip()
                company = parts[1].strip()
            else:
                clean_title = job_title
                company = 'Unknown'
            
            jobs.append({
                'title': clean_title,
                'company': company,
                'location': location,
                'link': job_link,
                'description': html.unescape(job_desc),
                'formatted_description': html.unescape(job_desc)
            })
        
        return jobs

    except Exception as e:
        print(f"❌ RSS Exception: {e}")
        import traceback
        traceback.print_exc()
        return [{"title": "Debug Error", "company": "Error", "location": location, "link": "#", "description": f"Full error: {str(e)}"}]
