import requests
from bs4 import BeautifulSoup
import os
import argparse
import time

SAVE_DIR = 'phpbb_archives'

PROXIES = {
    'http': 'socks5h://127.0.0.1:9150',
    'https': 'socks5h://127.0.0.1:9150'
}

def extract_pass(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    info_tags = soup.find_all('td', {'class': 'info'})
    
    extracted_texts = []
    for tag in info_tags:
        div_tag = tag.find('div')
        if div_tag:
            extracted_texts.append(div_tag.text)
    return extracted_texts

def get_total_pages(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    pagination_div = soup.find('div', {'class': 'pagination'})
    
    if pagination_div:
        pagination_tag = pagination_div.find('span', {'class': 'sr-only'})
        
        if pagination_tag:
            total_pages = int(pagination_tag.text.split('of')[-1].strip())
            return total_pages
    
    return None

def fetch_url(url):
    while True:
        try:
            response = requests.get(url, headers=HEADERS, proxies=PROXIES)
            if response.status_code == 200:
                return response.text
            else:
                print(f"[WARNING] Received status code {response.status_code} for URL: {url}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] An error occurred while fetching {url}. Error: {e}")
            print("[INFO] Waiting for 30 seconds before retrying...")
            time.sleep(30)

def save_page(filename, content):
    dir_name = os.path.dirname(filename)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

def sanitize_filename(filename):
    return "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (' ', '.', '_', '-')]).rstrip()

scraped_forums = set()
scraped_subforums = set()
scraped_topics = set()
def scrape_subforum(absolute_link, forum_dir):
    subforum_id = int(absolute_link.split('f=')[-1].split('&')[0])
    
    if subforum_id in scraped_subforums:
        print(f"[DEBUG] Skipping subforum ID {subforum_id} because it's already been scraped!")
        return
    
    scraped_subforums.add(subforum_id)
    
    print(f"[INFO] Processing subforum: {absolute_link}")
    subforum_page = fetch_url(absolute_link)
    base_domain = absolute_link.split('?')[0].rsplit('/', 1)[0]
    
    while subforum_page:
        subforum_soup = BeautifulSoup(subforum_page, 'html.parser')
        
        post_number = 1
        for post_link in subforum_soup.find_all('a', class_='topictitle'):
            post_relative_link = post_link.get('href')
            post_title = sanitize_filename(post_link.text.strip())
            topic_id = int(post_relative_link.split('t=')[-1].split('&')[0])
            
            if topic_id in scraped_topics:
                print(f"[DEBUG] Skipping topic ID {topic_id} because it's already been scraped!")
                continue
            scraped_topics.add(topic_id)
            if not post_title:
                post_title = str(post_number)
                post_number += 1
            post_filename = post_title + '.html'
            
            if post_relative_link:
                post_absolute_link = base_domain + '/' + post_relative_link
                print(f"[INFO] Fetching post page: {post_absolute_link}")
                post_page = fetch_url(post_absolute_link)
                
                if post_page:
                    print(f"[INFO] Saving post page: {forum_dir}/{post_filename}")
                    save_page(os.path.join(forum_dir, post_filename), post_page)
        
        if not args.only:
            for nested_forum_link in subforum_soup.find_all('a', class_='forumtitle'):
                nested_relative_link = nested_forum_link.get('href')
                nested_forum_name = sanitize_filename(nested_forum_link.text.strip())
                nested_forum_dir = os.path.join(forum_dir, nested_forum_name)
                
                if nested_relative_link:
                    nested_absolute_link = base_domain + '/' + nested_relative_link
                    scrape_subforum(nested_absolute_link, nested_forum_dir)
        
        next_page_link = subforum_soup.find('a', rel='next')
        if next_page_link:
            subforum_page = fetch_url(base_domain + '/' + next_page_link['href'])
        else:
            subforum_page = None


def scrape_forum(base_url):
    print("[INFO] Fetching the main forum page...")
    main_page = fetch_url(base_url)
    if not main_page:
        print("[ERROR] Failed to fetch the main page.")
        return
    
    soup = BeautifulSoup(main_page, 'html.parser')
    
    if not os.path.exists(SAVE_DIR):
        print(f"[INFO] Creating directory: {SAVE_DIR}")
        os.makedirs(SAVE_DIR)

    print("[INFO] Saving the main forum page...")
    save_page(os.path.join(SAVE_DIR, 'index.html'), main_page)

    base_domain = base_url.split('?')[0].rsplit('/', 1)[0]

    for forum_link in soup.find_all('a', class_='forumtitle'):
        relative_link = forum_link.get('href')
        
        forum_id = int(relative_link.split('f=')[-1].split('&')[0])
        
        if forum_id in scraped_forums:
            print(f"[DEBUG] Skipping forum ID {forum_id} because it's already been scraped!")
            continue
            
        scraped_forums.add(forum_id)
        if forum_id in default_ignores:
            print(f"[DEBUG] Skipping forum ID {forum_id} because in default ignore list!")
            continue
        if args.only and forum_id != args.only:
            print(f"[DEBUG] Skipping forum ID {forum_id} because it's not {args.only}")
            continue 
        if not args.only and forum_id in args.ignore:
            print(f"[INFO] Ignoring forum with ID: {forum_id}")
            continue

        forum_name = sanitize_filename(forum_link.text.strip())
        forum_dir = os.path.join(SAVE_DIR, forum_name)

        if relative_link:
            absolute_link = base_domain + '/' + relative_link
            scrape_subforum(absolute_link, forum_dir)

if __name__ == "__main__":
    print('''
        Username: (REDACTED)
        Password: (REDACTED)
''')
    parser = argparse.ArgumentParser(description='Scrape a phpBB forum.')
    parser.add_argument('--ignore', metavar='N', type=int, nargs='+', help='IDs of the forums to ignore', default=[])
    parser.add_argument('--only', metavar='N', type=int, help='ID of the forum to scrape exclusively')
    parser.add_argument('--forum', type=str, choices=['forum_1', 'forum_2', 'forum_3'], help='Forum selection.')
    parser.add_argument('--session_id', metavar='SESSION_ID', type=str, help='Session ID.')
    parser.add_argument('--user_id', metavar='UID', type=str, help='User ID.')
    parser.add_argument('--b_id', metavar='BID', type=str, help='\"b\" ID.')
    parser.add_argument('--k_id', metavar='KID', type=str, default='', help='\"k\" ID.')
    parser.add_argument('--extract_pass', action='store_true', help='Extract passwords.')
    parser.add_argument('--store_extracted_text', action='store_true', help="Store extracted text in a file")
    parser.add_argument('--start_page', type=int, default=1, help="Page number to start from")

    args = parser.parse_args()
    if args.forum == 'forum_1':
        default_ignores = [7, 9, 11, 12, 139, 144, 111, 112, 150, 14, 19, 20, 21, 22, 23, 24, 25, 26 ,27 ,28 ,29 ,30, 31, 32, 33, 34, 35, 36, 37, 102, 15, 16, 17, 18, 108, 136]
        BASE_URL = f'http://forum_1.onion/'
        
        
        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': f'{BASE_URL}',
            'Connection': 'keep-alive',
            'Cookie': f'_u={args.user_id}; _k={args.k_id}; _sid={args.session_id}',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }
    elif args.forum == 'forum_2':
        default_ignores = [104, 106, 2, 193, 35, 54, 29, 66, 80, 68, 79, 67, 74, 69, 72, 77, 73, 78, 83, 70, 75, 179, 82, 184, 71, 172, 211, 81, 185, 203, 215, 76, 204, 210, 214, 218, 63, 219, 60, 61, 103, 59, 186, 38, 118, 116, 120, 115, 117, 114, 119, 62, 65, 94, 58]
        BASE_URL = f'http://forum_2.onion/forum/'
        
        
        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': f'{BASE_URL}',
            'Connection': 'keep-alive',
            'Cookie': f'_u={args.user_id}; _k={args.k_id}; _sid={args.session_id}',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }
    elif args.forum == 'forum_3':
        default_ignores = [2, 116, 5, 569, 354, 7, 557, 8, 9, 12, 10, 62, 146, 11, 375, 576, 586, 148, 556, 149, 150, 588, 579, 555, 194, 118, 238, 195, 196, 199, 440, 453, 454, 550, 502]
        BASE_URL = f'http://forum_3.onion/'
        
        
        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': f'{BASE_URL}',
            'Connection': 'keep-alive',
            'Cookie': f'_u={args.user_id}; _k={args.k_id}; _sid={args.session_id}',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }

    if args.only:
        subforum_link = f"{BASE_URL}/viewforum.php?f={args.only}&sid={args.session_id}"
        forum_name = f"Forum_{args.only}"
        scrape_subforum(subforum_link, os.path.join(SAVE_DIR, forum_name))
    elif args.extract_pass:
        initial_data = requests.get(f"{BASE_URL}memberlist.php?start=0", proxies=PROXIES, headers=HEADERS)
        total_pages = get_total_pages(initial_data.text)
        print(total_pages)
        for page in range(args.start_page, total_pages + 1):
            start = (page - 1) * 25
            page_url = f'{BASE_URL}memberlist.php?start={start}'
            response = requests.get(page_url, proxies=PROXIES, headers=HEADERS)
            if response.status_code == 200:
                extracted_texts = extract_pass(response.text)
                print(f"Page {page} Extracted Texts: {extracted_texts}")
                if args.store_extracted_text:
                    with open('extracted_text.txt', 'a') as f:
                        for item in extracted_texts:
                            f.write(f"{item}\n")
            else:
                print(f"Failed to fetch page {page} URL: {response.status_code}")
    else:
        scrape_forum(BASE_URL)
