from bs4 import BeautifulSoup
from tldextract import extract
from urllib.parse import urlparse, urlunparse
from langdetect import detect
import re

import undetected_chromedriver as uc
#from selenium import webdriver
from tempfile import mkdtemp
import os, time

def get_size(start_path = '/tmp'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size

def clear_directory(directory):
    if os.path.exists(directory):
        # Recursively delete files and directories in the specified path
        for root, dirs, files in os.walk(directory, topdown=False):
            # Change the permissions and delete each file
            for name in files:
                filepath = os.path.join(root, name)
                try:
                    os.chmod(filepath, 0o777)  # Change the file permission
                    os.remove(filepath)        # Remove the file
                    # print(f"Removed file {filepath}")
                except Exception as e:
                    # print(f"Error removing file {filepath}: {e}")
                    pass

            # Change the permissions and delete each directory
            for name in dirs:
                dirpath = os.path.join(root, name)
                try:
                    os.chmod(dirpath, 0o777)  # Change the directory permission
                    os.rmdir(dirpath)         # Remove the directory
                    # print(f"Removed direct {dirpath}")
                except Exception as e:
                    # print(f"Error removing directory {dirpath}: {e}")
                    pass

        # Finally, remove the top directory
        try:
            os.rmdir(directory)
            # print(f"Removed direct {dirpath}")
        except Exception as e:
            # print(f"Error removing directory {directory}: {e}")
            pass

def is_valid_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|' # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|' # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)' # ...or ipv6
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, url) is not None

def get_domain_name(url):
    ext = extract(url)
    return ext.domain + '.' + ext.suffix if ext.domain else ''

def strip_subdomain(url):
    ext = extract(url)
    return url.replace(ext.subdomain+'.', '')

def remove_fragment(url):
    parsed_url = urlparse(url)
    # Reconstruct the URL without the fragment
    return urlunparse(parsed_url._replace(fragment=''))

def remove_query_parameters(url):
    parsed_url = urlparse(url)
    # Reconstruct the URL without query parameters
    return urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

def remove_http_and_www_from_url(url):
    parsed_url = urlparse(url)
    hostname = parsed_url.netloc
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return parsed_url._replace(netloc=hostname, scheme='').geturl().strip("/")

def clean_url(url):
    return remove_http_and_www_from_url(remove_fragment(remove_query_parameters(url)))


def find_unique_urls(driver, domain_name):
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    links = {}
    for link in soup.find_all('a'):
        url = link.get('href')
        label = link.get_text(strip=True)
        
        if url is None:
            continue

        if url.startswith('/'):
            url = 'https://' + domain_name + url

        if not url.startswith('http'):
            continue
    
        url = clean_url(url)
    
        if url in links:
            if label not in links[url]['label']:
                links[url]['label'] += ", " + label
        else:
            links[url] = {'url': url, 'label': label}

    return links

def extract_text(driver):
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    body = soup.find('body')
    if not body:
        return []
   
    text_elements = []
    for element in body.descendants:
        if element.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = element.get_text().strip()
            if text:
                text_elements.append(element.name + ": " + text)
                
    return text_elements

def handler(event=None, context=None):
    print(event)

    size = get_size()
    size_mb = size / (1024 * 1024)
    print(f"Size of /tmp: {size_mb} MB")

    urls = []
    if 'urls' in event:
        urls = event['urls']
    elif 'url' in event:
        urls = [event['url']]

    options = uc.ChromeOptions()
    #service = webdriver.ChromeService("/opt/chromedriver")

    user_data_dir = mkdtemp()
    data_path = mkdtemp()
    disk_cache_dir = mkdtemp()

    #options.binary_location = '/opt/chrome/chrome'
    options.headless=True
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(f"--data-path={data_path}")
    options.add_argument(f"--disk-cache-dir={disk_cache_dir}")    
    options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36")
    #driver = webdriver.Chrome(options=options, service=service)

    driver_executable_path = '/tmp/chromedriver'
    if not os.path.exists(driver_executable_path):
        os.system(f'cp /opt/chromedriver {driver_executable_path}')
        os.chmod(driver_executable_path, 0o777)

    driver = uc.Chrome(
        options=options,
        browser_executable_path='/opt/chrome/chrome',
        driver_executable_path=driver_executable_path,
        version_main=114)
    
    results = {}
    for url in urls:
        if not is_valid_url(url):
            continue 

        driver.get(url)
        time.sleep(3)
        domain_name = get_domain_name(url)
        links = find_unique_urls(driver, domain_name)
        #print(links)
        texts = extract_text(driver)
        #print(texts)
        results[url] = {
            "links": links,
            "texts": texts
        }

    driver.quit()

    clear_directory(user_data_dir)
    clear_directory(data_path)
    clear_directory(disk_cache_dir)

    return {
        "statusCode": 200,
        "body": results
    }
