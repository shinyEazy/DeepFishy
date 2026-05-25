"""Shared constants used across DeepFishy."""

CRAWLER_BASE_URL = "https://vneconomy.vn/"
CRAWLER_PATHS = [
    "tieu-diem",
    "kinh-te-the-gioi",
    "tai-chinh",
    "chung-khoan",
    "dau-tu",
    "cong-ty-doanh-nghiep",
    "kinh-te-so",
    "kinh-te-xanh",
    "dia-oc",
    "ha-tang-dau-tu",
    "tieu-dung",
    "thi-truong",
    "dan-sinh",
    "nhip-cau-doanh-nghiep",
]
CRAWLER_MAX_PAGES = 50
CRAWLER_MAX_WORKERS = 4

__all__ = [
    "CRAWLER_BASE_URL",
    "CRAWLER_MAX_PAGES",
    "CRAWLER_MAX_WORKERS",
    "CRAWLER_PATHS",
]
