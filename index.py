# 导入标准库
import traceback
import time
import sys
import logging
import codecs
import os
# 环境变量初始化
try:
    print("==========脚本开始初始化==========")
except UnicodeEncodeError:
    # 设置默认输出编码为utf-8, 但是会影响腾讯云函数日志输出。
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    print("==========脚本开始初始化(utf-8输出)==========")
absScriptDir = os.path.dirname(os.path.abspath(__file__))
os.chdir(absScriptDir)  # 将工作路径设置为脚本位置
if os.name == "posix":
    # 如果是linux系统, 增加TZ环境变量
    os.environ['TZ'] = "Asia/Shanghai"
# 将脚本路径加入模块搜索路径
sys.path.append(absScriptDir)
# 将stdout设为logging模块的输出
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
# 导入其他模块
if True:
    from xyb import XybSign, XybAccount
    from utils import TextData, TimeTools, LiteLog, SendMessage, FileOut


def loadConfig():
    '''载入配置'''
    config = TextData.loadJson("accounts.json")
    for u in config["users"]:
        u: dict
        u.setdefault("remarkname", "李华LiHua(默认备注名)")
        # 任务流程控制(是否成功, 执行时间范围)
        for i in ("signIn", "signOut"):
            u.setdefault(i, {})
            u[i].setdefault("time", "1-7 1-12 1-31 0-23 0-59")
            u[i].setdefault("overwrite", True)
            u[i]["success"] = False
            u[i]["inTime"] = TimeTools.isInTimeList(u[i]["time"])
    return config


def main():
    config = loadConfig()
    users = config["users"]
    # 任务执行
    for u in users:
        try:
            needSignIn = u["signIn"]["inTime"] and not u["signIn"]["success"]
            needSignOut = u["signOut"]["inTime"] and not u["signOut"]["success"]
            if needSignIn or needSignOut:
                LiteLog.log(1, f"即将为「{u['remarkname']}」执行任务")
                LiteLog.log(1, "正在暂停5妙")
                time.sleep(5)
                xybUser = XybAccount(**u)
            # 签到
            if needSignIn:
                LiteLog.log(1, f"即将为「{u['remarkname']}」签到")
                xybUser.sign_in(u["signIn"]["overwrite"])
                u["signIn"]["success"] = xybUser.is_sign_in
            # 签退
            if needSignOut:
                LiteLog.log(1, f"即将为「{u['remarkname']}」签退")
                xybUser.sign_out(u["signOut"]["overwrite"])
                u["signOut"]["success"] = xybUser.is_sign_out
        except RuntimeError as e:
            msg = f"[{e}]\n{traceback.format_exc()}"
            LiteLog.log(1, msg)

    # 全局消息整合
    signIn_task = sum(((1 if i["signIn"]["inTime"] else 0) for i in users))
    signIn_succ = sum(((1 if i["signIn"]["success"] else 0) for i in users))
    signOut_task = sum(((1 if i["signOut"]["inTime"] else 0) for i in users))
    signOut_succ = sum(((1 if i["signOut"]["success"] else 0) for i in users))

    title = f"校友邦签到(签到: ({signIn_succ}/{signIn_task})|签退: ({signOut_succ}/{signOut_task}))"
    msg = ""
    for u in users:
        u: dict
        signInStatus = ("+++成功+++" if u["signIn"]["success"]
                        else "---失败---") if u["signIn"]["inTime"] else "   跳过   "
        signOutStatus = ("+++成功+++" if u["signOut"]["success"]
                         else "---失败---") if u["signOut"]["inTime"] else "   跳过   "
        msg += f"「{u['remarkname']}」\n签到: {signInStatus}|签退: {signOutStatus}\n"
    LiteLog.log(1, msg)
    # 消息推送
    LiteLog.log(1, "即将进行消息推送")
    sm = SendMessage(config.get('sendMessage'))
    sm.send(msg, title, ((sys.stdout.log.encode(
        encoding='utf-8'), TimeTools.formatStartTime()+".txt"), ))
    LiteLog.log(1, '全局推送情况', sm.log_str)


def main_handler(event, context):
    sign_type = ("SignOut", "SignIn")
    if "TriggerName" in event and event["TriggerName"] in sign_type:
        tools = XybSign()
        tools.sign_in_all(True) if sign_type.index(
            event["TriggerName"]) else tools.sign_out_all(True)
    else:
        LiteLog.log(1, "触发器中没有SignIn/SignOut信息, 尝试使用配置中的SignIn/SignOut进行运作")
        # 替换stdout和stderr
        FileOut(None).start()
        main()


if __name__ == '__main__':
    # 替换stdout和stderr
    FileOut(TimeTools.formatStartTime(
        "log/日志#t=%Y-%m-%d--%H-%M-%S##.txt")).start()
    main()
