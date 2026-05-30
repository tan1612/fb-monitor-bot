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
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    def extract_id(self, raw: str) -> str | None:
        """
        Hàm này giờ chỉ đóng vai trò lọc sơ bộ. 
        Việc tìm UID thật sẽ do hàm _convert_to_uid đảm nhiệm.
        """
        raw = raw.strip().strip("/")
        if re.match(r"^\d+$", raw):
            return raw  # Nếu đã là số sẵn thì trả về luôn
        
        # Nếu là link, thêm https:// để chuẩn hóa
        if "facebook.com" in raw or "fb.com" in raw:
            return raw if raw.startswith("http") else f"https://{raw}"
        
        # Nếu chỉ nhập username (vd: Tandz.User), ghép thành link
        return f"https://www.facebook.com/{raw}"

    async def _convert_to_uid(self, link: str) -> str | None:
        """Sử dụng id.traodoisub.com để lấy UID từ link/username"""
        if link.isdigit():
            return link
            
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Gửi request lên API của traodoisub
                payload = {"link": link}
                headers = {**self.HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
                
                # Lưu ý: Endpoint api.php là chuẩn chung của các site dạng này
                resp = await client.post("https://id.traodoisub.com/api.php", data=payload, headers=headers)
                
                # Dùng Regex để vét cạn ID số (Thường là 1 chuỗi 15-16 số hoặc bắt đầu bằng 1000)
                match = re.search(r'"id"\s*:\s*"(\d+)"', resp.text) or re.search(r'\b(1000\d{11}|\d{15,16})\b', resp.text)
                if match:
                    # Trả về chuỗi số UID
                    return match.group(1) if '"id"' in resp.text else match.group(0)
        except Exception:
            pass
            
        return None

    async def check(self, raw_id: str) -> tuple[str, str | None]:
        # BƯỚC 1: Dùng Traodoisub để chuyển mọi thứ về UID SỐ
        fb_uid = await self._convert_to_uid(raw_id)
        
        # Nếu web thứ 3 không tìm được UID -> Báo unknown để thử lại sau
        if not fb_uid:
            return "unknown", None

        # BƯỚC 2: Check Live/Die bằng UID SỐ
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 1. THỬ DÙNG GRAPH API CỦA FACEBOOK TRƯỚC (Nhanh và chính xác nhất cho UID số)
                # Graph API check bằng hình ảnh rất khó bị block nếu ta truyền vào UID số chuẩn.
                api_url = f"https://graph.facebook.com/{fb_uid}/picture?type=large&redirect=false"
                fb_resp = await client.get(api_url)
                
                if fb_resp.status_code == 200:
                    return "live", fb_uid  # Trả về luôn fb_uid làm tên tạm thời
                elif fb_resp.status_code in [400, 404]:
                    return "die", None

                # 2. NẾU GRAPH API LỖI (Fallback) -> CHUYỂN SANG DÙNG CHECKUID.LIVE
                # Cào data từ Checkuid.live
                check_url = f"https://checkuid.live/api/check?uid={fb_uid}"
                cu_resp = await client.get(check_url, headers=self.HEADERS)
                
                # Đọc kết quả từ web checkuid.live (giả định họ trả về JSON hoặc HTML chứa keyword)
                cu_text = cu_resp.text.lower()
                if "live" in cu_text or '"status": "live"' in cu_text:
                    return "live", fb_uid
                if "die" in cu_text or '"status": "die"' in cu_text or "not found" in cu_text:
                    return "die", None
                    
        except Exception:
            pass
            
        return "unknown", None

    async def get_avatar_url(self, fb_id: str) -> str | None:
        """Lấy URL ảnh avatar từ graph.facebook.com."""
        fb_uid = await self._convert_to_uid(fb_id) or fb_id
        try:
            url = f"https://graph.facebook.com/{fb_uid}/picture?type=large&redirect=false"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data", {}).get("url"):
                    return data["data"]["url"]
        except Exception:
            pass
        return f"https://graph.facebook.com/{fb_uid}/picture?type=large"