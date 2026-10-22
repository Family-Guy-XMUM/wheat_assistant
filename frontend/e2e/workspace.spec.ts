import {test,expect,APIRequestContext,Page} from '@playwright/test';
const groups=['Field meanings and source columns','Included, excluded and unknown statuses','SKU matching and confirmed aliases','Master conversions and unit mappings','Business key and missing-line handling','Warehouse template and output columns'];
async function approve(page:Page){await page.getByRole('button',{name:'Check changes',exact:true}).click();for(const label of groups)await page.getByLabel(label,{exact:true}).check();await page.getByRole('button',{name:'Approve rules & run',exact:true}).click();await expect(page.getByRole('heading',{name:'Ready to review.'})).toBeVisible();}
async function seed(request:APIRequestContext,label:string,count:number,execute=true,skuCount=count){
 const master=Buffer.from('SKU,Name,Base unit\n'+Array.from({length:skuCount},(_,i)=>'S'+String(i).padStart(4,'0')+',Synthetic '+i+',piece').join('\n'));
 const orders=Buffer.from('Order ID,Line,Item Code,Qty,Unit,Order Status\n'+Array.from({length:count},(_,i)=>'O'+i+',1,S'+String(i%skuCount).padStart(4,'0')+',1,piece,Confirmed').join('\n'));
 const upload=async(name:string,body:Buffer,role:string)=>{const r=await request.post('/api/files',{multipart:{file:{name,mimeType:'text/csv',buffer:body},role,channel_id:role==='orders'?label:''}});expect(r.ok()).toBeTruthy();return (await r.json()).id;};
 const batch=await (await request.post('/api/batches',{data:{label,file_ids:[await upload('master.csv',master,'master'),await upload('orders.csv',orders,'orders')]}})).json();
 const spec=(await (await request.post('/api/batches/'+batch.id+'/plan',{data:{mode:'suggested'}})).json()).flow;
 const pre=await (await request.post('/api/batches/'+batch.id+'/preflight',{data:spec})).json();
 const flow=await (await request.post('/api/batches/'+batch.id+'/approve',{data:{flow:spec,reviewed:['fields','statuses','products','units','duplicates','output'],expected_input_hash:pre.input_hash}})).json();
 const run=await (await request.post('/api/runs',{data:{batch_id:batch.id,flow_id:flow.id}})).json();
 if(execute)expect((await request.post('/api/runs/'+run.id+'/execute')).ok()).toBeTruthy();
 return run;
}
test('three weeks, six approvals, exception repair and verified download',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:/01 Configure/}).click();await page.getByRole('button',{name:'Review editable setup'}).click();
 await page.getByLabel('Product alias',{exact:true}).fill('Jasmine500');await page.getByLabel('Confirmed SKU',{exact:true}).fill('TEA-001');await page.getByRole('button',{name:'Confirm alias',exact:true}).click();
 await page.getByLabel('Incoming unit',{exact:true}).fill('carton');await page.getByLabel('Master unit',{exact:true}).selectOption('box');await page.getByRole('button',{name:'Confirm unit',exact:true}).click();await approve(page);
 await expect(page.getByText('36 = 24 + 3 + 3 + 6',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:/^Exceptions 6/}).click();await page.locator('tbody tr').first().click();await expect(page.getByRole('dialog')).toBeVisible();await page.getByRole('button',{name:'Close source detail'}).click();
 await page.getByLabel(/I reviewed that 6 exception rows/).check();
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Approve & export XLSX',exact:true}).click();expect((await download).suggestedFilename()).toContain('.xlsx');
 await page.getByRole('button',{name:'Create preparation task',exact:true}).click();await expect(page.getByText(/Simulated task .* is ready/)).toBeVisible();
 await page.getByRole('button',{name:'Files & flows',exact:true}).click();await page.getByRole('button',{name:/02 Catch a change/}).click();await page.getByRole('button',{name:'Review editable setup'}).click();
 await expect(page.getByLabel('channel-b status Partially shipped',{exact:true})).toHaveValue('unreviewed');
 for(const label of groups)await page.getByLabel(label,{exact:true}).check();await expect(page.getByRole('button',{name:'Approve rules & run',exact:true})).toBeDisabled();
 await page.getByLabel('channel-b status Partially shipped',{exact:true}).selectOption('exclude');
 await approve(page);await expect(page.getByText('39 = 24 + 6 + 3 + 6',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Files & flows',exact:true}).click();await page.getByRole('button',{name:/03 Reuse/}).click();await page.getByRole('button',{name:'Review editable setup'}).click();await approve(page);await expect(page.getByText('24 = 24 + 0 + 0 + 0',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Activity & approval record',exact:true}).click();await expect(page.getByLabel('Show global activity instead of this run')).toBeVisible();
});
test('all detail and SKU pages, search reset and history navigation',async({page,request})=>{
 await seed(request,'Pagination review',10000,true,5000);await page.goto('/');await page.getByRole('button',{name:/Pagination review.*completed/}).click();
 await expect(page.getByText('1–100 of 10000',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Next',exact:true}).click();await expect(page.getByText('101–200 of 10000',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Last',exact:true}).click();await expect(page.getByText('9901–10000 of 10000',{exact:true})).toBeVisible();await expect(page.locator('tbody')).toContainText('S4999');
 await page.getByLabel('Search result rows').fill('S0001');await expect(page.getByText('1–2 of 2',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'All SKU totals',exact:true}).click();await expect(page.getByText('1–50 of 5000',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Last',exact:true}).click();await expect(page.getByText('4951–5000 of 5000',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'History',exact:true}).click();await expect(page.getByRole('heading',{name:'History you can find.'})).toBeVisible();await expect(page.getByText('Pagination review',{exact:true})).toBeVisible();
});
test('a disconnected start checks saved state and requires an explicit retry',async({page,request})=>{
 const run=await seed(request,'Recoverable review',2,false);await page.goto('/');await page.getByRole('button',{name:/Recoverable review.*ready/}).click();let attempts=0;
 await page.route('**/api/runs/'+run.id+'/execute',async route=>{attempts++;await route.abort('connectionfailed');});
 await page.getByRole('button',{name:'Start approved run'}).click();await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByRole('heading',{name:'Run ready.'})).toBeVisible();expect(attempts).toBe(1);
 await page.unroute('**/api/runs/'+run.id+'/execute');await page.getByRole('button',{name:'Start approved run'}).click();await expect(page.getByRole('heading',{name:'Ready to review.'})).toBeVisible();
});

for(const lostStep of ['approve','runs'])test('lost '+lostStep+' response recovers one saved run before execution',async({page,request})=>{
 await page.goto('/');await page.getByRole('button',{name:/01 Configure/}).click();await page.getByRole('button',{name:'Review editable setup'}).click();
 await page.getByRole('button',{name:'Check changes',exact:true}).click();for(const label of groups)await page.getByLabel(label,{exact:true}).check();
 let created:any;let mutations=0;let executions=0;
 page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/execute'))executions++;});
 const pattern=lostStep==='approve'?'**/api/batches/*/approve':'**/api/runs';
 await page.route(pattern,async route=>{if(route.request().method()!=='POST'){await route.continue();return;}mutations++;const response=await route.fetch();created=await response.json();await route.abort('connectionfailed');});
 await page.getByRole('button',{name:'Approve rules & run',exact:true}).click();await expect(page.getByRole('heading',{name:'Run ready.'})).toBeVisible();
 await expect(page.getByText(/A response was lost.*saved approval and run/)).toBeVisible();expect(mutations).toBe(1);expect(executions).toBe(0);
 const flowId=lostStep==='approve'?created.id:created.flow_id;
 const runs=await (await request.get('/api/history/runs?flow_id='+flowId)).json();expect(runs.total).toBe(1);
 await page.unroute(pattern);await page.getByRole('button',{name:'Start approved run'}).click();await expect(page.getByRole('heading',{name:'Ready to review.'})).toBeVisible();expect(executions).toBe(1);
});

test('late result responses cannot overwrite a newly selected run',async({page,request})=>{
 const old=await seed(request,'Fast context A',3);await seed(request,'Fast context B',2);
 await page.goto('/');await page.getByRole('button',{name:/Fast context A.*completed/}).click();await expect(page.locator('tbody')).toContainText('Fast context A');
 let release!:()=>void;let captured!:()=>void;let finished!:()=>void;
 const held=new Promise<void>(resolve=>release=resolve),seen=new Promise<void>(resolve=>captured=resolve),settled=new Promise<void>(resolve=>finished=resolve);
 await page.route('**/api/runs/'+old.id+'/rows?**',async route=>{const response=await route.fetch();captured();await held;try{await route.fulfill({response});}catch{}finally{finished();}});
 await page.getByLabel('Search result rows').fill('S0001');await seen;
 await page.getByRole('button',{name:/Fast context B.*completed/}).click();await expect(page.locator('tbody')).toContainText('Fast context B');release();await settled;
 await expect(page.locator('tbody')).not.toContainText('Fast context A');await expect(page.getByText('1–2 of 2',{exact:true})).toBeVisible();
});

test('ordinary uploads review a new source, all 75 statuses and actual master units',async({page,request})=>{
 const old=await seed(request,'Prior upload source',1,false);await page.goto('/');await page.getByLabel('Workflow to use').selectOption(old.flow_id);
 const header='Order ID,Line,Item Code,Qty,Unit,Order Status\n';
 const part=(start:number,count:number)=>Buffer.from(header+Array.from({length:count},(_,i)=>'U'+(start+i)+',1,S0000,1,crate,State'+(start+i)).join('\n'));
 await page.getByLabel('Upload synthetic files').setInputFiles([{name:'orders-first.csv',mimeType:'text/csv',buffer:part(0,70)},{name:'orders-second.csv',mimeType:'text/csv',buffer:part(70,5)},{name:'master.csv',mimeType:'text/csv',buffer:Buffer.from('SKU,Name,Base unit,Box size,Pack size\nS0000,Synthetic crate,crate,12,6')}]);
 for(const name of ['orders-first.csv','orders-second.csv'])await page.getByLabel('Source for '+name,{exact:true}).fill('new-source');
 let committedBatch:any;let imports=0;
 await page.route('**/api/batches',async route=>{imports++;const response=await route.fetch();committedBatch=await response.json();await route.abort('connectionfailed');});
 await page.getByRole('button',{name:'Read and validate files',exact:true}).click();await page.getByRole('button',{name:'Review editable setup'}).click();
 expect(imports).toBe(1);const recovered=await (await request.get('/api/batches/by-key/'+committedBatch.idempotency_key)).json();expect(recovered.batch.id).toBe(committedBatch.id);await page.unroute('**/api/batches');
 await expect(page.getByText('Missing channel rule: new-source',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Approve rules & run',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Add source rules for review',exact:true}).first().click();await page.getByRole('button',{name:'Check changes',exact:true}).click();
 await expect(page.getByLabel(/^new-source status /)).toHaveCount(75);await expect(page.getByLabel('new-source status State74',{exact:true})).toHaveValue('unreviewed');
 await page.getByLabel('new-source status State74',{exact:true}).selectOption('hold');for(const label of groups)await page.getByLabel(label,{exact:true}).check();await expect(page.getByRole('button',{name:'Approve rules & run',exact:true})).toBeDisabled();
 await page.getByLabel('Master unit',{exact:true}).selectOption('crate');await expect(page.getByLabel('Master unit',{exact:true})).toHaveValue('crate');
});


test('explicit Hold is required, editing clears confirmation, held orders stay isolated',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:/02 Catch a change/}).click();await page.getByRole('button',{name:'Review editable setup'}).click();
 await page.getByLabel('Product alias',{exact:true}).fill('Jasmine500');await page.getByLabel('Confirmed SKU',{exact:true}).fill('TEA-001');await page.getByRole('button',{name:'Confirm alias',exact:true}).click();
 await page.getByLabel('Incoming unit',{exact:true}).fill('carton');await page.getByLabel('Master unit',{exact:true}).selectOption('box');await page.getByRole('button',{name:'Confirm unit',exact:true}).click();
 await page.getByRole('button',{name:'Check changes',exact:true}).click();
 const decision=page.getByLabel('channel-b status Partially shipped',{exact:true});
 await expect(decision).toHaveValue('unreviewed');for(const label of groups)await page.getByLabel(label,{exact:true}).check();
 await expect(page.getByRole('button',{name:'Approve rules & run',exact:true})).toBeDisabled();
 await decision.selectOption('hold');await expect(page.getByLabel('Confirm hold channel-b Partially shipped',{exact:true})).toBeChecked();
 for(const label of groups)await page.getByLabel(label,{exact:true}).check();await expect(page.getByRole('button',{name:'Approve rules & run',exact:true})).toBeEnabled();
 await page.getByLabel('Flow name',{exact:true}).fill('Explicit synthetic status review');await page.getByRole('button',{name:'Check changes',exact:true}).click();
 await expect(decision).toHaveValue('unreviewed');await expect(page.getByLabel('Confirm hold channel-b Partially shipped',{exact:true})).not.toBeChecked();
 for(const label of groups)await page.getByLabel(label,{exact:true}).check();await expect(page.getByRole('button',{name:'Approve rules & run',exact:true})).toBeDisabled();
 await page.screenshot({path:test.info().outputPath('unconfirmed-status-blocked.png'),fullPage:true});
 await page.getByLabel('Confirm hold channel-b Partially shipped',{exact:true}).check();for(const label of groups)await page.getByLabel(label,{exact:true}).check();
 await page.getByRole('button',{name:'Approve rules & run',exact:true}).click();await expect(page.getByText('39 = 24 + 3 + 3 + 9',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:/^Exceptions 9/}).click();await page.getByLabel('Search result rows').fill('Partially shipped');await expect(page.getByText('1–3 of 3',{exact:true})).toBeVisible();
 await expect(page.locator('tbody tr')).toHaveCount(3);await expect(page.getByText('unknown status',{exact:true})).toHaveCount(3);await page.screenshot({path:test.info().outputPath('explicit-hold-isolated.png'),fullPage:true});
});
