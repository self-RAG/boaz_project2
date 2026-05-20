### 수집 필드: 명칭, 다른명칭, 전시명칭, 국적/시대, 재질, 분류, 크기, 소장품번호, 전시위치, 설명
### 저장 형식: JSON

import requests
from bs4 import BeautifulSoup
import json
import time
import os
import logging
from datetime import datetime

# ── 설정 ────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.museum.go.kr/MUSEUM/contents/M0502000000.do"
PARAMS_TEMPLATE = {
    "schM": "view",
    "searchId": "search",
}

OUTPUT_FILE = "museum_collections.json"
LOG_FILE    = "museum_crawler.log"

# relicId 탐색 범위 (최대한 넓게 설정; 없는 ID는 자동 스킵)
RELIC_ID_START = 1
RELIC_ID_END   = 50000          # 필요 시 늘려도 됨

# 요청 간격(초) — 서버 부하 방지
REQUEST_DELAY  = 0.5

# 연속 빈 페이지가 이 횟수 이상이면 탐색 종료
# 낮은 ID 대역(1~328)은 유물 없는 에러 페이지이므로 충분히 크게 설정
MAX_CONSECUTIVE_EMPTY = 500

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.museum.go.kr/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# ── 로깅 설정 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ── 파싱 함수 ────────────────────────────────────────────────────────────────
def parse_detail(html: str, relic_id: int) -> dict | None:
    """소장품 상세 페이지 HTML을 파싱하여 딕셔너리 반환. 유물 없으면 None."""
    soup = BeautifulSoup(html, "html.parser")

    # ── 1단계: 유물명 확인 (유효 페이지 판단) ────────────────────────────────
    # 실제 구조: <div class="outview"><strong class="outveiw-tit">유물명</strong>
    # (사이트에 오타 "outveiw-tit" 있음)
    title_tag = soup.select_one("strong.outveiw-tit")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)
    if not title:
        return None

    info: dict = {"relicId": relic_id, "title": title}

    # ── 2단계: 상세정보 파싱 ─────────────────────────────────────────────────
    # 구조: <ul class="outview-list"><li><strong>필드명</strong><p>값</p></li>...
    for li in soup.select("ul.outview-list li"):
        key_tag = li.find("strong")
        val_tag = li.find("p")
        if key_tag and val_tag:
            key = key_tag.get_text(strip=True)
            val = val_tag.get_text(strip=True)
            if key:
                info[key] = val

    # ── 3단계: 설명 추출 ────────────────────────────────────────────────────
    # outview-list 내부 p(=짧은 필드값)와 정부 안내문 제외
    outview_ps = {id(p) for p in soup.select("ul.outview-list p")}
    BAD_PHRASES = ["go.kr 주소를", "누리집", "관련 사이트", "이전 페이지", "04383", "대표전화"]
    desc_parts = []
    for p in soup.find_all("p"):
        if id(p) in outview_ps:
            continue
        text = p.get_text(strip=True)
        if len(text) > 50 and not any(phrase in text for phrase in BAD_PHRASES):
            desc_parts.append(text)
            if len(desc_parts) >= 3:
                break
    if desc_parts:
        info["description"] = " ".join(desc_parts)

    # ── 4단계: 기타 필드 ────────────────────────────────────────────────────
    badge = soup.find(class_=lambda c: c and "badge" in c.lower())
    if not badge:
        badge = soup.find("span", string=lambda s: s and s.strip() in ["중요", "국보", "보물"])
    if badge:
        info["importance"] = badge.get_text(strip=True)

    info["has3D"] = bool(soup.find("a", string=lambda s: s and "3D" in s))
    info["crawledAt"] = datetime.now().isoformat()

    return info


# ── 메인 크롤러 ──────────────────────────────────────────────────────────────
def crawl():
    session = requests.Session()
    session.headers.update(HEADERS)

    results: list[dict] = []

    # 이미 저장된 파일이 있으면 이어서 수집 (재시작 지원)
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            results = json.load(f)
        collected_ids = {r["relicId"] for r in results}
        log.info(f"기존 데이터 {len(results)}개 로드. 이어서 수집합니다.")
    else:
        collected_ids = set()

    consecutive_empty = 0
    total_saved = len(results)

    for relic_id in range(RELIC_ID_START, RELIC_ID_END + 1):
        if relic_id in collected_ids:
            continue

        params = {**PARAMS_TEMPLATE, "relicId": relic_id}

        try:
            resp = session.get(BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"relicId={relic_id} 요청 실패: {e}")
            time.sleep(REQUEST_DELAY * 2)
            continue

        item = parse_detail(resp.text, relic_id)

        if item is None:
            consecutive_empty += 1
            if consecutive_empty % 50 == 0:
                log.info(f"연속 빈 페이지 {consecutive_empty}개 (relicId={relic_id})")
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                log.info("연속 빈 페이지 한계 도달 — 탐색 종료")
                break
        else:
            consecutive_empty = 0
            results.append(item)
            total_saved += 1
            log.info(f"[{total_saved}] relicId={relic_id} | {item.get('title', '')}")

            # 100개마다 중간 저장
            if total_saved % 100 == 0:
                _save(results)
                log.info(f"  → 중간 저장 완료 ({total_saved}개)")

        time.sleep(REQUEST_DELAY)

    _save(results)
    log.info(f"\n 완료! 총 {len(results)}개 소장품 저장 → {OUTPUT_FILE}")


def _save(data: list[dict]):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 실행 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=== 국립중앙박물관 소장품 크롤러 시작 ===")
    log.info(f"탐색 범위: relicId {RELIC_ID_START} ~ {RELIC_ID_END}")
    log.info(f"요청 간격: {REQUEST_DELAY}초\n")
    crawl()