import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


def crawl_article_urls(html_content, base_url="https://vneconomy.vn"):
    """
    Extract all article URLs from the HTML content within the main-page section

    Args:
        html_content: HTML content as string
        base_url: Base URL for constructing absolute URLs

    Returns:
        list: List of article URLs
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Find the main-page section
    main_page = soup.find("main", class_="main-page")

    if not main_page:
        print("Warning: main-page section not found")
        return []

    # Find all article items
    article_items = main_page.find_all(
        "div", class_="featured-row_item featured-column_item"
    )

    urls = []
    for item in article_items:
        # Find the href in the link-layer-imt anchor tag
        link = item.find("a", class_="link-layer-imt")
        if link and link.get("href"):
            href = link.get("href")
            # Construct absolute URL
            absolute_url = urljoin(base_url, href)
            urls.append(absolute_url)

    return urls


def fetch_and_crawl_urls(task_info, max_retries=5):
    """
    Fetch HTML content from URL and extract article URLs with retry logic

    Args:
        task_info: Tuple of (path, page, url)
        max_retries: Maximum number of retry attempts (default: 5)

    Returns:
        tuple: (path, page, list of article URLs)
    """
    path, page, url = task_info

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            urls = crawl_article_urls(response.text)
            print(f"✓ Path: {path}, Page {page}: Found {len(urls)} articles")
            return (path, page, urls)
        except Exception as e:
            if attempt < max_retries:
                print(f"⚠ Attempt {attempt}/{max_retries} failed for {url}: {e}")
                time.sleep(2)  # Wait before retrying
            else:
                print(f"✗ Failed after {max_retries} attempts - {url}: {e}")
                return (path, page, [])


# Read paths from path.txt
with open("paths.txt", "r") as f:
    paths = [line.strip() for line in f if line.strip()]

URL_TEMPLATE = "https://vneconomy.vn/{path}.htm?page={page}"

print(f"Starting crawl with max 5 workers\n")

all_urls = []
unique_urls = []  # Track unique URLs as we go

# Process each path sequentially, but pages concurrently
for path in paths:
    print(f"\n{'='*60}")
    print(f"Processing path: {path}")
    print(f"{'='*60}")

    page = 1
    while page < 2000:
        # Create batch of tasks (process 10 pages at a time concurrently)
        batch_tasks = []
        for p in range(page, min(page + 10, 2000)):
            url = URL_TEMPLATE.format(path=path, page=p)
            batch_tasks.append((path, p, url))

        # Process batch concurrently
        batch_results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {
                executor.submit(fetch_and_crawl_urls, task): task
                for task in batch_tasks
            }

            for future in as_completed(future_to_task):
                path_result, page_result, urls = future.result()
                batch_results.append((page_result, urls))
                all_urls.extend(urls)

        # Sort batch results by page number for sequential checking
        batch_results.sort(key=lambda x: x[0])

        should_skip = False
        for page_num, urls in batch_results:
            if len(urls) == 0:
                print(f"⏭ Page {page_num} returned 0 articles. Moving to next path.")
                should_skip = True
                break

            # Track unique URL count before adding this page's URLs
            unique_count_before = len(unique_urls)

            # Add only new unique URLs
            for url in urls:
                if url not in unique_urls:
                    unique_urls.append(url)

            # Check if any new URLs were added
            unique_count_after = len(unique_urls)

            if unique_count_after == unique_count_before:
                print(
                    f"⏭ Page {page_num} contains only duplicate URLs. Skipping category from here."
                )
                should_skip = True
                break

        if should_skip:
            break

        # Move to next batch
        page += 10

# Write to urls.txt
with open("urls.txt", "a", encoding="utf-8") as f:
    for url in unique_urls:
        f.write(url + "\n")

print(f"\n--- Crawl Complete ---")
print(f"Total URLs collected: {len(all_urls)}")
print(f"Unique URLs: {len(unique_urls)}")
print(f"URLs appended to urls.txt")
