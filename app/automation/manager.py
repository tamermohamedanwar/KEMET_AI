from .executor import TaskExecutor
from .models import TaskResult


class AutomationManager:

    def run(self, task) -> TaskResult:
        print(f"\n===== بدء تنفيذ المهمة: {task.name} =====")
        executor = TaskExecutor()
        result = executor.execute(task)
        print(f"===== نتيجة المهمة: {result.message} =====\n")
        return result
