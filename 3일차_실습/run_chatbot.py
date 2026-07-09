"""Streamlit 실행 런처 (Windows SSL 오류 우회).

사용법:
    python run_chatbot.py

`streamlit run chatbot.py` 대신 이 파일을 실행하세요.
Windows 인증서 저장소 오류(ssl.SSLError)가 날 때 certifi 인증서를 사용합니다.
"""
import ssl
import sys
from pathlib import Path

import certifi

_original_create_default_context = ssl.create_default_context


def _patched_create_default_context(
    purpose=ssl.Purpose.SERVER_AUTH,
    *,
    cafile=None,
    capath=None,
    cadata=None,
):
    if cafile is None and capath is None and cadata is None:
        cafile = certifi.where()
    return _original_create_default_context(
        purpose, cafile=cafile, capath=capath, cadata=cadata
    )


ssl.create_default_context = _patched_create_default_context

from streamlit.web.cli import main

chatbot_path = Path(__file__).resolve().parent / "chatbot.py"
sys.argv = ["streamlit", "run", str(chatbot_path), *sys.argv[1:]]
main()
