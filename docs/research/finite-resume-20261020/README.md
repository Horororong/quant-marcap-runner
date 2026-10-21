# 有限 수집의 정상 분할·중단 재개

운영base a9da665e77eb06e09232c9fa1b382b1e3ea31d4f, 기존HOLD_FAILURE/checkpoint20100331002054를변경하지않는다. 대상run39504052321의57원문/871후보는별도연구감사에보존돼있다. 본변경은parser/diagnostic/source-owner6파일,기존원문/운영금융값과config상한을변경하지않는다.

문서100개를순차처리하며57개에599.507초를썼고0.492초를남기고58번째를시작한것이RUN_WALL_BUDGET원인이다. median9.834초,max28.286초. 원래로그에다운로드/파싱/검증/저장세부시간은없어이를추정하지않는다. 새timings/receipt.json과workerprogress의monotonic구간으로다운로드·파싱·검증·저장·대기·미계측시간을구분한다. 진행event사이의구간귀속이며CPU프로파일이라고표시하지않는다.

변경: 문서90초+종료reserve15초가남지않으면worker를시작하지않고PAUSED/YIELD로정상종료한다. max_documents로각segment를1..25건으로제한한다. 원문→result→collection/quality의순서와동일selection·hash·lease를검증한다. 부모SIGKILL은worker에도SIGTERM을보낸다. 새코드의resume=True는기존out의체크포인트를검증해완료건을건너뛰고,원문만있으면hash/CRC검사후HTTP없는cached replay로후보를완성한다. 손상·다른selection·비정상terminal상태는조용히재수집하지않고오류를낸다.

운영HOLD의자동해제는없다. 명시적인--resume-parent-run은마지막예약이RUN_WALL_BUDGET인경우에만허용하고새예약을하지않는다. day1회/최대3회에는재개segment도포함한다. 금융게시HOLD/backtestFalse/PIT0/6,source-ownerhash와최초독립review를유지한다. 기존예약100중남은43건을그대로사용한다. 기존실패기록은resume_segments에연결하고덮어쓰지않는다. 정상PAUSED는예약완료로잘못세지않는다.

검증: 기존rollout12시험,limited5시험,신규resume6시험. 실제SIGKILL후완료건재수집0/중복0/첫checkpoint변경0. 실제기존원문2건을오프라인1+1로재개해후보원본일치/HTTP0. 합성SIGKILL시험은금융값인증이아니다.

현재live2건은ONCE_PER_KST_DAY로차단돼신규HTTP0이다. 다음일일창2026-10-21T15:00Z 이후원격main/다른실행/예산을재확인하고본PR적용후기존workflow를한번dispatch한다:

gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f resume_parent_run=39504052321 -f batch_documents=2

이는남은3번째실행을쓴다. 이후추가배치는성공여부와예산을재검토해야하며이번승인만으로4회째실행하지않는다. 신규금융정확성·PIT인증0/원문수집재개와연구사용준비도는별개다.
