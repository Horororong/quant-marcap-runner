# 3단계 재현과 중단 복구

기준 원격3f1ac4fd, 불변 원60 및2단계CI artifact11884849665(SHA ac3c3830dc66238b32354aa27dfd8ceb8388a60eed06b7f7c4da40419db8cd6b).
기존40/20 원본 packet/kit 복원은2단계의 restore_inputs.py/restore_holdout.py를 재사용한다.
로컬 실제 경로는 다음과 같다. 모든 금융 계산은 원 kit verify 후 수행한다.

~~~bash
STAGE3_PYTHON=/workspace/financial-repair/runtime/.venv/bin/python
$STAGE3_PYTHON -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
$STAGE3_PYTHON -I tests/test_financial_accuracy_repair.py
$STAGE3_PYTHON -I tests/test_financial_extraction_stage3.py
$STAGE3_PYTHON -I docs/audits/financial-repair-20261014/replay60.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --runtime /workspace/financial-repair/runtime --output /workspace/financial-repair/stage3/after-replay60
$STAGE3_PYTHON -I docs/audits/financial-extraction-stage3-20261014/revalidate.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --replay /workspace/financial-repair/stage3/after-replay60 --output docs/audits/financial-extraction-stage3-20261014/results
$STAGE3_PYTHON -I docs/audits/financial-extraction-stage3-20261014/forensic_compare.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --before-replay /workspace/financial-repair/stage3/before-replay60 --before-audit /workspace/financial-repair/stage3/before-audit --after-replay /workspace/financial-repair/stage3/after-replay60 --after-audit docs/audits/financial-extraction-stage3-20261014/results --output docs/audits/financial-extraction-stage3-20261014/results
$STAGE3_PYTHON -I docs/audits/financial-extraction-stage3-20261014/assert_stage3.py --replay /workspace/financial-repair/stage3/after-replay60 --results docs/audits/financial-extraction-stage3-20261014/results
~~~

독립 verifier는 생산 파서를 import하지 않고 원 ZIP/XML DOM과 불변 통제값/새로 직접 확인한 source_controls를 대조한다.
CF 순이익 채택은 같은 원문에서 별도의 확정된 순이익 셀을 읽는 방법이다.
N10 IS 결합셀을 다른 계산으로 나누지 않는다. 기존 raw/원본/감사결과는 그대로 보존한다.
518 보호 exact key=(receipt,metric,start,end,scope,basis).
565 전후 파일은 잘못된 옛 월초일/증명된 원문일/현재 목표일을 별도 열로 남긴다.

CI restore_before.py는 원2단계 result ZIP의SHA/크기/CRC를 확인해 before/replay60와 before/results를 복원한다.
실제 packet을 로컬에서도 내려받아60개 before 파일의 바이트 일치를 확인했다.
before 결과는 v7로 다시 생성하지 않는다.
2단계 원60 원본90일 artifact11885652249와 로컬 preserved-originals60.zip은 기존 증거다.
kit manifest/원래 source controls/선정/manifest의 SHA는 immutable_evidence_manifest.json.

실행 stdout/stderr/초기 실패는 results/evidence.
최초 신규 테스트에서 gross 대시인 경우까지 명시적 단독 순액을 지워야 한다고 잘못 기대해1건 실패(exit1).
원문 순액의 숫자는 확정돼 있으므로 구분되는 정상 사례로 assertion을 바로잡았다:
진짜 순액/총액 충돌은 보류, 단독 순액은 보존. 기존 실패 로그 보존 후17 신규 테스트 exit0.
원문 조회에서 S39:146 구통제 key가 없음을 KeyError(exit1)로 발견했다.
같은 오류를 반복하지 않고 원본 table146의 정정후 표제/단위/기간/열을 직접 확인해 새 supplemental 통제에 기록했다.
숫자 공백 경계/CF 운영 영역/자산 채권 의미 등 코드 변경마다 고정60을 다시 실행했다.
이는 원문 재수집/2000 재처리가 아니고 변경 후 회귀 확인이다.

재개시 원 kit verify→보존60/통제SHA 확인→이전2단계 artifact 복원→새 일반 규칙의 해당 boundary 테스트→고정60+독립대조 순서.
source SHA가 바뀌면 중단하고 다른 데이터/기간/계산 방식으로 대체하지 않는다.
전체pytest의 blocker는 원 kit의 의존성 부재다; 인터넷 설치/시스템Python 우회 금지.
메인/2000 전체 재처리/투자 입력 승격은 금지 상태를 유지한다.

CI 점검 최초 YAML [main]을 Python literal로 읽다가 ValueError/exit1이 발생했다. 금융 계산/원격 쓰기 전 오류다. 단순 YAML 목록은 비실행 문자열로 읽도록 원인을 수정하고, unsupported shape는 실패시키는 review_ci_triggers.py를 작성했다. 실제3 매칭 workflow와2 skip guard/1 원 offline kit 경로를 확인한 뒤 게시한다.
