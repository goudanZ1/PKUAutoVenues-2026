import argparse
import base64
import json
import re
import sys
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
from utils.notify import Notifier
from utils.time import get_next_weekday, get_release_time, wait_until
from utils.config import LOGS_DIR, LOG_FILE, CONFIG


def main(
    venue: str,
    target_date: str,
    target_times: list[tuple[str, int]],
    preferred_spaces: list[str],
    skip_pay: bool,
):
    logger = Logger("main")
    logger.info(f"Running: {' '.join(sys.argv)}")
    logger.breathe()

    logger.info(f"Venue ID: {venue}")
    logger.info(f"Target date: {target_date}")
    logger.info(f"Target times:")
    for begin_time, slots_count in target_times:
        # 从 begin_time 开始，连续 slots_count 个时段
        logger.info(
            f"  - begin at {begin_time}, {f'{slots_count} consecutive slots' if slots_count > 1 else 'single slot'}"
        )
    logger.info(f"Preferred spaces: {preferred_spaces}")
    logger.info(f"Auto payment with campus card: {not skip_pay}")
    logger.breathe()

    release_time = get_release_time(target_date)
    login_time = release_time - timedelta(minutes=1)
    # captcha_time = release_time - timedelta(seconds=15)

    logger.info(f"Quota release time: {release_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Plan:")
    logger.info(f"  - login at {login_time.strftime('%H:%M:%S')}")
    logger.info(f"  - start main loop at {release_time.strftime('%H:%M:%S')}")
    logger.breathe()

    client = EpeClient("epe")
    recognizer = Recognizer()
    notifier = Notifier()

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
                logger.debug(f"Target times:")
                for begin_time, slots_count in target_times:
                    logger.debug(
                        f"  - begin at {begin_time}, {f'{slots_count} consecutive slots' if slots_count > 1 else 'single slot'}"
                    )
                logger.debug(f"Preferred spaces: {preferred_spaces}")
                logger.breathe()

                slots_info: list[dict] = sorted(  # 时段
                    info_data.get("spaceTimeInfo", []),
                    key=lambda slot: slot["beginTime"],
                )

                begin_time_to_slot_idx: dict[str, int] = {
                    slot["beginTime"]: i for i, slot in enumerate(slots_info)
                }

                res_date_space_info: dict[str, list[dict]] = info_data.get(
                    "reservationDateSpaceInfo", {}
                )

                if target_date not in res_date_space_info:
                    raise Exception(
                        f"Target date {target_date} not found in reservationDateSpaceInfo"
                    )

                spaces_res_info: list[dict] = res_date_space_info[target_date]

                for begin_time, slots_count in target_times:
                    if begin_time not in begin_time_to_slot_idx:
                        logger.warning(
                            f"('{begin_time}', {slots_count}) Begin time {begin_time} not found in spaceTimeInfo, skipping"
                        )
                        continue
                    begin_slot_idx = begin_time_to_slot_idx[begin_time]

                    if begin_slot_idx + slots_count > len(slots_info):
                        # slots: begin, begin + 1, ..., begin + count - 1
                        slots_max_count = len(slots_info) - begin_slot_idx
                        logger.warning(
                            f"('{begin_time}', {slots_count}) Not enough slots after {begin_time}, reducing to {slots_max_count}"
                        )
                        slots_count = slots_max_count

                    target_slots_info = slots_info[
                        begin_slot_idx : begin_slot_idx + slots_count
                    ]

                    available_space_to_trades: dict[str, list[dict]] = {}
                    for space_res_info in spaces_res_info:
                        trades: list[dict] = [
                            space_res_info.get(str(slot["id"]), {})
                            for slot in target_slots_info
                        ]
                        if all(trade.get("reservationStatus") == 1 for trade in trades):
                            # 1 空闲，2 不让约，3 待付款，4 已预约
                            available_space_to_trades[space_res_info["spaceName"]] = [
                                {
                                    "timeId": str(slot["id"]),
                                    "beginTime": slot["beginTime"],
                                    "endTime": slot["endTime"],
                                    "spaceId": str(space_res_info["id"]),
                                    "spaceName": space_res_info["spaceName"],
                                    "orderFee": int(trade["orderFee"]),
                                }
                                for slot, trade in zip(
                                    target_slots_info,
                                    trades,
                                )
                            ]

                    if not available_space_to_trades:
                        logger.info(
                            f"('{begin_time}', {slots_count}) No available spaces"
                        )
                        continue

                    logger.info(
                        f"('{begin_time}', {slots_count}) Available spaces: {list(available_space_to_trades.keys())}"
                    )
                    logger.breathe()

                    for space in preferred_spaces:
                        if space in available_space_to_trades:
                            selected_space = space
                            break
                    else:
                        selected_space = random.choice(
                            list(available_space_to_trades.keys())
                        )

                    selected_trades = available_space_to_trades[selected_space]

                    selected_time = f"{selected_trades[0]['beginTime']}-{selected_trades[-1]['endTime']}"
                    total_fee = sum(trade["orderFee"] for trade in selected_trades)

                    logger.info(
                        f"Selected: {selected_time} {selected_space}场地 (¥{total_fee})"
                    )
                    logger.debug(f"Trades to submit:")
                    for trade in selected_trades:
                        logger.debug(f"  - {trade}")
                    logger.breathe()
                    break

                else:
                    logger.breathe()
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
                        "reservationOrderJson": json.dumps(
                            [
                                {"spaceId": trade["spaceId"], "timeId": trade["timeId"]}
                                for trade in selected_trades
                            ],
                            separators=(",", ":"),
                        ),
                        "reservationDate": target_date,
                        "weekStartDate": target_date,
                        "reservationType": "-1",
                        "orderPrice": total_fee,
                        "orderPin": generate_order_pin(),
                        "venueSiteId": venue,
                        "phone": CONFIG["epe"]["phone"],
                    },
                )

                trade_id = submit_data.get("id")
                trade_no = submit_data.get("tradeNo")

                if trade_id and trade_no:
                    logger.info(f"Successfully submitted reservation order")
                    logger.info(
                        f"Check the order online: https://epe.pku.edu.cn/venue/orders"
                    )
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

        """
        Pay with campus card (optional)
        """

        if skip_pay:
            logger.info("Skipped auto payment")
            logger.breathe()
            notifier.notify_message(
                "[PKUAutoVenues] 需要手动付款 >_<",
                f"已成功预约 {target_date} {selected_time}（{selected_space}场地），请在十分钟内手动完成支付",
            )
            return

        try:
            pay_data = client.epe_post(
                "https://epe.pku.edu.cn/venue-server/api/venue/finances/order/pay",
                data={"payType": "1", "venueTradeNo": trade_no, "isApp": "0"},
            )
            pay_fee = pay_data.get("payFee")
            if not pay_fee:
                raise Exception(f"payFee not found in pay response")

            logger.info(
                f"Successfully paid ¥{pay_fee} for the reservation order with campus card"
            )
            logger.breathe()
            notifier.notify_message(
                "[PKUAutoVenues] 预约成功 OvO",
                f"已预约 {target_date} {selected_time}（{selected_space}场地），并成功用校园卡支付 {pay_fee} 元",
            )

        except Exception as e:
            logger.error(f"Failed to pay for the reservation order: {e}")
            logger.breathe()
            notifier.notify_message(
                "[PKUAutoVenues] 需要手动付款 >_<",
                f"已成功预约 {target_date} {selected_time}（{selected_space}场地），请在十分钟内手动完成支付 (Error: {e})",
            )

    except Exception as e:
        logger.error(str(e))
        logger.breathe()
        notifier.notify_message("[PKUAutoVenues] 预约失败 QAQ", str(e))

    finally:
        logger.info(f"Check the log file: {LOG_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PKU Auto Venues Reservation",
        epilog="Example: uv run main.py -v 五四 -d 7 -t 19:00/2 19:00 -s 9 8\nPlease check README.md for more usage examples.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--venue", required=True, help="Venue site name or ID, e.g. qdb, 86"
    )
    parser.add_argument(
        "-d",
        "--date",
        required=True,
        help="Target date or weekday, e.g. 2026-04-01, 6 (for next Saturday)",
    )
    parser.add_argument(
        "-t",
        "--times",
        required=True,
        nargs="+",
        help="Target begin times and durations, e.g. 15:00 (single slot) 17:00/2 (2 consecutive slots)",
    )
    parser.add_argument(
        "-s",
        "--spaces",
        nargs="*",
        default=[],
        help="Preferred space names (optional), e.g. 4号 5 (abbr for 5号)",
    )
    parser.add_argument(
        "--skip-pay",
        action="store_true",
        help="Skip auto payment, need to manually pay within 10 minutes",
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
    target_times: list[tuple[str, int]] = []
    for t in args.times:
        m = re.fullmatch(r"(\d{2}:\d{2})(?:/(\d+))?", t)
        if m is None:
            parser.error(
                f"Invalid -t/--times item {t!r}: must be HH:MM or HH:MM/N (e.g. 19:00, 19:00/2)"
            )

        begin_time = m.group(1)
        try:
            datetime.strptime(begin_time, "%H:%M")
        except ValueError:
            parser.error(
                f"Invalid -t/--times item {t!r}: {begin_time!r} is not a valid time"
            )

        slots_count = int(m.group(2)) if m.group(2) else 1
        if slots_count < 1:
            parser.error(f"Invalid -t/--times item {t!r}: must order at least 1 slot")

        target_times.append((begin_time, slots_count))

    # Process spaces
    preferred_spaces = []
    for s in args.spaces:
        try:
            preferred_spaces.append(f"{int(s)}号")
        except ValueError:
            preferred_spaces.append(s)

    main(
        venue=venue,
        target_date=target_date,
        target_times=target_times,
        preferred_spaces=preferred_spaces,
        skip_pay=args.skip_pay,
    )
