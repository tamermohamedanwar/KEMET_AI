class PluginRegistry:
    def __init__(self):
        self._plugins = {}

    def register(self, name, plugin):
        self._plugins[name] = plugin

    def get(self, name):
        return self._plugins.get(name)

    def remove(self, name):
        self._plugins.pop(name, None)

    def exists(self, name):
        return name in self._plugins

    def all(self):
        return self._plugins

registry = PluginRegistry()
