import logging

from dify_plugin import DifyPluginEnv, Plugin

# Native signed file capabilities and image arguments must not enter SDK payload logs.
for name in (
    "dify_plugin.core.server.tcp.request_reader",
    "dify_plugin.core.server.stdio.request_reader",
):
    logging.getLogger(name).disabled = True

plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=60, MAX_WORKER=4))
if __name__ == "__main__":
    plugin.run()
