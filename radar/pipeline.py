"""One place where a page text becomes a stored, validated brief.

Both the web handler and the command line go through here, so the audit trail is
identical no matter how the analysis was started.
"""

from . import extract as extract_mod
from . import offline
from . import validate


class Pipeline(object):
    def __init__(self, store, offline_default=False, default_year=None, reference=None):
        self.store = store
        self.offline_default = offline_default
        self.default_year = default_year
        self.reference = reference

    # -- readers ---------------------------------------------------------
    def propose(self, text, mode="offline", settings=None):
        if mode == "offline":
            return offline.extract(text, default_year=self.default_year)
        raw, _reply = extract_mod.propose(text, settings=settings)
        return raw

    # -- full run --------------------------------------------------------
    def run(self, text, mode="offline", inject=None, analysis_id=None, settings=None):
        raw = self.propose(text, mode=mode, settings=settings)
        if inject is not None:
            raw = inject(raw)
        result = validate.analyse(raw, text, mode=mode,
                                  default_year=self.default_year, reference=self.reference)
        result["reader"] = raw.get("reader") if isinstance(raw, dict) else None
        if inject is not None:
            result["injected"] = True
        saved = self.store.save(text, result, analysis_id=analysis_id)
        return result, saved
