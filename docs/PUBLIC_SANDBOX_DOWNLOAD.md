# 로그인 없는 실행 묶음 다운로드 복구 — 2026-10-03

사용자의 두 번째 screenshot에서 확인한 실패:

- oaiusercontent 서명 URL은 `Signed expiry time ... must be after signed start time`
  / `AuthenticationFailed`로 실패했다. 짧은 서명 링크를 재발급하는 방식은 최종 전달에 적합하지 않다.
- GitHub Actions artifact URL은 로그아웃 상태에서 404를 표시한다. 공개 저장소라도
  artifact 다운로드에 로그인은 필요하며, 익명 다운로드가 가능한 링크와는 다르다.

`Horororong/quant-marcap-runner`의 공개 여부와 admin/push 권한을 API로 직접 확인했다.
기존 검증 ZIP의 공개 코드·데이터·고정 wheel을 같은 공개 저장소의 release asset으로
전달한다. 저장소 공개 범위나 main을 바꾸지 않고, 취소된 PR #27 merge도 재시도하지 않는다.

기존 전달-only job에 명시적 public-download mode를 추가했다. 성공 run `37080822925`의
완성된 원본 ZIP을 내려받아 **291,308,667 bytes**, SHA256
`533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`, CRC, source commit와
kit ID를 다시 확인한다. 생성·백테스트·패키지 재현·수집은 실행하지 않는다.

Release는 `quant-sandbox-ee212da3e4a7`로, verified source `b350b61...`에 연결하고
prerelease/non-latest로 표시한다. 기존 release/asset이 있으면 재사용하며 크기/hash가
다르면 실패한다. 기존 asset/history를 삭제하거나 덮어쓰지 않는다.

업로드 후 **Authorization header 없이** release의 실제 browser_download_url을 GET하고
다운로드 전체 bytes와 SHA256까지 대조한다. 성공 확인 전에는 사용자에게 익명 다운로드
완료라고 알리지 않는다. 짧은 서명 URL은 문서/최종 링크로 사용하지 않는다.

현재 local YAML, Python/JS syntax와 test/sandbox jobs skip 조건, diff check 통과.
다음: remote commit → 전달-only 실행 → 익명 GET/bytes/SHA 확인 → release URL 전달.
Job 15분, download 5분, 복원 2분, publish/anonymous check 8분, 익명 GET 180초 한도다.


## 최종 완료: 실제 익명 다운로드 검증

- 전달 구현 commit `6d99daeff656042277bf75abff7adf73ce2a6f2d`, run `37081967124` / job `111084242487`
  **success**. Test/sandbox-replay jobs는 **skipped**다. 생성/백테스트/패키지 재현/백필을
  다시 하지 않았으며, 취소된 PR #27 merge도 재시도하지 않았다.
- 공개 release `quant-sandbox-ee212da3e4a7` (ID `402239704`, draft=false),
  원본 ZIP asset ID `606780546`, **291308667 bytes**.
- **Authorization header 없는 실제 GET**이 HTTP **200**을 반환했고, 전체 다운로드
  SHA256 `533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`가 원본과 일치했다.
- 최종 고정 다운로드 주소: https://github.com/Horororong/quant-marcap-runner/releases/download/quant-sandbox-ee212da3e4a7/quant-sandbox-ee212da3e4a7.zip
  로그인이나 단기 서명 URL이 필요 없다. Actions artifact의 30일 만료와 별도인
  공개 release asset이다. 기존 workspace/서명/artifact 링크를 최종 전달로 재사용하지 않는다.
- 이 파일은 안쪽 ZIP wrapper가 없는 원래 실행 ZIP이다. ChatGPT 퀀트 프로젝트의
  Python 실행 가능한 대화에 **그대로 첨부**하고 기존 bootstrap/verify를 사용한다.
- Machine checkpoint: `docs/audits/public-sandbox-download-checkpoint-20261003.json`.
