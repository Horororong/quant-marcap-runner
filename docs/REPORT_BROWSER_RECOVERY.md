# 보고 브라우저 복구 기록 · 2026-10-03

시작: 21:38:51 UTC. 종료 한도: 21:58:51 UTC. 동일 원인 수정·재검증 최대 2회.
기존 로컬 HEAD 91c9c10, 원격 구현 edcda2d990e40343d179b5ccbeceeb9b19dd04a7 보존.
현재 실행 프로세스 없음. 마지막 도구 호출은 12420.4초 후 사용자 취소.

원본 CI 37142451567 / job 111259574273: legendtoggle 클릭이 rangeslider-slidebox에 가려져 30초 timeout.
bash -e의 node | tee 파이프가 브라우저 오류를 숨겼음.
artifact 11281440104에는 PNG 없음, browser-verification.json 0바이트.

복구 1회: 범례를 위쪽 여백으로 이동. 엄격한 shell, 유한한 timeout, JSON/PNG 실물 검사.
기존 checked 보고 artifact의 canonical CSV와 manifest를 재사용; 엔진·백필·실행 묶음 재생성 안 함.
별도 제한시간 8분 브라우저 workflow로 실제 기간·표·세 그래프·범례·모바일 검증.
결과: 복구 1회에 실제 Chromium 통과. 아래 artifact 실물 검증 완료.
기존 미완료 게시 workflow와 delivery 스크립트는 수정하지 않고 보존.

원격 복구 커밋 58359b13aa2abe76b6bd25d6f27109f63a5e0198, run 37156156488.
실패 전달 음성 테스트: 가짜 node 종료 7이 wrapper 종료 7로 전달되고 failed JSON 보존, PNG 생성 없음. 소프트웨어 테스트이며 투자 검증이 아님.
기존 전체 CI sandbox replay는 missing-year 음성 테스트의 예상 종료 3 대신 4로 실패: 2019-04-30 t+1 체결 데이터 없음. 이번 PNG·브라우저 복구 범위 밖이며 해결·통과로 표시하지 않음.

## 완료 증거

2026-10-03 21:49 UTC 확인. run 37156156488 / job 111299836614 성공.
artifact 11286156835: browser-recovery-results, 2,146,091 bytes.
ZIP SHA256: 9bb221df03ddc0202d9df04b22ffb8e0cfbf30d9ad8a9a11d0cae723a97124a3.
실제 ZIP 다운로드 후 CRC 검사, PNG signature와 1280×2568 화면 확인.
report-preview.png 364,180 bytes; browser-verification.json 2,266 bytes, status passed.
3개 준비 기간의 실제 선택과 표·세 그래프 값/날짜·종료자산, 비용, 공유 확대, 범례 클릭, 모바일 폭, 데이터 부족 검사 통과.
- longest: 2019-01-02~2020-12-30, 비용 후 fixed_cost 종료자산 $17,459.13.
- from_2020: 2020-01-02~2020-12-30, $14,516.13.
- exact: 2020-05-12~2020-11-10, $12,438.02.
- from_2000: 데이터 부족; 표/차트 비움 검사.
원본 artifact의 daily NAV / metrics / benchmark CSV 바이트 동일; 계산 경로와 재무 검증 변경 없음.
Log 축과 hover용 실제 값의 브라우저 데이터 검증은 통과. 마우스 hover 팝업의 시각 검증은 별도 수행하지 않았음.

다운로드 한 번 ReadTimeout 후 한 번 재시도 성공. 반복 조회/무제한 대기 없음.
로컬 결과: /workspace/attachments/report-browser-recovery/verified-artifact/ 및 browser-recovery-results.zip.
GitHub 결과: https://github.com/Horororong/quant-marcap-runner/actions/runs/37156156488/artifacts/11286156835 (GitHub 로그인 필요, 2026-11-02 만료).

이번 범위 PNG·브라우저 복구 완료. 전체 실행 묶음은 기존 sandbox 음성 테스트 실패가 남아 신규 검증 ZIP 배포 완료로 표시하지 않음. main 병합 없음.
