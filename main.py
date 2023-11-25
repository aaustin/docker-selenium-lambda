from bs4 import BeautifulSoup
from tldextract import extract
from urllib.parse import urlparse, urlunparse
from langdetect import detect


import undetected_chromedriver as uc
#from selenium import webdriver
from tempfile import mkdtemp
import os, time

def strip_subdomain(url):
    tsd, td, tsu = extract(url)
    return url.replace(tsd+'.', '')

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


def find_unique_urls(driver):
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    links = {}
    for link in soup.find_all('a'):
        url = link.get('href')
        label = link.get_text(strip=True)
        
        if url is None:
            continue
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

    urls = []
    if 'urls' in event:
        urls = event['urls']
    elif 'url' in event:
        urls = [event['url']]

    options = uc.ChromeOptions()
    #service = webdriver.ChromeService("/opt/chromedriver")

    #options.binary_location = '/opt/chrome/chrome'
    options.headless=True
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f"--user-data-dir={mkdtemp()}")
    options.add_argument(f"--data-path={mkdtemp()}")
    options.add_argument(f"--disk-cache-dir={mkdtemp()}")    
    options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36")
    #driver = webdriver.Chrome(options=options, service=service)

    driver_executable_path = '/tmp/chromedriver'
    os.system(f'cp /opt/chromedriver {driver_executable_path}')
    os.chmod(driver_executable_path, 0o777)

    driver = uc.Chrome(
        options=options,
        browser_executable_path='/opt/chrome/chrome',
        driver_executable_path=driver_executable_path,
        version_main=114)
    
    results = {}
    for url in urls:
        driver.get(url)
        time.sleep(3)
        links = find_unique_urls(driver)
        print(links)
        texts = extract_text(driver)
        print(texts)
        results[url] = {
            "links": links,
            "texts": texts
        }

    driver.quit()

    return {
        "statusCode": 200,
        "body": results
    }
