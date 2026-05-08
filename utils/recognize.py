import time

from .client import Client
from .logger import Logger
from .encrypt import md5_hash
from .config import CONFIG


class Recognizer:

    def __init__(self):
        self._method = CONFIG.get("recognize", "method", fallback="")
        self._client = Client(self._method)
        self._logger = Logger("recognizer")

    def recognize_captcha(
        self, image_base64: str, words: list[str]
    ) -> list[tuple[int, int]]:
        start = time.perf_counter()

        if self._method == "ttshitu":
            result = self._ttshitu(image_base64, words)
        elif self._method == "chaojiying":
            result = self._chaojiying(image_base64, words)
        else:
            raise Exception(
                "Invalid recognition method, must be 'ttshitu' or 'chaojiying'"
            )

        elapsed = time.perf_counter() - start
        self._logger.info(
            f"Recognized captcha by {self._method} in {elapsed:.2f} seconds: {result}"
        )
        self._logger.breathe()

        # "234,47|168,90|101,63" -> [(234, 47), (168, 90), (101, 63)]
        return [
            (int(item.split(",")[0]), int(item.split(",")[1]))
            for item in result.split("|")
        ]

    def _ttshitu(self, image_base64: str, words: list[str]) -> str:
        resp = self._client.post(
            "http://api.ttshitu.com/predict",
            data={
                "username": CONFIG["recognize:ttshitu"]["username"],
                "password": CONFIG["recognize:ttshitu"]["password"],
                "typeid": "43",  # 快速点选，http://www.ttshitu.com/news/9c2cae0531a147d2bafac3cd737109e7.html
                "image": image_base64,
                "content": "".join(words),
            },
            timeout=4.0,
        )
        return resp.json()["data"]["result"]

    def _chaojiying(self, image_base64: str, words: list[str]) -> str:
        resp = self._client.post(
            "https://upload.chaojiying.net/Upload/Processing.php",
            data={
                "user": CONFIG["recognize:chaojiying"]["username"],
                "pass2": md5_hash(CONFIG["recognize:chaojiying"]["password"]),
                "softid": CONFIG["recognize:chaojiying"]["softid"],
                "codetype": "9801",
                "str_debug": f"{{8a:{','.join(words)}/8a}}",
                "file_base64": image_base64,
            },
            timeout=4.0,
        )
        return resp.json()["pic_str"]
