# 151개 회귀 파일과 비교 예외21개 감사

|구분|수량|실제 처리·영향|
|---|---:|---|
|엄격 비교|130|선정·목표비중·체결schedule/trades·현금장부·NAV·CURRENT성과·정규화전략과fingerprint 등의 기존bytes 일치. 새기준생성0.|
|실행계획|6|세전략각2개. engine v2-16-exec-5→10, CA registry7→9, DSL machine25→30만 변경. 나머지키/값동일.|
|preflight|3|세전략각1개. source-only에서planned-readiness v2로구조변경. 원본130개의금융수치를예외로처리하지않음.|
|전체byte비교제외|12|세전략각postprocess.log/run_status.json/chat_manifest_CURRENT.json/report_CURRENT.html. 원래정책상비교제외이며 원본envelope12개의실제필드차이는미검증.|

## preflight 실제 변경

phase ready→planned_ready; 세version필드변경. contract/control_files/source_files/planned_selected_codes/planned_execution_schedule/signal_populations/issues/warnings/runtime_checks_still_required 추가. 전체패널distinct_codes(2443/2426/2797) 대신 planned code수(33/3/1)를표시하며 이를전체universe변경으로해석하지않는다. history_coverage를연도별annual구조로이동하고시장목록순서가변경됐다. 옛corporate_action_audit는제거되고planned노출검사/미인증범위문구로대체됐다. 모멘텀provider_coverage의signal_date표현이ISOtimestamp로변경됐고technical_lookback/history_files가추가됐다. 세전략모두strategy_fingerprint/requested_period/benchmark/factor_sources 및krx_panel actual_start/end/rows는동일하며 planned노출의issues는없다. 전체필드별before/after값은comparison-exceptions-21.json에있다. 원래comparator의preflight분기는몇개의핵심값만검사하므로모든preflight필드가단순버전차이라고부르지않는다.

## 12개 파일 목록과 한계

|파일|허용근거·실제확인|
|---|---|
|original/postprocess.log|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|original/report/chat_manifest_CURRENT.json|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|original/report/report_CURRENT.html|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|original/run_status.json|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|momentum2020/postprocess.log|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|momentum2020/report/chat_manifest_CURRENT.json|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|momentum2020/report/report_CURRENT.html|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|momentum2020/run_status.json|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|size2024/postprocess.log|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|size2024/report/chat_manifest_CURRENT.json|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|size2024/report/report_CURRENT.html|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|
|size2024/run_status.json|기존volatile_envelope_preserved_only 정책. 원본before-bytes 미확보로상세차이UNVERIFIED.|

chat_manifest와HTML에는성과·차트payload가실제로들어있어전부무해한메타데이터라고취급할수없다. 이번현재envelope감사에서HTML report-data=chat dashboard_payload, CURRENT성과840개값, longest의실제표시NAV14,155개점이각각canonicalCSV와정확히일치했다(허용오차0). 이는원본HTML과동일한화면/문구/전체byte임을보장하지않는다. 오래된원본envelope12개는artifact12118487392로추가대조해야한다.

원본작업공간없는원격전용전체복원시험은미실시이며이번에도반복하지않았다.
