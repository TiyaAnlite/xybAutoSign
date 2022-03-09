import json
import logging
import time
from typing import Tuple
from collections import Counter

import requests

from webhooks import on_sign_in, on_sign_out


def init_logger(logger: logging.Logger, fmt="%(asctime)s - %(name)s - %(levelname)s: %(message)s"):
    # logger.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)


class XybAccount:
    def __init__(self, openid: str, unionid: str, location: dict):
        self.logger = logging.Logger("XybAccount", logging.INFO)
        init_logger(self.logger)
        self.session = requests.Session()
        self.session.headers = XybSign.HEADERS
        self.open_id = openid
        self.union_id = unionid
        self.location = location
        self.session_id = ""
        self.loginer_id = ""
        self.user_name = ""
        self.phone = ""
        self.train_id = ""
        self.sign_lat = 0
        self.sign_lng = 0
        self.is_sign_in = False
        self.is_sign_out = False
        self.login()
        self.load_user_info()
        self.load_train()
        self.load_train_info()

    def _request_error(self, msg: str, debug_data):
        self.logger.error(msg)
        self.logger.info(debug_data)
        raise RuntimeError(msg)

    def login(self):
        """执行登录，获得loginerId信息"""

        data = dict(
            openId=self.open_id,
            unionId=self.union_id
        )
        resp = self.session.post(url=XybSign.URL_LOGIN, data=data).json()
        if resp["code"] == "200":
            self.loginer_id = resp["data"]["loginerId"]
            self.session_id = resp["data"]["sessionId"]
            self.phone = resp["data"]["phone"]
            self.logger.info(f"Login susses: {self.loginer_id}")
        else:
            self._request_error(f"Login failed: {self.open_id}", resp)

    def load_user_info(self):
        """获得用户信息，取得userName"""

        # Loginer
        resp = self.session.get(url=XybSign.URL_ACCOUNT).json()
        if resp["code"] == "200":
            self.user_name = resp["data"]["loginer"]
            self.logger.name = f"XybAccount[{self.user_name}]"
            self.logger.info("Login ok")
        else:
            self._request_error(f"Get account info error: {self.open_id}", resp)

    def load_train(self):
        """获得train信息"""

        # TrainId
        resp = self.session.get(url=XybSign.URL_TRAIN).json()
        if resp["code"] == "200":
            if "clockVo" in resp["data"]:
                self.train_id = resp["data"]["clockVo"]["traineeId"]
                self.logger.info(
                    f"Loaded train plan: {resp['data']['clockVo']['planName']}({resp['data']['clockVo']['startDate']} - {resp['data']['clockVo']['endDate']})")
            else:
                self._request_error("No default plan", resp["data"])
        else:
            self._request_error("Failed to load train", resp)

    def load_train_info(self):
        """获得train详情"""

        # TrainInfo
        resp = self.session.post(url=XybSign.URL_TRAIN_INFO, data=dict(traineeId=self.train_id)).json()
        if resp["code"] == "200":
            self.sign_lat = resp["data"]["postInfo"]["lat"]
            self.sign_lng = resp["data"]["postInfo"]["lng"]
            self.is_sign_in = bool(resp["data"]["clockInfo"]["inTime"])
            self.is_sign_out = bool(resp["data"]["clockInfo"]["outTime"])
            self.logger.info(
                f"Loaded train info: Sign in[{'√' if self.is_sign_in else 'x'}] || Sign out[{'√' if self.is_sign_out else 'x'}]")
        else:
            self._request_error("Failed to load train info", resp)

    def get_ip(self) -> str:
        """获得请求IP"""
        resp = self.session.get(url=XybSign.URL_IP).json()
        if resp["code"] == "200":
            return resp["data"]["ip"]
        else:
            self._request_error(f"Failed to get IP", resp)

    def sign_behavior(self):
        """签到行为记录"""
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
        resp = self.session.post(url=XybSign.URL_BEHAVIOR, data=data).json()
        if resp["code"] != "200":
            self._request_error("Failed to send behavior", resp)

    def _prepare_sign(self, status: int) -> dict:
        """
        签到前准备，包括行为记录和构建数据
        :param status: 签到/签出类型(1签出2签到)
        :return: 构建好的签到数据
        """
        self.sign_behavior()
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
        resp = self.session.post(url=XybSign.URL_AUTO_CLOCK, data=self._prepare_sign(status)).json()
        self.load_train_info()
        if resp["code"] != "200":
            self._request_error(f"Failed to [AUTO]sign", resp)

    def new_sign(self, status: int):
        """
        签到签退追加型记录逻辑，非特殊不要直接使用
        会直接追加新的签到记录，新的记录可以是签到或者签退
        :param status: 签到/签出类型(1签出2签到)
        """
        resp = self.session.post(url=XybSign.URL_NEW_CLOCK, data=self._prepare_sign(status)).json()
        self.load_train_info()
        if resp["code"] != "200":
            self._request_error(f"Failed to [NEW]sign", resp)

    def update_sign(self, status: int):
        """
        签到签退更新型记录逻辑，非特殊不要直接使用
        更新最近的签到/签退记录，已有签退记录时无法更新之前的签到记录
        :param status: 签到/签出类型(1签出2签到)
        """
        resp = self.session.post(url=XybSign.URL_UPDATE_CLOCK, data=self._prepare_sign(status)).json()
        self.load_train_info()
        if resp["code"] != "200":
            self._request_error(f"Failed to [UPDATE]sign", resp)

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
                    self.logger.info("Sign in success(Overwrite mode)")
                    return True
                else:
                    self.logger.error("Cannot update sign in record, already sign out")
                    return False
            else:
                self.logger.warning("Sign in skip..")
                return False
        else:
            self.auto_sign(2)
            self.logger.info("Sign in success(Auto clock mode)")
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
                    self.logger.info("Sign out success(Overwrite mode)")
                    return True
                else:
                    self.logger.warning("Sign out skip..")
                    return False
            else:
                self.new_sign(1)
                self.logger.info("Sign out success(New append mode)")
                return True
        else:
            self.logger.error("Cannot sign out, must be sign in first")
            return False


class XybSign:
    URL_LOGIN = "https://xcx.xybsyw.com/login/login!wx.action"
    URL_ACCOUNT = "https://xcx.xybsyw.com/account/LoadAccountInfo.action"
    URL_IP = "https://xcx.xybsyw.com/behavior/Duration!getIp.action"
    URL_TRAIN = "https://xcx.xybsyw.com/student/clock/GetPlan!getDefault.action"
    URL_TRAIN_INFO = "https://xcx.xybsyw.com/student/clock/GetPlan!detail.action"
    URL_BEHAVIOR = "https://app.xybsyw.com/behavior/Duration.action"
    URL_AUTO_CLOCK = "https://xcx.xybsyw.com/student/clock/Post!autoClock.action"
    URL_NEW_CLOCK = "https://xcx.xybsyw.com/student/clock/PostNew.action"
    URL_UPDATE_CLOCK = "https://xcx.xybsyw.com/student/clock/PostNew!updateClock.action"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36 MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat",
        "content-type": "application/x-www-form-urlencoded"
    }

    def __init__(self, file="accounts.json"):
        self.logger = logging.Logger("XybSign", logging.INFO)
        init_logger(self.logger)
        with open(file, encoding="utf-8") as fp:
            accounts = json.load(fp)
        self.accounts = dict()
        for acc in accounts:
            try:
                self.accounts[acc["openid"]] = XybAccount(**acc)
            except Exception as err:
                self.logger.error("Error in preload")
                self.logger.exception(err)
        self.logger.info(f"Loaded {len(self.accounts)} account(s)")

    def get_accounts(self) -> Tuple[XybAccount]:
        """获得账户OpenId列表，便于后续的登录操作"""
        return tuple(self.accounts.values())

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
                self.logger.error("Sign in/out error")
                self.logger.exception(err)
                counter.update((False,))
            else:
                counter.update((ret,))
                task_result = ret
            finally:
                webhook_data = {
                    "openid": acc.open_id,
                    "loginer_id": acc.loginer_id,
                    "name": acc.user_name,
                    "phone": acc.phone,
                    "train_id": acc.train_id,
                    "sign_type": sign_type,
                    "result": task_result,
                    "is_sign_in": acc.is_sign_in,
                    "is_sign_out": acc.is_sign_out
                }
                webhook_queue.append(webhook_data)
        self.logger.info(f"Task end. {counter[True]}(Success) / {counter[False]}(Failed)")
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
                self.logger.error("Error in webhook")
                self.logger.exception(err)
                counter.update((False,))
        self.logger.info(f"Webhooks: {len(hook_data)} || {counter[True]}(Done) / {counter[False]}(Error)")

    def sign_in_all(self, overwrite=False):
        """
        批量签到
        :param overwrite: 已经签到时是否覆盖
        """
        self.logger.info(f"Start to sign in {len(self.accounts)} account(s)")
        self._batch_task(True, overwrite)

    def sign_out_all(self, overwrite=False):
        """
        批量签退
        :param overwrite: 已经签退时是否覆盖
        """
        self.logger.info(f"Start to sign out {len(self.accounts)} account(s)")
        self._batch_task(False, overwrite)


if __name__ == '__main__':
    xyb = XybSign()
    xyb.sign_in_all()
