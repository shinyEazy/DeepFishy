import requests
import time
import os
import zipfile
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

MINERU_API_KEY = os.getenv("MINERU_API_KEY")
BASE_URL = "https://mineru.net/api/v4/extract/task"
POLL_INTERVAL = 5
OUTPUT_DIR = "mineru_results"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {MINERU_API_KEY}",
}

payload = {
    "url": "https://cafef1.mediacdn.vn/Images/Uploaded/DuLieuDownload/PhanTichBaoCao/MBB_2025_12_04_SSIResearch08122025094945.pdf",
    # "enable_formula": True,
    # "enable_table": True,
    "language": "vi",
}


def create_task():
    res = requests.post(BASE_URL, headers=headers, json=payload)
    res.raise_for_status()
    data = res.json()["data"]
    task_id = data["task_id"]
    print(f"✅ Task created: {task_id}")
    return task_id


def poll_task(task_id):
    url = f"{BASE_URL}/{task_id}"

    while True:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()["data"]

        state = data.get("state")
        print(f"⏳ State: {state}")

        if state == "done":
            return data
        elif state == "failed":
            raise RuntimeError(f"❌ Task failed: {data.get('err_msg')}")
        else:
            time.sleep(POLL_INTERVAL)


def download_and_extract(zip_url):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = os.path.basename(urlparse(zip_url).path)
    zip_path = os.path.join(OUTPUT_DIR, filename)

    print(f"⬇️ Downloading {filename}")
    r = requests.get(zip_url)
    r.raise_for_status()

    with open(zip_path, "wb") as f:
        f.write(r.content)

    print("📦 Extracting files...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(OUTPUT_DIR)

    print(f"✅ Results ready in ./{OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        task_id = create_task()
        result = poll_task(task_id)
        download_and_extract(result["full_zip_url"])
    except Exception as e:
        print("❌ Error:", e)
