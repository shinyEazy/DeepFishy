import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def extract_article_data(html_content, url):
    """Extract article data from HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract title from meta og:title or first h1/h2
    title = None
    title_meta = soup.find("meta", property="og:title")
    if title_meta:
        title = title_meta.get("content")
    if not title:
        title_element = soup.find(["h1", "h2", "h3"])
        if title_element:
            title = title_element.get_text(strip=True)

    # Extract category - look for breadcrumb next to "Trang chủ"
    category = None
    breadcrumb = soup.find("div", class_=re.compile("breadcrumb", re.I))
    if breadcrumb:
        # Find all links in breadcrumb
        links = breadcrumb.find_all("a", class_="text-breadcrumb")
        # Get the second link (after "Trang chủ")
        if len(links) > 1:
            category = links[1].get_text(strip=True)

    # Extract date from data-field="distributionDate"
    date = None
    date_element = soup.find(class_="date", attrs={"data-field": "distributionDate"})
    if date_element:
        date = date_element.get_text(strip=True)

    # Extract content from data-field="body"
    content = ""
    body_element = soup.find(attrs={"data-field": "body"})
    if body_element:
        # Extract all paragraph text
        paragraphs = body_element.find_all("p", class_="text-justify")
        content = "\n\n".join([p.get_text(strip=True) for p in paragraphs])

    # Extract sapo (lead paragraph)
    sapo = ""
    sapo_element = soup.find(attrs={"data-field": "sapo"})
    if sapo_element:
        sapo = sapo_element.get_text(strip=True)

    # Extract tags
    tags = []
    tag_container = soup.find("div", class_="box-keyword")
    if tag_container:
        tag_elements = tag_container.find_all("a", class_="tag")
        tags = [tag.get_text(strip=True) for tag in tag_elements]

    return {
        "url": url,
        "title": title,
        "category": category,
        "date": date,
        "sapo": sapo,
        "content": content,
        "tags": tags,
    }


def sanitize_filename(title):
    """Create a safe filename from title."""
    if not title:
        return "untitled"
    # Remove invalid filename characters
    safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
    # Limit length
    safe_title = safe_title[:100]
    return safe_title.strip()


def get_session_with_retry():
    """Create a requests session with retry strategy."""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_html(url, session=None):
    """Fetch HTML content from URL with retry."""
    if session is None:
        session = get_session_with_retry()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def process_url(url, data_dir, idx, total):
    """Process a single URL - fetch, extract, and save data."""
    print(f"\n[{idx}/{total}] Processing: {url}")

    session = get_session_with_retry()

    try:
        # Fetch HTML from URL
        html_content = fetch_html(url, session)
        if not html_content:
            return None

        # Extract data
        article_data = extract_article_data(html_content, url)

        # Create filename from URL path
        url_path = url.rstrip("/").split("/")[-1]
        # Remove .htm or .html extension if present
        url_path = re.sub(r"\.(htm|html)$", "", url_path)
        filename = url_path + ".json"
        output_path = data_dir / filename

        # Save to JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(article_data, f, ensure_ascii=False, indent=2)

        print(f"✓ Saved: {output_path.name}")
        print(f"  Title: {article_data['title']}")
        print(f"  Date: {article_data['date']}")

        return output_path.name

    except Exception as e:
        print(f"✗ Error processing {url}: {e}")
        return None


def main():
    # Load URLs from urls.txt
    urls = []
    try:
        with open("urls.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: urls.txt not found")
        return

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    print(f"Loaded {len(urls)} URLs from urls.txt")
    print(f"Starting crawl with multiple workers...\n")

    # Use ThreadPoolExecutor for concurrent processing
    max_workers = 5
    successful = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_url = {
            executor.submit(process_url, url, data_dir, idx, len(urls)): url
            for idx, url in enumerate(urls, 1)
        }

        # Process completed tasks
        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                successful += 1
            else:
                failed += 1

    print(f"\n{'='*60}")
    print(f"Crawl completed!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(urls)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
