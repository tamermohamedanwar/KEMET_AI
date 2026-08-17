from .browser import Browser
from .logger import logger
from .models import TaskResult


class TaskExecutor:

    def execute(self, task) -> TaskResult:
        browser = Browser()
        logger.info(f"Task Started: {task.name}")

        try:
            browser.start()

            for step in task.steps:
                action = step.action.lower()
                params = step.params or {}

                if action == "goto":
                    browser.goto(params.get("url", ""))
                elif action == "type":
                    browser.type(
                        params.get("selector", ""),
                        params.get("text", "")
                    )
                elif action == "click":
                    browser.click(params.get("selector", ""))
                elif action == "wait":
                    browser.wait(float(params.get("seconds", 1)))
                elif action == "screenshot":
                    browser.screenshot(params.get("filename", "screenshot.png"))
                else:
                    logger.warning(f"Unknown action: {action}")

            browser.stop()
            logger.info("Task Finished successfully")
            return TaskResult(success=True, message=f"تم تنفيذ المهمة: {task.name}")

        except Exception as e:
            logger.error(f"Task Failed: {e}")
            try:
                browser.stop()
            except Exception:
                pass
            return TaskResult(success=False, message=str(e))
