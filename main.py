import argparse
import base64
import json
import re
import time
from datetime import datetime, timedelta
import random

from utils.client import EpeClient
from utils.logger import Logger
from utils.encrypt import (
    encrypt_rsa,
    encrypt_aes_ecb,
    generate_uuid,
    generate_order_pin,
)
from utils.recognize import Recognizer
from utils.time import get_next_weekday, get_release_time, wait_until
from utils.config import LOGS_DIR, LOG_FILE, CONFIG


def main(
    venue: str, target_date: str, target_times: list[str], preferred_spaces: list[str]
):
    logger = Logger("main")
    logger.info(f"Starting main function")
    logger.breathe()

    client = EpeClient("epe")
    recognizer = Recognizer()

    logger.info(f"Venue ID: {venue}")
    logger.info(f"Target date: {target_date}")
    logger.info(f"Target times: {target_times}")
    logger.info(f"Preferred spaces: {preferred_spaces}")
    logger.breathe()

    release_time = get_release_time(target_date)
    login_time = release_time - timedelta(minutes=1)
    # captcha_time = release_time - timedelta(seconds=15)

    logger.info(f"Quota release time: {release_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Plan:")
    logger.info(f"  - login at {login_time.strftime('%H:%M:%S')}")
    logger.info(f"  - start main loop at {release_time.strftime('%H:%M:%S')}")
    logger.breathe()

    try:
        """
        Login
        """

        wait_until(login_time, logger, "login", strict=False)

        # 1
        client.get("https://epe.pku.edu.cn/venue-server/loginto")

        # 2 (Optional?)
        client.post(
            "https://iaaa.pku.edu.cn/iaaa/oauth.jsp",
            data={
                "appID": "ty",
                "appName": "北京大学体测系统",
                "redirectUrl": "https://epe.pku.edu.cn/ggtypt/dologin",
                "redirectLogonUrl": "https://epe.pku.edu.cn/ggtypt/dologin",
            },
        )

        # 3
        iaaa_resp = client.post(
            "https://iaaa.pku.edu.cn/iaaa/oauthlogin.do",
            data={
                "appid": "ty",
                "userName": CONFIG["iaaa"]["username"],
                "password": encrypt_rsa(CONFIG["iaaa"]["password"]),
                "randCode": "",
                "smsCode": "",
                "otpCode": "",
                "remTrustChk": "false",
                "redirUrl": "https://epe.pku.edu.cn/ggtypt/dologin",
            },
        )

        try:
            iaaa_json: dict = iaaa_resp.json()
        except Exception as e:
            raise Exception(f"Failed to parse IAAA response as JSON: {e}")

        if iaaa_json.get("success") is True and "token" in iaaa_json:
            iaaa_token = iaaa_json["token"]
            logger.info(f"IAAA login successful")
            logger.debug(f"IAAA token: {iaaa_token}")
            logger.breathe()
        else:
            msg = iaaa_json.get("errors", {}).get("msg", "Unknown error")
            raise Exception(f"IAAA login failed: {msg}")

        # 4
        client.get(
            "https://epe.pku.edu.cn/ggtypt/dologin",
            params={
                "_rand": random.random(),
                "token": iaaa_token,
            },
        )

        # commonMethods.getToken()
        sso_pku_token = client.session.cookies.get("sso_pku_token")

        if sso_pku_token:
            logger.info(f"GGTYPT login successful")
            logger.debug(f"sso_pku_token: {sso_pku_token}")
            logger.breathe()
        else:
            raise Exception(f"GGTYPT login failed: sso_pku_token cookie not found")

        # 5
        epe_login_data = client.epe_post(
            "https://epe.pku.edu.cn/venue-server/api/login",
            headers={
                "sso-token": sso_pku_token,
            },
        )

        if epe_login_data.get("token", {}).get("access_token", None):
            # loginSuccess(), save as local storage (dataSix: e.token.access_token)
            client.cg_auth_token = epe_login_data["token"]["access_token"]
            logger.info(f"EPE login successful")
            logger.debug(f"cg_auth_token: {client.cg_auth_token}")
            logger.breathe()
        else:
            raise Exception(f"EPE login failed: access_token not found")

        # 6 (Optional?)
        role_login_data = client.epe_post(
            "https://epe.pku.edu.cn/venue-server/roleLogin",
            data={
                "roleid": 3,
            },
        )

        if role_login_data.get("token", {}).get("access_token", None):
            client.cg_auth_token = role_login_data["token"]["access_token"]
            logger.info(f"Role login successful")
            logger.debug(f"cg_auth_token (with role info): {client.cg_auth_token}")
            logger.breathe()
        else:
            raise Exception(f"Role login failed: access_token not found")

        """
        Loop: Recognize captcha, fetch reservation info, and submit order
        """

        max_turns = 20
        retry_delay = 0.2

        # 填一次验证码只能用于一次 submit 请求，如果 submit 失败了，需要重新识别验证码，所以这里设计成循环
        # 由于识别验证码需要耗一些时间，最好先识别验证码再请求 info 数据，确保 info 数据的时效性，减少 submit 失败的概率

        # 经试验，“在 12 点之前就识别好验证码，一到 12 点立刻获取 info 并提交” 是不行的，
        # 过了 12 点验证码会失效，submit 时会报 '(250) 验证码没有通过'

        client_point_uid = f"point-{generate_uuid()}"

        wait_until(release_time, logger, "main loop", strict=True)

        for turn in range(1, max_turns + 1):
            try:
                # Get captcha
                get_captcha_data = client.epe_get(
                    "https://epe.pku.edu.cn/venue-server/api/captcha/get",
                    params={
                        "captchaType": "clickWord",
                        "clientUid": client_point_uid,
                        "ts": str(int(time.time() * 1000)),
                    },
                )

                if get_captcha_data.get("success") is not True:
                    raise Exception(
                        f"Failed to get captcha: {get_captcha_data.get('repMsg')}"
                    )

                rep_data = get_captcha_data["repData"]

                image_base64 = rep_data["originalImageBase64"]
                words = rep_data["wordList"]
                captcha_token = rep_data["token"]
                captcha_secret_key = rep_data["secretKey"]

                image_path = (
                    LOGS_DIR
                    / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]}.png"
                )
                image_path.write_bytes(base64.b64decode(image_base64))

                logger.info(f"Captcha image saved to: {image_path}")
                logger.info(f"Words to click: {words}")
                logger.debug(f"Captcha token: {captcha_token}")
                logger.debug(f"Captcha secret key: {captcha_secret_key}")
                logger.breathe()

                # Recognize captcha
                recognize_result = recognizer.recognize_captcha(image_base64, words)

                # [(234, 47), (168, 90), (101, 63)]
                # -> '[{"x":234,"y":47},{"x":168,"y":90},{"x":101,"y":63}]'
                recognized_points = json.dumps(
                    [{"x": x, "y": y} for x, y in recognize_result],
                    separators=(",", ":"),
                )

                # Check captcha
                check_captcha_data = client.epe_post(
                    "https://epe.pku.edu.cn/venue-server/api/captcha/check",
                    data={
                        "captchaType": "clickWord",
                        "pointJson": encrypt_aes_ecb(
                            recognized_points, captcha_secret_key
                        ),
                        "token": captcha_token,
                    },
                )

                if check_captcha_data.get("success") is not True:
                    raise Exception(
                        f"Failed to pass captcha check, maybe the recognition is wrong: {check_captcha_data.get('repMsg')}"
                    )

                captcha_verified_at = time.perf_counter()

                logger.info("Captcha verified successfully!")
                logger.breathe()

                # Fetch reservation info
                info_data = client.epe_get(
                    "https://epe.pku.edu.cn/venue-server/api/reservation/day/info",
                    params={
                        "venueSiteId": venue,
                        "searchDate": target_date,
                    },
                )

                logger.debug(f"Target date: {target_date}")
                logger.debug(f"Target times: {target_times}")
                logger.debug(f"Preferred spaces: {preferred_spaces}")
                logger.breathe()

                space_time_info: list[dict] = info_data.get("spaceTimeInfo", [])
                time_to_id: dict[str, str] = {
                    st["beginTime"]: str(st["id"]) for st in space_time_info
                }
                id_to_time: dict[str, str] = {
                    str(st["id"]): st["beginTime"] for st in space_time_info
                }

                target_time_ids: list[str] = []
                for t in target_times:
                    if t in time_to_id:
                        target_time_ids.append(time_to_id[t])
                logger.debug(f"Target time IDs: {target_time_ids}")
                logger.breathe()

                if not target_time_ids:
                    raise Exception(
                        f"None of the target times {target_times} found in spaceTimeInfo"
                    )

                res_date_space_info: dict[str, list[dict]] = info_data.get(
                    "reservationDateSpaceInfo", {}
                )

                if target_date not in res_date_space_info:
                    raise Exception(
                        f"Target date {target_date} not found in reservationDateSpaceInfo"
                    )

                spaces: list[dict] = res_date_space_info[target_date]

                for time_id in target_time_ids:
                    available_space_to_trade: dict[str, dict] = {}
                    for space in spaces:
                        if time_id in space:
                            trade: dict = space[time_id]
                            if trade.get("reservationStatus") == 1:
                                # 1 空闲，2 不让约，3 待付款，4 已预约
                                available_space_to_trade[space["spaceName"]] = {
                                    "timeId": time_id,
                                    "spaceId": str(space["id"]),
                                    "spaceName": space["spaceName"],
                                    "orderFee": int(trade["orderFee"]),
                                }

                    if not available_space_to_trade:
                        logger.info(
                            f"No available spaces for time {id_to_time[time_id]}"
                        )
                        logger.breathe()
                        continue

                    logger.info(
                        f"Available spaces for time {id_to_time[time_id]}: {list(available_space_to_trade.keys())}"
                    )
                    for space, trade in available_space_to_trade.items():
                        logger.debug(f"  {space} {trade}")
                    logger.breathe()

                    for space in preferred_spaces:
                        if space in available_space_to_trade:
                            target_trade = available_space_to_trade[space]
                            break
                    else:
                        target_trade = random.choice(
                            list(available_space_to_trade.values())
                        )

                    logger.info(
                        f"Selected trade: {id_to_time[target_trade['timeId']]} {target_trade['spaceName']} (¥{target_trade['orderFee']})"
                    )
                    logger.breathe()
                    break

                else:
                    raise Exception(f"None of the target times have available spaces")

                # 如果 check captcha 后 submit 太快，submit 时会报 '(250) 验证码非法校验'
                elapsed = time.perf_counter() - captcha_verified_at
                if elapsed < 1:
                    logger.info(f"Sleep for {1 - elapsed:.2f} seconds...")
                    logger.breathe()
                    time.sleep(1 - elapsed)

                # Submit reservation order
                submit_data = client.epe_post(
                    "https://epe.pku.edu.cn/venue-server/api/reservation/order/submit",
                    data={
                        "captchaVerification": encrypt_aes_ecb(
                            captcha_token + "---" + recognized_points,
                            captcha_secret_key,
                        ),
                        "captchaToken": captcha_token,
                        "reservationOrderJson": f'[{{"spaceId":"{target_trade["spaceId"]}","timeId":"{target_trade["timeId"]}"}}]',
                        "reservationDate": target_date,
                        "weekStartDate": target_date,
                        "reservationType": "-1",
                        "orderPrice": target_trade["orderFee"],
                        "orderPin": generate_order_pin(),
                        "venueSiteId": venue,
                        "phone": CONFIG["epe"]["phone"],
                    },
                )

                trade_id = submit_data.get("id")
                trade_no = submit_data.get("tradeNo")

                if trade_id and trade_no:
                    logger.info(f"Successfully submitted reservation order")
                    logger.breathe()
                    break

                else:
                    raise Exception(
                        f"Failed to submit reservation order: trade ID or trade No not found in response"
                    )

            except Exception as e:
                logger.warning(f"Turn {turn}/{max_turns} failed: {e}")
                if turn < max_turns:
                    logger.warning(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                logger.breathe()

        else:
            logger.error(f"All {max_turns} turns failed, exiting")
            raise Exception(
                f"Failed to find available spaces for reservation after {max_turns} turns"
            )

        # Pay
        try:
            pay_data = client.epe_post(
                "https://epe.pku.edu.cn/venue-server/api/venue/finances/order/pay",
                data={"payType": "1", "venueTradeNo": trade_no, "isApp": "0"},
            )
            pay_fee = pay_data.get("payFee")
            if not pay_fee:
                raise Exception(f"payFee not found in pay response")
        except Exception as e:
            raise Exception(
                f"Please pay for the reservation order manually in 10 minutes. Error: {e}"
            )

        logger.info(
            f"Successfully paid ¥{pay_fee} for the reservation order with campus card"
        )
        logger.info(f"Check the order online: https://epe.pku.edu.cn/venue/orders")
        logger.info(f"Check the log file: {LOG_FILE}")
        logger.breathe()
        # notify

    except Exception as e:
        logger.error(str(e))
        # notify
        exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PKU Auto Venues Reservation")
    parser.add_argument(
        "-v", "--venue", required=True, help="Venue site name or ID, e.g. qdb / 86"
    )
    parser.add_argument(
        "-d",
        "--date",
        required=True,
        help="Target date or weekday, e.g. 2026-04-01 / 6 (for next Saturday)",
    )
    parser.add_argument(
        "-t",
        "--times",
        required=True,
        nargs="+",
        help="Target begin times, e.g. 15:00 20:00",
    )
    parser.add_argument(
        "-s",
        "--spaces",
        nargs="*",
        default=[],
        help="Preferred space names (optional), e.g. 4号 5号",
    )
    args = parser.parse_args()

    # Process venue
    venue_aliases = {
        "qdb": "60",
        "邱德拔": "60",
        "54": "86",
        "ws": "86",
        "五四": "86",
    }
    if args.venue in venue_aliases:
        venue = venue_aliases[args.venue]
    else:
        try:
            int(args.venue)
        except ValueError:
            parser.error(
                f"Invalid -v/--venue {args.venue!r}: must be an alias or an integer"
            )
        venue = args.venue

    # Process date
    if re.fullmatch(r"[1-7]", args.date):
        target_date = get_next_weekday(int(args.date))
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            parser.error(f"Invalid -d/--date {args.date!r}: not a valid calendar date")
        target_date = args.date
    else:
        parser.error(
            f"Invalid -d/--date {args.date!r}: must be in format YYYY-MM-DD (e.g. 2026-04-01) or an integer 1~7 (weekday)"
        )

    # Process times
    target_times = []
    for t in args.times:
        if not re.fullmatch(r"\d{2}:\d{2}", t):
            parser.error(
                f"Invalid -t/--times item {t!r}: must be in format HH:MM, e.g. 19:00"
            )
        target_times.append(t)

    # Process spaces
    preferred_spaces = []
    for s in args.spaces:
        try:
            int(s)
            preferred_spaces.append(f"{s}号")
        except ValueError:
            preferred_spaces.append(s)

    main(
        venue=venue,
        target_date=target_date,
        target_times=target_times,
        preferred_spaces=preferred_spaces,
    )
