# 연속 기간 연구 실행

현재 검증 예제는 원래 시총10분위2019–2020,3-1모멘텀 상위3개2020,
시총 상위1개2024, 별도로 사전 확정한 시총 상위1개2019–2025다.
전체 요청 구간을 유지한다. 원래10분위2019–2025와2001–2025는 아직 실행 불가다.
518개·64개·원문60건·기존 감사와 운영PIT게이트는 보존한다.

전용Python과 kit_manifest를 먼저 검증한다. 아래 경로는 이 작업공간의 기존 kit이며
CI는 RUNNER_TEMP의 동일 고정 kit을 복원한다. 인터넷 설치는 하지 않는다.

```bash
RESEARCH_PY=/workspace/financial-repair/runtime/.venv/bin/python
"$RESEARCH_PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$RESEARCH_PY" -I scripts/research_workbench.py capabilities
"$RESEARCH_PY" -I scripts/research_workbench.py inventory
"$RESEARCH_PY" -I scripts/research_workbench.py examples
"$RESEARCH_PY" -I scripts/research_workbench.py check --strategy config/strategies/research_size_top1_2019_2025.json --output /tmp/new-size-readiness.json
"$RESEARCH_PY" -I scripts/research_workbench.py run --strategy config/strategies/research_size_top1_2019_2025.json --report-periods config/reports/research_continuous_2025.json --output-dir /tmp/new-size-run
```

출력 파일·디렉터리는 새 경로여야 한다. 보고서는
`/tmp/new-size-run/report/report_CURRENT.html`, 원자료 기반 NAV·선정·체결 감사는
`/tmp/new-size-run/artifacts/`에 생성된다. 성과 계산·초기자산10,000 표준화·
누적자산/로그2/드로우다운·공통 기간/비용/포트폴리오 선택·KOSPI가격지수 비교는
기존 CURRENT만 담당한다. 초기10,000,000원 장부와 보고서의10,000 표준화는
별개이며 환전·추가입금이 아니다. 벤치마크는 배당 재투자 지수가 아니다.

같은 선정·체결·비용의 한국어 실행:

```bash
"$RESEARCH_PY" -I scripts/research_workbench.py run --request '기간:2019-01-01~2025-12-31;시장:코스피·코스닥;필터:시가총액>=10조원;팩터:시가총액 높은;포트폴리오:상위1개;리밸런싱:4월말;체결:1거래일뒤종가;비용:수수료1.5bp,매도세15bp,스프레드3bp,슬리피지5bp;벤치마크:코스피' --research-model-from config/strategies/research_size_top1_2019_2025.json --report-periods config/reports/research_continuous_2025.json --output-dir /tmp/new-korean-run
```

한국어/JSON의 NAV·목표비중·CURRENT성과는 바이트가 같다. 사용자 지정 팩터명
`size`/`Marcap`은 audit 컬럼 이름에만 영향을 준다. 동일(source,field,direction,
transform,weight)을 먼저 확인하고 그 이름만 대응한 선정 테이블은 모든 값이 정확히 같다.
미지원 표현·필터·팩터는 비슷한 전략으로 번역하지 않는다.

차단 예제와 저장된 진단 조회:

```bash
"$RESEARCH_PY" -I scripts/research_workbench.py run --strategy config/strategies/research_size_deciles_2019_2025_v1.json --report-periods config/reports/research_continuous_2025.json --output-dir /tmp/new-original-long
# 위 명령의 exit3은 해당 요청의 차단이며 성공 NAV가 아니다.
"$RESEARCH_PY" -I scripts/research_workbench.py issues --saved-run /tmp/new-original-long
```

`preflight.json`과 `readiness_incidents.json`에는 종류·분류·종목·실제 날짜·포트폴리오·
원 신호일·가격/등락률 차이·필요 조치·입력 fingerprint·원자료/통제파일SHA가 있다.
실행 도중 실패는 `runtime_incident.json`에 남는다. `issues`의status=ok는 조회 성공이며
예전 차단의 해제나 새 실행 허가가 아니다. 재실행에는 새 preflight가 필요하다.
`inventory`는 메타데이터만 조회한다. 전체 패널의 후보와 예정 보유 노출은 다르다.

연속수량·조건부 권리의 기초주식 종가 상당액 평가·haircut1.0·공식 추가상장일 종가의
가상 정산·배당 관련 세금 제외 모델이다. 가정은 DSL의research와 그 SHA/fingerprint에
남으며 관측가격·개별 계좌 입고 사실로 표시하지 않는다. Net은 명시적 고정 매매비용을
반영한다. 실제 역사적 세후계좌, 모든 현금배당·권리·소멸 정산, 완전한 법적 종목 이력,
투자PIT 인증을 의미하지 않는다. 모든 결과는RESEARCH_ONLY, 투자 사용 불가다.

상세 결과·공식 증거·재현은 stage16_report.md와stage16_reproduction.md를 참조한다.
