export type Data = Record<string, any>;
export type Flow = {schema_version:1; name:string; channels:Record<string,{fields:Record<string,string|null>;status_actions:Record<string,'include'|'exclude'>;dedup_mode:string;date_format:string}>;aliases:Record<string,string>;unit_aliases:Record<string,string>;master_fields:Record<string,string>;output_columns:{header:string;field:string}[];date_from:string|null;date_to:string|null};
export type Asset = {id:string;name:string;role:string;channel_id:string;profile:{headers:string[];row_count:number;samples:Data[];columns:Data;sheet:string}};
export type Batch = {id:string;label:string;files:Asset[];input_hash:string};
export type Approval = {id:string;spec:Flow;batch_id:string;workflow_id:string;rule_version:number;parent_flow_id:string|null;created_at:string};
export type Summary = {input:number;included:number;excluded:number;duplicate:number;exception:number};
export type Run = {id:string;batch_id:string;flow_id:string;status:string;summary?:Summary;error?:string;snapshot?:string;result_hash?:string;export_approved?:boolean;export_state?:string;export_stage?:string;export_error?:string;export_id?:string};
export type ResultRow = {source_row_id:string;source_id:string;source_name:string;sheet:string;row_number:number;row_end_number?:number;raw:Data;sku:string|null;quantity:string|null;unit?:string;disposition:string;reasons:{code:string;message:string}[];events:Data[];duplicate_of?:string};
export type Page<T> = {rows:T[];total:number;offset:number;limit:number};
export type HeldStatus = {channel_id:string;field:string;value:string};
export type Report = {errors:string[];input_hash:string;row_count:number;status_guard:Data;hold_review:{required:boolean;snapshot_hash:string;groups:(HeldStatus & {count:number})[]};unresolved_products:Record<string,number>;unresolved_units:Record<string,number>;products:Data[];available_units:string[];observed_statuses:Record<string,Record<string,number>>;diff:{groups:{group:string;changed:boolean;before:unknown;after:unknown}[];inputs:{kind:string;message:string}[]}};

export class ApiError extends Error {constructor(message:string,readonly status:number){super(message);}}
export const responseLost=(error:unknown)=>!(error instanceof ApiError)||error.status>=500;
export async function api<T=Data>(path:string, options:RequestInit & {json?:unknown} = {}):Promise<T> {
  const {json,signal,...rest}=options;
  const headers=new Headers(rest.headers);headers.set('X-Wheat-Request','1');if(json!==undefined)headers.set('Content-Type','application/json');
  const controller=new AbortController();let timedOut=false;
  const cancel=()=>controller.abort();signal?.addEventListener('abort',cancel,{once:true});if(signal?.aborted)cancel();
  const timer=setTimeout(()=>{timedOut=true;controller.abort();},120000);
  try{
    const response=await fetch('/api'+path,{...rest,headers,signal:controller.signal,...(json===undefined?{}:{body:JSON.stringify(json)})});
    if(!response.ok){const error=await response.json().catch(()=>({detail:'The local server could not complete this request.'}));throw new ApiError(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail),response.status);}
    return await response.json();
  }catch(error){if(timedOut)throw new Error('Request timed out. Refresh the saved status before retrying; the server may still be processing.');throw error;}
  finally{clearTimeout(timer);signal?.removeEventListener('abort',cancel);}
}
export const message=(error:unknown)=>error instanceof Error?error.message:'The request could not be completed.';
export const emptyPage=<T,>():Page<T>=>({rows:[],total:0,offset:0,limit:100});
