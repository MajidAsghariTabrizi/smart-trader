from dataclasses import dataclass
from typing import Dict, Optional, Any
import html
import requests

def _escape_html(s: str) -> str:
    # Safe escaping for Telegram HTML parse_mode
    return html.escape(str(s), quote=False)

def format_smart_analysis(block: str) -> str:
    """
    Wrap the provided SMART ANALYSIS text in <pre> for fixed-width formatting,
    and escape HTML-unsafe characters.
    """
    cleaned = block.strip("\n")
    return f"✅ <b>SMART ANALYSIS</b>\n<pre>{_escape_html(cleaned)}</pre>"

@dataclass
class TelegramClient:
    cfg: Dict[str, Any]
    logger: Optional[object] = None

    def _log(self, level: str, msg: str):
        if self.logger:
            try:
                getattr(self.logger, level.lower(), self.logger.info)(msg)
            except Exception:
                # Fallback to info
                try:
                    self.logger.info(msg)
                except Exception:
                    pass

    def send(self, message: str, level: str = "INFO") -> bool:
        token = self.cfg.get("bot_token")
        chat_id = self.cfg.get("chat_id")
        if not token or not chat_id:
            self._log("warning", "TelegramClient.send skipped: missing token or chat_id.")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                self._log("error", f"Telegram send failed [{resp.status_code}]: {resp.text}")
                return False
            data = resp.json()
            if not data.get("ok", False):
                self._log("error", f"Telegram API error: {data}")
                return False
            self._log("info", f"Telegram message sent: level={level}")
            return True
        except requests.RequestException as e:
            self._log("exception", f"Telegram network error: {e}")
            return False
        except Exception as e:
            self._log("exception", f"Telegram unexpected error: {e}")
            return False

    def send_smart_analysis(self, raw_block: str) -> bool:
        """
        Sends a nicely formatted SMART ANALYSIS block using HTML <pre>.
        """
        msg = format_smart_analysis(raw_block)
        return self.send(msg, level="INFO")
