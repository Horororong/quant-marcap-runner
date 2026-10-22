# 현재 재개 위치

- 운영main18f5d064bc2e5f3a106a2a03603be3d5b5bbbf0a, PR47병합. 원래3/3소진,추가0/2·0/82잔여. parent39504052321/checkpoint20100331002063/41pending.
- 다음일일창10/24KST00:00이후모든실제gate를확인한뒤만수집. 예산재승인불필요. 자동스케줄추가설정없음.

```sh
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f resume_parent_run=39504052321 -f batch_documents=21 -f supplemental_approval=finite41-20261023
```

첫후속실행정상후다음허용KSTday에는20. 실제실패이면중단하고원인/상태를보존한다. 별도승인만료는10/25KST23:59:59,기존원래예산만료/이력은변경하지않았다. 연구branch로수집하거나ledger를리셋하지않는다.

연구작업공간/workspace/quant-parser-repair-20261021/code, branchresearch/legacy-bridge-20261023. 전용Python/원래kitverify유지. 완료된집계/소스검토는동일상태에서반복하지않는다. 변경시만새output사용:

```sh
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/inventory_legacy_provider_scope.py --output /workspace/NEW_UNIQUE_SCOPE --new-source-review /workspace/quant-finite-resume-20261023/NEW34_SOURCE_REVIEW.json --trial-source /workspace/quant-finite-resume-20261023/trial-source
```

새세션원문확보는고정56514a4631fc5d677af732e90b382fb5937504c6의data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/39863731314/manifest.json및sources00.json.gz.b64를사용한다. 압축SHA는manifest.transfers[0].compressed_sha256,filesbase64를새경로에안전하게풀고docZIP/memberSHA·CRC를확인한다. 원래2문서를다시DART수집하지않는다. 별도auditCLI는review_finite_source_fields.py --source-root <새해제폴더> --output <새경로>다.

1495raw필드요건/동일필드의서로다른값44+9그룹/정확한회계기간·정정/PIT원본보완이우선이다. 수집장부0/1495를줄이기위해완료조건을변경하지않는다. 사조Q3미승인단일자료확보안은REPORT.md에한정된다.
