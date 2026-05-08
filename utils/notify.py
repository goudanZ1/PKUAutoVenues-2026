import re
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from .client import Client
from .logger import Logger
from .config import CONFIG


class Notifier:

    def __init__(self):
        self._method = CONFIG.get("notify", "method", fallback="")
        self._client = Client(self._method)
        self._logger = Logger("notifier")

    def notify_message(self, title: str, content: str) -> bool:
        """成功返回 True，失败返回 False，never raise Exception，不打断主流程"""

        if self._method == "none":
            self._logger.warning(
                f"Notification method is 'none', skipping notification: {title}"
            )
            self._logger.breathe()
            return True

        try:
            if self._method == "email":
                self._email(title, content)
            elif self._method == "sc3":
                self._sc3(title, content)
            elif self._method == "sct":
                self._sct(title, content)
            elif self._method == "bark":
                self._bark(title, content)
            else:
                raise Exception(
                    "Invalid notification method, must be 'email', 'sc3', 'sct', 'bark' or 'none'"
                )

            self._logger.info(f"Sent a notification message by {self._method}: {title}")
            self._logger.breathe()
            return True

        except Exception as e:
            self._logger.error(
                f"Failed to send the notification message by {self._method}: ({e.__class__.__name__}) {e}"
            )
            self._logger.breathe()
            return False

    """
    以下各种通知方法，通知失败会 raise Exception
    """

    def _email(self, title: str, content: str):
        email = CONFIG["notify:email"]["email"]
        password = CONFIG["notify:email"]["password"]

        domain = email.split("@")[-1]
        if domain == "stu.pku.edu.cn":
            host = "smtphz.qiye.163.com"
        elif domain in {"pku.edu.cn", "qq.com", "163.com", "126.com"}:
            host = f"smtp.{domain}"
        else:
            raise Exception(
                "Unsupported email address, must end with '@stu.pku.edu.cn', '@pku.edu.cn', '@qq.com', '@163.com' or '@126.com'"
            )

        message = MIMEText(content, "plain")
        message["From"] = formataddr(("PKUAutoVenues", email))
        message["To"] = email
        message["Subject"] = title

        try:
            server = smtplib.SMTP_SSL(host, port=465)
            server.login(email, password)
            server.sendmail(email, email, message.as_string())
            server.quit()
        except Exception as e:
            raise Exception(
                f"Maybe the email address or password (authorization code) is incorrect: ({e.__class__.__name__}) {e}"
            )

    def _sc3(self, title: str, content: str):
        sendkey = CONFIG["notify:sc3"]["sendkey"]

        match = re.match(r"^sctp(\d+)t", sendkey)
        if match is None:
            raise Exception(
                "Invalid SC3 sendkey, must follow a format like 'sctp<number>t...'"
            )
        uid = match.group(1)

        response = self._client.post(
            f"https://{uid}.push.ft07.com/send/{sendkey}.send",
            data={
                "title": title,
                "desp": content.replace("\n", "\n\n"),  # Markdown
                "short": content,  # 推送消息卡片的内容，这里直接提供原始消息内容，显示时会截取前若干个字符作为预览
                "tags": "PKUAutoVenues",
            },
            timeout=60.0,
        )

        response_data = response.json()

        if response_data["code"] != 0:
            raise Exception(
                f"Maybe the SC3 sendkey is incorrect: ({response_data['code']}) {response_data.get('error')}"
            )

    def _sct(self, title: str, content: str):
        sendkey = CONFIG["notify:sct"]["sendkey"]

        response = self._client.post(
            f"https://sctapi.ftqq.com/{sendkey}.send",
            data={
                "title": title,
                "desp": content.replace("\n", "\n\n"),  # Markdown
                "noip": "1",  # 隐藏调用 IP
                "channel": "9",  # 指定消息通道为方糖服务号
            },
            timeout=60.0,
        )

        response_data = response.json()

        if response_data["code"] != 0:
            if response_data["code"] == 40001 and response_data.get("scode") == 471:
                raise Exception(
                    f"SCT exceeded daily sending frequency limit: {response_data.get('message')}"
                )
            else:
                raise Exception(
                    f"Maybe the SCT sendkey is incorrect: ({response_data['code']}) {response_data.get('message')}"
                )

    def _bark(self, title: str, content: str):
        sendkey = CONFIG["notify:bark"]["sendkey"]

        response = self._client.post(
            f"https://api.day.app/{sendkey}",
            data={
                "title": title,
                "body": content,
                "group": "PKUAutoVenues",
                "badge": "1",  # 角标提醒
            },
            timeout=60.0,
        )

        response_data = response.json()

        if response_data["code"] != 200:
            raise Exception(
                f"Maybe the Bark sendkey is incorrect: ({response_data['code']}) {response_data['message']}"
            )
