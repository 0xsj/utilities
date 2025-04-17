import requests
from bs4 import BeautifulSoup
import urllib.parse
import argparse
import re

def discover_sitemap_url(base_url):
    """Try to discover the sitemap URL from robots.txt or common locations"""
    # Check robots.txt first
    try:
        robots_url = urllib.parse.urljoin(base_url, '/robots.txt')
        response = requests.get(robots_url, timeout=10)
        if response.status_code == 200:
            for line in response.text.splitlines():
                if line.lower().startswith('sitemap:'):
                    return line.split(':', 1)[1].strip()
    except requests.RequestException:
        pass
    
    # Try common sitemap locations
    common_paths = [
        '/sitemap.xml',
        '/sitemap_index.xml',
        '/sitemap.php',
        '/sitemap.txt',
    ]
    
    for path in common_paths:
        try:
            sitemap_url = urllib.parse.urljoin(base_url, path)
            response = requests.get(sitemap_url, timeout=10)
            if response.status_code == 200:
                return sitemap_url
        except requests.RequestException:
            continue
    
    return None

def parse_sitemap(sitemap_url, visited=None):
    """Parse a sitemap XML and return all URLs"""
    if visited is None:
        visited = set()
    
    if sitemap_url in visited:
        return []
    
    visited.add(sitemap_url)
    urls = []
    
    try:
        response = requests.get(sitemap_url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        
        # Handle sitemap index
        for sitemap in soup.find_all('sitemap'):
            loc = sitemap.find('loc')
            if loc:
                nested_urls = parse_sitemap(loc.text, visited)
                urls.extend(nested_urls)
        
        # Handle regular sitemap
        for url in soup.find_all('url'):
            loc = url.find('loc')
            if loc:
                urls.append(loc.text)
    except requests.RequestException as e:
        print(f"Error fetching sitemap: {e}")
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
    
    return urls

def extract_endpoints(urls, base_url):
    """Extract unique endpoints from URLs"""
    endpoints = set()
    base_parsed = urllib.parse.urlparse(base_url)
    
    for url in urls:
        parsed_url = urllib.parse.urlparse(url)
        
        # Skip URLs from different domains
        if parsed_url.netloc != base_parsed.netloc:
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

def crawl_site(url):
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
    sitemap_url = discover_sitemap_url(base_url)
    
    if not sitemap_url:
        print("Could not find sitemap, trying homepage...")
        try:
            response = requests.get(base_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for links in the HTML
            links = set()
            for a in soup.find_all('a', href=True):
                href = a['href']
                full_url = urllib.parse.urljoin(base_url, href)
                links.add(full_url)
            
            print(f"Found {len(links)} links in homepage")
            return extract_endpoints(links, base_url)
        except requests.RequestException as e:
            print(f"Error fetching homepage: {e}")
            return []
    
    print(f"Found sitemap: {sitemap_url}")
    urls = parse_sitemap(sitemap_url)
    print(f"Found {len(urls)} URLs in sitemap(s)")
    
    return extract_endpoints(urls, base_url)

def main():
    parser = argparse.ArgumentParser(description='Sitemap crawler to find all endpoints of a website.')
    parser.add_argument('url', help='The base URL of the website to crawl')
    parser.add_argument('-o', '--output', help='Output file for endpoints (default: print to console)')
    
    args = parser.parse_args()
    
    endpoints = crawl_site(args.url)
    
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