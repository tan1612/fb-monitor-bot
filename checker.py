import re
import httpx


class FacebookChecker:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    DIE_PATTERNS = [
        "this content isn't available",
        "this page isn't available",
        "content not found",
        "page not found",
        "trang này không khả dụng",
        "nội dung này không khả dụng",
        "sorry, this page isn't available",
        "the link you followed may be broken",
    ]

    async def check(self, fb_id: str):

        url = f"https://www.facebook.com/{fb_id}"

        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=20,
                follow_redirects=True
            ) as client:

                r = await client.get(url)

            html = r.text.lower()

            # 404
            if r.status_code == 404:
                return "die", None

            # Redirect bất thường
            final_url = str(r.url).lower()

            if final_url in (
                "https://www.facebook.com/",
                "https://facebook.com/",
            ):
                return "die", None

            if "/login" in final_url:
                return "unknown", None

            # Pattern die
            for pattern in self.DIE_PATTERNS:
                if pattern in html:
                    return "die", None

            # Title
            title_match = re.search(
                r"<title[^>]*>(.*?)</title>",
                r.text,
                re.I | re.S
            )

            if title_match:
                title = title_match.group(1).strip()

                # Facebook chung
                if title.lower() in [
                    "facebook",
                    "facebook - log in or sign up",
                    "facebook – log in or sign up",
                ]:
                    return "die", None

                title = re.sub(
                    r"\s*[\|\-–]\s*facebook.*$",
                    "",
                    title,
                    flags=re.I
                ).strip()

                return "live", title

            return "unknown", None

        except httpx.TimeoutException:
            return "unknown", None

        except Exception:
            return "unknown", None