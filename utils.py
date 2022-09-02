# 导入标准库
from urllib import parse
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email.header import Header
from email.mime.text import MIMEText
import smtplib
import json
import os
import time
import re
import sys
from typing import Sequence
# 导入第三方库
import requests


class TextData:
    '''json读写'''
    @staticmethod
    def loadJson(jsonFile='data.json'):
        with open(jsonFile, 'r', encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def writeJson(item, jsonFile='data.json'):
        with open(jsonFile, 'w', encoding='utf-8') as f:
            json.dump(item, f)


class TimeTools:
    '''时间相关工具'''
    startTime = time.time()

    @staticmethod
    def formatStartTime(format: str = "%Y-%m-%d %H:%M:%S"):
        return time.strftime(format, time.localtime(TimeTools.startTime))

    @staticmethod
    def isInTimeList(timeRanges, nowTime: float = startTime):
        '''判断(在列表中)是否有时间限定字符串是否匹配时间
        :params timeRages: 时间限定字符串列表。
            :时间限定字符串是形如"1,2,3 1,2,3 1,2,3 1,2,3 1,2,3"形式的字符串。
            :其各位置代表"周(星期几) 月 日 时 分", 周/月/日皆以1开始。
            :可以以"2-5"形式代表时间范围。比如"3,4-6"就等于"3,4,5,6"
        :params nowTime: 时间戳
        :return bool: 在列表中是否有时间限定字符串匹配时间
        '''
        timeRanges = TimeTools.formatStrList(timeRanges)
        for i in timeRanges:
            if TimeTools.isInTime(i, nowTime):
                return True
            else:
                pass
        else:
            return False

    @staticmethod
    def isInTime(timeRange: str, nowTime: float = startTime):
        '''
        判断时间限定字符串是否匹配时间
        :params timeRage: 时间限定字符串。
            :是形如"1,2,3 1,2,3 1,2,3 1,2,3 1,2,3"形式的字符串。
            :其各位置代表"周(星期几) 月 日 时 分", 周/月/日皆以1开始。
            :可以以"2-5"形式代表时间范围。比如"3,4-6"就等于"3,4,5,6"
        :params nowTime: 时间戳
        :return bool: 时间限定字符串是否匹配时间
        '''
        # 判断类型
        if type(timeRange) != str:
            raise TypeError(
                f"timeRange(时间限定字符串)应该是字符串, 而不是『{type(timeRange)}』")
        # 判断格式
        if not re.match(r"^(?:\d+-?\d*(?:,\d+-?\d*)* ){4}(?:\d+-?\d*(?:,\d+-?\d*)*)$", timeRange):
            raise Exception(f'『{timeRange}』不是正确格式的时间限定字符串')
        # 将时间范围格式化

        def formating(m):
            '''匹配a-e样式的字符串替换为a,b,c,d,e样式'''
            a = int(m.group(1))
            b = int(m.group(2))
            if a > b:
                a, b = b, a
            return ','.join([str(i) for i in range(a, b)]+[str(b)])
        timeRange = re.sub(r"(\d*)-(\d*)", formating, timeRange)
        # 将字符串转为二维整数数组
        timeRange = timeRange.split(' ')
        timeRange = [[int(j) for j in i.split(',')] for i in timeRange]
        # 将当前时间格式化为"周 月 日 时 分"
        nowTime = tuple(time.localtime(nowTime))
        nowTime = (nowTime[6]+1, nowTime[1],
                   nowTime[2], nowTime[3], nowTime[4])
        for a, b in zip(nowTime, timeRange):
            if a not in b:
                return False
            else:
                pass
        else:
            return True

    @staticmethod
    def executionSeconds(round_: int = 2):
        return round(time.time()-TimeTools.startTime, round_)

    @staticmethod
    def formatStrList(item):
        '''字符串序列或字符串 格式化为 字符串列表。
        :feature: 超级字符串会被格式化为字符串
        :feature: 空值会被格式化为 空列表'''
        if isinstance(item, str):
            strList = [item]
        elif isinstance(item, Sequence):
            strList = list(item)
        elif not item:
            strList = []
        else:
            raise TypeError('请传入序列/字符串')
        for i, v in enumerate(strList):
            strList[i] = str(v)
        return strList


class LiteLog:
    '''小型日志模块'''
    prefix = 'main'
    startTime = TimeTools.startTime
    log_list = []
    printLevel = 0
    logTypeDisplay = ['debug', 'info', 'warn', 'error', 'critical']

    @staticmethod
    def formatLog(logType: str, args):
        '''返回logItem[时间,类型,内容]'''
        string = ''
        for item in args:
            if type(item) == dict or type(item) == list:
                string += yaml.dump(item, allow_unicode=True)+'\n'
            else:
                string += str(item)+'\n'
        return [time.time()-LiteLog.startTime, logType, string]

    @staticmethod
    def log2FormatStr(logItem):
        logType = LiteLog.logTypeDisplay[logItem[1]]
        return '|||%s|||%s|||%0.3fs|||\n%s' % (LiteLog.prefix, logType, logItem[0], logItem[2])

    @staticmethod
    def log(logType=1, *args):
        '''日志函数
        logType:int = debug:0|info:1|warn:2|error:3|critical:4'''
        if not args:
            return
        logItem = LiteLog.formatLog(logType, args)
        LiteLog.log_list.append(logItem)
        if logType >= LiteLog.printLevel:
            print(LiteLog.log2FormatStr(logItem))

    @staticmethod
    def getLog(level=0):
        '''获取日志函数'''
        string = ''
        for item in LiteLog.log_list:
            if level <= item[1]:
                string += LiteLog.log2FormatStr(item)
        return string

    @staticmethod
    def saveLog(dir, level=0):
        '''保存日志函数'''
        if type(dir) != str:
            return

        log = LiteLog.getLog(level)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        dir = os.path.join(dir, TimeTools.formatStartTime(
            "LOG#t=%Y-%m-%d--%H-%M-%S##.txt"))
        with open(dir, 'w', encoding='utf-8') as f:
            f.write(log)


class FileOut:
    '''
    代替stdout和stderr, 使print同时输出到文件和终端中。
    start()方法可以直接用自身(self)替换stdout和stderr
    close()方法可以还原stdout和stderr
    '''
    stdout = sys.stdout
    stderr = sys.stderr

    def __init__(self, logPath: str = None):
        '''
        初始化
        :params logDir: 输出文件(如果路径不存在自动创建), 如果为空则不输出到文件
        '''
        self.log = ""  # 同时将所有输出记录到log字符串中
        if logPath:
            logDir = os.path.dirname(os.path.abspath(logPath))
            if not os.path.isdir(logDir):
                os.makedirs(logDir)
            self.logFile = open(logPath, "w+", encoding="utf-8")
        else:
            self.logFile = None

    def start(self):
        '''开始替换stdout和stderr'''
        sys.stdout = self
        sys.stderr = self

    def write(self, str_):
        r'''
        :params str: print传来的字符串
        :print(s)等价于sys.stdout.write(s+"\n")
        '''
        str_ = str(str_)
        self.log += str_
        if self.logFile:
            self.logFile.write(str_)
        FileOut.stdout.write(str_)
        self.flush()

    def flush(self):
        '''刷新缓冲区'''
        self.stdout.flush()
        if self.logFile:
            self.logFile.flush()

    def close(self):
        '''关闭'''
        if self.logFile:
            self.logFile.close()
        self.log = ""
        sys.stdout = FileOut.stdout
        sys.stderr = FileOut.stderr


class SendMessage:
    '''消息推送'''

    def __init__(self, con: dict):
        if type(con) != dict:
            con = dict()
        self.qmsg = Qmsg(con.get('qmsg_key'), con.get(
            'qmsg_qq'), con.get('qmsg_isGroup'))
        self.smtp = Smtp(con.get('smtp_host'), con.get('smtp_user'),
                         con.get('smtp_key'), con.get('smtp_sender'),
                         con.get('smtp_senderName'), con.get('smtp_receivers'))
        self.pp = Pushplus(con.get('pushplus_parameters'),
                           con.get('pushplus_isNew'))
        self.log_str = '推送情况\n'

    def send(self, msg='no msg', title='no title', attachments=()):
        try:
            self.log_str += '\nQMSG酱|' + self.qmsg.send(msg)
        except Exception as e:
            self.log_str += '\nQMSG酱|出错|%s' % e
        try:
            self.log_str += '\nSMTP|' + \
                self.smtp.sendmail(msg, title, attachments)
        except Exception as e:
            self.log_str += '\nSMTP|出错|%s' % e
        try:
            self.log_str += '\nPushplus|' + self.pp.sendPushplus(msg, title)
        except Exception as e:
            self.log_str += '\nPushplus|出错|%s' % e


class Pushplus:
    '''Pushplus推送类'''

    def __init__(self, parameters: str, isNew):
        """
        :param parameters: "xxx"形式的令牌 或者 "token=xxx&topic=xxx&yyy=xxx"形式参数列表
        """
        self.parameters = parameters
        if isNew:
            self.api = "https://www.pushplus.plus/send"
        else:
            self.api = "https://pushplus.hxtrip.com/send"
        self.configIsCorrect = self.isCorrectConfig()

    def isCorrectConfig(self):
        # 简单检查邮箱地址或API地址是否合法
        if not type(self.parameters) == str:
            return 0
        if not self.parameters:
            return 0
        return 1

    def sendPushplus(self, msg, title):
        msg = str(msg)
        msg = msg.replace("\n", "</br>")
        title = str(title)

        if self.configIsCorrect:
            # 解析参数
            if "=" in self.parameters:  # 如果是url形式的参数
                params = parse.parse_qs(
                    parse.urlparse(self.parameters).path)  # 解析参数
                params = {k: params.copy()[k][0]
                          for k in params.copy()}  # 解析参数
                params.update({'title': title, 'content': msg})
            else:  # 如果参数是token本身
                params = {
                    'token': self.parameters,
                    'title': title,
                    'content': msg,
                }
            # 准备发送
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0'
            }
            res = requests.post(
                self.api, headers=headers, params=params)
            if res.status_code == 200:
                return "发送成功"
            else:
                return "发送失败"
        else:
            return '无效配置'


class Qmsg:
    '''Qmsg发送类'''

    def __init__(self, key: str, qq: str, isGroup: bool = False):
        """
        :param key: qmsg密钥
        :param qq: 接收消息的qq(多个qq以","分隔)
        :param isGroup: 接收者是否为群
        """
        self.key = key
        self.qq = qq
        self.isGroup = isGroup
        self.configIsCorrect = self.isCorrectConfig()

    def isCorrectConfig(self):
        """简单检查配置是否合法"""
        if type(self.key) != str:
            return 0
        elif type(self.qq) != str:
            return 0
        elif not re.match('^[0-9a-f]{32}$', self.key):
            return 0
        elif not re.match('^\d+(,\d+)*$', self.qq):
            return 0
        else:
            return 1

    def send(self, msg):
        """发送消息
        :param msg: 要发送的消息(自动转为字符串类型)"""
        # msg处理
        msg = str(msg)
        # 替换数字(避开qmsg的屏蔽规则)
        for i, k in zip(list('0123456789'), list('𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗')):
            msg = msg.replace(i, k)
        # 简单检查配置
        if not self.configIsCorrect:
            return('无效配置')
        else:
            # 开始推送
            sendtype = 'group/' if self.isGroup else 'send/'
            res = requests.post(url='https://qmsg.zendee.cn/'+sendtype +
                                self.key, data={'msg': msg, 'qq': self.qq})
            return str(res)


class Smtp:
    '''Smtp发送类'''

    def __init__(self, host: str, user: str, key: str, sender: str, senderName: str, receivers: list):
        """
        :param host: SMTP的域名
        :param user: 用户名
        :param key: 用户的密钥
        :param sender: 邮件发送者(邮箱)
        :param receivers: 邮件接收者列表(邮箱)
        """
        self.host = host
        self.user = user
        self.key = key
        self.sender = sender
        self.senderName = senderName
        self.receivers = receivers
        self.configIsCorrect = self.isCorrectConfig()

    def isCorrectConfig(self):
        # 简单检查邮箱地址或API地址是否合法
        if type(self.receivers) != list:
            return 0
        for item in [self.host, self.user, self.key, self.sender]+self.receivers:
            if not type(item) == str:
                return 0
            if len(item) == 0:
                return 0
            if "*" in item:
                return 0
        return 1

    def sendmail(self, msg, title='no title', attachments=()):
        """发送邮件
        :param msg: 要发送的消息(自动转为字符串类型)
        :param title: 邮件标题(自动转为字符串类型)
        :param attachment: 附件元组，形式为((blob二进制文件,fileName文件名), (blob,fileName), ...)"""
        msg = str(msg)
        msg = msg.replace("\n", "<br>")
        title = str(title)
        if not self.configIsCorrect:
            return '无效配置'
        else:
            mail = MIMEMultipart()
            # 添加正文
            mail.attach(MIMEText(msg, 'html', 'utf-8'))
            # 添加标题
            mail['Subject'] = Header(title, 'utf-8')
            # 添加发送者
            mail['From'] = formataddr((self.senderName, self.sender), "utf-8")
            # 添加附件
            for attInfo in attachments:
                att = MIMEText(attInfo[0], 'base64', 'utf-8')
                att["Content-Type"] = 'application/octet-stream'
                att["Content-Disposition"] = f'attachment; filename="{attInfo[1]}"'
                mail.attach(att)
            # 发送邮件
            smtpObj = smtplib.SMTP_SSL(self.host, 465)
            smtpObj.login(self.user, self.key)
            smtpObj.sendmail(self.sender, self.receivers, mail.as_string())
            return("邮件发送成功")
