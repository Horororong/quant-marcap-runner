# 장기 연구와 main 백필 독립 확인

- [전체 결과·정확성·미해결 범위](report.md)
- [재현 명령·실패 원문 위치·버전·CI](reproduction.md)
- [main 최근12회 순증](backfill_progress.csv)
- [독립 재무 표본·금액·원문 좌표](results/financial_audit/audit_details.csv)
- [독립 판정 집계](results/financial_audit/audit_summary.json)
- [새2026연구 고정 숫자 해시](numeric2026_manifest.json)

완주한 기존 연구와2026새 단일종목 연구,미완주 장기 다종목 요청을 구분한다.
RESEARCH_ONLY,현금배당 총수익/실제 계좌/투자 PIT 인증 아님. main에는 수정 미적용.
최종 CI가 성공해도 금융 원문 감사의 FAIL/UNVERIFIED를 PASS로 바꾸지 않는다.
