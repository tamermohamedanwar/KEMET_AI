class MemoryAgent:
    def __init__(self):
        self.memory = {}

    def remember(self, user_id, key, value):
        self.memory.setdefault(user_id, {})
        self.memory[user_id][key] = value

    def recall(self, user_id, key, default=None):
        return self.memory.get(user_id, {}).get(key, default)

memory_agent = MemoryAgent()
