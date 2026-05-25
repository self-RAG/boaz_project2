import os
from dotenv import load_dotenv
load_dotenv()
from typing import List
from pydantic import BaseModel, Field
from typing_extensions import TypedDict, Annotated

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END

from hybrid_search import HybridSearcher

# ────────────────────────────────────────────────────────────────────────
# 1. 프롬프트 불러오기
# ────────────────────────────────────────────────────────────────────────
# (1) grader 프롬프트
from prompts.grader_prompts import (
    DOC_GRADE_SYSTEM,
    GROUNDED_SYSTEM,
    ANSWER_GRADE_SYSTEM,
    REWRITE_SYSTEM
)

# (2) 도슨트 프롬프트 레이어
from prompts.system_prompt import SYSTEM_PROMPT
from prompts.safety_prompt import SAFETY_PROMPT
from prompts.memory_prompt import MEMORY_PROMPT
from prompts.graph_prompt  import GRAPH_PROMPT
from prompts.style_prompt  import STYLE_PROMPT

# LLM 초기화
MODEL_NAME = "gemini-2.5-flash"
llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME, 
    temperature=0,
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# ────────────────────────────────────────────────────────────────────────
# 2. 데이터 모델 정의 
# ────────────────────────────────────────────────────────────────────────
class GradeDocuments(BaseModel):
    binary_score: str = Field(description="Documents are relevant to the question, 'yes' or 'no'")

class Groundedness(BaseModel):
    binary_score: str = Field(description="Answer is grounded in the facts, 'yes' or 'no'")

class GradeAnswer(BaseModel):
    binary_score: str = Field(description="Answer addresses the question, 'yes' or 'no'")

# ────────────────────────────────────────────────────────────────────────
# 3. 로직
# ────────────────────────────────────────────────────────────────────────
structured_grader_docs = llm.with_structured_output(GradeDocuments)
structured_grader_grounded = llm.with_structured_output(Groundedness)
structured_grader_answer = llm.with_structured_output(GradeAnswer)

retrieval_grader = ChatPromptTemplate.from_messages([
    ("system", DOC_GRADE_SYSTEM),
    ("human", "검색된 문서: \n\n {document} \n\n 사용자 질문: {question}")
]) | structured_grader_docs

groundedness_grader = ChatPromptTemplate.from_messages([
    ("system", GROUNDED_SYSTEM),
    ("human", "제공된 팩트: \n\n {documents} \n\n AI 생성 답변: {generation}")
]) | structured_grader_grounded

answer_grader = ChatPromptTemplate.from_messages([
    ("system", ANSWER_GRADE_SYSTEM),
    ("human", "사용자 질문: \n\n {question} \n\n AI 생성 답변: {generation}")
]) | structured_grader_answer

question_rewriter = ChatPromptTemplate.from_messages([
    ("system", REWRITE_SYSTEM),
    ("human", "원본 질문: \n\n {question} \n\n 개선된 질문을 작성해주세요.")
]) | llm | StrOutputParser()


# ────────────────────────────────────────────────────────────────────────
# 4. 답변 생성
# ────────────────────────────────────────────────────────────────────────
FINAL_GENERATION_PROMPT = f"""{SYSTEM_PROMPT}

{SAFETY_PROMPT}

{MEMORY_PROMPT}

{GRAPH_PROMPT}

{STYLE_PROMPT}

[사용자 맞춤 가이드]
{{persona_guide}}

[검색 정보]
{{context}}

[현재 질문]
{{question}}
"""

rag_chain = ChatPromptTemplate.from_template(FINAL_GENERATION_PROMPT) | llm | StrOutputParser()


# ────────────────────────────────────────────────────────────────────────
# 5. LangGraph 상태 및 노드 제어
# ────────────────────────────────────────────────────────────────────────
class GraphState(TypedDict):
    question: str
    persona_guide: str      
    generation: str
    documents: List[Document]

def retrieve(state):
    print("==== [1. RETRIEVE (Graph DB 검색)] ====")
    documents = []
    with HybridSearcher() as searcher:
        results = searcher.search(state["question"], n_results=3)
        for r in results:
            documents.append(Document(page_content=r["context"], metadata={"title": r["title"]}))
    return {"documents": documents}

def grade_documents(state):
    print("==== [2. GRADE DOCUMENTS (관련성 평가)] ====")
    filtered_docs = []
    for d in state["documents"]:
        score = retrieval_grader.invoke({"question": state["question"], "document": d.page_content})
        if score.binary_score.lower() == "yes":
            filtered_docs.append(d)
    return {"documents": filtered_docs}

def decide_to_generate(state):
    print("==== [3. ASSESS GRADED DOCUMENTS (분기 결정)] ====")
    if not state["documents"]:
        return "transform_query"
    return "generate"

def transform_query(state):
    print("==== [TRANSFORM QUERY (질문 재작성)] ====")
    better_question = question_rewriter.invoke({"question": state["question"]})
    return {"question": better_question}

def generate(state):
    print("==== [4. GENERATE (Prompt Layering 기반 답변 생성)] ====")
    context_text = "\n\n".join([d.page_content for d in state["documents"]])
    persona = state.get("persona_guide", "")
    
    generation = rag_chain.invoke({
        "context": context_text, 
        "question": state["question"],
        "persona_guide": persona
    })
    return {"generation": generation}

def grade_generation_v_documents_and_question(state):
    print("==== [5. CHECK HALLUCINATIONS (환각 및 정답 평가)] ====")
    documents = "\n\n".join([d.page_content for d in state["documents"]])
    
    score = groundedness_grader.invoke({"documents": documents, "generation": state["generation"]})
    if score.binary_score.lower() == "yes":
        score = answer_grader.invoke({"question": state["question"], "generation": state["generation"]})
        if score.binary_score.lower() == "yes":
            return "relevant"
        return "not relevant"
    return "hallucination"


# ────────────────────────────────────────────────────────────────────────
# 6. LangGraph 조립
# ────────────────────────────────────────────────────────────────────────
def build_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("generate", generate)
    workflow.add_node("transform_query", transform_query)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_conditional_edges("grade_documents", decide_to_generate, {
        "transform_query": "transform_query",
        "generate": "generate"
    })
    workflow.add_edge("transform_query", "retrieve")
    workflow.add_conditional_edges("generate", grade_generation_v_documents_and_question, {
        "hallucination": "generate",
        "not relevant": "transform_query",
        "relevant": END
    })
    return workflow.compile()


# ────────────────────────────────────────────────────────────────────────
# 7. 실시간 대화 테스트 
# ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = build_graph()


    # 페르소나 설정 
    default_persona = "친절한 박물관 도슨트처럼 다정하게 설명해줘. 이모티콘도 적절히 써줘."

    while True:
        user_question = input("\n사용자 질문: ")
        
        if user_question.lower() in ['종료', 'quit', 'exit', 'q']:
            break
            
        if not user_question.strip():
            continue

        inputs = {
            "question": user_question,
            "persona_guide": default_persona
        }
    
        for output in app.stream(inputs):
            pass # 진행 과정은 노드 내 print 문 참조

        print(value["generation"])
        print("-" * 60)
