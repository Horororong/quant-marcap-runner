# 퀀트 백테스트 환경 — 지속적인 상위 프로젝트 지침

이 문서는 저장소 소유자가 지정한 지속적인 프로젝트 지침이다. 새로운 Codex 작업과 세션에서는 `AGENTS.md` 다음에 이 문서를 먼저 읽고, 현재 코드·데이터·GitHub 상태를 확인한 뒤 기존 작업을 이어서 진행한다. 인수인계 문서와 과거 대화의 commit/CI 정보는 checkpoint이며 현재 상태의 증거가 아니다.

## 목표와 작업 책임

목표는 **신뢰할 수 있는 과거 데이터 + 재현 가능한 범용 백테스트 엔진 + 전략을 쉽게 추가할 수 있는 인터페이스**이다. 한국어 전략 요청을 지원 capability와 대조하고 Strategy Schema/DSL로 변환하여 동일 엔진에서 실행한다. 전략마다 엔진을 수정하거나 별도 백테스터를 생성하지 않는다. 미지원 요청을 비슷한 전략으로 임의 변환하지 않고 `capability_gap`과 `data_gap`을 구분한다.

Codex는 데이터 수집·저장, PIT 검증, DSL/registry/provider, 실행·성과 계산, 테스트, GitHub 운영과 반복 작업 자동화를 일관되게 관리한다. 사용자가 허용한 작업은 구현·검증까지 이어서 진행한다. 이미 진행 중인 작업은 안전하게 마무리하고 이 지침에 따라 남은 작업의 의존관계와 우선순위를 정한다. 기존 정상 기능은 불필요하게 다시 만들거나 리팩터링하지 않는다. 데이터 정확성이 속도보다 우선한다.

## 데이터와 PIT 무결성

- KRX 개별종목 가격·시가총액, 지수·벤치마크, DART 재무, 필요한 시장·매크로 데이터의 갱신 상태와 품질을 관리한다. 기존 저장소 데이터를 우선 사용한다.
- 당시 존재했던 상장폐지 종목을 포함한다. 현재 상장 목록으로 과거 universe를 재구성하거나 누락 종목을 조용히 제외하지 않는다.
- 실제 공시·사용 가능일 이전에 재무정보를 사용하지 않는다. 보고기간 말일, 공시일, 정정공시와 사용 가능일을 구분한다. Look-ahead bias, survivorship bias와 PIT 오류를 구조적으로 차단한다.
- 누락 값·수익률을 0, forward-fill, 추정치 또는 임의 proxy로 조용히 대체하지 않는다. 명시적으로 검증된 계약이 없는 대체는 gap으로 반환한다.
- 기업행동은 원천 증거가 검증된 event만 적용한다. 거래 불가능 종목, 리밸런싱·체결 날짜, 수익률 연결, 비용 누락, 벤치마크 기간 불일치를 검증한다.

## 최우선 인계: DART legacy 2000~2014

백필을 중간에 방치하지 않고 신뢰할 수 있는 2000~2014 PIT 재무데이터가 완성될 때까지 수집·검증 체계를 발전시킨다. 처리 건수나 `PARSED_4F` 자체는 정확성 또는 완료의 증거가 아니다.

- `PARSED_4F`, `PARSED_PARTIAL`, `NO_METRICS`, `NO_DOCUMENT`, `ERROR`, `RATE_LIMIT`을 parser version 및 보고기간별로 관찰한다. 과거 버전의 처리 건수를 현재 유효 데이터로 합산하지 않는다.
- 2000 Q3, 2001 H1/Q1/Q3 등 초기 구간의 낮거나 0인 4F 비율을 단순히 “원래 자료가 없음”으로 결론내리지 않는다. 대표 실패 공시를 실제 당시 DART 공시 원문과 대조하여 parser 문제와 source-data 부재를 구분한다.
- Statement heading, CFS/OFS scope, 단위, 실제 당기 numeric column, OCF, account alias를 원문 증거로 확인한다. Δ/▲/△ 음수기호 처리와 손실계정 음수 정규화는 회귀하지 않도록 유지한다.
- 수정 순서는 **현상 확인 → 원인 재현 → 실제 원천자료 확인 → 수정 → regression test → 실제 데이터 재검증**이다. 숫자를 맞추기 위한 임시방편을 쓰지 않는다.
- Parser 수정에는 회귀 테스트와 버전 관리가 필요하다. 재처리가 필요한 자료를 정확히 식별하고, 현재 버전에서 정상 처리한 자료는 불필요하게 반복 수집하지 않는다. 이전 버전의 잔여 metric을 새 버전 결과로 오인하지 않는다.
- 같은 parser로 다시 parsing하여 값이 일치하는 것은 재파싱 일관성 검사이며 독립적인 정확성 입증이 아니다. 실제 공시 원문과 독립적으로 대조하는 audit를 실시한다. 수집 완료와 품질 검증 완료를 구분한다. 검증되지 않은 legacy 데이터의 실행 capability를 공개하지 않는다.

## 반복 작업 자동화

- 기존 GitHub Actions와 schedule을 먼저 조사한다. 기존 자동화가 충분하면 재사용하고 필요한 부분만 수정한다. 중복 workflow나 무한 재실행을 만들지 않는다.
- 중단·timeout 후 다음 실행에서 resume할 수 있도록 진행 상태, 실패 상태와 안전한 checkpoint를 저장한다. 처리 상태가 데이터 저장보다 먼저 완료로 기록되지 않도록 한다.
- API rate limit, 재시도·batch·worker·실행시간 예산을 제한한다. 중복 실행을 막고 API 과다 호출, Actions 사용량과 Git 저장공간 낭비를 방지한다.
- 사용자가 매일 Codex를 수동 실행하지 않아도 예약 실행이 안전하게 진척되도록 한다. 자동으로 검증할 수 없는 원천 증거·데이터 gap은 숨기지 않고 별도 상태로 남긴다.
- 2000~2014 백필 완료는 데이터 품질 기준으로 판단한다. 완료 후 임시 고빈도 수집을 계속 방치하지 않고 정상 운영 상태로 전환한다. 일정 trigger가 남더라도 완료된 수집을 다시 실행하지 않아야 한다.

## 범용 엔진과 재현성

- Universe, eligibility, factor, ranking, weighting, rebalance, holding period, transaction cost, benchmark를 반복 가능한 DSL·registry·provider capability로 표현한다.
- 동일 DSL + 동일 데이터 + 동일 engine/registry/normalization version은 동일 fingerprint와 결과를 내야 한다. 실행 입력·환경·결과의 연결을 보존한다.
- Generated schema/capabilities와 runtime을 동기화한다. 입력 검증과 preflight를 우회하여 결과를 만들지 않는다.
- PROJECT는 실행, CURRENT/postprocess는 canonical 성과 계산을 담당한다. 전략별로 CAGR/MDD 등 성과지표를 별도로 다시 계산하지 않는다.

## 검증과 GitHub 운영

- “실행된다”와 “금융적으로 정확하다”를 구분한다. 변경에는 failure boundary를 포함한 unit/regression/integration test를 추가하고 중요한 변경은 실제 데이터로 재검증한다.
- 기존 정상 전략의 선정 결과·NAV·fingerprint를 조용히 변경하지 않는다. Generated-contract 검사와 실제 DART/KRX/top-N/10분위 E2E를 포함한 전체 Strategy DSL CI 계약을 만족시킨다.
- GitHub 저장소를 SSOT로 사용한다. Working `main`을 보존하고 작은 검증 가능한 단위로 의미 있는 commit을 만든다. 변경 전후 테스트와 최종 commit의 CI를 확인한다.
- 자동 생성 결과·timestamp·압축 metadata가 불필요하게 Git history를 키우지 않도록 관리한다. 대용량 데이터와 결과의 추적 필요성을 점검한다. Secrets는 Git과 로그에 저장하지 않는다.
- 데이터·history를 임의 삭제하지 않는다. Git history rewrite, force push, BFG/filter-repo 및 기존 대용량 blob 삭제는 별도 명시적 승인 없이는 실행하지 않는다. 외부 저장소·LFS 이전도 재현성·접근성·비용을 비교한 뒤 결정한다.

## 완료와 인계

작업은 여러 단계로 나눈다. **각 단계가 완료될 때 변경사항을 GitHub에 commit하고 완료 단계·현재 상태·다음 작업을 저장소에 기록한다.** 사용 한도나 세션 종료로 중단돼도 다음 세션이 저장소만 읽고 즉시 재개할 수 있어야 한다. 장시간 작업을 한 번에 모두 끝내려다가 저장되지 않은 상태로 종료하지 않는다.

현재 인계 우선순위는 (1) 상위 지침 저장·commit, (2) 코드·데이터·workflow 상태 확인, (3) 안전한 resume 검증, (4) 기존 Actions 자동화 구성·검증, (5) 실제 백필, (6) parser 이상 구간 원문 조사·수정, (7) 전체 2000~2014 품질 검증, (8) DSL·범용 백테스트의 남은 기능이다. 원문 확인 없이 parser를 임의 수정하지 않는다. 이후 우선순위가 바뀌면 근거와 새 순서를 기록한다.

요청한 구현은 계약·테스트·원천 증거·관련 CI로 검증하고, 남은 위험과 미검증 범위를 명시한다. 다음 세션이 이어갈 수 있도록 현재 checkpoint, 재개 명령, 버전, 자동화 상태와 독립 audit 상태를 `HANDOFF_CURRENT.md` 및 관련 문서에 기록한다. 백필이 종료됐다는 이유만으로 미해결 품질 문제를 완료 처리하지 않는다.
