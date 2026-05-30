import re
import httpx
from urllib.parse import urlparse


class FacebookChecker:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    DIE_PATTERNS = [
        # Thông báo lỗi / không tồn tại / vô hiệu hóa
        "This content isn't available",
        "This page isn't available",
        "content not found",
        "Page Not Found",
        "Trang này không khả dụng",
        "Nội dung này không khả dụng",
        "Sorry, this page isn't available",
        "Bạn hiện không xem được nội dung này",
        "You can't view this content",
        "This account has been disabled",
        "Tài khoản này đã bị vô hiệu hóa",
        "content isn't available right now",
        "profile is not available",
        "this page isn't available"
        # Đã loại bỏ các từ khóa Login ra khỏi mảng này
    ]

    def extract_id(self, raw: str) -> str | None:
        raw = raw.strip().strip("/")
        if "facebook.com" in raw or "fb.com" in raw:
            parsed = urlparse(raw if raw.startswith("http") else "https://" + raw)
            path = parsed.path.strip("/")
            if "profile.php" in parsed.path:
                match = re.search(r"id=(\d+)", parsed.query)
                if match:
                    return match.group(1)
            # Hỗ trợ lấy Username (như Tandz.User)
            if path and "/" not in path:
                return path
            return None
        if re.match(r"^[\w.]+$", raw):
            return raw
        return None

    async def check(self, fb_id: str) -> tuple[str, str | None]:
        url = f"https://www.facebook.com/{fb_id}"
        
        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS, follow_redirects=True, timeout=15.0
            ) as client:
                response = await client.get(url)

            # 1. BẮT LỖI HTTP 404 (Chắc chắn 100% là Die)
            # VD: facebook.com/100012345678 sẽ trả về 404
            if response.status_code == 404:
                return "die", None

            body = response.text
            final_url = str(response.url).lower()

            # 2. KIỂM TRA TEXT TRONG HTML TÌM THÔNG BÁO LỖI
            for pattern in self.DIE_PATTERNS:
                if pattern.lower() in body.lower():
                    return "die", None

            # 3. BẮT CƠ CHẾ ĐĂNG NHẬP (LOGIN WALL)
            # Nếu Facebook đẩy về trang Đăng nhập hoặc Checkpoint, 
            # chứng tỏ URL có tồn tại (LIVE) nhưng FB không cho xem dạng ẩn danh.
            if "login" in final_url or "checkpoint" in final_url:
                return "live", None

            # 4. NẾU VƯỢT QUA TẤT CẢ -> TÀI KHOẢN ĐANG LIVE VÀ PUBLIC
            display_name = self._extract_title(body)
            return "live", display_name

        except httpx.TimeoutException:
            return "unknown", None
        except Exception:
            return "unknown", None

    async def get_avatar_url(self, fb_id: str) -> str | None:
        """Lấy URL ảnh avatar từ graph.facebook.com."""
        try:
            url = f"https://graph.facebook.com/{fb_id}/picture?type=large&redirect=false"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data", {}).get("url"):
                    return data["data"]["url"]
        except Exception:
            pass
        return f"https://graph.facebook.com/{fb_id}/picture?type=large"

    async def get_profile_info(self, fb_id: str) -> dict:
        status, name = await self.check(fb_id)
        avatar_url = await self.get_avatar_url(fb_id)
        return {
            "status": status,
            "name": name,
            "avatar_url": avatar_url,
            "profile_url": f"https://facebook.com/{fb_id}",
        }

    def _extract_title(self, html: str) -> str | None:
        match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            title = re.sub(r"\s*[|\-]\s*Facebook.*$", "", title, flags=re.IGNORECASE)
            if title and title.lower() not in ("facebook", ""):
                return title.strip()
        return None