"""Prepare public ZIP and <30MB upload ZIPs from already verified CI artifacts.

Transport only: no engine/data/package modifications or re-execution. Manifest,
source revision, every transport part, original ZIP and both offline proofs are
checked before publication. All public byte checks are performed by the workflow.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from sandbox_bootstrap import load_manifest, hash_file, verify_file, safe_relative


def prepare(download: Path, preview: Path, proof311: Path, proof312: Path, output: Path, source_revision: str) -> dict:
    if output.exists():
        raise FileExistsError('public delivery directory must be new')
    # upload-artifact retains the ledger's delivery/ and parts/ parent folders.
    def unique_file(name):
        matches = [p for p in download.rglob(name) if p.is_file() and not p.is_symlink()]
        if len(matches) != 1:
            raise ValueError(f'expected exactly one verified transport metadata file: {name}')
        return matches[0]
    manifest_path = unique_file('kit_manifest.json')
    manifest = load_manifest(manifest_path)
    if manifest['source_revision'] != source_revision or manifest['versions']['performance_template_version'] != 'v2-18':
        raise ValueError('source/performance version does not match verified requested-report commit')
    if manifest['versions']['requested_report_contract_version'] != '1':
        raise ValueError('requested-report contract is not pinned')
    for proof,abi in ((proof311,'cp311'),(proof312,'cp312')):
        record = json.loads(proof.read_text())
        if record['status']!='passed' or record['runtime']!=abi or record['kit']['kit_id']!=manifest['kit_id'] or record['kit']['source_revision']!=source_revision:
            raise ValueError('offline ABI proof is missing or belongs to another kit')
        if not record['requested_report']['nav_unchanged'] or record['two_year_report_validation']['status']!='passed':
            raise ValueError('verified real reporting replay is required for both ABIs')
    browser = json.loads((preview/'browser-verification.json').read_text())
    if browser['status']!='passed' or not browser.get('rendered_hover'):
        raise ValueError('actual browser interaction verification did not pass')
    run = json.loads((preview/'run_status.json').read_text())
    if run['status']!='ok' or not run['nav_ready'] or not run['report_ready']:
        raise ValueError('preview must be a checked real-data report')
    ledger = json.loads(unique_file('download_manifest.json').read_text())
    if not re.fullmatch(r'quant-sandbox-[0-9a-f]{12}\.zip',ledger['zip_name']) or not 1<=len(ledger['segments'])<=32:
        raise ValueError('invalid delivery ledger')
    for entry in ledger['segments']:
        if not re.fullmatch(r'download\.part[0-9]{3}',entry['name']):
            raise ValueError('unsafe segment')
        verify_file(download,{'path':entry['name'],'bytes':entry['bytes'],'sha256':entry['sha256']})
    output.mkdir(parents=True)
    full = output/ledger['zip_name']
    digest = hashlib.sha256()
    with full.open('xb') as target:
        for entry in ledger['segments']:
            with (download/entry['name']).open('rb') as stream:
                while chunk:=stream.read(1024**2):
                    digest.update(chunk);target.write(chunk)
    if full.stat().st_size!=ledger['zip_bytes'] or digest.hexdigest()!=ledger['zip_sha256']:
        raise ValueError('reconstructed original ZIP mismatch')
    parts = output/'transport-source';parts.mkdir()
    expected = {'bootstrap_quant.py','kit_manifest.json','SANDBOX_START_HERE.md'}
    expected.update(p['path'] for a in manifest['archives'] for p in a['parts'])
    with zipfile.ZipFile(full) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or set(names)!=expected or archive.testzip():
            raise ValueError('original ZIP entries/CRC mismatch')
        for info in archive.infolist():
            safe_relative(info.filename)
            if info.filename!=Path(info.filename).name or ((info.external_attr>>16)&0o170000)==0o120000:
                raise ValueError('unsafe transport ZIP')
            with archive.open(info) as source,(parts/info.filename).open('xb') as target:
                shutil.copyfileobj(source,target,1024**2)
    if (parts/'kit_manifest.json').read_bytes()!=manifest_path.read_bytes():
        raise ValueError('embedded kit manifest differs from replay ledger')
    verify_file(parts,manifest['bootstrap'])
    entries=[]
    def record(path,kind):
        item={'name':path.name,'bytes':path.stat().st_size,'sha256':hash_file(path),'kind':kind}
        entries.append(item);return item
    def zipped(path,names):
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_STORED) as archive:
            for name in names:
                info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.external_attr=0o100644<<16;info.create_system=3
                with (parts/name).open('rb') as source,archive.open(info,'w') as target:
                    shutil.copyfileobj(source,target,1024**2)
        if path.stat().st_size>=30_000_000:
            raise ValueError('upload ZIP exceeds the requested 30MB limit')
        record(path,'upload_zip')
    setup=output/'quant-upload-setup.zip'
    zipped(setup,['bootstrap_quant.py','kit_manifest.json','SANDBOX_START_HERE.md'])
    for number,entry in enumerate((p for a in manifest['archives'] for p in a['parts']),1):
        verify_file(parts,entry)
        zipped(output/f'quant-upload-{number:03d}.zip',[entry['path']])
    report_file=preview/'report/report_CURRENT.html'
    for name,source,kind in [('report_CURRENT.html',report_file,'interactive_report'),
                              ('report-preview.png',preview/'report-preview.png','actual_browser_preview'),
                              ('browser-verification.json',preview/'browser-verification.json','browser_proof'),
                              ('report-preview-hover.png',preview/'report-preview-hover.png','actual_browser_hover'),
                              ('verification-cp311.json',proof311,'offline_proof'),('verification-cp312.json',proof312,'offline_proof')]:
        shutil.copyfile(source,output/name);record(output/name,kind)
    record(full,'original_kit_zip')
    installation = '''분할 업로드 방법
1. quant-upload-setup.zip과 모든 quant-upload-NNN.zip을 내려받아 Work 대화에 첨부합니다.
2. 실행 환경으로 각 ZIP을 가져와 새 폴더 하나에 모두 해제합니다. 내부 .partNNN의 이름을 유지합니다.
3. 지원 환경(CPython 3.11/3.12, Linux x86_64, glibc >=2.28)에서 SANDBOX_START_HERE.md를 읽습니다.
4. bootstrap_quant.py --parts-dir <해제 폴더> --destination <새 설치 폴더>를 실행합니다.
5. 설치된 전용 Python으로 sandbox_runtime.py verify를 실행합니다. hash 검사를 우회하지 않습니다.
6. config/strategies/kr_equity_report_validation_2019_2020.json을
   --report-periods config/reports/report_validation_periods.json으로 checked 실행합니다.
7. report/report_CURRENT.html은 실제 인터랙티브 결과입니다. 다운로드해 브라우저에서 열 수 있습니다.
예제는 실행·보고 소프트웨어 검증용이며 투자전략 채택·OOS·전체시장 검증이 아닙니다.
전체 ZIP은 같은 kit를 한 파일로 전달한 것입니다. 분할 ZIP과 동시에 첨부할 필요는 없습니다.
설치·실행에는 외부 다운로드가 필요하지 않습니다. 실제 세션의 호환성·도구 제한은 확인해야 합니다.
'''
    (output/'INSTALL_IN_WORK.txt').write_text(installation,encoding='utf-8');record(output/'INSTALL_IN_WORK.txt','instructions')
    public={'status':'prepared_from_verified_ci','kit_id':manifest['kit_id'],'source_revision':source_revision,
            'performance_template_version':'v2-18','requested_report_contract_version':'1',
            'tag':'quant-report-'+manifest['kit_id'][:12], 'files':entries,'upload_limit_bytes':30_000_000}
    (output/'public_delivery_manifest.json').write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.rmtree(parts)
    return public


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('download','preview','proof311','proof312','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-revision',required=True)
    args=p.parse_args()
    print(json.dumps(prepare(args.download,args.preview,args.proof311,args.proof312,args.output,args.source_revision),ensure_ascii=False,indent=2))
