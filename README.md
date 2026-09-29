# vhall-video-sniffer

嗅探微吼（Vhall）直播/回放页面的**真实视频地址**（m3u8），拿到后可直接用 ffmpeg 下载。
一个 WorkBuddy Agent Skill，同时也是可直接运行的独立脚本。

支持任意微吼观看页，包括私有化 / 定制域名部署（如 `xxx.vhall.homeway.com.cn`）。

## 安装

作为 WorkBuddy 技能安装：

```bash
git clone https://github.com/yoshikipok/vhall-video-sniffer.git \
  ~/.workbuddy/skills/vhall-video-sniffer
```

Windows（PowerShell）：

```powershell
git clone https://github.com/yoshikipok/vhall-video-sniffer.git `
  $env:USERPROFILE\.workbuddy\skills\vhall-video-sniffer
```

只想用脚本、不装技能：直接下载 `vhall_sniff.py` 即可，无依赖。

## 用法

观看页 URL 形如：

```
https://hexun.vhall.homeway.com.cn/v3/lives/watch/588693136
                                                  ^^^^^^^^^ webinar_id
```

```bash
python vhall_sniff.py <webinar_id> <页面域名>
python vhall_sniff.py 588693136 hexun.vhall.homeway.com.cn
```

输出：

```
直播主题: 实战班缠论专属系列课
直播时间: 2026-03-06 15:30:00 ~ 2026-03-06 16:28:32

有效期至: 2026-10-06 20:58:06

[线路1 / tx]
https://tehlsvodhls02.vhallyun.com/.../record.m3u8?token=XXXX_YYYY

[线路2 / bd]
https://bdhlsvodhls02.vhallyun.com/.../record.m3u8?token=XXXX_YYYY
```

其他参数：

| 参数 | 说明 |
|---|---|
| `--json` | 输出结构化 JSON，方便脚本处理 |
| `--line 线路1` | 只输出指定线路的 URL，便于管道传给 ffmpeg |

### 下载视频

```bash
URL=$(python vhall_sniff.py <id> <domain> --line 线路1 | tr -d '\r\n ')
ffmpeg -y -i "$URL" -c copy -bsf:a aac_adtstoasc -movflags +faststart "输出.mp4"
```

`-c copy` 不重新编码，实测 57 分钟视频 43 秒下完。

> **坑**：务必用 `tr -d '\r\n '` 去掉 URL 尾随空白，否则 CDN 返回 `403 Forbidden`。

机器上没装 ffmpeg 时，优先找本机已有的（不必重新下载）：
- Windows 剪映：`E:\Program Files\JianyingPro\<版本>\ffmpeg.exe`
- 格式工厂绿色版目录下也有

## 工作原理

微吼观看页是纯 SPA，HTML 里没有任何视频信息。真实地址藏在三步接口调用里：

1. `POST https://<domain>/v3/webinars/watch/init` → 拿到 PaaS 的 `app_id` / `access_token` / `record_id`
2. `POST https://api.vhallyun.com/sdk/v2/demand/get-record-watch-info` → 拿到 m3u8 列表和原始 token
3. **token 变换**：`CRC32(reverse(token 首段))` 转大写 16 进制后拼回尾段，得到真正的播放 token

第 3 步是关键——直接用接口返回的 token 或不带 token 访问 m3u8，都是 `403 Access Denied`。
另外两个常量 `client=pc_browser`、`package_check=peter` 硬编码在播放器 SDK 里，填错会报「客户端类型错误」。

接口一旦改版怎么重新挖，`SKILL.md` 里有完整排查路径。

## 常见问题

| 现象 | 原因 |
|---|---|
| `404 Route Not Found` | URL 少了 `/sdk` 前缀 |
| `40001 客户端类型错误` | `client` 不是 `pc_browser` |
| `10005 SDK鉴权信息不能为空` | `package_check` 没传 |
| m3u8 `403 Access Denied` | token 没变换 / URL 带空格 / token 已过 7 天 |
| init 返回非 200 | 需登录、白名单或付费 |

## 免责声明

仅供学习研究与个人备份自己有权观看的内容使用。请尊重内容版权与平台服务条款，不要分发他人的付费课程。

## License

MIT
