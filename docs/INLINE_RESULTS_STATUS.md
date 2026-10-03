# 결과 본문 그래프 표시 · 2026-10-03

사용자 지침: 그래프는 결과 본문에 바로 표시하고 링크만 남기지 않는다.

성과표와 차트는 checked 결과의 CURRENT 표준 payload를 사용한다. 사용한 전략·실제 기간·비용·벤치마크와 종료자산 기준일을 먼저 표시한다. 기본 차트는 누적자산/Log2/Drawdown 세 개다. 지원되는 UI에는 동일 canonical payload의 인터랙티브 차트를 직접 렌더링한다.

현재 대화 도구에는 HTML/Plotly를 메시지 본문에서 실행하는 렌더러가 없다. 이 환경의 결과에는 명확히 정적 미리보기로 표시한 세 이미지를 본문에 함께 보여준다. 기존 인터랙티브 HTML을 삭제·변경하거나 미리보기를 인터랙티브 결과라고 부르지 않는다. 렌더러 capability gap은 그대로 밝힌다. 다른 ChatGPT 프로젝트로 파일을 직접 옮길 도구도 없다.

본문 미리보기는 같은 CURRENT의 points.asset / points.multiple / points.drawdown_pct와 미리 계산된 log_ticks만 사용한다. CAGR·MDD·Sharpe 등 지표를 새로 계산하지 않는다. 실제 기간의 baseline_date~actual_end를 사용한다. 환율 미반영·추가 납입 없음 표시를 유지한다.

현재 결과는 기존에 검증된 KRX 대형주 1종목 2019-01-02~2020-12-30 실행·보고 검증 예제이며 투자 가설/OOS 인증이 아니다. 소스는 822c435f의 검증된 설치 묶음이다. 원래 manifest·ZIP·설치 파일은 수정하지 않았다.
현재 Work의 미리보기: /workspace/attachments/quant-inline-results/{wealth,log2,drawdown}.png.

PR #28 정상 merge: d442e07bd4df2358cc31141143945fc5e56c0f9a. 최신 main의 백필 변경 7개 파일을 유지. 기존 data mapping/state가 달라져 새 main CI 37159959636은 별도 확인 대상이며 실행 중인 것을 pass로 표시하지 않는다.
기존 소스 전체 CI 37157470156과 배포 CI 37158824033 및 새 Work bootstrap/verify/checked 보고는 이미 완료되어 반복하지 않는다.
미완료 데이터 작업은 독립 legacy 금융 품질 audit와 누락 장기 자료다. 예약 수집을 중복 수동 실행하거나 현재 처리량을 최종 품질 완료로 바꾸지 않는다.
