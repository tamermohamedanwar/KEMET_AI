from .models import Task, TaskStep

demo_task = Task(
    name="Open Website",
    steps=[
        TaskStep(
            action="goto",
            params={
                "url": "https://example.com"
            }
        )
    ]
)
