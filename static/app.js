const $ = id => document.getElementById(id);
let fieldCount = 0;
let excelSheets = [];
let charts = {};

function esc(v) { return String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'); }

// Tabs
for (const tab of document.querySelectorAll('.tab')) {
    tab.onclick = () => {
        document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(x => x.classList.remove('active'));
        tab.classList.add('active');
        $(tab.dataset.tab).classList.add('active');
    };
}

function addField(data={}) {
    fieldCount++;
    const row = document.createElement('div');
    row.className = 'field-row';
    row.innerHTML = `
      <div class="field-grid">
        <div><label>Tên cột Excel</label><input class="f-name" value="${esc(data.name||'')}" placeholder="Thời gian"></div>
        <div><label>Cách lấy</label><select class="f-mode"><option value="after">Sau từ khóa</option><option value="between">Giữa 2 từ khóa</option><option value="before">Trước từ khóa</option><option value="regex">Regex</option></select></div>
        <div><label>Kiểu dữ liệu</label><select class="f-type"><option value="text">Text</option><option value="date">Date</option><option value="number">Number</option></select></div>
        <div><label>Từ khóa</label><input class="f-marker" value="${esc(data.marker||'')}" placeholder="Ngày:"></div>
        <div class="scope-box"><label>Phạm vi</label><select class="f-scope"><option value="line">Một dòng</option><option value="multiline">Nhiều dòng</option></select></div>
        <div class="end-box"><label>Từ khóa kết thúc</label><input class="f-end" value="${esc(data.end_marker||'')}" placeholder="Số tiền:"></div>
        <div class="regex-box"><label>Biểu thức Regex</label><input class="f-regex" value="${esc(data.regex||'')}" placeholder="Mã:\\s*(\\w+)"></div>
      </div><button class="remove">Xóa trường</button>`;
    $('fields').appendChild(row);
    row.querySelector('.f-mode').value = data.mode || 'after';
    row.querySelector('.f-type').value = data.data_type || 'text';
    row.querySelector('.f-scope').value = data.scope || 'line';
    row.querySelector('.remove').onclick = () => row.remove();
    const refresh = () => {
        const m=row.querySelector('.f-mode').value;
        row.querySelector('.end-box').style.display=m==='between'?'block':'none';
        row.querySelector('.regex-box').style.display=m==='regex'?'block':'none';
        row.querySelector('.scope-box').style.display=m==='after'?'block':'none';
    };
    row.querySelector('.f-mode').onchange=refresh; refresh();
}
addField({name:'Thời gian',mode:'after',data_type:'date',marker:'Ngày:'});
addField({name:'Mã',mode:'after',data_type:'text',marker:'Mã:'});
addField({name:'Tên',mode:'after',data_type:'text',marker:'Tên:'});

function getConfig(){
    const fields=[...document.querySelectorAll('.field-row')].map(r=>({
      name:r.querySelector('.f-name').value.trim(), mode:r.querySelector('.f-mode').value,
      data_type:r.querySelector('.f-type').value, marker:r.querySelector('.f-marker').value,
      scope:r.querySelector('.f-scope').value, end_marker:r.querySelector('.f-end').value,
      regex:r.querySelector('.f-regex').value
    })).filter(x=>x.name);
    return {start_marker:$('startMarker').value,end_marker:$('endMarker').value,no_end_marker:$('noEndMarker').checked,fields};
}

async function sendExtract(endpoint){
    const file=$('file').files[0]; if(!file){alert('Bạn chưa chọn file TXT.');return;}
    const config=getConfig(); if(!config.start_marker||!config.fields.length){alert('Hãy nhập dấu bắt đầu và ít nhất một trường.');return;}
    const form=new FormData(); form.append('file',file); form.append('config',JSON.stringify(config));
    if(endpoint.includes('export')){
      const r=await fetch(endpoint,{method:'POST',body:form});
      if(!r.ok){alert('Xuất Excel thất bại.');return;}
      const blob=await r.blob(), url=URL.createObjectURL(blob), a=document.createElement('a'); a.href=url;a.download='du_lieu_trich_xuat.xlsx';a.click();URL.revokeObjectURL(url);return;
    }
    $('summary').innerHTML='Đang xử lý...'; const r=await fetch(endpoint,{method:'POST',body:form}); const d=await r.json();
    if(!d.ok){$('errors').innerHTML=`<div class="error">${d.errors.join('<br>')}</div>`;return;}
    $('summary').innerHTML=`<b>Tổng số khối:</b> ${d.total_blocks}`;
    $('errors').innerHTML=d.errors?.length?`<div class="warning"><b>Cảnh báo:</b><ul>${d.errors.map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`:'';
    renderTable(d.preview);
}
function renderTable(rows){
    if(!rows.length){$('tableWrap').innerHTML='<p>Không có dữ liệu.</p>';return;}
    const cols=Object.keys(rows[0]); let h='<table><thead><tr>'+cols.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr></thead><tbody>';
    rows.forEach(row=>{h+='<tr>'+cols.map(c=>`<td>${esc(row[c])}</td>`).join('')+'</tr>';}); h+='</tbody></table>'; $('tableWrap').innerHTML=h;
}
$('addField').onclick=()=>addField(); $('previewBtn').onclick=()=>sendExtract('/api/preview'); $('exportBtn').onclick=()=>sendExtract('/api/export');

// Excel analytics
$('excelFile').onchange = async () => {
    const file=$('excelFile').files[0]; if(!file)return;
    const form=new FormData(); form.append('file',file); $('excelInfo').classList.remove('hidden'); $('excelInfo').textContent='Đang đọc file...';
    const r=await fetch('/api/excel/info',{method:'POST',body:form}); const d=await r.json();
    if(!d.ok){$('excelInfo').textContent=d.errors.join('\n');return;}
    excelSheets=d.sheets; $('excelInfo').textContent=`Đã đọc ${d.sheets.length} sheet. Chọn sheet và các cột bên dưới.`;
    const ss=$('sheetSelect'); ss.innerHTML=d.sheets.map((s,i)=>`<option value="${esc(s.sheet)}">${esc(s.sheet)} (${s.rows} dòng)</option>`).join(''); ss.disabled=false;
    populateColumns(); $('analyzeBtn').disabled=false;
};
$('sheetSelect').onchange=populateColumns;
function populateColumns(){
    const sheet=excelSheets.find(s=>s.sheet===$('sheetSelect').value); if(!sheet)return;
    const opts=(allowBlank=true)=> (allowBlank?'<option value="">-- Không chọn --</option>':'')+sheet.columns.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
    for(const id of ['dateCol','profitCol','categoryCol','revenueCol','costCol']){$(id).innerHTML=opts(id!=='dateCol'&&id!=='profitCol');$(id).disabled=false;}
    const find=(terms)=>sheet.columns.find(c=>terms.some(t=>c.toLowerCase().includes(t)));
    const date=find(['ngày','date','time','thời gian']); const profit=find(['lợi nhuận','profit','net profit']); const revenue=find(['doanh thu','revenue']); const cost=find(['chi phí','cost','expense']); const cat=find(['loại','nhóm','category','type']);
    if(date)$('dateCol').value=date; if(profit)$('profitCol').value=profit; if(revenue)$('revenueCol').value=revenue; if(cost)$('costCol').value=cost; if(cat)$('categoryCol').value=cat;
}
$('analyzeBtn').onclick=analyzeExcel;
async function analyzeExcel(){
    const file=$('excelFile').files[0]; if(!file)return;
    if(!$('dateCol').value||!$('profitCol').value){alert('Hãy chọn cột ngày và cột lợi nhuận.');return;}
    const form=new FormData(); form.append('file',file); ['sheet','dateCol','profitCol','categoryCol','revenueCol','costCol'].forEach(id=>form.append(id,$(id).value));
    $('analyzeBtn').disabled=true; $('analyzeBtn').textContent='Đang phân tích...';
    const r=await fetch('/api/excel/analyze',{method:'POST',body:form}); const d=await r.json();
    $('analyzeBtn').disabled=false; $('analyzeBtn').textContent='Phân tích dữ liệu';
    if(!d.ok){$('analyticsResult').classList.remove('hidden');$('analyticsErrors').innerHTML=`<div class="error">${d.errors.join('<br>')}</div>`;return;}
    $('analyticsResult').classList.remove('hidden');
    $('totalProfit').textContent=fmt(d.total_profit); $('avgProfit').textContent=fmt(d.average_profit); $('rowCount').textContent=d.rows.toLocaleString('vi-VN'); $('validCount').textContent=d.valid_rows.toLocaleString('vi-VN');
    $('analyticsErrors').innerHTML=d.errors?.length?`<div class="warning">${d.errors.map(esc).join('<br>')}</div>`:'';
    drawLine('monthlyChart','Lợi nhuận',d.monthly.map(x=>x.period),d.monthly.map(x=>x.value), 'currency');
    drawLine('growthChart','Tăng trưởng (%)',d.monthly_growth.map(x=>x.period),d.monthly_growth.map(x=>x.growth), 'percent');
    drawLine('annualChart','Lợi nhuận',d.annual.map(x=>x.period),d.annual.map(x=>x.value), 'currency');
    drawLine('annualGrowthChart','Tăng trưởng (%)',d.annual_growth.map(x=>x.period),d.annual_growth.map(x=>x.growth), 'percent');
    if(d.category.length){$('categoryCard').style.display='block';drawPie(d.category);}else $('categoryCard').style.display='none';
    if(d.revenue.length||d.cost.length){$('revenueCostCard').style.display='block';drawCombined(d);}else $('revenueCostCard').style.display='none';
}
function fmt(v){return Number(v||0).toLocaleString('vi-VN',{maximumFractionDigits:2});}
function destroy(id){if(charts[id])charts[id].destroy();}
function drawLine(id,label,labels,values,type){destroy(id); charts[id]=new Chart($(id),{type:'line',data:{labels,datasets:[{label,data:values,borderWidth:2,tension:.25,spanGaps:true}]},options:{responsive:true,maintainAspectRatio:false,plugins:{tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${type==='percent'?(c.parsed.y==null?'':c.parsed.y.toFixed(2)+'%'):fmt(c.parsed.y)}`}}},scales:{y:{ticks:{callback:v=>type==='percent'?v+'%':fmt(v)}}}}});}
function drawPie(items){destroy('categoryChart');charts.categoryChart=new Chart($('categoryChart'),{type:'pie',data:{labels:items.map(x=>x.name),datasets:[{data:items.map(x=>x.value)}]},options:{responsive:true,maintainAspectRatio:false,plugins:{tooltip:{callbacks:{label:c=>`${c.label}: ${fmt(c.parsed)}`}}}}});}
function drawCombined(d){destroy('revenueCostChart');const labels=[...new Set([...d.monthly.map(x=>x.period),...d.revenue.map(x=>x.period),...d.cost.map(x=>x.period)])].sort();const map=a=>Object.fromEntries(a.map(x=>[x.period,x.value]));const p=map(d.monthly),r=map(d.revenue),c=map(d.cost);const ds=[{label:'Lợi nhuận',data:labels.map(x=>p[x]??null),borderWidth:2,tension:.25}];if(d.revenue.length)ds.push({label:'Doanh thu',data:labels.map(x=>r[x]??null),borderWidth:2,tension:.25});if(d.cost.length)ds.push({label:'Chi phí',data:labels.map(x=>c[x]??null),borderWidth:2,tension:.25});charts.revenueCostChart=new Chart($('revenueCostChart'),{type:'line',data:{labels,datasets:ds},options:{responsive:true,maintainAspectRatio:false,scales:{y:{ticks:{callback:v=>fmt(v)}}}}});}
