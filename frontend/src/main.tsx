import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type Any = Record<string, any>;
const fieldLabels: Any = {order_id:'Order identifier',line_id:'Line identifier',product:'Ordered product',quantity:'Ordered quantity',unit:'Order unit',status:'Order / shipping status',date:'Order date'};
const groups: Any = {fields:'Field meanings and source columns',statuses:'Included, excluded and unknown statuses',products:'SKU matching and confirmed aliases',units:'Master conversions and unit mappings',duplicates:'Business key and missing-line handling',output:'Warehouse template and output columns'};
const initialInstructions = 'Combine confirmed, unshipped orders from these channels. Match the product master, prevent duplicate counting, hold unknown products and units in an exception sheet, and prepare the warehouse template.';

async function api(path:string, options:Any = {}) {
  const {body,...rest} = options;
  const response = await fetch('/api'+path,{...rest,headers: body instanceof FormData ? {} : {'Content-Type':'application/json'},body:body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body)});
  if (!response.ok) {
    const value = await response.json().catch(()=>({detail:'The local server could not complete this request.'}));
    throw new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail));
  }
  return response.json();
}
function Icon({name='arrow',size=20}:{name?:string,size?:number}) {
 const paths:Any={
  arrow:<><path d="M4 12h15M13 6l6 6-6 6"/></>,
  file:<><path d="M6 3h8l4 4v14H6zM14 3v5h5M9 12h6M9 16h6"/></>,
  check:<path d="m5 12 4 4L19 6"/>,
  upload:<><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/></>,
  history:<><path d="M4 5v5h5M4 10a8 8 0 1 1 1 8M12 7v5l3 2"/></>,
  close:<path d="m6 6 12 12M6 18 18 6"/>,
  box:<><path d="m3 7 9-4 9 4v11l-9 4-9-4zM3 7l9 5 9-5M12 12v10"/></>,
  branch:<><path d="M7 4v13a3 3 0 1 0 3-3H7m0-4h7a3 3 0 0 0 3-3V4"/><circle cx="7" cy="3" r="2"/><circle cx="17" cy="3" r="2"/></>
 };
 return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]||paths.arrow}</svg>;
}
function Badge({children,tone='neutral'}:any){return <span className={'badge '+tone}>{children}</span>}
function App(){
 const [health,setHealth]=useState<Any>({});
 const [state,setState]=useState<Any>({flows:[],batches:[],runs:[],activity:[]});
 const [page,setPage]=useState('files');
 const [batch,setBatch]=useState<Any|null>(null);
 const [flow,setFlow]=useState<Any|null>(null);
 const [origin,setOrigin]=useState('manual');
 const [instructions,setInstructions]=useState(initialInstructions);
 const [draftInfo,setDraftInfo]=useState<Any|null>(null);
 const [report,setReport]=useState<Any|null>(null);
 const [reviewed,setReviewed]=useState<string[]>([]);
 const [run,setRun]=useState<Any|null>(null);
 const [rows,setRows]=useState<Any[]>([]);
 const [rowTotal,setRowTotal]=useState(0);
 const [disposition,setDisposition]=useState('included');
 const [query,setQuery]=useState('');
 const [selected,setSelected]=useState<Any|null>(null);
 const [busy,setBusy]=useState('');
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [preview,setPreview]=useState<Any|null>(null);
 const [staging,setStaging]=useState<Any[]>([]);
 const [alias,setAlias]=useState('');
 const [aliasSku,setAliasSku]=useState('TEA-001');
 const [unitFrom,setUnitFrom]=useState('carton');
 const [unitTo,setUnitTo]=useState('box');
 const [ack,setAck]=useState(false);
 const [handoff,setHandoff]=useState<Any|null>(null);
 const reload=async()=>{setState(await api('/state'));setHealth(await api('/health'));};
 useEffect(()=>{reload().catch(e=>setError(e.message));},[]);
 useEffect(()=>{
   if(!run?.id || run.status!=='completed')return;
   let cancelled=false;
   const timeout=setTimeout(()=>api('/runs/'+run.id+'/rows?disposition='+encodeURIComponent(disposition)+'&query='+encodeURIComponent(query)).then(value=>{
     if(!cancelled){setRows(value.rows);setRowTotal(value.total);}
   }).catch(e=>{if(!cancelled)setError(e.message)}),150);
   return()=>{cancelled=true;clearTimeout(timeout);};
 },[run?.id,run?.status,disposition,query]);
 const act=async(label:string,fn:()=>Promise<void>)=>{setBusy(label);setError('');setNotice('');try{await fn();}catch(e:any){setError(e.message);}finally{setBusy('');}};
 const change=(fn:(next:Any)=>void)=>{const next=structuredClone(flow);fn(next);setFlow(next);setReviewed([]);setReport(null);};
 const inspect=async(spec=flow, target=batch)=>{
   const value=await api('/batches/'+target.id+'/preflight',{method:'POST',body:spec});setReport(value);return value;
 };
 const loadWeek=(week:number)=>act('Reading synthetic week '+week,async()=>{
   const value=await api('/demo/load',{method:'POST',body:{week}});
   setBatch(value);setPreview(value.files[0]);setRun(null);setSelected(null);setReport(null);setReviewed([]);setDraftInfo(null);setAck(false);setHandoff(null);
   const previous=flow || state.flows[0]?.spec;
   const draft=await api('/batches/'+value.id+'/plan',{method:'POST',body:{mode:'suggested',...(previous?{flow:previous}:{})}});
   setFlow(draft.flow);setOrigin(previous?'saved_flow':'suggested_setup');setDraftInfo(draft);
   await reload();setPage('files');setNotice('Synthetic files were read by the real parser. Review the plan before processing.');
 });
 const plan=(mode:string)=>act(mode==='live'?'Requesting an AI workflow draft':'Preparing editable field suggestions',async()=>{
   const draft=await api('/batches/'+batch!.id+'/plan',{method:'POST',body:{mode,instructions,...(flow?{flow}:{})}});
   setFlow(draft.flow);setOrigin(draft.origin);setDraftInfo(draft);setReviewed([]);setReport(null);setPage('plan');
 });
 const openBatch=(id:string)=>act('Opening batch',async()=>{
   const value=await api('/batches/'+id);setBatch(value);setPreview(value.files[0]);setReport(null);setReviewed([]);setRun(null);
   const draft=await api('/batches/'+id+'/plan',{method:'POST',body:{mode:'suggested',...(state.flows[0]?{flow:state.flows[0].spec}:{})}});
   setFlow(draft.flow);setOrigin(state.flows[0]?'saved_flow':'suggested_setup');setPage('files');
 });
 const openRun=(id:string)=>act('Opening saved result',async()=>{setRun(await api('/runs/'+id));setPage('results');setSelected(null);setAck(false);setHandoff(null);});
 const approveAndRun=()=>act('Validating approved rules and processing all source rows',async()=>{
   const pre=await inspect();if(pre.errors.length)throw new Error(pre.errors.join('; '));
   const saved=await api('/batches/'+batch!.id+'/approve',{method:'POST',body:{flow,reviewed,expected_input_hash:pre.input_hash}});
   const created=await api('/runs',{method:'POST',body:{batch_id:batch!.id,flow_id:saved.id}});
   await api('/runs/'+created.id+'/execute',{method:'POST'});
   setRun(await api('/runs/'+created.id));setDisposition('included');setQuery('');setAck(false);setHandoff(null);setPage('results');await reload();
 });
 const importFiles=()=>act('Reading your synthetic files',async()=>{
   const ids=[];for(const item of staging){const form=new FormData();form.append('file',item.file);form.append('role',item.role);form.append('channel_id',item.channel);form.append('sheet_name',item.sheet||'');const asset=await api('/files',{method:'POST',body:form});ids.push(asset.id);}
   const created=await api('/batches',{method:'POST',body:{file_ids:ids,label:'Uploaded synthetic orders'}});
   const value=await api('/batches/'+created.id);setBatch(value);setPreview(value.files[0]);setReviewed([]);setReport(null);setRun(null);
   const draft=await api('/batches/'+created.id+'/plan',{method:'POST',body:{mode:'suggested'}});
   setFlow(draft.flow);setOrigin('suggested_setup');setDraftInfo(draft);setStaging([]);await reload();
 });
 const approveExport=()=>act('Building the approved workbook',async()=>{
   const value=await api('/runs/'+run!.id+'/export-approval',{method:'POST',body:{result_hash:run!.result_hash,acknowledge_exceptions:ack}});
   setRun(await api('/runs/'+run!.id));await reload();window.location.assign(value.download_url);setNotice('Workbook approved. Exceptions and source records are included in separate sheets.');
 });
 const summary=run?.summary;
 const disabled=Boolean(busy);
 const fields=Object.keys(fieldLabels);
 const selectedBatchName=state.batches.find((x:Any)=>x.id===run?.batch_id)?.label;
 return <div className="app-shell">
  <aside className="sidebar">
   <div className="brand"><div className="brand-mark"><i/><i/><i/></div><span>MaiZi<span className="brand-dot">.</span></span></div>
   <div className="workspace-label">ORDER WORKSPACE</div>
   <nav aria-label="Workflow steps">
    {[['files','01','Files & flows','file'],['plan','02','Plan & review','branch'],['results','03','Results & exceptions','box']].map(([key,n,label,icon])=><button key={key} aria-label={label} className={'nav-item '+(page===key?'active':'')} onClick={()=>setPage(key)}><Icon name={icon}/><span>{label}</span><small>{n}</small></button>)}
   </nav>
   <div className="sidebar-section"><div className="section-kicker">SAVED FLOWS <span>{state.flows.length}</span></div>
    {state.flows.length===0?<p className="quiet small">Your first approved workflow will appear here.</p>:state.flows.slice(0,4).map((item:Any)=><button className="saved-item" key={item.id} disabled={!batch||disabled} onClick={()=>{setFlow(item.spec);setOrigin('saved_flow');setReviewed([]);setReport(null);setPage('plan');}}><Icon name="branch" size={15}/><span>{item.spec.name}</span></button>)}
   </div>
   <div className="sidebar-section"><div className="section-kicker">RECENT RUNS <span>{state.runs.length}</span></div>
    {state.runs.length===0?<p className="quiet small">Run a reviewed plan to start a history.</p>:state.runs.slice(0,5).map((item:Any)=><button className="saved-item" key={item.id} onClick={()=>openRun(item.id)}><Icon name="history" size={15}/><span>{state.batches.find((x:Any)=>x.id===item.batch_id)?.label||'Order run'}<small>{item.status} · {item.summary?.included??'—'} included</small></span></button>)}
   </div>
   <div className="sidebar-footer"><span className="status-dot"/><div>Runs on this computer<small>Synthetic business data only</small></div></div>
  </aside>
  <div className="main-column">
   <header className="topbar"><div>Workspace <span className="slash">/</span> <strong>{batch?.label||'Weekly picking preparation'}</strong></div><div className="topbar-right"><Badge tone={health.ai_configured?'green':'neutral'}>{health.ai_configured?'API configured':'No API configured'}</Badge><span className="version">LOCAL · v{health.version||'0.1.0'}</span></div></header>
   <main>
    {error&&<div role="alert" className="banner error"><strong>Action needed</strong><span>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><Icon name="close" size={16}/></button></div>}
    {notice&&<div role="status" className="banner success"><Icon name="check" size={18}/><span>{notice}</span><button aria-label="Dismiss notice" onClick={()=>setNotice('')}><Icon name="close" size={16}/></button></div>}
    {busy&&<div role="status" className="working"><span className="spinner"/>{busy}<span className="quiet">Please keep the app open.</span></div>}

    {page==='files'&&<>
      <div className="page-heading"><div><div className="eyebrow">LESS REPETITION. MORE CERTAINTY.</div><h1>Prepare this week’s orders.</h1><p>Bring the files together. Confirm the rules. Leave a clear trail.</p></div><Badge>Picking preparation only</Badge></div>
      <section className="demo-strip" aria-label="Three-week demo"><div><span className="section-kicker">TRY THE COMPLETE JOURNEY</span><p>One workflow. Three weeks of change.</p></div>{[[1,'Configure','Different formats'],[2,'Catch a change','A new shipping status'],[3,'Reuse','Compatible files']].map(([week,title,subtitle])=><button key={week} className="week-button" disabled={disabled} onClick={()=>loadWeek(Number(week))}><span className="week-number">0{week}</span><span><strong>{title}</strong><small>{subtitle}</small></span><Icon size={16}/></button>)}</section>
      <div className="files-layout">
       <section className="panel">
        <div className="panel-heading"><div><h2>Source files</h2><p>{batch?batch.files.length+' files · '+batch.files.filter((x:Any)=>x.role==='orders').reduce((sum:number,x:Any)=>sum+x.profile.row_count,0)+' order lines':'Add order exports, one product master and a warehouse template.'}</p></div><label className="button secondary small-button"><Icon name="upload" size={16}/>Add files<input aria-label="Upload synthetic files" type="file" multiple accept=".csv,.xlsx" hidden onChange={event=>{const chosen=Array.from(event.target.files||[]);setStaging(prev=>[...prev,...chosen.map((file,index)=>({file,role:file.name.toLowerCase().includes('master')?'master':file.name.toLowerCase().includes('template')?'template':'orders',channel:'source-'+(prev.length+index+1),sheet:''}))]);event.target.value='';}}/></label></div>
        {staging.length>0&&<div className="staging"><h3>Confirm file roles</h3>{staging.map((item,index)=><div className="stage-row" key={index}><span>{item.file.name}</span><select aria-label={'Role for '+item.file.name} value={item.role} onChange={e=>setStaging(prev=>prev.map((x,i)=>i===index?{...x,role:e.target.value}:x))}><option value="orders">Orders</option><option value="master">Product master</option><option value="template">Template</option></select><input aria-label="Channel ID" value={item.channel} disabled={item.role!=='orders'} onChange={e=>setStaging(prev=>prev.map((x,i)=>i===index?{...x,channel:e.target.value}:x))}/><input aria-label="Worksheet name" placeholder="Sheet (if multiple)" value={item.sheet} onChange={e=>setStaging(prev=>prev.map((x,i)=>i===index?{...x,sheet:e.target.value}:x))}/><button className="icon-button" aria-label="Remove staged file" onClick={()=>setStaging(prev=>prev.filter((_,i)=>i!==index))}><Icon name="close" size={16}/></button></div>)}<button disabled={disabled} className="button" onClick={importFiles}>Read and validate files<Icon size={16}/></button></div>}
        {batch?<div className="file-list">{batch.files.map((item:Any)=><button key={item.id} onClick={()=>setPreview(item)} className={'file-row '+(preview?.id===item.id?'selected':'')}><span className="file-symbol"><Icon name="file"/></span><span className="file-info"><strong>{item.name}</strong><small>{item.channel_id||item.role} · {item.profile.row_count} {item.role==='template'?'template rows':'rows'} · {item.profile.headers.length} columns</small></span><Badge>{item.role==='orders'?'Orders':item.role==='master'?'Master':'Template'}</Badge></button>)}</div>:<div className="empty-state"><span className="empty-icon"><Icon name="file" size={30}/></span><h3>Your files, in one place.</h3><p>Load week 01 above, or add your own synthetic CSV and XLSX files.</p><small>Up to 5 order files · 10,000 order lines · 5 MB per file</small></div>}
        {preview&&<div className="preview-block"><div className="preview-caption">SOURCE PREVIEW <span>{preview.name} · {preview.profile.sheet}</span></div><div className="table-scroll"><table><thead><tr>{preview.profile.headers.map((key:string)=><th key={key}>{key}</th>)}</tr></thead><tbody>{preview.profile.samples.map((row:Any,index:number)=><tr key={index}>{preview.profile.headers.map((key:string)=><td key={key}>{String(row[key]??'')}</td>)}</tr>)}</tbody></table></div><p className="table-note">First five data rows. Processing always checks every accepted row.</p></div>}
       </section>
       <section className="panel intent-panel"><div className="section-kicker">THE JOB TO BE DONE</div><h2>Tell MaiZi what this batch needs.</h2><label className="sr-only" htmlFor="instructions">Processing instructions</label><textarea id="instructions" rows={8} value={instructions} onChange={e=>setInstructions(e.target.value)}/><div className="callout"><strong>You stay in control.</strong><p>Review the actual mappings, status rules and conversions before any order is included.</p></div><button className="button full" disabled={!batch||disabled||!health.ai_configured} onClick={()=>plan('live')}>Propose a plan with AI<Icon size={16}/></button><button className="text-button" disabled={!batch||disabled} onClick={()=>{setPage('plan');if(!flow)plan('suggested');}}>Review editable setup<Icon size={15}/></button><p className="small quiet">{health.ai_configured?'The API receives a bounded profile and sample rows. Your key stays in the local backend.':'Without a key, use the saved or manually reviewed setup. This does not make a live AI call.'}</p></section>
      </div>
      {state.batches.length>0&&<section className="batch-history"><h3>Available batches</h3><div className="batch-buttons">{state.batches.slice(0,8).map((item:Any)=><button className={'batch-chip '+(batch?.id===item.id?'current':'')} key={item.id} disabled={disabled} onClick={()=>openBatch(item.id)}>{item.label}<span>{new Date(item.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span></button>)}</div></section>}
    </>}

    {page==='plan'&&(!flow||!batch?<div className="empty-state"><Icon name="branch" size={36}/><h1>Start with your source files.</h1><p>A plan belongs to a particular set of inputs.</p><button className="button" onClick={()=>setPage('files')}>Go to files<Icon size={16}/></button></div>:<>
      <div className="page-heading"><div><div className="eyebrow">CHECK THE RULES BEFORE THEY RUN</div><h1>A plan you can inspect.</h1><p>Confirm what each step means for this batch.</p></div><Badge tone={origin==='live_ai'?'blue':'neutral'}>{origin==='live_ai'?'Live AI draft':origin==='saved_flow'?'Saved flow':'Editable setup · no AI call'}</Badge></div>
      {draftInfo?.explanation&&<p className="draft-explanation">{draftInfo.explanation}</p>}
      {draftInfo?.questions?.length>0&&<div className="callout amber"><strong>Questions from the planner</strong><ul>{draftInfo.questions.map((x:any,i:number)=><li key={i}>{typeof x==='string'?x:JSON.stringify(x)}</li>)}</ul></div>}
      <div className="plan-layout"><div>
        <section className="panel rule-panel"><div className="panel-heading"><h2><span className="step-square">1</span>Fields & status rules</h2></div>
         {Object.entries(flow.channels).map(([channel,rule]:[string,any])=>{
           const source=batch.files.find((x:Any)=>x.channel_id===channel);
           const statuses=[...new Set([...(Object.keys(source?.profile.columns[rule.fields.status]?.values||{})),...Object.keys(rule.status_actions)])];
           return <div className="channel-block" key={channel}><div className="channel-heading"><h3>{channel}</h3><small>{source?.name||'No matching source file'}</small></div><div className="mapping-grid">{fields.map(key=><label key={key}>{fieldLabels[key]}<select aria-label={channel+' '+fieldLabels[key]} value={rule.fields[key]||''} onChange={e=>change(n=>n.channels[channel].fields[key]=e.target.value||(key==='line_id'||key==='date'?null:''))}><option value="">Not mapped</option>{source?.profile.headers.map((header:string)=><option key={header} value={header}>{header}</option>)}</select></label>)}</div><div className="status-grid">{statuses.map((status:any)=><label className="status-rule" key={status}><span className="mono">{status||'(blank)'}</span><select aria-label={channel+' status '+status} value={rule.status_actions[status]||'hold'} onChange={e=>change(n=>{if(e.target.value==='hold')delete n.channels[channel].status_actions[status];else n.channels[channel].status_actions[status]=e.target.value;})}><option value="hold">Hold as exception</option><option value="include">Include</option><option value="exclude">Exclude</option></select></label>)}</div><label className="inline-field">Duplicate policy<select value={rule.dedup_mode} onChange={e=>change(n=>n.channels[channel].dedup_mode=e.target.value)}><option value="business_key">Channel + order + line ID</option><option value="source_row">Keep each source row (limited deduplication)</option></select></label><label className="inline-field">Date format<select value={rule.date_format} onChange={e=>change(n=>n.channels[channel].date_format=e.target.value)}><option value="%Y-%m-%d">YYYY-MM-DD</option><option value="%d/%m/%Y">DD/MM/YYYY</option><option value="%d-%m-%Y">DD-MM-YYYY</option></select></label></div>;
         })}
        </section>
        <section className="panel rule-panel"><div className="panel-heading"><h2><span className="step-square">2</span>Product & unit decisions</h2></div><p className="quiet">Exact SKUs match automatically. Add aliases only when the product and specification are confirmed.</p>
         <div className="decision-list">{Object.entries(flow.aliases).map(([name,sku]:any)=><div key={name}><span>{name}</span><Icon size={15}/><code>{sku}</code><button className="text-button" onClick={()=>change(n=>delete n.aliases[name])}>Remove</button></div>)}</div>
         <div className="add-rule"><input aria-label="Product alias" placeholder="e.g. Jasmine500" value={alias} onChange={e=>setAlias(e.target.value)}/><input aria-label="Confirmed SKU" placeholder="Master SKU" value={aliasSku} onChange={e=>setAliasSku(e.target.value)}/><button className="button secondary" disabled={!alias.trim()||!aliasSku.trim()} onClick={()=>{change(n=>n.aliases[alias.trim()]=aliasSku.trim());setAlias('');}}>Confirm alias</button></div>
         <div className="decision-list">{Object.entries(flow.unit_aliases).map(([name,unit]:any)=><div key={name}><span>{name}</span><Icon size={15}/><code>{unit}</code><button className="text-button" onClick={()=>change(n=>delete n.unit_aliases[name])}>Remove</button></div>)}</div>
         <div className="add-rule"><input aria-label="Incoming unit" value={unitFrom} onChange={e=>setUnitFrom(e.target.value)} placeholder="Incoming unit"/><select aria-label="Master unit" value={unitTo} onChange={e=>setUnitTo(e.target.value)}>{['piece','box','pack'].map(unit=><option key={unit}>{unit}</option>)}</select><button className="button secondary" disabled={!unitFrom.trim()} onClick={()=>change(n=>n.unit_aliases[unitFrom.trim()]=unitTo)}>Confirm unit</button></div>
         <p className="table-note">Conversion factors come from the product master for each SKU. No rounding or invented package size.</p>
         <details><summary>Product master field mapping</summary><div className="mapping-grid">{Object.entries(flow.master_fields).map(([key,value]:any)=><label key={key}>{key}<select value={value} onChange={e=>change(n=>n.master_fields[key]=e.target.value)}><option value="">Not mapped</option>{batch.files.find((x:Any)=>x.role==='master')?.profile.headers.map((header:string)=><option key={header}>{header}</option>)}</select></label>)}</div></details>
        </section>
        <section className="panel rule-panel"><div className="panel-heading"><h2><span className="step-square">3</span>Scope & warehouse output</h2></div><div className="scope-fields"><label>Flow name<input value={flow.name} onChange={e=>change(n=>n.name=e.target.value)}/></label><label>From date<input type="date" value={flow.date_from||''} onChange={e=>change(n=>n.date_from=e.target.value||null)}/></label><label>To date<input type="date" value={flow.date_to||''} onChange={e=>change(n=>n.date_to=e.target.value||null)}/></label></div><div className="output-map">{flow.output_columns.map((column:Any,index:number)=><label key={index}><span>{column.header}</span><Icon size={14}/><select value={column.field} onChange={e=>change(n=>n.output_columns[index].field=e.target.value)}>{['sku','name','quantity','unit'].map(key=><option key={key}>{key}</option>)}</select></label>)}</div></section>
      </div><aside className="review-column"><section className="panel review-card"><div className="section-kicker">BEFORE YOU RUN</div><h2>Check this batch.</h2><p>Changes and unknowns stay visible. A clear status does not guarantee that every row is eligible.</p><button className="button secondary full" disabled={disabled} onClick={()=>act('Checking full-batch rule coverage',async()=>{await inspect();})}>Check changes<Icon name="branch" size={16}/></button>
       {report&&<div className="preflight-report"><div className="report-count"><strong>{report.row_count}</strong><span>source rows checked</span></div>{report.errors.map((x:string)=><p className="issue error-text" key={x}>{x}</p>)}{report.status_guard.unknown_values.map((item:Any)=><div className="issue amber-text" key={item.channel_id+item.value}><strong>{item.value||'(blank)'}</strong><span>{item.channel_id} · {item.count} affected rows</span></div>)}{report.status_guard.covered&&<p className="covered"><Icon name="check" size={15}/>All observed statuses are covered.</p>}{Object.entries(report.unresolved_products).map(([value,count]:any)=><div className="issue" key={value}><strong>Unmatched product: {value||'(blank)'}</strong><span>{count} row(s) held for review</span></div>)}{Object.entries(report.unresolved_units).map(([value,count]:any)=><div className="issue" key={value}><strong>Unknown unit: {value}</strong><span>{count} row(s) held for review</span></div>)}<p className="small quiet">Unknown and invalid records remain in Exceptions. They are never silently included.</p><details><summary>Module provenance</summary><p className="small">Status coverage is checked by the module developed in Replit Free, running locally as part of MaiZi.</p></details></div>}
       <div className="review-checks">{Object.entries(groups).map(([key,label]:any)=><label key={key}><input type="checkbox" checked={reviewed.includes(key)} onChange={e=>{const checked=e.target.checked;setReviewed(old=>checked?[...old,key]:old.filter(x=>x!==key));}}/><span>{label}</span></label>)}</div><button className="button full" disabled={disabled||reviewed.length!==6||!report||report.errors.length>0} onClick={approveAndRun}>Approve rules & run<Icon size={16}/></button><p className="table-note">Approval saves an immutable flow version for these inputs. Changes require another review.</p></section></aside></div>
    </>)}

    {page==='results'&&(!run||run.status!=='completed'?<div className="empty-state"><Icon name="box" size={36}/><h1>A result with a clear trail.</h1><p>Approve and run a plan to inspect its output and exceptions.</p><button className="button" onClick={()=>setPage(batch?'plan':'files')}>Open workflow<Icon size={16}/></button></div>:<>
      <div className="page-heading"><div><div className="eyebrow">EVERY ROW ACCOUNTED FOR</div><h1>Ready to review.</h1><p>{selectedBatchName||'Order run'} · {summary.input} source lines · {run.snapshot.slice(0,12)}</p></div><Badge tone="green">Processing complete</Badge></div>
      <div className="result-metrics">{[['included','Included','green'],['exception','Exceptions','amber'],['excluded','Excluded','neutral'],['duplicate','Duplicates','blue']].map(([key,label,tone])=><button key={key} className={'metric '+(disposition===key?'chosen':'')} onClick={()=>setDisposition(key)}><span className={'metric-dot '+tone}/><span>{label}</span><strong>{summary[key]}</strong><small>{key==='included'?'Ready for preparation':key==='exception'?'Retained for human review':key==='excluded'?'By confirmed scope rules':'Linked to representative rows'}</small></button>)}</div>
      <div className="accounting"><Icon name="check" size={16}/><strong>{summary.input} = {summary.included} + {summary.excluded} + {summary.duplicate} + {summary.exception}</strong><span>Source-line reconciliation passed</span></div>
      <div className="results-layout"><section className="panel results-table"><div className="panel-heading"><div><h2>{disposition==='exception'?'Exception records':disposition==='included'?'Included order lines':disposition==='duplicate'?'Confirmed duplicate lines':'Excluded order lines'}</h2><p>Open a row to inspect its original values and processing trail.</p></div><input aria-label="Search result rows" className="search" placeholder="Search SKU, order or reason" value={query} onChange={e=>setQuery(e.target.value)}/></div><div className="table-scroll"><table><thead><tr><th>Source</th><th>SKU / original product</th><th>Base quantity</th><th>Reason</th><th></th></tr></thead><tbody>{rows.map(row=><tr key={row.source_row_id} onClick={()=>setSelected(row)} tabIndex={0} onKeyDown={event=>{if(event.key==='Enter')setSelected(row);}}><td><strong>{row.source_id}</strong><small>Row {row.row_number} · {row.sheet}</small></td><td className="mono">{row.sku||Object.entries(row.raw).find(([key])=>/item|product|商品/i.test(key))?.[1] as any||'—'}</td><td className="mono">{row.quantity??'—'} <span className="quiet">{row.unit||''}</span></td><td>{row.reasons.map((x:Any)=><span className="reason-code" key={x.code}>{x.code.replaceAll('_',' ').toLowerCase()}</span>)}{row.disposition==='included'&&<span className="quiet">Confirmed rules applied</span>}</td><td><Icon size={15}/></td></tr>)}</tbody></table>{rows.length===0&&<div className="table-empty">No matching records.</div>}</div><div className="table-footer">Showing {rows.length} of {rowTotal} records. Full results are included in the workbook.</div></section>
       <aside><section className="panel export-card"><div className="section-kicker">APPROVE THE OUTCOME</div><h2>Warehouse preparation.</h2><div className="sku-list">{run.sku_summary.slice(0,8).map((item:Any)=><div key={item.sku}><span><strong>{item.sku}</strong><small>{item.name}</small></span><b>{item.quantity}<small>{item.unit}</small></b></div>)}</div><p className="small quiet">The workbook includes detail, SKU summary, exceptions, exclusions, duplicates and lineage.</p>{summary.exception>0&&<label className="export-ack"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/><span>I reviewed that {summary.exception} exception rows are excluded from picking preparation and retained in the workbook.</span></label>}<button className="button full" disabled={disabled||(summary.exception>0&&!ack)} onClick={approveExport}>{run.export_approved?'Export approved workbook':'Approve & export XLSX'}<Icon name="upload" size={16}/></button><div className="divider"/><Badge>Orbyte Simulation</Badge><p className="small">Create a simulated warehouse review task after approving the output.</p><button className="button secondary full" disabled={!run.export_approved||disabled} onClick={()=>act('Creating simulated warehouse task',async()=>{setHandoff(await api('/runs/'+run.id+'/handoff',{method:'POST'}));await reload();})}>Create preparation task<Icon size={16}/></button>{handoff&&<p role="status" className="small green-text">Simulated task {handoff.id.slice(0,8)} is ready for review.</p>}</section></aside></div>
      <details className="activity-panel"><summary>Activity & approval record <span>{state.activity.length} recent events</span></summary><div>{state.activity.map((item:Any)=><div className="activity-row" key={item.id}><span>{new Date(item.created_at).toLocaleString()}</span><strong>{item.action.replaceAll('_',' ')}</strong><code>{JSON.stringify(item.detail)}</code></div>)}</div></details>
    </>)}
   </main><footer className="main-footer"><span>MaiZi / less busywork, better preparation.</span><span>Original files preserved · Human approval required</span></footer>
  </div>
  {selected&&<div className="drawer-backdrop" onClick={()=>setSelected(null)}><aside className="source-drawer" onClick={e=>e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Source and processing trail"><div className="drawer-heading"><div><div className="eyebrow">SOURCE & PROCESSING TRAIL</div><h2>One row. Every decision.</h2></div><button className="icon-button" aria-label="Close source detail" onClick={()=>setSelected(null)}><Icon name="close"/></button></div><Badge tone={selected.disposition==='included'?'green':'amber'}>{selected.disposition}</Badge><p><strong>{selected.source_name}</strong><br/><span className="quiet">{selected.sheet} · original row {selected.row_number}</span></p><a className="text-button" href={'/api/files/'+selected.source_row_id.split(':')[0]+'/download'}>Download original input<Icon size={15}/></a><h3>Original values</h3><dl className="raw-values">{Object.entries(selected.raw).map(([key,value])=><React.Fragment key={key}><dt>{key}</dt><dd>{String(value??'')}</dd></React.Fragment>)}</dl><h3>Processing decisions</h3>{selected.reasons.map((reason:Any)=><div className="callout amber" key={reason.code}><strong>{reason.code}</strong><p>{reason.message}</p></div>)}{selected.duplicate_of&&<p className="small">Representative source row: <code>{selected.duplicate_of}</code></p>}<div className="trail">{selected.events.map((event:Any,index:number)=><div key={index}><span className="trail-index">{index+1}</span><section><h4>{event.stage}</h4><p>{event.rule}</p><pre>{JSON.stringify({before:event.before,after:event.after,...(event.evidence?{evidence:event.evidence}:{})},null,2)}</pre></section></div>)}</div></aside></div>}
 </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
