import time


class Browser:
    def __init__(self):
        self.current_url = None
        self.history = []

    def start(self):
        print("[Browser] Started")
        self.history = []

    def goto(self, url: str):
        print(f"[Browser] Opening → {url}")
        self.current_url = url
        self.history.append({"action": "goto", "url": url})
        time.sleep(0.5)  # محاكاة تأخير

    def type(self, selector: str, text: str):
        print(f"[Browser] Typing in '{selector}' → {text}")
        self.history.append({"action": "type", "selector": selector, "text": text})
        time.sleep(0.3)

    def click(self, selector: str):
        print(f"[Browser] Clicking → {selector}")
        self.history.append({"action": "click", "selector": selector})
        time.sleep(0.3)

    def wait(self, seconds: float = 1):
        print(f"[Browser] Waiting {seconds}s")
        time.sleep(seconds)
        self.history.append({"action": "wait", "seconds": seconds})

    def screenshot(self, filename: str = "screenshot.png"):
        print(f"[Browser] Screenshot saved → {filename}")
        self.history.append({"action": "screenshot", "filename": filename})

    def stop(self):
        print("[Browser] Closed")
        print("[Browser] Actions performed:")
        for i, action in enumerate(self.history, 1):
            print(f"  {i}. {action}")
