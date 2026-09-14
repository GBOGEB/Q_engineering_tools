#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from numpy.linalg import eigh, eigvalsh, inv
from scipy.stats import chi2, spearmanr

FEATURES=["typographic_hierarchy","whitespace_grid","figure_quality","table_readability","colour_discipline","diagram_consistency","branding_restraint","captions_citations","metadata_versioning","export_print_fidelity","information_density","executive_legibility"]
FORMATS=["HTML","PDF","PPTX","XLSX"]
REQUIRED=["observation_id","artifact_id","artifact_format","artifact_version_or_snapshot","source_hash","render_locator_page_slide_sheet_view","render_hash","review_timestamp","reviewer_or_validator","content_parity_pass","visual_release_eligible",*FEATURES]
SOURCE_LOCATOR="source_locator_page_slide_sheet_view"
REGISTRY_NAME="QPS_VISUAL_REPLACEMENT_ASSET_REGISTRY_v0.2.yaml"

def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def fail(msg): raise SystemExit(msg)

def metrics(d):
    X=d[FEATURES].to_numpy(float); n,p=X.shape
    Z=(X-X.mean(0))/X.std(0,ddof=1); R=np.corrcoef(Z,rowvar=False); Ri=inv(R)
    P=np.empty_like(R)
    for i in range(p):
        for j in range(p): P[i,j]=1.0 if i==j else -Ri[i,j]/math.sqrt(Ri[i,i]*Ri[j,j])
    r2=np.sum(np.triu(R,1)**2); p2=np.sum(np.triu(P,1)**2); kmo=float(r2/(r2+p2))
    msa=[]
    for i in range(p):
        rr=np.delete(R[i]**2,i).sum(); pp=np.delete(P[i]**2,i).sum(); msa.append(float(rr/(rr+pp)))
    det=float(np.linalg.det(R)); bc=float(-(n-1-(2*p+5)/6)*np.log(det)); bdf=p*(p-1)//2; bp=float(chi2.sf(bc,bdf))
    vals,vecs=eigh(R); order=np.argsort(vals)[::-1]; vals,vecs=vals[order],vecs[:,order]; load=vecs*np.sqrt(vals)
    for j in range(p):
        if load[:,j].sum()<0: load[:,j]*=-1
    scores=Z@vecs; means=X.mean(0); pressure=.7*(10-means)+.3*np.abs(load[:,0])*10
    ranks=np.empty(p,int)
    for pos,i in enumerate(np.argsort(pressure)[::-1],1): ranks[i]=pos
    return dict(X=X,Z=Z,R=R,eigenvalues=vals,loadings=load,scores=scores,means=means,pressure=pressure,ranks=ranks,KMO=kmo,MSA=msa,bartlett_chi2=bc,bartlett_df=bdf,bartlett_p=bp)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--impl-dir',type=Path,default=Path(__file__).resolve().parent); a=ap.parse_args(); impl=a.impl_dir.resolve()
    shards=[impl/f"QPS_VISUAL_CENSUS_RAW_PROVENANCE_N112_{f}.csv" for f in FORMATS]
    for p in shards:
        if not p.is_file(): fail(f"missing input shard: {p}")
    registry_path=impl/REGISTRY_NAME
    if not registry_path.is_file(): fail(f"missing replacement registry: {registry_path}")
    raw=pd.concat([pd.read_csv(p) for p in shards],ignore_index=True)
    missing=[c for c in REQUIRED if c not in raw.columns]
    if missing: fail(f"missing required columns: {missing}")
    for c in REQUIRED[:9]:
        if raw[c].isna().any() or raw[c].astype(str).str.strip().eq('').any(): fail(f"blank required identity/provenance value in {c}")
    if raw['observation_id'].duplicated().any(): fail('duplicate observation_id in raw census')
    eligible=raw[raw['content_parity_pass'].astype(str).str.lower().eq('true') & raw['visual_release_eligible'].astype(str).str.lower().eq('true')].copy()
    if len(raw)!=112 or len(eligible)!=112: fail(f"population gate failed raw={len(raw)} eligible={len(eligible)}")
    numeric=eligible[FEATURES].apply(pd.to_numeric,errors='coerce')
    if numeric.isna().any().any(): fail('raw feature missing/non-numeric value found before aggregation')
    if ((numeric<0)|(numeric>10)).any().any(): fail('raw feature outside 0..10 range')
    eligible[FEATURES]=numeric
    eligible['artifact_key']=eligible['artifact_format'].astype(str)+'::'+eligible['artifact_id'].astype(str)

    reg=yaml.safe_load(registry_path.read_text(encoding='utf-8'))
    expected_ids=[str(x) for x in reg.get('expected_observation_ids',[])]
    assets={str(x['observation_id']):x for x in reg.get('assets',[])}
    if len(expected_ids)!=9 or len(set(expected_ids))!=9: fail('registry expected_observation_ids must contain exactly nine unique IDs')
    if set(assets)!=set(expected_ids): fail('registry assets must exactly match expected_observation_ids')
    if SOURCE_LOCATOR not in eligible.columns: fail(f"raw census missing {SOURCE_LOCATOR}")
    census_expected=eligible[eligible['observation_id'].isin(expected_ids)]
    if set(census_expected['observation_id'])!=set(expected_ids) or len(census_expected)!=9: fail('census does not contain exactly the complete nine-row replacement set')
    registered_artifacts={(a['artifact_format'],a['artifact_id']):oid for oid,a in assets.items()}
    for _,row in eligible.iterrows():
        key=(str(row['artifact_format']),str(row['artifact_id']))
        if key in registered_artifacts and str(row['observation_id'])!=registered_artifacts[key]: fail(f"replacement observation ID bypass for artifact {key}")
    extra_rep=set(eligible[eligible['observation_id'].astype(str).str.contains('-REP-',regex=False)]['observation_id'])-set(expected_ids)
    if extra_rep: fail(f"unregistered replacement-like observation IDs: {sorted(extra_rep)}")
    gate={'expected_rows':9,'rows_checked':0,'source_registry_mismatch':0,'render_registry_mismatch':0,'missing_locator':0,'artifact_identity_mismatch':0}
    for oid in expected_ids:
        row=eligible.loc[eligible['observation_id'].eq(oid)].iloc[0]; asset=assets[oid]; gate['rows_checked']+=1
        if str(row['artifact_id'])!=str(asset['artifact_id']) or str(row['artifact_format'])!=str(asset['artifact_format']): gate['artifact_identity_mismatch']+=1; fail(f"replacement artifact identity mismatch for {oid}")
        source=asset['source']; render=asset['review_render']; sl=str(row[SOURCE_LOCATOR]); rl=str(row['render_locator_page_slide_sheet_view'])
        if not sl or not rl or sl=='nan' or rl=='nan': gate['missing_locator']+=1; fail(f"replacement locator missing for {oid}")
        if sl!=str(source['row_locator']) or str(row['source_hash'])!=str(source['sha256']): gate['source_registry_mismatch']+=1; fail(f"replacement exact source locator/hash mismatch for {oid}")
        if rl!=str(render['row_locator']) or str(row['render_hash'])!=str(render['sha256']): gate['render_registry_mismatch']+=1; fail(f"replacement exact render locator/hash mismatch for {oid}")
    if gate['rows_checked']!=9: fail('replacement gate did not check all nine rows')

    if eligible.duplicated(['artifact_key','render_hash']).any(): fail('duplicate render_hash within statistical artifact')
    if eligible.duplicated(['artifact_key','render_locator_page_slide_sheet_view']).any(): fail('duplicate render locator within statistical artifact')
    if eligible.duplicated(['artifact_key','observation_id']).any(): fail('duplicate observation within statistical artifact')
    duplicate_gate={}
    for col in ['render_hash','source_hash']:
        g=eligible.groupby(col)['artifact_key'].nunique(); bad=g[g>1]; duplicate_gate[col]=int(len(bad))
        if len(bad): fail(f"duplicate {col} across distinct statistical artifact keys: {bad.to_dict()}")

    artifact=eligible.groupby(['artifact_format','artifact_id'],as_index=False)[FEATURES].mean().sort_values(['artifact_format','artifact_id']).reset_index(drop=True)
    artifact.insert(0,'derived_observation_id',[f'P{i:03d}' for i in range(1,len(artifact)+1)])
    counts=artifact['artifact_format'].value_counts().to_dict(); expected={f:25 for f in FORMATS}
    if len(artifact)!=100 or counts!=expected: fail(f"artifact balance gate failed N={len(artifact)} counts={counts}")
    if artifact[FEATURES].isna().any().any(): fail('artifact feature missingness after aggregation')

    matrix=impl/'QPS_VISUAL_CENSUS_DERIVED_ARTIFACT_N100.generated.csv'; loadp=impl/'QPS_VISUAL_PCA_PROVENANCE_N100_LOADINGS_BT.csv'; eigp=impl/'QPS_VISUAL_PCA_PROVENANCE_N100_EIGEN.csv'; convp=impl/'QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv'; recp=impl/'QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json'
    artifact.to_csv(matrix,index=False); m=metrics(artifact); p=len(FEATURES)
    load_df=pd.DataFrame({'dimension':FEATURES,'mean_maturity':m['means'],'PC1_loading':m['loadings'][:,0],'PC2_loading':m['loadings'][:,1],'PC3_loading':m['loadings'][:,2],'reverse_BT_pressure':m['pressure'],'reverse_BT_rank':m['ranks'],'MSA':m['MSA']}); load_df.to_csv(loadp,index=False)
    rng=np.random.default_rng(777); pa={}
    for n in [60,80,100]:
        E=np.empty((5000,p))
        for s in range(5000):
            Y=rng.standard_normal((n,p)); Y=(Y-Y.mean(0))/Y.std(0,ddof=1); E[s]=eigvalsh(np.corrcoef(Y,rowvar=False))[::-1]
        pa[n]=np.quantile(E,.95,axis=0)
    pd.DataFrame({'component':np.arange(1,p+1),'eigenvalue':m['eigenvalues'],'explained_pct':m['eigenvalues']/p*100,'cumulative_pct':np.cumsum(m['eigenvalues'])/p*100,'parallel95':pa[100],'retained_PA95':m['eigenvalues']>pa[100]}).to_csv(eigp,index=False)
    full_load,full_rank=m['loadings'][:,0],m['ranks']; rng=np.random.default_rng(20260913); conv=[]
    for per_fmt in [15,20,25]:
        n=per_fmt*4; reps=1 if per_fmt==25 else 500; arr=[]
        for _ in range(reps):
            parts=[]
            for fmt in FORMATS:
                g=artifact[artifact['artifact_format']==fmt]; idx=rng.choice(g.index,per_fmt,replace=False); parts.append(artifact.loc[idx])
            sm=metrics(pd.concat(parts)); l=sm['loadings'][:,0]
            if np.dot(l,full_load)<0: l=-l
            cong=float(np.dot(l,full_load)/np.sqrt(np.dot(l,l)*np.dot(full_load,full_load))); rho=float(spearmanr(sm['ranks'],full_rank).statistic)
            arr.append([sm['KMO'],sm['eigenvalues'][0]/p*100,sm['eigenvalues'][1],cong,rho,float(sm['eigenvalues'][1]>pa[n][1])])
        A=np.asarray(arr); conv.append({'N':n,'per_format':per_fmt,'reps':reps,'KMO_median':float(np.median(A[:,0])),'KMO_p05':float(np.quantile(A[:,0],.05)),'KMO_p95':float(np.quantile(A[:,0],.95)),'PC1_pct_median':float(np.median(A[:,1])),'PC1_pct_p05':float(np.quantile(A[:,1],.05)),'PC1_pct_p95':float(np.quantile(A[:,1],.95)),'PC2_eigen_median':float(np.median(A[:,2])),'PA95_PC2_threshold':float(pa[n][1]),'PC2_retention_fraction':float(A[:,5].mean()),'PC1_congruence_to_N100_median':float(np.median(A[:,3])),'PC1_congruence_p05':float(np.quantile(A[:,3],.05)),'BT_spearman_to_N100_median':float(np.median(A[:,4])),'BT_spearman_p05':float(np.quantile(A[:,4],.05))})
    pd.DataFrame(conv).to_csv(convp,index=False)
    pc1=m['scores'][:,0]; pc1z=(pc1-pc1.mean())/pc1.std(ddof=1); keep=np.abs(pc1z)<=3; sens=1.0
    if 30<=keep.sum()<len(artifact):
        ms=metrics(artifact.loc[keep]); l=ms['loadings'][:,0]
        if np.dot(l,full_load)<0:l=-l
        sens=float(np.dot(l,full_load)/np.sqrt(np.dot(l,l)*np.dot(full_load,full_load)))
    outputs=[matrix,loadp,eigp,convp]; inputs={x.name:sha256(x) for x in shards}; inputs[registry_path.name]=sha256(registry_path)
    receipt={'schema':'qps-visual-pca-generation-receipt/0.2','status':'PASS_FAIL_CLOSED_SCHEMA_0_4','raw_rows':len(raw),'eligible_rows':len(eligible),'artifact_N':len(artifact),'format_counts':counts,'features':FEATURES,'raw_feature_completeness_pct':100.0,'statistical_artifact_key':'artifact_format::artifact_id','duplicate_gate':duplicate_gate,'within_artifact_duplicate_gate':{'duplicate_observation_id':0,'duplicate_render_hash':0,'duplicate_render_locator':0},'replacement_asset_gate':gate,'adequacy':{'KMO':m['KMO'],'MSA':dict(zip(FEATURES,m['MSA'])),'minimum_MSA':min(m['MSA']),'minimum_MSA_dimension':FEATURES[int(np.argmin(m['MSA']))],'bartlett_chi_square':m['bartlett_chi2'],'bartlett_df':m['bartlett_df'],'bartlett_p_value':m['bartlett_p']},'PCA':{'eigenvalues':m['eigenvalues'].tolist(),'explained_pct':(m['eigenvalues']/p*100).tolist(),'parallel95_N100':pa[100].tolist(),'retained_PA95':(m['eigenvalues']>pa[100]).tolist()},'reverse_BT':load_df.sort_values('reverse_BT_rank')[['dimension','reverse_BT_pressure','reverse_BT_rank']].to_dict('records'),'convergence':conv,'sensitivity_without_extreme_PC1_score_outliers':{'rule':'abs(full_PC1_score_z)>3 excluded','excluded_count':int((~keep).sum()),'retained_count':int(keep.sum()),'PC1_loading_congruence_to_full':sens},'randomness':{'parallel_analysis_seed':777,'parallel_analysis_simulations_per_N':5000,'parallel_stream_order':[60,80,100],'balanced_sampling_seed':20260913},'inputs_sha256':inputs,'outputs_sha256':{x.name:sha256(x) for x in outputs}}
    recp.write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'KMO':m['KMO'],'minimum_MSA':min(m['MSA']),'PC1_pct':receipt['PCA']['explained_pct'][0],'PC2_pct':receipt['PCA']['explained_pct'][1],'PC3_pct':receipt['PCA']['explained_pct'][2],'replacement_asset_gate':gate,'inputs_sha256':inputs,'outputs_sha256':receipt['outputs_sha256'],'generation_receipt_sha256':sha256(recp)},indent=2))
if __name__=='__main__': main()
