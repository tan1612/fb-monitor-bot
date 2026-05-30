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
        "Accept": "*/*"
    }

    def extract_id(self, raw: str) -> str | None:
        raw = raw.strip()

        if raw.isdigit():
            return raw

        if "facebook.com" in raw or "fb.com" in raw:
            return raw if raw.startswith("http") else f"https://{raw}"

        if re.match(r"^[A-Za-z0-9._]+$", raw):
            return f"https://www.facebook.com/{raw}"

        return None

    async def _convert_to_uid(self, value: str) -> str | None:

        if value.isdigit():
            return value

        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True
            ) as client:

                resp = await client.post(
                    "https://id.traodoisub.com/api.php",
                    data={"link": value},
                    headers=self.HEADERS
                )

            text = resp.text

            patterns = [
                r'"id"\s*:\s*"(\d+)"',
                r'"uid"\s*:\s*"(\d+)"',
                r'\b\d{14,20}\b'
            ]

            for pattern in patterns:
                m = re.search(pattern, text)
                if m:
                    return m.group(1)

        except Exception:
            return None

        return None

    async def _check_graph(self, uid: str) -> bool | None:

        try:
            async with httpx.AsyncClient(timeout=15) as client:

                r = await client.get(
                    f"https://graph.facebook.com/{uid}/picture",
                    params={
                        "type": "normal",
                        "redirect": "false"
                    }
                )

            if r.status_code != 200:
                return False

            try:
                data = r.json()

                if (
                    data.get("data")
                    and data["data"].get("url")
                ):
                    return True

            except Exception:
                pass

        except Exception:
            pass

        return None

    async def check(self, raw: str):

        target = self.extract_id(raw)

        if not target:
            return "unknown", None

        uid = await self._convert_to_uid(target)

        if not uid:
            return "unknown", None

        graph_result = await self._check_graph(uid)

        if graph_result is True:
            return "live", uid

        if graph_result is False:
            return "die", None

        return "unknown", None

    async def get_avatar_url(self, raw: str):

        target = self.extract_id(raw)

        if not target:
            return None

        uid = await self._convert_to_uid(target)

        if not uid:
            return None

        return (
            f"https://graph.facebook.com/"
            f"{uid}/picture?type=large"
        )