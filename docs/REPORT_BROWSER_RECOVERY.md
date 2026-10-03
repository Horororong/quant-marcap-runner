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
결과: 실행 전. 미검증 항목을 통과로 표시하지 않음.
기존 미완료 게시 workflow와 delivery 스크립트는 수정하지 않고 보존.
