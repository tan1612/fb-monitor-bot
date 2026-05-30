import re
import httpx
from urllib.parse import urlparse


class FacebookChecker:
    """
    Kiểm tra trạng thái public của Facebook profile/page
    bằng cách gọi URL public (không cần đăng nhập).
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # Dấu hiệu trang bị xóa / không tồn tại
    DIE_PATTERNS = [
        "This content isn't available",
        "This page isn't available",
        "content not found",
        "Page Not Found",
        "Trang này không khả dụng",
        "Nội dung này không khả dụng",
        "Sorry, this page isn't available",
    ]

    def extract_id(self, raw: str) -> str | None:
        """
        Trích xuất Facebook ID hoặc username từ URL hoặc chuỗi thô.
        Hỗ trợ:
          - 100012345678
          - zuck
          - https://facebook.com/zuck
          - https://www.facebook.com/profile.php?id=100012345678
          - fb.com/zuck
        """
        raw = raw.strip().strip("/")

        # Nếu là URL
        if "facebook.com" in raw or "fb.com" in raw:
            parsed = urlparse(raw if raw.startswith("http") else "https://" + raw)
            path = parsed.path.strip("/")

            # profile.php?id=XXXXXXX
            if "profile.php" in parsed.path:
                match = re.search(r"id=(\d+)", parsed.query)
                if match:
                    return match.group(1)

            # facebook.com/username
            if path and "/" not in path:
                return path

            return None

        # Thuần số hoặc username
        if re.match(r"^[\w.]+$", raw):
            return raw

        return None

    async def check(self, fb_id: str) -> tuple[str, str | None]:
        """
        Kiểm tra một Facebook ID.
        Trả về: ("live" | "die", display_name | None)
        """
        url = f"https://www.facebook.com/{fb_id}"

        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS,
                follow_redirects=True,
                timeout=15.0
            ) as client:
                response = await client.get(url)

            status_code = response.status_code
            body = response.text

            # 404 rõ ràng
            if status_code == 404:
                return "die", None

            # Check các pattern "không tồn tại" trong body
            for pattern in self.DIE_PATTERNS:
                if pattern.lower() in body.lower():
                    return "die", None

            # Trích tên hiển thị từ <title>
            display_name = self._extract_title(body)

            return "live", display_name

        except httpx.TimeoutException:
            return "unknown", None
        except Exception:
            return "unknown", None

    def _extract_title(self, html: str) -> str | None:
        """Trích tên từ thẻ <title>."""
        match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Bỏ phần "| Facebook" ở cuối
            title = re.sub(r"\s*[|\-]\s*Facebook.*$", "", title, flags=re.IGNORECASE)
            if title and title.lower() not in ("facebook", ""):
                return title.strip()
        return None
