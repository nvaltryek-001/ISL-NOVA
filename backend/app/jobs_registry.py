"""Names for background jobs, so a job can be queued in Redis and run by ``python -m app.worker``."""

from __future__ import annotations


def _jobs():
    from .routers.ml import _eval_job, _train_job
    from .routers.personal import _analyse
    return {"train": _train_job, "evaluate": _eval_job, "analyse_video": _analyse}


def name_for(fn) -> str:
    for n, f in _jobs().items():
        if f is fn:
            return n
    raise ValueError(f"{fn.__name__} is not a registered job")


def get(name: str):
    j = _jobs().get(name)
    if j is None:
        raise KeyError(name)
    return j
