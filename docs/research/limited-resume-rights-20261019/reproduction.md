# 재현

```bash
"$PY" -I "$RUNTIME/scripts/sandbox_runtime.py" verify
"$PY" -I -m unittest discover -s scripts -p test_subscription_rights.py -v
"$PY" -I -m unittest discover -s scripts -p 'test_stock_dividend*.py' -v
"$PY" -I docs/research/source-readiness-20261019/reproduce.py --check
```

기존 수식/기간정책/provider gate는 c811807의 그대로다. 신규 독립 장부는
합성 source/수량/현금만 사용한다. 실제 권리가격/처분/평가를 만들지 않는다.
공개 인터페이스 조사 Actions는 [rights-public-path] marker1회만 사용하며
마지막 증거 게시 commit에서 source job을 해당 완료 SHA로 봉인한다.
실제 가격 시계열 미확보는 UNVERIFIED, inspection job 성공은 접근 내용
보존 성공일 뿐이다. 기존 401 API 재요청0, 신규 금융/시세 원본 수정0.
