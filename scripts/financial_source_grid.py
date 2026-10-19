"""Independent literal source-cell view. No production financial parser import."""
from html.parser import HTMLParser
class Grid(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.tables=[];self.stack=[];self.cell=None;self.history=''
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=='table':
            self.tables.append(dict(index=len(self.tables),context=self.history[-1500:],rows=[]));self.stack.append(self.tables[-1])
        if tag=='tr' and self.stack:self.stack[-1]['rows'].append([])
        if tag in {'td','th','te'} and self.stack:self.cell=[]
    def handle_data(self,data):
        self.history+=' '+data
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in {'td','th','te'} and self.cell is not None:
            if self.stack and self.stack[-1]['rows']:self.stack[-1]['rows'][-1].append(' '.join(' '.join(self.cell).split()))
            self.cell=None
        if tag=='table' and self.stack:self.stack.pop()
