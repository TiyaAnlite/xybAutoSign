import re
import json
import time
import random
import hashlib
import logging
from typing import Tuple, List
from collections import Counter
from urllib.parse import quote

import requests

from webhooks import on_sign_in, on_sign_out


def init_logger(logger: logging.Logger, fmt="%(asctime)s - %(name)s - %(levelname)s: %(message)s"):
    # logger.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)


class XybAccount:
    def __init__(self, **config):
        self.logger = logging.Logger("XybAccount", logging.INFO)
        init_logger(self.logger)
        self.train_init = False
        self.session = requests.Session()
        self.session.headers = XybSign.HEADERS
        self.open_id = config.get("openid")
        self.union_id = config.get("unionid")
        self.location = config.get("location")
        self.account = config.get("username")
        self.account_pass = config.get("password")
        self.session_id = ""
        self.loginer_id = ""
        self.user_name = ""
        self.phone = ""
        self.train_id = ""
        self.train_type = 0
        self.post_state = 0
        self.sign_lat = self.location.get("lat", 0)
        self.sign_lng = self.location.get("lng", 0)
        self.is_sign_in = False
        self.is_sign_out = False
        self.login()
        self.load_user_info()
        self.load_train()
        self.load_train_info()

    def _request_error(self, msg: str, debug_data=None):
        self.logger.error(msg)
        self.logger.info(debug_data)
        raise RuntimeError(msg)

    def _except_json_resp(self, resp: requests.models.Response):
        try:
            return resp.json()
        except ValueError:
            return {
                "code": 500,
                "text": resp.text
            }

    def login(self):
        """自动登录，根据配置情况进行OpenID或者账号密码登录"""

        if self.account and self.account_pass:
            self.logger.info("正在使用账号密码登录")
            self.login_phone()
        elif self.open_id and self.union_id:
            self.logger.info("正在使用OpenID登录")
            self.login_wx()
        else:
            self._request_error("未正确配置账户信息")

    def login_wx(self):
        """执行登录（使用OpenID），获得loginerId信息"""

        data = dict(
            openId=self.open_id,
            unionId=self.union_id
        )
        self.session.headers.update(self.sign_header(data))
        resp = self.session.post(url=XybSign.URL_LOGIN_WX, data=data)
        resp = self._except_json_resp(resp)
        if resp["code"] == "200":
            self.loginer_id = resp["data"]["loginerId"]
            self.session_id = resp["data"]["sessionId"]
            self.phone = resp["data"]["phone"]
            self.logger.info(f"已登录(OpenID)：{self.loginer_id}")
        else:
            self._request_error(f"登录失败：{self.open_id}", resp)

    def login_phone(self):
        """执行登录（使用手机号），获得loginerId信息"""

        pass_hash = hashlib.md5(self.account_pass.encode("utf-8"))
        data = dict(
            username=self.account,
            password=pass_hash.hexdigest()
        )
        self.session.headers.update(self.sign_header(data))
        resp = self.session.post(url=XybSign.URL_LOGIN_PHONE, data=data)
        resp = self._except_json_resp(resp)
        if resp["code"] == "200":
            self.loginer_id = resp["data"]["loginerId"]
            self.session_id = resp["data"]["sessionId"]
            self.phone = resp["data"]["phone"]
            self.logger.info(f"已登录(账户密码)：{self.loginer_id}")
        else:
            self._request_error(f"登录失败：{self.open_id}", resp)

    def sign_header(self, data: dict, noce: List[int] = None, now_time: int = None) -> dict:
        """
        请求签名

        :param data: 请求体数据
        :param noce: 随机数列表(下标不能超过密码本长度)
        :param now_time: 时间戳
        :return: 签名用Headers
        """
        re_punctuation = re.compile("[`~!@#$%^&*()+=|{}':;',\\[\\].<>/?~！@#￥%……&*（）——+|{}【】‘；：”“’。，、？]")
        cookbook = ["5", "b", "f", "A", "J", "Q", "g", "a", "l", "p", "s", "q", "H", "4", "L", "Q", "g", "1", "6", "Q",
                    "Z", "v", "w", "b", "c", "e", "2", "2", "m", "l", "E", "g", "G", "H", "I", "r", "o", "s", "d", "5",
                    "7", "x", "t", "J", "S", "T", "F", "v", "w", "4", "8", "9", "0", "K", "E", "3", "4", "0", "m", "r",
                    "i", "n"]
        except_key = ["content", "deviceName", "keyWord", "blogBody", "blogTitle", "getType", "responsibilities",
                      "street", "text", "reason", "searchvalue", "key", "answers", "leaveReason", "personRemark",
                      "selfAppraisal", "imgUrl", "wxname", "deviceId", "avatarTempPath", "file", "file", "model",
                      "brand", "system", "deviceId", "platform"]
        noce = noce if noce else [random.randint(0, len(cookbook) - 1) for _ in range(20)]
        now_time = now_time if now_time else int(time.time())
        sorted_data = dict(sorted(data.items(), key=lambda x: x[0]))

        sign_str = ""
        for k, v in sorted_data.items():
            v = str(v)
            if k not in except_key and not re.search(re_punctuation, v):
                self.logger.debug(f"Add keys: {k}")
                sign_str += str(v)
        sign_str += str(now_time)
        sign_str += "".join([cookbook[i] for i in noce])
        sign_str = re.sub(r'\s+', "", sign_str)
        sign_str = re.sub(r'\n+', "", sign_str)
        sign_str = re.sub(r'\r+', "", sign_str)
        sign_str = sign_str.replace("<", "")
        sign_str = sign_str.replace(">", "")
        sign_str = sign_str.replace("&", "")
        sign_str = sign_str.replace("-", "")
        sign_str = re.sub(f'\uD83C[\uDF00-\uDFFF]|\uD83D[\uDC00-\uDE4F]', "", sign_str)
        sign_str = quote(sign_str)
        sign = hashlib.md5(sign_str.encode('ascii'))

        return {
            "n": ",".join(except_key),
            "t": str(now_time),
            "s": "_".join([str(i) for i in noce]),
            "m": sign.hexdigest(),
            "v": "1.7.14"
        }

    def load_user_info(self):
        """获得用户信息，取得userName"""

        # Loginer
        self.session.headers.update(self.sign_header({}))
        resp = self.session.get(url=XybSign.URL_ACCOUNT)
        resp = self._except_json_resp(resp)
        if resp["code"] == "200":
            self.user_name = resp["data"]["loginer"]
            self.logger.name = f"XybAccount[{self.user_name}]"
            self.logger.info("拉取用户信息完成")
        else:
            self._request_error(f"无法获取用户信息：{self.open_id}", resp)

    def load_train(self):
        """获得train信息"""

        # TrainId
        self.session.headers.update(self.sign_header({}))
        resp = self.session.get(url=XybSign.URL_TRAIN)
        resp = self._except_json_resp(resp)
        if resp["code"] == "200":
            if "clockVo" in resp["data"]:
                self.train_id = resp["data"]["clockVo"]["traineeId"]
                self.logger.info(
                    f"已载入默认实习：{resp['data']['clockVo']['planName']}({resp['data']['clockVo']['startDate']} - {resp['data']['clockVo']['endDate']})")
            else:
                self._request_error("未找到默认实习，实习可能已结束", resp["data"])
        else:
            self._request_error("无法载入默认实习", resp)

    def load_train_info(self):
        """获得train详情"""

        # TrainInfo
        data = dict(traineeId=self.train_id)
        self.session.headers.update(self.sign_header(data))
        resp = self.session.post(url=XybSign.URL_TRAIN_INFO, data=data)
        resp = self._except_json_resp(resp)
        if resp["code"] == "200":
            self.train_type = resp["data"]["clockRuleType"]
            self.post_state = resp["data"]["postInfo"]["state"]
            self.is_sign_in = bool(resp["data"]["clockInfo"]["inTime"])
            self.is_sign_out = bool(resp["data"]["clockInfo"]["outTime"])
            if not self.train_init:
                self.logger.info(f"实习类型：{'自主' if self.train_type else '集中'}，实习定位：{'有' if self.post_state else '无'}")
                if self.post_state:
                    if self.sign_lat and self.sign_lng:
                        self.logger.warning(f"配置了一个有效的签到坐标{self.sign_lat}, {self.sign_lng}，将不再使用实习坐标")
                    else:
                        self.sign_lat = resp["data"]["postInfo"]["lat"]
                        self.sign_lng = resp["data"]["postInfo"]["lng"]
                        self.logger.info(f"将使用获取到的实习坐标：{self.sign_lat}, {self.sign_lng}")
            self.logger.info(
                f"考勤状态：Sign in[{'√' if self.is_sign_in else 'x'}] || Sign out[{'√' if self.is_sign_out else 'x'}]")
            if not self.sign_lat:
                self._request_error("无定位信息，请按照文档手动添加签到定位信息")
            self.train_init = True
        else:
            self._request_error("无法加载实习信息", resp)

    def get_ip(self) -> str:
        """获得请求IP"""
        self.session.headers.update(self.sign_header({}))
        resp = self.session.get(url=XybSign.URL_IP)
        resp = self._except_json_resp(resp)
        if resp["code"] == "200":
            return resp["data"]["ip"]
        else:
            self._request_error(f"无法获得本机IP", resp)

    def sign_behavior(self):
        """签到行为记录(目前已弃用)"""
        data = {
            'login': 1,
            'appVersion': '1.5.75',
            'operatingSystemVersion': 10,
            'deviceModel': 'microsoft',
            'operatingSystem': 'android',
            'screenWidth': 415,
            'screenHeight': 692,
            'reportSrc': '2',
            'eventTime': int(time.time()),
            'eventType': 'click',
            'eventName': 'clickSignEvent',
            'clientIP': self.get_ip(),
            'pageId': 30,
            'itemID': 'none',
            'itemType': '其他',
            'stayTime': 'none',
            'deviceToken': self.open_id,
            'netType': 'WIFI',
            'app': 'wx_student',
            'preferName': '成长',
            'pageName': '成长-签到',
            'userName': self.user_name,
            'userId': self.loginer_id,
            'province': self.location['province'],
            'country': self.location['country'],
            'city': self.location['city']
        }
        self.session.headers.update(self.sign_header(data))
        resp = self.session.post(url=XybSign.URL_BEHAVIOR, data=data)
        resp = self._except_json_resp(resp)
        if resp["code"] != "200":
            self._request_error("发送签到信息失败", resp)

    def _prepare_sign(self, status: int) -> dict:
        """
        签到前准备，包括行为记录(已停用)和构建数据

        :param status: 签到/签出类型(1签出2签到)
        :return: 构建好的签到数据
        """
        # self.sign_behavior()
        return {
            'traineeId': self.train_id,
            'adcode': self.location['adcode'],
            'lat': self.sign_lat,
            'lng': self.sign_lng,
            'address': self.location['address'],
            'deviceName': 'microsoft',
            'punchInStatus': 1,
            'clockStatus': status,
            'imgUrl': '',
            'reason': ""
        }

    def auto_sign(self, status: int):
        """
        签到签退自动触发型记录逻辑，非特殊不要直接使用

        自动签到逻辑下，仅有未签到记录时才会自动签到，其余情况不会修改记录

        :param status: 签到/签出类型(1签出2签到)
        """
        if status not in (1, 2):
            raise RuntimeError(f"传入的签到类型错误:{status}")
        data = self._prepare_sign(status)
        self.session.headers.update(self.sign_header(data))
        resp = self.session.post(url=XybSign.URL_AUTO_CLOCK, data=data)
        resp = self._except_json_resp(resp)
        self.load_train_info()
        if resp["code"] != "200":
            self._request_error(f"无法进行【自动】{['签退', '签到'][status - 1]}", resp)

    def new_sign(self, status: int):
        """
        签到签退追加型记录逻辑，非特殊不要直接使用

        会直接追加新的签到记录，新的记录可以是签到或者签退

        :param status: 签到/签出类型(1签出2签到)
        """
        if status not in (1, 2):
            raise RuntimeError(f"传入的签到类型错误:{status}")
        data = self._prepare_sign(status)
        self.session.headers.update(self.sign_header(data))
        resp = self.session.post(url=XybSign.URL_NEW_CLOCK, data=data)
        resp = self._except_json_resp(resp)
        self.load_train_info()
        if resp["code"] != "200":
            self._request_error(f"无法进行【新增】{['签退', '签到'][status - 1]}", resp)

    def update_sign(self, status: int):
        """
        签到签退更新型记录逻辑，非特殊不要直接使用

        更新最近的签到/签退记录，已有签退记录时无法更新之前的签到记录

        :param status: 签到/签出类型(1签出2签到)
        """
        if status not in (1, 2):
            raise RuntimeError(f"传入的签到类型错误:{status}")
        data = self._prepare_sign(status)
        self.session.headers.update(self.sign_header(data))
        resp = self.session.post(url=XybSign.URL_UPDATE_CLOCK, data=data)
        resp = self._except_json_resp(resp)
        self.load_train_info()
        if resp["code"] != "200":
            self._request_error(f"无法进行【覆盖】{['签退', '签到'][status - 1]}", resp)

    def sign_in(self, overwrite=False) -> bool:
        """
        签到

        :param overwrite: 已经签到时是否覆盖
        :return 签到结果
        """
        if self.is_sign_in:
            if overwrite:
                if not self.is_sign_out:
                    self.update_sign(2)
                    self.logger.info("签到完成：覆盖模式")
                    return True
                else:
                    self.logger.error("已签退，无法进行签到")
                    return False
            else:
                self.logger.warning("已经进行过签到，本次操作未进行...")
                return False
        else:
            self.auto_sign(2)
            self.logger.info("签到完成：自动触发模式")
            return True

    def sign_out(self, overwrite=False) -> bool:
        """
        签退

        :param overwrite: 已经签退时是否覆盖
        :return 签退结果
        """
        if self.is_sign_in:
            if self.is_sign_out:
                if overwrite:
                    self.update_sign(1)
                    self.logger.info("签退完成：覆盖模式")
                    return True
                else:
                    self.logger.warning("已经进行过签退，本次操作未进行...")
                    return False
            else:
                self.new_sign(1)
                self.logger.info("签退完成：新增记录模式")
                return True
        else:
            self.logger.error("无法进行签退，必须先进行签到操作")
            return False


class XybSign:
    URL_LOGIN_PHONE = "https://xcx.xybsyw.com/login/login.action"
    URL_LOGIN_WX = "https://xcx.xybsyw.com/login/login!wx.action"
    URL_ACCOUNT = "https://xcx.xybsyw.com/account/LoadAccountInfo.action"
    URL_IP = "https://xcx.xybsyw.com/behavior/Duration!getIp.action"
    URL_TRAIN = "https://xcx.xybsyw.com/student/clock/GetPlan!getDefault.action"
    URL_TRAIN_INFO = "https://xcx.xybsyw.com/student/clock/GetPlan!detail.action"
    URL_BEHAVIOR = "https://app.xybsyw.com/behavior/Duration.action"
    URL_AUTO_CLOCK = "https://xcx.xybsyw.com/student/clock/Post!autoClock.action"
    URL_NEW_CLOCK = "https://xcx.xybsyw.com/student/clock/PostNew.action"
    URL_UPDATE_CLOCK = "https://xcx.xybsyw.com/student/clock/Post!updateClock.action"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36 MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat",
        "content-type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate"
    }

    def __init__(self, file="accounts.json"):
        self.logger = logging.Logger("XybSign", logging.INFO)
        init_logger(self.logger)
        with open(file, encoding="utf-8") as fp:
            accounts = json.load(fp)
        self._accounts = list()
        for acc in accounts:
            try:
                self._accounts.append(XybAccount(**acc))
            except Exception as err:
                self.logger.error("载入账户时出现异常")
                self.logger.exception(err)
        self.logger.info(f"已载入 {len(self._accounts)} 个账号")

    def get_accounts(self) -> Tuple[XybAccount]:
        """获得账户OpenId列表，便于后续的登录操作"""
        return tuple(self._accounts)

    def _batch_task(self, sign_type: bool, *args):
        """
        批量任务

        :param sign_type: 签到/签出类型
        :param args: 任务参数
        """
        counter = Counter()
        webhook_queue = list()
        for acc in self.get_accounts():
            task_result = False
            try:
                ret = acc.sign_in(*args) if sign_type else acc.sign_out(*args)
            except RuntimeError as err:
                self.logger.error("签到/退失败")
                self.logger.exception(err)
                counter.update((False,))
            else:
                counter.update((ret,))
                task_result = ret
            finally:
                webhook_data = {
                    "openid": acc.open_id,
                    "username": acc.account,
                    "loginer_id": acc.loginer_id,
                    "name": acc.user_name,
                    "phone": acc.phone,
                    "train_type": bool(acc.train_type),
                    "train_id": acc.train_id,
                    "post_type": bool(acc.post_state),
                    "sign_type": sign_type,
                    "result": task_result,
                    "is_sign_in": acc.is_sign_in,
                    "is_sign_out": acc.is_sign_out
                }
                webhook_queue.append(webhook_data)
        self.logger.info(f"任务结束，{counter[True]}(成功) / {counter[False]}(失败)")
        self.webhook(sign_type, webhook_queue)

    def webhook(self, sign_type: bool, hook_data: list):
        """
        批量任务通知回调

        :param sign_type: 签到/签出类型
        :param hook_data: 回调数据
        """

        counter = Counter()
        for data in hook_data:
            try:
                on_sign_in(data) if sign_type else on_sign_out(data)
                counter.update((True,))
            except Exception as err:
                self.logger.error("调用Webhook时出现异常")
                self.logger.exception(err)
                counter.update((False,))
        self.logger.info(f"Webhooks: {len(hook_data)} || {counter[True]}(完成) / {counter[False]}(失败)")

    def sign_in_all(self, overwrite=False):
        """
        批量签到

        :param overwrite: 已经签到时是否覆盖
        """
        self.logger.info(f"开始批量签到 {len(self._accounts)} 个账户")
        self._batch_task(True, overwrite)

    def sign_out_all(self, overwrite=False):
        """
        批量签退

        :param overwrite: 已经签退时是否覆盖
        """
        self.logger.info(f"开始批量签退 {len(self._accounts)} 个账户")
        self._batch_task(False, overwrite)


if __name__ == '__main__':
    xyb = XybSign()
    xyb.sign_in_all()
