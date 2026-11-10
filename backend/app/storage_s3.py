"""S3-compatible object storage (AWS S3, MinIO, Cloudflare R2, ...) without extra dependencies.

Requests are signed with AWS Signature Version 4 using only the standard library.
Selected with STORAGE_BACKEND=s3 and S3_ENDPOINT / S3_BUCKET / S3_ACCESS_KEY /
S3_SECRET_KEY / S3_REGION. Keys are validated exactly like LocalStorage keys.
Objects that need a file path (OpenCV video decoding) are downloaded to a
private temporary cache that is cleared on delete.
"""

from __future__ import annotations

import hashlib
import hmac
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from .services import _KEY_RE


class S3Error(RuntimeError):
    pass


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


class S3Storage:
    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, region: str = "us-east-1",
                 cache_dir: Path | None = None, timeout: float = 30.0):
        if not (endpoint and bucket and access_key and secret_key):
            raise ValueError("S3 storage needs S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY and S3_SECRET_KEY")
        u = urllib.parse.urlsplit(endpoint.rstrip("/"))
        if u.scheme not in ("http", "https"):
            raise ValueError("S3_ENDPOINT must be an http(s) URL")
        self.scheme, self.host, self.base_path = u.scheme, u.netloc, u.path
        self.bucket, self.ak, self.sk, self.region, self.timeout = bucket, access_key, secret_key, region, timeout
        self.cache = Path(cache_dir or tempfile.mkdtemp(prefix="isl-nova-s3-"))
        self.cache.mkdir(parents=True, exist_ok=True)

    # --- signing ------------------------------------------------------------
    def _key(self, key: str) -> str:
        if not _KEY_RE.match(key) or ".." in key.split("/"):
            raise ValueError("invalid storage key")
        return key

    def _request(self, method: str, key: str | None, body: bytes = b"", query: dict | None = None,
                 extra: dict | None = None) -> tuple[int, bytes, dict]:
        now = datetime.now(UTC)
        amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        path = f"{self.base_path}/{self.bucket}" + (f"/{urllib.parse.quote(key, safe='/-_.~')}" if key else "")
        q = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(str(v), safe='-_.~')}"
                     for k, v in sorted((query or {}).items()))
        payload_hash = hashlib.sha256(body).hexdigest()
        headers = {"host": self.host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date, **(extra or {})}
        signed = ";".join(sorted(headers))
        canonical = "\n".join([method, path, q, *(f"{k}:{headers[k].strip()}" for k in sorted(headers)), "",
                               signed, payload_hash])
        scope = f"{day}/{self.region}/s3/aws4_request"
        to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        k = _sign(_sign(_sign(_sign(("AWS4" + self.sk).encode(), day), self.region), "s3"), "aws4_request")
        sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
        headers["authorization"] = f"AWS4-HMAC-SHA256 Credential={self.ak}/{scope}, SignedHeaders={signed}, Signature={sig}"
        url = f"{self.scheme}://{self.host}{path}" + (f"?{q}" if q else "")
        req = urllib.request.Request(url, data=body if method in ("PUT", "POST") else None, method=method,  # noqa: S310
                                     headers={k2: v for k2, v in headers.items() if k2 != "host"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 - URL built from config
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers or {})

    # --- storage API (same as LocalStorage) ------------------------------------
    def ensure_bucket(self) -> None:
        st, _, _ = self._request("HEAD", None)
        if st == 404:
            st, body, _ = self._request("PUT", None)
            if st not in (200, 409):
                raise S3Error(f"cannot create bucket {self.bucket}: {st} {body[:200]!r}")

    def put(self, key: str, data: bytes) -> None:
        st, body, _ = self._request("PUT", self._key(key), data)
        if st != 200:
            raise S3Error(f"PUT {key}: {st} {body[:200]!r}")

    def get(self, key: str) -> bytes:
        st, body, _ = self._request("GET", self._key(key))
        if st == 404:
            raise FileNotFoundError(key)
        if st != 200:
            raise S3Error(f"GET {key}: {st}")
        return body

    def exists(self, key: str) -> bool:
        try:
            return self._request("HEAD", self._key(key))[0] == 200
        except ValueError:
            return False

    def delete(self, key: str) -> bool:
        existed = self.exists(key)
        st, body, _ = self._request("DELETE", self._key(key))
        if st not in (200, 204):
            raise S3Error(f"DELETE {key}: {st} {body[:200]!r}")
        cached = self.cache / key
        if cached.exists():
            cached.unlink()
        return existed

    def local_path(self, key: str) -> Path:
        """A local copy for code that needs a file (video decoding). Written files must be put() back."""
        p = (self.cache / self._key(key)).resolve()
        if self.cache.resolve() not in p.parents:
            raise ValueError("invalid storage key")
        if not p.exists() and self.exists(key):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(self.get(key))
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def sync(self, key: str) -> None:
        """Upload the cached file written through local_path(key)."""
        self.put(key, self.local_path(key).read_bytes())

    def materialize(self, keys) -> Path:
        for k in keys:
            self.local_path(k)
        return self.cache
