"""Read literal official DART viewer options without inventing version chains."""
from html.parser import HTMLParser
from datetime import date
import hashlib,re
from urllib.parse import parse_qs

class ViewerOptions(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.section=None;self.current=None;self.options=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='select':self.section=a.get('id')
        elif tag=='option'and self.section in {'family','att'}:
            self.current=dict(section=self.section,value=a.get('value',''),text='')
    def handle_data(self,data):
        if self.current is not None:self.current['text']+=data
    def handle_endtag(self,tag):
        if tag=='option'and self.current is not None:
            item=self.current;self.current=None
            if item['value']=='null':return
            q=parse_qs(item['value']);text=' '.join(item['text'].split());m=re.search(r'\b(\d{4})\.(\d{2})\.(\d{2})\b',text)
            day=date(*map(int,m.groups())).isoformat()if m else None
            self.options.append(dict(section=item['section'],receipt=q.get('rcpNo',[None])[0],document_id=q.get('dcmNo',[None])[0],date=day,label=text))
        elif tag=='select':self.section=None
def viewer_evidence(raw):
    p=ViewerOptions();p.feed(raw.decode('utf-8',errors='strict'))
    return dict(sha256=hashlib.sha256(raw).hexdigest(),options=p.options,
                exact_publication_time='UNVERIFIED',chain_certification='UNVERIFIED',
                warning='A parent filing date does not date every attachment. Similar titles or alertInvestNotice parameters do not certify a version chain.')
