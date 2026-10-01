# GPT Python 샌드박스 실행 묶음 v1

이 묶음은 한국어 요청을 GPT가 지원 capability와 aliases에 따라 Strategy DSL
JSON으로 작성하고, 저장소의 공통 엔진에서 검증하는 오프라인 실행 환경이다.
API 키, GitHub 로그인, 백필 수집기, 인터넷 다운로드는 필요 없다.
GPT가 생성한 JSON도 반드시 엄격한 입력 검증과 preflight를 통과해야 한다.

## 한 번 설치하기

완성된 `quant-sandbox-*.zip`을 Python 파일 도구가 있는 GPT 대화에 올린다.
파일이 크면 `bootstrap_quant.py`, `kit_manifest.json`, 모든 `*.partNNN` 파일을
같은 폴더에 올린다. 실제 업로드·실행 한도는 해당 GPT 세션에서 확인한다.
지원 환경은 CPython **3.11 또는 3.12, Linux x86_64, glibc ≥ 2.28**이다.
설치할 Python ABI용 wheel이 manifest에 있어야 한다. 다른 환경은 명시적으로
실패하며 인터넷 설치나 임의 패키지 업그레이드로 우회하지 않는다.

GPT의 Python 도구에서 다음 절차를 수행한다. ZIP은 이름과 SHA256을 확인하고
새 폴더에 해제한다. ZIP 파일과 설치 폴더를 결과 폴더와 구분한다.

```python
import sys, subprocess, json
from pathlib import Path
parts = Path('/mnt/data/quant_parts')  # 첨부 ZIP을 해제한 폴더
installed = Path('/mnt/data/quant_runtime')  # 반드시 새 폴더
process = subprocess.run([
    sys.executable, str(parts / 'bootstrap_quant.py'),
    '--parts-dir', str(parts), '--destination', str(installed)
], capture_output=True, text=True)
assert process.returncode == 0, process.stdout + process.stderr
ready = json.loads(process.stdout)
python = ready['python']
runner = str(installed / 'scripts/sandbox_runtime.py')
```

**GPT의 기존 Python 커널에서 엔진 모듈을 직접 import하지 않는다.** 설치된
전용 Python을 subprocess로 호출해야 고정 패키지가 사용된다. `verify`는 코드,
데이터 hash, 계약 버전, 실제 설치 패키지를 확인하고 포함 coverage를 반환한다.

```python
subprocess.run([python, '-I', runner, 'verify'], check=True)
```

## 한국어 요청을 실행하는 규칙

1. `config/strategy_dsl_capabilities_v1.json`, `config/strategy_dsl_schema_v1.json`,
   `scripts/strategy_dsl_aliases.py`와 manifest의 coverage를 먼저 읽는다.
2. 지원하지 않는 조건은 `capability_gap`으로 설명한다. 일반 PER·ROE를 기존
   분기 PER 프록시·분기 ROE로 바꾸지 않는다. 회계기간, 방향, 비용, 리밸런싱,
   체결, 분석기간이 결과에 영향을 주는 모호성은 사용자에게 확인한다.
3. 요청을 보존한 DSL JSON과 해석을 보여 주고 JSON 파일에 저장한다.
   새 요청은 예를 들어 `/mnt/data/requests/strategy.json`에 저장한다.
   실행 코드·원자료·registry·패키지를 고치지 않는다.
4. 아래 **공통 checked 실행 명령**을 호출한다. 입력 오류는 데이터 로드 전에
   차단한다. 지원하지만 필요한 자료가 없으면 `data_gap`이다. 누락값을 0이나
   forward-fill로 채우거나 요청 기간·universe를 줄이지 않는다.
5. 반환 JSON과 `run_status.json`의 `status`, `nav_ready`, `report_ready`를 확인한다.
   `ok`/`nav_ready=true`만 검증된 NAV를 뜻한다. `report_ready=true`인 CURRENT
   결과만 표준 성과라고 보고한다. 오류·갭은 원인을 설명하고 수치를 만들지 않는다.

```python
p = subprocess.run([python, '-I', runner, 'run', '/mnt/data/requests/strategy.json',
                    '--execution-only', '--output-dir', '/mnt/data/run_001'],
                   capture_output=True, text=True)
result = json.loads(p.stdout)
```

`--execution-only`는 명시적인 연구 NAV 실행이다. 현재 기본 예제처럼 짧은
구간에는 이 옵션을 사용하고 **CAGR·MDD·Sharpe 등을 GPT나 별도 코드로 계산하지
않는다**. 옵션을 생략하면 기존 CURRENT 4기간·9차트 정식 보고 경로를 사용하며,
필요한 기간이 부족하면 실행 전에 `data_gap`으로 실패한다. 요청 기간 전용
CURRENT 연구 보고는 다음 milestone이다. 실행 디렉터리는 매번 새로 만들며,
기존 결과를 덮어쓰지 않는다.

## 기본 포함 범위와 한계

- 원본 KRX **2020·2024 전체 연도** PIT 패널. 현재 상장 종목 필터로 축소하지 않았다.
- DART **2019 Q3/FY, 2020 Q1/H1** 전체 원본 shard, 역사적 코드 매핑, backfill 상태.
  실제 공시 가용일, CFS 우선/OFS 대체, 모집단 coverage는 기존 provider가 검사한다.
- 원본 KOSPI 가격지수, 검증된 기업행동 registry와 알려진 미해결 event 목록.
- 예제: `super_value_dart_benchmark_dsl.json` (2020-04~11),
  `kr_equity_size_deciles_research.json` (2020-04~05),
  `kr_equity_split_research.json` (2024-03~04).
- capability catalog는 엔진 표현 능력이다. 모든 기간·팩터의 데이터가 이 묶음에
  들어 있다는 뜻은 아니다. 기술 팩터의 과거 warm-up 자료, 다른 DART 기간,
  다른 연도 자료가 필요한 요청은 preflight에서 확인한다.
- 알려진 기업행동의 외부 지급 증거가 부족하면 영향받는 보유종목의 실행을 막는다.
  과거 universe에서 종목을 빼서 통과시키지 않는다.

## 결과 내려받기

```python
subprocess.run([python, '-I', runner, 'export', result['output_dir'],
                '--output', '/mnt/data/backtest_result.zip'], check=True)
```

결과 ZIP에는 원본/정규화 DSL, preflight·readiness·상태, kit와 실행 manifest,
검증된 NAV·선정·매매·기업행동·held-return audit, 성공 시 CURRENT 결과가 들어간다.
실패 결과도 진단용으로 export할 수 있으며 성공 결과로 표시하지 않는다.
미검증 `_execution`/`_report` staging은 export하지 않는다. export 전에 산출물 hash를
확인한다. 결과 ZIP에 원자료나 wheel을 중복 저장하지 않는다.

소스 commit, 모든 데이터 SHA256, 계약 버전, Python·패키지 버전, DSL fingerprint로
재현 조건을 확인한다. hash는 파일 훼손 검출용이며 manifest 자체의 전자서명은 아니다.
신뢰하는 Codex/저장소에서 받은 묶음을 사용한다. Codex main 갱신은 이미 설치한
GPT 묶음을 바꾸지 않는다. 자료 범위를 넓히려면 Codex에서 새 묶음을 만든다.

## 대화 시작 문구

> 첨부된 quant sandbox 묶음을 SANDBOX_START_HERE.md에 따라 전용 Python으로
> 설치·검증해. 이후 내 한국어 전략 요청은 capability와 aliases를 확인해 DSL로
> 보여 주고 공통 checked runner로 실행해. unsupported·모호성·data gap을 임의로
> 대체하지 말고 설명해. 짧은 구간은 검증된 연구 NAV만 보고하고 결과 ZIP을 줘.

## Codex에서 새 묶음 만들기

코드 변경을 테스트하고 commit한 **깨끗한 tree**에서 수행한다. 수집기나 결과
history를 묶지 않는다. 생성 파일은 Git에 저장하지 않는다.

```bash
python scripts/prepare_sandbox_wheels.py --output-dir /tmp/quant-wheels
python scripts/build_sandbox_kit.py --wheels-dir /tmp/quant-wheels --output-dir dist/sandbox/kit-v1
```

`--runtime-target cp311` 또는 `cp312`로 크기를 줄일 수 있다. `--strategy`에 저장소의
검증된 DSL 경로를 여러 번 지정하면 그 전략의 전체 연도 패널과 DART 기간을
추가한다. 기술 팩터는 2년 전부터 signal 연도까지 원본 패널을 포함한다.
다른 coverage를 추가한 kit도 별도 replay 검증을 해야 한다.
