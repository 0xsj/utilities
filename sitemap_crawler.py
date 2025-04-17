import requests
from bs4 import BeautifulSoup
import urllib.parse
import argparse
import re
import time
from urllib3.exceptions import InsecureRequestWarning

# Suppress only the single warning from urllib3 needed.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

def get_page(url, verify_ssl=False):
    """Get a web page with error handling and retries"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    tries = 0
    max_tries = 3
    
    while tries < max_tries:
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=verify_ssl)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            return response
        except requests.exceptions.RequestException as e:
            tries += 1
            if tries == max_tries:
                print(f"Failed to fetch {url}: {e}")
                return None
            print(f"Retry {tries}/{max_tries} for {url}: {e}")
            time.sleep(1)

def discover_sitemap_url(base_url, verify_ssl=False):
    """Try to discover the sitemap URL from robots.txt or common locations"""
    print(f"Looking for sitemap at {base_url}...")
    
    # Check robots.txt first
    robots_url = urllib.parse.urljoin(base_url, '/robots.txt')
    print(f"Checking robots.txt at {robots_url}")
    
    response = get_page(robots_url, verify_ssl)
    if response and response.status_code == 200:
        print("Found robots.txt, checking for sitemap...")
        for line in response.text.splitlines():
            if line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                print(f"Found sitemap in robots.txt: {sitemap_url}")
                return sitemap_url
    else:
        print("No robots.txt found or unable to access it")
    
    # Try common sitemap locations
    common_paths = [
        '/sitemap.xml',
        '/sitemap_index.xml',
        '/sitemap.php',
        '/sitemap.txt',
        '/sitemap-index.xml',
        '/wp-sitemap.xml',  # WordPress
        '/sitemapindex.xml',
    ]
    
    for path in common_paths:
        sitemap_url = urllib.parse.urljoin(base_url, path)
        print(f"Trying {sitemap_url}")
        
        response = get_page(sitemap_url, verify_ssl)
        if response and response.status_code == 200 and ('xml' in response.headers.get('Content-Type', '') or response.text.strip().startswith('<?xml')):
            print(f"Found sitemap at {sitemap_url}")
            return sitemap_url
    
    print("No sitemap found in common locations")
    return None

def parse_sitemap(sitemap_url, visited=None, verify_ssl=False):
    """Parse a sitemap XML and return all URLs"""
    if visited is None:
        visited = set()
    
    if sitemap_url in visited:
        return []
    
    visited.add(sitemap_url)
    urls = []
    
    print(f"Parsing sitemap: {sitemap_url}")
    response = get_page(sitemap_url, verify_ssl)
    
    if not response:
        print(f"Failed to fetch sitemap: {sitemap_url}")
        return urls
    
    try:
        soup = BeautifulSoup(response.content, 'xml')
        
        # Handle sitemap index
        for sitemap in soup.find_all('sitemap'):
            loc = sitemap.find('loc')
            if loc:
                nested_url = loc.text
                print(f"Found nested sitemap: {nested_url}")
                nested_urls = parse_sitemap(nested_url, visited, verify_ssl)
                urls.extend(nested_urls)
        
        # Handle regular sitemap
        for url in soup.find_all('url'):
            loc = url.find('loc')
            if loc:
                urls.append(loc.text)
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
        
        # Try to extract URLs directly if XML parsing fails
        pattern = r'<loc>(.*?)</loc>'
        found_urls = re.findall(pattern, response.text)
        if found_urls:
            print(f"Found {len(found_urls)} URLs using regex")
            urls.extend(found_urls)
    
    print(f"Found {len(urls)} URLs in this sitemap")
    return urls

def extract_endpoints(urls, base_url):
    """Extract unique endpoints from URLs"""
    endpoints = set()
    base_parsed = urllib.parse.urlparse(base_url)
    
    print(f"Extracting endpoints from {len(urls)} URLs")
    
    for url in urls:
        parsed_url = urllib.parse.urlparse(url)
        
        # Skip URLs from different domains
        if parsed_url.netloc and parsed_url.netloc != base_parsed.netloc:
            continue
        
        # Extract the path
        path = parsed_url.path
        
        # Clean up the path
        if not path:
            path = '/'
        
        endpoints.add(path)
        
        # Add path parts as potential endpoints
        parts = path.split('/')
        current = ''
        for part in parts:
            if part:
                current += f'/{part}'
                endpoints.add(current)
    
    return sorted(endpoints)

def crawl_links(url, max_depth=1, visited=None, current_depth=0, base_url=None, verify_ssl=False):
    """Crawl links from a page recursively up to max_depth"""
    if visited is None:
        visited = set()
    
    if base_url is None:
        base_url = url
    
    if url in visited or current_depth > max_depth:
        return []
    
    print(f"Crawling page: {url} (depth {current_depth}/{max_depth})")
    visited.add(url)
    
    response = get_page(url, verify_ssl)
    if not response:
        return []
    
    urls = []
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        base_parsed = urllib.parse.urlparse(base_url)
        
        # Extract links
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urllib.parse.urljoin(url, href)
            parsed_url = urllib.parse.urlparse(full_url)
            
            # Only include URLs from the same domain
            if parsed_url.netloc == base_parsed.netloc or not parsed_url.netloc:
                urls.append(full_url)
                
                # Recursive crawl if not at max depth
                if current_depth < max_depth:
                    child_urls = crawl_links(full_url, max_depth, visited, current_depth + 1, base_url, verify_ssl)
                    urls.extend(child_urls)
    except Exception as e:
        print(f"Error parsing page {url}: {e}")
    
    return urls

def crawl_site(url, crawl_depth=1, verify_ssl=False):
    """Main crawler function that discovers and processes sitemaps"""
    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Normalize URL to include trailing slash for base URL
    base_url = url
    if not base_url.endswith('/'):
        base_url += '/'
    
    print(f"Crawling: {base_url}")
    
    # Try to discover sitemap
    sitemap_url = discover_sitemap_url(base_url, verify_ssl)
    
    if sitemap_url:
        print(f"Processing sitemap: {sitemap_url}")
        urls = parse_sitemap(sitemap_url, verify_ssl=verify_ssl)
        if urls:
            return extract_endpoints(urls, base_url)
    
    # Fall back to crawling
    print("No sitemap found or sitemap empty, falling back to crawling...")
    urls = crawl_links(base_url, max_depth=crawl_depth, verify_ssl=verify_ssl)
    
    if not urls:
        print("No URLs found by crawling")
        return []
    
    print(f"Found {len(urls)} URLs by crawling")
    return extract_endpoints(urls, base_url)

def main():
    parser = argparse.ArgumentParser(description='Sitemap crawler to find all endpoints of a website.')
    parser.add_argument('url', help='The base URL of the website to crawl')
    parser.add_argument('-o', '--output', help='Output file for endpoints (default: print to console)')
    parser.add_argument('-d', '--depth', type=int, default=2, help='Maximum crawl depth when no sitemap is found (default: 2)')
    parser.add_argument('--no-verify', action='store_true', help='Disable SSL certificate verification')
    
    args = parser.parse_args()
    
    verify_ssl = not args.no_verify
    if not verify_ssl:
        print("WARNING: SSL certificate verification disabled")
    
    endpoints = crawl_site(args.url, args.depth, verify_ssl)
    
    if args.output:
        with open(args.output, 'w') as f:
            for endpoint in endpoints:
                f.write(f"{endpoint}\n")
        print(f"Wrote {len(endpoints)} endpoints to {args.output}")
    else:
        print("\nDiscovered Endpoints:")
        for endpoint in endpoints:
            print(endpoint)
        print(f"\nTotal: {len(endpoints)} endpoints")

if __name__ == "__main__":
    main()