"""Optional bounded public-page enrichment. Failures fall back to CSV fields."""
import ipaddress
import socket
import re
from urllib.parse import urlsplit
import httpx
from app.config import settings


def fetch_public_excerpt(url):
    if not settings.ENABLE_WEB_ENRICHMENT or not url:
        return ''
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return ''
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            return ''
        # Never follow an unchecked redirect to a private service.
        with httpx.stream('GET', url, timeout=5, follow_redirects=False,
                          headers={'User-Agent': 'LeadPilotAI/0.2'}) as response:
            if response.status_code != 200 or 'text/html' not in response.headers.get('content-type', ''):
                return ''
            chunks = bytearray()
            for chunk in response.iter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 200_000:
                    break
        text = chunks[:200_000].decode('utf-8', errors='replace')
        text = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', text, flags=re.I | re.S)
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text)).strip()[:6000]
    except Exception:
        return ''
