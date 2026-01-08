import json
import logging
from urllib.request import Request, urlopen
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

def send_notification(title: str, content: str, notify_type: str, notify_key: str):
    """
    发送通知到指定平台
    :param title: 通知标题
    :param content: 通知内容 (支持 Markdown)
    :param notify_type: 'pushdeer' 或 'serverchan'
    :param notify_key: 推送密钥 (PushDeer Key 或 Server酱 SendKey)
    """
    if not notify_key:
        logger.warning("Notification key is missing, skipping notification.")
        return

    try:
        if notify_type.lower() == 'pushdeer':
            url = "https://api2.pushdeer.com/message/push"
            params = {
                "pushkey": notify_key,
                "text": title,
                "desp": content,
                "type": "markdown"
            }
            data = urlencode(params).encode('utf-8')
            req = Request(url, data=data, method='POST')
            
        elif notify_type.lower() == 'serverchan':
            url = f"https://sctapi.ftqq.com/{notify_key}.send"
            params = {
                "title": title,
                "desp": content
            }
            data = urlencode(params).encode('utf-8')
            req = Request(url, data=data, method='POST')
        
        else:
            logger.error(f"Unsupported notification type: {notify_type}")
            return

        with urlopen(req, timeout=10) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            logger.info(f"Notification sent via {notify_type}: {resp_data}")
            
    except Exception as e:
        logger.error(f"Failed to send notification via {notify_type}: {e}")

def format_scan_signals_markdown(signals: list[dict]) -> str:
    """格式化扫描信号为 Markdown 表格"""
    if not signals:
        return "本次扫描未发现信号。"
    
    lines = [
        "### 🚀 发现买入信号",
        "| 股票代码 | 信号日期 | 触发价格 | 止损价 | 盈亏比 |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for s in signals:
        # 处理可能的 None 或缺失字段
        symbol = s.get('symbol', 'Unknown')
        dt = s.get('date', 'Unknown')
        price = s.get('price', 0.0)
        stop = s.get('initial_stop', 0.0)
        rr = s.get('rr_ratio', 0.0)
        lines.append(f"| {symbol} | {dt} | {price:.2f} | {stop:.2f} | {rr:.2f} |")
    
    lines.append(f"\n**总计: {len(signals)} 个信号**")
    return "\n".join(lines)