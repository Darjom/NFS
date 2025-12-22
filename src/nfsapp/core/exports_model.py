
from typing import List

class ExportEntry(object):
    def __init__(self, path: str, host: str, options: List[str], raw: str = "", validated: bool = False):
        self.path = path
        self.host = host
        self.options = options
        self.raw = raw
        self.validated = validated
