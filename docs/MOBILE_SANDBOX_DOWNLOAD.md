# 휴대폰 실행 묶음 다운로드 복구 — 2026-10-03

사용자의 스크린샷으로 `/workspace/attachments/...zip` 링크가 모바일 ChatGPT에서
`파일을 열 수 없음`으로 실패한 것을 확인했다. 이 경로는 작업환경 파일 경로이며
실제로 내려받을 수 있는 HTTPS 첨부 링크가 아니었다. ZIP 생성/검증 완료와
사용자가 파일을 내려받을 수 있다는 것은 별도다.

기존 실제 ZIP은 291,308,667 bytes이고 SHA256은
`533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`이다.
파일 보존과 전체 SHA를 다시 확인했으며, 원격 성공 run `37075642412`의
12개 segment와 ledger artifact도 만료되지 않았다. 생성/패키지 설치/백테스트
검증/백필을 반복할 필요가 없다.

기존 Strategy DSL workflow에 **전달만 하는 mode**를 추가했다. 명시적
`download_existing_kit` 입력 또는 `deliver/mobile-download-*` branch에서만
기존 12개 artifact를 복원하고 전체 bytes/SHA/ZIP CRC/source revision/kit ID를
검증한 뒤, 원본 ZIP 하나를 담은 Actions artifact를 올린다. 이 mode는 기존
test/sandbox-replay jobs를 건너뛴다. 새 schedule/collector/engine은 없다.
Download step 5분, restore 2분, upload 3분, job 10분 상한이다.

Local workflow YAML, restore 코드 syntax, 전달 mode의 두 test-job skip 조건,
`git diff --check`를 확인했다. 현재 다음 단계는 remote commit → 전달-only
workflow 실제 완료 → 원본 ZIP을 포함하는 artifact의 HTTPS 링크 전달이다.

GitHub artifact URL은 로그인한 저장소 접근 권한으로 내려받는다. 다운로드 ZIP은
원본 `quant-sandbox-ee212da3e4a7.zip`을 안에 담는다. 다운로드 파일을 ChatGPT에
올린 뒤 내부 ZIP까지 풀어 bootstrap/verify하도록 요청하면 된다.
PR #27은 이전 취소 후 여전히 open이며, 이 복구 작업에서 취소된 merge를 재호출하지 않는다.
