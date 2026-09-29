---
name: vhall-video-sniffer
description: 嗅探微吼(Vhall)直播/回放页面的真实视频地址(m3u8)。当用户给出 vhall / e.vhall.com / *.vhall.* 之类的直播间 URL(形如 /v3/lives/watch/<id>)，并要求"拿视频地址、下载、嗅探、抓源、录下来"时使用。
agent_created: true
version: 1.0.0
---

# 微吼视频地址嗅探

## 何时用

用户给一个微吼观看页 URL(如 `https://xxx.vhall.homeway.com.cn/v3/lives/watch/588693136`)，想要里面的视频源地址或直接下载。

## 快速执行

直接用脚本，别再从零分析 JS：

```bash
python vhall_sniff.py <webinar_id> <页面域名>
# 例:python vhall_sniff.py 588693136 hexun.vhall.homeway.com.cn
```

- `webinar_id` = URL 末尾那串数字
- `domain` = URL 的 host（微吼私有化/定制部署各有自己的域名，必须显式传，不能默认 e.vhall.com）
- 纯 Python 标准库，无需 pip install
- `--json` 输出结构化结果；`--line 线路1` 只输出单条 URL 便于管道

输出两条线路(腾讯 tx / 百度 bd)的 `record.m3u8?token=...`，**token 有效期 7 天**。

## 下载视频

```bash
URL=$(python vhall_sniff.py <id> <domain> --line 线路1 | tr -d '\r\n ')
ffmpeg -y -i "$URL" -c copy -bsf:a aac_adtstoasc -movflags +faststart "输出.mp4"
```

- `-c copy` 不重编码，速度快（实测 57 分钟视频 43 秒下完）
- **必须 `tr -d '\r\n '` 去掉尾随空白**，否则 CDN 返回 403 Forbidden
- 机器上没有 ffmpeg 时，优先找本机已有的：
  - Windows 剪映：`E:\Program Files\JianyingPro\<版本>\ffmpeg.exe`
  - 格式工厂绿色版
  - 部分网络受限环境无法从外网下载 ffmpeg，别在这上面浪费时间

## 原理三步（脚本失效时按此手工排查）

1. **房间初始化** `POST https://<domain>/v3/webinars/watch/init`
   body(JSON)：`{"webinar_id":"<id>","clientType":"web","live_type":0,"stealth":0}`
   取：`data.interact.paas_app_id`、`data.interact.paas_access_token`、`data.interact.room_id`、`data.join_info.third_party_user_id`、`data.record.paas_record_id`
2. **取流**（form 表单 POST，不是 JSON）
   回放：`https://api.vhallyun.com/sdk/v2/demand/get-record-watch-info` + `record_id`
   直播中：`https://api.vhallyun.com/sdk/v2/room/get-watch-info` + `room_id`
   必填参数：`app_id` `access_token` `third_party_user_id` `client` `package_check`
3. **token 变换**（播放器 SDK 的 `Token.create()`）
   `newToken = CRC32(reverse(token.split("_")[0]))` 转大写 16 进制 + `"_"` + 尾段
   最终 `hls_domainname + "?token=" + newToken`

Python 一行：`"{:X}_{}".format(zlib.crc32(head[::-1].encode()) & 0xFFFFFFFF, tail)`

## 硬编码常量（关键，错一个就失败）

- `client = pc_browser`（填 pc/h5/web 都报「客户端类型错误」40001）
- `package_check = peter`
- 二者来自播放器 SDK `_createStore()`，是写死的常量而非业务数据

## 排错表

| 现象 | 原因 |
|---|---|
| `404 Route Not Found` | URL 少了 `/sdk` 前缀 |
| `40001 客户端类型错误` | client 不是 `pc_browser` |
| `10005 SDK鉴权信息不能为空` | package_check 没传 |
| m3u8 `403 Access Denied` | token 没做 CRC32 变换，或用了原始 token，或 URL 带尾随空格 |
| init 返回非 200 | 直播需登录/白名单/付费，返回体里的 `code` 会指明原因 |
| 明明是直播却拿到回放地址 | 直播已结束；进行中的直播要用 `get-watch-info` |

## 挖掘新版本接口的方法

微吼是 SPA，页面 HTML 里没有任何数据。改版后接口变了就按这条路重新找：

1. 抓页面 HTML，取入口 JS：`//cnstatic01.e.vhall.com/common-static/saas-watch/static/js/index.<hash>.js`
2. 入口 JS 里搜 `static/js/` 附近的 webpack chunk 映射表，拿到 `LiveRoom.<hash>.js`
3. 业务 chunk 里找 `new Domain({...initRoom:{webinar_id...}})`，具体接口名在 `middle-domain.js` 里
4. 真正取流在播放器 SDK：`https://static.vhallyun.com/jssdk/vhall-jssdk-player/<ver>/vhall-jssdk-player-<ver>.js`
   搜 `/v2/` 路径常量与 `urljoin("//api.vhallyun.com/sdk", x)`
5. PaaS API baseURL 常量：`{production:"//api.vhallyun.com", test:"//test01-api.vhallyun.com"}`

注意：微吼域名下所有路径都是 SPA fallback（任意路径都返回 200 的 index.html），靠枚举路径探测接口无效。

## 环境注意

- Windows 上 Bash 工具需要 `dangerouslyDisableSandbox: true`；PowerShell 工具可能不可用
- `agent-browser` 首次 open 可能卡住数分钟，纯静态分析通常更快；若用了记得 `agent-browser close --all`

## 合规提醒

仅用于下载自己有权限观看的内容（自己购买/自己主持/已授权的课程），尊重版权与平台条款，勿用于分发他人付费内容。
