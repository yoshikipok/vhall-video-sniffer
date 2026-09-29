#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微吼(Vhall)直播间视频地址嗅探

用法:
    python vhall_sniff.py <webinar_id> [页面域名]
    python vhall_sniff.py 588693136 hexun.vhall.homeway.com.cn
    python vhall_sniff.py 588693136 example.vhall.com --json   # 输出 JSON,方便管道处理

参数:
    webinar_id  直播间 ID,即观看页 URL 末尾的数字
    domain      页面所在域名(默认 e.vhall.com;私有化/定制部署必须显式传入)

三步拿到可播放地址:
    1) POST https://<domain>/v3/webinars/watch/init
       取 paas_app_id / paas_access_token / third_party_user_id / paas_record_id
    2) POST https://api.vhallyun.com/sdk/v2/demand/get-record-watch-info
       取 m3u8 列表与原始 token
    3) token 变换: CRC32(reverse(token 首段)) 转大写16进制 + "_" + 尾段

纯 Python 标准库,无需 pip install,Python 3.6+ 可直接运行。
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
import zlib

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

PAAS_API = "https://api.vhallyun.com/sdk"

# 以下两个值硬编码在微吼播放器 SDK 的 _createStore() 里,是写死的常量,不能改
CLIENT = "pc_browser"
PACKAGE_CHECK = "peter"


def _post(url, data=None, headers=None, json_body=None, timeout=30):
    """统一 POST: 传 json_body 走 JSON,否则走 form-urlencoded"""
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        ctype = "application/json"
    else:
        body = urllib.parse.urlencode(data).encode("utf-8")
        ctype = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": ctype,
        "User-Agent": UA,
        **(headers or {}),
    })
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def convert_token(origin_token):
    """播放器 SDK 的 Token.create(): 反转首段 -> CRC32 -> 大写16进制,再拼回尾段"""
    head, tail = origin_token.split("_", 1)
    crc = zlib.crc32(head[::-1].encode("utf-8")) & 0xFFFFFFFF
    return "{:X}_{}".format(crc, tail)


def sniff(webinar_id, domain="e.vhall.com", verbose=True):
    hdr = {"Origin": "https://" + domain,
           "Referer": "https://{}/v3/lives/watch/{}".format(domain, webinar_id)}

    # 第一步: 房间初始化
    init = _post("https://{}/v3/webinars/watch/init".format(domain),
                 json_body={"webinar_id": str(webinar_id), "clientType": "web",
                            "live_type": 0, "stealth": 0}, headers=hdr)
    if init.get("code") != 200:
        raise RuntimeError("init 失败: " + json.dumps(init, ensure_ascii=False)[:300])

    d = init["data"]
    interact, record = d["interact"], d["record"]
    join_id = d["join_info"]["third_party_user_id"]

    if verbose:
        print("直播主题: {}".format(d["webinar"]["subject"]))
        print("直播时间: {} ~ {}".format(d["webinar"]["start_time"],
                                         d["webinar"]["end_time"]))

    # 第二步: 取回放地址
    # 直播进行中要改用 /v2/room/get-watch-info 并传 room_id=interact["room_id"]
    vod = _post(PAAS_API + "/v2/demand/get-record-watch-info", data={
        "app_id": interact["paas_app_id"],
        "access_token": interact["paas_access_token"],
        "third_party_user_id": join_id,
        "client": CLIENT,
        "package_check": PACKAGE_CHECK,
        "record_id": record["paas_record_id"],
    }, headers=hdr)
    if vod.get("code") != 200:
        raise RuntimeError("取流失败: " + json.dumps(vod, ensure_ascii=False)[:300])

    server = vod["data"]["default_server"]
    token = convert_token(server["token"])

    result = {
        "webinar_id": webinar_id,
        "domain": domain,
        "subject": d["webinar"]["subject"],
        "start_time": d["webinar"]["start_time"],
        "end_time": d["webinar"]["end_time"],
        "token_expire": server.get("expired_datetime"),
        "urls": [{"line": c["line"], "cdn": c["cdn_name"],
                  "url": "{}?token={}".format(c["hls_domainname"], token)}
                 for c in server["hls_domainnames"]],
    }

    if verbose:
        print("\n有效期至: {}\n".format(result["token_expire"]))
        for u in result["urls"]:
            print("[{} / {}]".format(u["line"], u["cdn"]))
            print(u["url"])
            print()
    return result


def main():
    ap = argparse.ArgumentParser(description="微吼直播间视频地址嗅探")
    ap.add_argument("webinar_id", help="直播间 ID(URL 末尾的数字)")
    ap.add_argument("domain", nargs="?", default="e.vhall.com",
                    help="页面域名,私有化部署必填")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--line", default=None, help="只输出指定线路,如 '线路1'")
    args = ap.parse_args()

    try:
        r = sniff(args.webinar_id, args.domain, verbose=not args.json)
    except Exception as e:
        sys.stderr.write("错误: {}\n".format(e))
        return 1

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.line:
        for u in r["urls"]:
            if u["line"] == args.line:
                print(u["url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
