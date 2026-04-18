import time

from .client import Client
from .logger import Logger
from .encrypt import md5_hash
from .config import CONFIG

METHOD = "chaojiying"  # or "ttshitu"


class Recognizer:

    def __init__(self, method=METHOD):
        self._method = method
        self._client = Client(method)
        self._logger = Logger("recognizer")

    def recognize_captcha(
        self, image_base64: str, words: list[str]
    ) -> list[tuple[int, int]]:
        if self._method == "ttshitu":
            result = self._ttshitu(image_base64, words)
        elif self._method == "chaojiying":
            result = self._chaojiying(image_base64, words)
        else:
            raise ValueError("Invalid recognition method")

        # "234,47|168,90|101,63" -> [(234, 47), (168, 90), (101, 63)]
        return [
            (int(item.split(",")[0]), int(item.split(",")[1]))
            for item in result.split("|")
        ]

    def _ttshitu(self, image_base64: str, words: list[str]) -> str:
        start = time.perf_counter()

        resp = self._client.post(
            "http://api.ttshitu.com/predict",
            data={
                "username": CONFIG["recognize"]["username"],
                "password": CONFIG["recognize"]["password"],
                "typeid": "20",
                "image": image_base64,
                "remark": str(words),
            },
            timeout=8.0,
        )

        result = resp.json()["data"]["result"]

        elapsed = time.perf_counter() - start
        self._logger.info(f"Recognized captcha in {elapsed:.2f} seconds: {result}")
        self._logger.breathe()

        return result

    def _chaojiying(self, image_base64: str, words: list[str]) -> str:
        start = time.perf_counter()

        resp = self._client.post(
            "https://upload.chaojiying.net/Upload/Processing.php",
            data={
                "user": CONFIG["recognize"]["username"],
                "pass2": md5_hash(CONFIG["recognize"]["password"]),
                "softid": CONFIG["recognize"]["softid"],
                "codetype": "9801",
                "str_debug": f"{{8a:{','.join(words)}/8a}}",
                "file_base64": image_base64,
            },
            timeout=4.0,
        )

        result = resp.json()["pic_str"]

        elapsed = time.perf_counter() - start
        self._logger.info(f"Recognized captcha in {elapsed:.2f} seconds: {result}")
        self._logger.info(f"Sleeping for 1 second...")
        time.sleep(1)  # 否则太快了，check 完 submit 时会报错 '(250) 验证码非法校验'
        self._logger.breathe()

        return result
