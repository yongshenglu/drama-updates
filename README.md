# 剧集更新表

汇总国内四大视频平台（爱奇艺、优酷、腾讯视频、芒果TV）正在热播剧集的更新情况，
生成一个可在手机上直接查看的看板。

- **看板地址**：https://yongshenglu.github.io/drama-updates/
- **更新频率**：每天北京时间 09:07 自动采集并部署

## 看板功能

- 按平台分组，可点击平台标签快速切换
- 按状态筛选：全部 / 连载中 / 已完结
- 连载中的剧集置顶，显示更新到第几集
- 每张卡片可直接点击「播放」跳转到对应平台
- 腾讯视频额外提供精确到集的更新时间和更新计划

## 数据说明

| 平台 | 数据来源 | 可用信息 |
|------|---------|---------|
| 腾讯视频 | 频道页 JSON 接口 | 剧名、更新至第几集、精确更新时间、更新计划 |
| 优酷 | 频道页内嵌 SSR 数据 | 剧名、集数、更新状态 |
| 爱奇艺 | 频道页渲染后的 DOM | 剧名、集数、副标题 |
| 芒果TV | 频道页渲染后的 DOM | 剧名、集数、副标题 |

各平台的「集数」口径略有差异（有的标注「更新至X集」，有的标注「X集全」），
看板统一解析为「连载中 / 已完结」状态并保留原始文案。

## 本地运行

```bash
pip install -r requirements.txt
python main.py
```

生成的看板在 `output/latest.html`，直接用浏览器打开即可。

常用参数：

```bash
python main.py --platform youku,tencent   # 只采集指定平台
python main.py --out report.html          # 指定输出路径
python main.py --json                     # 同时输出 JSON 数据
```

爱奇艺和芒果TV 的剧集列表由前端渲染，需要本机装有 Chrome 或 Edge；
脚本会自动查找浏览器，也可通过环境变量 `BROWSER_PATH` 指定。

## 项目结构

```
main.py              入口：采集 + 生成看板
render.py            数据 -> HTML 看板
collector/
  models.py          Drama 数据模型与集数解析
  http.py            HTTP 请求 + 轻量 HTML DOM 解析
  browser.py         浏览器渲染（爱奇艺 / 芒果TV 需要）
  iqiyi.py youku.py tencent.py mgtv.py   各平台采集器
.github/workflows/deploy.yml   定时采集 + Pages 部署
```

## 免责声明

数据抓取自各平台公开页面，仅供个人追剧参考，请勿用于商业用途。
请遵守各平台的服务条款，合理控制抓取频率。
