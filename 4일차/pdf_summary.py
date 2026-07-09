import os
from pathlib import Path
from typing import Union

import pymupdf
from dotenv import load_dotenv
from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MODEL = "gpt-4o-mini"


def pdf_to_txt(pdf_path: Union[str, Path]) -> Path:
    """1. PDF를 읽어 txt 파일로 저장하고 txt 파일 경로를 반환한다."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    doc = pymupdf.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n------------------------\n"
    doc.close()

    txt_path = pdf_path.with_suffix(".txt")
    txt_path.write_text(full_text, encoding="utf-8")
    return txt_path


def summarize_txt(txt_path: Union[str, Path]) -> str:
    """2. txt 파일을 LLM으로 요약하고 요약문을 반환한다."""
    txt_path = Path(txt_path)
    if not txt_path.exists():
        raise FileNotFoundError(f"txt 파일을 찾을 수 없습니다: {txt_path}")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("`.env`에 OPENAI_API_KEY를 설정하세요.")

    client = OpenAI(api_key=api_key)
    txt = txt_path.read_text(encoding="utf-8")

    system_prompt = f"""
너는 다음 글을 요약하는 봇이다. 아래 글을 읽고,

작성해야 하는 포맷은 다음과 같음
# 제목

## 저자의 문제 인식 및 주장 (15문장 이내)

## 저자 소개

============= 이하 텍스트 ================
{txt[:10000]}
"""

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
        ],
    )

    return response.choices[0].message.content


def pdf_summarize(pdf_path: Union[str, Path]) -> str:
    """3. PDF → txt 변환 → LLM 요약 → summary.txt 저장 후 요약문 반환."""
    pdf_path = Path(pdf_path)

    txt_path = pdf_to_txt(pdf_path)
    summary = summarize_txt(txt_path)

    summary_path = pdf_path.parent / "summary.txt"
    summary_path.write_text(summary, encoding="utf-8")

    return summary


if __name__ == "__main__":
    sample_pdf = Path(__file__).resolve().parent / "samples" / "Language_Models.pdf"
    result = pdf_summarize(sample_pdf)
    print(result)
    print(f"\n저장 완료: {sample_pdf.parent / 'summary.txt'}")
