# Tencent cloud SCF function

from xyb import XybSign


def main_handler(event, context):
    sign_type = ("SignOut", "SignIn")
    if "TriggerName" in event and event["TriggerName"] in sign_type:
        tools = XybSign()
        tools.sign_in_all(True) if sign_type.index(event["TriggerName"]) else tools.sign_out_all(True)
    else:
        raise RuntimeError("触发器配置不正确，请参考配置说明")
