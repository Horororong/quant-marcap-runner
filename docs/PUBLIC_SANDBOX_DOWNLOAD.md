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
