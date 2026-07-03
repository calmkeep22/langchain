import os

import requests
import streamlit as st

DEFAULT_API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api")

st.set_page_config(page_title="RAG Code Reviewer", layout="wide")


def call_api(method: str, path: str, **kwargs) -> dict | None:
    url = f"{st.session_state['api_base_url']}{path}"
    try:
        response = requests.request(method, url, timeout=180, **kwargs)
    except requests.exceptions.RequestException as exc:
        st.error(f"서버에 연결할 수 없습니다: {exc}")
        return None

    body = response.json()
    if not body.get("success", False):
        error = body.get("error", {})
        st.error(f"[{error.get('code')}] {error.get('message')}")
        return None
    return body["data"]


def fetch_projects() -> list[dict]:
    return call_api("GET", "/projects") or []


def project_selector(key: str) -> dict | None:
    projects = fetch_projects()
    if not projects:
        st.info("등록된 프로젝트가 없습니다. '프로젝트 / 인덱싱' 페이지에서 먼저 등록하세요.")
        return None
    labels = [f"{p['project_id']} - {p['name']}" for p in projects]
    selected = st.selectbox("프로젝트 선택", labels, key=key)
    index = labels.index(selected)
    return projects[index]


def page_project_indexing() -> None:
    st.header("프로젝트 등록 / 인덱싱")

    with st.form("register_project_form"):
        st.subheader("프로젝트 등록")
        name = st.text_input("프로젝트 이름")
        root_path = st.text_input("코드 루트 경로", placeholder="C:/Users/me/my-project")
        submitted = st.form_submit_button("등록")
        if submitted:
            data = call_api("POST", "/projects", json={"name": name, "root_path": root_path})
            if data:
                st.success(f"등록 완료: project_id={data['project_id']}")

    st.divider()
    st.subheader("코드 인덱싱")
    project = project_selector("index_code_project")
    if project:
        force_reindex = st.checkbox("강제 재인덱싱 (force_reindex)", key="code_force_reindex")
        if st.button("코드 인덱싱 실행"):
            with st.spinner("인덱싱 중..."):
                data = call_api(
                    "POST",
                    "/index/code",
                    json={"project_id": project["project_id"], "force_reindex": force_reindex},
                )
            if data:
                st.success(
                    f"완료: 파일 {data['indexed_files']}개, 청크 {data['indexed_chunks']}개, "
                    f"스킵 {data['skipped_files']}개, 삭제 {data['deleted_files']}개"
                )

    st.divider()
    st.subheader("공식문서 인덱싱")
    with st.form("index_docs_form"):
        doc_name = st.text_input("문서 이름 (doc_name)")
        source = st.radio("입력 방식", ["URL", "로컬 Markdown 경로"], horizontal=True)
        url = path = None
        if source == "URL":
            url = st.text_input("URL", placeholder="https://fastapi.tiangolo.com/ko/tutorial/response-model/")
            max_depth = st.number_input("max_depth", min_value=1, max_value=3, value=2)
        else:
            path = st.text_input("로컬 Markdown 파일 경로")
            max_depth = 2
        force_reindex = st.checkbox("강제 재인덱싱 (force_reindex)", key="docs_force_reindex")
        submitted = st.form_submit_button("문서 인덱싱 실행")
        if submitted:
            with st.spinner("인덱싱 중... (URL 크롤링은 시간이 걸릴 수 있습니다)"):
                data = call_api(
                    "POST",
                    "/index/docs",
                    json={
                        "doc_name": doc_name,
                        "source_type": "official_doc",
                        "path": path,
                        "url": url,
                        "max_depth": int(max_depth),
                        "force_reindex": force_reindex,
                    },
                )
            if data:
                st.success(f"완료: {data}")


def render_review_result(data: dict) -> None:
    verdict_color = {
        "OK": "green",
        "PROBLEM": "red",
        "NEEDS_IMPROVEMENT": "orange",
        "INSUFFICIENT_CONTEXT": "gray",
    }.get(data["verdict"], "gray")
    st.markdown(f":{verdict_color}[**{data['verdict']}**]  (model: {data.get('model')}, {data.get('latency_ms')}ms)")
    st.markdown(data["answer"])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("관련 코드")
        for item in data.get("related_code", []):
            st.markdown(
                f"- `{item['file_path']}` "
                f"(L{item['start_line']}-{item['end_line']}"
                f"{', ' + item['symbol_name'] if item.get('symbol_name') else ''}) "
                f"— score {item['score']}"
            )
    with col2:
        st.subheader("공식문서 근거")
        for ref in data.get("official_references", []):
            st.markdown(f"- [{ref['title']}]({ref['source']}) — score {ref['score']}")


def page_ask_review() -> None:
    st.header("질문 / 리뷰")
    project = project_selector("review_project")
    if not project:
        return

    question = st.text_area("질문", placeholder="카메라 생성 API 흐름 설명해줘")
    col1, col2 = st.columns(2)
    code_top_k = col1.number_input("code_top_k", min_value=1, max_value=20, value=5)
    doc_top_k = col2.number_input("doc_top_k", min_value=1, max_value=20, value=5)

    if st.button("리뷰 요청", type="primary"):
        if not question.strip():
            st.warning("질문을 입력하세요.")
            return
        with st.spinner("검색 및 리뷰 생성 중..."):
            data = call_api(
                "POST",
                "/reviews",
                json={
                    "project_id": project["project_id"],
                    "question": question,
                    "code_top_k": int(code_top_k),
                    "doc_top_k": int(doc_top_k),
                },
            )
        if data:
            render_review_result(data)


def page_history() -> None:
    st.header("리뷰 히스토리")
    project = project_selector("history_project")
    if not project:
        return

    reviews = call_api("GET", f"/projects/{project['project_id']}/reviews") or []
    if not reviews:
        st.info("이 프로젝트에는 아직 리뷰 기록이 없습니다.")
        return

    labels = [f"#{r['review_id']} [{r['verdict']}] {r['question'][:40]} ({r['created_at']})" for r in reviews]
    selected = st.selectbox("리뷰 선택", labels)
    review_id = reviews[labels.index(selected)]["review_id"]

    detail = call_api("GET", f"/reviews/{review_id}")
    if detail:
        st.subheader(detail["question"])
        st.caption(detail["created_at"])
        st.markdown(detail["answer"])


def main() -> None:
    if "api_base_url" not in st.session_state:
        st.session_state["api_base_url"] = DEFAULT_API_BASE_URL

    st.sidebar.title("RAG Code Reviewer")
    st.session_state["api_base_url"] = st.sidebar.text_input(
        "API 서버 주소", value=st.session_state["api_base_url"]
    )
    page = st.sidebar.radio("페이지", ["프로젝트 / 인덱싱", "질문 / 리뷰", "히스토리"])

    if page == "프로젝트 / 인덱싱":
        page_project_indexing()
    elif page == "질문 / 리뷰":
        page_ask_review()
    else:
        page_history()


main()
