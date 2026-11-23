"""Python >=3.10, bibliothèque standard. Export CSV de contrats acceptés requis."""
import argparse,csv,hashlib,json,os,random,time,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--contrats',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);p.add_argument('--profil',choices=['propre','mixte'],default='propre');p.add_argument('--lots',type=int,default=2);p.add_argument('--intervalle',type=float,default=0);a=p.parse_args()
 if a.lots<1 or a.intervalle<0:p.error('lots positif et intervalle non négatif requis')
 with a.contrats.open(newline='',encoding='utf-8') as f:
  reader=csv.DictReader(f)
  if reader.fieldnames!=['contract_id']:raise ValueError('En-tête exact : contract_id')
  ids=sorted(set(int(r['contract_id']) for r in reader))
 if not ids or min(ids)<1:raise ValueError('Contrats positifs non vides requis')
 a.sortie.mkdir(parents=True,exist_ok=True);lock=a.sortie/'.lock'
 try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 except FileExistsError:raise SystemExit('Un générateur est actif, ou verrou résiduel à examiner.')
 try:
  os.close(fd);state=a.sortie/'campagne.json';sha=digest(a.contrats)
  if state.exists():meta=json.loads(state.read_text());assert meta['contrats_sha256']==sha,'Export modifié : nouvelle campagne nécessaire'
  else:
   meta={'campaign_id':str(uuid.uuid4()),'contrats_sha256':sha};tmp=a.sortie/'.campagne.tmp';tmp.write_text(json.dumps(meta));tmp.replace(state)
  # Les dossiers publiés font autorité après une panne entre publication et journalisation.
  existing=[int(x.name.split('-')[1]) for x in a.sortie.glob('lot-*') if x.is_dir()]
  start=max(existing,default=0)+1
  for n in range(start,start+a.lots):
   folder=a.sortie/f'.pending-{uuid.uuid4()}';folder.mkdir();rows=[]
   for i,kind in enumerate(['withdrawal','return','incident','failure','position']):
    event={'device_id':'sim-01','event_id':f'{meta["campaign_id"]}-{n:06d}-{i}','contract_id':ids[i%len(ids)],'event_type':kind,'observed_at':(datetime(2026,11,1,tzinfo=timezone.utc)+timedelta(minutes=n*10+i)).strftime('%Y-%m-%dT%H:%M:%SZ'),'payload':{'latitude':0.01,'longitude':0.02} if kind=='position' else {}}
    rows.append(event)
   if a.profil=='mixte':
    rows.append(dict(rows[0]));bad=dict(rows[0]);bad['event_type']='incident';rows.append(bad)
    for suffix,changes in [('late',{'observed_at':'2026-11-01T00:00:00Z'}),('unknown',{'contract_id':max(ids)+1000000}),('invalid',{'observed_at':'2026-02-30T00:00:00Z'})]:
     e=dict(rows[1]);e.update(changes);e['event_id']+='-'+suffix;rows.append(e)
   source=folder/'evenements.jsonl';source.write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in rows),encoding='utf-8')
   manifest={'schema_version':'campusequip-events-1','campaign_id':meta['campaign_id'],'batch_no':n,'profile':a.profil,'rows':len(rows),'files':{'evenements.jsonl':digest(source)},'contracts_sha256':sha}
   (folder/'manifest.json').write_text(json.dumps(manifest,indent=2));(folder/'READY').write_text('');folder.rename(a.sortie/f'lot-{n:06d}');print(json.dumps(manifest),flush=True)
   if a.intervalle:time.sleep(a.intervalle)
 except KeyboardInterrupt:print('Arrêt demandé ; lots publiés conservés.')
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
