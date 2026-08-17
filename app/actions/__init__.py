ACTIONS = {}

def register(name):
    def decorator(func):
        ACTIONS[name] = func
        return func
    return decorator

def execute(name, **kwargs):
    action = ACTIONS.get(name)
    if not action:
        return {"status": "error", "message": f"Action '{name}' not found"}
    return action(**kwargs)
