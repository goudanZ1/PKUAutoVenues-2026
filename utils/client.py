import time
from requests import sessions
from requests.models import Response
from typing import Literal, Optional

from .logger import Logger
from .encrypt import calculate_sign


class Client:

    def __init__(self, name: str):
        self.session = sessions.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            }
        )
        self._logger = Logger(name)
        self._logger.debug(f"Session initialized")
        self._logger.breathe()

    def _log_json(self, data, level: int) -> None:
        indent = "  " * level

        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    self._logger.debug(f"{indent}{k}:")
                    self._log_json(v, level + 1)
                elif isinstance(v, list):
                    self._logger.debug(f"{indent}{k}: Array({len(v)}) {v}")
                    self._log_json(v, level + 1)
                else:
                    self._logger.debug(f"{indent}{k}: {v}")

        elif isinstance(data, list):
            if level == 1:
                self._logger.debug(f"{indent}Array({len(data)}) {data}")
            if len(data) >= 1 and isinstance(data[0], (dict, list)):
                if isinstance(data[0], dict):
                    self._logger.debug(f"{indent}[0]:")
                    self._log_json(data[0], level + 1)
                else:
                    self._logger.debug(f"{indent}[0]: Array({len(data[0])}) {data[0]}")
                    self._log_json(data[0], level + 1)
                if len(data) >= 2:
                    self._logger.debug(f"{indent}[1]: ... ({len(data)} items in all)")

        else:
            self._logger.debug(f"{indent}{data}")

    def _request(self, method: Literal["GET", "POST"], url: str, **kwargs) -> Response:
        self._logger.debug(f"Sending request: {method} {url}")

        for key, value in kwargs.items():
            if value is not None and value != {}:
                if key in ["params", "data", "headers"]:
                    self._logger.debug(f"  {key}:")
                    for k, v in value.items():
                        self._logger.debug(f"    {k}: {v}")
                elif not (key == "allow_redirects" and value is True):
                    self._logger.debug(f"  {key}: {value}")
        self._logger.breathe()

        max_attempts = 3
        retry_delay = 0.5

        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.request(method, url, **kwargs)
                break
            except Exception as e:
                self._logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")
                if attempt < max_attempts:
                    self._logger.warning(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                self._logger.breathe()
        else:
            self._logger.error(f"All {max_attempts} attempts failed, exiting")
            raise Exception(
                f"Failed to send request after {max_attempts} attempts ({method} {url})"
            )

        self._logger.debug(f"Response status: {resp.status_code}")

        try:
            resp_json = resp.json()
            self._logger.debug(f"Response JSON:")
            self._log_json(resp_json, 1)
        except Exception as e:
            resp_text = resp.text.strip()
            if resp_text.startswith("<!DOCTYPE"):
                resp_text = "(HTML)"
            self._logger.debug(
                f"Response text: {resp_text[:400] + '...' if len(resp_text) > 400 else resp_text}"
            )
        self._logger.breathe()

        self._logger.debug(f"Session cookies:")
        for cookie in self.session.cookies:
            self._logger.debug(
                f"  {cookie.name}: {cookie.value} (domain={cookie.domain}; path={cookie.path})"
            )
        self._logger.breathe()

        return resp

    def get(
        self,
        url: str,
        params: dict = {},
        headers: dict = {},
        timeout=10.0,
        allow_redirects=True,
        **kwargs,
    ) -> Response:
        kwargs.pop("data", None)
        return self._request(
            "GET",
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            **kwargs,
        )

    def post(
        self,
        url: str,
        data: dict = {},
        headers: dict = {},
        timeout=10.0,
        allow_redirects=True,
        **kwargs,
    ) -> Response:
        kwargs.pop("params", None)
        return self._request(
            "POST",
            url,
            data=data,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            **kwargs,
        )


class EpeClient(Client):

    def __init__(self, name: str):
        super().__init__(name)
        self.cg_auth_token: Optional[str] = None  # Local storage: dataSix

    def _epe_request(self, method: Literal["GET", "POST"], url: str, **kwargs) -> dict:
        # emitAjax

        timestamp = str(int(time.time() * 1000))

        if method == "GET":
            params = dict(kwargs["params"])
            params["nocache"] = timestamp
            kwargs["params"] = params
            payload = params
        else:
            payload = dict(kwargs["data"])

        path = url.removeprefix("https://epe.pku.edu.cn/venue-server")
        sign = calculate_sign(timestamp, path, payload)

        headers = dict(kwargs["headers"])
        headers.update(
            {
                "app-key": "8fceb735082b5a529312040b58ea780b",
                "timestamp": timestamp,
                "sign": sign,
            }
        )
        if self.cg_auth_token:
            headers["cgAuthorization"] = self.cg_auth_token
        kwargs["headers"] = headers

        resp = super()._request(method, url, **kwargs)
        # 可能会 raise Exception，保持 message 让父过程 catch

        try:
            resp_json: dict = resp.json()
        except Exception as e:
            raise Exception(f"Failed to parse response as JSON: {e}")

        code = resp_json.get("code")
        message = resp_json.get("message", "")
        data = resp_json.get("data", {})

        if code != 200:
            raise Exception(f"{method} {path} failed: ({code}) {message}")

        return data

    def epe_get(
        self,
        url: str,
        params: dict = {},
        headers: dict = {},
        timeout=10.0,
        allow_redirects=True,
        **kwargs,
    ) -> dict:
        kwargs.pop("data", None)
        return self._epe_request(
            "GET",
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            **kwargs,
        )

    def epe_post(
        self,
        url: str,
        data: dict = {},
        headers: dict = {},
        timeout=10.0,
        allow_redirects=True,
        **kwargs,
    ) -> dict:
        kwargs.pop("params", None)
        return self._epe_request(
            "POST",
            url,
            data=data,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            **kwargs,
        )
