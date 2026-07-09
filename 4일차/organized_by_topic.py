"""
PDF 주제별 정리 스크립트

4.5 pdf 정리 agent.ipynb 의 Tool(list_documents, read_pdf_text, search_in_document 등)을 활용하고,
요약·카테고리화·폴더 이동·질의응답을 위해 추가 Tool을 정의합니다.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

# ── 경로 ──────────────────────────────────────────
BASE = Path(__file__).resolve().parent
load_dotenv(BASE.parent / ".env")

DOC_LIBRARY = BASE / "samples" / "pdf_samples"
CATALOG_DIR = DOC_LIBRARY / "_catalog"
ORGANIZED_INDEX = CATALOG_DIR / "organized_index.json"

AGENT_FILE = BASE / "4.5 pdf 정리 agent.py"
MODEL = "gpt-4o-mini"

client = OpenAI()


def _load_agent_module():
    """노트북과 동일한 Tool이 들어 있는 agent 모듈을 동적 로드."""
    spec = importlib.util.spec_from_file_location("pdf_agent", AGENT_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent = _load_agent_module()

# 노트북 Part A~C Tool 재사용
list_documents = agent.list_documents
read_pdf_text = agent.read_pdf_text
build_pdf_index = agent.build_pdf_index
search_in_document = agent.search_in_document
search_chunks = agent.search_chunks
run_agent = agent.run_agent


# ── 추가 Tool ─────────────────────────────────────


def safe_folder_name(name: str) -> str:
    """Windows에서 사용 가능한 폴더명으로 변환."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name.strip())
    return cleaned or "기타"


def summary_file_name(pdf_name: str) -> str:
    stem = Path(pdf_name).stem
    safe = re.sub(r"[^\w가-힣\-]+", "_", stem)[:50].strip("_")
    return f"{safe}.summary.txt"


def summarize_pdf_for_catalog(pdf_name: str) -> dict[str, Any]:
    """
    [추가 Tool] PDF 내용을 읽고 카탈로그용 요약 메타데이터를 LLM으로 생성.
    """
    pdf_path = DOC_LIBRARY / pdf_name
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 없음: {pdf_path}")

    text = read_pdf_text(pdf_path)
    prompt = f"""
다음 PDF 문서를 분석해 JSON만 반환하세요.

PDF 파일명: {pdf_name}

요구 JSON 형식:
{{
  "category": "문서 유형 (예: 규정, 논문, 보도자료, 보고서 등)",
  "folder_label": "폴더명으로 쓸 대표 단어 1개 (한글, 짧게)",
  "one_line_summary": "한 줄 요약",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "detail_summary": "3~5문장 상세 요약"
}}

문서 내용(앞부분):
{text[:12000]}
"""
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    data["pdf_name"] = pdf_name
    return data


def save_summary_txt(meta: dict[str, Any]) -> Path:
    """
    [추가 Tool] 요약 메타데이터를 _catalog/*.summary.txt 로 저장.
    """
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = CATALOG_DIR / summary_file_name(meta["pdf_name"])
    keywords = ", ".join(meta.get("keywords", []))
    content = f"""# {meta['pdf_name']}
## 유형
{meta.get('category', '')}
## 한 줄 요약
{meta.get('one_line_summary', '')}
## 핵심 키워드
{keywords}
## 상세 요약
{meta.get('detail_summary', '')}
"""
    summary_path.write_text(content, encoding="utf-8")
    return summary_path


def move_pdf_to_category(pdf_name: str, folder_label: str) -> str:
    """
    [추가 Tool] 대표 단어 폴더를 만들고 PDF를 이동. 이동 후 상대 경로 반환.
    """
    folder_name = safe_folder_name(folder_label)
    target_dir = DOC_LIBRARY / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    source = DOC_LIBRARY / pdf_name
    if not source.exists():
        raise FileNotFoundError(f"이동할 PDF 없음: {source}")

    destination = target_dir / Path(pdf_name).name
    if source.resolve() != destination.resolve():
        shutil.move(str(source), str(destination))

    return f"{folder_name}/{destination.name}"


def save_organized_index(entries: list[dict[str, Any]]) -> Path:
    """
    [추가 Tool] 정리 결과를 organized_index.json 에 저장.
    """
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"documents": entries}
    ORGANIZED_INDEX.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ORGANIZED_INDEX


def get_organized_catalog() -> str:
    """
    [추가 Tool] 정리된 카탈로그(폴더 위치 포함)를 JSON 문자열로 반환.
    """
    if not ORGANIZED_INDEX.exists():
        return json.dumps({"documents": [], "message": "아직 정리되지 않았습니다."}, ensure_ascii=False)

    data = json.loads(ORGANIZED_INDEX.read_text(encoding="utf-8"))
    return json.dumps(data, ensure_ascii=False, indent=2)


def find_pdf_by_question(question: str) -> dict[str, Any] | None:
    """
    [추가 Tool] 질문과 가장 관련 있는 PDF 메타데이터 1건 반환.
    """
    if not ORGANIZED_INDEX.exists():
        return None

    catalog = json.loads(ORGANIZED_INDEX.read_text(encoding="utf-8"))
    docs = catalog.get("documents", [])
    if not docs:
        return None

    prompt = f"""
질문과 가장 관련 있는 PDF 하나를 고르세요. JSON만 반환하세요.

질문: {question}

후보 목록:
{json.dumps(docs, ensure_ascii=False)}

형식: {{"pdf_name": "...", "relative_path": "..."}}
"""
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    picked = json.loads(response.choices[0].message.content)
    for doc in docs:
        if doc.get("pdf_name") == picked.get("pdf_name"):
            return doc
    return docs[0]


def answer_pdf_question(question: str) -> str:
    """
    [추가 Tool] PDF에 대한 질문 → 요약 + 카테고리 폴더 위치 안내.
    notebook의 search_in_document / build_pdf_index 도 함께 활용.
    """
    doc = find_pdf_by_question(question)
    if not doc:
        return "정리된 PDF가 없습니다. 먼저 `python organized_by_topic.py organize` 를 실행하세요."

    pdf_rel = doc.get("relative_path") or doc["pdf_name"]
    chunks = search_chunks(question, build_pdf_index(pdf_rel), top_k=2)

    chunk_text = ""
    if chunks:
        chunk_text = chunks[0].get("text", "")[:500]

    return (
        f"📄 문서: {doc['pdf_name']}\n"
        f"📁 카테고리 폴더: {doc.get('folder_label', '')} "
        f"(`samples/pdf_samples/{pdf_rel}`)\n"
        f"📝 한 줄 요약: {doc.get('one_line_summary', '')}\n"
        f"🔍 관련 내용: {chunk_text or doc.get('detail_summary', '')}"
    )


# ── 메인 파이프라인 ───────────────────────────────


def organize_pdfs_by_topic() -> list[dict[str, Any]]:
    """
    Step 1~4: PDF 목록 확인 → 요약 txt 생성 → 카테고리화 → 폴더 이동
    """
    # Step 1. pdf_samples PDF 파일명 확인
    listed = json.loads(list_documents())
    pdf_files = [name for name in listed["pdf_files"] if "/" not in name and "\\" not in name]
    print(f"[Step 1] PDF {len(pdf_files)}개 확인: {pdf_files}")

    entries: list[dict[str, Any]] = []

    for pdf_name in pdf_files:
        # Step 2. 요약 및 summary txt 생성
        print(f"[Step 2] 요약 생성: {pdf_name}")
        meta = summarize_pdf_for_catalog(pdf_name)
        summary_path = save_summary_txt(meta)

        # Step 3. 카테고리·대표 단어 설정
        folder_label = meta.get("folder_label") or meta.get("category", "기타")
        print(f"[Step 3] 카테고리: {meta.get('category')} / 폴더명: {folder_label}")

        # Step 4. 폴더 생성 및 PDF 이동
        relative_path = move_pdf_to_category(pdf_name, folder_label)
        print(f"[Step 4] 이동 완료 → {relative_path}")

        entries.append(
            {
                "pdf_name": pdf_name,
                "relative_path": relative_path,
                "category": meta.get("category", ""),
                "folder_label": folder_label,
                "keywords": meta.get("keywords", []),
                "one_line_summary": meta.get("one_line_summary", ""),
                "detail_summary": meta.get("detail_summary", ""),
                "summary_file": summary_path.name,
            }
        )

    save_organized_index(entries)
    print(f"[완료] 카탈로그 저장: {ORGANIZED_INDEX}")
    return entries


def print_checklist() -> None:
    print(
        """
[필요사항 체크리스트]
✅ pdf_samples PDF 파일명 확인        → list_documents()
✅ PDF 요약 및 summary txt 생성         → summarize_pdf_for_catalog(), save_summary_txt()
✅ 주제별 카테고리·대표 단어 설정       → summarize_pdf_for_catalog() (LLM)
✅ 대표 단어 폴더 생성 및 PDF 이동      → move_pdf_to_category()
✅ PDF 질문 시 요약+폴더 위치 안내      → answer_pdf_question()

[노트북에서 재사용한 Tool]
- list_documents, read_pdf_text, build_pdf_index, search_in_document, search_chunks, run_agent

[추가한 Tool]
- summarize_pdf_for_catalog, save_summary_txt, move_pdf_to_category
- save_organized_index, get_organized_catalog, find_pdf_by_question, answer_pdf_question
"""
    )


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "organize"

    if command == "organize":
        print_checklist()
        organize_pdfs_by_topic()
    elif command == "ask" and len(sys.argv) > 2:
        question = " ".join(sys.argv[2:])
        print(answer_pdf_question(question))
    elif command == "catalog":
        print(get_organized_catalog())
    elif command == "list":
        print(list_documents())
    else:
        print(
            "사용법:\n"
            "  python organized_by_topic.py organize   # PDF 주제별 정리\n"
            "  python organized_by_topic.py ask 질문  # PDF 질의응답\n"
            "  python organized_by_topic.py catalog  # 정리 카탈로그 보기\n"
            "  python organized_by_topic.py list     # PDF 목록 보기"
        )
