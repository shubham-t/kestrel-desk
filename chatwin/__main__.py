"""Run the plain chat window without the notebook.

    .venv\\Scripts\\python -m chatwin --stage 3            # real model from .env
    $env:KESTREL_FAKE_LLM = "1"; .venv\\Scripts\\python -m chatwin --stage 4   # offline
"""
from __future__ import annotations

import argparse

import uvicorn

from harness.config import STAGES
from harness.stages import build_agent

from .fake import get_llm, redirect_state
from .server import DEFAULT_PORT, HOST, app, set_builder


def main() -> None:
    redirect_state()
    parser = argparse.ArgumentParser(prog="python -m chatwin", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", type=int, default=0, choices=range(len(STAGES)))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    def builder(role="sales", session_id=None, approvals=None):
        return build_agent(args.stage, role, session_id=session_id, approvals=approvals, llm=get_llm())

    set_builder(builder, args.stage)
    print(f"Kestrel Desk chat window, stage {args.stage} ({STAGES[args.stage].name}): http://{HOST}:{args.port}")
    uvicorn.run(app, host=HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
