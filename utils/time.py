import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .logger import Logger


def get_next_weekday(weekday: int) -> str:
    """返回下一个周 weekday（1~7，包括今天）的日期"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    days_ahead = (weekday - 1 - today.weekday()) % 7  # weekday(): 0~6
    target = today + timedelta(days=days_ahead)
    return target.strftime("%Y-%m-%d")


def get_release_time(target_date: str) -> datetime:
    """根据 target_date 反推预约名额放出的时间（三天前的中午 12 点）"""
    d = datetime.strptime(target_date, "%Y-%m-%d")
    tz = ZoneInfo("Asia/Shanghai")
    return datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=tz) - timedelta(days=3)


def wait_until(dt: datetime, logger: Logger, label: str, strict: bool):
    """通过轮询，等待到 dt，若已过时就立刻返回"""
    while True:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        remaining = (dt - now).total_seconds()

        if remaining <= 0:
            logger.info(f"Target time {dt.strftime('%Y-%m-%d %H:%M:%S')} reached!")
            logger.info(f"Starting '{label}'...")
            logger.breathe()
            return

        should_log = True
        if remaining > 100:
            sleep = 30
        elif remaining > 30:
            sleep = 8
        elif remaining > 10:
            sleep = 2
        elif remaining > 3 or not strict:
            sleep = 1
        else:
            sleep = 0.1
            should_log = False

        if should_log:
            logger.info(
                f"Waiting for {dt.strftime('%H:%M:%S')} to start '{label}': {remaining:.2f}s remaining"
            )
        time.sleep(sleep)
