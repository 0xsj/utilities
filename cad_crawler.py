import requests
import re
import json
import urllib.parse
import argparse
import time
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
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
            return response
        except requests.exceptions.RequestException as e:
            tries += 1
            if tries == max_tries:
                print(f"Failed to fetch {url}: {e}")
                return None
            print(f"Retry {tries}/{max_tries} for {url}: {e}")
            time.sleep(1)

def extract_endpoints_from_js(js_content):
    """Extract potential endpoints from JavaScript content"""
    endpoints = set()
    
    # Look for route patterns in Next.js
    patterns = [
        r'path:\s*[\'"]([^\'"]+)[\'"]',
        r'pathname:\s*[\'"]([^\'"]+)[\'"]',
        r'href:\s*[\'"]([^\'"]+)[\'"]',
        r'as:\s*[\'"]([^\'"]+)[\'"]',
        r'url:\s*[\'"]([^\'"]+)[\'"]',
        r'route:\s*[\'"]([^\'"]+)[\'"]',
        r'goto\([\'"]([^\'"]+)[\'"]',
        r'router\.push\([\'"]([^\'"]+)[\'"]',
        r'Link\s+href=[\'"]([^\'"]+)[\'"]',
        r'navigate\([\'"]([^\'"]+)[\'"]',
        r'fetch\([\'"]([^\'"\/]+)[\'"]',
        r'fetch\([\'"]\/([^\'"\?]+)[\'"]',
        r'api\/([a-zA-Z0-9_\-\/]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, js_content)
        for match in matches:
            if match and not match.startswith(('http', 'https', '#', 'javascript:', 'mailto:')):
                # Clean up the match
                clean_match = match.split('?')[0].split('#')[0]
                
                # Ensure it starts with a slash if it's a path
                if not clean_match.startswith('/') and not clean_match.startswith('api/'):
                    clean_match = '/' + clean_match
                elif clean_match.startswith('api/'):
                    clean_match = '/' + clean_match
                
                endpoints.add(clean_match)
    
    return endpoints

def extract_known_endpoints(response_text):
    """Extract endpoints from links and forms in the HTML"""
    soup = BeautifulSoup(response_text, 'html.parser')
    endpoints = set()
    
    # Extract from anchor tags
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Skip external links and javascript
        if href and not href.startswith(('http', 'https', '#', 'javascript:', 'mailto:')):
            endpoint = href.split('?')[0].split('#')[0]
            endpoints.add(endpoint)
    
    # Extract from forms
    for form in soup.find_all('form', action=True):
        action = form['action']
        if action and not action.startswith(('http', 'https', '#', 'javascript:')):
            endpoint = action.split('?')[0]
            endpoints.add(endpoint)
    
    # Extract potential endpoints from data attributes
    for tag in soup.find_all(attrs={"data-href": True}):
        href = tag['data-href']
        if href and not href.startswith(('http', 'https', '#', 'javascript:')):
            endpoint = href.split('?')[0].split('#')[0]
            endpoints.add(endpoint)
    
    for tag in soup.find_all(attrs={"data-url": True}):
        url = tag['data-url']
        if url and not url.startswith(('http', 'https', '#', 'javascript:')):
            endpoint = url.split('?')[0].split('#')[0]
            endpoints.add(endpoint)
    
    # Look for React Router patterns
    router_pattern = r'path:\s*[\'"]([^\'"]+)[\'"]'
    script_contents = [script.string for script in soup.find_all('script') if script.string]
    
    for script in script_contents:
        if script:
            matches = re.findall(router_pattern, script)
            for match in matches:
                if match and not match.startswith(('http', 'https', '#', 'javascript:')):
                    endpoints.add(match)
    
    return endpoints

def extract_endpoints_from_network(page_url, verify_ssl=False):
    """Use browser-like behavior to extract network requests"""
    endpoints = set()
    
    # Get the main page
    response = get_page(page_url, verify_ssl)
    if not response:
        return endpoints
    
    # Get all JavaScript files
    soup = BeautifulSoup(response.text, 'html.parser')
    js_files = []
    
    for script in soup.find_all('script', src=True):
        src = script['src']
        # Skip external scripts
        if not src.startswith(('http', 'https', '//')):
            full_url = urllib.parse.urljoin(page_url, src)
            js_files.append(full_url)
        elif src.startswith('//'):
            if page_url.startswith('https:'):
                full_url = 'https:' + src
            else:
                full_url = 'http:' + src
            if urllib.parse.urlparse(full_url).netloc == urllib.parse.urlparse(page_url).netloc:
                js_files.append(full_url)
        else:
            # Only include scripts from the same domain
            if urllib.parse.urlparse(src).netloc == urllib.parse.urlparse(page_url).netloc:
                js_files.append(src)
    
    print(f"Found {len(js_files)} JavaScript files")
    
    # Extract endpoints from JS files
    for js_url in js_files:
        print(f"Processing JavaScript file: {js_url}")
        js_response = get_page(js_url, verify_ssl)
        if js_response and js_response.status_code == 200:
            js_endpoints = extract_endpoints_from_js(js_response.text)
            endpoints.update(js_endpoints)
    
    return endpoints

def scan_endpoints(base_url, seed_endpoints, verify_ssl=False):
    """Scan a set of seed endpoints to discover more endpoints"""
    discovered = set(seed_endpoints)
    processed = set()
    
    while discovered - processed:
        endpoint = next(iter(discovered - processed))
        processed.add(endpoint)
        
        full_url = urllib.parse.urljoin(base_url, endpoint)
        print(f"Scanning endpoint: {endpoint}")
        
        response = get_page(full_url, verify_ssl)
        if not response:
            continue
        
        # Extract endpoints from HTML
        html_endpoints = extract_known_endpoints(response.text)
        
        # Extract endpoints from JavaScript
        js_endpoints = extract_endpoints_from_network(full_url, verify_ssl)
        
        # Combine all discovered endpoints
        new_endpoints = html_endpoints.union(js_endpoints)
        discovered.update(new_endpoints)
        
        # Don't overload the server
        time.sleep(0.5)
    
    return discovered

def main():
    parser = argparse.ArgumentParser(description='Next.js application endpoint crawler')
    parser.add_argument('url', help='Base URL of the Next.js application')
    parser.add_argument('-o', '--output', help='Output file for discovered endpoints')
    parser.add_argument('--no-verify', action='store_true', help='Disable SSL certificate verification')
    
    args = parser.parse_args()
    
    # Ensure URL has correct format
    base_url = args.url
    if not base_url.startswith(('http://', 'https://')):
        base_url = 'https://' + base_url
    
    verify_ssl = not args.no_verify
    
    # Start with known endpoints
    seed_endpoints = [
        '/',
        '/users',
        '/audit',  # Adding this known endpoint
        '/api',
        '/login',
        '/dashboard'
    ]
    
    # Add query parameter variations
    with_params = []
    for endpoint in seed_endpoints:
        with_params.append(endpoint)
        if endpoint == '/users':
            with_params.append('/users?sort=nameAlphabetical')
    
    print(f"Starting with {len(with_params)} seed endpoints")
    all_endpoints = scan_endpoints(base_url, with_params, verify_ssl)
    
    # Clean and sort the results
    clean_endpoints = []
    for endpoint in all_endpoints:
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        clean_endpoints.append(endpoint)
    
    clean_endpoints = sorted(set(clean_endpoints))
    
    if args.output:
        with open(args.output, 'w') as f:
            for endpoint in clean_endpoints:
                f.write(endpoint + '\n')
        print(f"Wrote {len(clean_endpoints)} endpoints to {args.output}")
    else:
        print("\nDiscovered endpoints:")
        for endpoint in clean_endpoints:
            print(endpoint)
        print(f"\nTotal: {len(clean_endpoints)} endpoints")

if __name__ == "__main__":
    main()