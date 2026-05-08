# PKUAutoVenues-2026

```bash
echo 'cd ~/PKUAutoVenues-2026 && \
      uv run main.py \
        --venue 五四 \
        --date 2026-05-03 \
        --times 19:00 20:00 \
        --spaces 9 8' \
| at 11:50 2026-04-30
```

<img src="assets/preview.png" alt="Preview">

<img src="assets/notification.png" alt="Notification" width="500">

## 致谢

- [zyHan2077/EpeAutoReserve](https://github.com/zyHan2077/EpeAutoReserve)：大佬的文档为我指点迷津

- [qqworld-tutu/PKUautoBookingVenues-fixed-by-cq-tutu](https://github.com/qqworld-tutu/PKUautoBookingVenues-fixed-by-cq-tutu)

## 如何使用（<a href="https://www.kimi.com/_prefill_chat?prefill_prompt=请阅读一下 https://github.com/goudanZ1/PKUAutoVenues-2026 这个项目，我应该如何使用它？&send_immediately=true&force_search=true">Chat with Kimi</a>）

1. 安装 [uv](https://docs.astral.sh/uv/)

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. 将项目 clone 到本地

   ```bash
   git clone https://github.com/goudanZ1/PKUAutoVenues-2026
   cd PKUAutoVenues-2026
   ```

3. 填写配置文件，详见下面的 [验证码识别](#验证码识别) 和 [消息通知](#消息通知) 部分

   ```bash
   cp config.sample.ini config.ini
   vim config.ini
   ```

4. 运行项目，详见下面的 [运行项目](#运行项目) 和 [定时运行](#定时运行) 部分

   ```bash
   uv run main.py -h
   ```

## 验证码识别

本项目推荐使用 [TT 识图](http://www.ttshitu.com/) 进行验证码识别，识别一次价格为 0.016 元，充值 1 元大约可以识别 62 次。你需要在网站上注册账号（如果已有账号且很久没用的话需要在网站上解锁账号），并在 `config.ini` 的 `[recognize:ttshitu]` 部分填写账号的用户名和密码。

（如果你已经在超级鹰里充了很多钱，）你也可以选择使用 [超级鹰](https://www.chaojiying.com/) 平台进行验证码识别，识别一次价格为 0.028 元，一次至少充 19 元（看起来比 [去年](https://github.com/qqworld-tutu/PKUautoBookingVenues-fixed-by-cq-tutu#api) 更坑了）。你需要在 `config.ini` 的 `[recognize]` 部分将 `method` 的值改为 `chaojiying`，并在 `[recognize:chaojiying]` 部分填写账号的用户名、密码、软件 ID。

非高峰时段，TT 识图的响应耗时约为 0.5 秒，超级鹰约为 0.4 秒；高峰时段（12:00 前后），TT 识图的响应耗时约为 1~1.5 秒，超级鹰尚未充分测试。

## 消息通知

可以选择以下通知方式中的一种，在预约流程完成后会自动向你发送结果。你需要在 `config.ini` 中修改 `[notify]` 部分 `method` 的值，并在对应的 `[notify:{method}]` 部分填写该通知方式所需的配置。（你也可以保留 `method = none`，表示不启用通知功能，这样下方配置都无需修改，可以直接跳到 [运行项目](#运行项目) 部分。）

### 1. Email：给自己发邮件

基于 SMTP 协议，用自己的邮箱账号给自己发送邮件，手机上的邮箱客户端（如网易邮箱大师等）就可以很方便地收到通知。目前仅适配了 `@stu.pku.edu.cn`、`@pku.edu.cn`、`@qq.com`、`@163.com`、`@126.com` 邮箱。

以 `@stu.pku.edu.cn` 邮箱为例（其他邮箱类似），你需要在浏览器中登录 [网页版邮箱](https://mail.stu.pku.edu.cn/)，进入 “设置” - **“客户端设置”** 页面，点击 **“生成客户端授权密码”**，自行设置合适的客户端名称（如 “PKUAutoVenues”）和到期时间，将邮箱地址和 **生成的授权码**（而不是原始密码）填到 `config.ini` 的 `[notify:email]` 部分。注意，为了通过 Python 发送邮件，需要 **允许非官方客户端使用 SMTP 服务**，即页面中 “非网易官方客户端” 的权限至少要有 “IMAP / SMTP 协议” 和 “POP / SMTP 协议” 其中一项。

> 下面三种方式都类似于 “向注册了特定 SendKey 的客户端发通知”，小标题说明了 “客户端” 的存在形式：

### 2. Server酱<sup>3</sup>：手机 APP（主流手机系统均可安装）

1. 打开 [Server酱<sup>3</sup> 官网](https://sc3.ft07.com/)，使用微信扫码登录，在 [SendKey 页面](https://sc3.ft07.com/sendkey) 复制 SendKey（以 `sctp` 开头的字符串），填到 `config.ini` 的 `[notify:sc3]` 部分
2. 访问 [下载页面](https://sc3.ft07.com/client)，在手机上安装 Server酱 APP，启动 APP 后填入 SendKey 或扫描 [SendKey 页面](https://sc3.ft07.com/sendkey) 上的二维码以登录

### 3. Server酱<sup>Turbo</sup>：微信服务号

打开 [Server酱<sup>Turbo</sup> 官网](https://sct.ftqq.com/)，使用微信扫码登录（关注方糖服务号），在 [Key&API 页面](https://sct.ftqq.com/sendkey) 复制 SendKey（以 `SCT` 开头的字符串），填到 `config.ini` 的 `[notify:sct]` 部分

### 4. Bark：手机 APP（仅 iOS）

在手机 App Store 下载 [Bark](https://apps.apple.com/cn/app/id1403753865)，打开 APP 首页并复制任意一个测试 URL，`https://api.day.app/` 后面的一串字符串就是你的推送 Key，将它填到 `config.ini` 的 `[notify:bark]` 部分

## 运行项目

查看帮助信息：

```bash
uv run main.py -h
```

以正确的命令行参数（`venue`, `date`, `times`, `spaces`，其中 `spaces` 是可选的）运行 `main.py` 时，脚本将按如下流程工作，日志保存在 `logs/` 目录下：

1. 根据目标预约日期 `date` 计算出名额释放时间（三天前的中午 12 点）

2. 通过不断轮询，等待到名额释放前 1 分钟，登录智慧场馆系统

3. 等待到 12 点，获取验证码并识别、校验，然后获取当日 `venue` 场馆的预约信息，筛选出空闲的 `(时段, 场地)` 对，并根据 `times` 和 `spaces` 选出其中优先级最高者，提交订单并尝试使用校园卡支付

几个例子：

- 预约 [邱德拔羽毛球场](https://epe.pku.edu.cn/venue/venue-reservation/60) 2026-04-30 的 15:00-16:00 或 20:00-21:00 时段，优先选择 5 号或 6 号场地（5 号和 6 号都不可预约时会随机选择其他可预约场地）：

  ```bash
  uv run main.py \
    --venue qdb \
    --date 2026-04-30 \
    --times 15:00 20:00 \
    --spaces 5 6
  ```

  `venue` 参数填写 qdb / 邱德拔 / 60 都指向邱德拔羽毛球场，60 取的是该场馆的 ID，见上面链接 url

  预约优先级：`15:00 5号` > `15:00 6号` > `15:00 其他场地` > `20:00 5号` > `20:00 6号` > `20:00 其他场地`，成功预约到一场后就退出

- 预约 [五四羽毛球馆](https://epe.pku.edu.cn/venue/venue-reservation/86) 周六（即将到来的最近的周六，包括今天）的 18:00-19:00 时段，随机选择可预约场地（无特别偏好）：

  ```bash
  uv run main.py \
    -v 54 \
    -d 6 \
    -t 18:00
  ```

  `venue` 参数填写 54 / ws / 五四 / 86 都指向五四羽毛球馆，对于 ID 54 被占用一事 [邱德拔 121 化妆室](https://epe.pku.edu.cn/venue/venue-reservation/54) 表示没意见

- 预约 [邱德拔台球厅](https://epe.pku.edu.cn/venue/venue-reservation/64)（？）周日的 17:00-18:00 时段，优先选择 “斯诺克”（？）或 23 号场地：

  ```bash
  uv run main.py \
    -v 64 \
    -d 7 \
    -t 17:00 \
    -s 斯诺克 23
  ```

  `venue` 参数只做了邱德拔羽毛球场和五四羽毛球馆的 alias，如果有预约其他场馆的需求，必须填写场馆 ID，见上面链接 url

## 定时运行

直接 `uv run main.py` 的用法可能只适合名额释放前 10 分钟左右手动执行命令（前台运行），或者前一晚在 `tmux` 里挂着。

如果想要定时运行（一次），可以使用 Linux 的 `at` 命令：

```bash
sudo apt install at

sudo systemctl start atd
sudo systemctl enable atd
```

```bash
echo 'cd ~/PKUAutoVenues-2026 && \
      uv run main.py \
        --venue qdb \
        --date 2026-04-22 \
        --times 19:00 20:00 15:00 \
        --spaces 5 1' \
| at 11:50 2026-04-19
```

- 记得把 `~/PKUAutoVenues-2026` 替换成项目的实际位置！

- `atq` 查看所有已设置的定时任务，`atrm 任务号` 取消任务

如果想要周期运行（如固定每周四中午预约周日的场地），可以使用 Linux 的 `cron` 服务：

```bash
(crontab -l 2>/dev/null; \
 echo "50 11 * * 4 \
       cd ~/PKUAutoVenues-2026 && \
       $(which uv) run main.py \
         -v 54 \
         -d 7 \
         -t 19:00 20:00") \
| crontab -
```

- 这里 `50 11 * * 4` 表示每周四 11:50，`-d 7` 指定要预约周日的场地

- 记得把 `~/PKUAutoVenues-2026` 替换成项目的实际位置！

- `crontab -l` 查看所有已设置的周期任务，`crontab -e` 打开编辑器管理所有周期任务（上面这串命令和 `crontab -e` 手动追加一行的效果是一样的）

## TODO

- preflight
- helper
