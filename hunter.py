"""Scheduled public-job discovery. No login scraping or fabricated matches."""
import json, os, re, urllib.request, datetime, html
from pathlib import Path
ROOT=Path(__file__).parent
OUT=ROOT/'data'/'jobs.json'
UA={'User-Agent':'JobHunterDashboard/1.0 (personal job discovery)','Accept':'application/json'}
TITLES=['partner marketing','channel marketing','integrated marketing','field marketing','brand marketing','regional marketing','emea marketing','go-to-market','product marketing','strategic partnerships','sports marketing','marketing enablement','training and education','experiential marketing','lifestyle marketing']
POS=['partnership','marketing','go-to-market','brand','gtm','enablement','channel','product','sports','training','field','integrated','regional','emea','campaign','education']
SKILLS=['partnership','partner activation','go-to-market','gtm','brand','campaign','field marketing','channel','product launch','stakeholder','budget','agency','events','sports','consumer','b2b','training','education','sales enablement','international','emea','analytics','data','content','creative','community','creator','retail','marketing']
EXCLUDE=['intern','internship','werkstudent','working student','graduate trainee','junior','assistant','praktikant']
def get(url):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20) as r:return json.load(r)
 except Exception as e:print('Source unavailable:',url,str(e));return {}
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',str(s or '')))).strip()
def source_remotive():
 data=get('https://remotive.com/api/remote-jobs?category=marketing')
 for x in data.get('jobs',[]):
  yield dict(title=x.get('title',''),company=x.get('company_name',''),location=x.get('candidate_required_location',''),url=x.get('url',''),postedAt=x.get('publication_date','')[:10],description=clean(x.get('description','')),source='Remotive',salary=x.get('salary',''))
def source_arbeitnow():
 for page in (1,2,3):
  data=get('https://www.arbeitnow.com/api/job-board-api?page='+str(page))
  if not data.get('data'):break
  for x in data['data']:
   dt=datetime.datetime.fromtimestamp(x['created_at'],datetime.timezone.utc).date().isoformat() if x.get('created_at') else ''
   yield dict(title=x.get('title',''),company=x.get('company_name',''),location=x.get('location',''),url=x.get('url',''),postedAt=dt,description=clean(x.get('description','')),source='Arbeitnow',salary='')
def score(x):
 t=x['title'].lower();d=x['description'].lower();loc=x['location'].lower();combined=t+' '+d
 if not any(k in t for k in POS) or any(k in t for k in EXCLUDE):return None
 # Explicit German fluency requirements are hard filters, not soft scoring.
 if re.search(r'(c1|c2|native|fluent|business fluent|muttersprach|verhandlungssicher).{0,30}(german|deutsch)|(german|deutsch).{0,30}(c1|c2|native|fluent|business fluent|muttersprach|verhandlungssicher)',combined):return None
 remote='remote' in loc or 'anywhere' in loc or 'europe' in loc or 'worldwide' in loc
 german='germany' in loc or 'deutschland' in loc or 'munich' in loc or 'münchen' in loc or 'bavaria' in loc or 'berlin' in loc or 'hamburg' in loc
 if not (remote or german):return None
 # Exclude explicit remote location restrictions that do not include Germany/Europe.
 if remote and not german and any(z in loc for z in ['united states','usa only','canada only','uk only','united kingdom only','australia only']):return None
 hits=[k for k in SKILLS if k in combined];title_hits=[k for k in TITLES if k in t]
 if not title_hits:return None
 match=min(96,55+len(hits)*2+len(title_hits)*6)
 if match<80:return None
 return match,hits

def main():
 today=datetime.datetime.now(datetime.timezone.utc).date()
 old={}
 if OUT.exists():
  try:old={j['url']:j for j in json.loads(OUT.read_text()).get('jobs',[]) if j.get('url')}
  except Exception:pass
 found={}
 for x in list(source_remotive())+list(source_arbeitnow()):
  if not x['url'] or not x['company'] or not x['title']:continue
  if x['postedAt']:
   try:
    age=(today-datetime.date.fromisoformat(x['postedAt'])).days
    if age>14 or age<0:continue
   except ValueError:pass
  result=score(x)
  if not result:continue
  match,hits=result
  j={k:x[k] for k in ['title','company','location','url','postedAt','source','salary']}
  j.update(match=match,reason='Evidence in listing: '+', '.join(hits[:7]),gaps='Verify salary, German-language requirements, seniority and work eligibility; automated score is preliminary.',status=old.get(x['url'],{}).get('status','new'))
  found[x['url']]=j
 # retain prior matches so dashboard history is not lost
 for url,j in old.items():found.setdefault(url,j)
 jobs=sorted(found.values(),key=lambda j:(j.get('postedAt',''),j.get('match',0)),reverse=True)[:300]
 OUT.parent.mkdir(exist_ok=True,parents=True)
 OUT.write_text(json.dumps({'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'jobs':jobs,'sources':['Remotive','Arbeitnow'],'notice':'Public-source coverage only; matches are heuristic and require human verification.'},indent=2,ensure_ascii=False))
 print('Jobs in feed:',len(jobs))
if __name__=='__main__':main()
